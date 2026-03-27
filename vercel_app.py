import os
import sys

# 1. Forza i percorsi in /tmp/ (l'unica cartella scrivibile su Vercel)
os.environ['DATABASE_URL'] = 'sqlite:////tmp/hacs.db'
os.environ['PCT_STUDIO_CONFIG'] = '/tmp/studio.json'

# 2. Importa la tua app (assicurati che il percorso sia corretto)
try:
    from web.app import create_app
    app = create_app()
except Exception as e:
    print(f"ERRORE CRITICO AVVIO: {e}")
    raise e

# Indispensabile per Vercel
app = app
