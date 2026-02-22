import os
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./inventory.db")
PORT = int(os.getenv("PORT", "8005"))

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- DB Model ---

class InventoryModel(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, unique=True, nullable=False, index=True)
    product_name = Column(String(200), nullable=True)
    quantity = Column(Integer, default=0)
    reserved = Column(Integer, default=0)  # reserved for pending orders


Base.metadata.create_all(bind=engine)


# --- Schemas ---

class InventoryItem(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    reserved: int
    available: int  # computed: quantity - reserved

    class Config:
        from_attributes = True


class UpdateStockRequest(BaseModel):
    quantity: int
    product_name: str = ""


class ReserveRequest(BaseModel):
    quantity: int


# --- Seed Data ---

def seed_inventory(db: Session):
    if db.query(InventoryModel).count() == 0:
        # Default stock for all 20 products (product IDs 1-20)
        defaults = [
            (1, "Wireless Noise-Cancelling Headphones", 50),
            (2, "Mechanical Keyboard", 75),
            (3, "4K Webcam", 30),
            (4, "USB-C Hub 7-in-1", 100),
            (5, "Standing Desk Mat", 60),
            (6, "Monitor Arm", 40),
            (7, "Ergonomic Mouse", 90),
            (8, "Laptop Stand", 80),
            (9, "LED Desk Lamp", 45),
            (10, "Portable SSD 1TB", 35),
            (11, "Cable Management Kit", 120),
            (12, "Blue Light Glasses", 200),
            (13, "Desk Organizer Set", 55),
            (14, "Wireless Charger Pad", 70),
            (15, "Noise Machine", 25),
            (16, "Gaming Chair", 15),
            (17, "Bookshelf Speaker Set", 20),
            (18, "Smart Plug (4-pack)", 85),
            (19, "Webcam Privacy Cover", 300),
            (20, "USB Microphone", 40),
        ]
        for product_id, name, qty in defaults:
            db.add(InventoryModel(product_id=product_id, product_name=name, quantity=qty, reserved=0))
        db.commit()


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
    db = SessionLocal()
    try:
        seed_inventory(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Inventory Service",
    description="Stock level management — tracks product quantities and reservations",
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
    return {"status": "healthy", "service": "inventory-service"}


@app.get("/inventory", response_model=List[InventoryItem])
def list_inventory(db: Session = Depends(get_db)):
    items = db.query(InventoryModel).all()
    return [
        InventoryItem(
            id=i.id,
            product_id=i.product_id,
            product_name=i.product_name or "",
            quantity=i.quantity,
            reserved=i.reserved,
            available=max(0, i.quantity - i.reserved),
        )
        for i in items
    ]


@app.get("/inventory/{product_id}", response_model=InventoryItem)
def get_inventory(product_id: int, db: Session = Depends(get_db)):
    item = db.query(InventoryModel).filter(InventoryModel.product_id == product_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Product not in inventory")
    return InventoryItem(
        id=item.id,
        product_id=item.product_id,
        product_name=item.product_name or "",
        quantity=item.quantity,
        reserved=item.reserved,
        available=max(0, item.quantity - item.reserved),
    )


@app.put("/inventory/{product_id}", response_model=InventoryItem)
def update_stock(product_id: int, payload: UpdateStockRequest, db: Session = Depends(get_db)):
    if payload.quantity < 0:
        raise HTTPException(status_code=400, detail="Quantity cannot be negative")

    item = db.query(InventoryModel).filter(InventoryModel.product_id == product_id).first()
    if not item:
        item = InventoryModel(product_id=product_id, product_name=payload.product_name, quantity=0, reserved=0)
        db.add(item)

    item.quantity = payload.quantity
    if payload.product_name:
        item.product_name = payload.product_name
    db.commit()
    db.refresh(item)

    return InventoryItem(
        id=item.id,
        product_id=item.product_id,
        product_name=item.product_name or "",
        quantity=item.quantity,
        reserved=item.reserved,
        available=max(0, item.quantity - item.reserved),
    )


@app.post("/inventory/{product_id}/reserve")
def reserve_stock(product_id: int, payload: ReserveRequest, db: Session = Depends(get_db)):
    if payload.quantity < 1:
        raise HTTPException(status_code=400, detail="Reserve quantity must be at least 1")

    item = db.query(InventoryModel).filter(InventoryModel.product_id == product_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Product not in inventory")

    available = item.quantity - item.reserved
    if available < payload.quantity:
        raise HTTPException(
            status_code=409,
            detail=f"Insufficient stock. Available: {available}, Requested: {payload.quantity}",
        )

    item.reserved += payload.quantity
    db.commit()
    return {"reserved": payload.quantity, "remaining_available": item.quantity - item.reserved}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
