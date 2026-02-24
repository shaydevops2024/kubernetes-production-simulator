import os
import time
import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

KONG_ADMIN_URL = os.getenv("KONG_ADMIN_URL", "http://kong:8001")
API_SERVICE_URL = os.getenv("API_SERVICE_URL", "http://api-service:8001")
PORT = int(os.getenv("PORT", "8002"))

# In-memory cache
cache = {
    "kong_services": [],
    "kong_routes": [],
    "kong_plugins": [],
    "kong_consumers": [],
    "kong_status": {},
    "api_metrics": {},
    "kong_available": False,
    "last_updated": 0,
}


async def fetch_all():
    async with httpx.AsyncClient(timeout=5.0) as client:
        for endpoint, key in [
            ("/services", "kong_services"),
            ("/routes", "kong_routes"),
            ("/plugins", "kong_plugins"),
            ("/consumers", "kong_consumers"),
        ]:
            try:
                resp = await client.get(f"{KONG_ADMIN_URL}{endpoint}")
                if resp.status_code == 200:
                    cache[key] = resp.json().get("data", [])
                    cache["kong_available"] = True
            except Exception:
                cache["kong_available"] = False

        try:
            resp = await client.get(f"{KONG_ADMIN_URL}/status")
            if resp.status_code == 200:
                cache["kong_status"] = resp.json()
        except Exception:
            pass

        try:
            resp = await client.get(
                f"{API_SERVICE_URL}/v2/metrics",
                headers={"X-Consumer-Username": "analytics"},
            )
            if resp.status_code == 200:
                cache["api_metrics"] = resp.json()
        except Exception:
            pass

    cache["last_updated"] = time.time()


async def background_refresh():
    while True:
        await fetch_all()
        await asyncio.sleep(10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await fetch_all()
    task = asyncio.create_task(background_refresh())
    yield
    task.cancel()


app = FastAPI(title="Analytics Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "analytics-service",
        "kong_available": cache["kong_available"],
    }


@app.get("/analytics/stats")
def get_stats():
    server = cache.get("kong_status", {}).get("server", {})
    api = cache.get("api_metrics", {})
    return {
        "kong": {
            "available": cache["kong_available"],
            "services_count": len(cache["kong_services"]),
            "routes_count": len(cache["kong_routes"]),
            "plugins_count": len(cache["kong_plugins"]),
            "consumers_count": len(cache["kong_consumers"]),
            "connections_active": server.get("connections_active", 0),
            "connections_handled": server.get("connections_handled", 0),
            "total_requests": server.get("total_requests", 0),
        },
        "api_service": {
            "total_requests": api.get("total_requests", 0),
            "total_errors": api.get("total_errors", 0),
            "error_rate": api.get("error_rate", 0),
            "rate_limit_hits": api.get("rate_limit_hits", 0),
            "auth_failures": api.get("auth_failures", 0),
            "uptime_seconds": api.get("uptime_seconds", 0),
            "endpoints": api.get("endpoints", {}),
        },
        "last_updated": cache["last_updated"],
    }


@app.get("/analytics/routes")
def get_routes():
    return {
        "routes": [
            {
                "id": r.get("id", ""),
                "name": r.get("name", ""),
                "paths": r.get("paths", []),
                "methods": r.get("methods", []),
                "plugins": r.get("plugins", []),
            }
            for r in cache["kong_routes"]
        ],
        "total": len(cache["kong_routes"]),
    }


@app.get("/analytics/services")
def get_services():
    return {
        "services": [
            {
                "id": s.get("id", ""),
                "name": s.get("name", ""),
                "host": s.get("host", ""),
                "port": s.get("port", 80),
                "protocol": s.get("protocol", "http"),
                "path": s.get("path", "/"),
                "retries": s.get("retries", 5),
                "connect_timeout": s.get("connect_timeout", 60000),
            }
            for s in cache["kong_services"]
        ],
        "total": len(cache["kong_services"]),
    }


@app.get("/analytics/plugins")
def get_plugins():
    return {
        "plugins": [
            {
                "id": p.get("id", ""),
                "name": p.get("name", ""),
                "enabled": p.get("enabled", True),
                "scope": (
                    "route"
                    if p.get("route")
                    else "service"
                    if p.get("service")
                    else "global"
                ),
            }
            for p in cache["kong_plugins"]
        ],
        "total": len(cache["kong_plugins"]),
    }


@app.get("/analytics/consumers")
def get_consumers():
    return {
        "consumers": [
            {
                "id": c.get("id", ""),
                "username": c.get("username", ""),
                "created_at": c.get("created_at", 0),
            }
            for c in cache["kong_consumers"]
        ],
        "total": len(cache["kong_consumers"]),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
