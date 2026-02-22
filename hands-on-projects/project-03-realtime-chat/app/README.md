# App — Real-Time Chat Services

This folder contains the source code for all 4 microservices and the frontend. Each service is a standalone Python FastAPI application. The frontend is a single-page HTML/JS/CSS chat UI served by nginx.

You don't write application code — your job is to containerize, run, and eventually deploy it.

---

## Services Overview

| Service | Port | Language | Datastore | Description |
|---------|------|----------|-----------|-------------|
| **chat-service** | 8020 | Python/FastAPI | PostgreSQL + Redis | WebSocket chat engine with message persistence and pub/sub |
| **presence-service** | 8021 | Python/FastAPI | Redis | Online status and typing indicators via Redis TTL keys |
| **notification-service** | 8022 | Python/FastAPI | PostgreSQL | Push notification tracking for mentions and messages |
| **file-service** | 8023 | Python/FastAPI | PostgreSQL + MinIO | File upload and storage (S3-compatible) |
| **frontend** | 80 | HTML/CSS/JS + nginx | — | Single-page chat UI with WebSocket client |

---

## Architecture

```
Browser
  │
  ├── WebSocket ─────→ /ws/{room_id}/{user_id}?username=xxx
  │                              │
  │                         chat-service (8020)
  │                              │                    ┌─────────────────┐
  │                         ┌───┴───────────────┐     │  Redis pub/sub  │
  │                         │  on message recv: │────→│  room:general   │←──── all replicas
  │                         │  1. Save to PG    │     │  room:devops    │      subscribe here
  │                         │  2. Publish Redis │     └─────────────────┘
  │                         └───────────────────┘
  │                              │
  │                         PostgreSQL (messages, rooms)
  │
  ├── REST ──────────→ /api/presence/*
  │                         presence-service (8021)
  │                              │
  │                         Redis (TTL keys per user, TTL keys per typing event)
  │
  ├── REST ──────────→ /api/notifications/*
  │                         notification-service (8022)
  │                              │
  │                         PostgreSQL (notifications table)
  │
  └── REST ──────────→ /api/files/*
                            file-service (8023)
                                 │
                            MinIO (S3-compatible object storage)
                            PostgreSQL (file metadata)
```

---

## Running a Single Service (without Docker)

```bash
# Example: run the chat service
cd chat-service
pip install -r requirements.txt
uvicorn main:app --reload --port 8020
```

Then open: http://localhost:8020/docs — every service has automatic Swagger UI.

The chat-service will use SQLite and fall back to single-node mode (no Redis) if Redis isn't running locally.

---

## Environment Variables

### chat-service
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./chat.db` | PostgreSQL or SQLite connection string |
| `REDIS_URL` | `redis://localhost:6379` | Redis URL for pub/sub (falls back to local broadcast if unavailable) |
| `PORT` | `8020` | Port to listen on |

### presence-service
| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis URL (required — presence is Redis-only) |
| `PORT` | `8021` | Port to listen on |

### notification-service
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./notifications.db` | Database connection string |
| `PORT` | `8022` | Port to listen on |

### file-service
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./files.db` | Database for file metadata |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO (or S3) endpoint |
| `MINIO_ACCESS_KEY` | `minioadmin` | Access key |
| `MINIO_SECRET_KEY` | `minioadmin` | Secret key |
| `MINIO_BUCKET` | `chatfiles` | Bucket name |
| `PORT` | `8023` | Port to listen on |

---

## API Contracts

### chat-service

**WebSocket:**
```
ws://host/ws/{room_id}/{user_id}?username=alice
```

Client → Server messages:
```json
{"type": "message",     "content": "Hello!"}
{"type": "message",     "content": "file.png", "message_type": "file", "file_url": "/api/files/123/download"}
{"type": "typing"}
{"type": "stop_typing"}
```

Server → Client messages:
```json
{"type": "message",     "id", "room_id", "user_id", "username", "content", "message_type", "file_url", "timestamp"}
{"type": "typing",      "user_id", "username", "room_id"}
{"type": "stop_typing", "user_id", "username", "room_id"}
{"type": "user_joined", "user_id", "username", "room_id", "timestamp"}
{"type": "user_left",   "user_id", "username", "room_id", "timestamp"}
```

**REST:**
```
GET    /rooms                         → List all rooms
POST   /rooms                         → Create room {id, name, description}
GET    /rooms/{room_id}/messages      → Get message history (?limit=50)
GET    /health                        → Health check
```

### presence-service
```
POST   /presence/{user_id}/heartbeat  → Stay online (?username=alice)
GET    /presence                      → List all online users
GET    /presence/{user_id}            → Check a specific user
DELETE /presence/{user_id}            → Go offline explicitly
POST   /presence/{user_id}/typing     → Start typing (?room_id=general&username=alice)
DELETE /presence/{user_id}/typing     → Stop typing (?room_id=general)
GET    /presence/rooms/{room_id}/typing → Who is typing in a room
GET    /health                        → Health check
```

### notification-service
```
POST   /notifications                  → Create notification {user_id, title, body, notif_type, room_id}
GET    /notifications/{user_id}        → Get notifications (?unread_only=false&limit=50)
GET    /notifications/{user_id}/unread-count → Count unread notifications
PATCH  /notifications/{id}/read        → Mark one notification as read
PATCH  /notifications/{user_id}/read-all → Mark all as read
DELETE /notifications/{id}             → Delete notification
GET    /health                         → Health check
```

### file-service
```
POST   /upload                         → Upload a file (multipart/form-data)
GET    /files                          → List uploaded files (?room_id=general)
GET    /{file_id}                      → Get file metadata
GET    /{file_id}/download             → Download file (proxied from MinIO)
GET    /health                         → Health check (includes MinIO status)
```

---

## Key Design Decisions

### Why Redis pub/sub for chat?

When you run multiple `chat-service` replicas, each replica has its own in-memory WebSocket connections. Without Redis:
- User A connected to Replica 1 sends a message
- Replica 2 never knows about it — users connected to Replica 2 miss the message

With Redis pub/sub:
- Replica 1 receives the message via WebSocket and publishes to Redis channel `room:general`
- Redis delivers the message to ALL replicas (including Replica 1)
- Each replica broadcasts to its local WebSocket connections
- Every user sees the message — regardless of which replica they're connected to

This is the standard pattern for horizontally scalable WebSocket services.

### Why Redis TTL for presence?

Instead of tracking "user connected / user disconnected" events (which miss crashes and network drops), presence uses a heartbeat + TTL approach:

- The frontend sends `POST /presence/{user_id}/heartbeat` every 15 seconds
- Redis stores the key with a 30-second TTL
- If the browser closes, crashes, or the network drops, no more heartbeats → key expires after 30s → user goes offline automatically

This is more reliable than tracking connection events.

### Why MinIO for file storage?

MinIO is S3-compatible. The file-service code uses the MinIO Python client, but the same code works with AWS S3 by just changing the endpoint and credentials. In production, you'd set:
```
MINIO_ENDPOINT=s3.amazonaws.com
MINIO_ACCESS_KEY=your-aws-access-key
MINIO_SECRET_KEY=your-aws-secret-key
MINIO_BUCKET=your-s3-bucket
```

---

## Dockerfiles

All services follow the same pattern:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE <port>
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "<port>"]
```

**Questions to think about:**
- Why `python:3.11-slim` and not `python:3.11`?
- What does `--no-cache-dir` do?
- What's missing for production? (non-root user, health check directive, multi-stage build)
- How would you add the non-root user without breaking file permissions?
