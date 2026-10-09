"""
Django settings for Barangay Information and Management System.

All sensitive values are read from environment variables.
Copy .env.example to .env and fill in real values. Never commit .env.
"""

from pathlib import Path
import os
from django.core.exceptions import ImproperlyConfigured
from django.utils.log import DEFAULT_LOGGING

# ---------------------------------------------------------------------------
# Base directory
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def env(key, default=None, required=False):
    """Read from environment, optional strict-mode."""
    value = os.environ.get(key, default)
    if required and not value:
        raise RuntimeError(
            f"Required environment variable {key!r} is not set. "
            "See .env.example for guidance."
        )
    return value


def env_bool(key, default=False):
    return env(key, str(default)).lower() in ('1', 'true', 'yes')


def env_int(key, default=0):
    return int(env(key, str(default)))


# ---------------------------------------------------------------------------
# Core secrets  (required in production, have safe dev defaults)
# ---------------------------------------------------------------------------
DEV_SECRET_KEY = 'django-insecure-local-dev-only-change-this-in-production!'

DEBUG = env_bool('DEBUG', default=True)

# The dev key is only a fallback while DEBUG is on; production must set its own.
SECRET_KEY = env('SECRET_KEY', default='') or (DEV_SECRET_KEY if DEBUG else '')

# DEBUG: any host (LAN phones during local testing). Production: explicit list only.
_allowed_hosts_raw = env('ALLOWED_HOSTS', default='*' if DEBUG else '')
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_raw.split(',') if h.strip()]

if not DEBUG:
    # Refuse to start with unsafe production settings.
    if (
        not SECRET_KEY
        or SECRET_KEY == DEV_SECRET_KEY
        or SECRET_KEY.startswith('django-insecure')
        or len(SECRET_KEY) < 50
        or len(set(SECRET_KEY)) < 5
    ):
        raise ImproperlyConfigured(
            'DEBUG is False but SECRET_KEY is missing, the development default, or too weak. '
            'Set SECRET_KEY to a random string of at least 50 characters (see .env.example).'
        )
    if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            "DEBUG is False but ALLOWED_HOSTS is empty or contains '*'. "
            'Set ALLOWED_HOSTS to the comma-separated domain names of this site.'
        )

# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------
_csrf_raw = env('CSRF_TRUSTED_ORIGINS', default='')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_raw.split(',') if o.strip()]

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'channels',
    # Local
    'apps.core',
    'apps.accounts',
    'apps.appointments',
    'apps.communications',
    'apps.chat',
    'apps.records',
    'apps.statistics',
    'apps.history',
    'apps.blotter',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Content-Security-Policy + Permissions-Policy
    'apps.core.middleware.SecurityHeadersMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',          # static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # PermissionDenied -> 403 JSON for API/JSON callers
    'apps.core.middleware.JsonExceptionMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Custom approval gate
    'apps.accounts.middleware.ApprovalGateMiddleware',
    # Login throttle
    'apps.accounts.middleware.LoginThrottleMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.communications.context_processors.global_barangay_context',
            ],
        },
    },
]

# ASGI application for Django Channels & Daphne
ASGI_APPLICATION = 'config.asgi.application'
WSGI_APPLICATION = 'config.wsgi.application'

# Channels — use Redis in production, in-memory for dev/test
_redis_url = env('REDIS_URL', default='')
if _redis_url:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [_redis_url]},
        }
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        }
    }

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
_db_engine = env('DB_ENGINE', default='django.db.backends.sqlite3')
if _db_engine == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / env('DB_NAME', default='db.sqlite3'),
        }
    }
else:
    if _db_engine == 'django.db.backends.mysql':
        # Pure-Python MySQL driver (no C build tools needed on Windows).
        # Django 5.2 requires mysqlclient >= 2.2.1, so present a compatible version tuple.
        import pymysql
        pymysql.version_info = (2, 2, 1, 'final', 0)
        pymysql.install_as_MySQLdb()
    DATABASES = {
        'default': {
            'ENGINE': _db_engine,
            'NAME': env('DB_NAME', required=True),
            'USER': env('DB_USER', default='root'),
            'PASSWORD': env('DB_PASSWORD', default=''),
            'HOST': env('DB_HOST', default='127.0.0.1'),
            'PORT': env('DB_PORT', default='3306'),
            'OPTIONS': {'charset': 'utf8mb4'},
        }
    }

# ---------------------------------------------------------------------------
# Caching (Shared storage for login-throttle counters & sessions)
# ---------------------------------------------------------------------------
_redis_url = env('REDIS_URL', default='')
if _redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _redis_url,
            'KEY_PREFIX': 'brgy_cache',
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'brgy_cache_table',
            'TIMEOUT': 300,
        }
    }

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ---------------------------------------------------------------------------
# Session settings  (8-hour absolute, 30-minute idle)
# ---------------------------------------------------------------------------
SESSION_COOKIE_AGE = 8 * 60 * 60            # 8 hours
SESSION_SAVE_EVERY_REQUEST = True            # refresh on each request (idle timer)
SESSION_IDLE_TIMEOUT = 30 * 60              # 30 minutes idle  (custom middleware reads this)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Public media (avatars, attachments, announcements)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Private media (ID photos — served only via secure view, NEVER by web server)
PRIVATE_MEDIA_ROOT = BASE_DIR / 'private_media'

# Upload size limits (10 MB each)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# ---------------------------------------------------------------------------
# Default primary key field type
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Auth URLs
# ---------------------------------------------------------------------------
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = '/home/'
LOGOUT_REDIRECT_URL = 'accounts:login'

# ---------------------------------------------------------------------------
# Email  (SMTP — credentials MUST be set via env in production)
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend' if DEBUG else
            'django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env_int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default=f"Barangay e-Portal <{EMAIL_HOST_USER}>")
EMAIL_TIMEOUT = env_int('EMAIL_TIMEOUT', default=10)

# ---------------------------------------------------------------------------
# Barangay settings
# ---------------------------------------------------------------------------
BARANGAY_NAME = env('BARANGAY_NAME', default='Poblacion')
BARANGAY_VENUE = env('BARANGAY_VENUE', default='Barangay Hall Multi-Purpose Center')
BARANGAY_HEALTH_CENTER_VENUE = env('BARANGAY_HEALTH_CENTER_VENUE', default='Barangay Health Center')
# Fallback public contact number; the live value is BarangayInfo.contact_no (System Settings).
BARANGAY_CONTACT = env('BARANGAY_CONTACT', default='')

# Retention settings (in days)
REJECTED_REGISTRATION_RETENTION_DAYS = env_int('REJECTED_REGISTRATION_RETENTION_DAYS', default=90)
READ_NOTIFICATION_RETENTION_DAYS = env_int('READ_NOTIFICATION_RETENTION_DAYS', default=90)
AUDIT_LOG_RETENTION_DAYS = env_int('AUDIT_LOG_RETENTION_DAYS', default=365)

# ---------------------------------------------------------------------------
# Security headers. Secure by default when DEBUG is False; every value can be
# overridden through env (e.g. SECURE_SSL_REDIRECT=False when TLS ends at a
# proxy that already redirects).
# ---------------------------------------------------------------------------
SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', default=not DEBUG)
SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', default=not DEBUG)
CSRF_COOKIE_SECURE = env_bool('CSRF_COOKIE_SECURE', default=not DEBUG)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_HSTS_SECONDS = env_int('SECURE_HSTS_SECONDS', default=0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=not DEBUG)
SECURE_HSTS_PRELOAD = env_bool('SECURE_HSTS_PRELOAD', default=False)
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
# HSTS preload is a manual, hard-to-undo opt-in at hstspreload.org, so it stays
# off by default and its deploy-check warning is silenced on purpose.
SILENCED_SYSTEM_CHECKS = ['security.W021']

# Reverse proxies in front of the app that append to X-Forwarded-For.
# 0 = X-Forwarded-For is ignored and REMOTE_ADDR is the client IP.
TRUSTED_PROXY_COUNT = env_int('TRUSTED_PROXY_COUNT', default=0)
# Behind a trusted TLS-terminating proxy (nginx sets X-Forwarded-Proto), let
# Django see HTTPS requests as secure; otherwise SECURE_SSL_REDIRECT would loop.
# Never trusted without a proxy: a client could send the header itself.
if TRUSTED_PROXY_COUNT > 0:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Content-Security-Policy (apps.core.middleware.SecurityHeadersMiddleware).
# Everything is served from this origin; no inline scripts or handlers.
CSP_DIRECTIVES = {
    'default-src': ["'self'"],
    'script-src': ["'self'"],
    'style-src': ["'self'", "'unsafe-inline'"],
    'img-src': ["'self'", 'data:', 'blob:'],
    'font-src': ["'self'"],
    'connect-src': ["'self'", 'ws:', 'wss:'],
    'frame-ancestors': ["'none'"],
    'base-uri': ["'self'"],
    'form-action': ["'self'"],
    'object-src': ["'none'"],
}
CSP_REPORT_ONLY = env_bool('CSP_REPORT_ONLY', default=False)
PERMISSIONS_POLICY = 'camera=(), microphone=(), geolocation=()'

# ---------------------------------------------------------------------------
# Login throttle settings (apps.accounts.login_security)
# ---------------------------------------------------------------------------
LOGIN_FAILURE_LIMIT = env_int('LOGIN_FAILURE_LIMIT', default=5)            # per username + IP
LOGIN_LOCKOUT_SECONDS = env_int('LOGIN_LOCKOUT_SECONDS', default=15 * 60)  # window and lock length
LOGIN_IP_FAILURE_LIMIT = env_int('LOGIN_IP_FAILURE_LIMIT', default=20)     # per IP, any username
LOGIN_USER_FAILURE_LIMIT = env_int('LOGIN_USER_FAILURE_LIMIT', default=10) # per username, any IP

# ---------------------------------------------------------------------------
# Rate limits (apps.core.ratelimit). Format "<count>/<period>", period is
# s, m, h or d with an optional number (15m). Override each with
# RATE_LIMIT_<NAME>, e.g. RATE_LIMIT_SIGNUP=3/h.
# ---------------------------------------------------------------------------
_RATE_LIMIT_DEFAULTS = {
    'password_reset': '5/15m',
    'signup': '5/h',
    'public_booking': '10/h',
    'email_validation': '20/h',
    'chat_send': '30/m',
    'statistics_export': '20/h',
    'blotter_create': '20/h',
}
RATE_LIMITS = {
    name: env(f'RATE_LIMIT_{name.upper()}', default=rate)
    for name, rate in _RATE_LIMIT_DEFAULTS.items()
}

# Password reset token expiry (seconds)
PASSWORD_RESET_TIMEOUT = env_int('PASSWORD_RESET_TIMEOUT', default=3600)  # 1 hour

# ---------------------------------------------------------------------------
# Error reporting
# ---------------------------------------------------------------------------
ADMINS = [
    ('Barangay Admin', env('ADMIN_EMAIL', default='')),
]
SERVER_EMAIL = env('SERVER_EMAIL', default=DEFAULT_FROM_EMAIL)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'filters': ['require_debug_true'],
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'django.log'),
            'maxBytes': 10 * 1024 * 1024,   # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'errors.log'),
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
            'level': 'ERROR',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
            'include_html': False,
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file', 'error_file', 'mail_admins'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['error_file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
