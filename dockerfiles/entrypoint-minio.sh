#!/bin/sh
minio -c "mc alias set minio https://s3.doreeto.com ${S3_ACCESS_KEY} '${S3_SECRET_KEY}' && mc mb --ignore-existing minio/media && mc anonymous set download minio/media"