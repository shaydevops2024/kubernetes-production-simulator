# app/Dockerfile
# Multi-stage build for Python FastAPI application with baked-in scenarios
# FIXED: Proper paths for app/src/ structure

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages to /usr/local (system-wide)
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies (curl for healthcheck, wget for downloading CLIs)
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Helm CLI
RUN curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install ArgoCD CLI
RUN curl -sSL -o /usr/local/bin/argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64 \
    && chmod +x /usr/local/bin/argocd

# Copy Python packages from builder (system-wide installation)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
# Your structure: app/src/database.py, app/src/main.py, app/src/static/
COPY app/src/ /app/src/

# CRITICAL: Copy scenarios into the image at /scenarios
# This happens BEFORE we create the user, so it's done as root
COPY k8s-scenarios/ /scenarios/

# Copy ArgoCD scenarios into the image
COPY argocd-scenarios/ /argocd-scenarios/

# Copy Helm scenarios into the image
COPY helm-scenarios/ /helm-scenarios/

# Copy GitLab CI scenarios into the image
COPY gitlab-ci-scenarios/ /gitlab-ci-scenarios/

# Now create non-root user and set ownership
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /scenarios && \
    chmod -R 755 /scenarios && \
    chown -R appuser:appuser /argocd-scenarios && \
    chmod -R 755 /argocd-scenarios && \
    chown -R appuser:appuser /helm-scenarios && \
    chmod -R 755 /helm-scenarios && \
    chown -R appuser:appuser /gitlab-ci-scenarios && \
    chmod -R 755 /gitlab-ci-scenarios

# Switch to non-root user
USER appuser

# Set Python path so imports work correctly
# This allows "from database import" to find /app/src/database.py
ENV PYTHONPATH=/app/src

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application from /app/src directory
# This way "from database import" works
WORKDIR /app/src
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
