import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./products.db")
PORT = int(os.getenv("PORT", "8001"))

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- DB Model ---

class ProductModel(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    category = Column(String(100), nullable=False, index=True)
    image_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)


Base.metadata.create_all(bind=engine)


# --- Pydantic Schemas ---

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    category: str
    image_url: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class Product(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    category: str
    image_url: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


# --- Dependency ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Seed Data ---

SAMPLE_PRODUCTS = [
    {"name": "Wireless Noise-Cancelling Headphones", "description": "Premium over-ear headphones with 30-hour battery life and active noise cancellation.", "price": 249.99, "category": "Electronics", "image_url": "https://picsum.photos/seed/headphones/400/300"},
    {"name": "Mechanical Keyboard", "description": "Compact TKL mechanical keyboard with Cherry MX switches and RGB backlight.", "price": 129.99, "category": "Electronics", "image_url": "https://picsum.photos/seed/keyboard/400/300"},
    {"name": "4K Webcam", "description": "Ultra HD webcam with auto-focus, low-light correction, and built-in microphone.", "price": 89.99, "category": "Electronics", "image_url": "https://picsum.photos/seed/webcam/400/300"},
    {"name": "USB-C Hub 7-in-1", "description": "Expand your ports: HDMI 4K, 3x USB-A, SD card, USB-C PD 100W.", "price": 49.99, "category": "Electronics", "image_url": "https://picsum.photos/seed/hub/400/300"},
    {"name": "Standing Desk Mat", "description": "Anti-fatigue mat with ergonomic design, 3/4 inch thick memory foam.", "price": 59.99, "category": "Office", "image_url": "https://picsum.photos/seed/deskmat/400/300"},
    {"name": "Monitor Arm", "description": "Full-motion dual monitor arm, supports monitors up to 32 inches and 17.6 lbs.", "price": 79.99, "category": "Office", "image_url": "https://picsum.photos/seed/monitorarm/400/300"},
    {"name": "Ergonomic Mouse", "description": "Vertical ergonomic mouse reducing wrist strain, 6-button programmable.", "price": 44.99, "category": "Electronics", "image_url": "https://picsum.photos/seed/mouse/400/300"},
    {"name": "Laptop Stand", "description": "Adjustable aluminum laptop stand, compatible with MacBook and 10-17 inch laptops.", "price": 39.99, "category": "Office", "image_url": "https://picsum.photos/seed/laptopstand/400/300"},
    {"name": "LED Desk Lamp", "description": "Smart LED lamp with wireless charging pad, 5 color temps, touch control.", "price": 54.99, "category": "Office", "image_url": "https://picsum.photos/seed/desklamp/400/300"},
    {"name": "Portable SSD 1TB", "description": "NVMe portable SSD with transfer speeds up to 1050MB/s, USB 3.2.", "price": 109.99, "category": "Electronics", "image_url": "https://picsum.photos/seed/ssd/400/300"},
    {"name": "Cable Management Kit", "description": "Complete cable management set with sleeves, ties, clips, and adhesive mounts.", "price": 19.99, "category": "Office", "image_url": "https://picsum.photos/seed/cables/400/300"},
    {"name": "Blue Light Glasses", "description": "Anti-blue light gaming glasses, UV400 protection, lightweight TR90 frame.", "price": 29.99, "category": "Accessories", "image_url": "https://picsum.photos/seed/glasses/400/300"},
    {"name": "Desk Organizer Set", "description": "Bamboo desk organizer with 5 compartments, pen holder, and phone stand.", "price": 34.99, "category": "Office", "image_url": "https://picsum.photos/seed/organizer/400/300"},
    {"name": "Wireless Charger Pad", "description": "15W fast wireless charger compatible with Qi devices, with LED indicator.", "price": 24.99, "category": "Electronics", "image_url": "https://picsum.photos/seed/charger/400/300"},
    {"name": "Noise Machine", "description": "White noise machine with 30 natural sounds, timer, and night light.", "price": 44.99, "category": "Accessories", "image_url": "https://picsum.photos/seed/noisemachine/400/300"},
    {"name": "Gaming Chair", "description": "Ergonomic racing-style gaming chair with lumbar support and headrest pillow.", "price": 299.99, "category": "Furniture", "image_url": "https://picsum.photos/seed/gamingchair/400/300"},
    {"name": "Bookshelf Speaker Set", "description": "Powered bookshelf speakers with Bluetooth 5.0, 120W total output.", "price": 179.99, "category": "Electronics", "image_url": "https://picsum.photos/seed/speakers/400/300"},
    {"name": "Smart Plug (4-pack)", "description": "Wi-Fi smart plugs with energy monitoring, compatible with Alexa and Google Home.", "price": 39.99, "category": "Smart Home", "image_url": "https://picsum.photos/seed/smartplug/400/300"},
    {"name": "Webcam Privacy Cover", "description": "Universal webcam cover, thin profile, compatible with all laptops.", "price": 9.99, "category": "Accessories", "image_url": "https://picsum.photos/seed/privacycover/400/300"},
    {"name": "USB Microphone", "description": "Condenser USB microphone with cardioid pattern, for podcasting and streaming.", "price": 79.99, "category": "Electronics", "image_url": "https://picsum.photos/seed/microphone/400/300"},
]


def seed_products(db: Session):
    if db.query(ProductModel).count() == 0:
        for product_data in SAMPLE_PRODUCTS:
            db.add(ProductModel(**product_data))
        db.commit()


# --- App Lifecycle ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        seed_products(db)
    finally:
        db.close()
    yield


# --- App ---

app = FastAPI(
    title="Product Service",
    description="E-Commerce product catalog service",
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
    return {"status": "healthy", "service": "product-service"}


@app.get("/products", response_model=List[Product])
def list_products(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(ProductModel).filter(ProductModel.is_active == True)
    if category:
        query = query.filter(ProductModel.category == category)
    if search:
        query = query.filter(ProductModel.name.ilike(f"%{search}%"))
    return query.all()


@app.get("/products/categories")
def list_categories(db: Session = Depends(get_db)):
    rows = db.query(ProductModel.category).filter(ProductModel.is_active == True).distinct().all()
    return [r[0] for r in rows]


@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.post("/products", response_model=Product, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    product = ProductModel(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@app.put("/products/{product_id}", response_model=Product)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)):
    product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@app.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.is_active = False
    db.commit()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
