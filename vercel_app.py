# vercel_app.py
import os
import json
from pathlib import Path

BASE_TMP = Path("/tmp/hacs_data")
BASE_TMP.mkdir(parents=True, exist_ok=True)

def ensure_parent(path_str: str):
    p = Path(path_str)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def ensure_json_file(path_str: str, default=None):
    if default is None:
        default = {}
    p = ensure_parent(path_str)
    if not p.exists():
        p.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)

def ensure_text_file(path_str, default=""):
    p = ensure_parent(path_str)
    if not p.exists():
        p.write_text(default, encoding="utf-8")
    return str(p)

def ensure_dir(path_str: str):
    p = Path(path_str)
    p.mkdir(parents=True, exist_ok=True)
    return str(p)

# Segnala all'app che gira su Vercel/serverless
os.environ["VERCEL"] = "1"
os.environ["SERVERLESS"] = "1"
os.environ["PCT_DISABLE_SCHEDULER"] = "1"

# Root dati "finta" ma coerente per il progetto
DATA_DIR = BASE_TMP / "data"
CONFIG_DIR = BASE_TMP / "config"
TENANTS_DIR = BASE_TMP / "tenants"

ensure_dir(str(DATA_DIR))
ensure_dir(str(CONFIG_DIR))
ensure_dir(str(TENANTS_DIR))

# File e cartelle base coerenti con il progetto
os.environ["TENANTS_REGISTRY"] = ensure_json_file(str(DATA_DIR / "tenants.json"), {})
os.environ["STUDIO_CONFIG"] = ensure_json_file(str(CONFIG_DIR / "studio.json"), {})
os.environ["PCT_STUDIO_CONFIG"] = os.environ["STUDIO_CONFIG"]

os.environ["AUTH_DB"] = ensure_json_file(str(DATA_DIR / "auth" / "utenti.json"), {})
os.environ["AUDIT_DB"] = ensure_json_file(str(DATA_DIR / "auth" / "audit.json"), [])
os.environ["AGENDA_DB"] = ensure_json_file(str(DATA_DIR / "agenda" / "appuntamenti.json"), {})
os.environ["AGENDA_DB_PATH"] = os.environ["AGENDA_DB"]
os.environ["SCADENZIARIO_DB"] = ensure_json_file(str(DATA_DIR / "scadenziario" / "scadenze.json"), {})
os.environ["CLIENTI_DB"] = ensure_json_file(str(DATA_DIR / "clienti" / "anagrafica.json"), {})
os.environ["FASCICOLI_DB"] = ensure_json_file(str(DATA_DIR / "fascicoli" / "fascicoli.json"), {})
os.environ["FATTURAZIONE_DB"] = ensure_json_file(str(DATA_DIR / "fatturazione" / "parcelle.json"), {})
os.environ["MESSAGGI_DB"] = ensure_json_file(str(DATA_DIR / "messaggi" / "storico.json"), {})
os.environ["EMAIL_CASELLA_DB"] = ensure_json_file(str(DATA_DIR / "email" / "casella_email.json"), {})
os.environ["TEMPLATE_ATTI_DB"] = ensure_json_file(str(DATA_DIR / "template_atti" / "templates.json"), {})
os.environ["PORTALE_DB"] = ensure_json_file(str(DATA_DIR / "portale" / "portali.json"), {})
os.environ["NOTIFICHE_LOG"] = ensure_json_file(str(DATA_DIR / "notifiche" / "log.json"), [])
os.environ["SEARCH_INDEX"] = ensure_text_file(str(DATA_DIR / "search" / "index.db"))
os.environ["SEARCH_INDEX_DB"] = os.environ["SEARCH_INDEX"]
os.environ["SEARCH_DB"] = os.environ["SEARCH_INDEX"]

os.environ["PORTALE_UPLOADS"] = ensure_dir(str(DATA_DIR / "portale" / "uploads"))
os.environ["FASCICOLI_DOCS"] = ensure_dir(str(DATA_DIR / "fascicoli" / "documenti"))
os.environ["FASCICOLI_ARCH"] = ensure_dir(str(DATA_DIR / "fascicoli" / "archivio"))
os.environ["BACKUP_DIR"] = ensure_dir(str(DATA_DIR / "backup"))
os.environ["PAGAMENTI_DIR"] = ensure_dir(str(DATA_DIR / "pagamenti"))
ensure_dir(str(DATA_DIR / "ocr_temp"))

# Import finale dell'app solo dopo aver preparato l'ambiente
from web.app import create_app

app = create_app()

# Rafforza la config Flask
app.config["TENANTS_REGISTRY"] = os.environ["TENANTS_REGISTRY"]
app.config["STUDIO_CONFIG"] = os.environ["STUDIO_CONFIG"]
app.config["PCT_STUDIO_CONFIG"] = os.environ["PCT_STUDIO_CONFIG"]

for key in [
    "AUTH_DB",
    "AUDIT_DB",
    "AGENDA_DB",
    "AGENDA_DB_PATH",
    "SCADENZIARIO_DB",
    "CLIENTI_DB",
    "FASCICOLI_DB",
    "FATTURAZIONE_DB",
    "MESSAGGI_DB",
    "EMAIL_CASELLA_DB",
    "TEMPLATE_ATTI_DB",
    "PORTALE_DB",
    "NOTIFICHE_LOG",
    "SEARCH_INDEX",
    "SEARCH_INDEX_DB",
    "SEARCH_DB",
    "PORTALE_UPLOADS",
    "FASCICOLI_DOCS",
    "FASCICOLI_ARCH",
    "BACKUP_DIR",
    "PAGAMENTI_DIR",
]:
    app.config[key] = os.environ[key]
