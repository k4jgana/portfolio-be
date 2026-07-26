FROM python:3.10-slim

WORKDIR /app

# Install only essential build tools, then remove afterwards
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

# Replace with your preferred low-resource Gunicorn config if needed
EXPOSE 8000
CMD ["gunicorn", "--workers=1", "-k", "uvicorn.workers.UvicornWorker", "app:app", "--bind", "0.0.0.0:8000"]
