# ============================================================
#  Studio Legale PCT — Dockerfile produzione (versione integrale)
#
#  Build multi-stage:
#    Stage 1 (builder)  – compila le dipendenze Python con gcc
#    Stage 2 (runtime)  – immagine finale snella, senza build tools
#
#  Build:  docker build -t hacs .
#  Run:    docker run -p 8080:8080 -v hacs-data:/data hacs
# ============================================================


# ─────────────────────────────────────────────────────────────
#  Stage 1 — builder: compila tutte le dipendenze Python
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Dipendenze di build (rimangono solo in questo stage)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libxml2-dev \
        libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Crea un venv isolato → tutto finisce in /venv
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Layer cache: ricalcola solo se setup.py cambia
COPY setup.py .
COPY pct/__init__.py pct/__init__.py
RUN pip install --no-cache-dir ".[pdf,pades]" "gunicorn>=23.0.0,<24" "gevent>=24.2.0,<25"


# ─────────────────────────────────────────────────────────────
#  Stage 2 — sass: scarica dart-sass e compila gli SCSS → CSS
#  (nessun Node.js richiesto: dart-sass è un eseguibile standalone)
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS sass-builder

ARG DART_SASS_VERSION=1.83.0

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && curl -fsSL \
       "https://github.com/sass/dart-sass/releases/download/${DART_SASS_VERSION}/dart-sass-${DART_SASS_VERSION}-linux-x64.tar.gz" \
       | tar -xzC /tmp \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /scss
COPY web/static/scss .

RUN mkdir -p /out && /tmp/dart-sass/sass --no-source-map --style=compressed \
      app.scss:/out/app.css \
      design-system.scss:/out/design-system.css \
      editor-word.scss:/out/editor-word.css \
      mobile.scss:/out/mobile.css


# ─────────────────────────────────────────────────────────────
#  Stage 3 — runtime: immagine finale senza gcc né librerie -dev
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.title="HACS - Studio Legale PCT" \
      org.opencontainers.image.version="2.34.5" \
      org.opencontainers.image.description="Gestionale PCT per studi legali italiani" \
      org.opencontainers.image.created="2026-03-18"

# Solo le librerie runtime strettamente necessarie
RUN apt-get update && apt-get install -y --no-install-recommends \
        libffi8 \
        libxml2 \
        libxslt1.1 \
        tesseract-ocr \
        tesseract-ocr-ita \
        poppler-utils \
        libjpeg62-turbo \
        libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

# Copia il venv compilato dallo stage builder
COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"

WORKDIR /app

# Copia tutto il sorgente (templates, static, blueprints, ecc.)
COPY . .

# Sovrascrive i CSS con quelli compilati da SCSS (dart-sass, stage sass-builder)
COPY --from=sass-builder /out/ web/static/css/

# PYTHONPATH → pct/ e web/ vengono importati dal sorgente in /app
# (le dipendenze esterne arrivano dal /venv)
ENV PYTHONPATH=/app

# ---- Dati persistenti: tutti i file runtime puntano a /data ----
# Su Railway/Render monta un volume su /data
# In locale:  docker run -v $(pwd)/data:/data ... oppure usa docker-compose
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
    PCT_UFFICI_DB=/data/uffici/uffici_giudiziari.json \
    PCT_UFFICI_TTL_GIORNI=7 \
    PCT_TENANTS_REGISTRY=/data/tenants.json \
    PCT_STUDIO_CONFIG=/data/config/studio.json \
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

