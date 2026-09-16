FROM python:3.12-slim

# WeasyPrint's native dependencies (Pango, Cairo, GDK-Pixbuf, fonts). This is
# the most common deploy break in the whole build: WeasyPrint imports fine
# after `pip install` but raises OSError at runtime without these.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libcairo2 \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the fastembed ONNX model into the image at build time. Without this,
# the first request after every cold start pays a ~130 MB download, and on a
# 512 MB instance it can OOM instead of just being slow.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
