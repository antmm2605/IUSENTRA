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

# Solo metadati Git: nessun sorgente, credenziale o dato degli studi viene trasferito.
import hashlib
from pathlib import Path
repo = Path("/opt/iusentra/repo")
def git_metadata(*args):
    return subprocess.check_output(["git", "-C", str(repo), *args])
head = git_metadata("rev-parse", "HEAD").decode().strip()
changed = set(git_metadata("diff", "HEAD", "--name-only", "-z").decode().split("\0"))
changed.update(git_metadata("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0"))
changed.discard("")
metadata = []
for name in sorted(changed):
    path = repo / name
    row = {"path": name, "exists": path.is_file(), "symlink": path.is_symlink()}
    original = subprocess.run(["git", "-C", str(repo), "show", "HEAD:" + name], capture_output=True)
    row["tracked_at_head"] = original.returncode == 0
    if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(repo):
        data = path.read_bytes()
        row["sha256"] = hashlib.sha256(data).hexdigest()
        row["matches_head"] = original.returncode == 0 and data == original.stdout
        row["matches_head_normalized"] = original.returncode == 0 and data.replace(b"\r\n", b"\n") == original.stdout.replace(b"\r\n", b"\n")
    metadata.append(row)
print(json.dumps({"server_head": head, "source_changes_metadata": metadata}), flush=True)
