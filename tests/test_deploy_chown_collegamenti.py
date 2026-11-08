"""Il deploy riallinea il proprietario del collaudo senza seguire collegamenti simbolici."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[1] / "deploy" / "hetzner" / "deploy.sh"


def _comando() -> str:
    testo = DEPLOY.read_text(encoding="utf-8")
    trovato = re.search(r"sh -c '(d=/data/intelligence;[^']+)'", testo)
    assert trovato, "comando di riallineamento del collaudo non trovato"
    return trovato.group(1)


def _esegui(tmp_path: Path, cartella: Path) -> list[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    registro = tmp_path / "chown.log"
    finto = bin_dir / "chown"
    finto.write_text(f'#!/bin/sh\necho "$@" >> "{registro}"\n', encoding="utf-8")
    finto.chmod(0o755)
    comando = _comando().replace("/data/intelligence", str(cartella))
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}"}
    subprocess.run(["sh", "-c", comando], check=True, env=env)
    return registro.read_text(encoding="utf-8").splitlines() if registro.exists() else []


def test_chown_usa_h_e_salta_il_file_collegato(tmp_path):
    cartella = tmp_path / "intelligence"
    cartella.mkdir()
    bersaglio = tmp_path / "passwd"
    bersaglio.write_text("root:x:0:0", encoding="utf-8")
    (cartella / "collaudo_lettore.json").symlink_to(bersaglio)
    chiamate = _esegui(tmp_path, cartella)
    assert chiamate == [f"-h iusentra {cartella}"]


def test_chown_del_file_regolare(tmp_path):
    cartella = tmp_path / "intelligence"
    cartella.mkdir()
    (cartella / "collaudo_lettore.json").write_text("{}", encoding="utf-8")
    chiamate = _esegui(tmp_path, cartella)
    assert chiamate == [f"-h iusentra {cartella}", f"-h iusentra {cartella}/collaudo_lettore.json"]


def test_cartella_collegata_non_si_tocca(tmp_path):
    vera = tmp_path / "etc"
    vera.mkdir()
    cartella = tmp_path / "intelligence"
    cartella.symlink_to(vera)
    assert _esegui(tmp_path, cartella) == []
