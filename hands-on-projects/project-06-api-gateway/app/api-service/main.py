import os
import time
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from jose import JWTError, jwt

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./gateway_demo.db")
PORT = int(os.getenv("PORT", "8001"))
JWT_SECRET = os.getenv("JWT_SECRET", "gateway-demo-secret-key-2024")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── In-memory request metrics ──────────────────────────────────────────────
class MetricsStore:
    def __init__(self):
        self.endpoints: dict = {}
        self.start_time: float = time.time()
        self.rate_limit_hits: int = 0
        self.auth_failures: int = 0

    def record(self, endpoint: str, status: int, latency_ms: float = 0):
        if endpoint not in self.endpoints:
            self.endpoints[endpoint] = {"total": 0, "errors": 0, "total_latency": 0.0}
        self.endpoints[endpoint]["total"] += 1
        if status >= 400:
            self.endpoints[endpoint]["errors"] += 1
            if status == 429:
                self.rate_limit_hits += 1
            if status == 401:
                self.auth_failures += 1
        self.endpoints[endpoint]["total_latency"] += latency_ms


metrics = MetricsStore()


# ── DB Models ─────────────────────────────────────────────────────────────
class ProductModel(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    category = Column(String(100), nullable=False)
    stock = Column(Integer, default=100)
    rating = Column(Float, default=4.5)
    is_active = Column(Boolean, default=True)


class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    plan = Column(String(50), default="free")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class OrderModel(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    product_ids = Column(Text, nullable=False)
    total = Column(Float, nullable=False)
    status = Column(String(50), default="confirmed")
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


# ── Pydantic Schemas ──────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str = "any"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    consumer: str
    plan: str


class ProductV1(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    category: str
    is_active: bool

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    product_ids: List[int]
    total: float


# ── DB Dependency ─────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── JWT Helpers ───────────────────────────────────────────────────────────
def create_jwt(username: str, plan: str) -> tuple:
    consumer_key = "premium-user-key" if plan == "premium" else "demo-user-key"
    payload = {
        "iss": consumer_key,
        "sub": username,
        "plan": plan,
        "jti": str(uuid.uuid4()),
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, consumer_key


def decode_jwt_header(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header with Bearer token required")
    try:
        return jwt.decode(authorization.split(" ", 1)[1], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")


def get_username(
    authorization: Optional[str] = Header(None),
    x_consumer_username: Optional[str] = Header(None),
) -> str:
    # Prefer JWT sub claim (actual username like "alice") over X-Consumer-Username
    # which is the Kong consumer tier name ("premium-user", "demo-user")
    if authorization and authorization.startswith("Bearer "):
        payload = decode_jwt_header(authorization)
        return payload.get("sub", "")
    if x_consumer_username:
        return x_consumer_username
    raise HTTPException(status_code=401, detail="No authentication provided")


# ── Seed Data ─────────────────────────────────────────────────────────────
SEED_PRODUCTS = [
    {"name": "Kong API Gateway", "description": "Enterprise-grade API gateway with plugin ecosystem", "price": 0.0, "category": "Gateway", "stock": 999, "rating": 4.9},
    {"name": "JWT Auth Module", "description": "JSON Web Token authentication and validation plugin", "price": 0.0, "category": "Security", "stock": 999, "rating": 4.8},
    {"name": "Rate Limiter Pro", "description": "Advanced rate limiting: per-IP, per-consumer, per-route", "price": 0.0, "category": "Traffic", "stock": 999, "rating": 4.7},
    {"name": "Request Transformer", "description": "Modify HTTP requests and responses on the fly", "price": 0.0, "category": "Transform", "stock": 999, "rating": 4.6},
    {"name": "Prometheus Metrics", "description": "Export Kong metrics to Prometheus for Grafana dashboards", "price": 0.0, "category": "Observability", "stock": 999, "rating": 4.8},
    {"name": "CORS Plugin", "description": "Cross-Origin Resource Sharing policy enforcement", "price": 0.0, "category": "Security", "stock": 999, "rating": 4.5},
    {"name": "OAuth2 Plugin", "description": "OAuth2 authorization code and client credentials flow", "price": 0.0, "category": "Security", "stock": 100, "rating": 4.7},
    {"name": "Response Caching", "description": "Cache upstream responses to reduce backend load", "price": 0.0, "category": "Performance", "stock": 999, "rating": 4.6},
    {"name": "IP Restriction", "description": "Whitelist or blacklist IPs and CIDR ranges", "price": 0.0, "category": "Security", "stock": 999, "rating": 4.4},
    {"name": "OpenTelemetry Plugin", "description": "Distributed tracing with OpenTelemetry standard", "price": 0.0, "category": "Observability", "stock": 999, "rating": 4.8},
    {"name": "Canary Release", "description": "Traffic splitting for gradual rollouts and A/B testing", "price": 0.0, "category": "Traffic", "stock": 50, "rating": 4.7},
    {"name": "Load Balancer", "description": "Round-robin and least-connections load balancing", "price": 0.0, "category": "Traffic", "stock": 999, "rating": 4.9},
]

SEED_USERS = [
    {"username": "alice", "email": "alice@demo.dev", "plan": "premium"},
    {"username": "bob", "email": "bob@demo.dev", "plan": "free"},
    {"username": "charlie", "email": "charlie@demo.dev", "plan": "free"},
    {"username": "diana", "email": "diana@demo.dev", "plan": "premium"},
]


def seed_data(db: Session):
    if db.query(ProductModel).count() == 0:
        for p in SEED_PRODUCTS:
            db.add(ProductModel(**p))
        db.commit()
    if db.query(UserModel).count() == 0:
        for u in SEED_USERS:
            db.add(UserModel(**u))
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()
    yield


# ── App ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title="GatewayHub API",
    description="Demo REST API protected by Kong Gateway — v1 (public) and v2 (JWT-protected)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit-minute", "X-RateLimit-Remaining-minute",
                    "X-Kong-Upstream-Latency", "X-Kong-Proxy-Latency",
                    "X-API-Version", "X-Request-ID"],
)


# ── Health ────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "healthy", "service": "api-service", "version": "1.0.0",
            "uptime_seconds": round(time.time() - metrics.start_time, 2)}


# ── Auth ──────────────────────────────────────────────────────────────────
@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.username == payload.username).first()
    if not user:
        metrics.auth_failures += 1
        raise HTTPException(
            status_code=401,
            detail=f"User '{payload.username}' not found. Available users: alice, bob, charlie, diana"
        )
    token, consumer_key = create_jwt(user.username, user.plan)
    metrics.record("/auth/login", 200)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=JWT_EXPIRY_HOURS * 3600,
        consumer=consumer_key,
        plan=user.plan,
    )


@app.get("/auth/validate")
def validate_token(authorization: Optional[str] = Header(None)):
    payload = decode_jwt_header(authorization)
    return {
        "valid": True,
        "subject": payload.get("sub"),
        "consumer": payload.get("iss"),
        "plan": payload.get("plan"),
        "issued_at": datetime.fromtimestamp(payload.get("iat", 0)).isoformat(),
        "expires_at": datetime.fromtimestamp(payload.get("exp", 0)).isoformat(),
        "token_id": payload.get("jti"),
    }


# ── API v1 — Public ───────────────────────────────────────────────────────
@app.get("/v1/products")
def list_products_v1(category: Optional[str] = Query(None), db: Session = Depends(get_db)):
    metrics.record("/v1/products", 200)
    query = db.query(ProductModel).filter(ProductModel.is_active == True)
    if category:
        query = query.filter(ProductModel.category == category)
    products = query.all()
    return [{"id": p.id, "name": p.name, "description": p.description,
             "price": p.price, "category": p.category, "is_active": p.is_active}
            for p in products]


@app.get("/v1/products/categories")
def list_categories_v1(db: Session = Depends(get_db)):
    rows = db.query(ProductModel.category).filter(ProductModel.is_active == True).distinct().all()
    return [r[0] for r in rows]


@app.get("/v1/products/{product_id}")
def get_product_v1(product_id: int, db: Session = Depends(get_db)):
    product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    metrics.record(f"/v1/products/{product_id}", 200)
    return {"id": product.id, "name": product.name, "description": product.description,
            "price": product.price, "category": product.category, "is_active": product.is_active}


# ── API v1 — Protected (JWT required) ────────────────────────────────────
@app.get("/v1/users/me")
def get_current_user_v1(username: str = Depends(get_username), db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    metrics.record("/v1/users/me", 200)
    return {"id": user.id, "username": user.username, "email": user.email, "plan": user.plan}


@app.post("/v1/orders", status_code=201)
def create_order_v1(
    payload: OrderCreate,
    username: str = Depends(get_username),
    db: Session = Depends(get_db),
):
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    order = OrderModel(
        user_id=user.id,
        product_ids=json.dumps(payload.product_ids),
        total=payload.total,
        status="confirmed",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    metrics.record("/v1/orders", 201)
    return {"id": order.id, "status": order.status, "total": order.total,
            "message": "Order created successfully", "user": username}


@app.get("/v1/orders")
def list_orders_v1(username: str = Depends(get_username), db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    orders = db.query(OrderModel).filter(OrderModel.user_id == user.id).all()
    metrics.record("/v1/orders", 200)
    return [{"id": o.id, "total": o.total, "status": o.status,
             "product_ids": json.loads(o.product_ids),
             "created_at": o.created_at.isoformat()} for o in orders]


# ── API v2 — Enhanced (JWT required) ─────────────────────────────────────
@app.get("/v2/products")
def list_products_v2(
    category: Optional[str] = Query(None),
    username: str = Depends(get_username),
    db: Session = Depends(get_db),
):
    query = db.query(ProductModel).filter(ProductModel.is_active == True)
    if category:
        query = query.filter(ProductModel.category == category)
    products = query.all()
    metrics.record("/v2/products", 200)
    return {
        "data": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "price": p.price,
                "category": p.category,
                "stock": p.stock,
                "rating": p.rating,
                "is_active": p.is_active,
                "metadata": {
                    "availability": "in_stock" if p.stock > 0 else "out_of_stock",
                    "popularity_score": round(p.rating * min(p.stock, 100) / 100, 2),
                    "free_shipping": p.price == 0.0,
                    "tags": [p.category.lower(), "kong-plugin"],
                },
            }
            for p in products
        ],
        "total": len(products),
        "api_version": "2.0",
        "enhancements": ["stock_info", "ratings", "metadata", "availability_status"],
        "requested_by": username,
    }


@app.get("/v2/users/me")
def get_current_user_v2(username: str = Depends(get_username), db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    order_count = db.query(OrderModel).filter(OrderModel.user_id == user.id).count()
    metrics.record("/v2/users/me", 200)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "plan": user.plan,
        "stats": {
            "total_orders": order_count,
            "member_since": user.created_at.isoformat(),
            "api_access": "v1 + v2 (enhanced)" if user.plan == "premium" else "v1 only",
            "rate_limit": "60 req/min" if user.plan == "premium" else "30 req/min",
        },
        "api_version": "2.0",
    }


@app.get("/v2/metrics")
def service_metrics():
    uptime = time.time() - metrics.start_time
    total_requests = sum(d["total"] for d in metrics.endpoints.values())
    total_errors = sum(d["errors"] for d in metrics.endpoints.values())
    return {
        "uptime_seconds": round(uptime, 2),
        "total_requests": total_requests,
        "total_errors": total_errors,
        "error_rate": round(total_errors / max(total_requests, 1) * 100, 2),
        "rate_limit_hits": metrics.rate_limit_hits,
        "auth_failures": metrics.auth_failures,
        "endpoints": {
            ep: {
                "total": d["total"],
                "errors": d["errors"],
                "avg_latency_ms": round(d["total_latency"] / max(d["total"], 1), 2),
            }
            for ep, d in metrics.endpoints.items()
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
