FROM python:3.12-slim

# WeasyPrint's native dependencies (Pango, Cairo, GDK-Pixbuf, fonts). This is
# the most common deploy break in the whole build: WeasyPrint imports fine
# after `pip install` but raises OSError at runtime without these.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    shared-mime-info \
    fonts-liberation \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Run as an unprivileged user. The fastembed cache below must live under
# this user's home so the baked model is readable at runtime.
RUN useradd --create-home --shell /usr/sbin/nologin app
ENV HOME=/home/app \
    FASTEMBED_CACHE_PATH=/home/app/fastembed_cache

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the fastembed ONNX model into the image at build time. Without this,
# the first request after every cold start pays a ~130 MB download, and on a
# 512 MB instance it can OOM instead of just being slow.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')" \
    && chown -R app:app /home/app

COPY --chown=app:app . .

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
