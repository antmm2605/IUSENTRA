import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_openga_catalogo import risorsa
from pct.openga_catalogo import CatalogoOpenGA


def run_cli(tmp_path, *args):
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable, "-m", "tools.ricerca_openga", "permesso", *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_comando_reale_lessicale_e_fallback_esplicito(tmp_path):
    path, manifest = risorsa(
        tmp_path, [{"NUMERO_PROVVEDIMENTO": "1", "NUMERO_RICORSO": "A", "ESITO_PROVVEDIMENTO": "RESPINGE"}]
    )
    db = tmp_path / "catalogo.db"
    catalog = CatalogoOpenGA(db)
    catalog.importa(path, manifest)
    before = db.read_bytes()
    p = run_cli(tmp_path, "--db", str(db), "--limite", "1")
    assert p.returncode == 0, p.stderr
    result = json.loads(p.stdout)
    assert len(result["lessicali"]) == 1 and result["semantici_aggiuntivi"] == []
    assert result["modalita"] == "solo_lessicale"
    p = run_cli(tmp_path, "--db", str(db), "--semantica")
    assert p.returncode == 2, p.stderr
    result = json.loads(p.stdout)
    assert result["errore_semantico"] and len(result["lessicali"]) == 1
    assert db.read_bytes() == before
    p = run_cli(tmp_path, "--db", str(db), "--sede", "inesistente")
    assert p.returncode == 0 and json.loads(p.stdout)["lessicali"] == []


def test_comando_catalogo_assente_non_crea_database(tmp_path):
    db = tmp_path / "assente.db"
    p = run_cli(tmp_path, "--db", str(db))
    assert p.returncode == 1
    assert "assente" in json.loads(p.stdout)["errore"]
    assert not db.exists()


def test_comando_rifiuta_intervallo_invertito(tmp_path):
    db = tmp_path / "assente.db"
    p = run_cli(tmp_path, "--db", str(db), "--dal", "2026", "--al", "2020")
    assert p.returncode == 2 and "non validi" in p.stderr
    assert not db.exists()


def test_lista_unica_preserva_lessicale_se_indice_assente(tmp_path):
    path,manifest=risorsa(tmp_path,[{"NUMERO_PROVVEDIMENTO":"1","NUMERO_RICORSO":"A","ESITO_PROVVEDIMENTO":"RESPINGE"}])
    db=tmp_path/"catalogo.db";catalog=CatalogoOpenGA(db);catalog.importa(path,manifest)
    result=run_cli(tmp_path,"--db",str(db),"--semantica","--lista-unica")
    assert result.returncode==2
    data=json.loads(result.stdout)
    assert len(data["risultati"])==1 and data["errore_semantico"]
    assert data["evidence_scope"]=="metadata_only"


def test_classificatore_non_si_attiva_senza_flag_espliciti(tmp_path):
    db=tmp_path/"assente.db"
    result=run_cli(tmp_path,"--db",str(db),"--reranker-dir",str(tmp_path))
    assert result.returncode==2 and "richiede" in result.stderr
    assert not db.exists()


def test_modello_assente_dichiara_errore_e_conserva_ricerca_lessicale(tmp_path):
    path,manifest=risorsa(tmp_path,[{"NUMERO_PROVVEDIMENTO":"1","NUMERO_RICORSO":"A","ESITO_PROVVEDIMENTO":"RESPINGE"}])
    db=tmp_path/"catalogo.db";CatalogoOpenGA(db).importa(path,manifest)
    result=run_cli(tmp_path,"--db",str(db),"--semantica","--lista-unica","--reranker-dir",str(tmp_path/"modello-assente"))
    assert result.returncode==2
    data=json.loads(result.stdout)
    assert len(data["risultati"])==1 and data["errore_reranker"]
    assert data["modalita"]=="solo_lessicale_fallback_classificatore"
