import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
PORT      = int(os.getenv("PORT", "8021"))

# TTLs
ONLINE_TTL_SECONDS = 30    # user is online if heartbeat within 30s
TYPING_TTL_SECONDS = 5     # typing indicator clears after 5s

redis_client: Optional[aioredis.Redis] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    yield
    await redis_client.aclose()


app = FastAPI(title="Presence Service", description="Online status and typing indicators", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# --- Schemas ---

class UserPresence(BaseModel):
    user_id: str
    username: str
    online: bool
    last_seen: Optional[str]


class TypingUser(BaseModel):
    user_id: str
    username: str
    room_id: str


# --- Routes ---

@app.get("/health")
def health():
    return {"status": "healthy", "service": "presence-service"}


@app.post("/presence/{user_id}/heartbeat")
async def heartbeat(user_id: str, username: str = "anonymous"):
    """
    Call this every ~15 seconds to stay "online".
    Uses Redis SETEX so the key auto-expires after 30s — no cleanup needed.

    Why Redis TTL?  It handles disconnects automatically. If a client stops
    sending heartbeats (browser closed, network lost), they go offline after 30s
    without any explicit logout call.
    """
    key = f"presence:user:{user_id}"
    await redis_client.setex(key, ONLINE_TTL_SECONDS, username)
    return {"status": "ok", "user_id": user_id, "online_ttl_seconds": ONLINE_TTL_SECONDS}


@app.get("/presence", response_model=List[UserPresence])
async def get_all_online():
    """Return all currently online users (those with a live heartbeat key in Redis)."""
    keys = await redis_client.keys("presence:user:*")
    users = []
    for key in keys:
        username = await redis_client.get(key)
        ttl      = await redis_client.ttl(key)
        if username and ttl > 0:
            user_id = key.removeprefix("presence:user:")
            users.append(UserPresence(
                user_id=user_id,
                username=username,
                online=True,
                last_seen=None,
            ))
    return users


@app.get("/presence/{user_id}", response_model=UserPresence)
async def get_user_presence(user_id: str):
    """Check if a specific user is online."""
    key      = f"presence:user:{user_id}"
    username = await redis_client.get(key)
    ttl      = await redis_client.ttl(key)
    return UserPresence(
        user_id=user_id,
        username=username or user_id,
        online=bool(username and ttl > 0),
        last_seen=None,
    )


@app.delete("/presence/{user_id}")
async def go_offline(user_id: str):
    """Explicitly mark a user offline (called on browser unload)."""
    await redis_client.delete(f"presence:user:{user_id}")
    return {"status": "offline", "user_id": user_id}


@app.post("/presence/{user_id}/typing")
async def start_typing(user_id: str, room_id: str, username: str = "anonymous"):
    """
    Mark a user as typing in a specific room.
    Key auto-expires after 5s — typing stops if no more events.
    """
    key = f"presence:typing:{room_id}:{user_id}"
    await redis_client.setex(key, TYPING_TTL_SECONDS, username)
    return {"status": "ok"}


@app.delete("/presence/{user_id}/typing")
async def stop_typing(user_id: str, room_id: str):
    """Explicitly stop typing indicator."""
    key = f"presence:typing:{room_id}:{user_id}"
    await redis_client.delete(key)
    return {"status": "ok"}


@app.get("/presence/rooms/{room_id}/typing", response_model=List[TypingUser])
async def get_typing_in_room(room_id: str):
    """Return list of users currently typing in a given room."""
    pattern = f"presence:typing:{room_id}:*"
    keys    = await redis_client.keys(pattern)
    typing  = []
    for key in keys:
        username = await redis_client.get(key)
        ttl      = await redis_client.ttl(key)
        if username and ttl > 0:
            user_id = key.split(":")[-1]
            typing.append(TypingUser(user_id=user_id, username=username, room_id=room_id))
    return typing


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
