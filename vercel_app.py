import os
from pathlib import Path

# --- 1. PREPARAZIONE AMBIENTE VERCEL ---
os.environ['PCT_STUDIO_CONFIG'] = '/tmp/studio.json'

# --- 2. SUPER MONKEY PATCH (Intercettazione argomenti) ---
import pct.auth
import pct.agenda

# Patch per GestioneUtenti: intercettiamo gli argomenti db_path e audit_path
original_auth_init = pct.auth.GestioneUtenti.__init__
def patched_auth_init(self, *args, **kwargs):
    # Forza i percorsi in /tmp ignorando quello che arriva da web/app.py
    kwargs['db_path'] = "/tmp/utenti.json"
    kwargs['audit_path'] = "/tmp/audit.json"
    return original_auth_init(self, *args, **kwargs)

pct.auth.GestioneUtenti.__init__ = patched_auth_init

# Patch per Agenda: intercettiamo db_path
original_agenda_init = pct.agenda.Agenda.__init__
def patched_agenda_init(self, *args, **kwargs):
    kwargs['db_path'] = "/tmp/appuntamenti.json"
    return original_agenda_init(self, *args, **kwargs)

pct.agenda.Agenda.__init__ = patched_agenda_init

# --- 3. CARICAMENTO APPLICAZIONE ---
try:
    from web.app import create_app
    app = create_app()
    
    # Sovrascriviamo anche la configurazione Flask per sicurezza
    app.config.update(
        AUTH_DB_PATH='/tmp/utenti.json',
        AUTH_AUDIT_PATH='/tmp/audit.json',
        AGENDA_DB_PATH='/tmp/appuntamenti.json'
    )
except Exception as e:
    print(f"ERRORE CRITICO AVVIO: {type(e).__name__}: {e}")
    raise e

# Export per Vercel
app = app
