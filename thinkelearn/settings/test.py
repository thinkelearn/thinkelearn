import os
import tempfile

from .base import *  # noqa: F403,F401

# Test-specific settings
DEBUG = True
SECRET_KEY = "test-secret-key-not-for-production"  # nosec

# Database configuration for testing

if os.environ.get("DATABASE_URL"):
    # Use PostgreSQL in CI/CD
    from typing import Any

    import dj_database_url

    db_config: dict[str, Any] = dj_database_url.parse(
        os.environ.get("DATABASE_URL", "")
    )
    db_config["TEST"] = {"NAME": "test_thinkelearn"}
    DATABASES = {"default": db_config}
else:
    # Use SQLite for local testing
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
            "TEST": {
                "NAME": ":memory:",
            },
        }
    }

# Keep migrations enabled for Wagtail tests
# MIGRATION_MODULES can be enabled later if tests become too slow

# Email backend for testing
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Run Celery tasks eagerly in tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Fast password hashing for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable caching for tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Static files - use default storage for tests
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Media files - use temporary directory
MEDIA_ROOT = tempfile.mkdtemp()

# Wagtail settings for testing
WAGTAIL_SITE_NAME = "THINK eLearn Test"

# Disable debug toolbar in tests
if "debug_toolbar" in INSTALLED_APPS:  # noqa: F405
    INSTALLED_APPS.remove("debug_toolbar")  # noqa: F405

# Remove any middleware that might interfere with testing
MIDDLEWARE = [item for item in MIDDLEWARE if "debug_toolbar" not in item]  # noqa: F405

# Logging - minimize output during tests
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
        },
        "wagtail": {
            "handlers": ["console"],
            "level": "WARNING",
        },
    },
}

# Silence security warnings in tests
SILENCED_SYSTEM_CHECKS = [
    "security.W004",  # SECURE_HSTS_SECONDS
    "security.W008",  # SECURE_SSL_REDIRECT
    "security.W012",  # SESSION_COOKIE_SECURE
    "security.W016",  # CSRF_COOKIE_SECURE
    "security.W019",  # SECURE_CONTENT_TYPE_NOSNIFF
    "security.W020",  # SECURE_REFERRER_POLICY
    "security.W021",  # SECURE_CROSS_ORIGIN_OPENER_POLICY
]
