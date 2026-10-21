"""Installa nel sidecar Ollama il modello Lex verificato sul PC e configura il prossimo deploy.

Uso (sul server, come root): python3 install_lex_modello.py MODELLO DIGEST CARTELLA PREFISSO
Il modello arriva come manifest e blob Ollama in un tar diviso in parti (<PREFISSO>.tar.partNN) nella CARTELLA;
si installa solo se il digest del manifest coincide con quello accettato sul PC (deploy/hetzner/lex_modello.json).
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

def configuration(args):
    if len(args) != 4:
        raise ValueError("Servono modello, digest, cartella e prefisso")
    model, expected, folder, prefix = args
    if not re.fullmatch(r"[a-z0-9-]+:[a-z0-9.]+", model):
        raise ValueError("Nome modello non valido")
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or not re.fullmatch(r"[a-z0-9-]+", prefix):
        raise ValueError("Digest o prefisso non valido")
    if not Path(folder).is_absolute():
        raise ValueError("La cartella deve essere assoluta")
    return model, expected, folder, prefix


def valid_member(member, manifest):
    return member.isfile() and (
        member.name == manifest or re.fullmatch(r"blobs/sha256-[0-9a-f]{64}", member.name) is not None
    )


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    MODEL, DIGEST, CARTELLA, PREFISSO = configuration(sys.argv[1:])
    NOME, TAG = MODEL.split(":")
    MANIFEST = f"manifests/registry.ollama.ai/library/{NOME}/{TAG}"
    folder = Path(CARTELLA)
    repo = Path("/opt/iusentra/repo")
    compose = ["docker", "compose", "--env-file", "/opt/iusentra/.env.hetzner", "-f", str(repo / "deploy/hetzner/docker-compose.hetzner.yml")]
    container = run(*compose, "ps", "-q", "ollama")
    assert container and "\n" not in container, "Serve un unico sidecar Ollama attivo"
    # La lettura HTTP avviene dall'app sulla rete privata Compose.
    probe = "import json,urllib.request; print(urllib.request.urlopen('http://ollama:11434/api/tags').read().decode())"
    tags = json.loads(run(*compose, "exec", "-T", "app", "python", "-c", probe))
    installed = next((x for x in tags["models"] if x["name"] == MODEL), None)
    if not installed or installed.get("digest") != DIGEST:
        with tempfile.TemporaryDirectory(prefix=PREFISSO + "-", dir=folder) as temporary:
            temp = Path(temporary)
            archive_path = temp / "model.tar"
            with archive_path.open("wb") as target:
                for part in sorted(folder.glob(PREFISSO + ".tar.part*")):
                    with part.open("rb") as source:
                        shutil.copyfileobj(source, target, 8 * 1024 * 1024)
            with tarfile.open(archive_path) as archive:
                members = archive.getmembers()
                assert all(valid_member(m, MANIFEST) for m in members)
                assert len({m.name for m in members}) == len(members), "Membri duplicati nell'archivio"
                assert len(members) <= 20 and sum(m.size for m in members) < 7_000_000_000
                for member in members:
                    target = temp / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output, 8 * 1024 * 1024)
            assert digest(temp / MANIFEST) == DIGEST, "Manifest diverso dal modello accettato sul PC"
            manifest = json.loads((temp / MANIFEST).read_text())
            references = [manifest["config"]] + manifest["layers"]
            assert all(re.fullmatch(r"sha256:[0-9a-f]{64}", x["digest"]) and isinstance(x["size"], int) and x["size"] >= 0 for x in references)
            expected = {MANIFEST} | {"blobs/" + x["digest"].replace(":", "-") for x in references}
            assert {m.name for m in members} == expected
            for item in references:
                blob = temp / "blobs" / item["digest"].replace(":", "-")
                assert blob.stat().st_size == item["size"] and digest(blob) == item["digest"].split(":")[1]
            environment = json.loads(run("docker", "inspect", container))[0]["Config"]["Env"]
            model_root = next((x.split("=", 1)[1] for x in environment if x.startswith("OLLAMA_MODELS=")), "/root/.ollama/models")
            assert model_root.startswith("/") and model_root != "/"
            run("docker", "exec", container, "mkdir", "-p", model_root + "/blobs", model_root + "/manifests/registry.ollama.ai/library/" + NOME)
            for item in references:
                name = item["digest"].replace(":", "-")
                run("docker", "cp", str(temp / "blobs" / name), container + ":" + model_root + "/blobs/" + name)
            run("docker", "cp", str(temp / MANIFEST), container + ":" + model_root + "/" + MANIFEST)
    tags = json.loads(run(*compose, "exec", "-T", "app", "python", "-c", probe))
    assert any(x["name"] == MODEL and x.get("digest") == DIGEST for x in tags["models"])
    env_file = Path("/opt/iusentra/.env.hetzner")
    backup = env_file.with_name(".env.hetzner.prima-" + PREFISSO)
    if not backup.exists():
        shutil.copy2(env_file, backup)
        backup.chmod(0o600)
    rows = env_file.read_text().splitlines()
    rows = [row for row in rows if not row.startswith(("PCT_LOCAL_AI_CHAT_MODEL=", "LEX_DEFAULT_MODEL="))]
    rows += ["PCT_LOCAL_AI_CHAT_MODEL=" + MODEL, "LEX_DEFAULT_MODEL=" + MODEL]
    temporary = env_file.with_suffix(".hetzner." + PREFISSO + ".tmp")
    temporary.write_text("\n".join(rows) + "\n")
    temporary.chmod(0o600)
    os.replace(temporary, env_file)
    print(json.dumps({"model": MODEL, "digest": DIGEST, "configured_for_next_deploy": True}))


if __name__ == "__main__":
    main()
