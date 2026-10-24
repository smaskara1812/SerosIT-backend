"""JWT authentication with sign-out: an access token whose jti is in sys_revoked_token is refused until it would have expired anyway.
Kept apart from core/token_security.py because DRF imports this module while it is starting up, before simplejwt's views can be imported."""

from datetime import datetime

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings

from .models import RevokedToken


class SerosJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        token = super().get_validated_token(raw_token)
        if RevokedToken.objects.filter(jti=token.get(api_settings.JTI_CLAIM)).exists():
            raise InvalidToken("This sign-in has ended.")
        return token


def revoke_access_token(token):
    """Refuse this access token from now on (called at sign-out)."""
    jti = token.get(api_settings.JTI_CLAIM)
    exp = token.get("exp")
    if jti and exp:
        RevokedToken.objects.update_or_create(jti=jti, defaults={"expires_at": datetime.fromtimestamp(int(exp))})
