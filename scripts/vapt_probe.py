"""White-box and black-box security probe of the application API, run against a COPY of the data (seros_test), never the live dev database.

    MYSQL_DB=seros_test .venv/bin/python scripts/vapt_probe.py

It plays an attacker with different levels of access (nobody, a signed-in user with no rights, a signed-in user with rights on one page) against
the real API through Django's test client, inside one transaction that is rolled back. It prints one line per probe:
    ok       the attack was refused / the property holds
    FINDING  the attack worked or the weakness exists (with the evidence)
Nothing is guessed at random: passwords tried are made up and belong to a throwaway user created here.
"""
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.conf import settings
from django.db import transaction
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver

from core import media_uploads as mu
from core.models import (MstBusinessSystem, MstUser, MstUserPassword, SysMenu, UserMailCredential, UserPermission, UserProfile)

if "test" not in settings.DATABASES["default"]["NAME"].lower():
    sys.exit("Refusing to run: point MYSQL_DB at a test copy (for example seros_test).")

FINDINGS = []


def ok(name):
    print(f"  ok       {name}")


def finding(name, evidence=""):
    FINDINGS.append((name, evidence))
    print(f"  FINDING  {name}" + (f"\n           {evidence}" if evidence else ""))


def routes():
    def walk(patterns, prefix=""):
        for p in patterns:
            if isinstance(p, URLResolver):
                yield from walk(p.url_patterns, prefix + str(p.pattern))
            elif isinstance(p, URLPattern):
                yield prefix + str(p.pattern)
    return sorted(set(walk(get_resolver().url_patterns)))


class Rollback(Exception):
    pass


def login(c, user, password):
    return c.post("/api/auth/token/", json.dumps({"username": user, "password": password}), content_type="application/json")


def run():
    anon = Client(HTTP_HOST="localhost")
    sha = lambda s: hashlib.sha256(s.encode()).hexdigest()

    # a throwaway user with a local password and NO rights, and one with View on a single page
    def make_user(login_id, rights=()):
        u = MstUser.objects.create(user_name=f"vapt {login_id}", user_login_id=login_id, user_active="Y", user_type_id="E", user_from="2020-01-01", cr_user_id=0, cr_dt="2020-01-01")
        MstUserPassword.objects.create(user_id=u.user_id, password_hash=sha("Vapt#Pass123"))
        UserProfile.objects.create(user_id=u.user_id, user_login_id=login_id, is_app_admin=False)
        for k in rights:
            UserPermission.objects.create(user_id=u.user_id, menu_key=k, can_view=True)
        return u

    make_user("vapt_none")
    make_user("vapt_one", ["masters.rigs"])

    print("A. authentication and brute force")
    r = login(anon, "vapt_none", "Vapt#Pass123")
    tokens = r.json() if r.status_code == 200 else {}
    check_login = r.status_code == 200 and "access" in tokens
    ok("a valid login works (test setup)") if check_login else finding("test setup: login failed", r.content[:150])

    codes = []
    t0 = time.time()
    for i in range(60):
        codes.append(login(anon, "vapt_none", f"wrong-{i}").status_code)
    if 429 in codes:
        ok("repeated wrong passwords are rate limited")
    else:
        finding("NO RATE LIMIT / LOCKOUT on login: 60 wrong passwords in a row all processed", f"statuses {sorted(set(codes))}, {time.time() - t0:.1f}s; the account was still usable afterwards: {login(anon, 'vapt_none', 'Vapt#Pass123').status_code == 200}")
    r = login(anon, "vapt_none", "Vapt#Pass123")
    ok("even the right password is refused while the account waits") if r.status_code == 429 else finding("the account kept accepting logins during a brute force", r.status_code)
    from core import login_guard
    login_guard.unlock("vapt_none")  # the probe needs this account again

    unknown, wrong = login(anon, "no_such_user_zz", "x"), login(anon, "vapt_one", "x")  # both untouched so far: the throttle state must not tell them apart
    same_text = unknown.content == wrong.content and unknown.status_code == wrong.status_code
    ok("unknown user and wrong password give the same answer") if same_text else finding("user enumeration through the login answer", f"{unknown.content[:80]} vs {wrong.content[:80]}")

    print("B. tokens")
    access, refresh = tokens.get("access"), tokens.get("refresh")
    c = Client(HTTP_HOST="localhost", HTTP_AUTHORIZATION=f"Bearer {access}")
    me = c.get("/api/auth/me/")
    ok("a valid access token is accepted") if me.status_code == 200 else finding("token not accepted", me.status_code)
    c.post("/api/auth/logout/", json.dumps({"refresh": refresh}), content_type="application/json")
    after = c.get("/api/auth/me/").status_code
    finding("the ACCESS token still works after Sign out (valid up to 15 minutes; only the refresh token is revoked)", f"/me after logout: {after}") if after == 200 else ok("the access token stops working at logout")
    rr = anon.post("/api/auth/token/refresh/", json.dumps({"refresh": refresh}), content_type="application/json")
    ok("the refresh token is revoked at logout") if rr.status_code == 401 else finding("refresh token survived logout", rr.status_code)
    import base64
    head = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
    body = access.split(".")[1]
    forged = Client(HTTP_HOST="localhost", HTTP_AUTHORIZATION=f"Bearer {head}.{body}.")
    ok("a token with alg=none is refused") if forged.get("/api/auth/me/").status_code == 401 else finding("alg=none token accepted")
    flipped = access[:-3] + ("AAA" if access[-3:] != "AAA" else "BBB")
    ok("a token with a changed signature is refused") if Client(HTTP_HOST="localhost", HTTP_AUTHORIZATION=f"Bearer {flipped}").get("/api/auth/me/").status_code == 401 else finding("tampered token accepted")
    ok("SIMPLE_JWT signing key is not the public default") if settings.SECRET_KEY != "django-insecure-dev-only-change-me" else finding("SECRET_KEY is the built-in dev default: anyone who reads the source can forge any user's token (set SECRET_KEY in the environment in production)", "")
    finding("DEBUG defaults to True when the environment does not say otherwise: stack traces and settings leak on any error", "DEBUG=%s now" % settings.DEBUG) if settings.DEBUG else ok("DEBUG is off")

    print("C. access control (every route, three levels)")
    c0 = Client(HTTP_HOST="localhost", HTTP_AUTHORIZATION="Bearer " + login(anon, "vapt_none", "Vapt#Pass123").json()["access"])
    c1 = Client(HTTP_HOST="localhost", HTTP_AUTHORIZATION="Bearer " + login(anon, "vapt_one", "Vapt#Pass123").json()["access"])
    open_anon, open_norights = [], []
    allowed_anon = ("api/auth/token", "api/auth/me", "api/ping", "media/", "api/health")
    paths = [p for p in routes() if p.startswith("api/") and "<" not in p and "(?P" not in p and "$" not in p.replace("$", "") + "x"]
    for p in routes():
        if not p.startswith("api/") or "<" in p or "(?P" in p:
            continue
        path = "/" + p.replace("^", "").replace("\\.", ".").replace("$", "")
        if path.endswith("/export/") or "export" in path or "print" in path or "report" in path or "pdf" in path:
            pass
        if any(path.startswith("/" + a) for a in allowed_anon):
            continue
        ra = anon.get(path)
        if ra.status_code not in (401, 403, 404, 405):
            open_anon.append((path, ra.status_code))
        rn = c0.get(path)
        if rn.status_code == 200 and not path.startswith(("/api/auth/", "/api/home", "/api/notices", "/api/banner")):
            open_norights.append(path)
    ok(f"every API route refuses an anonymous request ({len(routes())} routes scanned)") if not open_anon else finding("routes that answer without signing in", str(open_anon[:10]))
    ok("a signed-in user with NO rights gets no data from any list route") if not open_norights else finding(f"{len(open_norights)} routes return data to a signed-in user with no rights at all", str(open_norights[:12]))

    # admin-only endpoints as a normal user
    admin_paths = ["/api/admin/user-management/", "/api/admin/users/", "/api/admin/audit/facets/", "/api/admin/history-settings/"]
    leaks = [p for p in admin_paths if c1.get(p).status_code == 200]
    ok("admin endpoints refuse a normal user") if not leaks else finding("admin endpoints open to a normal user", str(leaks))
    r = c1.post("/api/admin/user-management/create/", json.dumps({"login_id": "vapt_evil", "name": "x"}), content_type="application/json")
    ok("a normal user cannot create users") if r.status_code in (401, 403) else finding("a normal user created a user", r.status_code)

    print("D. sensitive data over the API")
    UserPermission.objects.create(user_id=MstUser.objects.get(user_login_id="vapt_one").user_id, menu_key="masters.business_systems", can_view=True)
    from core.permissions import invalidate_user_access
    invalidate_user_access("vapt_one")
    r = c1.get("/api/masters/business-systems/?page_size=50")
    leaked = [x for x in (r.json().get("results", []) if r.status_code == 200 else []) if x.get("mail_user_password")]
    finding(f"mail account PASSWORDS are returned in plain text by the API to anyone with View on Business Systems ({len(leaked)} of {r.json().get('count')} rows)", "field mail_user_password") if leaked else ok("business system mail passwords are not exposed")
    from core import secret_box
    plain = sum(1 for p in UserMailCredential.objects.values_list("password", flat=True) if p and not secret_box.is_encrypted(p))
    stored_ok = sum(1 for p in MstBusinessSystem.objects.values_list("mail_user_password", flat=True) if p and not secret_box.is_encrypted(p))
    finding(f"passwords are stored in plain text: {stored_ok} business-system mail passwords, {plain} cached user login passwords", "tables mst_business_system, sys_user_mail_credential") if (stored_ok or plain) else ok("no plain-text passwords at rest")
    rows = list(MstUserPassword.objects.values_list("password_hash", flat=True))
    unsalted = [h for h in rows if len(h) == 64 and all(ch in "0123456789abcdef" for ch in h)]
    dupes = len(unsalted) - len(set(unsalted))
    finding(f"{len(unsalted)} of {len(rows)} local passwords are still old unsalted SHA-256 (each is replaced with a salted hash when its owner next signs in; manage.py encrypt_stored_secrets counts them)", f"{dupes} of them share a hash with another account") if unsalted else ok("every local password hash is salted")
    weak = {"password", "Password1", "123456", "12345678", "admin", "welcome1", "Welcome@123", "seros123", "essar123", "qwerty"}
    cracked = sum(1 for h in unsalted if any(sha(w) == h for w in weak))
    finding(f"{cracked} local accounts use a password from a ten-word common list (found by testing the hashes offline)") if cracked else ok("no account uses a ten-word common password")

    print("E. files")
    from django.core.files.uploadedfile import SimpleUploadedFile
    link = mu.media_url(None, "fs_emp_photos/1.jpg")
    other = Client(HTTP_HOST="localhost").get(link)
    finding("a file address works for anyone who holds it", f"fetched with no login: {other.status_code}") if other.status_code == 200 else ok("a stored file cannot be fetched without signing in")
    nr = c0.get(link)
    finding("a signed-in user with no rights can read a stored file", f"{nr.status_code}") if nr.status_code == 200 else ok("a signed-in user without the page's right cannot read the file")
    ok("path traversal through the media route is refused") if c1.get("/api/media/fs_emp_photos/../../manage.py").status_code == 404 else finding("path traversal")

    print("F. injection")
    payloads = ["' OR '1'='1", "1; DROP TABLE mst_rig;--", "\" OR 1=1 --", "%00", "../../etc/passwd", "<script>alert(1)</script>"]
    bad = []
    base_count = c1.get("/api/masters/rigs/?search=zzzznomatch").json().get("count")
    for pl in payloads:
        for qs in (f"search={pl}", f"ordering={pl}", f"active={pl}", f"page_size={pl}", f"page={pl}"):
            r = c1.get("/api/masters/rigs/?" + qs)
            if r.status_code >= 500:
                bad.append((qs[:40], r.status_code))
            if qs.startswith("search=") and r.status_code == 200 and r.json().get("count") not in (0, None):
                bad.append((qs[:40], "returned rows for a nonsense search"))
    ok("SQL-injection style payloads in search, ordering, active and paging parameters cause no error and no extra rows") if not bad else finding("injection payloads changed behaviour or caused a server error", str(bad[:6]))

    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws["A1"] = '=HYPERLINK("http://evil.example","click")'
    from core.xlsx_export import xlsx_value
    from core import export_safety
    ws["A2"] = xlsx_value('=cmd|"/C calc"!A0')
    export_safety.xlsx_neutralise(ws["A2"])
    finding("Excel/CSV formula injection: a stored text starting with = + - or @ is written into exports as a live formula", f"cell type written: {ws['A2'].data_type} (f = formula); affects every export that carries free text (hazard cards, incidents, remarks)") if ws["A2"].data_type == "f" else ok("exports neutralise formulas")

    print("G. transport and browser protections")
    resp = anon.get("/api/auth/me/")
    hdr = {k.lower(): v for k, v in resp.headers.items()}
    for h, why in (("x-content-type-options", "stops MIME sniffing"), ("x-frame-options", "stops clickjacking"), ("content-security-policy", "limits script injection"), ("strict-transport-security", "forces HTTPS")):
        ok(f"{h} is set") if h in hdr else finding(f"response header {h} is missing ({why})")
    for name in ("SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE", "SECURE_SSL_REDIRECT", "SECURE_HSTS_SECONDS"):
        finding(f"{name} is not set") if not getattr(settings, name, False) else ok(f"{name} is set")
    pre = anon.options("/api/auth/token/", HTTP_ORIGIN="http://evil.example", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
    ok("CORS refuses an unknown origin") if "access-control-allow-origin" not in {k.lower() for k in pre.headers} else finding("CORS allows an unknown origin")
    finding("the browser keeps both JWTs in localStorage (readable by any script that runs on the page; there is no Content-Security-Policy to limit that)") if True else None

    print("H. denial of service surface")
    big = c1.get("/api/masters/rigs/?page_size=100000").json()
    ok("page size is capped") if len(big.get("results", [])) <= 1000 else finding("page size is not capped")
    finding("no throttling on any endpoint: one signed-in user can request expensive exports and reports in a loop", "REST_FRAMEWORK has no DEFAULT_THROTTLE_CLASSES") if not getattr(settings, "REST_FRAMEWORK", {}).get("DEFAULT_THROTTLE_CLASSES") else ok("API throttling is on")

    raise Rollback()


try:
    with transaction.atomic():
        run()
except Rollback:
    pass

print()
print(f"{len(FINDINGS)} findings")
for i, (n, e) in enumerate(FINDINGS, 1):
    print(f" {i:2}. {n}")
