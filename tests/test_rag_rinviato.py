"""L'indice semantico che non termina si rimanda: catalogo e presìdi restano consegnati."""

from __future__ import annotations

from types import SimpleNamespace

from web.services import archivio_letture_runtime, catalogo_archivio_runtime, rag_archivio_runtime


def test_rag_lento_non_fa_fallire_il_catalogo(monkeypatch):
    monkeypatch.setattr(catalogo_archivio_runtime, "aggiorna_catalogo_da_archivio", lambda f, registro: {"status": "updated"})

    def lento(fascicolo, registro):
        raise RuntimeError("Indicizzazione semantica del fascicolo non terminata")

    monkeypatch.setattr(rag_archivio_runtime, "aggiorna_rag_da_archivio", lento)
    esito = archivio_letture_runtime._aggiorna_catalogo_sql(SimpleNamespace(id="F-1"), registro=None)
    assert esito["status"] == "updated" and esito["rag"]["status"] == "rinviato"
    monkeypatch.setattr(rag_archivio_runtime, "aggiorna_rag_da_archivio", lambda f, r: {"chunks": 3})
    assert archivio_letture_runtime._aggiorna_catalogo_sql(SimpleNamespace(id="F-1"), registro=None)["rag"] == {"chunks": 3}


def test_la_lettura_consegna_i_frammenti_alla_coda_di_manutenzione(monkeypatch, tmp_path):
    from contextlib import closing
    import sqlite3

    from lex.providers import local_ai_service
    from web.services import document_intelligence_runtime

    rag = SimpleNamespace(
        _connect=lambda: closing(sqlite3.connect(tmp_path / "rag.db")),
        _pending_chunks_count=lambda conn, **kwargs: 3 if kwargs.get("practice_id") == "F-1" else 0,
    )
    repo = SimpleNamespace(backend_kind="sqlite")
    monkeypatch.setattr(local_ai_service, "get_local_ai_service", lambda: rag)
    monkeypatch.setattr(document_intelligence_runtime, "document_ai_tenant_id", lambda: "studio")
    monkeypatch.setattr(document_intelligence_runtime, "build_document_ai_service", lambda: SimpleNamespace(repository=repo))
    monkeypatch.setattr(rag_archivio_runtime, "indicizza_testi_archivio",
                        lambda fascicolo, repository, rag, registro, tenant: {"chunks": 3})
    report = rag_archivio_runtime.aggiorna_rag_da_archivio(SimpleNamespace(id="F-1"), registro=None)
    assert report == {"chunks": 3, "embeddings": {"status": "pending", "pending_remaining": 3}}
