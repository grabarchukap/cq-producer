FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data

WORKDIR /app

# Dependencies first — this layer is cached until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user; /data must be writable by this uid on the host
RUN useradd --uid 1000 --create-home appuser && mkdir -p /data && chown appuser /data
USER appuser

CMD ["python", "main.py"]
