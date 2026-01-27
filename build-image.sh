#!/bin/bash
# build-image.sh
# Builds Docker image with scenarios baked in

set -e

IMAGE_NAME="k8s-demo-app:latest"
CLUSTER_NAME="k8s-demo"

echo "=========================================="
echo "Building Docker Image with Scenarios"
echo "=========================================="
echo ""

# Check we're in project root
if [ ! -f "app/Dockerfile" ]; then
    echo "❌ ERROR: Must run from project root (where app/ and k8s-scenarios/ exist)"
    echo "Current directory: $(pwd)"
    exit 1
fi

if [ ! -d "k8s-scenarios" ]; then
    echo "❌ ERROR: k8s-scenarios directory not found"
    echo "Expected at: $(pwd)/k8s-scenarios"
    exit 1
fi

# Count scenarios
SCENARIO_COUNT=$(ls -1 k8s-scenarios | wc -l)
echo "Found ${SCENARIO_COUNT} scenarios to include in image"
echo ""

# Build image from project root (so it can access both app/ and k8s-scenarios/)
echo "Building Docker image..."
echo "Build context: $(pwd)"
echo "Dockerfile: app/Dockerfile"
echo ""

docker build -f app/Dockerfile -t ${IMAGE_NAME} . --no-cache

echo ""
echo "✅ Image built successfully!"
echo ""

# Check if Kind cluster exists
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Loading image into Kind cluster..."
    kind load docker-image ${IMAGE_NAME} --name ${CLUSTER_NAME}
    echo "✅ Image loaded into Kind cluster"
else
    echo "ℹ️  Kind cluster '${CLUSTER_NAME}' not found"
    echo "   Image built but not loaded into cluster"
    echo "   Run this after cluster is created:"
    echo "   kind load docker-image ${IMAGE_NAME} --name ${CLUSTER_NAME}"
fi

echo ""
echo "=========================================="
echo "✅ Build Complete!"
echo "=========================================="
echo ""
echo "Image: ${IMAGE_NAME}"
echo "Scenarios included: ${SCENARIO_COUNT}"
echo ""
echo "Next steps:"
echo "  1. Deploy: kubectl apply -f k8s/base/"
echo "  2. Or run: ./kind_setup.sh (if cluster not running)"
echo ""
