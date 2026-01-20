# 🚀 Kubernetes Production Demo Project

A **production-grade Kubernetes learning project** that demonstrates real-world DevOps practices.

![Kubernetes](https://img.shields.io/badge/kubernetes-1.28-blue)
![Python](https://img.shields.io/badge/python-3.11-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-teal)

---

## 🎯 What This Project Demonstrates

✅ **Production-Ready Kubernetes Configuration**
- Proper resource limits and requests
- Health and readiness probes
- Horizontal Pod Autoscaling (HPA)
- ConfigMaps and Secrets management
- Ingress for external access

✅ **Best Practices**
- Non-root container user
- Multi-stage Docker builds
- Prometheus metrics endpoint
- Comprehensive logging

✅ **Real-World Scenarios**
- Auto-scaling under load
- Incident simulation (pod crashes)
- Configuration management
- Observability

---

## 📁 Project Structure
```
k8s-production-project/
├── app/
│   ├── src/
│   │   └── main.py          # FastAPI application
│   ├── Dockerfile            # Multi-stage build
│   └── requirements.txt
│
├── k8s/
│   ├── base/
│   │   ├── namespace.yaml
│   │   ├── deployment.yaml   # Pod configuration
│   │   ├── service.yaml      # Internal networking
│   │   ├── configmap.yaml    # Non-sensitive config
│   │   └── secret.yaml       # Sensitive data
│   ├── ingress/
│   │   └── ingress.yaml      # External access
│   └── hpa/
│       └── hpa.yaml          # Auto-scaling config
│
├── scripts/
│   ├── deploy.sh             # Automated deployment
│   └── load-test.sh          # Load testing
│
├── Makefile                  # Convenient commands
└── README.md
```

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites
```bash
# Install Docker
# Install kind
brew install kind  # macOS
# or
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64

# Install kubectl
brew install kubectl  # macOS
```

### Step 1: Create Cluster
```bash
make setup
# or manually:
kind create cluster --name k8s-demo
```

### Step 2: Deploy Everything
```bash
make deploy
# This will:
# - Build Docker image
# - Deploy to Kubernetes
# - Install Ingress controller
# - Configure auto-scaling
```

### Step 3: Access the Application
```bash
# Add to /etc/hosts
echo "127.0.0.1 k8s-demo.local" | sudo tee -a /etc/hosts

# Open browser
open http://k8s-demo.local
```

**You should see a beautiful web dashboard!** 🎉

---

## 🧪 How to Test Everything

### 1️⃣ **Verify Deployment**
```bash
# Check pods are running
kubectl get pods -n k8s-demo

# Expected output:
# NAME                            READY   STATUS    RESTARTS   AGE
# k8s-demo-app-xxxxxxxxx-xxxxx    1/1     Running   0          1m
# k8s-demo-app-xxxxxxxxx-xxxxx    1/1     Running   0          1m
```

### 2️⃣ **Test Web UI**

Open browser: `http://k8s-demo.local`

You should see:
- ✅ Green "Healthy" status
- ✅ Green "Ready" status
- ✅ Environment: production
- ✅ Interactive buttons

### 3️⃣ **Test API Endpoints**
```bash
# Health check
curl http://k8s-demo.local/health
# Response: {"status":"healthy"}

# Readiness check
curl http://k8s-demo.local/ready
# Response: {"status":"ready"}

# Prometheus metrics
curl http://k8s-demo.local/metrics
# Response: (Prometheus format metrics)

# API documentation (Swagger UI)
open http://k8s-demo.local/docs
```

### 4️⃣ **Test Auto-Scaling**
```bash
# Watch HPA in one terminal
kubectl get hpa -n k8s-demo -w

# Run load test in another terminal
make test

# You should see:
# - CPU usage increase
# - Pods scale from 2 → 3 → 4... (up to 10)
# - After load stops, pods scale back down
```

### 5️⃣ **Simulate Pod Crash**

**Option A: Using Web UI**
1. Open `http://k8s-demo.local`
2. Click "💥 Simulate Crash"
3. Watch the status turn red
4. Kubernetes will restart the pod automatically!

**Option B: Using API**
```bash
curl -X POST http://k8s-demo.local/simulate/crash
```

**Watch recovery:**
```bash
kubectl get pods -n k8s-demo -w
# You'll see pod restart
```

### 6️⃣ **Simulate Not Ready**
```bash
# Make app not ready
curl -X POST http://k8s-demo.local/simulate/notready

# Check that Kubernetes stops routing traffic
kubectl get pods -n k8s-demo
# Pod shows 1/1 but READY will be 0/1

# Reset
curl -X POST http://k8s-demo.local/reset
```

### 7️⃣ **Test Configuration Changes**
```bash
# Edit ConfigMap
kubectl edit configmap app-config -n k8s-demo
# Change APP_ENV from "production" to "staging"

# Restart pods to pick up new config
kubectl rollout restart deployment/k8s-demo-app -n k8s-demo

# Verify
curl http://k8s-demo.local/api/info
# Should show environment: "staging"
```

---

## 📊 Monitoring & Observability

### View Logs
```bash
# Live logs
make logs
# or
kubectl logs -f -l app=k8s-demo-app -n k8s-demo

# Logs from specific pod
kubectl logs k8s-demo-app-xxxxxxxxx-xxxxx -n k8s-demo
```

### Check Resource Usage
```bash
# Pod resource usage (requires metrics-server)
kubectl top pods -n k8s-demo

# Node resource usage
kubectl top nodes
```

### View Events
```bash
# See what Kubernetes is doing
kubectl get events -n k8s-demo --sort-by='.lastTimestamp'
```

---

## 🎓 Learning Exercises

### Exercise 1: Scale Manually
```bash
kubectl scale deployment k8s-demo-app --replicas=5 -n k8s-demo
kubectl get pods -n k8s-demo -w
```

### Exercise 2: Update the Application
```bash
# Edit app/src/main.py
# Change the welcome message

# Rebuild and redeploy
make build
kubectl rollout restart deployment/k8s-demo-app -n k8s-demo

# Watch rolling update
kubectl rollout status deployment/k8s-demo-app -n k8s-demo
```

### Exercise 3: Add New Environment Variable
```bash
# Edit k8s/base/configmap.yaml
# Add: NEW_FEATURE: "enabled"

kubectl apply -f k8s/base/configmap.yaml
kubectl rollout restart deployment/k8s-demo-app -n k8s-demo
```

---

## 🐛 Troubleshooting

### Pods Not Starting?
```bash
kubectl describe pod <pod-name> -n k8s-demo
kubectl logs <pod-name> -n k8s-demo
```

### Image Not Found?
```bash
# Rebuild and load image
make build
```

### Cannot Access via Browser?
```bash
# Check /etc/hosts
cat /etc/hosts | grep k8s-demo

# Check Ingress
kubectl get ingress -n k8s-demo

# Port forward as backup
kubectl port-forward svc/k8s-demo-service 8080:80 -n k8s-demo
# Then open: http://localhost:8080
```

### HPA Not Working?
```bash
# Install metrics-server for kind
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Patch for kind (self-signed certs)
kubectl patch -n kube-system deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
```

---

## 🧹 Cleanup
```bash
# Delete everything
make clean

# Or manually
kind delete cluster --name k8s-demo
```

---

## 📚 What Each Component Does

| Component | Purpose | Why It Matters |
|-----------|---------|----------------|
| **Namespace** | Isolates resources | Organization, security boundaries |
| **Deployment** | Manages pods | Ensures desired state, rolling updates |
| **Service** | Internal networking | Stable IP for pod communication |
| **Ingress** | External access | Routes traffic from outside cluster |
| **ConfigMap** | Non-sensitive config | Change config without rebuilding |
| **Secret** | Sensitive data | Secure storage of passwords, tokens |
| **HPA** | Auto-scaling | Handles traffic spikes automatically |
| **Probes** | Health checks | Auto-restart unhealthy pods |

---

## 🎯 Production Readiness Checklist

✅ Resource limits defined  
✅ Non-root user  
✅ Health probes configured  
✅ Configuration externalized  
✅ Secrets not in Git  
✅ Auto-scaling enabled  
✅ Metrics endpoint exposed  
✅ Proper logging  
✅ Documentation complete  

---

## 🤝 Contributing

This is a learning project! Feel free to:
- Add features
- Improve documentation
- Report issues
- Suggest enhancements

---

## 📝 License

MIT License - Use this for learning and your portfolio!

---

## 🌟 Next Steps

1. **Add Prometheus & Grafana** (monitoring dashboards)
2. **Implement CI/CD** (GitHub Actions)
3. **Add database** (PostgreSQL with persistent storage)
4. **Multi-environment** (dev, staging, prod)
5. **Service mesh** (Istio or Linkerd)

---

**Built with ❤️ for learning Kubernetes**
