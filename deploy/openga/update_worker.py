"""Aggiornamento del servizio pubblico con riuso di dati e pesi."""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if __package__:
    from .verify_reading import expected_unavailability
else:
    from verify_reading import expected_unavailability


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




def verify_sources(repo, container):
    paths = ["pct/openga_catalogo.py", "pct/openga_query.py", "pct/openga_reranker.py",
             "pct/openga_riformulazione.py", "pct/openga_search.py", "pct/openga_identita.py",
             "pct/__init__.py", "server.py"]
    code = ("import pathlib,hashlib,json,sys;paths=json.loads(sys.argv[1]);"
            "print(json.dumps({p:hashlib.sha256((pathlib.Path('/app')/p).read_bytes()).hexdigest() for p in paths}))")
    actual = json.loads(command("docker", "exec", container, "python", "-c", code, json.dumps(paths)))
    expected = {p: hashlib.sha256((repo / ("deploy/openga/server.py" if p == "server.py" else p)).read_bytes()).hexdigest()
                for p in paths}
    if actual != expected:
        raise ValueError("Sorgenti del servizio diversi dalla revisione verificata")
    print("PARITA_SORGENTI_OPENGA_JSON=" + json.dumps(expected))

def verify_reading(repo, container):
    # Include the exact regression cases: joined proceedings and legacy XML.
    cases = [("003", "202300001", "202212886"),
             ("003", "202006342", "201910229"),
             ("015", "201900341", "201800345")]
    code = ("import sqlite3,json,sys;c=sqlite3.connect('file:/catalogo/catalogo.db?mode=ro',uri=True);"
            "cases=json.loads(sys.argv[1]);"
            "query='SELECT a.relazione,a.risorsa,s.sha256 FROM attive a JOIN risorse s "
            "ON s.id=a.risorsa WHERE a.sede=? AND a.numero=? AND a.ricorso=? LIMIT 1';"
            "rows=[c.execute(query,case).fetchone() for case in cases];"
            "assert all(rows),'Caso pubblico di collaudo assente';"
            "print(json.dumps([dict(zip(('relazione_id','resource_id','resource_sha256'),r)) for r in rows]))")
    selected = json.loads(command("docker", "exec", container, "python", "-c", code, json.dumps(cases)))
    if len(selected) != len(cases):
        raise ValueError("Casi di lettura incompleti")
    proofs = []
    readings = set()
    for reference in selected:
        identity = request("iusentra-app", f"http://{container}:8092/document-identity", reference)
        if identity.get("ok") is not True:
            raise ValueError("Identità della lettura non riscontrata nel servizio")
        try:
            result = subprocess.run(["docker", "exec", "-i", "iusentra-app", "python", "-",
                                     json.dumps(identity["identita"]), json.dumps(reference)],
                                    input=(repo / "deploy/openga/verify_reading.py").read_text(),
                                    text=True, capture_output=True, check=True, timeout=180)
        except subprocess.CalledProcessError as exc:
            # This subprocess reads only a public decision in a temporary queue.
            # Preserve its diagnostic instead of hiding it behind the docker argv.
            detail = (exc.stderr or "").strip()[-4000:] or "Nessuna diagnostica restituita."
            raise RuntimeError(
                f"Verifica lettura pubblica fallita ({reference['relazione_id']}, "
                f"uscita {exc.returncode}):\n{detail}"
            ) from None
        proof = json.loads(result.stdout.strip().splitlines()[-1])
        if proof.get("stato") == "acquisito":
            if (proof.get("caratteri", 0) < 300
                    or proof.get("lettura_confermata") is not True
                    or proof.get("coda_persistente_verificata") is not True
                    or proof.get("html_consultabile_verificato") is not True
                    or proof.get("approvazione_automatica") is not False
                    or proof.get("scritture_dati_studio") is not False):
                raise ValueError("Lettura pubblica e coda non verificate")
            readings.add(reference["relazione_id"])
            print("LETTURA_UFFICIALE_SERVER_JSON=" + json.dumps(proof))
        elif (expected_unavailability(identity["identita"], reference, proof)
                and proof.get("fonte_indisponibile_verificata") is True
                and proof.get("lettura_confermata") is False
                and proof.get("caratteri") == 0
                and proof.get("coda_persistente_verificata") is True
                and proof.get("html_consultabile_verificato") is False
                and proof.get("approvazione_automatica") is False
                and proof.get("scritture_dati_studio") is False):
            print("FONTE_INDISPONIBILE_SERVER_JSON=" + json.dumps(proof))
        else:
            raise ValueError("Lettura pubblica e coda non verificate")
        proofs.append(proof)
    if len(readings) < 2:
        raise ValueError("Almeno due letture pubbliche distinte devono riuscire")
    return proofs

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
                  "COPY pct/openga_catalogo.py pct/openga_query.py pct/openga_reranker.py pct/openga_riformulazione.py /app/pct/\n"
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
        verify_sources(repo, name)
        verify_reading(repo, name)
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
