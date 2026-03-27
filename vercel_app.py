import os
import sys
from pathlib import Path

# --- 1. PREPARAZIONE AMBIENTE VERCEL ---
os.environ['PCT_STUDIO_CONFIG'] = '/tmp/studio.json'

# --- 2. SUPER MONKEY PATCH (Correzione Posizionale + Keyword) ---
import pct.auth
import pct.agenda

# Patch per GestioneUtenti (Autenticazione)
def patched_auth_init(self, db_path=None, audit_path=None, *args, **kwargs):
    # Forza i percorsi in /tmp ignorando qualsiasi valore passato
    new_db_path = "/tmp/utenti.json"
    new_audit_path = "/tmp/audit.json"
    # Chiamata all'init originale con i percorsi forzati
    return original_auth_init(self, new_db_path, new_audit_path, *args, **kwargs)

original_auth_init = pct.auth.GestioneUtenti.__init__
pct.auth.GestioneUtenti.__init__ = patched_auth_init

# Patch per Agenda
def patched_agenda_init(self, db_path=None, *args, **kwargs):
    new_db_path = "/tmp/appuntamenti.json"
    return original_agenda_init(self, new_db_path, *args, **kwargs)

original_agenda_init = pct.agenda.Agenda.__init__
pct.agenda.Agenda.__init__ = patched_agenda_init

# --- 3. CARICAMENTO APPLICAZIONE ---
try:
    from web.app import create_app
    app = create_app()
    
    # Forziamo le configurazioni Flask a livello globale
    app.config.update(
        AUTH_DB_PATH='/tmp/utenti.json',
        AUTH_AUDIT_PATH='/tmp/audit.json',
        AGENDA_DB_PATH='/tmp/appuntamenti.json',
        # Se hai un modulo OCR che scrive log o temp, forzalo qui
        OCR_TEMP_DIR='/tmp/ocr'
    )
    
    # Creiamo preventivamente le cartelle se necessario
    Path("/tmp/ocr").mkdir(parents=True, exist_ok=True)
    
except Exception as e:
    print(f"ERRORE CRITICO AVVIO: {type(e).__name__}: {e}")
    raise e

app = app
