import os
import sys

# 1. Configurazione Percorsi
# Usiamo la variabile impostata su Vercel (Neon), altrimenti fallback su SQLite
if 'DATABASE_URL' not in os.environ:
    os.environ['DATABASE_URL'] = os.environ.get('DATABASE_URL')

# Forza il file config in zona scrivibile (RAM)
os.environ['AUTH_DB_PATH'] = '/tmp/auth.db'
os.environ['PCT_STUDIO_CONFIG'] = '/tmp/studio.json'

# 2. Inizializzazione App
try:
    from web.app import create_app
    app = create_app()
except Exception as e:
    # Questo scriverà l'errore esatto nei log di Vercel se qualcosa fallisce
    print(f"ERRORE CRITICO AVVIO: {e}")
    raise e

# Export per il motore di Vercel
app = app
