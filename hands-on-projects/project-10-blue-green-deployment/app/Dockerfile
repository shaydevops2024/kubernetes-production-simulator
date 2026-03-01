FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENV APP_COLOR=blue \
    APP_VERSION=v1 \
    APP_ENV=production \
    PORT=5000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
