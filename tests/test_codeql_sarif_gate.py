"""Il presidio sui risultati CodeQL ferma solo cio' che deve fermare.

Il gate «Analyze (python)» e' un controllo richiesto del deploy: se sbaglia in
un senso blocca la produzione senza motivo, se sbaglia nell'altro lascia
passare un avviso grave. Questi test coprono i due errori.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import check_codeql_sarif as gate


def _sarif(risultati: list[dict], regole: list[dict] | None = None) -> dict:
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "CodeQL", "rules": regole or []}},
                "results": risultati,
            }
        ],
    }


def _scrivi(cartella: Path, documento: dict) -> None:
    cartella.mkdir(parents=True, exist_ok=True)
    (cartella / "python.sarif").write_text(json.dumps(documento), encoding="utf-8")


def test_analisi_senza_rilievi_non_ferma(tmp_path: Path) -> None:
    _scrivi(tmp_path, _sarif([]))
    assert gate.main([str(tmp_path)]) == 0


def test_avviso_di_livello_error_ferma(tmp_path: Path) -> None:
    _scrivi(
        tmp_path,
        _sarif(
            [
                {
                    "ruleId": "py/sql-injection",
                    "level": "error",
                    "message": {"text": "Query costruita con dati non fidati"},
                    "locations": [
                        {"physicalLocation": {"artifactLocation": {"uri": "web/x.py"}, "region": {"startLine": 12}}}
                    ],
                }
            ]
        ),
    )
    assert gate.main([str(tmp_path)]) == 1


def test_gravita_alta_ferma_anche_senza_livello_error(tmp_path: Path) -> None:
    documento = _sarif(
        [{"ruleId": "py/weak-crypto", "level": "warning", "message": {"text": "Algoritmo debole"}}],
        regole=[{"id": "py/weak-crypto", "properties": {"security-severity": "8.1"}}],
    )
    _scrivi(tmp_path, documento)
    assert gate.main([str(tmp_path)]) == 1


def test_gravita_sotto_soglia_non_ferma(tmp_path: Path) -> None:
    documento = _sarif(
        [{"ruleId": "py/unused-import", "level": "note", "message": {"text": "Import inutilizzato"}}],
        regole=[{"id": "py/unused-import", "properties": {"security-severity": "2.0"}}],
    )
    _scrivi(tmp_path, documento)
    assert gate.main([str(tmp_path)]) == 0


def test_cartella_senza_sarif_ferma(tmp_path: Path) -> None:
    """Un'analisi che non produce nulla non e' un'analisi pulita: e' un guasto."""
    assert gate.main([str(tmp_path)]) == 1


def test_eccezione_richiede_un_motivo_scritto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    percorso = tmp_path / "eccezioni.json"
    percorso.write_text(json.dumps({"regole_non_bloccanti": [{"id": "py/x"}]}), encoding="utf-8")
    monkeypatch.setattr(gate, "ECCEZIONI", percorso)
    with pytest.raises(SystemExit):
        gate.leggi_eccezioni(percorso)


def _deroghe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, voci: list[dict]) -> None:
    percorso = tmp_path / "eccezioni.json"
    percorso.write_text(json.dumps({"regole_non_bloccanti": voci}), encoding="utf-8")
    monkeypatch.setattr(gate, "ECCEZIONI", percorso)


def _avviso(regola: str, percorso: str) -> dict:
    return {
        "ruleId": regola,
        "level": "error",
        "message": {"text": "x"},
        "locations": [{"physicalLocation": {"artifactLocation": {"uri": percorso}, "region": {"startLine": 7}}}],
    }


def test_eccezione_dichiarata_non_ferma(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _deroghe(tmp_path, monkeypatch, [{"id": "py/path-injection", "motivo": "coperta da path_security"}])
    risultati = tmp_path / "sarif"
    _scrivi(risultati, _sarif([_avviso("py/path-injection", "pct/x.py")]))
    assert gate.main([str(risultati)]) == 0


def test_deroga_limitata_al_file_vale_solo_li(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Una deroga su un file non deve spegnere la regola altrove."""
    _deroghe(
        tmp_path,
        monkeypatch,
        [{"id": "py/url-redirection", "file": "web/bootstrap/soggetti_routes.py", "motivo": "sanificatore non riconosciuto"}],
    )
    coperto = tmp_path / "coperto"
    _scrivi(coperto, _sarif([_avviso("py/url-redirection", "web/bootstrap/soggetti_routes.py")]))
    assert gate.main([str(coperto)]) == 0

    altrove = tmp_path / "altrove"
    _scrivi(altrove, _sarif([_avviso("py/url-redirection", "web/bootstrap/altro_routes.py")]))
    assert gate.main([str(altrove)]) == 1


def test_il_file_delle_eccezioni_del_progetto_e_valido() -> None:
    """Le deroghe reali del progetto sono leggibili, motivate e circoscritte."""
    deroghe = gate.leggi_eccezioni()
    assert isinstance(deroghe, list)
    for deroga in deroghe:
        assert deroga["motivo"], f"deroga «{deroga['id']}» senza motivo"
        assert deroga["file"], f"deroga «{deroga['id']}» non circoscritta a un file"
