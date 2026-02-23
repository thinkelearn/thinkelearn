from thinkelearn.backends.storage import rewrite_s3_url


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
