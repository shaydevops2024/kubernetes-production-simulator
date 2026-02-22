# Main — Production Kubernetes Deployment

This is the production phase. You'll deploy the entire ChatFlow platform to Kubernetes, then progressively add horizontal scaling, observability, and production hardening.

This folder is intentionally empty — **you build it**. The guide below tells you exactly what to create.

---

## What You'll Build

```
main/
├── namespace.yaml
├── secrets/
│   ├── db-secrets.yaml
│   └── minio-secrets.yaml
├── configmaps/
│   └── service-config.yaml
├── infrastructure/
│   ├── redis.yaml              ← StatefulSet + Service
│   ├── postgres-chat.yaml      ← StatefulSet + Service
│   ├── postgres-notifications.yaml
│   ├── postgres-files.yaml
│   └── minio.yaml              ← StatefulSet + Service + PVC
├── deployments/
│   ├── chat-service.yaml
│   ├── presence-service.yaml
│   ├── notification-service.yaml
│   ├── file-service.yaml
│   └── frontend.yaml
├── services/
│   ├── chat-service.yaml
│   ├── presence-service.yaml
│   ├── notification-service.yaml
│   ├── file-service.yaml
│   └── frontend.yaml
├── hpa/
│   └── chat-service-hpa.yaml   ← Horizontal Pod Autoscaler
└── ingress/
    └── ingress.yaml            ← WebSocket-aware Ingress (the tricky part)
```

---

## Phase 3A — Core Kubernetes Deployment

### Step 1 — Create the Namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: chatflow
  labels:
    app: chatflow
```

Apply: `kubectl apply -f namespace.yaml`

### Step 2 — Secrets

**Never commit real secrets to git.** For this exercise, use `--dry-run=client -o yaml`:

```bash
kubectl create secret generic db-credentials \
  --namespace chatflow \
  --from-literal=POSTGRES_USER=chatuser \
  --from-literal=POSTGRES_PASSWORD=chatpass \
  --dry-run=client -o yaml > secrets/db-secrets.yaml

kubectl create secret generic minio-credentials \
  --namespace chatflow \
  --from-literal=MINIO_ACCESS_KEY=minioadmin \
  --from-literal=MINIO_SECRET_KEY=minioadmin \
  --dry-run=client -o yaml > secrets/minio-secrets.yaml
```

**Production note:** Use Sealed Secrets, Vault, or External Secrets Operator to avoid plain Secrets in git.

### Step 3 — Deploy Redis

Redis is required by chat-service and presence-service. Use a StatefulSet to ensure stable storage and network identity:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
  namespace: chatflow
spec:
  serviceName: redis
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        command: ["redis-server", "--save", "", "--appendonly", "no"]
        ports:
        - containerPort: 6379
        readinessProbe:
          exec:
            command: ["redis-cli", "ping"]
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "200m"
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: chatflow
spec:
  clusterIP: None   # Headless service for StatefulSet
  selector:
    app: redis
  ports:
  - port: 6379
```

**Why StatefulSet for Redis?**
StatefulSets give pods stable DNS names (`redis-0.redis.chatflow.svc.cluster.local`).
This is important for Redis Sentinel/Cluster setups where nodes must find each other by name.

### Step 4 — Deploy PostgreSQL Databases

Deploy three separate PostgreSQL StatefulSets (one per service that needs its own DB):

```yaml
# Example for postgres-chat (repeat for postgres-notifications and postgres-files)
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres-chat
  namespace: chatflow
spec:
  serviceName: postgres-chat
  replicas: 1
  selector:
    matchLabels:
      app: postgres-chat
  template:
    metadata:
      labels:
        app: postgres-chat
    spec:
      containers:
      - name: postgres
        image: postgres:16-alpine
        envFrom:
        - secretRef:
            name: db-credentials
        env:
        - name: POSTGRES_DB
          value: chat_db
        ports:
        - containerPort: 5432
        readinessProbe:
          exec:
            command: ["pg_isready", "-U", "chatuser", "-d", "chat_db"]
          initialDelaySeconds: 10
          periodSeconds: 5
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 5Gi
```

### Step 5 — Deploy MinIO

MinIO needs persistent storage and a stable endpoint:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: minio
  namespace: chatflow
spec:
  serviceName: minio
  replicas: 1
  selector:
    matchLabels:
      app: minio
  template:
    metadata:
      labels:
        app: minio
    spec:
      containers:
      - name: minio
        image: minio/minio:latest
        args: ["server", "/data", "--console-address", ":9001"]
        envFrom:
        - secretRef:
            name: minio-credentials
        env:
        - name: MINIO_ROOT_USER
          valueFrom:
            secretKeyRef:
              name: minio-credentials
              key: MINIO_ACCESS_KEY
        - name: MINIO_ROOT_PASSWORD
          valueFrom:
            secretKeyRef:
              name: minio-credentials
              key: MINIO_SECRET_KEY
        ports:
        - containerPort: 9000   # API
        - containerPort: 9001   # Console
        readinessProbe:
          httpGet:
            path: /minio/health/ready
            port: 9000
          initialDelaySeconds: 15
          periodSeconds: 10
        volumeMounts:
        - name: data
          mountPath: /data
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
```

**Production note:** In AWS, replace MinIO with:
- Update env vars: `MINIO_ENDPOINT=s3.amazonaws.com`, credentials from IAM role (using IRSA or a Secret)
- Delete the MinIO StatefulSet entirely — AWS handles storage

### Step 6 — Deploy Application Services

For each service (chat, presence, notification, file):

```yaml
# Example: chat-service
apiVersion: apps/v1
kind: Deployment
metadata:
  name: chat-service
  namespace: chatflow
spec:
  replicas: 2
  selector:
    matchLabels:
      app: chat-service
  template:
    metadata:
      labels:
        app: chat-service
    spec:
      containers:
      - name: chat-service
        image: your-registry/chat-service:v1   # build and push this
        ports:
        - containerPort: 8020
        env:
        - name: DATABASE_URL
          value: postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@postgres-chat:5432/chat_db
        - name: REDIS_URL
          value: redis://redis:6379
        envFrom:
        - secretRef:
            name: db-credentials
        readinessProbe:
          httpGet:
            path: /health
            port: 8020
          initialDelaySeconds: 15
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /health
            port: 8020
          initialDelaySeconds: 30
          periodSeconds: 10
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "500m"
```

### Step 7 — The Critical Part: WebSocket-Aware Ingress

WebSockets require special handling in the Ingress. Without these annotations, nginx drops
connections after 60 seconds and the chat stops working mid-session.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: chatflow-ingress
  namespace: chatflow
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "60"
    # WebSocket upgrade headers
    nginx.ingress.kubernetes.io/configuration-snippet: |
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection "upgrade";
    # Allow large file uploads
    nginx.ingress.kubernetes.io/proxy-body-size: "15m"
spec:
  ingressClassName: nginx
  rules:
  - http:
      paths:
      # WebSocket endpoint — must come FIRST (more specific path)
      - path: /ws
        pathType: Prefix
        backend:
          service:
            name: chat-service
            port:
              number: 8020
      # REST APIs
      - path: /api/chat
        pathType: Prefix
        backend:
          service:
            name: chat-service
            port:
              number: 8020
      - path: /api/presence
        pathType: Prefix
        backend:
          service:
            name: presence-service
            port:
              number: 8021
      - path: /api/notifications
        pathType: Prefix
        backend:
          service:
            name: notification-service
            port:
              number: 8022
      - path: /api/files
        pathType: Prefix
        backend:
          service:
            name: file-service
            port:
              number: 8023
      # Frontend — catch-all
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 80
```

**Why `/ws` before `/api`?**
nginx Ingress matches paths in order of specificity. Since `/ws` is a prefix of nothing specific,
ensure it appears before the general `/` catch-all. The `pathType: Prefix` with `/ws`
will match `/ws/general/alice?username=alice`.

---

## Phase 3B — Horizontal Pod Autoscaler

The chat-service is the most load-sensitive component. Add an HPA:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: chat-service-hpa
  namespace: chatflow
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: chat-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 70
```

**Why does horizontal scaling work for WebSockets here?**

Because of Redis pub/sub. When a user connects to replica A and sends a message:
1. Replica A publishes to Redis channel `room:general`
2. ALL replicas (A, B, C...) receive it from Redis
3. Each replica delivers the message to its own WebSocket connections
4. The user on replica B sees the message — ✅

Without Redis, you'd need "sticky sessions" (session affinity) to route each user to the same replica. With Redis, any replica works — true horizontal scaling.

---

## Phase 3C — Building and Pushing Images

```bash
# From the project root (project-03-realtime-chat/)
docker build -t your-registry/chat-service:v1         app/chat-service/
docker build -t your-registry/presence-service:v1     app/presence-service/
docker build -t your-registry/notification-service:v1 app/notification-service/
docker build -t your-registry/file-service:v1         app/file-service/
docker build -t your-registry/chat-frontend:v1        app/frontend/

docker push your-registry/chat-service:v1
docker push your-registry/presence-service:v1
docker push your-registry/notification-service:v1
docker push your-registry/file-service:v1
docker push your-registry/chat-frontend:v1
```

Or load directly into a Kind cluster:
```bash
kind load docker-image your-registry/chat-service:v1 --name your-cluster-name
```

---

## Verification Checklist

- [ ] All pods running in `chatflow` namespace (`kubectl get pods -n chatflow`)
- [ ] Redis StatefulSet has a bound PVC
- [ ] All 3 PostgreSQL StatefulSets running with PVCs bound
- [ ] MinIO StatefulSet running, bucket `chatfiles` accessible
- [ ] Frontend serves the chat UI via Ingress
- [ ] WebSocket connects successfully (check browser DevTools → Network → WS)
- [ ] Messages sent from browser tab A appear in browser tab B (same cluster)
- [ ] Scale chat-service to 3 replicas — messages still work across all replicas
- [ ] HPA activates when you generate CPU load
- [ ] File upload works end-to-end (upload → MinIO → download URL in chat)

---

## Tips

- Deploy infrastructure (Redis, Postgres, MinIO) first, then services, then Ingress
- Use `kubectl describe pod <pod>` to diagnose startup failures
- If WebSockets don't connect, check Ingress annotations first — missing `Upgrade` headers is the most common issue
- Use `kubectl exec -it redis-0 -n chatflow -- redis-cli SUBSCRIBE "room:general"` to watch pub/sub live from the cluster
- Test horizontal scaling with multiple browser tabs and `kubectl scale deployment/chat-service --replicas=3 -n chatflow`
