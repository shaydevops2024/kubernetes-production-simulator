import time
import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Function Service", description="FaaS Function Registry & Invoker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FUNCTION_RUNNER_URL = os.getenv("FUNCTION_RUNNER_URL", "http://localhost:8002")

# In-memory function registry
FUNCTIONS = {
    "hello-world": {
        "name": "hello-world",
        "description": "Returns a greeting message for a given name. The simplest possible function — perfect for understanding the invocation flow.",
        "trigger": "HTTP",
        "runtime": "python3.11",
        "timeout_s": 5,
        "memory": "64Mi",
        "invocations": 0,
        "avg_latency_ms": 0.0,
        "status": "ready",
        "example_payload": {"name": "DevOps Engineer"},
    },
    "fibonacci": {
        "name": "fibonacci",
        "description": "Computes the Nth Fibonacci number. CPU-intensive at high N — ideal for auto-scaling and cold-start demos.",
        "trigger": "HTTP",
        "runtime": "python3.11",
        "timeout_s": 30,
        "memory": "128Mi",
        "invocations": 0,
        "avg_latency_ms": 0.0,
        "status": "ready",
        "example_payload": {"n": 35},
    },
    "text-processor": {
        "name": "text-processor",
        "description": "Analyzes a block of text: word count, character count, sentence count, reading time, sentiment, and unique word ratio.",
        "trigger": "HTTP",
        "runtime": "python3.11",
        "timeout_s": 10,
        "memory": "64Mi",
        "invocations": 0,
        "avg_latency_ms": 0.0,
        "status": "ready",
        "example_payload": {"text": "Kubernetes is an amazing platform for running containerized workloads at scale."},
    },
    "image-info": {
        "name": "image-info",
        "description": "Returns metadata about an image at a given URL: format, dimensions, estimated file size. Simulates an async media processing function.",
        "trigger": "HTTP",
        "runtime": "python3.11",
        "timeout_s": 15,
        "memory": "128Mi",
        "invocations": 0,
        "avg_latency_ms": 0.0,
        "status": "ready",
        "example_payload": {"url": "https://example.com/photo.jpg"},
    },
    "weather-report": {
        "name": "weather-report",
        "description": "Returns a weather report for a city with 3-day forecast. Simulates a Cron-triggered data aggregation function that calls an external API.",
        "trigger": "HTTP / Cron",
        "runtime": "python3.11",
        "timeout_s": 10,
        "memory": "64Mi",
        "invocations": 0,
        "avg_latency_ms": 0.0,
        "status": "ready",
        "example_payload": {"city": "Tel Aviv"},
    },
}


class InvokeRequest(BaseModel):
    payload: Optional[dict] = {}


@app.get("/health")
def health():
    return {"status": "healthy", "service": "function-service"}


@app.get("/functions")
def list_functions():
    return {"functions": list(FUNCTIONS.values()), "total": len(FUNCTIONS)}


@app.get("/functions/{name}")
def get_function(name: str):
    if name not in FUNCTIONS:
        raise HTTPException(status_code=404, detail=f"Function '{name}' not found")
    return FUNCTIONS[name]


@app.post("/functions/{name}/invoke")
async def invoke_function(name: str, req: InvokeRequest):
    if name not in FUNCTIONS:
        raise HTTPException(status_code=404, detail=f"Function '{name}' not found")

    start = time.time()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{FUNCTION_RUNNER_URL}/run/{name}",
                json={"payload": req.payload or {}},
                timeout=35.0,
            )
            response.raise_for_status()

        latency_ms = (time.time() - start) * 1000
        fn = FUNCTIONS[name]
        fn["invocations"] += 1
        prev_avg = fn["avg_latency_ms"]
        n = fn["invocations"]
        fn["avg_latency_ms"] = round((prev_avg * (n - 1) + latency_ms) / n, 2)

        return {
            "function": name,
            "result": response.json(),
            "latency_ms": round(latency_ms, 2),
            "invocations_total": fn["invocations"],
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Runner returned error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Cannot reach function runner: {str(e)}")


@app.get("/stats")
def get_stats():
    total_invocations = sum(f["invocations"] for f in FUNCTIONS.values())
    return {
        "total_functions": len(FUNCTIONS),
        "total_invocations": total_invocations,
        "functions": [
            {
                "name": f["name"],
                "invocations": f["invocations"],
                "avg_latency_ms": f["avg_latency_ms"],
            }
            for f in FUNCTIONS.values()
        ],
    }
