import os

from .base import *  # noqa: F403

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-+b*&pr)e-cccn-$kw35u-tv1r89%t92k#(&*no#^dj72w)ymz_"  # nosec

# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = ["*"]

# Store full Stripe webhook payloads in development for debugging
STRIPE_WEBHOOK_STORE_FULL_PAYLOAD = True

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
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL"])}  # type: ignore[dict-item]
else:
    # Default PostgreSQL configuration for development
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "thinkelearn",
            "USER": "postgres",
            "PASSWORD": "postgres",  # nosec B105
            "HOST": "localhost",
            "PORT": "5432",
        }
    }


# S3 storage configuration (MinIO in dev, AWS in production)
if os.environ.get("AWS_STORAGE_BUCKET_NAME"):
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
    AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL")
    AWS_S3_BROWSER_ENDPOINT_URL = os.environ.get("AWS_S3_BROWSER_ENDPOINT_URL")
    AWS_S3_CUSTOM_DOMAIN = None
    AWS_S3_ADDRESSING_STYLE = "path"
    AWS_QUERYSTRING_AUTH = True
    AWS_QUERYSTRING_EXPIRE = 3600
    AWS_DEFAULT_ACL = None
    AWS_S3_FILE_OVERWRITE = False

    STORAGES = {
        "default": {
            "BACKEND": "thinkelearn.backends.storage.BrowserAccessibleS3Storage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
        },
    }

try:
    from .local import *  # noqa: F403
except ImportError:
    pass
