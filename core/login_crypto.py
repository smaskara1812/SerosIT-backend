"""Encrypted sign-in. The sign-in form never sends the password as plain text: the browser fetches a public key and a one-time number from the
server, encrypts {username, password, nonce} and sends only the ciphertext. Anyone watching the request (the browser's network tab, a reverse
proxy, a firewall or other logging that records request bodies) sees an unreadable blob; the server decrypts it and carries on exactly as if it had
received the plain text.

Hybrid scheme (what the browser's WebCrypto supports): a fresh AES-256-GCM key encrypts the JSON, and the server's RSA-2048 public key (OAEP,
SHA-256) encrypts that AES key. The one-time number is signed by the server, valid for two minutes, and may be used once (a captured request cannot
be replayed). This sits on top of HTTPS, it does not replace it. The RSA key lives in LOGIN_PRIVATE_KEY_FILE (created on first use); it protects
no stored data, so replacing it only affects sign-ins in progress."""

import base64
import json
import os
import secrets

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core import signing

NONCE_SALT = "seros.login.nonce"
NONCE_MAX_AGE = 120  # seconds

_key = None


class LoginDecryptError(Exception):
    pass


def _private_key():
    global _key
    if _key is None:
        path = str(settings.LOGIN_PRIVATE_KEY_FILE)
        if os.path.isfile(path):
            with open(path, "rb") as fh:
                _key = serialization.load_pem_private_key(fh.read(), password=None)
        else:
            _key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            pem = _key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as fh:
                fh.write(pem)
    return _key


def public_key_b64():
    der = _private_key().public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return base64.b64encode(der).decode()


def issue_nonce():
    return signing.TimestampSigner(salt=NONCE_SALT).sign(secrets.token_urlsafe(16))


def nonce_is_valid(nonce):
    try:
        signing.TimestampSigner(salt=NONCE_SALT).unsign(nonce, max_age=NONCE_MAX_AGE)
        return True
    except signing.BadSignature:
        return False


def decrypt_login(enc):
    """{"username", "password", "nonce"} from the browser's {"k", "iv", "ct"} (all base64), or raises LoginDecryptError."""
    try:
        wrapped, iv, ct = (base64.b64decode(enc[x], validate=True) for x in ("k", "iv", "ct"))
        aes_key = _private_key().decrypt(wrapped, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
        data = json.loads(AESGCM(aes_key).decrypt(iv, ct, None).decode())
        if not isinstance(data, dict) or not all(isinstance(data.get(f), str) for f in ("username", "password", "nonce")):
            raise ValueError("shape")
        return data
    except Exception as exc:
        raise LoginDecryptError(str(exc)) from exc
