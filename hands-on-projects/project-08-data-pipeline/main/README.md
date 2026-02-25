# Main — DevOps Journey Guide

This is where **your work begins**. The application is pre-built. You deploy, wire, scale, secure, and observe it — phase by phase.

---

## Overview

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6
Manual     K8s +     CI/CD +   Observ-   Security  Chaos
Setup      Helm      GitOps    ability             Engineering
```

All solution files are in `../solution/` — use them only **after** you attempt each phase yourself.

---

## Prerequisites

Before starting, ensure you have:

- [ ] A running Kubernetes cluster (EKS, GKE, or Kind locally)
- [ ] `kubectl` configured and pointing at the cluster
- [ ] `helm` v3 installed
- [ ] `argocd` CLI installed
- [ ] GitLab account (for CI/CD phases)
- [ ] Container registry access (GitLab, Docker Hub, or ECR)
- [ ] Completed `../local/` — you've seen the pipeline running

---

## Phase 1 — Manual Operator Setup

**Goal:** Install the Kubernetes operators that manage Kafka and Spark. Understand the operator pattern before automating it.

### Step 1.1 — Create the namespace

```bash
kubectl create namespace data-pipeline
kubectl label namespace data-pipeline project=data-pipeline
```

### Step 1.2 — Install Strimzi (Kafka Operator)

Strimzi lets you declare a Kafka cluster as a Kubernetes CRD instead of managing StatefulSets manually.

```bash
# Install Strimzi operator
helm repo add strimzi https://strimzi.io/charts/
helm repo update

helm install strimzi-operator strimzi/strimzi-kafka-operator \
  --namespace data-pipeline \
  --set watchNamespaces="{data-pipeline}"

# Verify the operator is running
kubectl -n data-pipeline get pods -l name=strimzi-cluster-operator
```

### Step 1.3 — Deploy a Kafka cluster via Strimzi CRD

Create a file `kafka-cluster.yaml`:

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: pipeline-kafka
  namespace: data-pipeline
spec:
  kafka:
    version: 3.6.0
    replicas: 3
    listeners:
      - name: plain
        port: 9092
        type: internal
        tls: false
    config:
      offsets.topic.replication.factor: 3
      transaction.state.log.replication.factor: 3
      transaction.state.log.min.isr: 2
      default.replication.factor: 3
      min.insync.replicas: 2
    storage:
      type: jbod
      volumes:
        - id: 0
          type: persistent-claim
          size: 20Gi
          deleteClaim: false
  zookeeper:
    replicas: 3
    storage:
      type: persistent-claim
      size: 5Gi
      deleteClaim: false
  entityOperator:
    topicOperator: {}
    userOperator: {}
```

```bash
kubectl apply -f kafka-cluster.yaml
kubectl -n data-pipeline wait kafka/pipeline-kafka --for=condition=Ready --timeout=300s
```

**What to observe:** Watch Strimzi create StatefulSets, PVCs, ConfigMaps, and Services automatically. This is the operator pattern in action.

### Step 1.4 — Create the Kafka topic via CRD

```yaml
# kafka-topic.yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaTopic
metadata:
  name: sensor-events
  namespace: data-pipeline
  labels:
    strimzi.io/cluster: pipeline-kafka
spec:
  partitions: 6
  replicas: 3
  config:
    retention.ms: "86400000"   # 24 hours
    cleanup.policy: delete
```

```bash
kubectl apply -f kafka-topic.yaml
```

### Step 1.5 — Install Spark Operator

```bash
helm repo add spark-operator https://kubeflow.github.io/spark-operator
helm repo update

helm install spark-operator spark-operator/spark-operator \
  --namespace data-pipeline \
  --set sparkJobNamespace=data-pipeline \
  --set webhook.enable=true \
  --set metrics.enable=true
```

### Step 1.6 — Deploy TimescaleDB

```bash
helm repo add timescale https://charts.timescale.com
helm repo update

helm install timescaledb timescale/timescaledb-single \
  --namespace data-pipeline \
  --set replicaCount=1 \
  --set credentials.superuser.password=pipeline123 \
  --set credentials.admin.password=pipeline123 \
  --set credentials.standby.password=pipeline123 \
  --set persistentVolumes.data.size=20Gi
```

**Checkpoint questions:**
- What CRDs did Strimzi install? (`kubectl get crds | grep strimzi`)
- How many StatefulSets exist? Which ones? Why?
- What does the `entityOperator` in the Kafka CR do?

---

## Phase 2 — K8s Workloads (Producer + Processor + Dashboard)

**Goal:** Deploy all three application components to Kubernetes using Deployments, ConfigMaps, Secrets, and Services.

### Step 2.1 — Build and push Docker images

```bash
# Set your registry
export REGISTRY=registry.gitlab.com/YOUR_USERNAME/data-pipeline

# Build images
docker build -t ${REGISTRY}/pipeline-producer:v1.0.0 ../app/pipeline-producer/
docker build -t ${REGISTRY}/pipeline-processor:v1.0.0 ../app/pipeline-processor/
docker build -t ${REGISTRY}/pipeline-dashboard:v1.0.0 ../app/dashboard-ui/

# Push
docker push ${REGISTRY}/pipeline-producer:v1.0.0
docker push ${REGISTRY}/pipeline-processor:v1.0.0
docker push ${REGISTRY}/pipeline-dashboard:v1.0.0
```

### Step 2.2 — Create Secrets

```bash
# TimescaleDB credentials
kubectl -n data-pipeline create secret generic timescale-secret \
  --from-literal=url="postgresql://pipeline:pipeline123@timescaledb:5432/pipeline" \
  --from-literal=user="pipeline" \
  --from-literal=password="pipeline123"

# Registry pull secret (if private)
kubectl -n data-pipeline create secret docker-registry registry-secret \
  --docker-server=registry.gitlab.com \
  --docker-username=YOUR_USERNAME \
  --docker-password=YOUR_GITLAB_TOKEN
```

### Step 2.3 — Deploy the Producer

Write a Deployment manifest. Key questions to answer before writing:
- How should the producer know the Kafka bootstrap address?
- Should you use a ConfigMap or environment variables?
- What liveness/readiness probes should you use? (hint: `/health`)
- How many replicas? Can you run 2 producers safely?

After writing the manifest:
```bash
kubectl apply -f producer-deployment.yaml
kubectl -n data-pipeline rollout status deployment/pipeline-producer
```

### Step 2.4 — Deploy the Spark Job via SparkApplication CRD

This is the most complex manifest. The Spark Operator uses a `SparkApplication` CRD:

```yaml
apiVersion: sparkoperator.k8s.io/v1beta2
kind: SparkApplication
metadata:
  name: sensor-processor
  namespace: data-pipeline
spec:
  type: Python
  pythonVersion: "3"
  mode: cluster
  image: "${REGISTRY}/pipeline-processor:v1.0.0"
  imagePullPolicy: Always
  mainApplicationFile: "local:///app/main.py"
  sparkVersion: "3.5.1"
  restartPolicy:
    type: OnFailure
    onFailureRetries: 3
    onFailureRetryInterval: 10
    onSubmissionFailureRetries: 5
    onSubmissionFailureRetryInterval: 20
  driver:
    cores: 1
    memory: "1g"
    labels:
      version: v1.0.0
    serviceAccount: spark
    env:
      - name: KAFKA_BOOTSTRAP_SERVERS
        value: "pipeline-kafka-kafka-bootstrap.data-pipeline.svc:9092"
  executor:
    cores: 2
    instances: 2
    memory: "2g"
    labels:
      version: v1.0.0
```

```bash
kubectl apply -f spark-application.yaml
kubectl -n data-pipeline get sparkapplication sensor-processor
kubectl -n data-pipeline logs -l spark-role=driver
```

### Step 2.5 — Deploy the Dashboard

```bash
kubectl apply -f dashboard-deployment.yaml
kubectl apply -f dashboard-service.yaml
kubectl apply -f dashboard-ingress.yaml
```

Visit the dashboard URL and verify live data flows in.

**Checkpoint questions:**
- The Spark driver pod needs a ServiceAccount. Why? What permissions does it need?
- How is the Spark executor different from a regular Deployment pod?
- What happens if the Spark driver crashes? What about an executor?

---

## Phase 3 — CI/CD + GitOps

**Goal:** No more manual kubectl applies. GitLab CI builds, tests, scans, and pushes images. ArgoCD deploys automatically.

### Step 3.1 — Repository Structure

Organize your GitLab repo:

```
data-pipeline/
├── .gitlab-ci.yml          ← Pipeline definition
├── app/                    ← Application code (build source)
├── k8s/                    ← Kubernetes manifests (GitOps source)
│   ├── base/
│   └── overlays/
│       └── production/
└── helm/                   ← Helm chart
```

### Step 3.2 — GitLab CI Pipeline

Your `.gitlab-ci.yml` must:
1. **test** — Run unit tests for producer and processor
2. **build** — Build Docker images, tag with Git SHA
3. **scan** — Run Trivy vulnerability scan (fail on CRITICAL)
4. **push** — Push to GitLab Container Registry
5. **update-manifests** — Update image tag in k8s/ manifests, commit back to repo
6. **sync** — Trigger ArgoCD sync (or let ArgoCD poll)

Key rules:
- Never run `kubectl apply` in CI
- `main` branch → deploys to production
- MRs → build + scan only

### Step 3.3 — Install ArgoCD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Get initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# Port-forward UI
kubectl -n argocd port-forward svc/argocd-server 8443:443
```

### Step 3.4 — Create ArgoCD Application

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: data-pipeline
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://gitlab.com/YOUR_USERNAME/data-pipeline.git
    targetRevision: main
    path: k8s/overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: data-pipeline
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

**Test the pipeline:**
1. Push a commit that changes `EVENTS_PER_SECOND` to 20
2. Watch GitLab CI build and update the manifest
3. Watch ArgoCD detect the change and sync
4. Verify the producer pod restarts with the new env var

**Checkpoint questions:**
- What is "self-healing" in ArgoCD? Test it by manually deleting a pod.
- What does "prune" do? What happens if you delete a manifest from Git?
- Why do we update the manifest in Git rather than patching the running deployment directly?

---

## Phase 4 — Observability

**Goal:** Full visibility into pipeline health: metrics, logs, traces, and alerts.

### Step 4.1 — Prometheus + Grafana Stack

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set grafana.enabled=true \
  --set grafana.adminPassword=admin \
  --set prometheus.prometheusSpec.retention=7d
```

### Step 4.2 — Kafka Metrics (Strimzi JMX Exporter)

Strimzi has built-in Prometheus metrics support. Enable it:

```yaml
# Add to your Kafka CR
kafka:
  metricsConfig:
    type: jmxPrometheusExporter
    valueFrom:
      configMapKeyRef:
        name: kafka-metrics
        key: kafka-metrics-config.yml
```

Key metrics to monitor:
- `kafka_consumer_fetch_manager_metrics_records_lag` — consumer lag
- `kafka_server_brokertopicmetrics_messagesinpersec` — ingestion rate
- `kafka_log_log_size` — topic partition size

### Step 4.3 — Spark Metrics

The Spark Operator exposes metrics via the Spark History Server and Prometheus JMX exporter.

```bash
helm install spark-history-server spark-operator/spark-history-server \
  --namespace data-pipeline \
  --set sparkConf."spark.history.fs.logDirectory"=s3a://your-bucket/spark-logs
```

Key metrics:
- `spark_executor_runTime` — executor utilization
- `spark_streaming_lastCompletedBatch_processingDelay` — batch latency
- `spark_streaming_lastCompletedBatch_schedulingDelay` — scheduling overhead

### Step 4.4 — Loki for Logs

```bash
helm install loki grafana/loki-stack \
  --namespace monitoring \
  --set grafana.enabled=false \
  --set promtail.enabled=true
```

Query examples in Grafana (LogQL):
```
{namespace="data-pipeline", container="pipeline-producer"} |= "error"
{namespace="data-pipeline"} | json | avg_temperature > 90
```

### Step 4.5 — AlertManager Rules

Create alerts for:

```yaml
groups:
  - name: pipeline-alerts
    rules:
      - alert: KafkaConsumerLagHigh
        expr: kafka_consumer_fetch_manager_metrics_records_lag > 10000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Consumer lag exceeded 10k messages"

      - alert: SparkBatchDelayed
        expr: spark_streaming_lastCompletedBatch_processingDelay > 30000
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "Spark batch taking >30s to process"

      - alert: ProducerDown
        expr: up{job="pipeline-producer"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Producer is down — no events being published"
```

**Build these Grafana dashboards:**
1. Pipeline Overview — events/sec, lag, active sensors
2. Kafka Health — broker throughput, partition status
3. Spark Performance — batch duration, executor CPU/memory

---

## Phase 5 — Security

**Goal:** Secrets out of environment variables and into Vault. Images scanned before deployment.

### Step 5.1 — Install HashiCorp Vault

```bash
helm repo add hashicorp https://helm.releases.hashicorp.com
helm repo update

helm install vault hashicorp/vault \
  --namespace vault \
  --create-namespace \
  --set server.dev.enabled=true
```

### Step 5.2 — Store Pipeline Secrets in Vault

```bash
kubectl -n vault exec -it vault-0 -- vault kv put secret/data-pipeline/timescaledb \
  user=pipeline \
  password=pipeline123 \
  url="postgresql://pipeline:pipeline123@timescaledb:5432/pipeline"
```

### Step 5.3 — Vault Agent Injector

Instead of `env.valueFrom.secretKeyRef`, use Vault annotations:

```yaml
annotations:
  vault.hashicorp.com/agent-inject: "true"
  vault.hashicorp.com/agent-inject-secret-db: "secret/data-pipeline/timescaledb"
  vault.hashicorp.com/role: "data-pipeline"
  vault.hashicorp.com/agent-inject-template-db: |
    {{- with secret "secret/data-pipeline/timescaledb" -}}
    export TIMESCALE_USER="{{ .Data.data.user }}"
    export TIMESCALE_PASSWORD="{{ .Data.data.password }}"
    {{- end -}}
```

### Step 5.4 — Trivy in GitLab CI

Add to your `.gitlab-ci.yml`:

```yaml
scan:
  stage: scan
  image: aquasec/trivy:latest
  script:
    - trivy image --exit-code 1 --severity CRITICAL ${REGISTRY}/pipeline-producer:${CI_COMMIT_SHA}
    - trivy image --exit-code 1 --severity CRITICAL ${REGISTRY}/pipeline-processor:${CI_COMMIT_SHA}
  allow_failure: false
```

**A CRITICAL vulnerability should fail the pipeline and block deployment.**

### Step 5.5 — Network Policies

Restrict traffic between components:

```yaml
# Only allow Spark processor to reach TimescaleDB
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: timescale-access
  namespace: data-pipeline
spec:
  podSelector:
    matchLabels:
      app: timescaledb
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              spark-role: driver
        - podSelector:
            matchLabels:
              spark-role: executor
        - podSelector:
            matchLabels:
              app: pipeline-dashboard
      ports:
        - port: 5432
```

---

## Phase 6 — Chaos Engineering

**Goal:** Prove the pipeline self-heals under failure conditions.

### Install Chaos Mesh

```bash
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update

helm install chaos-mesh chaos-mesh/chaos-mesh \
  --namespace chaos-testing \
  --create-namespace \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock
```

### Chaos Experiment 1 — Kill a Kafka broker

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: kill-kafka-broker
  namespace: chaos-testing
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces: [data-pipeline]
    labelSelectors:
      strimzi.io/cluster: pipeline-kafka
  scheduler:
    cron: "@every 5m"
```

**Expected:** Kafka partition leader re-election occurs. Consumer lag spikes briefly then recovers. Alert fires and clears.

### Chaos Experiment 2 — Spark executor failure

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: kill-spark-executor
  namespace: chaos-testing
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces: [data-pipeline]
    labelSelectors:
      spark-role: executor
```

**Expected:** Spark reschedules the executor on another node. Batch processing resumes within one trigger interval.

### Chaos Experiment 3 — Network partition

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: producer-network-loss
  namespace: chaos-testing
spec:
  action: loss
  mode: one
  selector:
    namespaces: [data-pipeline]
    labelSelectors:
      app: pipeline-producer
  loss:
    loss: "50"
    correlation: "25"
  duration: "2m"
```

**Expected:** Producer retries with backoff. Consumer lag stays stable (no new messages = no lag growth). Dashboard shows drop in events/sec.

### Your Chaos Checklist

- [ ] Kill 1 Kafka broker → pipeline recovers in < 30s
- [ ] Kill Spark driver → SparkApplication auto-restarts
- [ ] Kill Spark executor → tasks reschedule automatically
- [ ] Kill TimescaleDB pod → Spark batches retry, dashboard shows degraded state
- [ ] Network loss on producer → consumer lag stays flat, producer reconnects
- [ ] Delete all producer pods → dashboard shows 0 events/sec, alert fires

---

## Solution Reference

All solution files are in `../solution/`:

```
solution/
├── k8s/                ← All Kubernetes manifests
├── helm/               ← Helm chart for the full pipeline
├── argocd/             ← ArgoCD Application definitions
├── terraform/          ← Cloud infrastructure (EKS, RDS, VPC)
├── ansible/            ← VM configuration for operators
└── gitlab-ci/          ← GitLab CI pipeline templates
```

**Only look at solution files after attempting each phase yourself.**
