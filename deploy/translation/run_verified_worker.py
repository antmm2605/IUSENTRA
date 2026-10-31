"""Avvio locale senza rete del modello di traduzione fissato e verificato."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import socket
import stat
from pathlib import Path

MODEL_SHA256 = "9f96256500f3fc1ab4d64336b58f52a949a95ad7516b0c229476eef782f9f77b"
ALIAS = "iusentra-traduzione-hymt2-7b-9f962565"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_runtime(directory, manifest):
    directory = directory.resolve(strict=True)
    for name, expected in manifest["files"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Manifesto del motore non valido.")
        item = directory / relative
        if not item.resolve(strict=True).is_relative_to(directory):
            raise ValueError("Collegamento del motore fuori dalla cartella autorizzata.")
        if "link" in expected:
            if not item.is_symlink() or str(item.readlink()) != expected["link"]:
                raise ValueError("Collegamento del motore non corrispondente.")
        elif item.is_symlink() or sha256(item) != expected["sha256"]:
            raise ValueError("Impronta del motore non corrispondente.")
    actual = {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file() or p.is_symlink()}
    if actual != set(manifest["files"]):
        raise ValueError("File del motore inattesi o mancanti.")
    return directory / "llama-server"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--socket", type=Path, default=Path("/run/translation/motore.sock"))
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(Path(__file__).with_name("runtime-b12020-cpu.json").read_text())
    binary = verify_runtime(args.runtime, manifest)
    if args.model.is_symlink() or not args.model.is_file() or sha256(args.model) != MODEL_SHA256:
        raise ValueError("Impronta del modello non corrispondente.")
    if args.verify_only:
        print("MODELLO_E_MOTORE_VERIFICATI", flush=True)
        return
    # Il container deve essere creato con --network none; nessun listener TCP.
    if {p.name for p in Path("/sys/class/net").iterdir()} != {"lo"}:
        raise ValueError("Il traduttore richiede un ambiente senza rete esterna.")
    location = args.socket
    if not location.is_absolute() or len(os.fsencode(location)) > 100:
        raise ValueError("Percorso del socket non valido.")
    location.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = (location.parent / "worker.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    os.set_inheritable(lock.fileno(), True)
    if location.exists():
        if not stat.S_ISSOCK(location.lstat().st_mode):
            raise ValueError("Destinazione del socket occupata.")
        with socket.socket(socket.AF_UNIX) as probe:
            probe.settimeout(1)
            try:
                probe.connect(str(location))
            except ConnectionRefusedError:
                location.unlink()
            else:
                raise ValueError("Un traduttore è già in funzione.")
    os.umask(0o077)
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(args.runtime.resolve())
    env["CUDA_VISIBLE_DEVICES"] = ""
    command = [str(binary), "-m", str(args.model), "--alias", ALIAS, "--host", str(location),
        "--no-webui", "--threads", "4", "--threads-batch", "4", "--parallel", "1",
        "--ctx-size", "4096", "--batch-size", "128", "--ubatch-size", "64",
        "--n-gpu-layers", "0", "--no-context-shift", "--log-disable"]
    os.execve(binary, command, env)


if __name__ == "__main__":
    main()
