"""
Django settings for config project.
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env_list(name, default=""):
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ── Core ─────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-only-change-me")
DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")


# ── Applications ─────────────────────────────────────────────────────────

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "core",
]

# Mst_User local-password/AD check first, ModelBackend after (for the Django
# superuser account, which isn't in Mst_User at all).
AUTHENTICATION_BACKENDS = [
    "core.auth_backend.SerosAuthBackend",
    "django.contrib.auth.backends.ModelBackend",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # CorsMiddleware must sit above CommonMiddleware (and as early as
    # possible generally) so CORS headers land on every response, including
    # error responses.
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ── Database ─────────────────────────────────────────────────────────────
# Toggle with DB_ENGINE in .env — "mysql" for dev, "mssql" for prod.
# Everything else in the app is identical either way.

DB_ENGINE = os.getenv("DB_ENGINE", "mysql")

if DB_ENGINE == "mssql":
    DATABASES = {
        "default": {
            "ENGINE": "mssql",
            "NAME": os.getenv("MSSQL_DB", ""),
            "USER": os.getenv("MSSQL_USER", ""),
            "PASSWORD": os.getenv("MSSQL_PASSWORD", ""),
            "HOST": os.getenv("MSSQL_HOST", "localhost"),
            "PORT": os.getenv("MSSQL_PORT", "1433"),
            # Without this, Django opens a fresh ODBC connection (TCP +
            # driver init + SQL Server login) on every single request and
            # tears it down at the end — negligible over MySQL on
            # localhost, but a real tens-to-hundreds-of-ms tax per API call
            # over pyodbc. Reusing the connection for this long instead is
            # the single biggest lever for API latency on this backend.
            "CONN_MAX_AGE": int(os.getenv("MSSQL_CONN_MAX_AGE", "600")),
            "OPTIONS": {
                "driver": os.getenv("MSSQL_DRIVER", "ODBC Driver 17 for SQL Server"),
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("MYSQL_DB", "serosit"),
            "USER": os.getenv("MYSQL_USER", "root"),
            "PASSWORD": os.getenv("MYSQL_PASSWORD", ""),
            "HOST": os.getenv("MYSQL_HOST", "localhost"),
            "PORT": os.getenv("MYSQL_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }


# ── CORS ─────────────────────────────────────────────────────────────────
# Explicit allowlist only — never CORS_ALLOW_ALL_ORIGINS. Only matters while
# frontend and backend run on separate origins (Vite's dev proxy avoids
# needing this at all during normal local dev).

CORS_ALLOWED_ORIGINS = _env_list(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "x-csrftoken",
    "x-requested-with",
]


# ── DRF / JWT ────────────────────────────────────────────────────────────

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    # Masters list endpoints can grow past what's sane to ship in one
    # response (imported legacy data alone already puts some in the
    # hundreds) — paginate by default so list pages lazy-load instead of
    # transferring and holding the whole table client-side. Endpoints used
    # purely as dropdown sources ask for a bigger page via ?page_size=.
    "DEFAULT_PAGINATION_CLASS": "core.pagination.MastersPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_FILTER_BACKENDS": ("rest_framework.filters.SearchFilter",),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}


# ── Password validation ──────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ── Internationalization ─────────────────────────────────────────────────

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# ── Static files ──────────────────────────────────────────────────────────

STATIC_URL = "static/"

# ── Media (user-uploaded files, e.g. interviewer signatures) ────────────────

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
