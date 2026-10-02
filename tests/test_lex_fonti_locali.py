"""Fonti Normattiva sul PC e sul server: pacchetto, checksum, swap atomico, dry-run, aggiornamento notturno.

Nessuna rete e nessun Docker reale: il comando ``docker`` e' sostituito da uno script finto che registra le chiamate.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

from lex.normativa.normattiva_importer import import_raw_dir
from lex.ricerca_giuridica import indice_vettoriale as iv
from lex.ricerca_giuridica.embedding import EmbedderFinto
from lex.ricerca_giuridica.indice_fts import sincronizza_fts
from tests.test_normattiva_importer import NIR_CODE_XML

RADICE = Path(__file__).resolve().parents[1]
SCRIPT_SH = RADICE / "deploy" / "hetzner" / "carica_fonti_lex.sh"

_spec = importlib.util.spec_from_file_location("lex_normattiva_locale", RADICE / "scripts" / "lex_normattiva_locale.py")
locale = importlib.util.module_from_spec(_spec)
sys.modules["lex_normattiva_locale"] = locale
_spec.loader.exec_module(locale)

NIR_SECONDO = NIR_CODE_XML.replace("Approvazione del testo del Codice civile.", "Approvazione del testo del Codice di procedura civile.").replace(
    "<numDoc>262</numDoc>", "<numDoc>1443</numDoc>"
).replace("Art. 2043.", "Art. 325.").replace("Risarcimento per fatto illecito.", "Termine per proporre appello.").replace(
    "Qualunque fatto doloso o colposo, che cagiona ad altri un danno ingiusto, obbliga chi ha commesso il fatto a risarcire il danno.",
    "Il termine per proporre appello e' di trenta giorni dalla notificazione della sentenza.",
)


def _zip(raw: Path, nome: str, xml: str, entry: str) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    with ZipFile(raw / nome, "w") as z:
        z.writestr(entry, xml.encode("utf-8"))


def _archivio(base: Path, *, vettori: bool = True) -> locale.Percorsi:
    p = locale.Percorsi(base)
    _zip(p.raw, "Codici_XML_ORIGINALE_2026-10-01.zip", NIR_CODE_XML, "RD_1942_262/a.xml")
    stats = import_raw_dir(raw_dir=p.raw, db_path=p.db, jsonl_path=p.jsonl, min_score=0)
    assert stats.errors == 0
    if vettori:
        conn = sqlite3.connect(str(p.db))
        try:
            iv.costruisci_indice(conn, p.vettori, EmbedderFinto())
        finally:
            conn.close()
    return p


@pytest.fixture(params=["gz", "zst"])
def formato(request):
    if request.param == "zst" and shutil.which("zstd") is None:
        pytest.skip("zstd non installato")
    return request.param


# ---------------------------------------------------------------------------------------------- #
# Pacchetto                                                                                       #
# ---------------------------------------------------------------------------------------------- #

def test_pacchetto_contenuto_e_checksum(tmp_path, formato):
    p = _archivio(tmp_path / "pc")
    pacchetto = locale.crea_pacchetto(p, formato=formato)
    assert pacchetto.name.endswith(".tar.zst" if formato == "zst" else ".tar.gz")
    sidecar = pacchetto.with_name(pacchetto.name + ".sha256")
    assert sidecar.read_text().split()[0] == locale.sha256_file(pacchetto)
    meta = locale.controlla_pacchetto(pacchetto)
    assert meta["conteggi"]["documenti"] == 1
    assert meta["conteggi"]["chunk"] >= 3
    assert meta["vettori"]["presente"] and meta["vettori"]["copertura"] == 1.0
    nomi = {f["percorso"] for f in meta["file"]}
    assert "normativa/normattiva.sqlite" in nomi and "normativa/vettori_normattiva/meta.json" in nomi
    assert not any(n.endswith(".jsonl") for n in nomi)  # il JSONL si include solo con --con-jsonl


def test_pacchetto_corrotto_viene_rifiutato(tmp_path):
    p = _archivio(tmp_path / "pc")
    pacchetto = locale.crea_pacchetto(p, formato="gz")
    dati = bytearray(pacchetto.read_bytes())
    dati[len(dati) // 2] ^= 0xFF
    pacchetto.write_bytes(bytes(dati))
    with pytest.raises(ValueError):
        locale.controlla_pacchetto(pacchetto)


def test_pacchetto_senza_vettori_o_con_vettori_incompleti(tmp_path):
    p = _archivio(tmp_path / "pc", vettori=False)
    with pytest.raises(RuntimeError, match="vettoriale assente"):
        locale.crea_pacchetto(p, formato="gz")
    senza = locale.crea_pacchetto(p, formato="gz", con_vettori=False)
    assert locale.controlla_pacchetto(senza)["vettori"] == {"presente": False}

    conn = sqlite3.connect(str(p.db))
    try:
        iv.costruisci_indice(conn, p.vettori, EmbedderFinto(), massimo=1)
    finally:
        conn.close()
    with pytest.raises(RuntimeError, match="incompleto"):
        locale.crea_pacchetto(p, formato="gz", destinazione=tmp_path / "altro")
    ok = locale.crea_pacchetto(p, formato="gz", destinazione=tmp_path / "altro", consenti_parziale=True)
    assert locale.controlla_pacchetto(ok)["vettori"]["copertura"] < 1


def test_verifica_zip_elimina_quelli_danneggiati(tmp_path):
    raw = tmp_path / "raw"
    _zip(raw, "ok.zip", NIR_CODE_XML, "a.xml")
    (raw / "rotto.zip").write_bytes(b"PK\x03\x04non e' uno zip")
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"items": [
        {"collection_name": "Ok", "output_path": str(raw / "ok.zip"), "sha256": locale.sha256_file(raw / "ok.zip")},
        {"collection_name": "Rotto", "output_path": str(raw / "rotto.zip"), "sha256": "00"},
        {"collection_name": "Assente", "output_path": str(raw / "assente.zip"), "sha256": "00"},
    ]}), encoding="utf-8")
    problemi = locale.verifica_zip_scaricati(raw, manifest)
    assert len(problemi) == 2 and not (raw / "rotto.zip").exists() and (raw / "ok.zip").exists()


def test_verifica_locale_tre_ricerche(tmp_path, monkeypatch):
    monkeypatch.setenv("LEX_RICERCA_SEMANTICA", "0")
    p = _archivio(tmp_path / "pc", vettori=False)
    esiti = locale.esegui_ricerche_di_prova(p.db)
    assert len(esiti) == 3 and esiti[0]["ok"], esiti[0]


# ---------------------------------------------------------------------------------------------- #
# Aggiornamento notturno incrementale                                                              #
# ---------------------------------------------------------------------------------------------- #

def test_notturno_incrementale_senza_duplicati_e_vettori_solo_nuovi(tmp_path):
    p = _archivio(tmp_path / "srv")
    prima = locale.conteggi_db(p.db)
    embedder = EmbedderFinto()

    class Contatore(EmbedderFinto):
        testi = 0

        def embed(self, testi):
            Contatore.testi += len(testi)
            return super().embed(testi)

    # Stesso ZIP: nessun nuovo articolo/chunk, FTS e vettori invariati.
    stats = import_raw_dir(raw_dir=p.raw, db_path=p.db, jsonl_path=p.jsonl, min_score=0)
    assert stats.articles_imported == 0 and stats.chunks_written == 0 and stats.fts_indicizzati == 0
    assert locale.conteggi_db(p.db)["articoli"] == prima["articoli"]
    conn = sqlite3.connect(str(p.db))
    try:
        esito = iv.costruisci_indice(conn, p.vettori, Contatore())
    finally:
        conn.close()
    assert Contatore.testi == 0 and esito.nuovi == 0

    # Arriva un documento nuovo: solo i suoi chunk entrano in FTS e nei vettori.
    _zip(p.raw, "Codici_XML_ORIGINALE_2026-10-02.zip", NIR_SECONDO, "RD_1942_1443/b.xml")
    stats = import_raw_dir(raw_dir=p.raw, db_path=p.db, jsonl_path=p.jsonl, min_score=0)
    dopo = locale.conteggi_db(p.db)
    assert dopo["documenti"] == prima["documenti"] + 1
    nuovi_chunk = dopo["chunk"] - prima["chunk"]
    assert nuovi_chunk > 0 and stats.fts_indicizzati == nuovi_chunk and dopo["chunk_fts"] == dopo["chunk"]
    conn = sqlite3.connect(str(p.db))
    try:
        esito = iv.costruisci_indice(conn, p.vettori, Contatore())
    finally:
        conn.close()
    assert Contatore.testi == nuovi_chunk and esito.nuovi == nuovi_chunk and esito.invariati == prima["chunk"]
    del embedder


def test_comando_notturno_vettori_e_degradazione(tmp_path, monkeypatch, capsys):
    from pct.scheduler import comando_aggiornamento_vettori_normattiva

    monkeypatch.setenv("LEX_VETTORI_NOTTURNO_MASSIMO", "123")
    comando = comando_aggiornamento_vettori_normattiva("/data/normativa/normattiva.sqlite", "/data/normativa/vettori_normattiva")
    assert comando[1:4] == ["-m", "lex.ricerca_giuridica.indice_vettoriale", "aggiorna"]
    assert "--se-disponibile" in comando and "--solo-esistente" in comando and comando[comando.index("--massimo") + 1] == "123"

    p = _archivio(tmp_path / "srv", vettori=False)
    base = ["aggiorna", "--db", str(p.db), "--out", str(p.vettori), "--url", "http://127.0.0.1:9", "--se-disponibile"]
    assert iv.main([*base, "--solo-esistente"]) == 0  # nessun indice: salta
    assert "assente" in capsys.readouterr().out
    assert iv.main(base) == 0  # Ollama spento: degrada senza errore
    assert "Ollama non raggiungibile" in capsys.readouterr().out
    assert iv.main(base[:-1]) == 3  # senza --se-disponibile resta un errore (uso manuale)


def test_scheduler_include_il_passaggio_vettori():
    sorgente = (RADICE / "pct" / "scheduler.py").read_text(encoding="utf-8")
    assert '"normattiva vettori lex"' in sorgente and "comando_aggiornamento_vettori_normattiva(normativa_db" in sorgente
    compose = (RADICE / "deploy" / "hetzner" / "docker-compose.hetzner.yml").read_text(encoding="utf-8")
    assert "LEX_EMBED_MODEL" in compose


# ---------------------------------------------------------------------------------------------- #
# carica_fonti_lex.sh con docker finto                                                             #
# ---------------------------------------------------------------------------------------------- #

DOCKER_FINTO = """#!/usr/bin/env bash
echo "$*" >> "$FAKE_DOCKER_LOG"
case " $* " in
  *" ps "*) echo fakecontainer ;;
  *" exec "*)
    if [ "${FAKE_DOCKER_EXEC_FAIL:-0}" = "1" ]; then echo "controllo finto fallito"; exit 1; fi
    shift_args=("$@")
    for i in "${!shift_args[@]}"; do
      if [ "${shift_args[$i]}" = "python" ]; then
        exec "$TEST_PYTHON" "${shift_args[@]:$((i+1))}"
      fi
    done
    ;;
esac
exit 0
"""


@pytest.fixture()
def server(tmp_path, monkeypatch):
    home = tmp_path / "iusentra"
    data = home / "data"
    (data / "normativa" / "index").mkdir(parents=True)
    (data / "normativa" / "normattiva.sqlite").write_bytes(b"VECCHIO-DB")
    (data / "normativa" / "vettori_normattiva").mkdir()
    (data / "normativa" / "vettori_normattiva" / "meta.json").write_text("{\"vecchio\": true}")
    (data / "normativa" / "normattiva.sqlite-wal").write_bytes(b"wal")
    docker = tmp_path / "bin" / "docker"
    docker.parent.mkdir()
    docker.write_text(DOCKER_FINTO)
    docker.chmod(0o755)
    log = tmp_path / "docker.log"
    ambiente = {
        **os.environ,
        "IUSENTRA_HOME": str(home),
        "IUSENTRA_DATA_DIR": str(data),
        "REPO_DIR": str(home / "repo"),
        "IUSENTRA_ENV_FILE": str(home / ".env"),
        "COMPOSE_FILE": str(home / "compose.yml"),
        "DOCKER": str(docker),
        "FAKE_DOCKER_LOG": str(log),
        "TEST_PYTHON": sys.executable,
        "PYTHONPATH": str(RADICE),
        "FONTI_LEX_DB_CONTAINER": str(data / "normativa" / "normattiva.sqlite"),
        "FONTI_LEX_ATTESA_WORKER_S": "4",
        "LEX_RICERCA_SEMANTICA": "0",
    }
    return {"home": home, "data": data, "log": log, "env": ambiente}


def _lancia(server, *args):
    return subprocess.run(["bash", str(SCRIPT_SH), *args], env=server["env"], capture_output=True, text=True, cwd=str(RADICE))


def _pacchetto(tmp_path, **kw):
    p = _archivio(tmp_path / "pc")
    return locale.crea_pacchetto(p, formato="gz", **kw)


def test_carica_dry_run_non_tocca_nulla(tmp_path, server):
    pacchetto = _pacchetto(tmp_path)
    r = _lancia(server, "--dry-run", str(pacchetto))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[dry-run]" in r.stdout and "compose stop scheduler-worker" in r.stdout
    assert (server["data"] / "normativa" / "normattiva.sqlite").read_bytes() == b"VECCHIO-DB"
    assert not server["log"].exists()  # nessun comando docker eseguito
    assert not list((server["home"]).glob("backups/*"))


def test_carica_checksum_errato_blocca_tutto(tmp_path, server):
    pacchetto = _pacchetto(tmp_path)
    dati = bytearray(pacchetto.read_bytes())
    dati[len(dati) // 2] ^= 0xFF
    pacchetto.write_bytes(bytes(dati))
    r = _lancia(server, str(pacchetto))
    assert r.returncode != 0 and "checksum" in (r.stdout + r.stderr).lower()
    assert (server["data"] / "normativa" / "normattiva.sqlite").read_bytes() == b"VECCHIO-DB"
    assert not server["log"].exists()


def test_carica_sostituisce_con_backup_e_controllo(tmp_path, server):
    pacchetto = _pacchetto(tmp_path)
    r = _lancia(server, str(pacchetto))
    assert r.returncode == 0, r.stdout + r.stderr
    norm = server["data"] / "normativa"
    assert conteggi_ok(norm / "normattiva.sqlite")
    assert (norm / "vettori_normattiva" / "ids.i64").exists()
    wal = norm / "normattiva.sqlite-wal"
    assert not wal.exists() or wal.read_bytes() != b"wal"  # il -wal del vecchio database non deve sopravvivere
    assert not list(norm.glob(".carica_fonti_lex_*")) and not list(norm.glob("*.vecchio_*"))
    backup = next((server["home"] / "backups").glob("fonti_lex_*"))
    assert (backup / "normativa" / "normattiva.sqlite").read_bytes() == b"VECCHIO-DB"
    chiamate = server["log"].read_text().splitlines()
    ordine = [next(i for i, c in enumerate(chiamate) if chiave in c) for chiave in ("stop scheduler-worker", "up -d --no-deps scheduler-worker", "restart app", "exec -T scheduler-worker")]
    assert ordine == sorted(ordine)
    assert "OK archivio Normattiva verificato" in r.stdout


def conteggi_ok(db: Path) -> bool:
    return locale.conteggi_db(db)["documenti"] == 1


def test_carica_ripristina_il_backup_se_il_controllo_fallisce(tmp_path, server):
    pacchetto = _pacchetto(tmp_path)
    server["env"]["FAKE_DOCKER_EXEC_FAIL"] = "1"
    r = _lancia(server, str(pacchetto))
    assert r.returncode != 0
    norm = server["data"] / "normativa"
    assert (norm / "normattiva.sqlite").read_bytes() == b"VECCHIO-DB"
    assert (norm / "vettori_normattiva" / "meta.json").read_text() == "{\"vecchio\": true}"
    chiamate = server["log"].read_text().splitlines()
    assert sum("up -d --no-deps scheduler-worker" in c for c in chiamate) >= 2  # riavviato anche dopo il ripristino
    assert not list(norm.glob(".carica_fonti_lex_*"))


def test_ripristino_manuale_da_backup(tmp_path, server):
    pacchetto = _pacchetto(tmp_path)
    assert _lancia(server, str(pacchetto)).returncode == 0
    backup = next((server["home"] / "backups").glob("fonti_lex_*"))
    r = _lancia(server, "--ripristina", str(backup))
    assert r.returncode == 0, r.stdout + r.stderr
    norm = server["data"] / "normativa"
    assert (norm / "normattiva.sqlite").read_bytes() == b"VECCHIO-DB"
    assert (norm / "vettori_normattiva" / "meta.json").read_text() == "{\"vecchio\": true}"


def test_script_server_sintassi():
    assert subprocess.run(["bash", "-n", str(SCRIPT_SH)]).returncode == 0
    if shutil.which("shellcheck"):
        assert subprocess.run(["shellcheck", str(SCRIPT_SH)], capture_output=True, text=True).returncode == 0


def test_import_solo_vigenza_ignora_zip_di_altra_vigenza(tmp_path):
    p = locale.Percorsi(tmp_path / "srv")
    _zip(p.raw, "Codici_XML_ORIGINALE_2026-10-01.zip", NIR_CODE_XML, "RD_1942_262/a.xml")
    stats = import_raw_dir(raw_dir=p.raw, db_path=p.db, jsonl_path=p.jsonl, min_score=0, solo_vigenza="VIGENTE")
    assert stats.zip_files == 0 and stats.articles_imported == 0
    stats = import_raw_dir(raw_dir=p.raw, db_path=p.db, jsonl_path=p.jsonl, min_score=0, solo_vigenza="ORIGINALE")
    assert stats.zip_files == 1 and stats.articles_imported > 0


def test_scheduler_notturno_usa_la_vigenza_del_pacchetto():
    sorgente = (RADICE / "pct" / "scheduler.py").read_text(encoding="utf-8")
    assert 'os.getenv("IUSENTRA_NORMATTIVA_VIGENZA", "VIGENTE")' in sorgente
    assert sorgente.count("vigenza_normattiva,") == 2  # download (--vigenza) e import (--solo-vigenza)
    assert '"--solo-vigenza",' in sorgente


def test_bundle_ca_normattiva_include_l_intermedio(monkeypatch):
    from lex.normativa import normattiva_client as nc

    monkeypatch.delenv("LEX_NORMATTIVA_CA_BUNDLE", raising=False)
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    percorso = nc.bundle_ca_normattiva()
    contenuto = Path(percorso).read_text(encoding="ascii", errors="ignore")
    intermedio = (nc.CERTIFICATI_INTERMEDI / "globalsign_gcc_r46_ov_tls_ca_2025.pem").read_text(encoding="ascii")
    assert intermedio.strip() in contenuto and contenuto.count("BEGIN CERTIFICATE") > 100
    assert nc.NormattivaClient().session.verify == percorso
    monkeypatch.setenv("LEX_NORMATTIVA_CA_BUNDLE", "/etc/ssl/mio.pem")
    assert nc.bundle_ca_normattiva() == "/etc/ssl/mio.pem"


def test_intermedio_normattiva_valido_e_firmato_da_globalsign_root_r46():
    import subprocess

    import certifi

    pem = RADICE / "lex" / "normativa" / "certificati" / "globalsign_gcc_r46_ov_tls_ca_2025.pem"
    if shutil.which("openssl") is None:
        pytest.skip("openssl non installato")
    esito = subprocess.run(["openssl", "verify", "-CAfile", certifi.where(), str(pem)], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stdout + esito.stderr
