import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./notifications.db")
PORT         = int(os.getenv("PORT", "8022"))

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- DB Model ---

class NotificationModel(Base):
    __tablename__ = "notifications"
    id         = Column(String(50), primary_key=True)
    user_id    = Column(String(100), nullable=False, index=True)
    title      = Column(String(200), nullable=False)
    body       = Column(Text, nullable=False)
    notif_type = Column(String(50), default="message")   # message | mention | system
    room_id    = Column(String(50), nullable=True)
    from_user  = Column(String(100), nullable=True)
    read       = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


# --- Schemas ---

class NotificationCreate(BaseModel):
    user_id: str
    title: str
    body: str
    notif_type: str = "message"
    room_id: Optional[str] = None
    from_user: Optional[str] = None


class Notification(BaseModel):
    id: str
    user_id: str
    title: str
    body: str
    notif_type: str
    room_id: Optional[str]
    from_user: Optional[str]
    read: bool
    created_at: datetime
    class Config:
        from_attributes = True


# --- App ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Notification Service",
    description="Push notifications for chat messages, mentions, and system events",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Routes ---

@app.get("/health")
def health():
    return {"status": "healthy", "service": "notification-service"}


@app.post("/notifications", response_model=Notification, status_code=201)
def create_notification(payload: NotificationCreate, db: Session = Depends(get_db)):
    """Create a push notification for a user.

    In production this would also trigger:
    - Web Push (browser push notifications via VAPID)
    - Mobile push (FCM / APNs)
    - Email notification for offline users
    """
    notif = NotificationModel(
        id=str(uuid.uuid4()),
        created_at=datetime.utcnow(),
        **payload.model_dump(),
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


@app.get("/notifications/{user_id}", response_model=List[Notification])
def get_notifications(
    user_id: str,
    unread_only: bool = Query(False),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """Fetch notifications for a user. Poll this endpoint to show the notification badge."""
    q = db.query(NotificationModel).filter(NotificationModel.user_id == user_id)
    if unread_only:
        q = q.filter(NotificationModel.read == False)
    return q.order_by(NotificationModel.created_at.desc()).limit(limit).all()


@app.get("/notifications/{user_id}/unread-count")
def get_unread_count(user_id: str, db: Session = Depends(get_db)):
    count = (
        db.query(NotificationModel)
        .filter(NotificationModel.user_id == user_id, NotificationModel.read == False)
        .count()
    )
    return {"user_id": user_id, "unread_count": count}


@app.patch("/notifications/{notification_id}/read")
def mark_read(notification_id: str, db: Session = Depends(get_db)):
    notif = db.query(NotificationModel).filter(NotificationModel.id == notification_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.read = True
    db.commit()
    return {"status": "ok", "id": notification_id}


@app.patch("/notifications/{user_id}/read-all")
def mark_all_read(user_id: str, db: Session = Depends(get_db)):
    db.query(NotificationModel).filter(
        NotificationModel.user_id == user_id,
        NotificationModel.read == False,
    ).update({"read": True})
    db.commit()
    return {"status": "ok", "user_id": user_id}


@app.delete("/notifications/{notification_id}")
def delete_notification(notification_id: str, db: Session = Depends(get_db)):
    notif = db.query(NotificationModel).filter(NotificationModel.id == notification_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.delete(notif)
    db.commit()
    return {"status": "deleted"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
