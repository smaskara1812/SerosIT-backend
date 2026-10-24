"""Local password hashing. New and changed passwords use Django's salted, slow PBKDF2-SHA256 ("pbkdf2_sha256$600000$salt$hash"). The older
unsalted SHA-256 hashes (64 hex characters, from the legacy system) still verify, and are replaced with the new format the first time their
owner signs in, so nobody has to reset anything."""

import hashlib
import hmac
import re

from django.contrib.auth.hashers import check_password, make_password

_LEGACY = re.compile(r"^[0-9a-f]{64}$")


def is_legacy_hash(stored):
    return bool(_LEGACY.match(stored or ""))


def hash_password(password):
    return make_password(password)


def verify_password(password, stored):
    """True when `password` matches `stored` (either format). Constant-time comparison."""
    if not stored:
        return False
    if is_legacy_hash(stored):
        return hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(), stored)
    return check_password(password, stored)
