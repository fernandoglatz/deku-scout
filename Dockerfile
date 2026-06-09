FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY wsgi.py .

RUN useradd -m appuser && mkdir -p /data && chown appuser:appuser /data
USER appuser

ENV DB_FILE=/data/session.db
ENV ICONS_DIR=/data/icons

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "--timeout", "120", "wsgi:app"]
