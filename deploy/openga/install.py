"""Installazione versionata dei soli dati pubblici. Non sostituisce corpus dello studio."""
import argparse
import hashlib
import json
import shutil
import sqlite3
import tarfile
import urllib.request
from pathlib import Path


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def install(bundle, destination, manifests, model_source=None):
    package = json.loads((manifests / "pacchetto.json").read_text())
    catalog = json.loads((manifests / "catalogo-manifest.json").read_text())
    model = json.loads((manifests / "modello-manifest.json").read_text())
    if sha(bundle) != package["sha256"]:
        raise ValueError("Impronta del pacchetto non corrispondente")
    destination = destination.resolve()
    if destination.exists():
        raise ValueError("Destinazione già presente: conservata senza modifiche")
    if shutil.disk_usage(destination.parent).free < 8 * 1024**3:
        raise ValueError("Spazio insufficiente per installazione e ripristino")
    destination.mkdir(mode=0o755)
    public = destination / "catalogo"
    public.mkdir()
    expected = {row["file"]: row for row in catalog["files"]}
    with tarfile.open(bundle) as archive:
        members = archive.getmembers()
        if len(members) != len(expected) or {m.name for m in members} != set(expected):
            raise ValueError("Contenuto del pacchetto non previsto")
        for member in members:
            row = expected[member.name]
            target = public / member.name
            if not member.isfile() or target.resolve().is_relative_to(public) is False or member.size != row["bytes"]:
                raise ValueError("Percorso o dimensione non validi")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as src, target.open("xb") as out:
                shutil.copyfileobj(src, out)
            if sha(target) != row["sha256"]:
                raise ValueError("Dati o indice alterati")
    db = public / "catalogo.db"
    with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as conn:
        if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Catalogo non integro")
        counts = conn.execute("SELECT count(*),count(distinct decisione) FROM attive").fetchone()
        if counts != (catalog["relazioni"], catalog["decisioni"]):
            raise ValueError("Conteggi del catalogo non corrispondenti")
    folder = public / "catalogo.db.vettori-oggetti"
    state = json.loads((folder / "scope.json").read_text())
    if state.get("scope") != "metadata_only" or not state.get("completo") or state["esito"]["righe"] != catalog["unita"]:
        raise ValueError("Perimetro dell'indice non provato")
    # Riscope esplicito solo sulla nuova copia integralmente verificata; originale preservato.
    (destination / "scope-originale.json").write_text(json.dumps(state, indent=2))
    state["provenienza_installazione"] = {"pacchetto_sha256": package["sha256"], "catalogo_sha256": expected["catalogo.db"]["sha256"], "catalogo_originale": state["catalogo"]}
    state["catalogo"] = "/catalogo/catalogo.db"
    (folder / "scope.json").write_text(json.dumps(state, indent=2))
    weights = destination / "modello"
    if model_source:
        model_source = model_source.resolve()
        for row in model["files"]:
            if Path(row["file"]).name != row["file"] or sha(model_source / row["file"]) != row["sha256"]:
                raise ValueError("Modello locale non corrispondente")
        weights.symlink_to(model_source, target_is_directory=True)
    else:
        weights.mkdir()
        for row in model["files"]:
            name = row["file"]
            if Path(name).name != name:
                raise ValueError("Nome del modello non valido")
            url = f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{name}"
            target = weights / name
            with urllib.request.urlopen(url, timeout=120) as src, target.open("xb") as out:
                shutil.copyfileobj(src, out)
            if sha(target) != row["sha256"]:
                raise ValueError("Pesi o configurazione non corrispondenti")
        (weights / "iusentra-model-manifest.json").write_text(json.dumps(model, indent=2))
    report = {"pacchetto_sha256": package["sha256"], "relazioni": counts[0], "decisioni": counts[1], "unita": catalog["unita"], "scope": "metadata_only", "training": False, "originali_modificati": False}
    (destination / "INSTALLATO.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--model-source", type=Path, help="Riusa solo pesi locali con impronte corrispondenti")
    args = parser.parse_args()
    print(json.dumps(install(args.bundle, args.destination, Path(__file__).parent, args.model_source), indent=2))
