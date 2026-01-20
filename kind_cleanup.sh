#!/bin/bash
# cleanup.sh
# Complete cleanup script - removes all Kubernetes resources and kind cluster
# Run this when you're finished with the demo

set -e  # Exit on any error

# ============================================
# CONFIGURATION
# ============================================
CLUSTER_NAME="k8s-demo"
NAMESPACE="k8s-multi-demo"
APP_IMAGE="k8s-demo-app:latest"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================
# HELPER FUNCTIONS
# ============================================
print_header() {
    echo ""
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}============================================${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# ============================================
# CONFIRMATION
# ============================================
clear
print_header "KUBERNETES DEMO - COMPLETE CLEANUP"

echo -e "${YELLOW}⚠️  WARNING: This script will DELETE:${NC}"
echo ""
echo "  1. Kind cluster: '${CLUSTER_NAME}'"
echo "  2. All Kubernetes resources in namespace: '${NAMESPACE}'"
echo "  3. Docker image: '${APP_IMAGE}' (optional)"
echo "  4. All running port-forwards"
echo "  5. Temporary configuration files"
echo ""
echo -e "${RED}This action CANNOT be undone!${NC}"
echo ""
echo -e "${CYAN}You can always recreate everything by running:${NC}"
echo -e "  ${GREEN}./kind_setup.sh${NC}"
echo ""

# Ask for confirmation
read -p "Are you sure you want to proceed? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    print_warning "Cleanup cancelled by user"
    echo ""
    echo -e "${GREEN}No changes were made.${NC}"
    echo ""
    exit 0
fi

echo ""
print_warning "Starting cleanup in 3 seconds... (Press Ctrl+C to cancel)"
sleep 1
echo "3..."
sleep 1
echo "2..."
sleep 1
echo "1..."
echo ""

# ============================================
# STEP 1: STOP PORT-FORWARDS
# ============================================
print_header "STEP 1/6: STOPPING PORT-FORWARDS"

print_step "Finding port-forward processes..."
PORT_FORWARDS=$(ps aux | grep -E "port-forward.*${NAMESPACE}" | grep -v grep | wc -l)

if [ "$PORT_FORWARDS" -gt 0 ]; then
    print_step "Killing port-forward processes..."
    pkill -f "port-forward.*${NAMESPACE}" 2>/dev/null || true
    sleep 2
    print_success "Stopped $PORT_FORWARDS port-forward process(es)"
else
    print_info "No port-forwards running"
fi

# Kill any remaining port-forwards
print_step "Cleaning up all remaining port-forwards..."
pkill -f "port-forward" 2>/dev/null || true
print_success "All port-forwards stopped"

# ============================================
# STEP 2: DELETE KUBERNETES NAMESPACE
# ============================================
print_header "STEP 2/6: DELETING KUBERNETES NAMESPACE"

print_step "Checking if namespace exists..."
if kubectl get namespace ${NAMESPACE} &>/dev/null; then
    print_step "Deleting namespace '${NAMESPACE}' (this removes ALL resources)..."
    
    # Show what will be deleted
    echo ""
    echo -e "${YELLOW}Resources to be deleted:${NC}"
    kubectl get all,configmap,secret,ingress,hpa -n ${NAMESPACE} 2>/dev/null || true
    echo ""
    
    # Delete the namespace
    kubectl delete namespace ${NAMESPACE} --wait=false
    
    print_step "Waiting for namespace to be fully deleted..."
    kubectl wait --for=delete namespace/${NAMESPACE} --timeout=60s 2>/dev/null || true
    
    print_success "Namespace '${NAMESPACE}' deleted"
else
    print_info "Namespace '${NAMESPACE}' not found (already deleted)"
fi

# ============================================
# STEP 3: DELETE KIND CLUSTER
# ============================================
print_header "STEP 3/6: DELETING KIND CLUSTER"

print_step "Checking for kind cluster..."
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    print_step "Deleting kind cluster '${CLUSTER_NAME}'..."
    kind delete cluster --name ${CLUSTER_NAME}
    
    # Verify deletion
    sleep 2
    if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
        print_error "Failed to delete cluster"
    else
        print_success "Cluster '${CLUSTER_NAME}' deleted"
    fi
else
    print_info "Cluster '${CLUSTER_NAME}' not found (already deleted)"
fi

print_step "Verifying no clusters remain..."
REMAINING_CLUSTERS=$(kind get clusters 2>/dev/null | wc -l)
if [ "$REMAINING_CLUSTERS" -eq 0 ]; then
    print_success "No kind clusters remaining"
else
    print_warning "$REMAINING_CLUSTERS kind cluster(s) still exist"
    kind get clusters
fi

# ============================================
# STEP 4: DELETE DOCKER IMAGE (OPTIONAL)
# ============================================
print_header "STEP 4/6: DOCKER IMAGE CLEANUP"

print_step "Checking for Docker image..."
if docker images | grep -q "k8s-demo-app"; then
    echo ""
    print_warning "Docker image '${APP_IMAGE}' found"
    echo -e "${YELLOW}Do you want to delete the Docker image?${NC}"
    echo -e "  ${CYAN}Deleting saves disk space${NC}"
    echo -e "  ${CYAN}Keeping allows faster rebuild${NC}"
    echo ""
    read -p "Delete Docker image? (yes/no): " DELETE_IMAGE
    
    if [ "$DELETE_IMAGE" = "yes" ]; then
        print_step "Removing Docker image..."
        docker rmi ${APP_IMAGE} -f 2>/dev/null || true
        docker rmi $(docker images -q k8s-demo-app) -f 2>/dev/null || true
        print_success "Docker image deleted"
    else
        print_info "Docker image preserved"
    fi
else
    print_info "Docker image not found (already deleted)"
fi

# ============================================
# STEP 5: CLEANUP TEMPORARY FILES
# ============================================
print_header "STEP 5/6: CLEANING TEMPORARY FILES"

print_step "Removing temporary configuration files..."
TEMP_FILES=(
    "/tmp/kind-config.yaml"
    "/tmp/k8s-demo-*.yaml"
)

FILES_REMOVED=0
for file in "${TEMP_FILES[@]}"; do
    if [ -f "$file" ]; then
        rm -f "$file"
        FILES_REMOVED=$((FILES_REMOVED + 1))
    fi
done

if [ $FILES_REMOVED -gt 0 ]; then
    print_success "Removed $FILES_REMOVED temporary file(s)"
else
    print_info "No temporary files found"
fi

# ============================================
# STEP 6: CLEANUP KUBECTL CONTEXT
# ============================================
print_header "STEP 6/6: KUBECTL CONTEXT CLEANUP"

print_step "Checking kubectl contexts..."
if kubectl config get-contexts | grep -q "kind-${CLUSTER_NAME}"; then
    print_step "Removing kubectl context 'kind-${CLUSTER_NAME}'..."
    kubectl config delete-context kind-${CLUSTER_NAME} 2>/dev/null || true
    kubectl config delete-cluster kind-${CLUSTER_NAME} 2>/dev/null || true
    kubectl config unset users.kind-${CLUSTER_NAME} 2>/dev/null || true
    print_success "Kubectl context cleaned up"
else
    print_info "Kubectl context already removed"
fi

# ============================================
# FINAL SUMMARY
# ============================================
print_header "CLEANUP COMPLETE"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                   CLEANUP SUCCESSFUL!                        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${CYAN}✅ REMOVED:${NC}"
echo "  ✓ Kind cluster: ${CLUSTER_NAME}"
echo "  ✓ Kubernetes namespace: ${NAMESPACE}"
echo "  ✓ All pods, services, deployments"
echo "  ✓ HPA, Ingress, ConfigMaps, Secrets"
echo "  ✓ Port-forward processes"
echo "  ✓ Temporary files"
echo "  ✓ Kubectl context"
if [ "$DELETE_IMAGE" = "yes" ]; then
    echo "  ✓ Docker image: ${APP_IMAGE}"
fi
echo ""

echo -e "${CYAN}🔍 VERIFICATION:${NC}"
echo ""
print_step "Checking for remaining kind clusters..."
if kind get clusters 2>/dev/null | wc -l | grep -q "^0$"; then
    print_success "No kind clusters found"
else
    print_warning "Some kind clusters still exist:"
    kind get clusters
fi
echo ""

print_step "Checking for Docker images..."
REMAINING_IMAGES=$(docker images | grep -c "k8s-demo-app" || echo "0")
if [ "$REMAINING_IMAGES" -eq 0 ]; then
    print_success "No demo Docker images found"
else
    print_info "Demo Docker images still present: $REMAINING_IMAGES"
fi
echo ""

print_step "Checking for port-forwards..."
REMAINING_PORT_FORWARDS=$(ps aux | grep -c "port-forward" | grep -v grep || echo "0")
if [ "$REMAINING_PORT_FORWARDS" -eq 0 ]; then
    print_success "No port-forwards running"
else
    print_info "Some port-forwards still running: $REMAINING_PORT_FORWARDS"
fi
echo ""

echo -e "${CYAN}♻️  TO REDEPLOY:${NC}"
echo ""
echo -e "  Run the setup script again:"
echo -e "  ${GREEN}./kind_setup.sh${NC}"
echo ""
echo -e "  Or deploy manually:"
echo -e "  ${GREEN}git clone https://github.com/shaydevops2024/kubernetes-production-simulator.git${NC}"
echo -e "  ${GREEN}cd kubernetes-production-simulator${NC}"
echo -e "  ${GREEN}./kind_setup.sh${NC}"
echo ""

echo -e "${CYAN}📚 DISK SPACE FREED:${NC}"
if command -v du &>/dev/null; then
    DOCKER_SIZE=$(docker system df --format "{{.Size}}" 2>/dev/null | head -1 || echo "Unknown")
    echo "  Current Docker disk usage: ${DOCKER_SIZE}"
    echo ""
    echo "  To reclaim more space, run:"
    echo -e "  ${YELLOW}docker system prune -a --volumes${NC}"
fi
echo ""

print_header "✅ ALL CLEANUP TASKS COMPLETED"

echo ""
echo -e "${GREEN}Your system has been cleaned up successfully!${NC}"
echo -e "${CYAN}Thank you for trying the Kubernetes Production Demo!${NC}"
echo ""
echo -e "${YELLOW}⭐ If this project helped you learn Kubernetes, please star it on GitHub!${NC}"
echo -e "${BLUE}   https://github.com/shaydevops2024/kubernetes-production-simulator${NC}"
echo ""
