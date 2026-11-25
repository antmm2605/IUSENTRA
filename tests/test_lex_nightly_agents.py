from __future__ import annotations

import json
from types import SimpleNamespace

from lex.operational_knowledge import nightly_agents


def test_inventario_notturno_distingue_studi_attivi_e_archivi_incompleti(tmp_path, monkeypatch):
    from pct import tenant

    pec = tmp_path / "casella.json"
    pec.write_text(json.dumps({"msg": {"allegati": [
        {"archivio_membro": "originale.eml"},
        {"path": "allegato.pdf"},
        {},
        None,
    ]}}), encoding="utf-8")
    documenti = tmp_path / "allegati"
    documenti.mkdir()
    (documenti / "documento.txt").write_text("atto", encoding="utf-8")

    class Registro:
        def __init__(self, percorso):
            assert percorso == str(tmp_path / "registro.json")

        def lista(self):
            return [
                SimpleNamespace(slug="alfa", nome="Studio Alfa", stato="ATTIVO"),
                SimpleNamespace(slug="beta", nome="Studio Beta", stato="ATTIVO"),
                SimpleNamespace(slug="sospeso", nome="Studio sospeso", stato="SOSPESO"),
                SimpleNamespace(slug="", nome="Registro incompleto", stato="ATTIVO"),
            ]

        def percorsi_dati(self, slug, *, reconcile_aliases):
            assert not reconcile_aliases and slug != "sospeso"
            if slug == "alfa":
                return {"EMAIL_CASELLA_DB": str(pec), "ALLEGATI": str(documenti)}
            return {"EMAIL_CASELLA_DB": str(tmp_path / "assente.json")}

    monkeypatch.setattr(tenant, "GestioneTenant", Registro)
    config = {"MULTI_TENANT": True, "TENANTS_REGISTRY": str(tmp_path / "registro.json"),
              "LEX_OPERATIONAL_AGENTS_DB": str(tmp_path / "inventario.sqlite")}
    esito = nightly_agents.run_operational_micro_agents(
        config=config,
        agents=[{"agent_id": "email_pec", "paths": ["EMAIL_CASELLA_DB", "ALLEGATI"], "criteria": ["Inventario"]}],
    )
    assert not esito["ok"]
    risultato = esito["results"][0]
    assert risultato["status"] == "da_verificare"
    assert risultato["missing_keys"] == ["ALLEGATI", "EMAIL_CASELLA_DB"]
    alfa, beta = risultato["runs"]
    assert (alfa["tenant_slug"], alfa["status"]) == ("alfa", "ok")
    assert (beta["tenant_slug"], beta["status"]) == ("beta", "da_verificare")
    assert alfa["details"][1]["records"] == 1 and alfa["details"][1]["bytes"] == 4
    assert alfa["details"][2] == {"key": "EMAIL_CASELLA_DB_ALLEGATI", "attachments_total": 3,
                                  "attachments_archived": 1, "attachments_loose": 1,
                                  "attachments_missing_metadata": 1}
    persistito = nightly_agents.load_operational_agents_payload(config=config)
    assert set(persistito["latest"]["email_pec"]) == {"alfa", "beta"}
    assert persistito["runs"] == [alfa, beta]


def test_migrazione_registro_agenti_conserva_eventi_e_ultimo_esito(tmp_path):
    storico = tmp_path / "agenti.json"
    primo = {"agent_id": "email_pec", "tenant_slug": "alfa", "status": "da_verificare"}
    secondo = {**primo, "status": "ok"}
    storico.write_text(json.dumps({
        "latest": {"email_pec": {"alfa": primo}}, "runs": [primo], "generated_at": "2026-11-25T07:00:00Z",
    }), encoding="utf-8")
    repository = nightly_agents.OperationalAgentRunRepository(storico)
    assert repository.latest("email_pec") == {"alfa": primo}
    assert not repository.sqlite_path.exists()
    repository.migra_storico()
    assert repository.sqlite_path.is_file()
    assert repository.load()["generated_at"] == "2026-11-25T07:00:00Z"
    aggiornato = repository.record(secondo)
    assert aggiornato["runs"] == [primo, secondo]
    repository.migra_storico()
    assert repository.latest("email_pec") == {"alfa": secondo}
    assert repository.load()["runs"] == [primo, secondo]


def test_registro_senza_schema_usa_lo_storico_in_sola_lettura(tmp_path):
    import sqlite3

    storico = tmp_path / "agenti.json"
    storico.write_text('{"generated_at":"2026-11-25T07:00:00Z"}', encoding="utf-8")
    percorso = tmp_path / "agenti.sqlite"
    with sqlite3.connect(percorso):
        pass
    repository = nightly_agents.OperationalAgentRunRepository(percorso)
    assert repository.load()["generated_at"] == "2026-11-25T07:00:00Z"
    assert repository.latest() == {}
    with sqlite3.connect(percorso) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []


def test_contatori_archivio_non_scambiano_json_corrotto_per_dati(tmp_path):
    percorso = tmp_path / "archivio.json"
    for testo, atteso in (('{', 0), ('[1,2]', 2), ('{"records":{"a":1,"b":2}}', 2), ('"testo"', 0)):
        percorso.write_text(testo, encoding="utf-8")
        assert nightly_agents._path_probe("ARCHIVIO", percorso)["records"] == atteso


def test_inventario_segnala_l_errore_di_accesso_e_continua(tmp_path, monkeypatch):
    from pathlib import Path

    un_file = tmp_path / "archivio.json"
    un_file.write_text('{"items":[1,2]}', encoding="utf-8")
    illeggibile = tmp_path / "non-leggibile"
    illeggibile.mkdir()
    scansione_originale = Path.rglob

    def scansione(self, pattern):
        if self == illeggibile:
            raise PermissionError("Archivio non leggibile")
        return scansione_originale(self, pattern)

    monkeypatch.setattr(Path, "rglob", scansione)
    esito = nightly_agents.run_operational_micro_agent(
        agent_id="inventario",
        config={"LEX_OPERATIONAL_AGENTS_DB": str(tmp_path / "report.sqlite"),
                "ARCHIVIO": str(un_file), "CARTELLA": str(illeggibile)},
        required_path_keys=["ARCHIVIO", "CARTELLA"],
    )
    assert esito["status"] == "errore" and not esito["ok"]
    integro, errore = esito["runs"][0]["details"]
    assert integro["records"] == 2
    assert errore["status"] == "errore" and "non leggibile" in errore["message"]
    assert esito["missing_keys"] == []


def test_rapporto_usa_la_cartella_dell_archivio_legale(tmp_path, monkeypatch):
    from pathlib import Path

    for name in ("IUSENTRA_LEX_OPERATIONAL_AGENTS_DB", "LEX_OPERATIONAL_AGENTS_DB", "PCT_LEGAL_INTELLIGENCE_DB"):
        monkeypatch.delenv(name, raising=False)
    archivio = tmp_path / "normativa" / "archivio.json"
    assert nightly_agents._db_path({"LEGAL_INTELLIGENCE_DB": str(archivio)}).parent == archivio.parent

    exists = Path.exists
    monkeypatch.setattr(Path, "exists", lambda path: True if path == Path("/data") else exists(path))
    assert nightly_agents._db_path({}).parent == Path("/data/intelligence")
    monkeypatch.setattr(Path, "exists", lambda path: False if path == Path("/data") else exists(path))
    assert nightly_agents._db_path({}).parent == Path("intelligence")


def test_inventario_non_va_oltre_il_limite_degli_allegati(tmp_path, monkeypatch):
    from itertools import repeat
    from pathlib import Path

    allegato = tmp_path / "atto.pdf"
    allegato.write_bytes(b"atto")
    originale = Path.rglob
    monkeypatch.setattr(Path, "rglob",
                        lambda path, pattern: repeat(allegato, 10001) if path == tmp_path else originale(path, pattern))
    esito = nightly_agents._path_probe("ALLEGATI", tmp_path)
    assert esito["partial"] and esito["records"] == 10000 and esito["bytes"] == 40000


def test_preparazione_riservata_al_registro_pdp_configurato(tmp_path, monkeypatch):
    from pct import pdp_penale_workflow

    creati = []
    chiusi = []

    class Registro:
        def __init__(self, path):
            creati.append(path)

        def close(self):
            chiusi.append(True)

    monkeypatch.setattr(pdp_penale_workflow, "PDPPenaleWorkflowRepository", Registro)
    assente = tmp_path / "pdp.sqlite"
    nightly_agents._prepare_known_archive("ALTRO_DB", assente)
    assert not creati
    nightly_agents._prepare_known_archive("PDP_PENALE_DB", assente)
    assert creati == [str(assente)] and chiusi == [True]

    def occupato(_):
        raise OSError("Registro in manutenzione")

    monkeypatch.setattr(pdp_penale_workflow, "PDPPenaleWorkflowRepository", occupato)
    nightly_agents._prepare_known_archive("PDP_PENALE_DB", assente)
    assert not assente.exists()


def test_inventario_ripiega_sulla_configurazione_corrente_se_il_registro_non_si_apre(tmp_path, monkeypatch):
    from pct import tenant

    def non_disponibile(_):
        raise OSError("Registro in manutenzione")

    monkeypatch.setattr(tenant, "GestioneTenant", non_disponibile)
    cfg = {"MULTI_TENANT": True, "TENANTS_REGISTRY": str(tmp_path / "registro.json")}
    destinazioni = nightly_agents._tenant_targets(cfg)
    assert len(destinazioni) == 1 and destinazioni[0].tenant_slug == "default"


def test_contatori_saltano_allegati_senza_riga_documentale(tmp_path):
    archivio = tmp_path / "casella.json"
    archivio.write_text('[null, {"allegati":[{"file":"atto.pdf"}]}]', encoding="utf-8")
    esito = nightly_agents._email_attachment_probe(str(archivio))
    assert esito["attachments_total"] == esito["attachments_loose"] == 1


def test_file_divenuto_illeggibile_non_azzera_il_conteggio_della_cartella(tmp_path, monkeypatch):
    from pathlib import Path

    allegato = tmp_path / "allegato.pdf"
    allegato.write_text("atto", encoding="utf-8")
    stat_originale = Path.stat
    tentativi = []

    def stat(path, *args, **kwargs):
        if path == allegato:
            tentativi.append(path)
            if len(tentativi) == 2:
                raise OSError("File spostato durante l'inventario")
        return stat_originale(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    risultato = nightly_agents._path_probe("ALLEGATI", tmp_path)
    assert risultato["status"] == "presente" and risultato["records"] == 1 and risultato["bytes"] == 0
