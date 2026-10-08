"""Predisposizione esplicita dei soli pesi pubblici QAT; nessun dato dello studio."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path


def verified(directory: Path, manifest: dict) -> bool:
    if not directory.is_dir():
        return False
    if {p.name for p in directory.iterdir()} != {manifest["file"], "manifest.json"}:
        return False
    try:
        if json.loads((directory / "manifest.json").read_text(encoding="utf-8")) != manifest:
            return False
        source = directory / manifest["file"]
        if source.is_symlink() or source.stat().st_size != manifest["bytes"]:
            return False
        with source.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest() == manifest["sha256"]
    except (OSError, ValueError):
        return False


def prepare(root: Path) -> Path:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(Path(__file__).with_name("litert-model-manifest.json").read_text(encoding="utf-8"))
    target = root / "litert-model"
    if target.is_symlink():
        raise ValueError("Destinazione del modello non consentita")
    if verified(target, manifest):
        return target
    # Soltanto l'installazione esplicita accede al modello pubblico.
    # Il processo applicativo non scarica pesi durante la lettura dei documenti.
    os.environ["HF_HUB_OFFLINE"] = "0"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    from huggingface_hub import hf_hub_download

    source = Path(hf_hub_download(
        repo_id=manifest["repository"], revision=manifest["revision"],
        filename=manifest["file"], cache_dir=str(root / "litert-download-cache"),
        token=False,
    ))
    if not source.resolve().is_relative_to((root / "litert-download-cache").resolve()):
        raise ValueError("Cache del modello non consentita")
    staging = root / ("litert-preparing-" + uuid.uuid4().hex)
    staging.mkdir()
    shutil.copyfile(source, staging / manifest["file"])
    (staging / manifest["file"]).chmod(0o644)
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if not verified(staging, manifest):
        raise ValueError("Pesi LiteRT non corrispondenti alle impronte ufficiali")
    if target.exists():
        target.rename(root / ("litert-previous-" + uuid.uuid4().hex))
    staging.rename(target)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    print(prepare(parser.parse_args().root))
