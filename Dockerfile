#  version: 2.220.0
#  IUSENTRA | Dockerfile produzione

#  Build multi-stage:
#    Stage 1 (builder) - compila le dipendenze Python con gcc
#    Stage 2 (runtime) - immagine finale snella, senza build tools
#
#  Build:  docker build -t iusentra .
#  Run:    docker run -p 8080:8080 -v iusentra-data:/data iusentra



# -------------------------------------------------------------
#  Stage 1 - builder: compila tutte le dipendenze Python
# -------------------------------------------------------------
FROM python:3.12-slim AS builder

# Dipendenze di build (rimangono solo in questo stage)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libxml2-dev \
        libxslt1-dev \
        libpcsclite-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Crea un venv isolato -> tutto finisce in /venv
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Layer cache: ricalcola solo se cambiano manifest o requirements
COPY setup.py .
COPY pyproject.toml .
COPY packaging_manifest.py .
COPY requirements ./requirements
COPY pct/__init__.py pct/__init__.py
RUN pip install --no-cache-dir --timeout 120 ".[pdf,pades,pkcs11]" "gunicorn>=23.0.0,<24" "gevent>=24.2.0,<25"


# -------------------------------------------------------------
#  Stage 2 - sass: scarica dart-sass e compila gli SCSS -> CSS
#  (nessun Node.js richiesto: dart-sass e un eseguibile standalone)
# -------------------------------------------------------------
FROM debian:bookworm-slim AS sass-builder

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
      auth.scss:/out/auth.css \
      design-system.scss:/out/design-system.css \
      editor-word.scss:/out/editor-word.css \
      mobile.scss:/out/mobile.css \
      portal.scss:/out/portal.css \
      studio_site_public.scss:/out/studio_site_public.css \
      theme.scss:/out/theme.css


# -------------------------------------------------------------
#  Stage 3 - runtime: immagine finale senza gcc ne librerie -dev
# -------------------------------------------------------------
FROM python:3.12-slim

LABEL org.opencontainers.image.title="IUSENTRA" \
      org.opencontainers.image.version="2.220.0" \
      org.opencontainers.image.description="Gestionale PCT per studi legali italiani" \
      org.opencontainers.image.created="2026-03-18"

# Solo le librerie runtime strettamente necessarie
# libpcsclite1 + opensc: firma PKCS#11 in-device (Aruba Key) - il demone pcscd
# gira sul HOST; il container lo raggiunge via socket montato in docker-compose
RUN apt-get update && apt-get install -y --no-install-recommends \
        libffi8 \
        libxml2 \
        libxslt1.1 \
        tesseract-ocr \
        tesseract-ocr-ita \
        poppler-utils \
        ghostscript \
        libjpeg62-turbo \
        libpng16-16 \
        libpcsclite1 \
        opensc \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system iusentra \
    && adduser --system --ingroup iusentra --home /nonexistent --no-create-home iusentra

# Copia il venv compilato dallo stage builder
COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copia tutto il sorgente (templates, static, blueprints, ecc.)
COPY . .
# Overlay esplicito dei moduli applicativi caldi: su Windows evita che
# rebuild apparentemente riusciti restino ancorati a sorgenti stale nel layer finale.
COPY pct /app/pct
COPY pct/__init__.py /app/pct/__init__.py
COPY web /app/web
COPY lex /app/lex
COPY docker/entrypoint.py /usr/local/bin/iusentra-entrypoint.py
RUN find /app -type d -name '__pycache__' -prune -exec rm -rf {} + \
    && find /app -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

# Sovrascrive i CSS con quelli compilati da SCSS (dart-sass, stage sass-builder)
COPY --from=sass-builder /out/ web/static/css/

# PYTHONPATH -> pct/ e web/ vengono importati dal sorgente in /app
# (le dipendenze esterne arrivano dal /venv)
ENV PYTHONPATH=/app

# ---- Dati persistenti: tutti i file runtime puntano a /data ----
# Su Railway/Render monta un volume su /data
# In locale:  docker run -v $(pwd)/data:/data ... oppure usa docker-compose
ENV PCT_AGENDA_DB=/data/agenda/appuntamenti.json \
    PCT_DATA_ROOT=/data \
    PCT_STORAGE_MODE=SQLITE \
    PCT_SQLITE_MODE=1 \
    PCT_CALENDAR_SYNC_DB=/data/agenda/calendar_sync.json \
    PCT_CLIENTI_DB=/data/clienti/anagrafica.json \
    PCT_CONDIVISIONI_DB=/data/clienti/condivisioni.json \
    PCT_NOTE_FALDONE_DB=/data/clienti/note_faldone.json \
    PCT_SOGGETTI_DB=/data/soggetti/anagrafica.json \
    PCT_SOGGETTI_PARTI_DB=/data/soggetti/parti.json \
    PCT_FASCICOLI_DB=/data/fascicoli/fascicoli.json \
    PCT_FASCICOLI_DOCS=/data/fascicoli/documenti \
    PCT_FASCICOLI_ARCH=/data/fascicoli/archivio \
    PCT_PRACTICE_ENGINE_DB=/data/fascicoli/practice_engine/practice_engine.json \
    PCT_MESSAGGI_DB=/data/messaggi/storico.json \
    PCT_EMAIL_DB=/data/email/casella.json \
    PCT_EMAIL_ORDINARIA_DB=/data/email/ordinaria.json \
    PCT_BACKUP_DIR=/data/backup \
    PCT_AUTH_DB=/data/auth/utenti.json \
    PCT_AUDIT_DB=/data/auth/audit.json \
    PCT_SUPPORT_DB=/data/support/assistenza_remota.db \
    PCT_SCADENZIARIO_DB=/data/scadenziario/scadenze.json \
    PCT_TIMESHEET_DB=/data/timesheet/entries.json \
    PCT_TIME_TRACKING_DB=/data/timesheet/time_tracking.json \
    PCT_NOTIFICATIONS_DB=/data/notifications/notifications.db \
    PCT_SEARCH_INDEX=/data/search/index.db \
    PCT_PRIVACY_DB=/data/privacy/registro.json \
    PCT_PORTALE_DB=/data/portale/portali.json \
    PCT_PORTALE_UPLOADS=/data/portale/uploads \
    PCT_FATTURAZIONE_DB=/data/fatturazione/parcelle.json \
    PCT_PREVENTIVI_DB=/data/preventivi/preventivi.json \
    PCT_NOTIFICHE_LOG=/data/notifiche/log.json \
    PCT_WIZARD_PRO_DB=/data/wizard_pro/sessioni.json \
    PCT_LEGAL_INTELLIGENCE_DB=/data/intelligence/motori.json \
    PCT_GIURISPRUDENZA_DB=/data/intelligence/giurisprudenza.json \
    PCT_WORKSPACE_INTELLIGENCE_DB=/data/intelligence/workspace_intelligence.json \
    PCT_NORMATIVE_TABLES_DB=/data/intelligence/tabelle_normative.json \
    PCT_VALIDATION_RUNS_DB=/data/intelligence/validation_runs.json \
    PCT_REDACTION_ASSISTANT_DB=/data/intelligence/assistente_redazionale.json \
    PCT_TELEMATICO_DB=/data/telematico/workflow.db \
    PCT_TEMPLATE_ATTI_DB=/data/template_atti/templates.json \
    PCT_TEMPLATE_ATTI_PREFS_DB=/data/template_atti/editor_layout.json \
    PCT_PAGAMENTI_DIR=/data/pagamenti \
    PCT_UFFICI_DB=/data/uffici/uffici_giudiziari.json \
    PCT_UFFICI_TTL_GIORNI=7 \
    PCT_TENANTS_REGISTRY=/data/tenants.json \
    PCT_STUDIO_CONFIG=/data/config/studio.json \
    IUSENTRA_WEB_PUSH_ENABLED=0 \
    IUSENTRA_VAPID_PUBLIC_KEY="" \
    IUSENTRA_VAPID_PRIVATE_KEY="" \
    IUSENTRA_VAPID_SUBJECT="mailto:admin@example.com" \
    PCT_MULTI_TENANT=1 \
    PCT_HTTPS=true \
    PCT_STUDIO_NOME="IUSENTRA"

# PCT_SECRET_KEY e PCT_DOC_KEY vanno impostati come variabili d'ambiente
# nel pannello Railway/Render - NON metterle nel Dockerfile!

RUN mkdir -p /data

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os, urllib.request; port=os.getenv('PORT', '8080'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/pronto', timeout=5)"

ENTRYPOINT ["python", "/usr/local/bin/iusentra-entrypoint.py"]

# Gunicorn: configurazione governata in gunicorn.conf.py, con bind derivato da PORT.
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
