FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# APP_VERSION and APP_COLOR are injected at runtime (not build time)
# so the same image can run as v1 (blue) or v2 (green)
ENV APP_PORT=4545

EXPOSE 4545

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:4545/health')"

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4545"]
