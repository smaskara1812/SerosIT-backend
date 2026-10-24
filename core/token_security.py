"""Session rules on top of SimpleJWT.

  - The refresh token is rotated on every use (as before) but its expiry is carried over, never extended: a session ends REFRESH_LIFETIME (2 days)
    after sign-in, whatever the user does, and then they sign in again.
  - A session that has been idle for IDLE_TIMEOUT_MINUTES cannot be refreshed. The browser refreshes the access token (15 minutes) when it
    expires and the user is working, so a refresh token that has not been used for this long means nobody was there.
  - An access token that was signed out is refused until its own expiry (sys_revoked_token), so Sign out ends the session at once
    (the authentication class for that is in core/jwt_auth.py, which must not import simplejwt's views: it is loaded while DRF starts).
"""

import time

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.views import TokenRefreshView

from .jwt_auth import revoke_access_token  # noqa: F401  (kept importable from here)


class SerosRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        idle = settings.IDLE_TIMEOUT_MINUTES * 60
        issued = refresh.payload.get("iat")
        if issued and time.time() - int(issued) > idle:
            raise TokenError("The session ended after being idle. Sign in again.")
        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM)
        if user_id:
            user = get_user_model().objects.get(**{api_settings.USER_ID_FIELD: user_id})
            if not api_settings.USER_AUTHENTICATION_RULE(user):
                raise AuthenticationFailed(self.error_messages["no_active_account"], "no_active_account")
        data = {"access": str(refresh.access_token)}
        refresh.blacklist()
        refresh.set_jti()
        refresh.set_iat()  # the expiry is left as it was: rotation never extends a session
        refresh.outstand()
        data["refresh"] = str(refresh)
        return data


class SerosTokenRefreshView(TokenRefreshView):
    serializer_class = SerosRefreshSerializer
