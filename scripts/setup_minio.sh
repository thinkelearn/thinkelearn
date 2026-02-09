#!/bin/bash
# One-time setup: create the dev bucket in MinIO
# Run this after `./start.sh` brings up the MinIO container.

set -e

docker run --rm --network host --entrypoint sh minio/mc -c "
  mc alias set local http://localhost:9000 minioadmin minioadmin &&
  mc mb local/thinkelearn-dev --ignore-existing &&
  mc anonymous set download local/thinkelearn-dev
"

echo "MinIO bucket 'thinkelearn-dev' ready at http://localhost:9001"
