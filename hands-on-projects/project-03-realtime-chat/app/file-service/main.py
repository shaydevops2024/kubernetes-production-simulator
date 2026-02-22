import os
import io
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from minio import Minio
from minio.error import S3Error
from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL    = os.getenv("DATABASE_URL",    "sqlite:///./files.db")
MINIO_ENDPOINT  = os.getenv("MINIO_ENDPOINT",  "localhost:9000")
MINIO_ACCESS    = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET    = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET    = os.getenv("MINIO_BUCKET",    "chatfiles")
PORT            = int(os.getenv("PORT", "8023"))

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- DB Model ---

class FileModel(Base):
    __tablename__ = "files"
    id           = Column(String(50), primary_key=True)
    original_name = Column(String(300), nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes   = Column(Integer, nullable=False)
    minio_key    = Column(String(300), nullable=False)
    uploaded_by  = Column(String(100), nullable=False)
    room_id      = Column(String(50), nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)

minio_client: Optional[Minio] = None
minio_available = False


# --- Schemas ---

class FileInfo(BaseModel):
    id: str
    original_name: str
    content_type: str
    size_bytes: int
    uploaded_by: str
    room_id: Optional[str]
    created_at: datetime
    download_url: str
    class Config:
        from_attributes = True


# --- App ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    global minio_client, minio_available
    try:
        minio_client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS,
            secret_key=MINIO_SECRET,
            secure=False,
        )
        # Ensure bucket exists
        if not minio_client.bucket_exists(MINIO_BUCKET):
            minio_client.make_bucket(MINIO_BUCKET)
        minio_available = True
        print(f"[file-service] Connected to MinIO at {MINIO_ENDPOINT}, bucket: {MINIO_BUCKET}")
    except Exception as e:
        print(f"[file-service] MinIO unavailable ({e}). File uploads will return an error.")
        minio_available = False
    yield


app = FastAPI(
    title="File Service",
    description="File upload and storage via MinIO (S3-compatible). In production, swap MinIO for AWS S3.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MAX_FILE_SIZE = 10 * 1024 * 1024   # 10 MB
ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf", "text/plain",
    "application/zip",
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def build_download_url(file_id: str) -> str:
    """Return the API endpoint URL that proxies the file — browser never talks to MinIO directly."""
    return f"/api/files/{file_id}/download"


# --- Routes ---

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "file-service",
        "minio": "connected" if minio_available else "unavailable",
        "bucket": MINIO_BUCKET,
    }


@app.post("/upload", response_model=FileInfo, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    uploaded_by: str = Query("anonymous"),
    room_id: Optional[str] = Query(None),
):
    """
    Upload a file and store it in MinIO (S3-compatible object storage).

    Production note: swap MINIO_ENDPOINT for your S3 bucket endpoint.
    Add bucket policies, encryption at rest (SSE-S3), and lifecycle rules.
    """
    if not minio_available:
        raise HTTPException(status_code=503, detail="File storage (MinIO) is not available")

    # Content-type check
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail=f"File type '{content_type}' is not allowed")

    # Size check (read into memory — fine for ≤10MB)
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    file_id   = str(uuid.uuid4())
    ext       = os.path.splitext(file.filename or "file")[1]
    minio_key = f"{file_id}{ext}"

    # Upload to MinIO
    try:
        minio_client.put_object(
            MINIO_BUCKET,
            minio_key,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {e}")

    # Persist metadata
    db = SessionLocal()
    try:
        file_record = FileModel(
            id=file_id,
            original_name=file.filename or "unnamed",
            content_type=content_type,
            size_bytes=len(data),
            minio_key=minio_key,
            uploaded_by=uploaded_by,
            room_id=room_id,
            created_at=datetime.utcnow(),
        )
        db.add(file_record)
        db.commit()
        db.refresh(file_record)
    finally:
        db.close()

    return FileInfo(
        id=file_record.id,
        original_name=file_record.original_name,
        content_type=file_record.content_type,
        size_bytes=file_record.size_bytes,
        uploaded_by=file_record.uploaded_by,
        room_id=file_record.room_id,
        created_at=file_record.created_at,
        download_url=build_download_url(file_id),
    )


@app.get("/files")
def list_files(room_id: Optional[str] = Query(None), limit: int = Query(50)):
    db = SessionLocal()
    try:
        q = db.query(FileModel)
        if room_id:
            q = q.filter(FileModel.room_id == room_id)
        records = q.order_by(FileModel.created_at.desc()).limit(limit).all()
        return [
            FileInfo(
                id=r.id,
                original_name=r.original_name,
                content_type=r.content_type,
                size_bytes=r.size_bytes,
                uploaded_by=r.uploaded_by,
                room_id=r.room_id,
                created_at=r.created_at,
                download_url=build_download_url(r.id),
            )
            for r in records
        ]
    finally:
        db.close()


@app.get("/{file_id}")
def get_file_info(file_id: str):
    db = SessionLocal()
    try:
        record = db.query(FileModel).filter(FileModel.id == file_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="File not found")
        return FileInfo(
            id=record.id,
            original_name=record.original_name,
            content_type=record.content_type,
            size_bytes=record.size_bytes,
            uploaded_by=record.uploaded_by,
            room_id=record.room_id,
            created_at=record.created_at,
            download_url=build_download_url(record.id),
        )
    finally:
        db.close()


@app.get("/{file_id}/download")
def download_file(file_id: str):
    """
    Proxy the file from MinIO to the browser.
    The browser only knows about this API endpoint — MinIO is an internal detail.

    Production alternative: generate a presigned S3 URL and redirect instead,
    which offloads bandwidth from the service.
    """
    if not minio_available:
        raise HTTPException(status_code=503, detail="File storage unavailable")

    db = SessionLocal()
    try:
        record = db.query(FileModel).filter(FileModel.id == file_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="File not found")
        minio_key    = record.minio_key
        content_type = record.content_type
        filename     = record.original_name
    finally:
        db.close()

    try:
        response = minio_client.get_object(MINIO_BUCKET, minio_key)
        return StreamingResponse(
            content=response,
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    except S3Error as e:
        raise HTTPException(status_code=404, detail=f"File not found in storage: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
