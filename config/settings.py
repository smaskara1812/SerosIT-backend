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

# The project's own apps. THE one list: exports, imports, History and revert, the admin site, the self-test and the structure check all
# read it (core/project_apps.py). A new app goes here and nowhere else; the structure check fails if an app folder is missing from it.
PROJECT_APPS = ["core", "hr"]

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
    *PROJECT_APPS,
]

# django-silk is a request/query profiler that works on plain JSON API
# responses (unlike Django Debug Toolbar, which injects itself into an HTML
# body and has nothing to inject into here — this is a DRF API with no
# server-rendered pages). It logs every request's timing plus the full SQL
# query log, so N+1s show up directly instead of being inferred. Dev-only —
# never run this against prod: it stores request/response bodies and query
# params in its own DB tables, which is a real data-exposure risk in
# production, on top of the profiling overhead itself.
#
# Opt-in (ENABLE_SILK=True), not tied to DEBUG alone: on SQL Server, Silk's
# own writes to its own log tables deadlock (error 1205) under completely
# ordinary concurrency — two routine GETs firing on one page load is enough —
# because SQL Server's default lock-based concurrency has none of MySQL's
# tolerance for this pattern. Turning SILKY_ANALYZE_QUERIES off (below)
# wasn't enough to stop it. Since profiling is a deliberate, occasional
# session and not something the app needs to function, it's off by default
# everywhere and switched on only when actually profiling.
ENABLE_SILK = DEBUG and os.getenv("ENABLE_SILK", "False") == "True"
if ENABLE_SILK:
    INSTALLED_APPS.append("silk")

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

if ENABLE_SILK:
    # After AuthenticationMiddleware so silk can attribute requests to a
    # user; must run before the request reaches any view to time it fully.
    MIDDLEWARE.append("silk.middleware.SilkyMiddleware")
    # Runs an EXPLAIN on every captured query, synchronously, inside the same
    # response-teardown step that writes Silk's own log tables — extra load
    # right at the point that already deadlocks on SQL Server (see above).
    # Leave off; flip True only for a single focused profiling session.
    SILKY_ANALYZE_QUERIES = False

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
            # Same reasoning as the mssql branch — a fresh-connection-per-
            # request tax exists here too (confirmed via profiling: a
            # request after any idle gap runs ~5x slower than a warm one,
            # even on localhost), just smaller since MySQL's handshake is
            # cheaper than pyodbc's.
            "CONN_MAX_AGE": int(os.getenv("MYSQL_CONN_MAX_AGE", "600")),
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
CORS_EXPOSE_HEADERS = ["X-Card-Meta"]  # how a birthday card preview was fitted (the browser may read it when the API is on another address)
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
        "core.jwt_auth.SerosJWTAuthentication",
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

# Encrypted sign-in (core/login_crypto.py): the RSA key file (created on first use) and whether a plain-text sign-in is still accepted.
LOGIN_PRIVATE_KEY_FILE = os.getenv("LOGIN_PRIVATE_KEY_FILE", str(BASE_DIR / "login_key.pem"))
LOGIN_REQUIRE_ENCRYPTED = os.getenv("LOGIN_REQUIRE_ENCRYPTED", "False") == "True"

# A session lives at most 2 days (the refresh token, which is rotated but never extended), and ends after IDLE_TIMEOUT_MINUTES without use.
REFRESH_LIFETIME = timedelta(days=2)
IDLE_TIMEOUT_MINUTES = int(os.getenv("IDLE_TIMEOUT_MINUTES", "30"))
# How long the cached mail password may be used: never longer than a session.
CREDENTIAL_TTL_SECONDS = int(REFRESH_LIFETIME.total_seconds())

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": REFRESH_LIFETIME,
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
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = False


# ── Static files ──────────────────────────────────────────────────────────

STATIC_URL = "static/"

# ── Media (user-uploaded files, e.g. interviewer signatures) ────────────────

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ── Email ─────────────────────────────────────────────────────────────────
# EMAIL_USE_CONSOLE=True (dev default) prints every outgoing message to the
# terminal running the backend instead of touching a real mail server —
# Django's console backend does exactly this, so approval-notification code
# elsewhere just calls send_mail()/EmailMessage and never has to branch on
# console-vs-real itself. Flip EMAIL_USE_CONSOLE=False once real SMTP
# credentials (previously tested against email.essar.com:25, no TLS/SSL) are
# confirmed for whichever environment is running.
EMAIL_USE_CONSOLE = os.getenv("EMAIL_USE_CONSOLE", "True") == "True"
if EMAIL_USE_CONSOLE:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "email.essar.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
# The shared "Oilfield Services" fallback account (Mst_Business_System,
# Business_System_id=6) — core/mailer.py only reaches for this when a
# per-user send (auth'd as whoever performed the action) is unavailable or
# fails; it is never the primary path.
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "False") == "True"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False") == "True"
# From: address used only on the fallback path above — the relay enforces
# that From must match whoever authenticated, so this must be the fallback
# account's own address, confirmed against the real relay.
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "eosil.autoalerts@essar.com")

# ── Scheduled mails (the Birthday Mailer and the other automations) ──────────────────────────────────────────────────────────
# The birthday mail has its own sending account, set here and never in the database or on a page. When it is not set, or when it fails, the
# mail is sent with the default account above (EMAIL_HOST...). The From name comes from the alert (its display name); the From address is the
# one below, or the account's own user name when it is an address, or DEFAULT_FROM_EMAIL.
BIRTHDAY_EMAIL_HOST = os.getenv("BIRTHDAY_EMAIL_HOST", "")
BIRTHDAY_EMAIL_PORT = int(os.getenv("BIRTHDAY_EMAIL_PORT", "25") or 25)
BIRTHDAY_EMAIL_USER = os.getenv("BIRTHDAY_EMAIL_USER", "")
BIRTHDAY_EMAIL_PASSWORD = os.getenv("BIRTHDAY_EMAIL_PASSWORD", "")
BIRTHDAY_EMAIL_USE_TLS = os.getenv("BIRTHDAY_EMAIL_USE_TLS", "False") == "True"
BIRTHDAY_EMAIL_USE_SSL = os.getenv("BIRTHDAY_EMAIL_USE_SSL", "False") == "True"
BIRTHDAY_EMAIL_FROM = os.getenv("BIRTHDAY_EMAIL_FROM", "")
SCHEDULER_MAX_RETRIES = int(os.getenv("SCHEDULER_MAX_RETRIES", "2") or 2)  # after the first try: at most this many more, one per hourly run
# Who is told when an automatic mail has finally failed (after its retries): comma separated addresses. Empty = nobody is mailed (the failure still shows on
# Scheduled Mails and in the logs). The error mail goes out through the default account.
SCHEDULER_ERROR_MAIL_TO = [a.strip() for a in os.getenv("SCHEDULER_ERROR_MAIL_TO", "").split(",") if a.strip()]

# ── Log files ────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# backend/logs/ (or LOG_DIR): scheduler-<date>.log (every hourly run), automation_errors-<date>.log (every error, with its traceback) and
# django-<date>.log. One file per day, kept LOG_KEEP_DAYS days. Passwords are never logged.
LOG_DIR = Path(os.getenv("LOG_DIR") or (BASE_DIR / "logs"))
LOG_KEEP_DAYS = int(os.getenv("LOG_KEEP_DAYS", "60") or 60)
_LOG_FMT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": _LOG_FMT},
        # runserver's own request line, coloured by status: [27/Oct/2026 17:00:00] "GET /api/... HTTP/1.1" 200 1234
        "server": {"()": "django.utils.log.ServerFormatter", "format": "[{server_time}] {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
        "server_console": {"class": "logging.StreamHandler", "formatter": "server"},
        "scheduler_file": {"class": "core.log_setup.DailyFileHandler", "folder": str(LOG_DIR), "prefix": "scheduler", "keep_days": LOG_KEEP_DAYS, "formatter": "plain"},
        "error_file": {"class": "core.log_setup.DailyFileHandler", "folder": str(LOG_DIR), "prefix": "automation_errors", "keep_days": LOG_KEEP_DAYS, "formatter": "plain", "level": "ERROR"},
        "django_file": {"class": "core.log_setup.DailyFileHandler", "folder": str(LOG_DIR), "prefix": "django", "keep_days": LOG_KEEP_DAYS, "formatter": "plain", "level": "WARNING"},
    },
    "loggers": {
        # everything the scheduler and the automations do; errors also go to their own file
        "seros.scheduler": {"handlers": ["scheduler_file", "error_file", "console"], "level": "INFO", "propagate": False},
        "django": {"handlers": ["django_file", "console"], "level": "WARNING", "propagate": False},
        # the development server's request lines (every API call) in the terminal, as Django prints them by default; not written to the log files
        "django.server": {"handlers": ["server_console"], "level": "INFO", "propagate": False},
    },
}
