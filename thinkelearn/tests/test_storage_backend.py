from unittest.mock import patch

from thinkelearn.backends.storage import BrowserAccessibleS3Storage, rewrite_s3_url


def test_rewrite_s3_url_rewrites_internal_endpoint_to_public_endpoint():
    url = (
        "http://minio:9000/thinkelearn-dev/original_images/example.jpg"
        "?AWSAccessKeyId=minioadmin&Signature=abc&Expires=123"
    )

    rewritten = rewrite_s3_url(
        url=url,
        endpoint_url="http://minio:9000",
        public_url="http://localhost:9000",
    )

    assert rewritten.startswith(
        "http://localhost:9000/thinkelearn-dev/original_images/"
    )
    assert "Signature=abc" in rewritten


def test_rewrite_s3_url_does_not_change_non_matching_urls():
    url = "http://example.com/thinkelearn-dev/original_images/example.jpg"

    rewritten = rewrite_s3_url(
        url=url,
        endpoint_url="http://minio:9000",
        public_url="http://localhost:9000",
    )

    assert rewritten == url


def test_rewrite_s3_url_returns_url_unchanged_when_endpoint_url_is_none():
    url = "http://minio:9000/bucket/file.jpg"

    rewritten = rewrite_s3_url(
        url=url, endpoint_url=None, public_url="http://localhost:9000"
    )

    assert rewritten == url


def test_rewrite_s3_url_returns_url_unchanged_when_public_url_is_none():
    url = "http://minio:9000/bucket/file.jpg"

    rewritten = rewrite_s3_url(
        url=url, endpoint_url="http://minio:9000", public_url=None
    )

    assert rewritten == url


def test_rewrite_s3_url_returns_url_unchanged_when_both_are_none():
    url = "http://minio:9000/bucket/file.jpg"

    rewritten = rewrite_s3_url(url=url, endpoint_url=None, public_url=None)

    assert rewritten == url


def test_rewrite_s3_url_handles_trailing_slash_on_endpoint():
    url = "http://minio:9000/bucket/file.jpg"

    rewritten = rewrite_s3_url(
        url=url,
        endpoint_url="http://minio:9000/",
        public_url="http://localhost:9000",
    )

    assert rewritten == "http://localhost:9000/bucket/file.jpg"


def test_browser_accessible_s3_storage_url_rewrites_internal_endpoint():
    internal_url = "http://minio:9000/thinkelearn-dev/file.jpg?Signature=abc"
    expected_url = "http://localhost:9000/thinkelearn-dev/file.jpg?Signature=abc"

    with (
        patch(
            "storages.backends.s3boto3.S3Boto3Storage.url", return_value=internal_url
        ),
        patch(
            "django.conf.settings.AWS_S3_ENDPOINT_URL", "http://minio:9000", create=True
        ),
        patch(
            "django.conf.settings.AWS_S3_BROWSER_ENDPOINT_URL",
            "http://localhost:9000",
            create=True,
        ),
    ):
        storage = BrowserAccessibleS3Storage()
        result = storage.url("thinkelearn-dev/file.jpg")

    assert result == expected_url
