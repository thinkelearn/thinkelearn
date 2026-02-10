#!/bin/bash
# Set CORS on the thinkelearn S3 bucket to allow presigned uploads from the browser.
aws s3api put-bucket-cors --bucket thinkelearn --region ca-central-1 --cors-configuration '{"CORSRules":[{"AllowedHeaders":["*"],"AllowedMethods":["POST"],"AllowedOrigins":["https://www.thinkelearn.com","https://thinkelearn.com"],"MaxAgeSeconds":3600}]}'

# Verify
aws s3api get-bucket-cors --bucket thinkelearn --region ca-central-1
