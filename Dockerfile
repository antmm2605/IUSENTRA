# ============================================================
#  Studio Legale PCT — Dockerfile produzione
#  Build:  docker build -t studio-legale-pct .
#  Run:    docker run -p 8080:8080 -v pct-data:/data studio-legale-pct
# ============================================================

FROM python:3.12-slim

# Dipendenze di sistema minime (reportlab + cryptography le richiedono)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        tesseract-ocr \
        tesseract-ocr-ita \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia prima solo i file di dipendenze per sfruttare la cache Docker
COPY setup.py .
COPY pct/__init__.py pct/__init__.py
RUN pip install --no-cache-dir -e ".[pdf]" gunicorn gevent

# Copia il resto del codice
COPY . .

# ---- Dati persistenti: tutti i file runtime puntano a /data ----
# Su Railway/Render monta un volume su /data
# In locale:  docker run -v $(pwd)/data:/data ...
ENV PCT_AGENDA_DB=/data/agenda/appuntamenti.json \
    PCT_CLIENTI_DB=/data/clienti/anagrafica.json \
    PCT_CONDIVISIONI_DB=/data/clienti/condivisioni.json \
    PCT_FASCICOLI_DB=/data/fascicoli/fascicoli.json \
    PCT_FASCICOLI_DOCS=/data/fascicoli/documenti \
    PCT_FASCICOLI_ARCH=/data/fascicoli/archivio \
    PCT_MESSAGGI_DB=/data/messaggi/storico.json \
    PCT_BACKUP_DIR=/data/backup \
    PCT_AUTH_DB=/data/auth/utenti.json \
    PCT_AUDIT_DB=/data/auth/audit.json \
    PCT_SCADENZIARIO_DB=/data/scadenziario/scadenze.json \
    PCT_SEARCH_INDEX=/data/search/index.db \
    PCT_PRIVACY_DB=/data/privacy/registro.json \
    PCT_PORTALE_DB=/data/portale/portali.json \
    PCT_PORTALE_UPLOADS=/data/portale/uploads \
    PCT_FATTURAZIONE_DB=/data/fatturazione/parcelle.json \
    PCT_NOTIFICHE_LOG=/data/notifiche/log.json \
    PCT_TEMPLATE_ATTI_DB=/data/template_atti/templates.json \
    PCT_PAGAMENTI_DIR=/data/pagamenti \
    PCT_TENANTS_REGISTRY=/data/tenants.json \
    PCT_MULTI_TENANT=1 \
    PCT_HTTPS=true \
    PCT_STUDIO_NOME="HACS - Studio Legale PCT"

# PCT_SECRET_KEY e PCT_DOC_KEY vanno impostati come variabili d'ambiente
# nel pannello Railway/Render — NON metterle nel Dockerfile!

RUN mkdir -p /data

EXPOSE 8080

# Gunicorn: worker gevent per SSE/long-polling, timeout 120s per PDF/ZIP grandi
CMD gunicorn \
    --bind "0.0.0.0:${PORT:-8080}" \
    --worker-class gevent \
    --workers 2 \
    --worker-connections 100 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    wsgi:app
