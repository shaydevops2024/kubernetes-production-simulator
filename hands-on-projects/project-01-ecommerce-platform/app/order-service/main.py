import os
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./orders.db")
CART_SERVICE_URL = os.getenv("CART_SERVICE_URL", "http://localhost:8002")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8004")
INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8005")
PORT = int(os.getenv("PORT", "8003"))

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- DB Model ---

class OrderModel(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    status = Column(String(50), default="pending")   # pending | paid | shipped | delivered | cancelled
    items_json = Column(Text, nullable=False)          # JSON-serialized list of items
    total = Column(Float, nullable=False)
    payment_id = Column(String(100), nullable=True)
    customer_name = Column(String(200), nullable=True)
    customer_email = Column(String(200), nullable=True)
    shipping_address = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


# --- Schemas ---

class OrderItem(BaseModel):
    product_id: int
    name: str
    price: float
    quantity: int
    subtotal: float


class CreateOrderRequest(BaseModel):
    user_id: str
    customer_name: str
    customer_email: str
    shipping_address: str


class UpdateStatusRequest(BaseModel):
    status: str


class Order(BaseModel):
    id: int
    user_id: str
    status: str
    items: List[OrderItem]
    total: float
    payment_id: Optional[str]
    customer_name: Optional[str]
    customer_email: Optional[str]
    shipping_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# --- Dependency ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Helpers ---

def order_to_schema(order: OrderModel) -> Order:
    return Order(
        id=order.id,
        user_id=order.user_id,
        status=order.status,
        items=json.loads(order.items_json),
        total=order.total,
        payment_id=order.payment_id,
        customer_name=order.customer_name,
        customer_email=order.customer_email,
        shipping_address=order.shipping_address,
        created_at=order.created_at,
    )


# --- App ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Order Service",
    description="Order management — creates orders from carts and tracks their status",
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
    return {"status": "healthy", "service": "order-service"}


@app.get("/orders", response_model=List[Order])
def list_orders(db: Session = Depends(get_db)):
    orders = db.query(OrderModel).order_by(OrderModel.created_at.desc()).all()
    return [order_to_schema(o) for o in orders]


@app.get("/orders/{order_id}", response_model=Order)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(OrderModel).filter(OrderModel.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_to_schema(order)


@app.post("/orders", response_model=Order, status_code=201)
async def create_order(payload: CreateOrderRequest, db: Session = Depends(get_db)):
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Fetch cart
        try:
            cart_resp = await client.get(f"{CART_SERVICE_URL}/cart/{payload.user_id}")
            cart_resp.raise_for_status()
            cart = cart_resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Cart service unavailable")

        if not cart["items"]:
            raise HTTPException(status_code=400, detail="Cart is empty")

        total = cart["total"]

        # 2. Process payment
        try:
            payment_resp = await client.post(
                f"{PAYMENT_SERVICE_URL}/payments/process",
                json={"order_total": total, "user_id": payload.user_id},
            )
            payment_resp.raise_for_status()
            payment = payment_resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Payment service unavailable")

        if payment["status"] != "success":
            raise HTTPException(status_code=402, detail="Payment failed")

        # 3. Reserve inventory (best-effort)
        for item in cart["items"]:
            try:
                await client.post(
                    f"{INVENTORY_SERVICE_URL}/inventory/{item['product_id']}/reserve",
                    json={"quantity": item["quantity"]},
                )
            except Exception:
                pass  # Don't block order on inventory errors

        # 4. Save order
        order = OrderModel(
            user_id=payload.user_id,
            status="paid",
            items_json=json.dumps(cart["items"]),
            total=total,
            payment_id=payment["payment_id"],
            customer_name=payload.customer_name,
            customer_email=payload.customer_email,
            shipping_address=payload.shipping_address,
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        # 5. Clear cart
        try:
            await client.delete(f"{CART_SERVICE_URL}/cart/{payload.user_id}")
        except Exception:
            pass

    return order_to_schema(order)


@app.patch("/orders/{order_id}/status", response_model=Order)
def update_status(order_id: int, payload: UpdateStatusRequest, db: Session = Depends(get_db)):
    valid_statuses = {"pending", "paid", "shipped", "delivered", "cancelled"}
    if payload.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Choose from: {valid_statuses}")

    order = db.query(OrderModel).filter(OrderModel.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = payload.status
    db.commit()
    db.refresh(order)
    return order_to_schema(order)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
