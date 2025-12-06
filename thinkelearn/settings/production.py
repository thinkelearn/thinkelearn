import os

import dj_database_url
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *  # noqa: F403,F405

# Sentry configuration
if os.environ.get("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.environ.get("SENTRY_DSN"),
        integrations=[DjangoIntegration()],
        traces_sample_rate=1.0,
        send_default_pii=True,
        profile_session_sample_rate=0.5,
        profile_lifecycle="trace",
    )

# Security settings
DEBUG = False
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    # During Docker build, use a temporary key for collectstatic
    # This will be overridden at runtime with the real SECRET_KEY
    SECRET_KEY = "django-insecure-build-time-key-will-be-overridden-at-runtime"  # nosec
    import warnings

    warnings.warn(
        "Using temporary SECRET_KEY during build. Ensure SECRET_KEY is set at runtime.",
        stacklevel=2,
    )

# Railway deployment settings
ALLOWED_HOSTS = [
    "thinkelearn.com",
    "www.thinkelearn.com",
    ".railway.app",
]

# Database configuration - Railway provides both DATABASE_URL and individual vars
if os.environ.get("DATABASE_URL"):
    # Use DATABASE_URL if provided (Railway standard)
    DATABASES = {
        "default": dj_database_url.config(  # type: ignore[dict-item]
            default=os.environ.get("DATABASE_URL"),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
elif os.environ.get("PGHOST"):
    # Fallback to individual PostgreSQL environment variables
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("PGDATABASE"),
            "USER": os.environ.get("PGUSER"),
            "PASSWORD": os.environ.get("PGPASSWORD"),
            "HOST": os.environ.get("PGHOST"),
            "PORT": os.environ.get("PGPORT", "5432"),
            "OPTIONS": {  # type: ignore[dict-item]
                "sslmode": "require",
            },
        }
    }
else:
    # During Docker build, use SQLite for collectstatic (no DB operations needed)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

# Static files configuration for Railway
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")  # noqa: F405

# Use whitenoise for static file serving
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405

# Whitenoise configuration
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Whitenoise additional settings for better performance
WHITENOISE_USE_FINDERS = False
WHITENOISE_AUTOREFRESH = False
WHITENOISE_MANIFEST_STRICT = False
WHITENOISE_SKIP_COMPRESS_EXTENSIONS = [
    "jpg",
    "jpeg",
    "png",
    "gif",
    "webp",
    "zip",
    "gz",
    "tgz",
    "bz2",
    "tbz",
    "xz",
    "br",
]

# Static file optimization
WHITENOISE_MAX_AGE = 31536000  # 1 year cache for static files

# Media files (for user uploads) - AWS S3 Configuration
if os.environ.get("AWS_STORAGE_BUCKET_NAME"):
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "ca-central-1")
    AWS_S3_CUSTOM_DOMAIN = None  # Required for presigned URLs to work
    AWS_QUERYSTRING_AUTH = True  # Generate presigned URLs
    AWS_QUERYSTRING_EXPIRE = 3600  # URLs valid for 1 hour (adjust as needed)
    AWS_DEFAULT_ACL = None  # Don't set ACLs on objects
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400",
    }

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    # Don't set MEDIA_URL - django-storages generates full presigned URLs
else:
    # Fallback to local storage (development or during Docker build)
    # Note: During Docker build, AWS vars aren't available yet - this is expected
    MEDIA_URL = "/media/"
    MEDIA_ROOT = os.path.join(BASE_DIR, "media")  # noqa: F405

# Security headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# HTTPS settings (Railway provides HTTPS)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Email configuration (for contact forms and admin notifications)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "live.smtp.mailtrap.io")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "api")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@thinkelearn.com")
EMAIL_TIMEOUT = 60  # SMTP connection timeout in seconds (prevents worker timeout)

# Wagtail settings for production
WAGTAILADMIN_BASE_URL = os.environ.get(
    "WAGTAILADMIN_BASE_URL", "https://www.thinkelearn.com"
)

# Logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

try:
    from .local import *  # noqa: F403
except ImportError:
    pass
