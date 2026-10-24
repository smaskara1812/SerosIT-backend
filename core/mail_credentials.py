"""The password a user signed in with, kept (encrypted, for a limited time) so approval mail can be sent through the SMTP relay as that user. It is
written at sign-in, deleted at sign-out, and ignored once older than CREDENTIAL_TTL (the longest a session can live)."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from . import secret_box
from .models import UserMailCredential


def store(user_id, password):
    UserMailCredential.objects.update_or_create(user_id=user_id, defaults={"password": secret_box.encrypt(password)})


def fetch(user_id):
    """The user's cached password, or None when there is none or it has expired."""
    cred = UserMailCredential.objects.filter(user_id=user_id).first()
    if cred is None:
        return None
    if timezone.now() - cred.updated_at > timedelta(seconds=settings.CREDENTIAL_TTL_SECONDS):
        cred.delete()
        return None
    return secret_box.decrypt(cred.password) or None


def clear(user_id):
    UserMailCredential.objects.filter(user_id=user_id).delete()
