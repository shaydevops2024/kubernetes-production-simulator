#!/usr/bin/env bash
# ============================================================
# build-images.sh
# Builds all Docker images and loads them into Kind
# Run from: project-02-multitenant-saas/
# Usage:    bash main/solution/build-images.sh
# ============================================================
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/../../app" && pwd)"
KIND_CLUSTER="${KIND_CLUSTER:-kind}"

echo "==> Building images from $APP_DIR"
echo ""

services=(
  "platform-api:8010"
  "app-service:8011"
  "billing-service:8012"
  "admin-ui:80"
)

for entry in "${services[@]}"; do
  svc="${entry%%:*}"
  echo "--- Building $svc:v1"
  docker build -t "$svc:v1" "$APP_DIR/$svc"
  echo "--- Loading $svc:v1 into Kind cluster '$KIND_CLUSTER'"
  kind load docker-image "$svc:v1" --name "$KIND_CLUSTER"
  echo ""
done

echo "==> All images built and loaded into Kind"
echo ""
echo "Verify with:"
echo "  docker images | grep ':v1'"
