"""Encryption at rest for the few secrets the app must be able to read back (a password used to send mail as a user, a mail account password).
Fernet (AES-128-CBC with an HMAC) from the `cryptography` package. The key comes from the environment variable CREDENTIAL_KEY (a Fernet key;
several, comma separated, allow rotation: the first encrypts, all decrypt). Without it a key is derived from SECRET_KEY, which is fine for
development but means anyone with SECRET_KEY can decrypt: set CREDENTIAL_KEY in production, kept outside the database and the source.

A stored value is "enc1:<token>". A value without that prefix is treated as legacy plain text and returned as is, so old rows keep working until
they are rewritten (manage.py encrypt_stored_secrets does that in one go)."""

import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings

logger = logging.getLogger(__name__)
PREFIX = "enc1:"


def _fernet():
    keys = [k.strip() for k in os.getenv("CREDENTIAL_KEY", "").split(",") if k.strip()]
    if not keys:
        digest = hashlib.sha256(("seros-credential-key:" + settings.SECRET_KEY).encode()).digest()
        keys = [base64.urlsafe_b64encode(digest).decode()]
    return MultiFernet([Fernet(k.encode()) for k in keys])


def encrypt(text):
    if text is None or text == "" or str(text).startswith(PREFIX):
        return text
    return PREFIX + _fernet().encrypt(str(text).encode()).decode()


def decrypt(value):
    """The plain text, or "" when an encrypted value cannot be read (wrong key)."""
    if value is None or value == "":
        return value
    value = str(value)
    if not value.startswith(PREFIX):
        return value
    try:
        return _fernet().decrypt(value[len(PREFIX):].encode()).decode()
    except InvalidToken:
        logger.error("A stored secret could not be decrypted (is CREDENTIAL_KEY the key it was written with?)")
        return ""


def rotate(value):
    """The same secret re-encrypted with the first (newest) key, for after CREDENTIAL_KEY gained a new key at the front."""
    if not is_encrypted(value):
        return value
    try:
        return PREFIX + _fernet().rotate(value[len(PREFIX):].encode()).decode()
    except InvalidToken:
        return value


def is_encrypted(value):
    return bool(value) and str(value).startswith(PREFIX)
