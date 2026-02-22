import os
import json
import uuid
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chat.db")
REDIS_URL    = os.getenv("REDIS_URL", "redis://localhost:6379")
PORT         = int(os.getenv("PORT", "8020"))

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- DB Models ---

class RoomModel(Base):
    __tablename__ = "rooms"
    id          = Column(String(50), primary_key=True)
    name        = Column(String(100), nullable=False)
    description = Column(String(300), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)


class MessageModel(Base):
    __tablename__ = "messages"
    id           = Column(String(50), primary_key=True)
    room_id      = Column(String(50), nullable=False, index=True)
    user_id      = Column(String(100), nullable=False)
    username     = Column(String(100), nullable=False)
    content      = Column(Text, nullable=False)
    message_type = Column(String(20), default="text")   # text | file | system
    file_url     = Column(String(500), nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


# --- Seed data ---

SEED_ROOMS = [
    {"id": "general",  "name": "# general",  "description": "General discussion — everyone welcome"},
    {"id": "devops",   "name": "# devops",   "description": "DevOps tools, K8s, Docker, CI/CD"},
    {"id": "random",   "name": "# random",   "description": "Off-topic, memes, water cooler chat"},
]

SEED_MESSAGES = [
    {"room_id": "general", "user_id": "alice",   "username": "alice",   "content": "👋 Hey everyone! Welcome to ChatFlow."},
    {"room_id": "general", "user_id": "bob",     "username": "bob",     "content": "Awesome platform! Love the real-time feel."},
    {"room_id": "general", "user_id": "alice",   "username": "alice",   "content": "This is running on WebSockets + Redis pub/sub. Each replica handles its own WS connections, Redis keeps them in sync."},
    {"room_id": "devops",  "user_id": "charlie", "username": "charlie", "content": "🚀 Anyone deployed this to K8s yet?"},
    {"room_id": "devops",  "user_id": "bob",     "username": "bob",     "content": "Working on it! The WebSocket Ingress config is the interesting part."},
    {"room_id": "random",  "user_id": "alice",   "username": "alice",   "content": "☕ Coffee break. Anyone else?"},
]


# --- WebSocket Connection Manager ---

class ConnectionManager:
    """Manages WebSocket connections per room. Works in single-node mode.
    When running multiple replicas, Redis pub/sub keeps all nodes in sync."""

    def __init__(self):
        # room_id → list of {"ws": WebSocket, "user_id": str, "username": str}
        self.rooms: Dict[str, List[dict]] = {}

    async def connect(self, ws: WebSocket, room_id: str, user_id: str, username: str):
        await ws.accept()
        self.rooms.setdefault(room_id, [])
        self.rooms[room_id].append({"ws": ws, "user_id": user_id, "username": username})

    def disconnect(self, ws: WebSocket, room_id: str):
        if room_id in self.rooms:
            self.rooms[room_id] = [c for c in self.rooms[room_id] if c["ws"] is not ws]

    async def send_to_room(self, room_id: str, message: dict):
        """Broadcast to all local WebSocket connections in a room."""
        for conn in list(self.rooms.get(room_id, [])):
            try:
                await conn["ws"].send_json(message)
            except Exception:
                pass


manager = ConnectionManager()
redis_client: Optional[aioredis.Redis] = None
subscriber_task: Optional[asyncio.Task] = None


async def redis_subscriber():
    """Listen to all room channels from Redis and forward to local WS connections.
    This is the key to horizontal scaling: each replica subscribes to Redis and
    delivers messages to its own connected clients."""
    pubsub = redis_client.pubsub()
    await pubsub.psubscribe("room:*")
    try:
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                try:
                    data = json.loads(message["data"])
                    room_id = data.get("room_id")
                    if room_id:
                        await manager.send_to_room(room_id, data)
                except Exception:
                    pass
    except asyncio.CancelledError:
        await pubsub.punsubscribe("room:*")
        raise


async def publish_to_room(room_id: str, payload: dict):
    """Publish a message to Redis so all replicas can deliver it to their WS clients."""
    if redis_client:
        try:
            await redis_client.publish(f"room:{room_id}", json.dumps(payload))
            return
        except Exception:
            pass
    # Fallback: direct local broadcast (single-node only)
    await manager.send_to_room(room_id, payload)


# --- App lifecycle ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, subscriber_task

    # Seed DB
    db = SessionLocal()
    try:
        if db.query(RoomModel).count() == 0:
            for r in SEED_ROOMS:
                db.add(RoomModel(**r))
            db.commit()
        if db.query(MessageModel).count() == 0:
            for m in SEED_MESSAGES:
                db.add(MessageModel(id=str(uuid.uuid4()), created_at=datetime.utcnow(), **m))
            db.commit()
    finally:
        db.close()

    # Connect to Redis and start pub/sub listener
    try:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        subscriber_task = asyncio.create_task(redis_subscriber())
    except Exception as e:
        print(f"[chat-service] Redis unavailable ({e}). Running in single-node mode.")
        redis_client = None

    yield

    if subscriber_task:
        subscriber_task.cancel()
        try:
            await subscriber_task
        except asyncio.CancelledError:
            pass
    if redis_client:
        await redis_client.aclose()


# --- App ---

app = FastAPI(title="Chat Service", description="WebSocket-based real-time chat", version="1.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# --- Dependency ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Schemas ---

class RoomCreate(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class Room(BaseModel):
    id: str
    name: str
    description: Optional[str]
    class Config:
        from_attributes = True


class Message(BaseModel):
    id: str
    room_id: str
    user_id: str
    username: str
    content: str
    message_type: str
    file_url: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True


# --- REST Routes ---

@app.get("/health")
def health():
    return {"status": "healthy", "service": "chat-service"}


@app.get("/rooms", response_model=List[Room])
def list_rooms(db: Session = Depends(get_db)):
    return db.query(RoomModel).all()


@app.post("/rooms", response_model=Room, status_code=201)
def create_room(payload: RoomCreate, db: Session = Depends(get_db)):
    existing = db.query(RoomModel).filter(RoomModel.id == payload.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Room already exists")
    room = RoomModel(**payload.model_dump(), created_at=datetime.utcnow())
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@app.get("/rooms/{room_id}/messages", response_model=List[Message])
def get_messages(room_id: str, limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    room = db.query(RoomModel).filter(RoomModel.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return (
        db.query(MessageModel)
        .filter(MessageModel.room_id == room_id)
        .order_by(MessageModel.created_at.asc())
        .limit(limit)
        .all()
    )


# --- WebSocket Route ---

@app.websocket("/ws/{room_id}/{user_id}")
async def websocket_endpoint(ws: WebSocket, room_id: str, user_id: str, username: str = Query("anonymous")):
    """
    WebSocket endpoint for real-time chat.

    Connection: ws://host/ws/{room_id}/{user_id}?username=alice

    Message types sent by client:
      {"type": "message", "content": "Hello!"}
      {"type": "message", "content": "file.png", "message_type": "file", "file_url": "/api/files/123"}
      {"type": "typing"}
      {"type": "stop_typing"}

    Message types received by client:
      {"type": "message",     "id", "room_id", "user_id", "username", "content", "message_type", "file_url", "timestamp"}
      {"type": "typing",      "user_id", "username", "room_id"}
      {"type": "stop_typing", "user_id", "username", "room_id"}
      {"type": "user_joined", "user_id", "username", "room_id"}
      {"type": "user_left",   "user_id", "username", "room_id"}
      {"type": "system",      "content", "room_id"}
    """
    # Verify room exists
    db = SessionLocal()
    try:
        room = db.query(RoomModel).filter(RoomModel.id == room_id).first()
        if not room:
            await ws.close(code=4004)
            return
    finally:
        db.close()

    await manager.connect(ws, room_id, user_id, username)

    # Announce join
    await publish_to_room(room_id, {
        "type": "user_joined",
        "user_id": user_id,
        "username": username,
        "room_id": room_id,
        "timestamp": datetime.utcnow().isoformat(),
    })

    try:
        while True:
            data = await ws.receive_json()
            event_type = data.get("type", "message")

            if event_type == "message":
                content      = data.get("content", "").strip()
                msg_type     = data.get("message_type", "text")
                file_url     = data.get("file_url")
                if not content:
                    continue

                # Persist to DB
                msg_id = str(uuid.uuid4())
                db = SessionLocal()
                try:
                    db.add(MessageModel(
                        id=msg_id, room_id=room_id, user_id=user_id,
                        username=username, content=content,
                        message_type=msg_type, file_url=file_url,
                        created_at=datetime.utcnow(),
                    ))
                    db.commit()
                finally:
                    db.close()

                # Broadcast via Redis (or direct fallback)
                await publish_to_room(room_id, {
                    "type": "message",
                    "id": msg_id,
                    "room_id": room_id,
                    "user_id": user_id,
                    "username": username,
                    "content": content,
                    "message_type": msg_type,
                    "file_url": file_url,
                    "timestamp": datetime.utcnow().isoformat(),
                })

            elif event_type == "typing":
                await publish_to_room(room_id, {
                    "type": "typing",
                    "user_id": user_id,
                    "username": username,
                    "room_id": room_id,
                })

            elif event_type == "stop_typing":
                await publish_to_room(room_id, {
                    "type": "stop_typing",
                    "user_id": user_id,
                    "username": username,
                    "room_id": room_id,
                })

    except WebSocketDisconnect:
        manager.disconnect(ws, room_id)
        await publish_to_room(room_id, {
            "type": "user_left",
            "user_id": user_id,
            "username": username,
            "room_id": room_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        manager.disconnect(ws, room_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
