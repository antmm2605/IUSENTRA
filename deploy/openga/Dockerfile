# Motore opzionale separato dal runtime bloccato del gestionale.
FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
WORKDIR /app
COPY deploy/openga/runtime-lock.txt /runtime-lock.txt
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r /runtime-lock.txt
COPY pct ./pct
COPY lex ./lex
COPY scripts ./scripts
COPY deploy/openga/server.py ./server.py
ENV PYTHONPATH=/app OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
ENV IUSENTRA_OPENGA_CATALOGO_DB=/catalogo/catalogo.db IUSENTRA_OPENGA_RERANKER_DIR=/modello
USER 65534:65534
EXPOSE 8092
CMD ["python", "server.py"]
