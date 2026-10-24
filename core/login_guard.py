"""Throttle for sign-in attempts. Delays, never hard locks, so nobody can lock a real user out by typing their name.

Rules (all counted from the sys_login_attempt table, shared by every server worker):
  per account    5 wrong passwords in a row are free; after the 5th the next try must wait 30 s, after the 6th and every later one DELAY_AFTER_6TH_ON (5 min).
                 A correct password resets it. Attempts made during a wait are refused and do NOT lengthen it.
  per account+IP at most 10 failures in 10 minutes.
  per device     at most 30 failures in 10 minutes (a random cookie, an extra key; a person who clears it only gets a new key).
  per IP         at most 300 attempts in 10 minutes (high enough for an office behind one address), and an address failing against 20 or more
                 different accounts in 10 minutes is flagged in the audit log.
An unknown user name is throttled exactly like a real one (the key is the typed name), so the answer never says whether an account exists.

An attempt is written BEFORE the password is checked, and judged against the rows in time order afterwards, so a burst of parallel requests cannot
slip past the limit while the first ones are still being checked."""

import math
import random
import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone

from .client_ip import client_ip
from .models import LoginAttempt

FREE_FAILURES = 5
DELAY_AFTER_5TH = 30
DELAY_AFTER_6TH_ON = 300
WINDOW = timedelta(minutes=10)
ACCOUNT_IP_MAX = 10
DEVICE_MAX = 30
IP_MAX = 300
SPRAY_ACCOUNTS = 20
KEEP = timedelta(days=2)
DEVICE_COOKIE = "seros_device"


def username_key(name):
    return (name or "").strip().lower()[:60]


def delay_after(failure_number):
    """Seconds to wait after the nth consecutive failure."""
    if failure_number < FREE_FAILURES:
        return 0
    return DELAY_AFTER_5TH if failure_number == FREE_FAILURES else DELAY_AFTER_6TH_ON


class Attempt:
    """The handle for one sign-in attempt: `blocked` is None, or the seconds the caller must wait."""

    def __init__(self, row, retry_after=None, reason="", new_device=False):
        self.row, self.retry_after, self.reason, self.new_device = row, retry_after, reason, new_device

    @property
    def blocked(self):
        return self.retry_after is not None

    def succeeded(self):
        if self.row is not None and not self.blocked:
            LoginAttempt.objects.filter(pk=self.row.pk).update(success=True)

    def failed(self):
        if self.row is not None and not self.blocked:
            _flag_spraying(self.row)


def _retry(seconds):
    return max(1, int(math.ceil(seconds)))


def begin(request, username, nonce=""):
    now = timezone.now()
    if random.random() < 0.01:  # housekeeping, now and then
        LoginAttempt.objects.filter(ts__lt=now - KEEP).delete()
    from .models import RevokedToken

    if random.random() < 0.01:
        RevokedToken.objects.filter(expires_at__lt=now).delete()
    key, ip = username_key(username), client_ip(request)
    device = request.COOKIES.get(DEVICE_COOKIE, "")
    new_device = False
    try:
        uuid.UUID(device)
    except ValueError:
        device, new_device = str(uuid.uuid4()), True
    row = LoginAttempt.objects.create(ts=now, username_key=key, ip=ip, device=device, nonce=nonce)
    retry, reason = _judge(row)
    if retry is not None:
        LoginAttempt.objects.filter(pk=row.pk).update(blocked=True)
        return Attempt(row, retry, reason, new_device)
    return Attempt(row, None, "", new_device)


def _judge(row):
    """(seconds to wait, reason) when this attempt must be refused, else (None, "")."""
    now = row.ts
    # 1. the account's wait ladder, from the failures since its last success, in time order
    last_ok = LoginAttempt.objects.filter(username_key=row.username_key, success=True).aggregate(m=models.Max("ts"))["m"]
    q = LoginAttempt.objects.filter(username_key=row.username_key, success=False, blocked=False, ts__lte=row.ts)
    if last_ok:
        q = q.filter(ts__gt=last_ok)
    seq = list(q.order_by("ts", "pk").values_list("pk", "ts"))
    pks = [p for p, _ in seq]
    if row.pk in pks:
        k = pks.index(row.pk)  # 0-based: this is failure number k+1
        if k >= FREE_FAILURES:
            prev_ts = seq[k - 1][1]
            wait = delay_after(k) - (row.ts - prev_ts).total_seconds()
            if wait > 0:
                return _retry(wait), "account"
    # 2. this account from this address
    since = now - WINDOW
    fq = LoginAttempt.objects.filter(username_key=row.username_key, ip=row.ip, success=False, blocked=False, ts__gte=since, ts__lte=now)
    if last_ok:  # a correct password starts the count again
        fq = fq.filter(ts__gt=last_ok)
    fails = list(fq.order_by("ts", "pk").values_list("ts", flat=True))
    if len(fails) > ACCOUNT_IP_MAX:
        return _retry((fails[len(fails) - 1 - ACCOUNT_IP_MAX] + WINDOW - now).total_seconds()), "account_ip"
    # 3. this browser
    if row.device:
        d = list(LoginAttempt.objects.filter(device=row.device, success=False, blocked=False, ts__gte=since, ts__lte=now).order_by("ts", "pk").values_list("ts", flat=True))
        if len(d) > DEVICE_MAX:
            return _retry((d[len(d) - 1 - DEVICE_MAX] + WINDOW - now).total_seconds()), "device"
    # 4. this address, all attempts
    a = list(LoginAttempt.objects.filter(ip=row.ip, blocked=False, ts__gte=since, ts__lte=now).order_by("ts", "pk").values_list("ts", flat=True))
    if len(a) > IP_MAX:
        return _retry((a[len(a) - 1 - IP_MAX] + WINDOW - now).total_seconds()), "ip"
    return None, ""


def _flag_spraying(row):
    """An address failing against many different accounts is written to the audit log (once an hour per address)."""
    since = row.ts - WINDOW
    names = LoginAttempt.objects.filter(ip=row.ip, success=False, blocked=False, ts__gte=since).values("username_key").distinct().count()
    if names >= SPRAY_ACCOUNTS:
        from .models import SysAuditLog

        if not SysAuditLog.objects.filter(action="login_spray_suspected", ip=row.ip, ts__gte=row.ts - timedelta(hours=1)).exists():
            SysAuditLog.objects.create(
                user_id=None, username="", action="login_spray_suspected", entity="auth", entity_label="Authentication", record_id="",
                record_label=row.ip[:200], changes={"accounts_tried_in_10_min": names}, ip=row.ip, user_agent="", target_table="", target_pk="",
                batch_id="", source="api", kind="event", note="")


def was_recently_refused(row_key, before, minutes=10):
    return LoginAttempt.objects.filter(username_key=row_key, blocked=True, ts__lt=before, ts__gte=before - timedelta(minutes=minutes)).exists()


def unlock(username):
    """Clears an account's wait (an administrator's override). Returns the number of rows removed."""
    return LoginAttempt.objects.filter(username_key=username_key(username)).delete()[0]


def status():
    """Accounts waiting now and addresses flagged lately, for the admin page."""
    now = timezone.now()
    waiting = []
    for key in LoginAttempt.objects.filter(success=False, blocked=False, ts__gte=now - timedelta(hours=1)).values_list("username_key", flat=True).distinct():
        last_ok = LoginAttempt.objects.filter(username_key=key, success=True).aggregate(m=models.Max("ts"))["m"]
        q = LoginAttempt.objects.filter(username_key=key, success=False, blocked=False)
        if last_ok:
            q = q.filter(ts__gt=last_ok)
        rows = list(q.order_by("ts", "pk").values_list("ts", flat=True))
        if len(rows) >= FREE_FAILURES:
            wait = delay_after(len(rows)) - (now - rows[-1]).total_seconds()
            waiting.append({"username": key, "failures": len(rows), "last_failure": rows[-1], "wait_seconds": max(0, int(wait))})
    from .models import SysAuditLog

    flagged = list(SysAuditLog.objects.filter(action="login_spray_suspected", ts__gte=now - timedelta(days=2)).order_by("-ts").values("ts", "ip", "changes")[:20])
    refused = LoginAttempt.objects.filter(blocked=True, ts__gte=now - timedelta(hours=1)).count()
    return {"waiting": sorted(waiting, key=lambda w: -w["failures"]), "flagged_addresses": flagged, "refused_last_hour": refused}
