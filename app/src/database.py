# app/src/database.py
# Database connection, models, and CRUD operations
# SQLAlchemy setup with async support for PostgreSQL

from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Text, Float, ForeignKey, Index, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid
import os
import logging

logger = logging.getLogger(__name__)

# Get database URL from environment variable (set by Kubernetes Secret)
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://k8s_demo_user:K8sDemoPass2024!@postgres-service:5432/k8s_demo_db')

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using them
    echo=False  # Set to True for SQL query logging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# ============================================
# DATABASE MODELS
# ============================================

class User(Base):
    """User model for authentication and task ownership"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    full_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active,
            "tasks_count": len(self.tasks) if self.tasks else 0
        }


class Task(Base):
    """Task model for CRUD operations demo"""
    __tablename__ = "tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(String(20), default='pending', nullable=False)  # pending, in_progress, completed
    priority = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="tasks")
    
    # Indexes
    __table_args__ = (
        Index('idx_task_user_id', 'user_id'),
        Index('idx_task_status', 'status'),
        Index('idx_task_created_at', 'created_at'),
    )
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "username": self.user.username if self.user else None,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class AppMetric(Base):
    """Application metrics for tracking and dashboard"""
    __tablename__ = "app_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float)
    metric_type = Column(String(50))  # counter, gauge, histogram
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    meta_data = Column(JSONB)  # Changed from 'metadata' (reserved name)
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "metric_type": self.metric_type,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
            "meta_data": self.meta_data  # Changed from 'metadata'
        }


# ============================================
# DATABASE UTILITY FUNCTIONS
# ============================================

def get_db():
    """
    Database session dependency for FastAPI
    Usage: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database tables
    Creates all tables if they don't exist
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        return False


def check_db_connection():
    """
    Check if database connection is working
    Returns: (bool, str) - (success, message)
    """
    try:
        db = SessionLocal()
        # Try a simple query (wrapped in text() for SQLAlchemy 2.0)
        db.execute(text("SELECT 1"))
        db.close()
        return True, "Database connection successful"
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False, f"Database connection failed: {str(e)}"


def get_db_stats():
    """
    Get database statistics for dashboard
    Returns: dict with connection info, table counts, etc.
    """
    try:
        db = SessionLocal()
        
        stats = {
            "connected": True,
            "database_url": DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else "Unknown",  # Hide password
            "users_count": db.query(User).count(),
            "tasks_count": db.query(Task).count(),
            "metrics_count": db.query(AppMetric).count(),
            "active_users_count": db.query(User).filter(User.is_active == True).count(),
            "pending_tasks_count": db.query(Task).filter(Task.status == 'pending').count(),
            "completed_tasks_count": db.query(Task).filter(Task.status == 'completed').count(),
        }
        
        db.close()
        return stats
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        return {
            "connected": False,
            "error": str(e)
        }


def record_metric(metric_name: str, metric_value: float, metric_type: str = "gauge", meta_data: dict = None):
    """
    Record an application metric to the database
    """
    try:
        db = SessionLocal()
        metric = AppMetric(
            metric_name=metric_name,
            metric_value=metric_value,
            metric_type=metric_type,
            meta_data=meta_data
        )
        db.add(metric)
        db.commit()
        db.close()
        return True
    except Exception as e:
        logger.error(f"Failed to record metric: {e}")
        return False