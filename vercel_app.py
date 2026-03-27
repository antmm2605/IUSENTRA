import os
import sys
from pathlib import Path

# --- 1. AMBIENTE VERCEL ---
os.environ['PCT_STUDIO_CONFIG'] = '/tmp/studio.json'

# --- 2. MEGA MONKEY PATCH (Blocca ogni tentativo di scrittura su disco fisso) ---
import pct.auth
import pct.agenda
import pct.scadenziario  # <--- Aggiunto questo
try:
    import pct.notifiche
except ImportError:
    pass

# Funzione universale per forzare i path in /tmp
def get_tmp_path(original_path, filename):
    return f"/tmp/{filename}"

# Patch Autenticazione
original_auth_init = pct.auth.GestioneUtenti.__init__
def patched_auth_init(self, db_path=None, audit_path=None, *args, **kwargs):
    return original_auth_init(self, "/tmp/utenti.json", "/tmp/audit.json", *args, **kwargs)
pct.auth.GestioneUtenti.__init__ = patched_auth_init

# Patch Agenda
original_agenda_init = pct.agenda.Agenda.__init__
def patched_agenda_init(self, db_path=None, *args, **kwargs):
    return original_agenda_init(self, "/tmp/appuntamenti.json", *args, **kwargs)
pct.agenda.Agenda.__init__ = patched_agenda_init

# Patch Scadenziario (L'errore che vedi ora)
original_scad_init = pct.scadenziario.GestioneScadenziario.__init__
def patched_scad_init(self, db_path=None, *args, **kwargs):
    # Forziamo il database dello scadenziario in /tmp
    return original_scad_init(self, "/tmp/scadenze.json", *args, **kwargs)
pct.scadenziario.GestioneScadenziario.__init__ = patched_scad_init

# --- 3. CARICAMENTO APPLICAZIONE ---
try:
    from web.app import create_app
    app = create_app()
    
    # Sovrascriviamo le configurazioni Flask per sicurezza extra
    app.config.update(
        AUTH_DB_PATH='/tmp/utenti.json',
        AUTH_AUDIT_PATH='/tmp/audit.json',
        AGENDA_DB_PATH='/tmp/appuntamenti.json',
        SCADENZIARIO_DB='/tmp/scadenze.json',
        NOTIFICHE_DB='/tmp/notifiche.json',
        ASSISTENTE_DB='/tmp/assistente.json',
        OCR_TEMP_DIR='/tmp/ocr'
    )
    
    # Prepariamo le cartelle temporanee
    Path("/tmp/ocr").mkdir(parents=True, exist_ok=True)
    
except Exception as e:
    print(f"ERRORE CRITICO: {e}")
    raise e

# Export per Vercel
app = app
