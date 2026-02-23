# AWS S3 & IAM Setup

Production S3 configuration for media storage, SCORM content serving, and presigned uploads.

## Bucket

- **Name**: `thinkelearn`
- **Region**: `ca-central-1`
- **ACLs**: Disabled (bucket owner enforced)
- **Public access**: Blocked (all content served via presigned URLs)
- **Versioning**: Off (SCORM packages are immutable; re-upload creates a new key)

## CORS Configuration

Required for SCORM video/audio playback. The `<video crossorigin="anonymous">` attribute in SCORM content triggers browser CORS enforcement when Django redirects media requests to presigned S3 URLs.

```json
[
    {
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["GET", "HEAD", "POST"],
        "AllowedOrigins": [
            "https://www.thinkelearn.com",
            "https://thinkelearn.com"
        ],
        "ExposeHeaders": []
    }
]
```

| Method | Purpose |
| ------ | ------- |
| `GET` | Video/audio playback via presigned URL redirect (`lms/views.py`) |
| `HEAD` | Browser range-request probing for video seeking |
| `POST` | Direct browser-to-S3 SCORM package upload (`lms/services.py`) |

**If GET/HEAD are removed**, video elements with `crossorigin="anonymous"` will fail with "The media could not be loaded" — the browser blocks the S3 response without `Access-Control-Allow-Origin`.

## IAM Policy

The application IAM user needs these permissions on the `thinkelearn` bucket:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "DjangoStoragesReadWrite",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::thinkelearn",
                "arn:aws:s3:::thinkelearn/*"
            ]
        }
    ]
}
```

- `GetObject` — presigned URL generation, file downloads during SCORM extraction
- `PutObject` — presigned POST uploads, django-storages writes (SCORM extraction to `scorm_content/`)
- `DeleteObject` — admin package deletion
- `ListBucket` — django-storages `exists()` checks

## S3 Key Structure

```text
thinkelearn/
├── scorm_packages/          # Uploaded SCORM ZIPs (presigned POST target)
│   └── {uuid}_{filename}.zip
├── scorm_content/           # Extracted SCORM content (served to learners)
│   └── {package_slug}/
│       └── scormcontent/
│           ├── index.html
│           └── assets/
│               ├── *.mp4    # Redirected to presigned URL
│               ├── *.mp3    # Redirected to presigned URL
│               ├── *.jpg    # Proxied through Django
│               └── ...
├── original_images/         # Wagtail image originals
└── images/                  # Wagtail image renditions
```

## Django Settings

### Production (`thinkelearn/settings/production.py`)

```python
AWS_S3_CUSTOM_DOMAIN = None      # Required — presigned URLs need the S3 domain
AWS_QUERYSTRING_AUTH = True      # Generate presigned URLs (not public URLs)
AWS_QUERYSTRING_EXPIRE = 3600    # 1-hour URL lifetime
AWS_DEFAULT_ACL = None           # No public ACLs
AWS_S3_FILE_OVERWRITE = False    # Prevent accidental overwrites
```

### Railway Environment Variables

| Variable | Value |
| -------- | ----- |
| `AWS_STORAGE_BUCKET_NAME` | `thinkelearn` |
| `AWS_ACCESS_KEY_ID` | IAM user access key |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret key |
| `AWS_S3_REGION_NAME` | `ca-central-1` |

### Dev Environment (MinIO)

Docker Compose runs MinIO as an S3-compatible local substitute:

| Variable | Value |
| -------- | ----- |
| `AWS_STORAGE_BUCKET_NAME` | `thinkelearn-dev` |
| `AWS_ACCESS_KEY_ID` | `minioadmin` |
| `AWS_SECRET_ACCESS_KEY` | `minioadmin` |
| `AWS_S3_REGION_NAME` | `us-east-1` |
| `AWS_S3_ENDPOINT_URL` | `http://minio:9000` (internal) |
| `AWS_S3_BROWSER_ENDPOINT_URL` | `http://localhost:9000` (browser-accessible) |

MinIO console: <http://localhost:9001> (minioadmin/minioadmin)

## How Content Serving Works

1. SCORM iframe requests `assets/video.mp4` (relative URL)
2. Django resolves to `/lms/scorm-content/{package}/scormcontent/assets/video.mp4`
3. `lms/views.py:serve_scorm_content` checks MIME type:
   - **video/\*, audio/\***: Generates presigned S3 URL, returns 302 redirect
   - **Everything else**: Proxies through Django with `Cache-Control` headers
4. Browser follows redirect to S3, which serves the file with CORS headers

## Verifying CORS

Test that S3 returns CORS headers for GET requests:

```bash
curl -I -H "Origin: https://www.thinkelearn.com" \
  "https://thinkelearn.s3.ca-central-1.amazonaws.com/scorm_content/{package}/scormcontent/assets/{file}"
```

Expected response includes:

```logs
Access-Control-Allow-Origin: https://www.thinkelearn.com
Access-Control-Allow-Methods: GET, HEAD, POST
```
