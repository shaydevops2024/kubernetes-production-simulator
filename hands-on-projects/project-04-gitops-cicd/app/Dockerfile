FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY static/ static/

EXPOSE 8080

# Build-time args injected into env vars (set by CI pipeline)
ARG APP_VERSION=v1
ARG BUILD_DATE=unknown
ARG GIT_COMMIT=unknown

ENV APP_VERSION=$APP_VERSION
ENV BUILD_DATE=$BUILD_DATE
ENV GIT_COMMIT=$GIT_COMMIT

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
