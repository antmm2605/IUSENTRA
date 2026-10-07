"""Diagnosi Consulta in sola lettura, senza dati identificativi degli studi."""
import json
import subprocess

command = ["docker", "compose", "--env-file", "/opt/iusentra/.env.hetzner", "-f", "/opt/iusentra/repo/deploy/hetzner/docker-compose.hetzner.yml"]
container = subprocess.check_output(command + ["ps", "-q", "scheduler-worker"], text=True).strip()
assert container, "Worker non presente"
processes = subprocess.check_output(["docker", "top", container, "-eo", "pid,etime,args"], text=True)
print(json.dumps({"import_processes": [line for line in processes.splitlines() if "tools/cortecost_importa.py" in line]}), flush=True)
code = """
import json, os, re
from pathlib import Path
from pct.corte_costituzionale_opendata import archivio_completo_presente, corpus_ha_pronunce
from tools.cortecost_importa import corpus_dei_tenant
paths=corpus_dei_tenant(os.getenv('PCT_TENANTS_REGISTRY','/data/tenants.json'),os.getenv('PCT_DATA_ROOT','/data'))
for index,path in enumerate(paths):
    p=Path(path)
    print(json.dumps({'corpus_index':index,'complete':archivio_completo_presente(path),'pronunce':corpus_ha_pronunce(path),'db_bytes':p.stat().st_size if p.exists() else 0}),flush=True)
folder=Path('/data/fonti_ufficiali/cortecost')
print(json.dumps({'downloads':[{'name':p.name,'bytes':p.stat().st_size} for p in sorted(folder.glob('*.zip*'))]}),flush=True)
p=folder/'import.log'
if p.exists():
    lines=p.read_text(errors='replace').splitlines()[-30:]
    for line in lines:
        if re.search(r'pronunce lette|Scaricati|ERRORE:|Un altro import|Corte costituzionale:',line):
            print(re.sub(r'/data/[^ ]+', '[percorso]', line),flush=True)
"""
subprocess.run(command + ["exec", "-T", "scheduler-worker", "python", "-"], input=code, text=True, check=True, timeout=90)
