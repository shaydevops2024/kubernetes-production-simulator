import time
import random
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Function Runner", description="FaaS Function Executor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    payload: Optional[dict] = {}


# ── Function handlers ──────────────────────────────────────────────────────────

def fn_hello_world(payload: dict) -> dict:
    name = payload.get("name", "World")
    return {
        "message": f"Hello, {name}!",
        "timestamp": time.time(),
        "version": "1.0.0",
    }


def fn_fibonacci(payload: dict) -> dict:
    n = int(payload.get("n", 10))
    if n < 0 or n > 40:
        raise ValueError("n must be between 0 and 40")

    start = time.perf_counter()
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    result = b if n > 0 else 0
    elapsed_ms = (time.perf_counter() - start) * 1000

    return {
        "input_n": n,
        "result": result,
        "compute_ms": round(elapsed_ms, 4),
        "note": "Try n=40 to see CPU load for the scaling demo",
    }


def fn_text_processor(payload: dict) -> dict:
    text = payload.get("text", "Hello, World!")
    if not text.strip():
        raise ValueError("text payload cannot be empty")

    words = text.split()
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]

    positive_words = {"good", "great", "excellent", "happy", "love", "wonderful", "best", "amazing", "awesome", "fantastic"}
    negative_words = {"bad", "terrible", "awful", "hate", "worst", "horrible", "poor", "dreadful", "useless"}

    lower_words = [w.lower().strip(".,!?;:\"'") for w in words]
    pos_count = sum(1 for w in lower_words if w in positive_words)
    neg_count = sum(1 for w in lower_words if w in negative_words)

    if pos_count > neg_count:
        sentiment = "positive"
    elif neg_count > pos_count:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    unique_words = set(lower_words)
    word_count = len(words)

    return {
        "word_count": word_count,
        "character_count": len(text),
        "character_count_no_spaces": len(text.replace(" ", "")),
        "sentence_count": len(sentences),
        "unique_words": len(unique_words),
        "lexical_diversity": round(len(unique_words) / word_count, 2) if word_count > 0 else 0,
        "reading_time_seconds": round(word_count / 3, 1),
        "sentiment": sentiment,
        "sentiment_scores": {"positive": pos_count, "negative": neg_count},
    }


def fn_image_info(payload: dict) -> dict:
    url = payload.get("url", "https://example.com/image.jpg")
    formats = ["JPEG", "PNG", "WebP", "GIF", "AVIF"]
    widths = [320, 640, 800, 1024, 1280, 1920, 3840]

    # Deterministic-ish result based on URL length so repeated calls look consistent
    seed = len(url)
    random.seed(seed)
    fmt = random.choice(formats)
    width = random.choice(widths)
    height = int(width * random.uniform(0.5, 1.8))
    quality_factor = random.uniform(5, 20)
    estimated_kb = round((width * height * 3) / 1024 / quality_factor, 1)

    return {
        "url": url,
        "format": fmt,
        "width_px": width,
        "height_px": height,
        "megapixels": round((width * height) / 1_000_000, 2),
        "aspect_ratio": f"{width}x{height}",
        "estimated_size_kb": estimated_kb,
        "color_space": "sRGB",
        "note": "Mock response — simulates async media-processing function",
    }


def fn_weather_report(payload: dict) -> dict:
    city = payload.get("city", "New York")
    conditions = ["Sunny", "Cloudy", "Rainy", "Partly Cloudy", "Thunderstorm", "Snowy", "Foggy", "Windy"]

    random.seed(len(city) + int(time.time() / 3600))  # changes every hour
    temp_c = round(random.uniform(-5, 40), 1)
    temp_f = round(temp_c * 9 / 5 + 32, 1)

    return {
        "city": city,
        "temperature_c": temp_c,
        "temperature_f": temp_f,
        "condition": random.choice(conditions),
        "humidity_percent": random.randint(20, 95),
        "wind_speed_kmh": round(random.uniform(0, 80), 1),
        "uv_index": random.randint(0, 11),
        "forecast": [
            {
                "day": "Tomorrow",
                "condition": random.choice(conditions),
                "high_c": round(temp_c + random.uniform(-3, 3), 1),
                "low_c": round(temp_c - random.uniform(3, 10), 1),
            },
            {
                "day": "Day 2",
                "condition": random.choice(conditions),
                "high_c": round(temp_c + random.uniform(-5, 5), 1),
                "low_c": round(temp_c - random.uniform(3, 10), 1),
            },
            {
                "day": "Day 3",
                "condition": random.choice(conditions),
                "high_c": round(temp_c + random.uniform(-5, 5), 1),
                "low_c": round(temp_c - random.uniform(3, 10), 1),
            },
        ],
        "note": "Mock data — simulates a Cron-triggered weather aggregation function",
    }


# ── Router ─────────────────────────────────────────────────────────────────────

FUNCTION_MAP = {
    "hello-world": fn_hello_world,
    "fibonacci": fn_fibonacci,
    "text-processor": fn_text_processor,
    "image-info": fn_image_info,
    "weather-report": fn_weather_report,
}


@app.get("/health")
def health():
    return {"status": "healthy", "service": "function-runner", "functions": list(FUNCTION_MAP.keys())}


@app.get("/functions")
def list_available():
    return {"available": list(FUNCTION_MAP.keys())}


@app.post("/run/{name}")
def run_function(name: str, req: RunRequest):
    if name not in FUNCTION_MAP:
        raise HTTPException(status_code=404, detail=f"No handler registered for function '{name}'")
    try:
        result = FUNCTION_MAP[name](req.payload or {})
        return {"status": "success", "output": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Function execution failed: {str(e)}")
