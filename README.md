# 🚀 Kubernetes Production Simulator

A **production-grade Kubernetes learning project** demonstrating real-world DevOps practices with auto-scaling, monitoring, incident simulation, and a modern web interface.

![Kubernetes](https://img.shields.io/badge/kubernetes-1.28+-blue) ![Python](https://img.shields.io/badge/python-3.11-green) ![FastAPI](https://img.shields.io/badge/FastAPI-0.104-teal) ![Docker](https://img.shields.io/badge/docker-24.0+-blue)

**Portfolio Project** | **DevOps Engineer Demo** | **Production Best Practices**

---

## 📑 Table of Contents

- [Overview](#-overview)
- [What This Demonstrates](#-what-this-demonstrates)
- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
  - [Method 1: Automated Deployment (Recommended)](#method-1-automated-deployment-recommended)
  - [Method 2: Manual Step-by-Step](#method-2-manual-step-by-step-deployment)
- [Access Methods](#-access-methods)
  - [Port-Forward (WSL2/Ubuntu)](#1-port-forward-wsl2ubuntu---recommended-for-local)
  - [Ingress with Custom Domain](#2-ingress-with-custom-domain)
  - [NodePort Direct Access](#3-nodeport-direct-access)
  - [kubectl Proxy](#4-kubectl-proxy)
- [Testing Features](#-testing-features)
  - [HPA Auto-Scaling](#1-horizontal-pod-autoscaler-hpa)
  - [Health Probes](#2-health--readiness-probes)
  - [Load Testing](#3-load-testing)
  - [Live Monitoring](#4-live-monitoring)
- [Monitoring & Debugging](#-monitoring--debugging)
- [Updating the Application](#-updating-the-application)
- [Troubleshooting](#-troubleshooting)
- [Project Structure](#-project-structure)
- [Cleanup](#-cleanup)
- [Advanced Topics](#-advanced-topics)

---

## 🎯 Overview

This project is a **complete Kubernetes production environment** simulator built to showcase DevOps engineering skills. It features:

- **FastAPI web application** with professional UI dashboard
- **Full Kubernetes orchestration** (Deployment, Service, Ingress, HPA)
- **Production-ready configurations** (health probes, resource limits, secrets)
- **Auto-scaling demonstration** with Horizontal Pod Autoscaler
- **Monitoring & observability** with Prometheus metrics
- **Incident simulation** for testing resilience
- **Complete automation** with deployment scripts

**Perfect for**: DevOps portfolios, technical interviews, learning Kubernetes production patterns

---

## ✨ What This Demonstrates

### Production Kubernetes Skills
- ✅ Multi-replica deployments with rolling updates
- ✅ Horizontal Pod Autoscaling (HPA) with CPU metrics
- ✅ Health checks (liveness & readiness probes)
- ✅ Resource management (requests & limits)
- ✅ ConfigMaps and Secrets management
- ✅ Ingress routing with NGINX
- ✅ Service discovery and load balancing

### DevOps Best Practices
- ✅ Non-root container security
- ✅ Multi-stage Docker builds
- ✅ Infrastructure as Code (IaC)
- ✅ Prometheus metrics integration
- ✅ Comprehensive automation scripts
- ✅ Professional documentation

### Application Features
- ✅ Modern web dashboard with real-time updates
- ✅ Live log viewer with auto-scroll
- ✅ Load testing capabilities
- ✅ Incident simulation controls
- ✅ CLI command reference
- ✅ Status monitoring

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                        │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │   Ingress    │────│   Service    │────│  Deployment  │ │
│  │   (NGINX)    │    │  (ClusterIP) │    │   (2-10      │ │
│  │              │    │              │    │   replicas)  │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│         │                                        │          │
│         │                                        │          │
│  ┌──────▼─────────────────────────────────┐    │          │
│  │           Pod (replicas: 2-10)          │◄───┤          │
│  │  ┌────────────────────────────────┐    │    │          │
│  │  │   FastAPI Application          │    │    │          │
│  │  │   - Web Dashboard              │    │    │          │
│  │  │   - /health (liveness)         │    │    │          │
│  │  │   - /ready (readiness)         │    │    │          │
│  │  │   - /metrics (Prometheus)      │    │    │          │
│  │  │   - Load test controls         │    │    │          │
│  │  └────────────────────────────────┘    │    │          │
│  │  ┌────────────────────────────────┐    │    │          │
│  │  │   ConfigMap (environment)      │    │    │          │
│  │  │   Secret (tokens)              │    │    │          │
│  │  └────────────────────────────────┘    │    │          │
│  └──────────────────▲────────────────────┘    │          │
│                     │                          │          │
│              ┌──────┴──────┐                  │          │
│              │     HPA     │──────────────────┘          │
│              │  (CPU-based)│                             │
│              │  2-10 pods  │                             │
│              └─────────────┘                             │
│                     ▲                                     │
│              ┌──────┴──────┐                             │
│              │metrics-server│                             │
│              └─────────────┘                             │
└─────────────────────────────────────────────────────────────┘
```

**Key Components:**
- **Deployment**: Manages 2-10 pod replicas with rolling updates
- **Service**: ClusterIP for internal load balancing
- **Ingress**: NGINX-based external routing
- **HPA**: Auto-scales based on CPU (70% threshold)
- **ConfigMap**: Environment variables (APP_ENV, APP_NAME)
- **Secret**: Sensitive data (SECRET_TOKEN)
- **Probes**: Health checks for automatic pod recovery

---

## 📋 Prerequisites

### Required Tools

| Tool | Version | Installation |
|------|---------|-------------|
| **Docker** | 24.0+ | [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) |
| **kubectl** | 1.28+ | [kubernetes.io/docs/tasks/tools](https://kubernetes.io/docs/tasks/tools/) |
| **kind** | 0.20+ | See below |

### Install kind

**On WSL2/Ubuntu:**
```bash
# Download and install kind
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

# Verify installation
kind version
```

**On macOS:**
```bash
# Using Homebrew
brew install kind

# Verify installation
kind version
```

**On Windows (PowerShell):**
```powershell
# Using Chocolatey
choco install kind

# Or using Scoop
scoop install kind
```

### System Requirements
- **CPU**: 2+ cores
- **RAM**: 4GB+ available
- **Disk**: 10GB+ free space
- **OS**: Linux, macOS, or Windows with WSL2

---

## 🚀 Quick Start

### Method 1: Automated Deployment (Recommended)

**Complete setup in one command:**

```bash
# 1. Clone the repository
git clone https://github.com/shaydevops2024/kubernetes-production-simulator.git
cd kubernetes-production-simulator

# 2. Run the automated deployment script
chmod +x kind_setup.sh
./kind_setup.sh
```

**What this script does:**
1. ✅ Checks all prerequisites
2. ✅ Deletes existing clusters (if any)
3. ✅ Creates kind cluster with Ingress support
4. ✅ Installs NGINX Ingress Controller
5. ✅ Builds Docker image
6. ✅ Deploys all Kubernetes resources
7. ✅ Sets up metrics-server and HPA
8. ✅ Runs comprehensive tests
9. ✅ Displays access URLs

**Expected output:**
```
============================================
DEPLOYMENT COMPLETE! 🎉
============================================

✅ Cluster: k8s-demo
✅ Namespace: k8s-multi-demo
✅ Pods: 2/2 Running
✅ Service: k8s-demo-service (80:8000/TCP)
✅ Ingress: k8s-multi-demo.local

Access the application:
  http://localhost:8080 (port-forward)
  http://k8s-multi-demo.local (ingress)
```

---

### Method 2: Manual Step-by-Step Deployment

For learning purposes or custom configurations, follow these manual steps:

#### **Step 1: Create kind Cluster**

```bash
# Create cluster with Ingress port mapping
cat <<EOF | kind create cluster --name k8s-demo --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 30080
    hostPort: 30080
    protocol: TCP
EOF

# Verify cluster creation
kubectl cluster-info --context kind-k8s-demo
```

#### **Step 2: Install NGINX Ingress Controller**

```bash
# Install NGINX Ingress (kind-specific version)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# Wait for Ingress Controller to be ready
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=90s

# Verify Ingress Controller
kubectl get pods -n ingress-nginx
```

#### **Step 3: Build and Load Docker Image**

```bash
# Build the application image
docker build -t k8s-demo-app:latest ./app

# Load image into kind cluster
kind load docker-image k8s-demo-app:latest --name k8s-demo

# Verify image is loaded
docker exec -it k8s-demo-control-plane crictl images | grep k8s-demo-app
```

#### **Step 4: Deploy Application**

```bash
# Create namespace
kubectl apply -f k8s/base/namespace.yaml

# Deploy configuration
kubectl apply -f k8s/base/configmap.yaml
kubectl apply -f k8s/base/secret.yaml

# Deploy application
kubectl apply -f k8s/base/deployment.yaml

# Create service
kubectl apply -f k8s/base/service.yaml

# Deploy ingress
kubectl apply -f k8s/ingress/ingress.yaml

# Wait for pods to be ready
kubectl wait --for=condition=ready pod \
  -l app=k8s-demo-app \
  -n k8s-multi-demo \
  --timeout=120s

# Verify deployment
kubectl get all -n k8s-multi-demo
```

#### **Step 5: Setup Horizontal Pod Autoscaler**

```bash
# Install metrics-server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Patch metrics-server for kind (insecure TLS)
kubectl patch -n kube-system deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

# Wait for metrics-server
kubectl wait --for=condition=ready pod \
  -l k8s-app=metrics-server \
  -n kube-system \
  --timeout=120s

# Deploy HPA
kubectl apply -f k8s/hpa/hpa.yaml

# Verify HPA
kubectl get hpa -n k8s-multi-demo
```

#### **Step 6: Verify Deployment**

```bash
# Check all resources
kubectl get all,configmap,secret,ingress,hpa -n k8s-multi-demo

# Check pod status
kubectl get pods -n k8s-multi-demo -o wide

# View pod logs
kubectl logs -l app=k8s-demo-app -n k8s-multi-demo --tail=50

# Check HPA metrics (may take 1-2 minutes)
kubectl get hpa -n k8s-multi-demo -w
```

**Expected output:**
```
NAME                               READY   STATUS    RESTARTS   AGE
pod/k8s-demo-app-xxxxxxxxxx-xxxxx   1/1     Running   0          2m
pod/k8s-demo-app-xxxxxxxxxx-xxxxx   1/1     Running   0          2m

NAME                       TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
service/k8s-demo-service   ClusterIP   10.96.xxx.xxx   <none>        80/TCP    2m

NAME                           READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/k8s-demo-app   2/2     2            2           2m

NAME                                      DESIRED   CURRENT   READY   AGE
replicaset.apps/k8s-demo-app-xxxxxxxxxx   2         2         2       2m

NAME                                              REFERENCE                 TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
horizontalpodautoscaler.autoscaling/k8s-demo-hpa   Deployment/k8s-demo-app   5%/70%    2         10        2          1m
```

---

## 🌐 Access Methods

After deployment, you can access the application using multiple methods:

### 1. Port-Forward (WSL2/Ubuntu) - **Recommended for Local**

**Best for**: WSL2 users who want to access via Windows browser

```bash
# Start port-forward in the background
kubectl port-forward svc/k8s-demo-service 8080:80 -n k8s-multi-demo > /dev/null 2>&1 &

# For WSL2: Open in Windows browser
explorer.exe http://localhost:8080

# For Ubuntu Desktop: Open in browser
google-chrome http://localhost:8080
# or
firefox http://localhost:8080

# For headless servers: Use curl to test
curl http://localhost:8080
```

**Advantages:**
- ✅ Works immediately without configuration
- ✅ Perfect for WSL2 (Windows browser)
- ✅ Simple and reliable
- ✅ No hosts file modification needed

**To stop port-forward:**
```bash
# Find and kill port-forward process
pkill -f "port-forward"

# Or find specific process
ps aux | grep port-forward
kill <PID>
```

---

### 2. Ingress with Custom Domain

**Best for**: Production-like setup with custom domain

#### **Configure /etc/hosts:**

**On WSL2/Linux:**
```bash
# Add entry to hosts file
echo "127.0.0.1 k8s-multi-demo.local" | sudo tee -a /etc/hosts

# Verify
cat /etc/hosts | grep k8s-multi-demo
```

**On Windows (if not using WSL2):**
```powershell
# Run PowerShell as Administrator
Add-Content -Path C:\Windows\System32\drivers\etc\hosts -Value "127.0.0.1 k8s-multi-demo.local"
```

**On macOS:**
```bash
sudo echo "127.0.0.1 k8s-multi-demo.local" >> /etc/hosts
```

#### **Access via Ingress:**

```bash
# The Ingress is already configured and running
# Access the application
curl http://k8s-multi-demo.local

# Or open in browser
explorer.exe http://k8s-multi-demo.local   # WSL2
google-chrome http://k8s-multi-demo.local  # Ubuntu Desktop
```

**Advantages:**
- ✅ Production-like routing
- ✅ Demonstrates Ingress knowledge
- ✅ Multiple applications via different domains
- ✅ Professional setup

**Verify Ingress:**
```bash
# Check Ingress status
kubectl get ingress -n k8s-multi-demo

# Describe Ingress for details
kubectl describe ingress k8s-demo-ingress -n k8s-multi-demo

# Check NGINX Ingress logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller
```

---

### 3. NodePort Direct Access

**Best for**: Direct cluster access without port-forward

#### **Option A: Use existing NodePort service (port 30080)**

```bash
# The cluster already has port 30080 mapped
# Access directly via NodePort
curl http://localhost:30080

# Or deploy the NodePort service
kubectl apply -f k8s/base/service-nodeport.yaml

# Access via browser
explorer.exe http://localhost:30080  # WSL2
```

**Advantages:**
- ✅ No port-forward needed
- ✅ Direct cluster access
- ✅ Persistent connection
- ✅ Fixed port (30080)

**Verify NodePort:**
```bash
# Check NodePort service
kubectl get svc k8s-demo-nodeport -n k8s-multi-demo

# Should show: 80:30080/TCP
```

---

### 4. kubectl Proxy

**Best for**: API-based access or testing

```bash
# Start kubectl proxy
kubectl proxy --port=8001 &

# Access via proxy URL
curl http://localhost:8001/api/v1/namespaces/k8s-multi-demo/services/k8s-demo-service:80/proxy/

# Full URL for browser
echo "http://localhost:8001/api/v1/namespaces/k8s-multi-demo/services/k8s-demo-service:80/proxy/"
```

---

## 🧪 Testing Features

### 1. Horizontal Pod Autoscaler (HPA)

#### **Method A: Using the Web UI (Easiest)**

1. **Access the application** (via any method above)
2. **Click "🔥 Start Load Test"** button
3. **Open a new terminal** and watch HPA:
   ```bash
   kubectl get hpa -n k8s-multi-demo -w
   ```
4. **Observe scaling:**
   - CPU usage increases to ~100%
   - Pods scale from 2 → 3 → 4 → up to 10
   - Watch replicas increase in real-time

5. **Click "🛑 Stop Load Test"**
6. **Watch scale down** (takes ~5 minutes):
   ```bash
   kubectl get pods -n k8s-multi-demo -w
   ```

**Expected behavior:**
```
NAME                            REFERENCE                 TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
k8s-demo-hpa   Deployment/k8s-demo-app   5%/70%    2         10        2          5m
k8s-demo-hpa   Deployment/k8s-demo-app   95%/70%   2         10        2          6m
k8s-demo-hpa   Deployment/k8s-demo-app   95%/70%   2         10        4          7m
k8s-demo-hpa   Deployment/k8s-demo-app   88%/70%   2         10        6          8m
```

#### **Method B: CLI Load Test (Professional)**

```bash
# Terminal 1: Watch HPA continuously
kubectl get hpa -n k8s-multi-demo -w

# Terminal 2: Generate load with curl
for i in {1..50}; do 
  (while true; do 
    curl -s http://localhost:8080/ > /dev/null
    sleep 0.1
  done) &
done

# Wait 2-3 minutes to see scaling

# Stop load test
pkill curl

# Terminal 1: Watch scale down (takes ~5 minutes)
```

#### **Method C: Using the load-test.sh script**

```bash
# Use the included script
./load-test.sh

# This sends 5000 requests in ~2 minutes
# Watch scaling in another terminal
```

---

### 2. Health & Readiness Probes

**Test liveness probe (automatic pod restart):**

1. Access the UI
2. Click **"💥 Simulate Crash"**
3. Watch pod restart automatically:
   ```bash
   kubectl get pods -n k8s-multi-demo -w
   ```
4. Check events:
   ```bash
   kubectl describe pod <pod-name> -n k8s-multi-demo
   # Look for: Liveness probe failed: HTTP probe failed
   ```

**Expected behavior:**
- Pod becomes unhealthy
- Kubernetes restarts the pod automatically
- New pod comes up healthy
- Zero downtime (other pods handle traffic)

**Test readiness probe (stop receiving traffic):**

1. Access the UI
2. Click **"⚠️ Simulate Not Ready"**
3. Watch pod status:
   ```bash
   kubectl get pods -n k8s-multi-demo -o wide
   # Pod shows 0/1 in READY column
   ```
4. Pod stops receiving traffic (but doesn't restart)
5. Click **"🔄 Reset"** to restore

**Verify with endpoints:**
```bash
# Check which pods are receiving traffic
kubectl get endpoints k8s-demo-service -n k8s-multi-demo

# Healthy pods appear in endpoints
# Unhealthy pods are removed
```

---

### 3. Load Testing

#### **Built-in Load Test (Recommended)**

Access the web UI and use the built-in load test controls:

```
1. Click "🔥 Start Load Test"
   - Generates 20 concurrent requests per batch
   - Runs for 2 minutes
   - Targets the Kubernetes service (distributed load)

2. Monitor in real-time:
   - Live logs show request count
   - CPU usage visible in HPA
   - Pod scaling happens automatically

3. Click "🛑 Stop Load Test"
   - Graceful shutdown
   - CPU drops within 30 seconds
   - Pods scale down in ~5 minutes
```

#### **External Load Test Tools**

**Using Apache Bench:**
```bash
# Install if needed
sudo apt-get install apache2-utils  # Ubuntu
brew install apache2                # macOS

# Run load test
ab -n 10000 -c 100 http://localhost:8080/
```

**Using hey (modern alternative):**
```bash
# Install
go install github.com/rakyll/hey@latest

# Run load test
hey -z 2m -c 50 http://localhost:8080/
```

**Using wrk:**
```bash
# Install
sudo apt-get install wrk  # Ubuntu

# Run load test
wrk -t4 -c50 -d2m http://localhost:8080/
```

---

### 4. Live Monitoring

**From the Web UI:**
1. Click **"📋 View Live Logs"**
2. Logs refresh automatically every 30 seconds
3. See all application events in real-time
4. Scroll to bottom for latest entries

**CLI Monitoring Commands:**

```bash
# Real-time logs from all pods
kubectl logs -f -l app=k8s-demo-app -n k8s-multi-demo

# Logs from specific pod
kubectl logs -f <pod-name> -n k8s-multi-demo

# Watch pods scale
kubectl get pods -n k8s-multi-demo -w

# Watch HPA metrics
kubectl get hpa -n k8s-multi-demo -w

# Live CPU/Memory usage
watch kubectl top pods -n k8s-multi-demo

# View all events
kubectl get events -n k8s-multi-demo --sort-by='.lastTimestamp'
```

---

## 📊 Monitoring & Debugging

### Essential Monitoring Commands

```bash
# Get all resources in namespace
kubectl get all,configmap,secret,ingress,hpa -n k8s-multi-demo

# Detailed pod information
kubectl get pods -n k8s-multi-demo -o wide

# Check resource usage (CPU/Memory)
kubectl top pods -n k8s-multi-demo
kubectl top nodes

# Watch HPA in real-time
kubectl get hpa -n k8s-multi-demo -w

# View recent events
kubectl get events -n k8s-multi-demo --sort-by='.lastTimestamp' | tail -20

# Check service endpoints
kubectl get endpoints -n k8s-multi-demo

# Describe resources for debugging
kubectl describe deployment k8s-demo-app -n k8s-multi-demo
kubectl describe pod <pod-name> -n k8s-multi-demo
kubectl describe hpa k8s-demo-hpa -n k8s-multi-demo
```

### Prometheus Metrics

Access Prometheus metrics from any pod:

```bash
# Via port-forward
kubectl port-forward svc/k8s-demo-service 8080:80 -n k8s-multi-demo
curl http://localhost:8080/metrics

# Via direct pod access
kubectl exec -it <pod-name> -n k8s-multi-demo -- curl localhost:8000/metrics
```

**Available metrics:**
- `app_requests_total` - Total HTTP requests by endpoint
- `app_request_duration_seconds` - Request latency histogram
- Standard Python/FastAPI metrics

### Debugging Pods

```bash
# Get detailed pod information
kubectl describe pod <pod-name> -n k8s-multi-demo

# View container logs
kubectl logs <pod-name> -n k8s-multi-demo
kubectl logs <pod-name> -n k8s-multi-demo --previous  # Previous container

# Execute commands in pod
kubectl exec -it <pod-name> -n k8s-multi-demo -- /bin/bash

# Check pod events
kubectl get events --field-selector involvedObject.name=<pod-name> -n k8s-multi-demo

# Port-forward to specific pod
kubectl port-forward pod/<pod-name> 8080:8000 -n k8s-multi-demo
```

---

## 🔄 Updating the Application

After making code changes to the application:

### Method 1: Complete Rebuild

```bash
# 1. Rebuild Docker image with no cache
docker build -t k8s-demo-app:latest ./app --no-cache

# 2. Load image into kind cluster
kind load docker-image k8s-demo-app:latest --name k8s-demo

# 3. Restart deployment (rolling update)
kubectl rollout restart deployment/k8s-demo-app -n k8s-multi-demo

# 4. Watch rollout progress
kubectl rollout status deployment/k8s-demo-app -n k8s-multi-demo

# 5. Verify new pods
kubectl get pods -n k8s-multi-demo

# 6. Check logs to confirm new code
kubectl logs -l app=k8s-demo-app -n k8s-multi-demo --tail=20
```

### Method 2: Version-Tagged Update

```bash
# 1. Build with version tag
docker build -t k8s-demo-app:v2.0 ./app

# 2. Load into kind
kind load docker-image k8s-demo-app:v2.0 --name k8s-demo

# 3. Update deployment image
kubectl set image deployment/k8s-demo-app \
  app=k8s-demo-app:v2.0 \
  -n k8s-multi-demo

# 4. Watch rollout
kubectl rollout status deployment/k8s-demo-app -n k8s-multi-demo
```

### Rollback if Needed

```bash
# View rollout history
kubectl rollout history deployment/k8s-demo-app -n k8s-multi-demo

# Rollback to previous version
kubectl rollout undo deployment/k8s-demo-app -n k8s-multi-demo

# Rollback to specific revision
kubectl rollout undo deployment/k8s-demo-app --to-revision=2 -n k8s-multi-demo

# Check rollout status
kubectl rollout status deployment/k8s-demo-app -n k8s-multi-demo
```

### Restart Port-Forward After Update

```bash
# Stop existing port-forward
pkill -f "port-forward"

# Start new port-forward
kubectl port-forward svc/k8s-demo-service 8080:80 -n k8s-multi-demo > /dev/null 2>&1 &

# Test connection
curl http://localhost:8080/health
```

---

## 🐛 Troubleshooting

### Pods Not Starting

**Check pod status:**
```bash
kubectl get pods -n k8s-multi-demo
kubectl describe pod <pod-name> -n k8s-multi-demo
```

**Common issues:**

1. **ImagePullBackOff / ErrImagePull**
   ```bash
   # Image not loaded into kind cluster
   docker images | grep k8s-demo-app
   kind load docker-image k8s-demo-app:latest --name k8s-demo
   ```

2. **CrashLoopBackOff**
   ```bash
   # Check application logs
   kubectl logs <pod-name> -n k8s-multi-demo
   kubectl logs <pod-name> -n k8s-multi-demo --previous
   
   # Common causes:
   # - Application crash on startup
   # - Missing dependencies
   # - Port conflicts
   ```

3. **Pending state**
   ```bash
   # Check node resources
   kubectl describe node k8s-demo-control-plane
   
   # Check events
   kubectl get events -n k8s-multi-demo
   ```

### Can't Access the Application

1. **Port-forward not working:**
   ```bash
   # Check if port-forward is running
   ps aux | grep port-forward
   
   # Kill and restart
   pkill -f "port-forward"
   kubectl port-forward svc/k8s-demo-service 8080:80 -n k8s-multi-demo &
   
   # Test locally
   curl http://localhost:8080/health
   ```

2. **Ingress not working:**
   ```bash
   # Check Ingress status
   kubectl get ingress -n k8s-multi-demo
   kubectl describe ingress k8s-demo-ingress -n k8s-multi-demo
   
   # Check NGINX Ingress Controller
   kubectl get pods -n ingress-nginx
   kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller
   
   # Verify hosts file
   cat /etc/hosts | grep k8s-multi-demo
   
   # Test Ingress Controller
   curl -H "Host: k8s-multi-demo.local" http://localhost
   ```

3. **Service not routing traffic:**
   ```bash
   # Check service
   kubectl get svc k8s-demo-service -n k8s-multi-demo
   
   # Check endpoints (should show pod IPs)
   kubectl get endpoints k8s-demo-service -n k8s-multi-demo
   
   # If no endpoints, pods aren't ready
   kubectl get pods -n k8s-multi-demo
   ```

### HPA Not Working

```bash
# Check HPA status
kubectl get hpa -n k8s-multi-demo
kubectl describe hpa k8s-demo-hpa -n k8s-multi-demo

# Common issue: metrics-server not ready
kubectl get pods -n kube-system | grep metrics-server

# If metrics unavailable:
kubectl top nodes  # Should show node metrics
kubectl top pods -n k8s-multi-demo  # Should show pod metrics

# Reinstall metrics-server
kubectl delete -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch -n kube-system deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

# Wait for metrics-server
kubectl wait --for=condition=ready pod -l k8s-app=metrics-server -n kube-system --timeout=120s

# Test metrics
kubectl top pods -n k8s-multi-demo
```

### Load Test Not Scaling Pods

```bash
# Verify load test is running
kubectl logs -l app=k8s-demo-app -n k8s-multi-demo --tail=50 | grep "Load test"

# Check CPU usage
kubectl top pods -n k8s-multi-demo

# Check HPA targets
kubectl get hpa -n k8s-multi-demo
# Look at TARGETS column: should show actual/target (e.g., 95%/70%)

# If CPU not increasing:
# 1. Load test might not be running
# 2. Not enough load being generated
# 3. Resource limits too high

# Manual load test to verify
for i in {1..50}; do (while true; do curl -s http://localhost:8080/ > /dev/null; sleep 0.1; done) & done
```

### Cluster Issues

```bash
# Recreate cluster if corrupted
kind delete cluster --name k8s-demo
./kind_setup.sh  # Run automated setup

# Check Docker
docker ps | grep k8s-demo

# Check kind
kind get clusters

# Verify kubectl context
kubectl config get-contexts
kubectl config use-context kind-k8s-demo
```

---

## 📁 Project Structure

```
.
├── README.md
├── app
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src
│       └── main.py
├── k8s
│   ├── base
│   │   ├── configmap.yaml
│   │   ├── deployment.yaml
│   │   ├── namespace.yaml
│   │   ├── secret.yaml
│   │   ├── service-nodeport-8080.yaml
│   │   ├── service-nodeport.yaml
│   │   └── service.yaml
│   ├── hpa
│   │   └── hpa.yaml
│   └── ingress
│       └── ingress.yaml
├── k8s-tests
│   └── nginx-service.yaml
├── kind_cleanup.sh
├── kind_setup.sh
└── scenario-scripts
    ├── load-test.sh
    └── setup-hpa.sh

```

### Key Files Explained

**app/src/main.py** (1,100+ lines)
- Modern FastAPI application with web dashboard
- Health endpoints: `/health`, `/ready`
- Monitoring: `/metrics` (Prometheus)
- Load test controls: `/load-test/start`, `/load-test/stop`
- Incident simulation: `/simulate/crash`, `/simulate/notready`
- Live logs via `/logs`

**k8s/base/deployment.yaml**
- Production-ready Deployment configuration
- Non-root security (user 1000)
- Liveness probe: restarts unhealthy pods
- Readiness probe: removes unhealthy pods from service
- Resource requests/limits: prevent resource starvation
- ConfigMap and Secret integration

**k8s/hpa/hpa.yaml**
- Horizontal Pod Autoscaler
- Scales based on CPU utilization (70% target)
- Min 2 replicas, max 10 replicas
- Fast scale-up (0s window), slow scale-down (60s window)
- Prevents flapping during load changes

**kind_setup.sh**
- Complete automation script
- Idempotent (can run multiple times)
- Comprehensive error checking
- Colored output for better UX
- Built-in testing and verification

---

## 🧹 Cleanup

### Script for deletion:

``` bash
    ./kind_cleanup.sh
```

### Delete Everything

```bash
# Delete the entire cluster
kind delete cluster --name k8s-demo

# Verify deletion
kind get clusters
# Should not show k8s-demo

# Remove Docker images (optional)
docker rmi k8s-demo-app:latest
```

### Delete Only Application Resources

```bash
# Delete namespace (removes all resources in it)
kubectl delete namespace k8s-multi-demo

# Or delete resources individually
kubectl delete -f k8s/hpa/hpa.yaml
kubectl delete -f k8s/ingress/ingress.yaml
kubectl delete -f k8s/base/service.yaml
kubectl delete -f k8s/base/deployment.yaml
kubectl delete -f k8s/base/secret.yaml
kubectl delete -f k8s/base/configmap.yaml
kubectl delete -f k8s/base/namespace.yaml
```

### Clean Up Port-Forwards

```bash
# Kill all port-forward processes
pkill -f "port-forward"

# Or find and kill specific processes
ps aux | grep port-forward
kill <PID>
```

### Remove kind Completely

```bash
# Remove kind binary
sudo rm /usr/local/bin/kind

# Remove kind configurations
rm -rf ~/.kube/config
```

---

## 🚀 Advanced Topics

### Custom Resource Limits

Edit `k8s/base/deployment.yaml` to adjust resources:

```yaml
resources:
  requests:
    memory: "256Mi"   # Minimum memory
    cpu: "200m"       # Minimum CPU (0.2 cores)
  limits:
    memory: "512Mi"   # Maximum memory
    cpu: "500m"       # Maximum CPU (0.5 cores)
```

### Adjust HPA Thresholds

Edit `k8s/hpa/hpa.yaml`:

```yaml
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      type: Utilization
      averageUtilization: 50  # Change from 70% to 50%

minReplicas: 3  # Increase minimum
maxReplicas: 20 # Increase maximum
```

### Add Memory-Based Scaling

Edit `k8s/hpa/hpa.yaml`:

```yaml
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      type: Utilization
      averageUtilization: 70
- type: Resource
  resource:
    name: memory
    target:
      type: Utilization
      averageUtilization: 80  # Scale if memory > 80%
```

### Enable Multiple Ingress Hosts

Edit `k8s/ingress/ingress.yaml`:

```yaml
spec:
  ingressClassName: nginx
  rules:
  - host: k8s-multi-demo.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: k8s-demo-service
            port:
              number: 80
  - host: demo.local  # Add second host
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: k8s-demo-service
            port:
              number: 80
```

### Enable TLS/HTTPS

```bash
# Generate self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=k8s-multi-demo.local/O=k8s-multi-demo"

# Create TLS secret
kubectl create secret tls demo-tls \
  --cert=tls.crt \
  --key=tls.key \
  -n k8s-multi-demo

# Update ingress.yaml to use TLS
# Add:
# spec:
#   tls:
#   - hosts:
#     - k8s-multi-demo.local
#     secretName: demo-tls
```

### Multi-Node Cluster

```yaml
# kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
  - containerPort: 30080
    hostPort: 30080
- role: worker
- role: worker
- role: worker

# Create cluster
kind create cluster --name k8s-demo --config=kind-config.yaml
```

### Persistent Storage

Add PersistentVolumeClaim:

```yaml
# pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-storage
  namespace: k8s-multi-demo
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi

# Update deployment to use PVC
# Add to deployment.yaml:
# volumes:
# - name: data
#   persistentVolumeClaim:
#     claimName: app-storage
# volumeMounts:
# - name: data
#   mountPath: /data
```

### Network Policies

Add network restrictions:

```yaml
# network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: app-network-policy
  namespace: k8s-multi-demo
spec:
  podSelector:
    matchLabels:
      app: k8s-demo-app
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 53  # DNS
```

---

## 🎓 Learning Outcomes

By working with this project, you will understand:

### Kubernetes Core Concepts
- ✅ **Pods**: Smallest deployable units
- ✅ **Deployments**: Declarative pod management
- ✅ **Services**: Stable networking and load balancing
- ✅ **Ingress**: HTTP routing and domain management
- ✅ **ConfigMaps**: Environment configuration
- ✅ **Secrets**: Sensitive data management
- ✅ **Namespaces**: Resource isolation

### Production Patterns
- ✅ **Health Probes**: Automatic failure detection and recovery
- ✅ **Resource Management**: CPU/memory requests and limits
- ✅ **Auto-Scaling**: Horizontal Pod Autoscaler (HPA)
- ✅ **Rolling Updates**: Zero-downtime deployments
- ✅ **Security**: Non-root containers, least privilege

### DevOps Practices
- ✅ **Infrastructure as Code**: All configs in Git
- ✅ **Automation**: Deployment scripts and CI/CD-ready
- ✅ **Monitoring**: Prometheus metrics, live logs
- ✅ **Incident Response**: Simulated failures and recovery
- ✅ **Documentation**: Production-grade README

### Interview Topics
- ✅ How HPA works and when to use it
- ✅ Difference between liveness and readiness probes
- ✅ Service types (ClusterIP, NodePort, LoadBalancer)
- ✅ Ingress vs Service vs NodePort
- ✅ Resource requests vs limits
- ✅ ConfigMaps vs Secrets
- ✅ Rolling updates and rollbacks
- ✅ Kubernetes networking basics

---

## 💡 Interview Tips

**Common Questions You Can Answer:**

1. **"How do you handle auto-scaling in Kubernetes?"**
   - "I implemented HPA with CPU-based scaling at 70% threshold"
   - "Configured min 2, max 10 replicas with metrics-server"
   - "Tested with load generation showing scale-up and scale-down"

2. **"Explain your deployment strategy"**
   - "Rolling updates for zero-downtime deployments"
   - "Health probes ensure only healthy pods receive traffic"
   - "Resource limits prevent resource starvation"

3. **"How do you monitor applications in Kubernetes?"**
   - "Prometheus metrics endpoint for observability"
   - "kubectl commands for real-time monitoring"
   - "Live logs and event streaming"

4. **"What's the difference between liveness and readiness?"**
   - "Liveness: Kubernetes restarts the pod if it fails"
   - "Readiness: Pod stops receiving traffic if not ready"
   - "I tested both with incident simulation"

5. **"How do you expose services externally?"**
   - "Ingress for production (domain-based routing)"
   - "NodePort for development/testing"
   - "Port-forward for local debugging"
   - "All demonstrated in this project"

---

## 📞 Contact & Author

**Author**: Shay Guedj
**GitHub**: [@shaydevops2024](https://github.com/shaydevops2024)

**Issues & Questions**: [Create an issue on GitHub](https://github.com/shaydevops2024/kubernetes-production-simulator/issues)

---

## 📝 License

MIT License - Free to use for learning and portfolios!

---

## 🌟 Acknowledgments

- **Kubernetes Community** for excellent documentation
- **FastAPI** for the modern web framework
- **kind** for local Kubernetes clusters
- **NGINX Ingress** for production-grade routing

---

## 🎯 Next Steps

Want to expand this project? Here are some ideas:

1. **Add CI/CD Pipeline**
   - GitHub Actions workflow
   - Automated testing
   - Docker image building

2. **Add Monitoring Stack**
   - Prometheus + Grafana
   - Custom dashboards
   - Alerting rules

3. **Add Database**
   - PostgreSQL StatefulSet
   - Persistent storage
   - Database migrations

4. **Add Multiple Services**
   - Microservices architecture
   - Service mesh (Istio)
   - Inter-service communication

5. **Add Security Scanning**
   - Container image scanning
   - Kubernetes security policies
   - RBAC implementation

6. **Deploy to Cloud**
   - AWS EKS
   - Google GKE
   - Azure AKS

---

## ⭐ Star This Repo!

If this project helped you learn Kubernetes or land a DevOps role, please star it on GitHub!

**🚀 Happy Kubernetes Learning! 🚀**
