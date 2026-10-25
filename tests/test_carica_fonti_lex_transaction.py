from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import tarfile
from pathlib import Path

import pytest

INSTALLER = Path(__file__).resolve().parents[1] / "deploy/hetzner/carica_fonti_lex.sh"


def database(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE payload(value TEXT)")
        conn.execute("INSERT INTO payload VALUES (?)", (value,))


def fixture(tmp_path, *, changed_baseline=False):
    home = tmp_path / "installation"
    data = home / "data/normativa"
    database(data / "normattiva.sqlite", "old")
    (data / "codici_leggi.sqlite").write_bytes(b"protected library")
    old_vectors = data / "vettori_normattiva"
    old_vectors.mkdir()
    (old_vectors / "meta.json").write_text('{"righe":1,"origin":"old"}')
    stage = tmp_path / "package"
    database(stage / "normativa/normattiva.sqlite", "new")
    vectors = stage / "normativa/vettori_normattiva"
    vectors.mkdir()
    (vectors / "meta.json").write_text('{"righe":1,"origin":"new"}')
    if changed_baseline:
        (vectors / "CANONICO.json").write_text(json.dumps({"baseline_server_files": {"normativa/vettori_normattiva/meta.json": "0" * 64}}))
    files = [p for p in stage.rglob("*") if p.is_file()]
    (stage / "SHA256SUMS").write_text("".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + str(p.relative_to(stage)) + "\n" for p in files))
    (stage / "PACCHETTO.json").write_text(json.dumps({"conteggi": {"documenti": 1, "articoli": 1, "chunk": 1}, "vettori": {"presente": True, "righe": 1}, "con_jsonl": False, "file": [{"byte": p.stat().st_size} for p in files], "creato": "fixture"}))
    package = tmp_path / "fixture.tar.gz"
    with tarfile.open(package, "w:gz") as archive:
        for p in stage.iterdir():
            archive.add(p, arcname=p.name)
    Path(str(package) + ".sha256").write_text(hashlib.sha256(package.read_bytes()).hexdigest() + "  " + package.name + "\n")
    docker = tmp_path / "docker-fixture"
    docker.write_text("""#!/usr/bin/env python3
import os,sys,sqlite3
from pathlib import Path
args=sys.argv[1:]
with open(os.environ['EVENTS'],'a') as log:log.write(' '.join(args)+chr(10))
if 'ps' in args:print('fixture-container')
if 'exec' in args:
 sys.stdin.read()
 if os.environ.get('FAIL_VERIFY')=='1':sys.exit(19)
 with sqlite3.connect(os.environ['CURRENT_DB']) as c:
  assert c.execute('SELECT value FROM payload').fetchone()[0]=='new'
""")
    docker.chmod(0o755)
    env = dict(os.environ, IUSENTRA_HOME=str(home), DOCKER=str(docker), EVENTS=str(tmp_path / "events"), CURRENT_DB=str(data / "normattiva.sqlite"))
    return home, data, package, env


@pytest.mark.skipif(os.name == "nt", reason="Installer Bash Linux")
@pytest.mark.parametrize("failure,changed_baseline", [(False, False), (True, False), (False, True)])
def test_import_or_rollback_preserves_library_and_independent_backup(tmp_path, failure, changed_baseline):
    home, data, package, env = fixture(tmp_path, changed_baseline=changed_baseline)
    if failure:
        env["FAIL_VERIFY"] = "1"
    result = subprocess.run(["bash", str(INSTALLER), str(package)], env=env, text=True, capture_output=True)
    assert (result.returncode == 0) is (not failure and not changed_baseline), result.stdout + result.stderr
    expected = "old" if failure or changed_baseline else "new"
    with sqlite3.connect(data / "normattiva.sqlite") as conn:
        assert conn.execute("SELECT value FROM payload").fetchone()[0] == expected
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    assert (data / "codici_leggi.sqlite").read_bytes() == b"protected library"
    backup = next((home / "backups").glob("fonti_lex_*")) / "normativa"
    with sqlite3.connect(backup / "normattiva.sqlite") as conn:
        assert conn.execute("SELECT value FROM payload").fetchone()[0] == "old"
    assert (data / "normattiva.sqlite").stat().st_ino != (backup / "normattiva.sqlite").stat().st_ino
    assert json.loads((backup / "vettori_normattiva/meta.json").read_text())["origin"] == "old"
    assert (tmp_path / "events").read_text().count("stop app") >= 1
    if failure:
        assert (tmp_path / "events").read_text().count("stop app") >= 2
    (data / "vettori_normattiva/meta.json").write_text("active changed later")
    assert json.loads((backup / "vettori_normattiva/meta.json").read_text())["origin"] == "old"
