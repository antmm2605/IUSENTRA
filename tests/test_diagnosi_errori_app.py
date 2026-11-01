"""La diagnosi degli errori dell'app stampa solo lo scheletro dell'eccezione, mai il messaggio."""
import importlib.util
import json
import types
from pathlib import Path

MODULO = Path(__file__).resolve().parents[1] / "deploy" / "hetzner" / "diagnosi_errori_app.py"

LOG = """2026-11-01 ERROR web: Exception on /api/v1/ui/fascicoli/87E6AAA6/dettaglio [GET]
Traceback (most recent call last):
  File "/app/web/services/discordanze_letture_runtime.py", line 118, in riepilogo_discordanze
    result = repo.aperte(tenant,page=page)
  File "/usr/local/lib/python3.12/sqlite3/dbapi.py", line 5, in execute
sqlite3.OperationalError: database is locked per Mario Rossi
"""


def _carica():
    spec = importlib.util.spec_from_file_location("diagnosi_errori_app", MODULO)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_scheletro_senza_messaggio_e_senza_identificativi(monkeypatch, capsys):
    modulo = _carica()
    monkeypatch.setattr(modulo.subprocess, "run", lambda *a, **k: types.SimpleNamespace(stdout=LOG))
    monkeypatch.setenv("SERVIZI", "app")
    monkeypatch.delenv("FILTRO", raising=False)
    modulo.main()
    uscita = capsys.readouterr().out
    assert "Mario Rossi" not in uscita and "database is locked" not in uscita and "87E6AAA6" not in uscita
    prima = json.loads(uscita.splitlines()[0])
    assert prima["eccezione"] == "OperationalError"
    assert prima["rotta"] == "/api/v1/ui/fascicoli/<id>/dettaglio"
    assert prima["frames"][0] == "web/services/discordanze_letture_runtime.py:118 riepilogo_discordanze"
    assert prima["frames"][1] == "[libreria]/dbapi.py:5 execute"


def test_filtro_esclude_le_altre_firme(monkeypatch, capsys):
    modulo = _carica()
    monkeypatch.setattr(modulo.subprocess, "run", lambda *a, **k: types.SimpleNamespace(stdout=LOG))
    monkeypatch.setenv("SERVIZI", "app")
    monkeypatch.setenv("FILTRO", "nessuna-corrispondenza")
    modulo.main()
    assert json.loads(capsys.readouterr().out.splitlines()[-1]) == {"firme_distinte": 0, "totale": 0}
