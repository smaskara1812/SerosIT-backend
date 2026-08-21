import base64
import hashlib
import logging

import requests
from django.contrib.auth import get_user_model

from .models import MstUser

logger = logging.getLogger(__name__)

AD_AUTH_URL = "https://mobileservices.essar.com/prod/web/ldap/api/AuthAPI/IsAccountAuthorized/"
AD_TIMEOUT = 10  # seconds


def _sha256(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _check_local_password(mst_user: MstUser, password: str) -> bool | None:
    """
    Returns True  — local password exists and matches
            False — local password exists but does NOT match
            None  — no local password row found (caller should try AD)
    """
    row = getattr(mst_user, "password_row", None)
    if row is None:
        return None
    return row.password_hash == _sha256(password)


def _fetch_mst_user(login_id: str) -> MstUser | None:
    """
    The legacy data has a real, if rare, case of duplicate login_ids (one
    active row + one or more inactive rows, from rehires/name changes).
    Prefer the active one; fall back to the most recently created inactive
    row so the "This account is inactive" path still has something to show.
    """
    rows = list(MstUser.objects.filter(user_login_id__iexact=login_id))
    if not rows:
        return None
    for row in rows:
        if row.user_active == "Y":
            return row
    return max(rows, key=lambda r: r.user_id)


def _authenticate_ad(login_id: str, password: str) -> bool:
    """Calls the Essar AD REST API. Returns True if isSuccess, False otherwise."""
    try:
        headers = {
            "UserID": base64.b64encode(login_id.encode()).decode(),
            "Password": base64.b64encode(password.encode()).decode(),
        }
        resp = requests.get(AD_AUTH_URL, headers=headers, timeout=AD_TIMEOUT)
        if resp.status_code == 200:
            return bool(resp.json().get("isSuccess", False))
    except Exception as exc:
        logger.warning("AD auth request failed for %s: %s", login_id, exc)
    return False


class SerosAuthBackend:
    """
    Authentication order for an Mst_User row:
      1. mst_user_password row exists → SHA-256 compare → allow or reject
      2. No local password row        → AD REST API      → allow or reject

    Inactive users still authenticate here but come back with is_active=False,
    so SimpleJWT's own active-user check rejects the token issuance.
    Users not in Mst_User fall through to ModelBackend (Django superusers).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        mst = _fetch_mst_user(username)
        if mst is None:
            return None  # not in Mst_User → try ModelBackend

        is_active = mst.user_active == "Y"

        if is_active:
            local = _check_local_password(mst, password)
            if local is True:
                pass  # authenticated locally
            elif local is False:
                return None  # wrong password
            else:
                if not _authenticate_ad(mst.user_login_id, password):
                    return None

        User = get_user_model()
        display = mst.user_name[:150]
        user, created = User.objects.get_or_create(
            username=mst.user_login_id,
            defaults={
                "first_name": display,
                "email": mst.user_email or "",
                "is_active": is_active,
            },
        )
        if not created:
            changed = False
            for attr, val in [
                ("first_name", display),
                ("email", mst.user_email or ""),
                ("is_active", is_active),
            ]:
                if getattr(user, attr) != val:
                    setattr(user, attr, val)
                    changed = True
            if changed:
                user.save()

        return user

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
