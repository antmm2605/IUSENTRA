FROM python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 \
    TOKENIZERS_PARALLELISM=false IUSENTRA_EMBEDDING_BIND=0.0.0.0 \
    IUSENTRA_EMBEDDING_MODEL_DIR=/models/model
WORKDIR /srv
RUN pip install --no-cache-dir torch==2.14.1 torchvision==0.29.1 \
      --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir transformers==5.19.0 \
      sentence-transformers==6.1.0 pillow==12.3.0 numpy==2.5.3
COPY pct/__init__.py pct/embeddinggemma2.py ./pct/
COPY deploy/embeddinggemma2/server.py ./server.py
COPY deploy/embeddinggemma2/model-manifest.json ./model-manifest.json
COPY deploy/embeddinggemma2/provision.py ./provision.py
USER 65534:65534
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:11140/health',timeout=3)"
CMD ["python", "server.py"]
