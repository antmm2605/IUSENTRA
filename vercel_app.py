import os
from pathlib import Path
import pct.auth

# --- MONKEY PATCH PER VERCEL ---
# Sovrascriviamo i percorsi della GestioneUtenti per puntare alla RAM (/tmp)
# Questo evita l'errore "Read-only file system" senza toccare pct/auth.py

original_init = pct.auth.GestioneUtenti.__init__

def patched_init(self, *args, **kwargs):
    # Forziamo i file JSON degli utenti nella cartella scrivibile /tmp
    kwargs['db_path'] = "/tmp/utenti.json"
    kwargs['audit_path'] = "/tmp/audit.json"
    return original_init(self, *args, **kwargs)

# Applichiamo la modifica al volo
pct.auth.GestioneUtenti.__init__ = patched_init

# --- CONFIGURAZIONE AMBIENTE ---
# Forza il file studio.json in /tmp
os.environ['PCT_STUDIO_CONFIG'] = '/tmp/studio.json'

# Se hai configurato Neon, l'app userà quello per i dati legali
# altrimenti userà un database SQLite temporaneo
if 'DATABASE_URL' not in os.environ:
    os.environ['DATABASE_URL'] = 'sqlite:////tmp/hacs.db'

# --- AVVIO APP ---
try:
    from web.app import create_app
    app = create_app()
except Exception as e:
    print(f"ERRORE CRITICO AVVIO: {e}")
    raise e

# Export per Vercel
app = app
