"""Carica un'immagine precostruita solo dopo SHA e spazio verificati.

Il chiamante esegue questo passo dopo il backup preventivo. Nessuna build,
nessuna rimozione di immagini precedenti, nessun avvio di container.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen


def load(url: str, expected: str, revision: str, directory: Path) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("SHA256 dell'archivio obbligatorio")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Revisione Git non valida")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("URL dell'archivio non ammesso")
    directory = directory.resolve(strict=True)
    docker_root = Path(subprocess.check_output(
        ["docker", "info", "--format", "{{.DockerRootDir}}"], text=True).strip())
    # Margine per tar compresso, strati estratti e metadati; nessuna build.
    # Sullo stesso filesystem i due ruoli si sommano.
    budgets = {}
    for path, amount in ((directory, 3 * 1024**3), (docker_root, 7 * 1024**3)):
        device = path.stat().st_dev
        entry = budgets.setdefault(device, [shutil.disk_usage(path).free, 0])
        entry[0] = min(entry[0], shutil.disk_usage(path).free)
        entry[1] += amount
    if any(free < required for free, required in budgets.values()):
        raise ValueError("Spazio insufficiente per il caricamento verificato")
    image = "iusentra-app:" + revision
    with tempfile.TemporaryDirectory(prefix="iusentra-image-", dir=directory) as work:
        archive = Path(work) / "release.tar"
        digest = hashlib.sha256()
        size = 0
        with urlopen(url, timeout=60) as response, archive.open("xb") as output:
            while block := response.read(8 * 1024**2):
                size += len(block)
                if size > 2 * 1024**3:
                    raise ValueError("Archivio oltre il limite previsto di 2 GiB")
                digest.update(block)
                output.write(block)
        if digest.hexdigest() != expected:
            raise ValueError("SHA dell'archivio discordante: immagine non caricata")
        subprocess.run(["docker", "load", "--input", str(archive)], check=True, capture_output=True)
        metadata = json.loads(subprocess.check_output(["docker", "image", "inspect", image], text=True))[0]
        if metadata.get("Config", {}).get("Labels", {}).get("org.opencontainers.image.revision") != revision:
            raise ValueError("Immagine non riferita al commit richiesto")
    return {"image": image, "image_id": metadata["Id"], "archive_sha256": expected,
            "archive_bytes": size, "container_avviati": False, "archivio_temporaneo_rimosso": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(load(os.environ["IUSENTRA_PREBUILT_IMAGE_URL"],
                          os.environ["IUSENTRA_PREBUILT_IMAGE_SHA256"], args.revision, args.directory)))


if __name__ == "__main__":
    main()
