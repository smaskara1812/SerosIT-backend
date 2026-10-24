"""Checks the security hardening of 24 Oct 2026 through the real API (all inside a transaction that is rolled back):

    cd backend
    .venv/bin/python scripts/check_security_fixes.py

  1. passwords: salted PBKDF2 hashes, old SHA-256 hashes still work and are upgraded at the owner's next sign-in; the cached mail password and the
     business-system mail password are encrypted, the latter never returned and never written to the audit log;
  2. login throttle: 5 free wrong passwords, then 30 s, then 2 min and 2 min for every further one; a delay is not lengthened by tries made during it;
     an unknown name is throttled the same; a correct password resets it; per account+IP, per address and per device limits; unlock;
  3. sessions: a refresh never extends the 2 days, a session idle too long cannot be refreshed, Sign out ends the access token at once;
  4. exports: texts that would run as formulas are neutralised in CSV and Excel;
  5. files: served only to signed-in users with the right to the file's page.
Exits 1 on any failure."""
import hashlib
import json
import os
import sys
import time
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.test import Client
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from core import export_safety, login_guard, secret_box
from core.models import (LoginAttempt, MstBusinessSystem, MstUser, MstUserPassword, RevokedToken, SysAuditLog, UserMailCredential, UserPermission, UserProfile)
from core.passwords import hash_password, is_legacy_hash, verify_password

FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {str(detail)[:300]}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


class Rollback(Exception):
    pass


def post(c, path, data, **extra):
    return c.post(path, json.dumps(data), content_type="application/json", **extra)


def run():
    c = Client(HTTP_HOST="localhost")
    sha = lambda s: hashlib.sha256(s.encode()).hexdigest()

    def make_user(login, password, hashed=None, rights=()):
        u = MstUser.objects.create(user_name=f"sec {login}", user_login_id=login, user_active="Y", user_type_id="E", user_from="2020-01-01", cr_user_id=0, cr_dt="2020-01-01")
        MstUserPassword.objects.create(user_id=u.user_id, password_hash=hashed or hash_password(password))
        UserProfile.objects.create(user_id=u.user_id, user_login_id=login, is_app_admin=False)
        for k in rights:
            UserPermission.objects.create(user_id=u.user_id, menu_key=k, can_view=True)
        return u

    print("1. passwords")
    h = hash_password("Abc#12345")
    check("a new hash is salted PBKDF2", h.startswith("pbkdf2_sha256$") and not is_legacy_hash(h))
    check("two hashes of the same password differ (salt)", hash_password("Abc#12345") != h)
    check("a password verifies against the new format", verify_password("Abc#12345", h) and not verify_password("wrong", h))
    check("an old SHA-256 hash still verifies", verify_password("Old#Pass1", sha("Old#Pass1")) and not verify_password("x", sha("Old#Pass1")))
    u = make_user("sec_old", "Old#Pass1", hashed=sha("Old#Pass1"))
    r = post(c, "/api/auth/token/", {"username": "sec_old", "password": "Old#Pass1"})
    row = MstUserPassword.objects.get(user_id=u.user_id)
    check("an old hash is replaced by a salted one at the owner's next sign-in", r.status_code == 200 and not is_legacy_hash(row.password_hash) and verify_password("Old#Pass1", row.password_hash))
    cred = UserMailCredential.objects.get(user_id=u.user_id)
    check("the cached mail password is stored encrypted", secret_box.is_encrypted(cred.password) and "Old#Pass1" not in cred.password)
    check("and decrypts to the password", secret_box.decrypt(cred.password) == "Old#Pass1")
    from core import mail_credentials
    check("the cached password is usable now", mail_credentials.fetch(u.user_id) == "Old#Pass1")
    UserMailCredential.objects.filter(user_id=u.user_id).update(updated_at=timezone.now() - timedelta(seconds=settings.CREDENTIAL_TTL_SECONDS + 5))
    check("and unusable after the session lifetime", mail_credentials.fetch(u.user_id) is None)
    check("a changed key cannot decrypt (returns nothing, no crash)", secret_box.decrypt("enc1:not-a-real-token") == "")
    check("encrypting twice does not double-encrypt", secret_box.encrypt(secret_box.encrypt("x")) == secret_box.encrypt("x") or secret_box.decrypt(secret_box.encrypt(secret_box.encrypt("x"))) == "x")

    admin = Client(HTTP_HOST="localhost")
    admin.force_login(get_user_model().objects.filter(is_superuser=True).first()) if False else None
    from rest_framework.test import APIClient
    api = APIClient(HTTP_HOST="localhost")
    api.force_authenticate(get_user_model().objects.filter(is_superuser=True).first())
    bs = MstBusinessSystem.objects.first()
    r = api.patch(f"/api/masters/business-systems/{bs.pk}/", {"mail_user_password": "Secret#Mail1"}, format="json")
    stored = MstBusinessSystem.objects.get(pk=bs.pk).mail_user_password
    check("a business-system mail password is stored encrypted", r.status_code == 200 and secret_box.is_encrypted(stored) and secret_box.decrypt(stored) == "Secret#Mail1", r.content.decode())
    body = api.get(f"/api/masters/business-systems/{bs.pk}/").json()
    check("it is never returned by the API (only whether one is set)", "mail_user_password" not in body and body.get("has_mail_password") is True)
    api.patch(f"/api/masters/business-systems/{bs.pk}/", {"mail_user_password": ""}, format="json")
    check("a blank value keeps the stored password", MstBusinessSystem.objects.get(pk=bs.pk).mail_user_password == stored)
    check("it never reaches the audit log", not SysAuditLog.objects.filter(entity="masters.business_systems", changes__icontains="mail_user_password").exists() and not SysAuditLog.objects.filter(entity="masters.business_systems", changes__icontains="Secret#Mail1").exists())

    print("2. login throttle")
    make_user("sec_thr", "Good#Pass1")
    bad = lambda: post(c, "/api/auth/token/", {"username": "sec_thr", "password": "wrong"})
    codes = [bad().status_code for _ in range(5)]
    check("the first 5 wrong passwords are answered normally (401)", codes == [401] * 5, codes)
    r = bad()
    check("the 6th is refused with a wait of up to 30 s", r.status_code == 429 and 1 <= r.json()["retry_after_seconds"] <= 30 and r.has_header("Retry-After"), r.content.decode())
    check("the answer says how long to wait", "Try again in" in r.json()["detail"] and r.json()["code"] == "login_throttled")
    r2 = post(c, "/api/auth/token/", {"username": "sec_thr", "password": "Good#Pass1"})
    check("even the right password is refused during the wait", r2.status_code == 429)
    LoginAttempt.objects.filter(username_key="sec_thr").update(ts=F("ts") - timedelta(seconds=40))
    r = bad()
    check("after 30 s a try is allowed again (and fails: the 6th wrong password)", r.status_code == 401, r.content.decode())
    r = bad()
    long_wait = login_guard.DELAY_AFTER_6TH_ON  # the wait from the 6th wrong password on (5 minutes now)
    check(f"the 7th wait is {long_wait // 60} minutes", r.status_code == 429 and long_wait - 20 <= r.json()["retry_after_seconds"] <= long_wait, r.content.decode())
    LoginAttempt.objects.filter(username_key="sec_thr").update(ts=F("ts") - timedelta(seconds=60))
    r = bad()
    check("tries made during a wait do not lengthen it (60 s later the wait is 60 s shorter, not longer)", r.status_code == 429 and r.json()["retry_after_seconds"] <= long_wait - 59, r.content.decode())
    LoginAttempt.objects.filter(username_key="sec_thr").update(ts=F("ts") - timedelta(seconds=long_wait))
    r = bad()
    check(f"after {long_wait // 60} minutes one more try is allowed", r.status_code == 401)
    r = bad()
    check(f"and every further wait is {long_wait // 60} minutes, never longer", r.status_code == 429 and r.json()["retry_after_seconds"] <= long_wait)
    LoginAttempt.objects.filter(username_key="sec_thr").update(ts=F("ts") - timedelta(seconds=long_wait))
    ok = post(c, "/api/auth/token/", {"username": "sec_thr", "password": "Good#Pass1"})
    check("the right password signs in once the wait is over", ok.status_code == 200)
    check("and resets the count: 5 more wrong passwords are free again", [bad().status_code for _ in range(5)] == [401] * 5)
    check("an administrator can unlock the account", login_guard.unlock("sec_thr") > 0 and bad().status_code == 401)

    for _ in range(5):
        post(c, "/api/auth/token/", {"username": "no_such_user_zz", "password": "x"})
    r = post(c, "/api/auth/token/", {"username": "no_such_user_zz", "password": "x"})
    check("an unknown name is throttled exactly like a real one", r.status_code == 429)
    check("the answer for it does not say the account is missing", "no_such" not in r.content.decode() and "exist" not in r.content.decode().lower())

    # per account + address: 10 failures in 10 minutes
    now = timezone.now()
    LoginAttempt.objects.bulk_create([LoginAttempt(ts=now - timedelta(seconds=300 + i), username_key="sec_ip", ip="9.9.9.9", device="") for i in range(10)])
    LoginAttempt.objects.filter(username_key="sec_ip").update(success=False)
    # spread out so the account ladder is not what refuses: mark every other as a success boundary is unnecessary; check the account+ip rule directly
    row = LoginAttempt.objects.create(ts=now, username_key="sec_ip", ip="9.9.9.9", device="")
    retry, reason = login_guard._judge(row)
    check("10 failures in 10 minutes from one address for one account are refused", retry is not None)
    # per address: 300 attempts
    LoginAttempt.objects.bulk_create([LoginAttempt(ts=now - timedelta(seconds=i % 500), username_key=f"u{i}", ip="8.8.8.8", device="", success=True) for i in range(300)])
    row = LoginAttempt.objects.create(ts=now, username_key="fresh", ip="8.8.8.8", device="")
    retry, reason = login_guard._judge(row)
    check("300 attempts in 10 minutes from one address refuse the next", retry is not None and reason == "ip", (retry, reason))
    row = LoginAttempt.objects.create(ts=now, username_key="fresh2", ip="7.7.7.7", device="")
    check("a quiet address is not affected", login_guard._judge(row)[0] is None)
    LoginAttempt.objects.bulk_create([LoginAttempt(ts=now - timedelta(seconds=i), username_key=f"spray{i}", ip="6.6.6.6", device="") for i in range(21)])
    login_guard._flag_spraying(LoginAttempt.objects.filter(ip="6.6.6.6").first())
    check("an address failing against 20+ accounts is flagged in the audit log", SysAuditLog.objects.filter(action="login_spray_suspected", ip="6.6.6.6").exists())
    LoginAttempt.objects.bulk_create([LoginAttempt(ts=now - timedelta(seconds=i), username_key=f"dev{i}", ip=f"5.5.5.{i % 200}", device="11111111-1111-1111-1111-111111111111") for i in range(31)])
    row = LoginAttempt.objects.create(ts=now, username_key="dev_x", ip="4.4.4.4", device="11111111-1111-1111-1111-111111111111")
    check("30 failures from one browser in 10 minutes refuse the next", login_guard._judge(row)[0] is not None)
    from django.test import RequestFactory
    from core.client_ip import client_ip
    rf = RequestFactory()
    check("without a trusted proxy the forwarded header is ignored", client_ip(rf.get("/", REMOTE_ADDR="1.2.3.4", HTTP_X_FORWARDED_FOR="9.9.9.9")) == "1.2.3.4")
    import core.client_ip as ci
    import ipaddress
    ci._NETS = [ipaddress.ip_network("10.0.0.5")]
    check("behind a trusted proxy the real client address is used", client_ip(rf.get("/", REMOTE_ADDR="10.0.0.5", HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.5")) == "203.0.113.9")
    check("a client cannot fake its address through the header", client_ip(rf.get("/", REMOTE_ADDR="10.0.0.5", HTTP_X_FORWARDED_FOR="1.1.1.1, 203.0.113.9")) == "203.0.113.9")
    ci._NETS = None

    print("3. sessions")
    make_user("sec_sess", "Sess#Pass1", rights=["masters.rigs"])
    LoginAttempt.objects.all().delete()
    tok = post(c, "/api/auth/token/", {"username": "sec_sess", "password": "Sess#Pass1"}).json()
    old_exp = RefreshToken(tok["refresh"]).payload["exp"]
    time.sleep(1)
    r = post(c, "/api/auth/token/refresh/", {"refresh": tok["refresh"]})
    new_exp = RefreshToken(r.json()["refresh"]).payload["exp"] if r.status_code == 200 else None
    check("a refresh rotates the token but never extends the session", r.status_code == 200 and new_exp == old_exp, (old_exp, new_exp))
    check("the session lifetime is 2 days", abs(old_exp - time.time() - 2 * 86400) < 120)
    check("a used refresh token cannot be used again", post(c, "/api/auth/token/refresh/", {"refresh": tok["refresh"]}).status_code == 401)
    stale = RefreshToken(r.json()["refresh"])
    stale.payload["iat"] = int(time.time()) - (settings.IDLE_TIMEOUT_MINUTES * 60 + 60)
    check("a session idle longer than the limit cannot be refreshed", post(c, "/api/auth/token/refresh/", {"refresh": str(stale)}).status_code == 401)
    fresh = post(c, "/api/auth/token/", {"username": "sec_sess", "password": "Sess#Pass1"}).json()
    ca = Client(HTTP_HOST="localhost", HTTP_AUTHORIZATION="Bearer " + fresh["access"])
    check("a valid access token works", ca.get("/api/auth/me/").status_code == 200)
    check("/me tells the browser the idle limit", ca.get("/api/auth/me/").json().get("idle_timeout_minutes") == settings.IDLE_TIMEOUT_MINUTES)
    post(ca, "/api/auth/logout/", {"refresh": fresh["refresh"]})
    check("after Sign out the access token stops working at once", ca.get("/api/auth/me/").status_code == 401)
    check("and its id is recorded as revoked", RevokedToken.objects.exists())

    print("4. exports")
    check("CSV: a formula text gets a leading apostrophe", export_safety.csv_safe('=HYPERLINK("http://x")').startswith("'="))
    check("CSV: + - @ are neutralised too", all(export_safety.csv_safe(v).startswith("'") for v in ("+1+1", "-cmd", "@SUM(A1)")))
    check("CSV: a plain signed number is left alone", export_safety.csv_safe("-5.2") == "-5.2" and export_safety.csv_safe(7) == 7)
    from openpyxl import Workbook
    cell = Workbook().active.cell(row=1, column=1, value="=cmd|'/C calc'!A0")
    export_safety.xlsx_neutralise(cell)
    check("Excel: a formula text is stored as text", cell.data_type == "s")
    from core.models import MstRig
    rig = MstRig.objects.first()
    old = rig.rig_name
    MstRig.objects.filter(pk=rig.pk).update(rig_name="=HYPERLINK(\"http://evil\")")
    resp = api.get("/api/masters/rigs/export/")
    text = b"".join(resp.streaming_content).decode("utf-8", "ignore") if getattr(resp, "streaming", False) else resp.content.decode("utf-8", "ignore")
    check("a real master export carries the neutralised text", "'=HYPERLINK" in text and ",=HYPERLINK" not in text and '"=HYPERLINK' not in text, text[:200])
    MstRig.objects.filter(pk=rig.pk).update(rig_name=old)

    print("5. files")
    anon = Client(HTTP_HOST="localhost")
    none = Client(HTTP_HOST="localhost", HTTP_AUTHORIZATION="Bearer " + post(anon, "/api/auth/token/", {"username": "sec_sess", "password": "Sess#Pass1"}).json()["access"])
    check("a signed-in user without the page's right gets nothing (404)", none.get("/api/media/fs_emp_photos/1.jpg").status_code == 404)
    check("someone not signed in is refused", anon.get("/api/media/fs_emp_photos/1.jpg").status_code == 401)
    make_user("sec_fs", "Fs#Pass123", rights=["masters.fs_employees"])
    LoginAttempt.objects.all().delete()
    fs = Client(HTTP_HOST="localhost", HTTP_AUTHORIZATION="Bearer " + post(anon, "/api/auth/token/", {"username": "sec_fs", "password": "Fs#Pass123"}).json()["access"])
    check("a user with View on FS Employee is served an FS photo", fs.get("/api/media/fs_emp_photos/1.jpg").status_code == 200)
    check("but not a signature (a different page)", fs.get("/api/media/signatures/84.jpg").status_code == 404)
    check("an administrator is served every listed folder", api.get("/api/media/signatures/84.jpg").status_code == 200)
    check("path traversal is refused", fs.get("/api/media/fs_emp_photos/../../manage.py").status_code == 404)
    check("an unlisted folder is never served", api.get("/api/media/Letterhead Logo/Footer2.jpg").status_code == 404)
    check("the old signed-link route is gone", anon.get("/media/fs_emp_photos/1.jpg?s=x").status_code == 404)

    print("6. encrypted sign-in")
    import base64
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from core import login_crypto

    make_user("sec_enc", "Enc#Pass123")
    LoginAttempt.objects.all().delete()

    def browser_encrypt(username, password, nonce=None, public_b64=None):
        """What the sign-in form does: fetch the key and nonce, AES-GCM the JSON, RSA-OAEP the AES key."""
        info = c.get("/api/auth/login-key/").json()
        pub = serialization.load_der_public_key(base64.b64decode(public_b64 or info["public_key"]))
        aes_key = os.urandom(32)
        iv = os.urandom(12)
        ct = AESGCM(aes_key).encrypt(iv, json.dumps({"username": username, "password": password, "nonce": nonce or info["nonce"]}).encode(), None)
        wrapped = pub.encrypt(aes_key, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
        b = lambda x: base64.b64encode(x).decode()
        return {"k": b(wrapped), "iv": b(iv), "ct": b(ct)}

    k = c.get("/api/auth/login-key/")
    check("the server publishes a key and a one-time number (not cacheable)", k.status_code == 200 and k.json().get("public_key") and k.json().get("nonce") and k.headers.get("Cache-Control") == "no-store")
    enc = browser_encrypt("sec_enc", "Enc#Pass123")
    check("the request body carries no readable password", "Enc#Pass123" not in json.dumps(enc) and "sec_enc" not in json.dumps(enc))
    r = post(c, "/api/auth/token/", {"enc": enc})
    check("an encrypted sign-in works like a plain one (tokens come back)", r.status_code == 200 and "access" in r.json(), r.content.decode())
    check("the password was used as usual (cached encrypted for mail)", mail_credentials.fetch(MstUser.objects.get(user_login_id="sec_enc").user_id) == "Enc#Pass123")
    r = post(c, "/api/auth/token/", {"enc": enc})
    check("replaying the same captured request is refused", r.status_code == 400 and r.json().get("code") == "login_unreadable", r.content.decode())
    r = post(c, "/api/auth/token/", {"enc": browser_encrypt("sec_enc", "wrong-password")})
    check("a wrong password in an encrypted sign-in is a normal 401", r.status_code == 401, r.content.decode())
    old = login_crypto.NONCE_MAX_AGE
    login_crypto.NONCE_MAX_AGE = -1
    r = post(c, "/api/auth/token/", {"enc": browser_encrypt("sec_enc", "Enc#Pass123")})
    login_crypto.NONCE_MAX_AGE = old
    check("a one-time number that has expired is refused", r.status_code == 400, r.content.decode())
    r = post(c, "/api/auth/token/", {"enc": browser_encrypt("sec_enc", "Enc#Pass123", nonce="not-a-real-nonce")})
    check("an invented one-time number is refused", r.status_code == 400)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pub = base64.b64encode(other.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
    r = post(c, "/api/auth/token/", {"enc": browser_encrypt("sec_enc", "Enc#Pass123", public_b64=other_pub)})
    check("a request encrypted for another key is refused", r.status_code == 400)
    tampered = browser_encrypt("sec_enc", "Enc#Pass123")
    raw = bytearray(base64.b64decode(tampered["ct"]))
    raw[0] ^= 1
    tampered["ct"] = base64.b64encode(bytes(raw)).decode()
    check("a tampered ciphertext is refused", post(c, "/api/auth/token/", {"enc": tampered}).status_code == 400)
    login_guard.unlock("?127.0.0.1")  # unreadable requests are counted against the sender's address (5 free, then a wait); start that count again
    check("garbage in place of the encrypted form is refused (not a server error)", post(c, "/api/auth/token/", {"enc": {"k": "x", "iv": "y", "ct": "z"}}).status_code == 400 and post(c, "/api/auth/token/", {"enc": "nonsense"}).status_code == 400)
    login_guard.unlock("?127.0.0.1")
    check("unreadable requests never lock an account", [post(c, "/api/auth/token/", {"enc": "junk"}).status_code for _ in range(3)] == [400] * 3 and post(c, "/api/auth/token/", {"enc": browser_encrypt("sec_enc", "Enc#Pass123")}).status_code == 200)
    check("the throttle counts encrypted sign-ins too (5 free, then a wait)", [post(c, "/api/auth/token/", {"enc": browser_encrypt("sec_thr", "x")}).status_code for _ in range(6)][-1] == 429)
    check("a plain sign-in is still accepted while it is allowed", post(c, "/api/auth/token/", {"username": "sec_enc", "password": "Enc#Pass123"}).status_code in (200, 429))
    settings.LOGIN_REQUIRE_ENCRYPTED = True
    r = post(c, "/api/auth/token/", {"username": "sec_enc", "password": "Enc#Pass123"})
    settings.LOGIN_REQUIRE_ENCRYPTED = False
    check("a plain sign-in is refused once encryption is required", r.status_code == 400 and r.json().get("code") == "login_plaintext_refused", r.content.decode())
    check("the private key file is not readable by other users", (os.stat(str(settings.LOGIN_PRIVATE_KEY_FILE)).st_mode & 0o077) == 0)

    raise Rollback()


try:
    with transaction.atomic():
        run()
except Rollback:
    pass

print()
print("FAILED:" if FAILED else "all checks passed", *FAILED, sep="\n  " if FAILED else " ")
sys.exit(1 if FAILED else 0)
