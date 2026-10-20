"""Il worker prepara il testo; soltanto il ciclo tenant-aware interpreta il procedimento."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from pct.registro_letture import Oggetto, RegistroLetture
from pct.registro_letture.repository import RegistroLettureError
from web.services import archivio_letture_runtime as runtime


def test_cache_riepilogo_precedente_non_nasconde_presidi_accodati(tmp_path, monkeypatch):
    from flask import Flask
    from pct.discordanze_letture_repository import RegistroDiscordanze
    from web.services import registro_letture_runtime as registro_runtime
    from web.services.lettura_cache import LetturaPayloadCache, chiave_lettura

    registro = RegistroLetture(tmp_path / "registro.db")
    monkeypatch.setattr(registro_runtime, "registro_corrente", lambda: registro)
    monkeypatch.setattr(registro_runtime, "tenant_corrente", lambda: "studio-a")
    app = Flask(__name__, instance_path=str(tmp_path / "instance"))
    with app.app_context():
        cache = LetturaPayloadCache()
        esiti = RegistroDiscordanze(registro)
        esiti.pubblica_esito("studio-a", "CASE", {"in_corso": False, "esiti": {"pec": {"esaminate": 0}}})
        precedente = chiave_lettura("studio-a", "CASE")
        cache.set(precedente, b'{"ok":true,"lettura":{"verifiche":{"in_corso":false}}}')
        assert cache.get(precedente) is not None
        generation = registro.accoda_evento("studio-a", "CASE", presidi=True)
        pendente = chiave_lettura("studio-a", "CASE")
        assert pendente != precedente and cache.get(pendente) is None
        assert registro.presidi_in_corso("studio-a", "CASE")
        registro.reclama_evento("studio-a", "CASE", "worker")
        attivo = chiave_lettura("studio-a", "CASE")
        assert attivo != pendente and cache.get(attivo) is None
        esiti.pubblica_esito("studio-a", "CASE", {"in_corso": False, "esiti": {"pec": {"esaminate": 1}}})
        registro.concludi_evento("studio-a", "CASE", "worker", generation)
        finale = chiave_lettura("studio-a", "CASE")
        assert finale != precedente and cache.get(finale) is None
        assert not registro.presidi_in_corso("studio-a", "CASE")


def test_presidi_evento_recuperato_preserva_richiesta_e_non_forza_documenti(tmp_path, monkeypatch):
    from pct.registro_letture import RegistroLetture

    registro = RegistroLetture(tmp_path / "presidi.db")
    registro.accoda_evento("studio-a", "CASE", presidi=True)
    assert registro.presidi_in_corso("studio-a", "CASE")
    assert not registro.presidi_in_corso("studio-b", "CASE")
    assert registro.reclama_evento("studio-a", "CASE", "worker-morto") == {
        "generation": 1, "forza": False, "presidi": True,
    }
    with registro.connection() as conn:
        conn.execute("UPDATE letture_eventi SET lease_until=? WHERE tenant_id=?", ("2000-01-01T00:00:00Z", "studio-a"))
    evento = registro.reclama_evento("studio-a", "CASE", "worker-ripreso")
    assert evento == {"generation": 1, "forza": False, "presidi": True}
    assert registro.concludi_evento("studio-a", "CASE", "worker-ripreso", 1, riuscito=False)
    assert registro.presidi_in_corso("studio-a", "CASE")
    assert registro.reclama_evento("studio-a", "CASE", "worker-finale") is None
    deadline = registro.esito_evento("studio-a", "CASE")["available_at"]
    monkeypatch.setattr("pct.registro_letture.repository._adesso", lambda: deadline)
    assert registro.reclama_evento("studio-a", "CASE", "worker-finale") == evento
    assert not registro.concludi_evento("studio-a", "CASE", "worker-finale", 1)
    assert not registro.presidi_in_corso("studio-a", "CASE")


def test_presidi_arrivati_durante_lettura_restano_per_generazione_successiva(tmp_path):
    from pct.registro_letture import RegistroLetture

    registro = RegistroLetture(tmp_path / "presidi.db")
    registro.accoda_evento("studio-a", "CASE")
    assert registro.reclama_evento("studio-a", "CASE", "lettore") == {"generation": 1, "forza": False}
    registro.accoda_evento("studio-a", "CASE", presidi=True)
    assert registro.concludi_evento("studio-a", "CASE", "lettore", 1)
    assert registro.reclama_evento("studio-a", "CASE", "verificatore") == {
        "generation": 2, "forza": False, "presidi": True,
    }


def test_migrazione_presidi_preserva_coda_sqlite_precedente(tmp_path):
    import sqlite3
    from pct.registro_letture import RegistroLetture
    from pct.registro_letture.repository import SCHEMA_SQLITE

    path = tmp_path / "registro-precedente.db"
    schema = SCHEMA_SQLITE.read_text(encoding="utf-8")
    schema = schema.replace("    pending_presidi INTEGER NOT NULL DEFAULT 0,\n", "")
    schema = schema.replace("    claimed_presidi INTEGER NOT NULL DEFAULT 0,\n", "")
    with sqlite3.connect(path) as conn:
        conn.executescript(schema)
        conn.execute("INSERT INTO letture_eventi (id,tenant_id,fascicolo_id,generation,stato,creato_il,aggiornato_il) VALUES (?,?,?,?,?,?,?)", ("old", "studio", "CASE", 7, "pending", "2026-10-12", "2026-10-12"))
    registro = RegistroLetture(path)
    assert registro.reclama_evento("studio", "CASE", "nuovo-worker") == {"generation": 7, "forza": False}
    assert not registro.presidi_in_corso("studio", "CASE")


def test_schema_pec_confermato_non_scrive_sotto_lock_di_altro_processo(tmp_path):
    import sqlite3
    from pct.pec_pipeline import PecAuditRepository, _PEC_AUDIT_SCHEMA_READY

    path = tmp_path / "pec.db"
    PecAuditRepository(path, tenant_id="studio-a")
    _PEC_AUDIT_SCHEMA_READY.clear()
    with sqlite3.connect(path) as concurrent:
        concurrent.execute("BEGIN IMMEDIATE")
        repository = PecAuditRepository(path, tenant_id="studio-a")
        assert repository.tenant_id == "studio-a"
        concurrent.rollback()
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM pec_schema_migrations WHERE version LIKE '%:schema:%'").fetchone()[0] == 1


def test_comando_presidi_accoda_senza_thread_web_o_forzatura_ocr(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from web.services import fascicolo_lettura_verifiche as verifiche
    from web.services import registro_letture_runtime as letture

    registro = RegistroLetture(tmp_path / "presidi.db")
    monkeypatch.setattr(verifiche, "leggi_registro", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(letture, "registro_per_percorsi", lambda _paths: registro)
    monkeypatch.setattr(letture, "tenant_corrente", lambda: "studio-a")
    monkeypatch.setattr(verifiche.threading, "Thread", lambda *_args, **_kwargs: pytest.fail("Nessuna lavorazione nel processo web"))
    assert verifiche.avvia_verifiche_in_background(SimpleNamespace(config={}), "CASE", tenant_slug="studio-a", forza=True)
    assert registro.reclama_evento("studio-a", "CASE", "worker") == {
        "generation": 1, "forza": False, "presidi": True,
    }



def _registro(tmp_path):
    registro = RegistroLetture(str(tmp_path / "registro.db"))
    objects = [Oggetto(tipo="documento", oggetto_id=doc, sha256=sha) for doc, sha in (("DOC", "a" * 64), ("ALTRO", "b" * 64))]
    registro.registra_inventario("studio-a", "CASE", objects)
    for obj in objects:
        registro.segna_letto("studio-a", "CASE", obj, "motore_documenti")
    return registro, objects


def test_ocr_riapre_solo_la_fonte_e_accoda_senza_estrarre_parti(tmp_path, monkeypatch):
    registro, objects = _registro(tmp_path)
    monkeypatch.setattr(runtime, "registro_per_percorsi", lambda _paths: registro)
    monkeypatch.setattr(runtime, "leggi_testo", lambda *args, **kwargs: pytest.fail("nessun fatto senza contesto studio"))
    job = SimpleNamespace(registro_path="registro", tenant_id="studio-a", id_fasc="CASE", id_doc="DOC", hash_sha256="a" * 64)
    assert runtime.registra_lettura_ocr_nell_archivio(job, "REPUBBLICA ITALIANA - sentenza di un'altra causa") == 0
    assert registro.da_leggere("studio-a", "CASE", "motore_documenti") == [objects[0]]
    assert registro.stato_evento("studio-a", "CASE") == "pending"
    assert registro.stato_evento("studio-b", "CASE") == "idle"
    assert registro.fatti("studio-a", "CASE", verifiche=None) == []


def test_ocr_rifiuta_tenant_estraneo_e_versione_sostituita(tmp_path):
    registro, objects = _registro(tmp_path)
    with pytest.raises(RegistroLettureError):
        registro.accoda_testo_ocr("studio-b", "CASE", objects[0])
    with pytest.raises(RegistroLettureError):
        registro.accoda_testo_ocr("studio-a", "CASE", Oggetto(tipo="documento", oggetto_id="DOC", sha256="c" * 64))
    assert registro.da_leggere("studio-a", "CASE", "motore_documenti") == []
    assert registro.stato_evento("studio-a", "CASE") == "idle"


def test_ocr_evento_fallito_non_lascia_lettura_riaperta(tmp_path, monkeypatch):
    registro, objects = _registro(tmp_path)

    def fail(*_args):
        raise RuntimeError("evento non confermato")

    monkeypatch.setattr(registro, "_accoda_evento_conn", fail)
    with pytest.raises(RuntimeError, match="evento non confermato"):
        registro.accoda_testo_ocr("studio-a", "CASE", objects[0])
    assert registro.da_leggere("studio-a", "CASE", "motore_documenti") == []
    assert registro.stato_evento("studio-a", "CASE") == "idle"


def test_worker_non_dichiara_consegnato_un_evento_fallito(monkeypatch):
    from pct.ocr_worker import _alimenta_archivio

    def fail(*_args):
        raise RuntimeError("consegna SQL fallita")

    monkeypatch.setattr(runtime, "registra_lettura_ocr_nell_archivio", fail)
    with pytest.raises(RuntimeError, match="consegna SQL fallita"):
        _alimenta_archivio(SimpleNamespace(id=17), "Testo già conservato")


def test_payload_consulta_la_coda_di_un_altro_processo_senza_accodare(tmp_path, monkeypatch):
    registro, _objects = _registro(tmp_path)
    monkeypatch.setattr(runtime, "tenant_corrente", lambda: "studio-a")
    monkeypatch.setattr(runtime, "collaudo_lettore_payload", lambda: {"eseguito": False})
    fascicolo = SimpleNamespace(id="CASE")

    def stato():
        return runtime.stato_archivio_payload(fascicolo, registro=registro, fatti=[])['lettura_automatica']

    assert stato()["completa"] is True
    assert registro.accoda_evento("studio-a", "CASE") == 1
    assert stato()["in_corso"] is True
    assert stato()["completa"] is False
    assert registro.reclama_evento("studio-a", "CASE", "scheduler") == {"generation": 1, "forza": False}
    assert stato()["in_corso"] is True
    # False significa nessuna nuova generazione da riprendere, non un errore.
    assert registro.concludi_evento("studio-a", "CASE", "scheduler", 1) is False
    assert stato()["in_corso"] is False
    assert stato()["completa"] is True


def test_coda_ocr_persistita_usa_indice_studio_anche_se_produttore_passa_globale(tmp_path, monkeypatch):
    from flask import Flask, g
    from web.services import ocr_runtime

    app = Flask(__name__)
    app.config["MULTI_TENANT"] = True
    indice = tmp_path / "studio-a" / "search" / "index.db"
    coda = ocr_runtime.OCRRuntime(queue_db_path=str(tmp_path / "coda.db"))
    monkeypatch.setattr(ocr_runtime, "_registro_per_job", lambda *_args: ("studio-a", "registro-a"))
    with app.test_request_context("/letture"):
        g.data_paths = {"STUDIO_DB": str(tmp_path / "studio-a" / "studio.db"), "SEARCH_INDEX": str(indice)}
        identifier = coda.enqueue(percorso="documento.pdf", hash_sha256="a" * 64, id_fasc="CASE", id_doc="DOC", nome_doc="documento.pdf", tipo_doc="ATTO", index_path=str(tmp_path / "globale" / "index.db"))
    row = coda.store.conn.execute("SELECT tenant_id,index_path FROM ocr_jobs WHERE id=?", (identifier,)).fetchone()
    assert row["tenant_id"] == "studio-a"
    assert Path(row["index_path"]).resolve() == indice.resolve()


def test_errore_registro_nella_richiesta_non_diventa_job_senza_studio(monkeypatch):
    from flask import Flask
    from web.services.ocr_runtime import _registro_per_job

    def fail():
        raise RuntimeError("registro studio non disponibile")

    monkeypatch.setattr("web.services.registro_letture_runtime.registro_corrente", fail)
    with Flask(__name__).test_request_context("/letture"):
        with pytest.raises(RuntimeError, match="registro studio non disponibile"):
            _registro_per_job("CASE", "DOC", "a" * 64)


def test_deduplicazione_ocr_rispetta_lo_studio_del_job(tmp_path):
    from pct.ocr_jobs import OCRJobStore

    store = OCRJobStore(str(tmp_path / "coda.db"))
    args = dict(percorso="documento.pdf", hash_sha256="a" * 64, id_fasc="CASE", id_doc="DOC", nome_doc="documento.pdf", tipo_doc="ATTO", index_path="indice")
    primo = store.enqueue(**args, tenant_id="studio-a", registro_path="registro-a")
    secondo = store.enqueue(**args, tenant_id="studio-b", registro_path="registro-b")
    assert primo != secondo
    assert store.enqueue(**args, tenant_id="studio-a", registro_path="registro-a") == primo
    assert store.enqueue(**args, tenant_id="studio-b", registro_path="registro-b") == secondo
    assert store.pending_count() == 2
def test_consumer_indicizza_solo_fonti_pendenti(monkeypatch):
    from web.services import archivio_letture_runtime as runtime

    chiamate = []
    stato = {"ready": 2, "errors": 1, "not_indexed": 0, "queued": 0, "stale": 0}

    def riepilogo(fid, **kwargs):
        chiamate.append((fid, kwargs))
        return dict(stato)

    monkeypatch.setattr("web.services.document_intelligence_runtime.build_lex_indexing_summary_payload", riepilogo)
    runtime._indicizza_fonti_pendenti("CASE", "studio-a")
    assert len(chiamate) == 1 and chiamate[0][1]["process"] is False
    stato["stale"] = 1
    runtime._indicizza_fonti_pendenti("CASE", "studio-a")
    assert len(chiamate) == 3
    assert chiamate[-1][1]["process"] is True
    assert chiamate[-1][1]["retry_errors"] is False
    assert chiamate[-1][1]["user_context"]["tenant_slug"] == "studio-a"
    assert chiamate[-1][1]["apply_automations"] is False
