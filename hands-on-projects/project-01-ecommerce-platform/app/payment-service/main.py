import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./payments.db")
PORT = int(os.getenv("PORT", "8004"))

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- DB Model ---

class PaymentModel(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(50), default="pending")   # success | failed | refunded
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


# --- Schemas ---

class ProcessPaymentRequest(BaseModel):
    order_total: float
    user_id: str


class Payment(BaseModel):
    id: int
    payment_id: str
    user_id: str
    amount: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ProcessPaymentResponse(BaseModel):
    payment_id: str
    status: str
    amount: float
    message: str


# --- Dependency ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- App ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Payment Service",
    description="Mock payment gateway — processes payments for orders",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Routes ---

@app.get("/health")
def health():
    return {"status": "healthy", "service": "payment-service"}


@app.post("/payments/process", response_model=ProcessPaymentResponse)
def process_payment(payload: ProcessPaymentRequest, db: Session = Depends(get_db)):
    """
    Mock payment processor.
    - Always succeeds for amounts <= $5000
    - Fails for amounts > $5000 (simulates declined card)
    """
    if payload.order_total <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    payment_id = str(uuid.uuid4())

    # Simulate payment logic
    if payload.order_total > 5000:
        status = "failed"
        message = "Payment declined — amount exceeds limit"
    else:
        status = "success"
        message = "Payment processed successfully"

    payment = PaymentModel(
        payment_id=payment_id,
        user_id=payload.user_id,
        amount=payload.order_total,
        status=status,
    )
    db.add(payment)
    db.commit()

    return ProcessPaymentResponse(
        payment_id=payment_id,
        status=status,
        amount=payload.order_total,
        message=message,
    )


@app.get("/payments/{payment_id}", response_model=Payment)
def get_payment(payment_id: str, db: Session = Depends(get_db)):
    payment = db.query(PaymentModel).filter(PaymentModel.payment_id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
