import os
import sys
import json
from pathlib import Path

# --- 1. BYPASS PERMESSI DI SCRITTURA ---
original_mkdir = Path.mkdir
def safe_mkdir(self, mode=0o777, parents=False, exist_ok=False):
    try:
        original_mkdir(self, mode, parents, exist_ok)
    except OSError as e:
        if e.errno == 30: pass 
        else: raise e
Path.mkdir = safe_mkdir

# --- 2. MAPPATURA COMPLETA (Inclusi i mancanti) ---
DB_FILES = {
    'AUTH_DB': 'utenti.json',
    'AGENDA_DB_PATH': 'appuntamenti.json',
    'AGENDA_DB': 'appuntamenti.json',
    'SCADENZIARIO_DB': 'scadenze.json',
    'FASCICOLI_DB': 'fascicoli.json',
    'CLIENTI_DB': 'anagrafica.json',
    'FATTURAZIONE_DB': 'parcelle.json',
    'MESSAGGI_DB': 'storico_messaggi.json',
    'STUDIO_CONFIG': 'studio.json',
    'PCT_STUDIO_CONFIG': 'studio.json',
    'TENANTS_REGISTRY': 'tenants.json',
    'AUDIT_DB': 'audit.json',
    'NOTIFICHE_LOG': 'log_notifiche.json',
    # Correzione per Search Index
    'SEARCH_INDEX_DB': 'index.db',
    'SEARCH_DB': 'index.db'
}

# Inizializzazione file in /tmp
for key, filename in DB_FILES.items():
    full_path = Path("/tmp") / filename
    os.environ[key] = str(full_path)
    if not full_path.exists():
        with open(full_path, 'w') as f:
            if filename.endswith('.json'):
                json.dump({}, f)
            else:
                f.write("") # Per il .db della ricerca

# --- 3. MONKEY PATCHING AGGRESSIVO ---
# Qui risolviamo il problema "Appuntamenti" che puntava a "agenda/"
try:
    import pct.agenda
    import pct.scadenziario
    # Se hai un modulo per la ricerca, aggiungilo qui sotto
    
    # Forza il modulo Agenda a ignorare "agenda/appuntamenti.json"
    pct.agenda.Agenda.__init__ = lambda self, db_path=None, *args, **kwargs: \
        original_agenda_init(self, db_path="/tmp/appuntamenti.json", *args, **kwargs) \
        if 'original_agenda_init' in globals() else None

    # Nota: Usiamo una tecnica più diretta per sovrascrivere
    def force_tmp_agenda(self, db_path=None, *args, **kwargs):
        self.db_path = Path("/tmp/appuntamenti.json")
    
    pct.agenda.Agenda.__init__ = force_tmp_agenda
    pct.scadenziario.GestioneScadenziario.__init__ = lambda self, *args, **kwargs: \
        setattr(self, 'db_path', Path("/tmp/scadenze.json"))

except Exception as e:
    print(f"Patching error: {e}")

# --- 4. AVVIO APP ---
try:
    from web.app import create_app
    app = create_app()
    
    # Sovrascrittura finale della config Flask
    app.config.update({
        'AGENDA_DB_PATH': '/tmp/appuntamenti.json',
        'AGENDA_DB': '/tmp/appuntamenti.json',
        'SEARCH_INDEX_DB': '/tmp/index.db',
        'SEARCH_DB': '/tmp/index.db',
        'CLIENTI_DB': '/tmp/anagrafica.json',
        'FASCICOLI_DB': '/tmp/fascicoli.json'
    })
except Exception as e:
    raise e

app = app
