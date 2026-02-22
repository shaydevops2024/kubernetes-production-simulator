import os
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8001")
PORT = int(os.getenv("PORT", "8002"))

# In-memory store: { user_id: { product_id: { quantity, product_snapshot } } }
carts: Dict[str, Dict[int, dict]] = {}


# --- Schemas ---

class AddItemRequest(BaseModel):
    product_id: int
    quantity: int = 1


class CartItem(BaseModel):
    product_id: int
    name: str
    price: float
    quantity: int
    subtotal: float
    image_url: Optional[str] = None


class Cart(BaseModel):
    user_id: str
    items: List[CartItem]
    total: float
    item_count: int


# --- App ---

app = FastAPI(
    title="Cart Service",
    description="Shopping cart service — manages items in user carts",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Helpers ---

def build_cart_response(user_id: str) -> Cart:
    user_cart = carts.get(user_id, {})
    items = []
    for product_id, entry in user_cart.items():
        items.append(CartItem(
            product_id=product_id,
            name=entry["name"],
            price=entry["price"],
            quantity=entry["quantity"],
            subtotal=round(entry["price"] * entry["quantity"], 2),
            image_url=entry.get("image_url"),
        ))
    total = round(sum(i.subtotal for i in items), 2)
    return Cart(user_id=user_id, items=items, total=total, item_count=sum(i.quantity for i in items))


async def fetch_product(product_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{PRODUCT_SERVICE_URL}/products/{product_id}")
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Product service unavailable")


# --- Routes ---

@app.get("/health")
def health():
    return {"status": "healthy", "service": "cart-service"}


@app.get("/cart/{user_id}", response_model=Cart)
def get_cart(user_id: str):
    return build_cart_response(user_id)


@app.post("/cart/{user_id}/items", response_model=Cart)
async def add_item(user_id: str, payload: AddItemRequest):
    if payload.quantity < 1:
        raise HTTPException(status_code=400, detail="Quantity must be at least 1")

    product = await fetch_product(payload.product_id)

    if user_id not in carts:
        carts[user_id] = {}

    user_cart = carts[user_id]
    if payload.product_id in user_cart:
        user_cart[payload.product_id]["quantity"] += payload.quantity
    else:
        user_cart[payload.product_id] = {
            "name": product["name"],
            "price": product["price"],
            "quantity": payload.quantity,
            "image_url": product.get("image_url"),
        }

    return build_cart_response(user_id)


@app.delete("/cart/{user_id}/items/{product_id}", response_model=Cart)
def remove_item(user_id: str, product_id: int):
    user_cart = carts.get(user_id, {})
    if product_id not in user_cart:
        raise HTTPException(status_code=404, detail="Item not in cart")
    del user_cart[product_id]
    return build_cart_response(user_id)


@app.delete("/cart/{user_id}", status_code=204)
def clear_cart(user_id: str):
    carts.pop(user_id, None)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
