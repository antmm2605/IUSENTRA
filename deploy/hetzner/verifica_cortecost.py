"""Controlla in sola lettura l'import della Consulta nei corpus della release."""
import json
import os
from pathlib import Path
import time

from pct.corte_costituzionale_opendata import archivio_completo_presente
from tools.cortecost_importa import corpus_dei_tenant

paths = corpus_dei_tenant(os.getenv("PCT_TENANTS_REGISTRY", "/data/tenants.json"), os.getenv("PCT_DATA_ROOT", "/data"))
assert paths, "Nessun corpus della Consulta da verificare"
for attempt in range(61):
    complete = sum(archivio_completo_presente(path) for path in paths)
    print(json.dumps({"cortecost_corpus": len(paths), "cortecost_completi": complete, "tentativo": attempt + 1}), flush=True)
    if complete == len(paths):
        break
    if attempt == 60:
        log = Path("/data/fonti_ufficiali/cortecost/import.log")
        lines = log.read_text(errors="replace").splitlines()[-20:] if log.is_file() else []
        errors = [line for line in lines if "ERRORE:" in line or "Traceback" in line]
        raise RuntimeError("Import Consulta non completato entro 15 minuti: " + " | ".join(errors))
    time.sleep(15)
