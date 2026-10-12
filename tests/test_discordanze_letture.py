"""Guardrail del registro delle discordanze e degli esiti condivisi."""
from pct.registro_letture import RegistroLetture
from pct.discordanze_letture_repository import RegistroDiscordanze


def test_discordanza_unica_isolata_e_audit_idempotente(tmp_path):
    registro = RegistroLetture(tmp_path / "registro.db")
    repo = RegistroDiscordanze(registro)
    voce = {"chiave": "cliente-1", "titolo": "Codice fiscale discordante", "fonti": [{"id": "doc-1"}]}
    repo.riconcilia("studio-a", "f1", "cf_cliente_atto", [voce, voce])
    repo.riconcilia("studio-a", "f1", "cf_cliente_atto", [voce])
    assert repo.aperte("studio-a")["totale"] == 1
    assert repo.aperte("studio-b")["totale"] == 0
    with registro.connection() as c:
        assert c.execute("SELECT COUNT(*) FROM letture_discordanze_audit").fetchone()[0] == 1
    repo.riconcilia("studio-a", "f1", "cf_cliente_atto", [])
    assert repo.aperte("studio-a")["totale"] == 0
    with registro.connection() as c:
        assert c.execute("SELECT stato FROM letture_discordanze").fetchone()[0] == "superata"
        assert c.execute("SELECT COUNT(*) FROM letture_discordanze_audit").fetchone()[0] == 2


def test_lettura_pendente_non_pubblica_esiti_precedenti(tmp_path):
    registro = RegistroLetture(tmp_path / "registro.db")
    repo = RegistroDiscordanze(registro)
    repo.riconcilia("studio-a", "f1", "cf", [{"chiave": "c1"}])
    registro.accoda_evento("studio-a", "f1", forza=False)
    result = repo.aperte("studio-a")
    assert result["totale"] == 0
    assert result["lettureInCorso"] == 1
    assert result["voci"] == []


def test_revisioni_esiti_condivise_e_isolamento(tmp_path):
    repo = RegistroDiscordanze(RegistroLetture(tmp_path / "registro.db"))
    repo.pubblica_esito("studio-a", "f1", {"in_corso": True})
    revision = repo.esito("studio-a", "f1")[1]
    repo.pubblica_esito("studio-a", "f1", {"in_corso": False})
    assert repo.esito("studio-a", "f1")[1] != revision
    assert repo.esito("studio-b", "f1") == ({}, "")


def test_paginazione_non_perde_il_totale(tmp_path):
    repo = RegistroDiscordanze(RegistroLetture(tmp_path / "registro.db"))
    repo.riconcilia("studio-a", "f1", "cf", [{"chiave": str(n)} for n in range(7)])
    first = repo.aperte("studio-a", page=1, limit=3)
    second = repo.aperte("studio-a", page=2, limit=3)
    last = repo.aperte("studio-a", page=3, limit=3)
    assert first["totale"] == second["totale"] == last["totale"] == 7
    assert first["altre"] and second["altre"] and not last["altre"]
    assert len({v["chiave"] for page in (first, second, last) for v in page["voci"]}) == 7


def test_riferimenti_sql_prevalgono_su_payload_storico(tmp_path):
    repo = RegistroDiscordanze(RegistroLetture(tmp_path / "registro.db"))
    repo.riconcilia("studio-a", "f1", "giudice_da_fonte",
                   [{"chiave": "giudice", "campo": "giudice"}])
    voce = repo.aperte("studio-a")["voci"][0]
    assert (voce["fascicoloId"], voce["codice"], voce["chiave"]) == ("f1", "giudice_da_fonte", "giudice")
    repo.riconcilia("studio-a", "f1", "giudice_da_fonte",
                   [{"chiave": "giudice", "fascicoloId": "estraneo", "codice": "altro"}])
    voce = repo.aperte("studio-a")["voci"][0]
    assert (voce["fascicoloId"], voce["codice"]) == ("f1", "giudice_da_fonte")
    assert repo.aperte("studio-b")["voci"] == []


def test_giudici_discordanti_pubblicano_confronto_apribile(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from web.services.giudice_fascicolo_runtime import consegna_giudice
    from web.services import registro_letture_runtime
    registro = RegistroLetture(tmp_path / "registro.db")
    facts = [SimpleNamespace(id=f"fatto-{i}", campo="giudice", valore=nome,
                             oggetto_id=f"doc-{i}", sha256=str(i) * 64,
                             contesto=f"Il giudice {nome}", prove=[], verifica="verificata")
             for i, nome in ((1, "Mario Rossi"), (2, "Laura Verdi"))]
    monkeypatch.setattr(registro, "fatti", lambda *a, **kw: facts)
    monkeypatch.setattr(registro_letture_runtime, "registro_corrente", lambda: registro)
    monkeypatch.setattr(registro_letture_runtime, "tenant_corrente", lambda: "studio-a")
    case = SimpleNamespace(id="f1", id_cliente="c1", titolo="Rossi c. Ente",
                           nome_cliente="Rossi Luigi", numero_rg="12", anno_rg="2026",
                           numero="2026/3", giudice="Mario Rossi",
                           documenti=[SimpleNamespace(id=f"doc-{i}", nome=f"Provvedimento {i}.pdf")
                                      for i in (1, 2)])
    result = consegna_giudice(case, facts)
    assert all(r["stato"] == "non_pertinente" for r in result)
    voce = RegistroDiscordanze(registro).aperte("studio-a")["voci"][0]
    assert voce["titolo"] == "Giudice da verificare"
    assert voce["valoreAnagrafica"] == case.giudice == "Mario Rossi"
    assert voce["valoriAtto"] == ["Laura Verdi", "Mario Rossi"]
    assert voce["cliente"] == "Rossi Luigi" and voce["rg"] == "12/2026"
    assert [f["href"] for f in voce["fonti"]] == [
        "/fascicoli/f1/documenti/doc-1/visualizza", "/fascicoli/f1/documenti/doc-2/visualizza"]
    assert len(voce["evidenze"]) == 2


def test_parita_schema_sqlite_postgresql():
    from pathlib import Path
    root = Path(__file__).parents[1] / "pct" / "sql"
    assert (root / "20261002_letture_discordanze.sql").read_bytes() == (root / "20261002_letture_discordanze_postgres.sql").read_bytes()


def test_nome_discordante_con_prova_idempotente_senza_correggere_cliente(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from web.services import discordanze_letture_runtime as runtime
    registro = RegistroLetture(tmp_path / 'registro.db')
    repo = RegistroDiscordanze(registro)
    monkeypatch.setattr(runtime, 'repository', lambda: (repo, 'studio-a'))
    caso = SimpleNamespace(id='f1', id_cliente='c1', titolo='Ricorso', nome_cliente='Rossi Mario',
                           numero_rg='', anno_rg='', numero='2026/1',
                           documenti=[SimpleNamespace(id='d1', nome='Ricorso.pdf')])
    fonte = {'id': 'd1', 'sha256': 'a' * 64, 'valore': 'Rosso Mario', 'citazione': 'Il ricorrente Rosso Mario'}
    runtime.pubblica_discordanza_nome_cliente(caso, caso.nome_cliente, [fonte, fonte])
    prima = repo.aperte('studio-a')['voci'][0]
    runtime.pubblica_discordanza_nome_cliente(caso, caso.nome_cliente, [fonte])
    seconda = repo.aperte('studio-a')['voci'][0]
    assert prima['revisione'] == seconda['revisione']
    assert seconda['valoreAnagrafica'] == 'Rossi Mario'
    assert seconda['valoriAtto'] == ['Rosso Mario']
    assert len(seconda['fonti']) == 1
    assert seconda['fonti'][0]['href'] == '/fascicoli/f1/documenti/d1/visualizza'
    assert caso.nome_cliente == 'Rossi Mario'
    assert repo.aperte('studio-b')['totale'] == 0
    with registro.connection() as c:
        assert c.execute('SELECT COUNT(*) FROM letture_discordanze_audit').fetchone()[0] == 1
    runtime.pubblica_discordanza_nome_cliente(caso, caso.nome_cliente, [{**fonte, 'valore': 'Mario Rossi'}])
    assert repo.aperte('studio-a')['totale'] == 0


def test_nome_discordante_rifiuta_fonti_estranee(tmp_path, monkeypatch):
    import pytest
    from types import SimpleNamespace
    from web.services import discordanze_letture_runtime as runtime
    repo = RegistroDiscordanze(RegistroLetture(tmp_path / 'registro.db'))
    monkeypatch.setattr(runtime, 'repository', lambda: (repo, 'studio-a'))
    caso = SimpleNamespace(documenti=[])
    with pytest.raises(ValueError):
        runtime.pubblica_discordanza_nome_cliente(caso, 'Rossi Mario',
                                                 [{'id': 'altro', 'sha256': 'a' * 64, 'valore': 'Rosso Mario'}])
    assert repo.aperte('studio-a')['totale'] == 0
