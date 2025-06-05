FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

CMD ["gunicorn", "main:app", "--workers", "4", "--preload", "--timeout", "120", "--bind", "0.0.0.0:8080", "--worker-class", "uvicorn.workers.UvicornWorker", "--keyfile", "/app/certs/privkey.pem", "--certfile", "/app/certs/fullchain.pem"]
