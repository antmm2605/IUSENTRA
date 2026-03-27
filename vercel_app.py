import os
import sys
from pathlib import Path

# --- 1. BYPASS PERMESSI (ANTI-CRASH VERCEL) ---
# Sovrascriviamo i metodi di creazione cartelle: se Vercel nega la scrittura, 
# l'app va avanti invece di crashare con Errore 500.
original_mkdir = Path.mkdir
def safe_mkdir(self, mode=0o777, parents=False, exist_ok=False):
    try:
        original_mkdir(self, mode, parents, exist_ok)
    except OSError as e:
        if e.errno == 30: # Read-only file system
            pass 
        else:
            raise e
Path.mkdir = safe_mkdir

original_makedirs = os.makedirs
def safe_makedirs(name, mode=0o777, exist_ok=False):
    try:
        original_makedirs(name, mode, exist_ok)
    except OSError as e:
        if e.errno == 30:
            pass
        else:
            raise e
os.makedirs = safe_makedirs

# Questo forza l'agenda a guardare SEMPRE in /tmp anche se il blueprint non passa parametri
    original_agenda_init = pct.agenda.Agenda.__init__
    def patched_agenda_init(self, db_path=None, *args, **kwargs):
        return original_agenda_init(self, db_path="/tmp/appuntamenti.json", *args, **kwargs)
    pct.agenda.Agenda.__init__ = patched_agenda_init

    original_scad_init = pct.scadenziario.GestioneScadenziario.__init__
    def patched_scad_init(self, db_path=None, *args, **kwargs):
        return original_scad_init(self, db_path="/tmp/scadenze.json", *args, **kwargs)
    pct.scadenziario.GestioneScadenziario.__init__ = patched_scad_init
except Exception as e:
    print(f"Patching non riuscito: {e}")

# --- 2. MAPPATURA PERCORSI SU /TMP ---
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
    'PORTALE_UPLOADS': 'uploads_portale',
    'PAGAMENTI_DIR': 'pagamenti',
    'OCR_TEMP_DIR': 'ocr_temp'
}

# Impostiamo le variabili d'ambiente prima dell'import dell'app
for env_var, folder_or_file in DB_FILES.items():
    os.environ[env_var] = f"/tmp/{folder_or_file}"

# Creazione fisica delle sottocartelle in RAM
for folder in ['uploads_portale', 'pagamenti', 'ocr_temp']:
    Path(f"/tmp/{folder}").mkdir(parents=True, exist_ok=True)

# --- 3. MONKEY PATCHING DELLE CLASSI CORE ---
# Importiamo i moduli per forzare i percorsi nei costruttori (__init__)
try:
    import pct.auth
    import pct.agenda
    import pct.scadenziario
    import pct.clienti
    import pct.fascicoli

    def patch_path(original_init, key):
        def patched_init(self, db_path=None, *args, **kwargs):
            # Forza l'uso del percorso in /tmp definito sopra
            new_path = f"/tmp/{DB_FILES[key]}"
            return original_init(self, db_path=new_path, *args, **kwargs)
        return patched_init

    pct.auth.GestioneUtenti.__init__ = patch_path(pct.auth.GestioneUtenti.__init__, 'AUTH_DB')
    pct.agenda.Agenda.__init__ = patch_path(pct.agenda.Agenda.__init__, 'AGENDA_DB_PATH')
    pct.scadenziario.GestioneScadenziario.__init__ = patch_path(pct.scadenziario.GestioneScadenziario.__init__, 'SCADENZIARIO_DB')
    pct.clienti.GestioneClienti.__init__ = patch_path(pct.clienti.GestioneClienti.__init__, 'CLIENTI_DB')
    pct.fascicoli.GestioneFascicoli.__init__ = patch_path(pct.fascicoli.GestioneFascicoli.__init__, 'FASCICOLI_DB')
except ImportError:
    print("Avviso: Moduli PCT non trovati per il patching, procedo con config standard.")

# --- 4. AVVIO APPLICAZIONE ---
app = None
try:
    from web.app import create_app
    app = create_app()
    
    # Aggiorniamo la configurazione Flask con i percorsi /tmp
    for env_var, folder_or_file in DB_FILES.items():
        app.config[env_var] = f"/tmp/{folder_or_file}"
        
except Exception as e:
    print(f"ERRORE CRITICO AVVIO: {e}")
    raise e

# Export per Vercel
app = app
