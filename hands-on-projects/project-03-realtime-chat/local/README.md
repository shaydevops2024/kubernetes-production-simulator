# Local — Running ChatFlow with Docker Compose

This is your first DevOps task: get the entire real-time chat platform running locally with Docker Compose.

By the end of this step you'll have:
- A live WebSocket-based chat running in your browser
- Redis handling pub/sub for horizontal scaling
- 3 PostgreSQL databases (chat messages, notifications, file metadata)
- MinIO object storage for file uploads
- nginx routing WebSocket and REST traffic to the right service

---

## Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose plugin)
- At least 4GB of free RAM
- Ports 8092, 9000, 9001 not in use

Verify:
```bash
docker --version        # Docker version 24+
docker compose version  # Docker Compose version v2+
```

---

## Run It

```bash
# From this directory (local/)
docker compose up --build
```

First build takes 3–5 minutes. Once all services are healthy:

- **Chat UI:** http://localhost:8092
- **MinIO Console:** http://localhost:9001 (login: `minioadmin` / `minioadmin`)
- **Chat Service API docs:** http://localhost:8092/api/chat/docs
- **Presence Service API docs:** http://localhost:8092/api/presence/docs
- **Notification Service API docs:** http://localhost:8092/api/notifications/docs
- **File Service API docs:** http://localhost:8092/api/files/docs

---

## Architecture in docker-compose

```
Browser (http://localhost:8092)
        │
        ▼
   [gateway — nginx:80]                ← Port 8092 exposed to host
        │
        ├── /ws/*         ──→ chat-service:8020    (WebSocket, HTTP Upgrade)
        │                         │
        │                    Redis pub/sub ←── enables horizontal scaling
        │                         │
        │                    PostgreSQL    ←── message persistence
        │
        ├── /api/chat/*   ──→ chat-service:8020    (REST: rooms, history)
        ├── /api/presence/* → presence-service:8021 ← Redis TTL keys
        ├── /api/notifications/* → notification-service:8022 ← PostgreSQL
        ├── /api/files/*  ──→ file-service:8023     ← MinIO storage
        └── /             ──→ frontend:80           (static HTML/JS)
```

**Key learning:** The WebSocket connection proxied by nginx requires special headers:
- `Upgrade: websocket`
- `Connection: upgrade`
- Long timeout settings (`proxy_read_timeout 3600s`)

Without these, nginx drops WebSocket connections after 60 seconds. Open `nginx/nginx.conf` and read the comments.

---

## Useful Commands

```bash
# Start in detached mode
docker compose up --build -d

# Check status
docker compose ps

# Tail logs for a specific service
docker compose logs -f chat-service
docker compose logs -f presence-service

# Tail all logs
docker compose logs -f

# Stop everything
docker compose down

# Stop and remove all data (reset databases, MinIO storage)
docker compose down -v

# Rebuild only one service after code change
docker compose up --build chat-service
```

---

## DevOps Tasks for This Phase

### Task 1 — Observe WebSocket Traffic

Open the browser, go to http://localhost:8092, open DevTools → Network tab, filter by "WS".

Send a message in the chat. Watch the WebSocket frames:

```bash
# You'll see the handshake and then JSON frames like:
# {"type":"message","content":"hello","room_id":"general",...}
```

**Questions:**
- What HTTP status code starts a WebSocket upgrade? (hint: not 200)
- How is the WebSocket connection identified in the Network tab?
- What happens to the WS connection when you switch rooms?

### Task 2 — Explore Redis pub/sub

```bash
# Open a Redis CLI session
docker compose exec redis redis-cli

# Monitor all commands in real-time
127.0.0.1:6379> MONITOR

# In another terminal, send a chat message in the browser.
# Watch what appears in the MONITOR output — you'll see the PUBLISH command!
```

In another terminal:
```bash
# Subscribe to the general room channel directly
docker compose exec redis redis-cli SUBSCRIBE "room:general"

# Now send a message in the browser and watch it appear here in real-time!
```

**Question:** Why does the chat-service subscribe to `room:*` (all rooms) instead of a specific room?
How does this allow one instance to handle messages for multiple rooms?

### Task 3 — Check Presence via Redis

```bash
# See all online users (presence keys with TTL)
docker compose exec redis redis-cli KEYS "presence:user:*"

# Check the TTL for your user
docker compose exec redis redis-cli TTL "presence:user:YOUR-USERNAME"

# After 30 seconds of not sending a heartbeat, your key expires.
# Try stopping the heartbeat by closing the browser and watching the key disappear.
```

**Question:** What is a Redis TTL-based presence system? How does it handle disconnects better
than storing "last seen" in a SQL database?

### Task 4 — Inspect MinIO

After uploading a file via the chat UI:

1. Open http://localhost:9001 (MinIO Console, login: minioadmin/minioadmin)
2. Go to Buckets → chatfiles
3. Browse the uploaded files

```bash
# Also check the file-service database
docker compose exec postgres-files psql -U chatuser -d files_db
\dt
SELECT id, original_name, content_type, size_bytes, minio_key FROM files;
\q
```

**Question:** The file is stored in MinIO with a UUID key (not the original filename). Why?
What are the advantages of content-addressable storage?

### Task 5 — Simulate Horizontal Scaling

The chat service uses Redis pub/sub to support multiple replicas. Let's test it:

```bash
# Scale chat-service to 2 replicas
docker compose up --scale chat-service=2 -d

# Check that both are running
docker compose ps chat-service

# Open two browser tabs. Connect with different usernames.
# Send messages from each tab — they should both receive each other's messages!
# (Even though they might be on different replicas)
```

**Note:** The nginx gateway config only has one upstream for `chat-service`. For load balancing
across replicas, you'd need to change the nginx config. In Kubernetes, the Service object
handles this automatically.

### Task 6 — Simulate a Redis Failure

```bash
# Stop Redis
docker compose stop redis

# Try sending a chat message in the browser.
# What happens? Does the chat-service fall back gracefully?
# Look at the logs:
docker compose logs -f chat-service

# Bring Redis back
docker compose start redis

# Messages should work again without restarting the chat-service.
```

### Task 7 — Explore the Database Schemas

```bash
# Connect to the chat database
docker compose exec postgres-chat psql -U chatuser -d chat_db

\dt                          -- list tables
\d rooms                     -- describe rooms table
\d messages                  -- describe messages table

SELECT id, room_id, username, LEFT(content, 50) AS preview, created_at FROM messages ORDER BY created_at DESC LIMIT 10;
\q
```

---

## Common Issues

**Port 8092 already in use:**
```bash
lsof -i :8092
# Change the port in docker-compose.yml: "8093:80" instead of "8092:80"
```

**MinIO not healthy:**
MinIO takes ~15 seconds to start. The file-service waits for it. If it still fails, check:
```bash
docker compose logs minio
```

**WebSocket connection fails:**
Check the gateway logs. The most common issue is the `Upgrade` header not being forwarded:
```bash
docker compose logs gateway
```

---

## Next Step

Once you're comfortable with the local stack, move to [../main/README.md](../main/README.md)
to deploy this on Kubernetes — including the tricky WebSocket Ingress configuration.
