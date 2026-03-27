import os
import sys
from pathlib import Path

# --- 1. MAPPATURA TOTALE DI TUTTI I DATABASE JSON ---
# Elenchiamo tutte le variabili usate dai tuoi Blueprints
DB_FILES = {
    'AUTH_DB': 'utenti.json',
    'AUDIT_DB': 'audit.json',
    'AGENDA_DB_PATH': 'appuntamenti.json',
    'SCADENZIARIO_DB': 'scadenze.json',
    'FASCICOLI_DB': 'fascicoli.json',
    'CLIENTI_DB': 'anagrafica.json',
    'FATTURAZIONE_DB': 'parcelle.json',
    'MESSAGGI_DB': 'storico_messaggi.json',
    'EMAIL_CASELLA_DB': 'casella_email.json',
    'TEMPLATE_ATTI_DB': 'templates.json',
    'PORTALE_DB': 'portali.json',
    'STUDIO_CONFIG': 'studio.json',
    'PCT_STUDIO_CONFIG': 'studio.json',
    'NOTIFICHE_LOG': 'log_notifiche.json',
    'TENANTS_REGISTRY': 'tenants.json',
    # Cartelle
    'PORTALE_UPLOADS': 'uploads_portale',
    'PAGAMENTI_DIR': 'pagamenti',
    'OCR_TEMP_DIR': 'ocr_temp'
}

# --- 2. INIEZIONE NELLE VARIABILI D'AMBIENTE ---
for env_var, folder_or_file in DB_FILES.items():
    os.environ[env_var] = f"/tmp/{folder_or_file}"

# Creiamo le cartelle temporanee necessarie per gli upload
Path("/tmp/uploads_portale").mkdir(parents=True, exist_ok=True)
Path("/tmp/pagamenti").mkdir(parents=True, exist_ok=True)
Path("/tmp/ocr_temp").mkdir(parents=True, exist_ok=True)

# --- 3. MEGA MONKEY PATCH PER CLASSI HARDCODED ---
# Forziamo le classi principali a usare /tmp ignorando i valori scritti in web/app.py
import pct.auth
import pct.agenda
import pct.scadenziario
import pct.clienti
import pct.fascicoli

def patch_path(original_init, new_path):
    def patched_init(self, db_path=None, *args, **kwargs):
        return original_init(self, db_path=new_path, *args, **kwargs)
    return patched_init

pct.auth.GestioneUtenti.__init__ = patch_path(pct.auth.GestioneUtenti.__init__, "/tmp/utenti.json")
pct.agenda.Agenda.__init__ = patch_path(pct.agenda.Agenda.__init__, "/tmp/appuntamenti.json")
pct.scadenziario.GestioneScadenziario.__init__ = patch_path(pct.scadenziario.GestioneScadenziario.__init__, "/tmp/scadenze.json")
pct.clienti.GestioneClienti.__init__ = patch_path(pct.clienti.GestioneClienti.__init__, "/tmp/anagrafica.json")
pct.fascicoli.GestioneFascicoli.__init__ = patch_path(pct.fascicoli.GestioneFascicoli.__init__, "/tmp/fascicoli.json")

# --- 4. AVVIO APPLICAZIONE ---
try:
    from web.app import create_app
    app = create_app()
    
    # Doppio lucchetto: sovrascriviamo anche app.config di Flask
    for env_var, folder_or_file in DB_FILES.items():
        app.config[env_var] = f"/tmp/{folder_or_file}"
        
except Exception as e:
    print(f"ERRORE CRITICO AVVIO: {type(e).__name__}: {e}")
    raise e

# Export per il server Serverless di Vercel
app = app
