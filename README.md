# 🚀 Kubernetes Production Simulator

A **production-grade Kubernetes learning project** demonstrating real-world DevOps practices with auto-scaling, monitoring, and incident simulation.

![Kubernetes](https://img.shields.io/badge/kubernetes-1.28-blue)
![Python](https://img.shields.io/badge/python-3.11-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-teal)

**GitHub:** [shaydevops2024/kubernetes-production-simulator](https://github.com/shaydevops2024/kubernetes-production-simulator)

---

## 🎯 What This Project Demonstrates

✅ **Production-Ready Kubernetes Configuration**
- Horizontal Pod Autoscaling (HPA)
- Health & readiness probes
- Resource limits & requests
- ConfigMaps & Secrets management
- Ingress routing

✅ **Modern Web Interface**
- Real-time status monitoring
- Incident simulation controls
- Live log viewer
- Professional UI/UX

✅ **DevOps Best Practices**
- Non-root containers
- Multi-stage Docker builds
- Prometheus metrics
- Comprehensive automation

---

## 📋 Prerequisites

### Required Tools:
- **Docker** ([Install Guide](https://docs.docker.com/get-docker/))
- **kubectl** ([Install Guide](https://kubernetes.io/docs/tasks/tools/))
- **kind** (Kubernetes in Docker)

### Install kind:

**On WSL2/Ubuntu:**
```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
```

**On macOS:**
```bash
brew install kind
```

---

## 🚀 Quick Start

### **Option 1: WSL2 (Windows)**
```bash
# 1. Clone repository
git clone https://github.com/shaydevops2024/kubernetes-production-simulator.git
cd kubernetes-production-simulator

# 2. Create kind cluster with ingress support
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
EOF

# 3. Install NGINX Ingress Controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=90s

# 4. Build and deploy application
docker build -t k8s-demo-app:latest ./app
kind load docker-image k8s-demo-app:latest --name k8s-demo

kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/base/configmap.yaml
kubectl apply -f k8s/base/secret.yaml
kubectl apply -f k8s/base/deployment.yaml
kubectl apply -f k8s/base/service.yaml
kubectl apply -f k8s/ingress/ingress.yaml

# 5. Setup HPA (auto-scaling)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch -n kube-system deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl apply -f k8s/hpa/hpa.yaml

# 6. Wait for pods
kubectl wait --for=condition=ready pod -l app=k8s-demo-app -n k8s-multi-demo --timeout=120s

# 7. Start port-forward
kubectl port-forward svc/k8s-demo-service 8080:80 -n k8s-multi-demo > /dev/null 2>&1 &

# 8. Open in Windows browser
explorer.exe http://localhost:8080
```

---

### **Option 2: Ubuntu Server (Remote or Local)**
```bash
# 1. Clone repository
git clone https://github.com/shaydevops2024/kubernetes-production-simulator.git
cd kubernetes-production-simulator

# 2. Create kind cluster
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
EOF

# 3. Install NGINX Ingress
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=90s

# 4. Deploy application
docker build -t k8s-demo-app:latest ./app
kind load docker-image k8s-demo-app:latest --name k8s-demo

kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/base/configmap.yaml
kubectl apply -f k8s/base/secret.yaml
kubectl apply -f k8s/base/deployment.yaml
kubectl apply -f k8s/base/service.yaml
kubectl apply -f k8s/ingress/ingress.yaml

# 5. Setup HPA
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch -n kube-system deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl apply -f k8s/hpa/hpa.yaml

# 6. Wait for ready
kubectl wait --for=condition=ready pod -l app=k8s-demo-app -n k8s-multi-demo --timeout=120s

# 7. Access the application
# Option A: Port-forward (local access)
kubectl port-forward svc/k8s-demo-service 8080:80 -n k8s-multi-demo

# Option B: SSH tunnel (from your local machine)
# ssh -L 8080:localhost:8080 user@your-server-ip
# Then open: http://localhost:8080

# Option C: Use server IP directly
# Get server IP: hostname -I | awk '{print $1}'
# Access: http://YOUR_SERVER_IP (requires exposing port 80)
```

---

### **Option 3: Ubuntu Desktop (with GUI)**

Same as Ubuntu Server, but open browser directly:
```bash
# After step 7, start port-forward
kubectl port-forward svc/k8s-demo-service 8080:80 -n k8s-multi-demo &

# Open browser
google-chrome http://localhost:8080
# or
firefox http://localhost:8080
```

---

## 🧪 Testing Auto-Scaling (HPA)

### **Method 1: Using the UI**
1. Open `http://localhost:8080`
2. Click **"🔥 Start Load Test"**
3. Open terminal and watch scaling:
```bash
   kubectl get hpa -n k8s-multi-demo -w
```
4. See pods scale from 2 → 3 → 4...
5. Click **"🛑 Stop Load Test"**
6. Watch scale down to 2 (takes ~5 min)

### **Method 2: CLI Load Test (Professional)**
```bash
# Terminal 1: Watch HPA
kubectl get hpa -n k8s-multi-demo -w

# Terminal 2: Generate load
for i in {1..50}; do 
  (while true; do 
    curl -s http://localhost:8080/ > /dev/null
    sleep 0.1
  done) &
done

# Wait 2 minutes, then stop
pkill curl

# Watch scale down in Terminal 1
```

---

## 📊 Monitoring Commands
```bash
# Watch HPA in real-time
kubectl get hpa -n k8s-multi-demo -w

# Watch pods scale
kubectl get pods -n k8s-multi-demo -w

# Check CPU/Memory usage
kubectl top pods -n k8s-multi-demo

# View logs
kubectl logs -f -l app=k8s-demo-app -n k8s-multi-demo

# Check all resources
kubectl get all -n k8s-multi-demo
```

---

## 🎯 Features to Test

### **1. Auto-Scaling**
- Start load test (UI or CLI)
- Watch pods increase automatically
- Stop load → pods decrease

### **2. Health Probes**
- Click **"💥 Simulate Crash"** → Pod restarts
- Click **"⚠️ Simulate Not Ready"** → Traffic stops
- Click **"🔄 Reset"** → Back to normal

### **3. Live Monitoring**
- Click **"📋 View Live Logs"**
- Copy CLI commands directly
- Watch real-time application logs

---

## 🔄 Update Application

After making code changes:
```bash
# 1. Rebuild image
docker build -t k8s-demo-app:latest ./app --no-cache

# 2. Load into kind
kind load docker-image k8s-demo-app:latest --name k8s-demo

# 3. Restart deployment
kubectl rollout restart deployment/k8s-demo-app -n k8s-multi-demo

# 4. Wait for rollout
kubectl rollout status deployment/k8s-demo-app -n k8s-multi-demo

# 5. Restart port-forward
pkill -f "port-forward"
kubectl port-forward svc/k8s-demo-service 8080:80 -n k8s-multi-demo > /dev/null 2>&1 &
```

---

## 🧹 Cleanup
```bash
# Delete cluster
kind delete cluster --name k8s-demo

# Verify deletion
kind get clusters
```

---

## 🐛 Troubleshooting

### **Pods not starting?**
```bash
kubectl describe pod <pod-name> -n k8s-multi-demo
kubectl logs <pod-name> -n k8s-multi-demo
```

### **Can't access UI?**
```bash
# Check port-forward is running
ps aux | grep port-forward

# Restart port-forward
pkill -f "port-forward"
kubectl port-forward svc/k8s-demo-service 8080:80 -n k8s-multi-demo &
```

### **HPA not working?**
```bash
# Check metrics-server
kubectl get pods -n kube-system | grep metrics-server

# Reinstall if needed
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch -n kube-system deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
```

---

## 📚 Project Structure
```
kubernetes-production-simulator/
├── app/
│   ├── src/
│   │   └── main.py          # FastAPI application
│   ├── Dockerfile            # Multi-stage build
│   └── requirements.txt
├── k8s/
│   ├── base/
│   │   ├── namespace.yaml
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── configmap.yaml
│   │   └── secret.yaml
│   ├── ingress/
│   │   └── ingress.yaml
│   └── hpa/
│       └── hpa.yaml
└── README.md
```

---

## 🎓 What You'll Learn

- ✅ Kubernetes deployments & services
- ✅ Auto-scaling with HPA
- ✅ Health & readiness probes
- ✅ ConfigMaps & Secrets
- ✅ Ingress routing
- ✅ Resource management
- ✅ Monitoring & observability
- ✅ Incident handling

---

## 📝 License

MIT License - Free to use for learning and portfolios!

---

## 🌟 Star this repo if it helped you learn Kubernetes!

**Author:** Shay  
**GitHub:** [shaydevops2024](https://github.com/shaydevops2024)