# Project 03 — Real-Time Chat Platform: Explained

---

## 1. The App

You are deploying a **production-grade real-time chat platform** using WebSockets and Redis pub/sub. The key engineering challenge: when you run multiple instances of the chat server, all instances need to share messages — Redis pub/sub solves this, making the system horizontally scalable.

```
Browser (WebSocket + REST)
  └─▶ NGINX (API Gateway)
        ├─▶ /ws/*            →  chat-service (WebSocket)  → Redis pub/sub + PostgreSQL
        ├─▶ /api/chat/*      →  chat-service (REST)       → PostgreSQL (messages)
        ├─▶ /api/presence/*  →  presence-service          → Redis (TTL keys)
        ├─▶ /api/files/*     →  file-service              → MinIO (S3-compatible)
        └─▶ /api/notify/*    →  notification-service      → PostgreSQL (notifications)
```

| Service | What it does |
|---------|-------------|
| **chat-service** | WebSocket engine. Handles connections, broadcasts messages via Redis pub/sub, persists history to PostgreSQL |
| **presence-service** | Tracks who's online and typing indicators. Uses Redis TTL keys — when a user disconnects, their TTL expires and they appear offline |
| **notification-service** | Stores @mentions and system notifications. PostgreSQL-backed, queried on page load |
| **file-service** | Handles image/file uploads to MinIO. Proxies downloads so the browser never talks to MinIO directly (security) |
| **frontend** | Single-page chat UI — rooms, typing indicators, file uploads, notification badge |

**Why Redis pub/sub matters:** If chat-server-1 receives a message, it publishes to Redis. All other chat-server instances subscribe and push the message to their connected clients. This is how chat scales.

---

## 2. How to Use the App

### Phase 1 — Run Locally (Docker Compose)

```bash
cd hands-on-projects/project-03-realtime-chat/local/

docker compose up --build
```

Once all containers are healthy:

| Endpoint | URL |
|----------|-----|
| Chat Web UI | http://localhost:8080 |
| Chat Service API | http://localhost:8001/docs |
| Presence Service API | http://localhost:8002/docs |
| File Service API | http://localhost:8003/docs |
| Notification Service API | http://localhost:8004/docs |
| MinIO Console | http://localhost:9001 (user: minioadmin / minioadmin) |

**Basic workflow:**
1. Open http://localhost:8080 in two browser tabs (simulates two users)
2. Enter different usernames in each tab
3. Join a room (e.g., "general") in both tabs
4. Send a message from tab 1 — it should appear instantly in tab 2
5. Observe the typing indicator as you type
6. Upload an image using the file attach button

### Phase 2 — Deploy to Kubernetes

```bash
cd hands-on-projects/project-03-realtime-chat/main/

kubectl apply -f namespace.yaml
kubectl apply -f configmaps/
kubectl apply -f secrets/
kubectl apply -f statefulsets/      # Redis, PostgreSQL, MinIO
kubectl apply -f deployments/
kubectl apply -f services/
kubectl apply -f ingress/
```

**WebSocket note:** The Ingress must enable WebSocket support. For NGINX Ingress:
```yaml
annotations:
  nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
  nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
  nginx.ingress.kubernetes.io/websocket-services: "chat-service"
```

---

## 3. How to Test It

### WebSocket Connection Test

```bash
# Install wscat (WebSocket CLI client)
npm install -g wscat

# Connect to the chat WebSocket
wscat -c ws://localhost:8080/ws/user1/general

# Send a message (JSON format)
{"type": "message", "content": "Hello from wscat!"}
```

### Presence System Test

```bash
# Check who's online in a room
curl http://localhost:8002/presence/general

# Check typing status
curl http://localhost:8002/presence/general/typing
```

### File Upload Test

```bash
# Upload a file
curl -X POST http://localhost:8003/upload \
  -F "file=@/path/to/image.png" \
  -F "room=general"

# Response includes a file URL
# Verify it's accessible
curl http://localhost:8080/api/files/<returned-file-id>
```

### Redis pub/sub Verification

```bash
# Connect to Redis and monitor pub/sub traffic
docker compose exec redis redis-cli MONITOR

# In another terminal, send a chat message
# Watch PUBLISH commands appear in the monitor output
```

### Scale Test (Kubernetes)

```bash
# Scale chat-service to 3 replicas
kubectl scale deployment chat-service -n chat --replicas=3

# Open 3 browser tabs, verify messages reach all tabs
# even when they connect to different pods (Redis pub/sub bridges them)
kubectl get pods -n chat
```

### Notification Test

```bash
# Send a message mentioning another user
curl -X POST http://localhost:8001/messages \
  -H "Content-Type: application/json" \
  -d '{"room": "general", "user": "alice", "content": "@bob check this out"}'

# Check bob's notifications
curl http://localhost:8004/notifications/bob
```

---

## 4. Tools Used and How

| Tool | Role | How it's used |
|------|------|---------------|
| **Docker / Docker Compose** | Local development | Runs 5 services + Redis + PostgreSQL + MinIO |
| **NGINX** | Reverse proxy + WebSocket router | Upgrades HTTP connections to WebSocket, routes API paths |
| **Redis** | Pub/sub + presence store | Chat messages published/subscribed between service instances; presence via TTL keys |
| **PostgreSQL** | Persistent storage | Message history and notifications stored durably |
| **MinIO** | S3-compatible object storage | File and image uploads; local replacement for AWS S3 |
| **WebSocket (ws://)** | Real-time protocol | Persistent bidirectional connection between browser and chat-service |
| **Kubernetes** | Production orchestration | HPA for chat-service based on WebSocket connection count |
| **NGINX Ingress Controller** | K8s ingress | WebSocket passthrough, sticky sessions optional |

### Key Concepts Practiced

- **Redis pub/sub** for fan-out messaging across multiple server instances
- **WebSocket lifecycle**: connect, heartbeat/ping-pong, disconnect handling
- **TTL-based presence**: Redis keys expire = user goes offline automatically
- **MinIO** as a self-hosted S3 — same API as AWS S3
- **Horizontal scaling of stateful WebSocket connections** via shared Redis

---

## 5. Troubleshooting

### WebSocket connection drops immediately

```bash
# Check NGINX timeout settings — WebSockets need long timeouts
docker compose logs nginx

# Verify nginx.conf has:
# proxy_read_timeout 3600s;
# proxy_send_timeout 3600s;
# proxy_set_header Upgrade $http_upgrade;
# proxy_set_header Connection "upgrade";
cat local/nginx/nginx.conf | grep -A5 websocket
```

### Messages not reaching all browser tabs

```bash
# Check Redis pub/sub is working
docker compose exec redis redis-cli SUBSCRIBE chat:general

# In another terminal, publish manually
docker compose exec redis redis-cli PUBLISH chat:general '{"content":"test"}'
# Should appear in subscriber terminal

# Check chat-service Redis connection
docker compose logs chat-service | grep redis
```

### Presence not updating (user always shows online)

```bash
# Check Redis TTL on presence keys
docker compose exec redis redis-cli TTL "presence:user1"
# Should be > 0 (counts down when user is active)
# -1 = no TTL set (bug), -2 = key expired

# Check presence-service heartbeat logic
docker compose logs presence-service
```

### File uploads failing (MinIO errors)

```bash
# Check MinIO is running
docker compose ps minio

# Check MinIO console
open http://localhost:9001  # minioadmin / minioadmin

# Check bucket exists
docker compose exec minio mc ls local/

# Check file-service environment
docker compose exec file-service env | grep MINIO
```

### Kubernetes: WebSocket 101 Upgrade Failed

```bash
# NGINX Ingress must have upgrade headers set
kubectl describe ingress chat-ingress -n chat

# Add/verify annotation:
kubectl annotate ingress chat-ingress \
  nginx.ingress.kubernetes.io/websocket-services=chat-service -n chat
```

---

## 6. Cleanup

### Local (Docker Compose)

```bash
cd hands-on-projects/project-03-realtime-chat/local/

# Stop everything
docker compose down

# Remove all data (messages, files, Redis state)
docker compose down -v

# Also remove MinIO stored files
docker compose down -v --remove-orphans
```

### Kubernetes

```bash
# Delete the entire namespace (removes all resources)
kubectl delete namespace chat

# If MinIO was installed via Helm
helm uninstall minio -n chat

# If Redis was installed via Helm
helm uninstall redis -n chat
```
