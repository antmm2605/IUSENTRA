import os
import sys
import json
from pathlib import Path

# --- 1. BYPASS PERMESSI (ANTI-CRASH VERCEL) ---
# Sovrascriviamo i metodi di creazione cartelle per evitare il crash su Read-only FS
original_mkdir = Path.mkdir
def safe_mkdir(self, mode=0o777, parents=False, exist_ok=False):
    try:
        original_mkdir(self, mode, parents, exist_ok)
    except OSError as e:
        if e.errno == 30: pass 
        else: raise e
Path.mkdir = safe_mkdir

original_makedirs = os.makedirs
def safe_makedirs(name, mode=0o777, exist_ok=False):
    try:
        original_makedirs(name, mode, exist_ok)
    except OSError as e:
        if e.errno == 30: pass
        else: raise e
os.makedirs = safe_makedirs

# --- 2. MAPPATURA PERCORSI SU /TMP ---
# Inseriamo qui tutti i database che la tua tabella indicava come "Non trovati"
DB_FILES = {
    'AUTH_DB': 'utenti.json',
    'AUDIT_DB': 'audit.json',
    'AGENDA_DB_PATH': 'appuntamenti.json',
    'AGENDA_DB': 'appuntamenti.json',
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
    # Correzione per Search Index che cercava "search/index.db"
    'SEARCH_INDEX_DB': 'index.db',
    'SEARCH_DB': 'index.db'
}

# Inizializziamo i file in /tmp così l'app li trova pronti
for env_var, filename in DB_FILES.items():
    full_path = Path("/tmp") / filename
    os.environ[env_var] = str(full_path)
    if not full_path.exists():
        with open(full_path, 'w') as f:
            if filename.endswith('.json'):
                json.dump({}, f)
            else:
                f.write("")

# Creazione cartelle per upload/temp
for folder in ['uploads_portale', 'pagamenti', 'ocr_temp']:
    Path(f"/tmp/{folder}").mkdir(parents=True, exist_ok=True)

# --- 3. MONKEY PATCHING DELLE CLASSI CORE ---
try:
    import pct.auth
    import pct.agenda
    import pct.scadenziario
    import pct.clienti
    import pct.fascicoli

    # Funzione per forzare il path a prescindere da cosa chiede il codice originale
    def patch_class_path(cls, filename):
        original_init = cls.__init__
        def patched_init(self, *args, **kwargs):
            # Ignora il db_path passato e forza /tmp
            kwargs['db_path'] = f"/tmp/{filename}"
            return original_init(self, *args, **kwargs)
        cls.__init__ = patched_init

    patch_class_path(pct.auth.GestioneUtenti, 'utenti.json')
    patch_class_path(pct.agenda.Agenda, 'appuntamenti.json')
    patch_class_path(pct.scadenziario.GestioneScadenziario, 'scadenze.json')
    patch_class_path(pct.clienti.GestioneClienti, 'anagrafica.json')
    patch_class_path(pct.fascicoli.GestioneFascicoli, 'fascicoli.json')

except Exception as e:
    print(f"Avviso Patching: {e}")

# --- 4. AVVIO APPLICAZIONE ---
app = None
try:
    from web.app import create_app
    app = create_app()
    
    # Sovrascriviamo la config di Flask per sicurezza estrema
    for key, filename in DB_FILES.items():
        app.config[key] = f"/tmp/{filename}"
        
except Exception as e:
    print(f"ERRORE CRITICO AVVIO: {e}")
    raise e

app = app
