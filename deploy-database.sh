#!/bin/bash
# deploy-database.sh

# This script should be run after the main cluster setup

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

NAMESPACE="k8s-multi-demo"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}DEPLOYING POSTGRESQL DATABASE${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if namespace exists
if ! kubectl get namespace $NAMESPACE &> /dev/null; then
    echo -e "${RED}❌ Namespace $NAMESPACE does not exist${NC}"
    echo -e "${YELLOW}Run ./kind_setup.sh first to create the cluster${NC}"
    exit 1
fi

# Step 1: Deploy PostgreSQL Secret
echo -e "${BLUE}▶ Creating PostgreSQL Secret...${NC}"
kubectl apply -f k8s/database/postgres-secret.yaml
echo -e "${GREEN}✅ Secret created${NC}"
echo ""

# Step 2: Deploy PostgreSQL ConfigMap
echo -e "${BLUE}▶ Creating PostgreSQL ConfigMap...${NC}"
kubectl apply -f k8s/database/postgres-configmap.yaml
echo -e "${GREEN}✅ ConfigMap created${NC}"
echo ""

# Step 3: Deploy PostgreSQL StatefulSet
echo -e "${BLUE}▶ Creating PostgreSQL StatefulSet...${NC}"
kubectl apply -f k8s/database/postgres-statefulset.yaml
echo -e "${GREEN}✅ StatefulSet created${NC}"
echo ""

# Step 4: Deploy PostgreSQL Service
echo -e "${BLUE}▶ Creating PostgreSQL Service...${NC}"
kubectl apply -f k8s/database/postgres-service.yaml
echo -e "${GREEN}✅ Service created${NC}"
echo ""

# Step 5: Wait for PostgreSQL to be ready
echo -e "${BLUE}▶ Waiting for PostgreSQL to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=postgres -n $NAMESPACE --timeout=600s
echo -e "${GREEN}✅ PostgreSQL is ready${NC}"
echo ""

# Step 6: Verify database initialization
echo -e "${BLUE}▶ Verifying database initialization...${NC}"
sleep 5

POD_NAME=$(kubectl get pods -n $NAMESPACE -l app=postgres -o jsonpath='{.items[0].metadata.name}')
echo -e "${YELLOW}PostgreSQL Pod: $POD_NAME${NC}"

# Check if tables were created
echo -e "${BLUE}▶ Checking database tables...${NC}"
kubectl exec -n $NAMESPACE $POD_NAME -- psql -U k8s_demo_user -d k8s_demo_db -c "\dt" || true
echo ""

# Check if sample data was inserted
echo -e "${BLUE}▶ Checking sample data...${NC}"
kubectl exec -n $NAMESPACE $POD_NAME -- psql -U k8s_demo_user -d k8s_demo_db -c "SELECT COUNT(*) as user_count FROM users;" || true
kubectl exec -n $NAMESPACE $POD_NAME -- psql -U k8s_demo_user -d k8s_demo_db -c "SELECT COUNT(*) as task_count FROM tasks;" || true
echo ""

# Step 7: Update application deployment
echo -e "${BLUE}▶ Updating application deployment with database config...${NC}"
kubectl apply -f k8s/base/deployment.yaml
echo -e "${GREEN}✅ Deployment updated${NC}"
echo ""

# Step 8: Wait for application rollout
echo -e "${BLUE}▶ Waiting for application rollout...${NC}"
kubectl rollout status deployment/k8s-demo-app -n $NAMESPACE --timeout=600s
echo -e "${GREEN}✅ Application updated${NC}"
echo ""

# Display summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}DATABASE DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Database Information:${NC}"
echo -e "  Host: postgres-service"
echo -e "  Port: 5432"
echo -e "  Database: k8s_demo_db"
echo -e "  User: k8s_demo_user"
echo ""
echo -e "${BLUE}Database Resources:${NC}"
kubectl get statefulset,pod,pvc,svc -n $NAMESPACE -l app=postgres
echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo -e "  ${YELLOW}# Connect to PostgreSQL:${NC}"
echo -e "  kubectl exec -it $POD_NAME -n $NAMESPACE -- psql -U k8s_demo_user -d k8s_demo_db"
echo ""
echo -e "  ${YELLOW}# View database logs:${NC}"
echo -e "  kubectl logs -f $POD_NAME -n $NAMESPACE"
echo ""
echo -e "  ${YELLOW}# Check database size:${NC}"
echo -e "  kubectl exec -n $NAMESPACE $POD_NAME -- psql -U k8s_demo_user -d k8s_demo_db -c \"SELECT pg_size_pretty(pg_database_size('k8s_demo_db'));\""
echo ""
echo -e "  ${YELLOW}# View all tables:${NC}"
echo -e "  kubectl exec -n $NAMESPACE $POD_NAME -- psql -U k8s_demo_user -d k8s_demo_db -c \"\dt\""
echo ""
echo -e "${GREEN}Access the application at: http://localhost:30080${NC}"
echo -e "${GREEN}Check the Database tab in the UI to see connection status!${NC}"
echo ""
