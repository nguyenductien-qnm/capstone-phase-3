#!/usr/bin/env bash
# Build 17 app image multi-arch (amd64+arm64) từ source de-branded và push
# lên Docker Hub: nghiadaulau/techx-corp:1.0-<service>  (PUBLIC).
# Prereq: docker + buildx + QEMU; đã: docker login -u nghiadaulau
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT/techx-corp-platform"
[ -f .env.override ] || { echo "missing .env.override"; exit 1; }
echo ">> IMAGE_NAME: $(grep IMAGE_NAME .env.override)"

# (khuyến nghị) smoke build 1 service Go trước để bắt lỗi rebrand sớm - single arch, không push
echo ">> smoke build checkout (single-arch, no push)"
docker compose build checkout

# builder multi-arch (one-time)
make create-multiplatform-builder || true

# build + push toàn bộ multi-arch
echo ">> multi-arch build + push ALL (amd64+arm64)"
make build-multiplatform-and-push

echo "done -> https://hub.docker.com/r/nghiadaulau/techx-corp/tags  (nhớ set repo = Public)"
