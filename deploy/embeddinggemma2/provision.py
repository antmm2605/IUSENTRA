"""Preparazione esplicita di soli pesi pubblici ufficiali; nessun dato dello studio."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path


def verified(directory: Path, manifest: dict) -> bool:
    if not directory.exists():
        return False
    files = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    if files != set(manifest["sha256"]) | {"iusentra-manifest.json"}:
        return False
    if json.loads((directory/"iusentra-manifest.json").read_text(encoding="utf-8")) != manifest:
        return False
    for name,digest in manifest["sha256"].items():
        source=(directory/name).resolve()
        if not source.is_relative_to(directory.resolve()):
            return False
        with source.open("rb") as stream:
            if hashlib.file_digest(stream,"sha256").hexdigest()!=digest:
                return False
    return True


def prepare(root: Path) -> Path:
    root=root.resolve()
    root.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(Path(__file__).with_name("model-manifest.json").read_text(encoding="utf-8"))
    target=root/"model"
    if not target.resolve().is_relative_to(root):
        raise ValueError("Destinazione del modello non consentita")
    if verified(target,manifest):
        return target
    # La connessione è consentita solo alla procedura di predisposizione.
    # Il servizio di inferenza rimane offline e su rete interna senza uscite.
    os.environ["HF_HUB_OFFLINE"]="0"
    os.environ["HF_HUB_DISABLE_TELEMETRY"]="1"
    from huggingface_hub import snapshot_download

    source=Path(snapshot_download(
        repo_id="google/embeddinggemma-2",revision=manifest["revision"],
        allow_patterns=list(manifest["sha256"]),cache_dir=str(root/"download-cache"),
        token=False,max_workers=2,
    ))
    if not source.resolve().is_relative_to((root/"download-cache").resolve()):
        raise ValueError("Cache del modello non consentita")
    staging=root/("preparing-"+uuid.uuid4().hex)
    staging.mkdir()
    for name in manifest["sha256"]:
        path=staging/name
        path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/name,path)
        path.chmod(0o644)
    (staging/"iusentra-manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    if not verified(staging,manifest):
        raise ValueError("Pesi scaricati non corrispondenti alle impronte ufficiali")
    if not target.resolve().is_relative_to(root) or not staging.resolve().is_relative_to(root):
        raise ValueError("Destinazione del modello non consentita")
    if target.exists():
        preserved=root/("previous-"+uuid.uuid4().hex)
        target.rename(preserved)  # Conservare la copia precedente, anche se incompleta.
    staging.rename(target)
    return target


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    args=parser.parse_args()
    print(prepare(args.root))
