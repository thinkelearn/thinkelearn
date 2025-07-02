import os

import dj_database_url

from .base import *  # noqa: F403

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-+b*&pr)e-cccn-$kw35u-tv1r89%t92k#(&*no#^dj72w)ymz_"  # nosec

# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = ["*"]

# Email configuration for development with Mailpit
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "mailpit"
EMAIL_PORT = 1025
EMAIL_USE_TLS = False
EMAIL_USE_SSL = False
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""  # nosec

# Database configuration - use PostgreSQL by default in development
# Fallback to SQLite only if DATABASE_URL is not set (traditional setup)
if "DATABASE_URL" in os.environ:
    DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL"])}  # type: ignore[dict-item]
else:
    # Default PostgreSQL configuration for development
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "thinkelearn",
            "USER": "postgres",
            "PASSWORD": "postgres",
            "HOST": "localhost",
            "PORT": "5432",
        }
    }


try:
    from .local import *  # noqa: F403
except ImportError:
    pass
