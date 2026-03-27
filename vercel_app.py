import os
import sys
from pathlib import Path

# --- TRUCCO PER VERCEL: Sovrascriviamo i percorsi prima di importare l'app ---
import pct.auth

# Definiamo i nuovi percorsi scrivibili (nella RAM di Vercel)
VERCEL_AUTH_DB = "/tmp/utenti.json"
VERCEL_AUDIT_DB = "/tmp/audit.json"

# Modifichiamo i valori predefiniti della classe GestioneUtenti "al volo"
# Questo evita l'errore "Read-only file system" senza toccare pct/auth.py
original_init = pct.auth.GestioneUtenti.__init__

def patched_init(self, *args, **kwargs):
    # Forziamo i percorsi verso /tmp/ ignorando quelli passati o di default
    kwargs['db_path'] = VERCEL_AUTH_DB
    kwargs['audit_path'] = VERCEL_AUDIT_DB
    original_init(self, *args, **kwargs)

# Applichiamo la patch
pct.auth.GestioneUtenti.__init__ = patched_init
# --------------------------------------------------------------------------

# Ora importiamo l'app normalmente
try:
    from web.app import create_app
    app = create_app()
except Exception as e:
    print(f"ERRORE CRITICO AVVIO: {e}")
    raise e

# Export per Vercel
app = app
