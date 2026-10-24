"""Aggiornamento del servizio pubblico con riuso di dati e pesi."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def inspect(name):
    return json.loads(command("docker", "inspect", name))[0]


def request(container, url, payload=None):
    code = ("import json,urllib.request;"
            "url,payload=json.loads(__import__('sys').argv[1]);"
            "req=urllib.request.Request(url,None if payload is None else json.dumps(payload).encode(),"
            "{'Content-Type':'application/json'});"
            "print(urllib.request.urlopen(req,timeout=10).read().decode())")
    return json.loads(command("docker", "exec", container, "python", "-c", code, json.dumps([url, payload])))


def run(sha):
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("SHA non valido")
    repo = Path("/opt/iusentra/repo")
    if command("git", "-C", str(repo), "rev-parse", "HEAD") != sha:
        raise ValueError("Revisione server diversa dal candidato")
    name = "iusentra-openga-" + sha[:12]
    active = command("docker", "ps", "-q", "--filter", "label=io.iusentra.component=openga").split()
    if len(active) != 1:
        raise ValueError("Numero servizi pubblici attivi inatteso")
    old = inspect(active[0])
    if old["Name"] == "/" + name:
        result = request("iusentra-app", "http://openga-search:8092/inventory")
        if result.get("ok") is not True:
            raise ValueError("Inventario non disponibile")
        print(json.dumps({"gia_aggiornato": True, "inventario": result}))
        return
    old_name = old["Name"].lstrip("/")
    base_image = old["Config"]["Image"]
    if not re.fullmatch(r"iusentra-openga:[a-f0-9]{40}", base_image):
        raise ValueError("Immagine precedente non governata")
    mounts = {m["Destination"]: m for m in old["Mounts"]}
    if set(mounts) != {"/catalogo", "/modello"} or any(m["RW"] for m in mounts.values()):
        raise ValueError("Volumi pubblici diversi dal profilo read-only")
    catalog = Path(mounts["/catalogo"]["Source"])
    model = Path(mounts["/modello"]["Source"])
    if any(not p.is_relative_to("/opt/iusentra/openga") or not p.is_dir() for p in (catalog, model)):
        raise ValueError("Origine dei dati non governata")
    installed = json.loads((catalog.parent / "INSTALLATO.json").read_text())
    if installed.get("scope") != "metadata_only":
        raise ValueError("Perimetro del catalogo non dimostrato")
    networks = old["NetworkSettings"]["Networks"]
    if len(networks) != 1:
        raise ValueError("Rete del servizio pubblico ambigua")
    network = next(iter(networks))
    if shutil.disk_usage(repo).free < 2 * 1024**3:
        raise ValueError("Margine disco insufficiente")
    mem = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
    if int(mem["MemAvailable"].split()[0]) < 2 * 1024**2:
        raise ValueError("Margine memoria insufficiente")
    baseline = request("iusentra-app", "http://openga-search:8092/search", {"q": "permesso soggiorno", "semantica": False})
    if not baseline.get("ok"):
        raise ValueError("Servizio precedente non pronto")
    # Ranking e pesi preservati nell'immagine di origine; nessuna installazione.
    dockerfile = (f"FROM {base_image}\n"
                  "COPY pct/openga_search.py /app/pct/openga_search.py\n"
                  "COPY pct/openga_identita.py /app/pct/openga_identita.py\n"
                  "COPY pct/__init__.py /app/pct/__init__.py\n"
                  "COPY deploy/openga/server.py /app/server.py\n")
    image = "iusentra-openga:" + sha
    with tempfile.NamedTemporaryFile(mode="w", suffix=".Dockerfile") as handle:
        handle.write(dockerfile)
        handle.flush()
        subprocess.run(["docker", "build", "--pull=false", "-f", handle.name, "-t", image,
                        "--label", "io.iusentra.component=openga",
                        "--label", "org.opencontainers.image.revision=" + sha, str(repo)], check=True)
    subprocess.run(["docker", "run", "-d", "--name", name,
                    "--label", "io.iusentra.component=openga", "--label", "org.opencontainers.image.revision=" + sha,
                    "--restart", "unless-stopped", "--network", network, "--read-only",
                    "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--cpus", "4", "--memory", "6g",
                    "--tmpfs", "/tmp:rw,noexec,nosuid,size=128m",
                    "-e", "LEX_EMBED_URL=http://ollama:11434", "-e", "LEX_EMBED_MODEL=embeddinggemma:300m",
                    "-v", str(catalog) + ":/catalogo:ro", "-v", str(model) + ":/modello:ro", image], check=True)
    switched = False
    try:
        for _attempt in range(30):
            try:
                inventory = request("iusentra-app", f"http://{name}:8092/inventory")
                break
            except subprocess.CalledProcessError:
                time.sleep(1)
        else:
            raise ValueError("Servizio candidato non pronto")
        if (inventory.get("ok") is not True or inventory.get("evidence_scope") != "metadata_only"
            or inventory.get("decisioni") != installed["decisioni"] or inventory.get("relazioni") != installed["relazioni"]):
            raise ValueError("Conteggi diversi dalla copia verificata installata")
        candidate = request("iusentra-app", f"http://{name}:8092/search", {"q": "permesso soggiorno", "semantica": False})
        if candidate != baseline:
            raise ValueError("Ricerca di controllo diversa: collegamento preservato")
        subprocess.run(["docker", "network", "disconnect", network, old_name], check=True)
        switched = True
        subprocess.run(["docker", "network", "disconnect", network, name], check=True)
        subprocess.run(["docker", "network", "connect", "--alias", "openga-search", network, name], check=True)
        proof = request("iusentra-app", "http://openga-search:8092/inventory")
        if proof != inventory:
            raise ValueError("Inventario applicativo non corrispondente")
        subprocess.run(["docker", "stop", old_name], check=True)
        print("INVENTARIO_SERVER_JSON=" + json.dumps({"commit": sha, "inventario": proof,
              "catalogo_riusato": True, "modello_riusato": True, "ricerca_rapida_invariata": True,
              "ripristino": old_name, "training": False}))
    except Exception:
        if switched:
            subprocess.run(["docker", "network", "disconnect", network, name], check=False)
            subprocess.run(["docker", "network", "connect", "--alias", "openga-search", network, old_name], check=True)
        subprocess.run(["docker", "stop", name], check=False)
        raise


if __name__ == "__main__":
    run(sys.argv[1])
