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
