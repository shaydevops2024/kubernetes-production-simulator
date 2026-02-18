# 🚀 Kubernetes Production Simulator

> **A comprehensive, hands-on DevOps learning platform** - Master Kubernetes, ArgoCD, Ansible, Helm, Jenkins, GitLab CI, and Terraform through interactive, real-world scenarios.

![Kubernetes](https://img.shields.io/badge/kubernetes-1.28+-blue) ![Python](https://img.shields.io/badge/python-3.11-green) ![FastAPI](https://img.shields.io/badge/FastAPI-0.104-teal) ![Docker](https://img.shields.io/badge/docker-24.0+-blue) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)

**Educational Platform** | **DevOps Training** | **Production Patterns** | **Portfolio Project**

---

## 📑 Table of Contents

- [Overview](#-overview)
- [What's Inside](#-whats-inside)
- [Features](#-features)
- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Scenario Categories](#-scenario-categories)
- [Using the Platform](#-using-the-platform)
- [Access Methods](#-access-methods)
- [Development](#-development)
- [Project Structure](#-project-structure)
- [Adding New Scenarios](#-adding-new-scenarios)
- [Monitoring & Debugging](#-monitoring--debugging)
- [Troubleshooting](#-troubleshooting)
- [Cleanup](#-cleanup)
- [Learning Outcomes](#-learning-outcomes)
- [Contributing](#-contributing)

---

## 🎯 Overview

**Kubernetes Production Simulator** is a full-stack educational platform designed for learning DevOps technologies through hands-on practice. It provides an interactive web interface with **50+ real-world scenarios** covering the entire DevOps ecosystem.

Unlike traditional tutorials, this platform:
- ✅ **Runs locally** on your machine with Kind (no cloud costs)
- ✅ **Interactive scenarios** with step-by-step guided commands
- ✅ **Real Kubernetes cluster** - not simulated
- ✅ **Production patterns** - actual configurations you'll use in production
- ✅ **Self-paced learning** - complete scenarios at your own speed
- ✅ **Validation scripts** - verify your work automatically
- ✅ **Clean architecture** - easy to extend with new scenarios

**Perfect for:**
- DevOps engineers building portfolios
- Students learning Kubernetes and cloud-native technologies
- Professionals preparing for CKA/CKAD certifications
- Teams training on GitOps and CI/CD practices
- Technical interviews and skill demonstrations

---

## 📦 What's Inside

### 🎓 Learning Scenarios (50+)

| Category | Count | Topics Covered |
|----------|-------|----------------|
| **Kubernetes** | 16 | HPA, VPA, Rolling Updates, StatefulSets, DaemonSets, Network Policies, RBAC, Pod Disruption Budgets, Blue-Green Deployments, Node Affinity |
| **ArgoCD** | 12 | GitOps, Auto-sync, Self-healing, Sync Waves, Hooks, App of Apps, Kustomize, Helm, Multi-source Apps, Canary Deployments, Disaster Recovery |
| **Ansible** | 12 | Inventory, Package Management, User Management, Templates, Multi-tier Apps, Vault, Rolling Updates, Hardening, Monitoring, Disaster Recovery, CI/CD Integration |
| **Helm** | Multiple | Chart Creation, Dependencies, Values, Templates, Releases, Upgrades, Rollbacks |
| **Jenkins** | Multiple | Pipeline Creation, Declarative Pipelines, Shared Libraries, Blue Ocean, Integration |
| **GitLab CI** | Multiple | Pipeline Setup, Stages, Jobs, Artifacts, Caching, Multi-project Pipelines |
| **Terraform** | Multiple | Infrastructure as Code, State Management, Modules, Providers, Workspaces |

### 🛠️ Full-Stack Application

- **Backend**: FastAPI (Python) - High-performance async API
- **Frontend**: Vanilla JavaScript - No framework dependencies, fast and lightweight
- **Database**: PostgreSQL - Persistent storage for progress tracking
- **Container Runtime**: Docker - Consistent environments
- **Kubernetes**: Kind - Local multi-node clusters
- **Monitoring**: Prometheus metrics integration
- **CI/CD Tools**: ArgoCD, Jenkins, GitLab CI integration ready

---

## ✨ Features

### 🎮 Interactive Learning Experience

- **Scenario Browser** - Browse all scenarios by category with difficulty ratings
- **Step-by-Step Guides** - Each scenario includes detailed instructions
- **Command Reference** - Copy-paste ready commands with explanations
- **Live Validation** - Check your work with built-in validation scripts
- **Progress Tracking** - Save your progress in PostgreSQL database
- **Clean Playgrounds** - Each scenario runs in isolated namespaces

### 🏗️ Production-Ready Architecture

- **Multi-namespace Isolation** - Clean separation between scenarios
- **Resource Management** - Proper requests/limits on all workloads
- **Health Monitoring** - Liveness and readiness probes
- **Auto-scaling** - HPA and VPA demonstrations
- **Security Best Practices** - RBAC, Network Policies, Pod Security
- **GitOps Workflows** - Full ArgoCD integration
- **Infrastructure as Code** - All manifests versioned in Git

### 🔧 Developer-Friendly

- **Easy Setup** - One script deploys everything
- **Hot Reload** - Update scenarios without redeploying
- **Comprehensive Logging** - Debug with detailed logs
- **API Documentation** - FastAPI auto-generated docs at `/docs`
- **Extensible** - Add new scenarios easily
- **Well-Documented** - Every scenario includes README and commands.json

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Kind Kubernetes Cluster (3 nodes)                 │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      Ingress Controller (NGINX)                   │   │
│  │                         Port 80 → NodePort 30080                  │   │
│  └────────────────────┬──────────────────────────────────────────────┘   │
│                       │                                                   │
│  ┌────────────────────▼─────────────────────────────────────────────┐   │
│  │                     k8s-multi-demo Namespace                       │   │
│  │  ┌──────────────────────────────────────────────────────────────┐ │   │
│  │  │  FastAPI Application (Deployment: 2 replicas)                │ │   │
│  │  │  - REST API: /api/scenarios, /api/argocd-scenarios, etc.     │ │   │
│  │  │  - Web UI: index.html, scenarios.html, scenario-detail.html  │ │   │
│  │  │  - Database: PostgreSQL connection for progress tracking     │ │   │
│  │  │  - Monitoring: /metrics (Prometheus), /health, /ready        │ │   │
│  │  └──────────────────────────────────────────────────────────────┘ │   │
│  │  ┌──────────────────────────────────────────────────────────────┐ │   │
│  │  │  PostgreSQL StatefulSet (1 replica)                          │ │   │
│  │  │  - PersistentVolume: 1Gi storage                             │ │   │
│  │  │  - Database: k8s_demo (users, tasks tables)                  │ │   │
│  │  └──────────────────────────────────────────────────────────────┘ │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      Scenarios Namespace                          │   │
│  │  Dynamic scenario workloads (HPA demos, StatefulSets, etc.)      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    ArgoCD Namespace (Optional)                    │   │
│  │  - ArgoCD Server (NodePort 30800)                                │   │
│  │  - Application Controller                                         │   │
│  │  - Repo Server                                                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Jenkins Namespace (Optional)                   │   │
│  │  - Jenkins Server (NodePort 30880)                               │   │
│  │  - Build Agents                                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

                            ↕ kubectl commands

                    ┌─────────────────────┐
                    │   User's Terminal   │
                    │  - kubectl          │
                    │  - helm             │
                    │  - argocd CLI       │
                    │  - ansible          │
                    └─────────────────────┘
```

### Key Components

1. **Kind Cluster** - Local multi-node Kubernetes cluster
2. **FastAPI Backend** - Serves scenarios, tracks progress, provides API
3. **PostgreSQL Database** - Stores user data, tasks, progress
4. **Frontend (Vanilla JS)** - Interactive scenario browser and detail views
5. **Scenario Directories** - Self-contained scenarios with YAML, README, commands.json
6. **NGINX Ingress** - Routes traffic to applications
7. **Metrics Server** - Enables HPA with CPU/memory metrics
8. **ArgoCD** (optional) - GitOps continuous delivery
9. **Jenkins** (optional) - CI/CD pipeline automation

---

## 📋 Prerequisites

### Required Tools

| Tool | Version | Installation |
|------|---------|-------------|
| **Docker** | 24.0+ | [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) |
| **kubectl** | 1.28+ | [kubernetes.io/docs/tasks/tools](https://kubernetes.io/docs/tasks/tools/) |
| **kind** | 0.20+ | [kind.sigs.k8s.io](https://kind.sigs.k8s.io/docs/user/quick-start/) |
| **Helm** (optional) | 3.0+ | [helm.sh/docs/intro/install](https://helm.sh/docs/intro/install/) |
| **ArgoCD CLI** (optional) | 2.8+ | [argo-cd.readthedocs.io](https://argo-cd.readthedocs.io/en/stable/cli_installation/) |

### System Requirements

- **CPU**: 4+ cores recommended (2 minimum)
- **RAM**: 8GB+ available (4GB minimum)
- **Disk**: 20GB+ free space
- **OS**: Linux, macOS, or Windows with WSL2

### Install kind (Quick Reference)

**Linux/WSL2:**
```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
kind version
```

**macOS:**
```bash
brew install kind
kind version
```

**Windows (PowerShell):**
```powershell
choco install kind
# or
scoop install kind
```

---

## 🚀 Quick Start

### Automated Deployment (Recommended)

**Complete setup in 3 commands:**

```bash
# 1. Clone the repository
git clone https://github.com/shaydevops2024/kubernetes-production-simulator.git
cd kubernetes-production-simulator

# 2. Run the automated deployment script
chmod +x kind_setup.sh
./kind_setup.sh

# 3. Access the application
# Browser: http://localhost:30080
# Or port-forward: kubectl port-forward svc/k8s-demo-service 8080:80 -n k8s-multi-demo
```

**What the script does:**
1. ✅ Validates prerequisites (Docker, kubectl, kind)
2. ✅ Creates Kind cluster with 3 nodes and port mappings
3. ✅ Installs NGINX Ingress Controller
4. ✅ Deploys PostgreSQL database with persistent storage
5. ✅ Builds and loads application Docker image
6. ✅ Deploys FastAPI backend (2 replicas)
7. ✅ Installs metrics-server for HPA support
8. ✅ Creates namespaces for scenario isolation
9. ✅ Runs health checks and verification
10. ✅ Displays access URLs and next steps

**Expected output:**
```
============================================
DEPLOYMENT COMPLETE! 🎉
============================================

✅ Cluster: k8s-demo (3 nodes)
✅ Namespace: k8s-multi-demo
✅ Pods: 3/3 Running (app: 2, db: 1)
✅ Database: PostgreSQL ready
✅ Ingress: NGINX Ingress Controller running
✅ Metrics: metrics-server ready

Access the platform:
  🌐 http://localhost:30080 (NodePort)
  🔧 http://localhost:8080 (port-forward)

API Documentation:
  📚 http://localhost:30080/docs (OpenAPI/Swagger)

Scenario Namespaces:
  - k8s-multi-demo (main app)
  - scenarios (K8s scenarios)
  - argocd (ArgoCD scenarios)

Next Steps:
  1. Open http://localhost:30080 in your browser
  2. Browse scenarios by category
  3. Follow step-by-step instructions
  4. Verify your work with validation scripts

Useful Commands:
  kubectl get all -n k8s-multi-demo
  kubectl get all -n scenarios
  kubectl logs -f -l app=k8s-demo-app -n k8s-multi-demo
```

---

## 🎓 Scenario Categories

### 1. Kubernetes Fundamentals (16 scenarios)

| # | Scenario | Difficulty | Duration | Key Concepts |
|---|----------|-----------|----------|--------------|
| 01 | HPA Autoscaling | Easy | 15 min | Horizontal Pod Autoscaler, metrics-server, CPU-based scaling |
| 02 | Node Failure Simulation | Medium | 20 min | Node drain, cordon, pod rescheduling, resilience |
| 03 | VPA Configuration | Medium | 20 min | Vertical Pod Autoscaler, resource recommendations |
| 04 | ConfigMaps & Secrets | Easy | 15 min | Configuration management, environment variables |
| 05 | Rolling Updates | Easy | 15 min | Zero-downtime deployments, rollout strategies |
| 06 | Network Policies | Hard | 30 min | Network segmentation, ingress/egress rules |
| 07 | Pod Disruption Budget | Medium | 20 min | High availability, controlled disruptions |
| 08 | Self-Healing | Easy | 15 min | Automatic recovery, replica management |
| 09 | Liveness & Readiness | Easy | 15 min | Health probes, traffic management |
| 10 | StatefulSet Operations | Medium | 25 min | Stateful workloads, ordered deployment, persistent volumes |
| 11 | DaemonSet Deployment | Medium | 20 min | Node-level services, system daemons |
| 12 | Jobs & CronJobs | Easy | 15 min | Batch processing, scheduled tasks |
| 13 | Blue-Green Deployment | Medium | 25 min | Deployment strategies, instant rollback |
| 14 | Ingress Configuration | Medium | 20 min | HTTP routing, virtual hosts, path-based routing |
| 15 | RBAC Setup | Hard | 30 min | Role-based access control, service accounts |
| 16 | Node Affinity | Medium | 20 min | Pod scheduling, node selection, taints/tolerations |

### 2. ArgoCD & GitOps (12 scenarios)

| # | Scenario | Difficulty | Duration | Key Concepts |
|---|----------|-----------|----------|--------------|
| 01 | Basic App Deploy | Easy | 15 min | ArgoCD application, Git repository sync |
| 02 | Auto-Sync & Self-Heal | Medium | 20 min | Automated deployments, drift detection |
| 03 | Sync Waves & Hooks | Hard | 30 min | Ordered deployments, pre/post hooks |
| 04 | App of Apps Pattern | Medium | 25 min | Multi-app management, hierarchical apps |
| 05 | Kustomize Environments | Medium | 25 min | Environment overlays, configuration variants |
| 06 | Helm Deployment | Medium | 20 min | Helm charts via ArgoCD, values management |
| 07 | GitOps Rollback | Medium | 20 min | Git-based rollback, history management |
| 08 | Multi-Source App | Hard | 30 min | Multiple Git sources, combined deployments |
| 09 | Health Checks | Medium | 20 min | Custom health checks, resource hooks |
| 10 | Projects & RBAC | Hard | 30 min | Multi-tenancy, access control |
| 11 | Canary Rollout | Hard | 35 min | Progressive delivery, traffic splitting |
| 12 | Disaster Recovery | Hard | 30 min | Backup/restore, cluster migration |

### 3. Ansible Automation (12 scenarios)

| # | Scenario | Difficulty | Duration | Key Concepts |
|---|----------|-----------|----------|--------------|
| 01 | Ansible Basics & Inventory | Easy | 15 min | Inventory files, ad-hoc commands, modules |
| 02 | Package Management | Easy | 15 min | Package installation, system updates |
| 03 | User Management | Easy | 15 min | User creation, SSH keys, sudo access |
| 04 | File Deployment & Templates | Medium | 20 min | Jinja2 templates, file distribution |
| 05 | Multi-Tier App Deployment | Medium | 25 min | Web/app/db tiers, orchestration |
| 06 | Ansible Vault (Secrets) | Medium | 20 min | Encrypted variables, secure credential storage |
| 07 | Rolling Updates (Zero Downtime) | Medium | 25 min | Serial execution, health checks |
| 08 | System Hardening & Compliance | Hard | 30 min | Security baselines, CIS benchmarks |
| 09 | Monitoring Stack Deployment | Hard | 35 min | Prometheus, Grafana, exporters |
| 10 | Disaster Recovery Automation | Hard | 30 min | Backup automation, restore procedures |
| 11 | Dynamic Infrastructure Orchestration | Hard | 35 min | Dynamic inventory, cloud provisioning |
| 12 | CI/CD Pipeline Automation | Hard | 40 min | Jenkins/GitLab integration, deployment pipelines |

### 4. Additional Modules

- **Helm**: Chart authoring, dependency management, templating, release management
- **Jenkins**: Pipeline as Code, Declarative/Scripted pipelines, Blue Ocean, integrations
- **GitLab CI**: Pipeline configuration, stages, jobs, artifacts, multi-project pipelines
- **Terraform**: Infrastructure as Code, state management, modules, workspaces

---

## 💻 Using the Platform

### Web Interface

1. **Home Dashboard** (`index.html`)
   - Overview of all scenario categories
   - Quick access to documentation
   - System status indicators
   - Database connection status

2. **Scenario Browser** (`scenarios.html`, `argocd-scenarios.html`, etc.)
   - Browse scenarios by category
   - Filter by difficulty level
   - See estimated completion time
   - Track progress (coming soon)

3. **Scenario Detail View** (`scenario-detail.html`)
   - Full scenario description
   - Learning objectives
   - Step-by-step command guide
   - Copy-paste ready commands
   - Expected output examples
   - Validation instructions
   - Cleanup procedures

### REST API

Access the API documentation at `http://localhost:30080/docs`

**Key Endpoints:**

```bash
# Get all Kubernetes scenarios
GET /api/scenarios

# Get specific scenario
GET /api/scenarios/{scenario_id}

# Get ArgoCD scenarios
GET /api/argocd-scenarios
GET /api/argocd-scenarios/{scenario_id}

# Get Ansible scenarios
GET /api/ansible-scenarios
GET /api/ansible-scenarios/{scenario_id}

# Health checks
GET /health
GET /ready

# Prometheus metrics
GET /metrics

# Database stats
GET /api/db/stats
```

### Command-Line Workflow

**Typical scenario workflow:**

```bash
# 1. Access the web UI to browse scenarios
# http://localhost:30080

# 2. Select a scenario (e.g., "01-hpa-autoscaling")

# 3. Follow the commands from the scenario detail page
kubectl apply -f k8s-scenarios/01-hpa-autoscaling/deployment.yaml
kubectl apply -f k8s-scenarios/01-hpa-autoscaling/hpa.yaml

# 4. Verify the deployment
kubectl get hpa -n scenarios

# 5. Run validation script (if available)
./k8s-scenarios/01-hpa-autoscaling/validate.sh

# 6. Clean up when done
kubectl delete -f k8s-scenarios/01-hpa-autoscaling/
```

---

## 🌐 Access Methods

### 1. NodePort Access (Recommended - Simplest)

```bash
# Application is automatically exposed on port 30080
# No additional commands needed
open http://localhost:30080

# For WSL2 users
explorer.exe http://localhost:30080
```

**Advantages:**
- ✅ Works immediately after deployment
- ✅ No additional configuration needed
- ✅ Persistent connection
- ✅ Fixed port (30080)
- ✅ Perfect for WSL2 users

### 2. Port-Forward (Alternative)

```bash
# Start port-forward
kubectl port-forward svc/k8s-demo-service 8080:80 -n k8s-multi-demo

# Access application
open http://localhost:8080

# Stop port-forward
pkill -f "port-forward"
```

### 3. Ingress with Custom Domain (Advanced)

```bash
# Add to /etc/hosts (Linux/macOS/WSL2)
echo "127.0.0.1 k8s-multi-demo.local" | sudo tee -a /etc/hosts

# Access via Ingress
open http://k8s-multi-demo.local

# Windows (PowerShell as Administrator)
Add-Content -Path C:\Windows\System32\drivers\etc\hosts -Value "127.0.0.1 k8s-multi-demo.local"
```

### 4. ArgoCD Access (If Installed)

```bash
# ArgoCD UI is exposed on NodePort 30800
open http://localhost:30800

# Get initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

### 5. Jenkins Access (If Installed)

```bash
# Jenkins UI is exposed on NodePort 30880
open http://localhost:30880

# Get initial admin password
kubectl exec -n jenkins deployment/jenkins -- cat /var/jenkins_home/secrets/initialAdminPassword
```

---

## 🛠️ Development

### Running Locally (Outside Kubernetes)

For development and testing:

```bash
# Install dependencies
cd app
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/k8s_demo"

# Run the application
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Access at http://localhost:8000
```

### Rebuilding After Code Changes

```bash
# Rebuild Docker image
docker build -t k8s-demo-app:latest ./app

# Load into Kind cluster
kind load docker-image k8s-demo-app:latest --name k8s-demo

# Restart deployment (rolling update)
kubectl rollout restart deployment/k8s-demo-app -n k8s-multi-demo

# Watch rollout progress
kubectl rollout status deployment/k8s-demo-app -n k8s-multi-demo

# Verify new pods
kubectl get pods -n k8s-multi-demo
```

### Database Migrations

```bash
# Connect to PostgreSQL pod
kubectl exec -it deployment/postgres -n k8s-multi-demo -- psql -U postgres -d k8s_demo

# View tables
\dt

# Query data
SELECT * FROM users;
SELECT * FROM tasks;
```

---

## 📁 Project Structure

```
.
├── README.md                          # This file
├── kind_setup.sh                      # Automated deployment script
├── kind_cleanup.sh                    # Cleanup script
│
├── app/                               # FastAPI application
│   ├── Dockerfile                     # Multi-stage build
│   ├── requirements.txt               # Python dependencies
│   └── src/
│       ├── main.py                    # FastAPI app (1160+ lines)
│       ├── database.py                # SQLAlchemy models
│       └── static/                    # Frontend files
│           ├── index.html             # Main dashboard
│           ├── scenarios.html         # K8s scenarios list
│           ├── scenario-detail.html   # K8s scenario detail
│           ├── argocd-scenarios.html
│           ├── argocd-scenario-detail.html
│           ├── ansible-scenarios.html
│           ├── ansible-scenario-detail.html
│           ├── helm-scenarios.html
│           ├── helm-scenario-detail.html
│           ├── jenkins-scenarios.html
│           ├── jenkins-scenario-detail.html
│           ├── gitlab-ci-scenarios.html
│           ├── gitlab-ci-scenario-detail.html
│           ├── terraform-scenarios.html
│           ├── terraform-scenario-detail.html
│           ├── app.js                 # Frontend JavaScript (69KB)
│           └── style.css              # Stylesheet (34KB)
│
├── k8s/                               # Kubernetes manifests
│   ├── base/
│   │   ├── namespace.yaml
│   │   ├── deployment.yaml            # FastAPI deployment
│   │   ├── service.yaml               # ClusterIP service
│   │   ├── service-nodeport.yaml      # NodePort service (30080)
│   │   ├── configmap.yaml
│   │   └── secret.yaml
│   ├── database/
│   │   ├── postgres-deployment.yaml   # PostgreSQL StatefulSet
│   │   ├── postgres-service.yaml
│   │   └── postgres-pvc.yaml          # Persistent storage
│   ├── hpa/
│   │   └── hpa.yaml                   # Horizontal Pod Autoscaler
│   └── ingress/
│       └── ingress.yaml               # NGINX Ingress
│
├── k8s-scenarios/                     # Kubernetes learning scenarios
│   ├── 00-namespace.yaml
│   ├── 01-hpa-autoscaling/
│   │   ├── README.md
│   │   ├── commands.json
│   │   ├── deployment.yaml
│   │   ├── hpa.yaml
│   │   └── validate.sh
│   ├── 02-node-failure/
│   ├── 03-vpa-config/
│   ├── 04-configmap-secrets/
│   ├── 05-rolling-updates/
│   ├── 06-network-policies/
│   ├── 07-pod-disruption-budget/
│   ├── 08-self-healing/
│   ├── 09-liveness-readiness/
│   ├── 10-statefulset-operations/
│   ├── 11-daemonset-deployment/
│   ├── 12-job-cronjob/
│   ├── 13-blue-green-deployment/
│   ├── 14-ingress-configuration/
│   ├── 15-rbac-setup/
│   └── 16-node-affinity/
│
├── argocd-scenarios/                  # ArgoCD GitOps scenarios
│   ├── 01-basic-app-deploy/
│   │   ├── README.md
│   │   ├── commands.json
│   │   ├── application.yaml
│   │   └── manifests/
│   ├── 02-auto-sync-self-heal/
│   ├── 03-sync-waves-hooks/
│   ├── 04-app-of-apps/
│   ├── 05-kustomize-envs/
│   ├── 06-helm-deploy/
│   ├── 07-gitops-rollback/
│   ├── 08-multi-source-app/
│   ├── 09-health-checks/
│   ├── 10-projects-rbac/
│   ├── 11-canary-rollout/
│   └── 12-disaster-recovery/
│
├── ansible-scenarios/                 # Ansible automation scenarios
│   ├── 01-ansible-basics-inventory/
│   │   ├── README.md
│   │   ├── commands.json
│   │   ├── inventory/
│   │   └── playbooks/
│   ├── 02-package-management/
│   ├── 03-user-management/
│   ├── 04-file-deployment-templates/
│   ├── 05-multi-tier-app-deployment/
│   ├── 06-ansible-vault-secrets/
│   ├── 07-rolling-updates-zero-downtime/
│   ├── 08-system-hardening-compliance/
│   ├── 09-monitoring-stack-deployment/
│   ├── 10-disaster-recovery-automation/
│   ├── 11-dynamic-infrastructure-orchestration/
│   └── 12-ci-cd-pipeline-automation/
│
└── scenario-scripts/                  # Helper scripts
    ├── load-test.sh
    └── setup-hpa.sh
```

### Key Files Explained

**[app/src/main.py](app/src/main.py:1)** (1160+ lines)
- FastAPI application with comprehensive REST API
- Auto-discovers scenarios by scanning directories
- Serves frontend HTML/JS/CSS files
- Database integration for progress tracking
- Prometheus metrics endpoint
- Health and readiness probes
- Kubernetes API integration for cluster status

**[app/src/database.py](app/src/database.py)**
- SQLAlchemy models (User, Task)
- PostgreSQL connection management
- Database initialization and migrations

**[kind_setup.sh](kind_setup.sh:1)** (500+ lines)
- Complete automated deployment
- Prerequisite checking
- Cluster creation with custom configuration
- NGINX Ingress installation
- Database deployment
- Application build and deployment
- Health verification
- Colorized output

---

## ➕ Adding New Scenarios

Each scenario is self-contained in its own directory. Here's how to add new ones:

### Scenario Directory Structure

```
scenario-name/
├── README.md              # Overview, learning objectives, prerequisites
├── commands.json          # Step-by-step commands with metadata
├── *.yaml                 # Kubernetes manifests
└── validate.sh (optional) # Validation script
```

### 1. Create the Scenario Directory

```bash
# Choose the appropriate category
cd k8s-scenarios/     # or argocd-scenarios/ or ansible-scenarios/

# Create directory with zero-padded number prefix
mkdir 17-my-new-scenario
cd 17-my-new-scenario
```

### 2. Create README.md

```markdown
# Scenario: My New Scenario

## Overview
Brief description of what this scenario teaches.

## Learning Objectives
- Objective 1
- Objective 2
- Objective 3

## Prerequisites
- Knowledge of X
- Completed scenarios: Y, Z

## Difficulty
Medium

## Estimated Duration
20 minutes

## Resources Created
- Deployment: my-app
- Service: my-service
- ConfigMap: my-config

## Cleanup
```bash
kubectl delete -f .
```
```

### 3. Create commands.json

```json
{
  "scenario_id": "17-my-new-scenario",
  "title": "My New Scenario",
  "difficulty": "medium",
  "duration": "20 min",
  "category": "kubernetes",
  "commands": [
    {
      "step": 1,
      "name": "Create Namespace",
      "command": "kubectl create namespace my-scenario",
      "description": "Create isolated namespace for this scenario",
      "explanation": "Namespaces provide resource isolation in Kubernetes",
      "what_it_does": "Creates a new namespace called 'my-scenario'",
      "expected_output": "namespace/my-scenario created",
      "next_step": "Deploy the application",
      "cleanup": false
    },
    {
      "step": 2,
      "name": "Deploy Application",
      "command": "kubectl apply -f deployment.yaml -n my-scenario",
      "description": "Deploy the demo application",
      "explanation": "This creates a Deployment with 3 replicas",
      "what_it_does": "Creates pods running the application",
      "expected_output": "deployment.apps/my-app created",
      "next_step": "Verify deployment status",
      "cleanup": false
    },
    {
      "step": 3,
      "name": "Cleanup",
      "command": "kubectl delete namespace my-scenario",
      "description": "Remove all resources from this scenario",
      "explanation": "Deleting the namespace removes everything in it",
      "what_it_does": "Cleans up all scenario resources",
      "expected_output": "namespace 'my-scenario' deleted",
      "cleanup": true
    }
  ]
}
```

### 4. Add Kubernetes Manifests

Create your YAML files (deployment.yaml, service.yaml, etc.):

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: scenarios
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
      - name: app
        image: nginx:latest
        ports:
        - containerPort: 80
```

### 5. Add Validation Script (Optional)

```bash
#!/bin/bash
# validate.sh

echo "Validating scenario resources..."

# Check deployment
kubectl get deployment my-app -n scenarios &>/dev/null
if [ $? -eq 0 ]; then
  echo "✅ Deployment exists"
else
  echo "❌ Deployment not found"
  exit 1
fi

# Check replica count
REPLICAS=$(kubectl get deployment my-app -n scenarios -o jsonpath='{.status.readyReplicas}')
if [ "$REPLICAS" -eq 3 ]; then
  echo "✅ All 3 replicas are ready"
else
  echo "❌ Expected 3 replicas, found $REPLICAS"
  exit 1
fi

echo "🎉 Validation successful!"
```

### 6. Test Your Scenario

```bash
# Test locally
kubectl apply -f .
./validate.sh
kubectl delete -f .

# Rebuild application to include the scenario
docker build -t k8s-demo-app:latest ./app
kind load docker-image k8s-demo-app:latest --name k8s-demo
kubectl rollout restart deployment/k8s-demo-app -n k8s-multi-demo

# Verify in web UI
open http://localhost:30080/scenarios.html
```

### Auto-Discovery

The backend automatically discovers new scenarios by:
1. Scanning scenario directories (k8s-scenarios/, argocd-scenarios/, etc.)
2. Reading README.md for metadata
3. Parsing commands.json for step-by-step instructions
4. Serving via REST API endpoints
5. Displaying in the web UI

**No backend code changes needed!**

---

## 📊 Monitoring & Debugging

### Essential Commands

```bash
# View all resources in main namespace
kubectl get all -n k8s-multi-demo

# View scenario resources
kubectl get all -n scenarios
kubectl get all -n argocd

# Check pod logs (FastAPI application)
kubectl logs -f -l app=k8s-demo-app -n k8s-multi-demo

# Check database logs
kubectl logs -f deployment/postgres -n k8s-multi-demo

# Watch pod status
kubectl get pods -n k8s-multi-demo -w

# View events
kubectl get events -n k8s-multi-demo --sort-by='.lastTimestamp'

# Check resource usage
kubectl top pods -n k8s-multi-demo
kubectl top nodes

# Describe resources
kubectl describe deployment k8s-demo-app -n k8s-multi-demo
kubectl describe pod <pod-name> -n k8s-multi-demo
```

### Application Endpoints

```bash
# Health check
curl http://localhost:30080/health

# Readiness check
curl http://localhost:30080/ready

# Prometheus metrics
curl http://localhost:30080/metrics

# API documentation (OpenAPI/Swagger)
open http://localhost:30080/docs

# Database stats
curl http://localhost:30080/api/db/stats
```

### Database Access

```bash
# Connect to PostgreSQL
kubectl exec -it deployment/postgres -n k8s-multi-demo -- psql -U postgres -d k8s_demo

# Inside psql:
\dt                    # List tables
\d users              # Describe users table
SELECT * FROM users;  # Query users
\q                    # Exit
```

### Debugging Failed Scenarios

```bash
# Check if scenario namespace exists
kubectl get namespace scenarios

# View resources in scenario namespace
kubectl get all -n scenarios

# Check pod status and logs
kubectl get pods -n scenarios
kubectl logs <pod-name> -n scenarios

# Describe pod for events
kubectl describe pod <pod-name> -n scenarios

# Delete and recreate resources
kubectl delete -f k8s-scenarios/XX-scenario-name/
kubectl apply -f k8s-scenarios/XX-scenario-name/
```

---

## 🐛 Troubleshooting

### Application Not Accessible

**Problem**: Can't access http://localhost:30080

```bash
# Check if cluster exists
kind get clusters

# Check if NodePort service exists
kubectl get svc k8s-demo-nodeport -n k8s-multi-demo

# Check pod status
kubectl get pods -n k8s-multi-demo

# Check pod logs
kubectl logs -l app=k8s-demo-app -n k8s-multi-demo

# Port-forward as alternative
kubectl port-forward svc/k8s-demo-service 8080:80 -n k8s-multi-demo
# Then access http://localhost:8080
```

### Database Connection Errors

**Problem**: Application shows database errors

```bash
# Check PostgreSQL pod
kubectl get pods -n k8s-multi-demo | grep postgres

# Check PostgreSQL logs
kubectl logs deployment/postgres -n k8s-multi-demo

# Restart PostgreSQL
kubectl rollout restart deployment/postgres -n k8s-multi-demo

# Check database service
kubectl get svc postgres -n k8s-multi-demo
```

### Scenarios Not Loading

**Problem**: Scenario list is empty in web UI

```bash
# Verify scenario directories exist
ls k8s-scenarios/
ls argocd-scenarios/

# Check application logs
kubectl logs -l app=k8s-demo-app -n k8s-multi-demo | grep -i scenario

# Verify image includes scenarios
kubectl exec deployment/k8s-demo-app -n k8s-multi-demo -- ls /app/k8s-scenarios

# Rebuild if needed
docker build -t k8s-demo-app:latest ./app
kind load docker-image k8s-demo-app:latest --name k8s-demo
kubectl rollout restart deployment/k8s-demo-app -n k8s-multi-demo
```

### Pods Not Starting

**Problem**: Pods stuck in Pending, CrashLoopBackOff, or ImagePullBackOff

```bash
# Check pod status
kubectl get pods -n k8s-multi-demo

# Describe pod for events
kubectl describe pod <pod-name> -n k8s-multi-demo

# Common fixes:

# 1. ImagePullBackOff - Image not loaded
docker images | grep k8s-demo-app
kind load docker-image k8s-demo-app:latest --name k8s-demo

# 2. CrashLoopBackOff - Check logs
kubectl logs <pod-name> -n k8s-multi-demo
kubectl logs <pod-name> -n k8s-multi-demo --previous

# 3. Pending - Check resources
kubectl top nodes
kubectl describe node k8s-demo-control-plane
```

### Cluster Issues

**Problem**: Cluster not responding or corrupted

```bash
# Check cluster status
kubectl cluster-info
kubectl get nodes

# Restart cluster (Warning: destructive)
kind delete cluster --name k8s-demo
./kind_setup.sh

# Check Docker daemon
docker ps
docker info
```

### Metrics Server Issues

**Problem**: HPA scenarios show "unknown" metrics

```bash
# Check metrics-server
kubectl get pods -n kube-system | grep metrics-server

# Test metrics
kubectl top nodes
kubectl top pods -n scenarios

# Reinstall metrics-server
kubectl delete -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch -n kube-system deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
```

---

## 🧹 Cleanup

### Quick Cleanup (Delete Everything)

```bash
# Run cleanup script
./kind_cleanup.sh

# Or manually:
kind delete cluster --name k8s-demo

# Verify deletion
kind get clusters
docker ps
```

### Partial Cleanup (Keep Cluster, Remove Application)

```bash
# Delete main application
kubectl delete namespace k8s-multi-demo

# Delete scenario resources
kubectl delete namespace scenarios
kubectl delete namespace argocd

# Keep cluster for other experiments
```

### Cleanup Individual Scenarios

```bash
# Most scenarios include cleanup instructions
kubectl delete -f k8s-scenarios/01-hpa-autoscaling/

# Or delete by namespace
kubectl delete namespace <scenario-namespace>
```

### Remove Docker Images

```bash
# List images
docker images | grep k8s-demo

# Remove specific image
docker rmi k8s-demo-app:latest

# Remove all unused images
docker image prune -a
```

---

## 🎓 Learning Outcomes

By working through this platform, you will master:

### Kubernetes Core Concepts
- ✅ Pods, Deployments, Services, Ingress
- ✅ StatefulSets, DaemonSets, Jobs, CronJobs
- ✅ ConfigMaps, Secrets, Persistent Volumes
- ✅ Namespaces, RBAC, Network Policies
- ✅ Health Probes, Resource Management
- ✅ Horizontal & Vertical Pod Autoscaling

### GitOps with ArgoCD
- ✅ Application deployment and synchronization
- ✅ Auto-sync and self-healing
- ✅ Sync waves and hooks
- ✅ Multi-source applications
- ✅ Kustomize and Helm integration
- ✅ Canary deployments and rollbacks

### Ansible Automation
- ✅ Inventory management and playbooks
- ✅ Roles, templates, and variables
- ✅ Ansible Vault for secrets
- ✅ Multi-tier application deployment
- ✅ System hardening and compliance
- ✅ CI/CD pipeline integration

### Production Best Practices
- ✅ Infrastructure as Code
- ✅ Zero-downtime deployments
- ✅ High availability patterns
- ✅ Security hardening
- ✅ Monitoring and observability
- ✅ Disaster recovery

### DevOps Skills
- ✅ Container orchestration
- ✅ Service mesh concepts
- ✅ CI/CD pipeline design
- ✅ GitOps workflows
- ✅ Configuration management
- ✅ Troubleshooting and debugging

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Adding Scenarios

1. Fork the repository
2. Create a new scenario following the [Adding New Scenarios](#-adding-new-scenarios) guide
3. Test your scenario thoroughly
4. Submit a pull request with:
   - Scenario description
   - Learning objectives
   - Testing evidence (screenshots)

### Reporting Issues

Open an issue on GitHub with:
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, kubectl version, etc.)
- Relevant logs

### Suggesting Features

Open an issue tagged "enhancement" with:
- Use case description
- Proposed solution
- Alternative approaches considered

---

## 📞 Contact & Support

**Author**: Shay Guedj
**GitHub**: [@shaydevops2024](https://github.com/shaydevops2024)
**Repository**: [kubernetes-production-simulator](https://github.com/shaydevops2024/kubernetes-production-simulator)

**Get Help:**
- 🐛 [Report a Bug](https://github.com/shaydevops2024/kubernetes-production-simulator/issues)
- 💡 [Request a Feature](https://github.com/shaydevops2024/kubernetes-production-simulator/issues)
- 📚 [Read the Docs](https://github.com/shaydevops2024/kubernetes-production-simulator/wiki)

---

## 📝 License

MIT License - Free to use for learning, portfolios, and commercial projects!

See [LICENSE](LICENSE) file for details.

---

## 🌟 Acknowledgments

This project builds on the excellent work of:
- **Kubernetes Community** - For comprehensive documentation
- **ArgoCD Team** - For GitOps best practices
- **FastAPI** - For the modern web framework
- **PostgreSQL** - For reliable data persistence
- **Kind** - For local Kubernetes clusters
- **NGINX Ingress** - For production-grade routing

---

## 🎯 Roadmap

### Coming Soon
- [ ] Progress tracking and scenario completion badges
- [ ] Interactive terminal in web UI
- [ ] Scenario difficulty ratings and recommendations
- [ ] Video tutorials for complex scenarios
- [ ] Community-contributed scenarios
- [ ] Certification practice exams (CKA, CKAD, CKS)
- [ ] Terraform, Pulumi, and CloudFormation scenarios
- [ ] Service mesh scenarios (Istio, Linkerd)
- [ ] Observability stack (Prometheus, Grafana, Loki, Tempo)

### Future Enhancements
- [ ] Multi-cluster scenarios
- [ ] Cloud provider integration (AWS EKS, GCP GKE, Azure AKS)
- [ ] GitLab integration for GitOps
- [ ] Slack/Discord notifications
- [ ] Leaderboards and gamification
- [ ] API for programmatic access
- [ ] Mobile-responsive UI improvements
- [ ] Dark mode

---

## ⭐ Star This Repo!

If this platform helped you learn Kubernetes, land a DevOps role, or ace an interview, please give it a star on GitHub! ⭐

**🚀 Happy Learning! 🚀**

---

## 📊 Project Stats

- **50+ Scenarios** across 7 categories
- **1200+ lines** of Python (FastAPI backend)
- **140KB+ JavaScript** for interactive frontend
- **500+ lines** of bash automation
- **100+ Kubernetes manifests**
- **Fully documented** with README files and inline comments
- **Production-ready** architecture and patterns
- **Actively maintained** and growing

---

## 💡 Use Cases

### For Students
- Learn DevOps technologies hands-on
- Build a portfolio project
- Prepare for certifications (CKA, CKAD)
- Practice for technical interviews

### For Professionals
- Sharpen Kubernetes skills
- Learn GitOps workflows
- Experiment with new tools safely
- Create training materials for teams

### For Teams
- Onboarding new DevOps engineers
- Internal training workshops
- Proof-of-concept for new patterns
- Reference architecture for projects

### For Educators
- Teaching material for courses
- Lab environment for students
- Assessment and grading scenarios
- Demonstration platform for concepts

---

**Built with ❤️ by [Shay Guedj](https://github.com/shaydevops2024)**
