# app/Dockerfile
# Fixed version - installs dependencies correctly

FROM python:3.11-slim

WORKDIR /app

# Copy requirements first
COPY requirements.txt .

# Install dependencies BEFORE switching user
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/main.py .

# Create non-root user (AFTER installing packages)
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

EXPOSE 8000

# Run with unbuffered output
CMD ["python", "-u", "main.py"]