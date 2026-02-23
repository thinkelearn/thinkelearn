"""Custom storage backends."""

from __future__ import annotations

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


def rewrite_s3_url(
    url: str,
    endpoint_url: str | None,
    public_url: str | None,
) -> str:
    """Rewrite internal S3 endpoint URLs for browser access."""
    if not endpoint_url or not public_url:
        return url

    endpoint = endpoint_url.rstrip("/")
    public = public_url.rstrip("/")
    if url.startswith(endpoint):
        return f"{public}{url[len(endpoint) :]}"
    return url


class BrowserAccessibleS3Storage(S3Boto3Storage):
    """S3 storage that rewrites internal endpoint URLs for browser clients."""

    def url(
        self,
        name: str,
        parameters: dict[str, str] | None = None,
        expire: int | None = None,
        http_method: str | None = None,
    ) -> str:
        url = super().url(
            name,
            parameters=parameters,
            expire=expire,
            http_method=http_method,
        )
        return rewrite_s3_url(
            url,
            getattr(settings, "AWS_S3_ENDPOINT_URL", None),
            getattr(settings, "AWS_S3_PRESIGNED_URL", None),
        )
