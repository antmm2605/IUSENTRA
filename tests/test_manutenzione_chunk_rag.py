"""Il ripasso sui chunk lasciati dallo splitter vecchio.

I test partono da un archivio in cui il chunk gigante c'e' davvero: lo si
scrive a mano, perche' lo splitter di oggi non e' piu' capace di produrlo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pct.local_ai import _RAG_MAX_CHUNK_CHARS, LocalAIService
from pct.manutenzione_chunk_rag import chunk_da_scartare, esamina, rispezza
from tests.test_web_bootstrap import _cfg_web
from web.app import create_app
from web.services.chunk_rag_runtime import esamina_tutti

REPO_ROOT = Path(__file__).resolve().parents[1]

TESTO_ATTO = (
    "TRIBUNALE DI PALMI\n\n"
    "RICORRENTE\n\n"
    "Mario Rossi, rappresentato e difeso dall'avvocato di fiducia.\n\n"
    "FATTO\n\n"
    "Il ricorrente ha prestato attivita' lavorativa alle dipendenze della "
    "societa' convenuta dal gennaio 2019 al marzo 2024.\n\n"
    "DIRITTO\n\n"
    "La domanda e' fondata ai sensi dell'articolo 414 del codice di "
    "procedura civile.\n"
)


def _servizio(tmp_path: Path) -> LocalAIService:
    config_path = tmp_path / "config" / "studio.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({"studio": {"nome": "Studio Test"}, "ai_locale": {"attivo": True}}),
        encoding="utf-8",
    )
    return LocalAIService(
        db_path=str(tmp_path / "intelligence" / "local_ai.db"),
        policy_path=str(REPO_ROOT / "config" / "ai-policy.json"),
        config_path=str(config_path),
        app_root=str(REPO_ROOT),
        models_path=str(tmp_path / "intelligence" / "models"),
    )


def _documento_indicizzato(service: LocalAIService, tmp_path: Path) -> tuple[str, Path]:
    percorso = tmp_path / "documenti" / "ricorso.txt"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(TESTO_ATTO, encoding="utf-8")
    esito = service.index_file(
        source_type="fascicolo_documento",
        source_id="DOC-1",
        practice_id="FASC-1",
        file_path=str(percorso),
        title="Ricorso",
    )
    assert esito["status"] == "indexed"
    return str(esito["document_id"]), percorso


def _scrivi_chunk_gigante(service: LocalAIService, document_id: str, *, caratteri: int) -> str:
    """Lo scrive a mano: e' quello che lo splitter vecchio lasciava."""
    chunk_id = "chunk-storico-gigante"
    with service._connect() as conn:
        conn.execute(
            """
            INSERT INTO rag_chunks (
                id, document_id, practice_id, section_type, ordinal, page_from, page_to,
                token_estimate, text, metadata_json, embedding_state, created_at, updated_at
            ) VALUES (?, ?, 'FASC-1', 'corpo', 99, 1, 1, ?, ?, '{}', 'pending', ?, ?)
            """,
            (
                chunk_id,
                document_id,
                caratteri // 4,
                "parola " * (caratteri // 7),
                "2026-09-01T00:00:00",
                "2026-09-01T00:00:00",
            ),
        )
        conn.commit()
    return chunk_id


def test_esamina_trova_il_chunk_fuori_misura_senza_scrivere(tmp_path: Path):
    service = _servizio(tmp_path)
    document_id, _ = _documento_indicizzato(service, tmp_path)
    _scrivi_chunk_gigante(service, document_id, caratteri=_RAG_MAX_CHUNK_CHARS * 4)

    esito = esamina(service, studio="studio-test")

    assert esito.chunk_da_scartare == 1
    assert esito.documenti_coinvolti == 1
    assert esito.documenti_senza_file == 0
    assert "oltre il limite" in esito.esempi[0]["motivo"]
    with service._connect() as conn:
        rimasti = conn.execute(
            "SELECT COUNT(*) FROM rag_chunks WHERE id = 'chunk-storico-gigante'"
        ).fetchone()[0]
    assert rimasti == 1, "esamina non deve toccare niente"


def test_rispezza_rifa_il_documento_e_il_gigante_sparisce(tmp_path: Path):
    service = _servizio(tmp_path)
    document_id, _ = _documento_indicizzato(service, tmp_path)
    _scrivi_chunk_gigante(service, document_id, caratteri=_RAG_MAX_CHUNK_CHARS * 4)

    esito = rispezza(service, studio="studio-test")

    assert esito.documenti_rifatti == 1
    with service._connect() as conn:
        righe = conn.execute(
            "SELECT id, length(text) AS lunghezza FROM rag_chunks WHERE document_id = ?",
            (document_id,),
        ).fetchall()
    assert righe, "il documento deve restare cercabile"
    assert all(riga["lunghezza"] <= _RAG_MAX_CHUNK_CHARS for riga in righe)
    assert all(riga["id"] != "chunk-storico-gigante" for riga in righe)


def test_rispezza_non_svuota_il_documento_senza_file_di_partenza(tmp_path: Path):
    service = _servizio(tmp_path)
    document_id, percorso = _documento_indicizzato(service, tmp_path)
    _scrivi_chunk_gigante(service, document_id, caratteri=_RAG_MAX_CHUNK_CHARS * 4)
    percorso.unlink()

    esito = rispezza(service, studio="studio-test")

    assert esito.documenti_senza_file == 1
    assert esito.documenti_rifatti == 0
    assert esito.documenti_in_errore == 0
    with service._connect() as conn:
        rimasti = conn.execute(
            "SELECT COUNT(*) FROM rag_chunks WHERE document_id = ?", (document_id,)
        ).fetchone()[0]
    assert rimasti > 0, "senza il file non si tocca niente"


def test_archivio_gia_sano_non_ha_niente_da_rifare(tmp_path: Path):
    service = _servizio(tmp_path)
    _documento_indicizzato(service, tmp_path)

    scarti, totale = chunk_da_scartare(service)

    assert totale > 0, "i chunk appena creati sono in attesa"
    assert scarti == []
    assert rispezza(service, studio="studio-test").documenti_rifatti == 0


def test_documento_che_passa_all_ocr_non_lascia_chunk_orfani(tmp_path: Path, monkeypatch):
    """chunk_count va a zero: i chunk devono sparire davvero."""

    service = _servizio(tmp_path)
    percorso = tmp_path / "documenti" / "scansione.pdf"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_bytes(b"%PDF-1.4 finto")
    monkeypatch.setattr(
        service,
        "_extract_pdf_pages",
        lambda data: [{"page_number": 1, "text": TESTO_ATTO}],
    )
    primo = service.index_file(
        source_type="fascicolo_documento",
        source_id="DOC-SCAN",
        practice_id="FASC-1",
        file_path=str(percorso),
        title="Scansione",
    )
    assert primo["status"] == "indexed"
    document_id = str(primo["document_id"])

    monkeypatch.setattr(
        service,
        "_extract_pdf_pages",
        lambda data: (_ for _ in ()).throw(ValueError("senza testo")),
    )
    secondo = service.index_file(
        source_type="fascicolo_documento",
        source_id="DOC-SCAN",
        practice_id="FASC-1",
        file_path=str(percorso),
        title="Scansione",
        force=True,
    )

    assert secondo["status"] == "needs_ocr"
    with service._connect() as conn:
        rimasti = conn.execute(
            "SELECT COUNT(*) FROM rag_chunks WHERE document_id = ?", (document_id,)
        ).fetchone()[0]
        dichiarati = conn.execute(
            "SELECT chunk_count FROM rag_documents WHERE id = ?", (document_id,)
        ).fetchone()[0]
    assert dichiarati == 0
    assert rimasti == 0, "l'archivio non puo' dire zero chunk e tenerne dentro"


if __name__ == "__main__":
    pytest.main([__file__])


def test_esamina_tutti_guarda_l_archivio_vero_dell_applicazione(tmp_path: Path):
    """Il conteggio deve venire dal database che usa l'app, non da uno ricostruito.

    Il primo tentativo apriva un archivio suo, ricavato dai percorsi a mano, e
    tornava sempre zero mentre i chunk erano tutti al loro posto.
    """

    app = create_app(_cfg_web(tmp_path))
    percorso = tmp_path / "ricorso.txt"
    percorso.write_text(TESTO_ATTO, encoding="utf-8")

    with app.test_request_context("/"):
        from lex.providers.local_ai_service import get_local_ai_service

        servizio = get_local_ai_service()
        esito = servizio.index_file(
            source_type="fascicolo_documento",
            source_id="DOC-APP",
            practice_id="FASC-APP",
            file_path=str(percorso),
            title="Ricorso",
        )
        assert esito["status"] == "indexed"
        _scrivi_chunk_gigante(servizio, str(esito["document_id"]), caratteri=_RAG_MAX_CHUNK_CHARS * 4)

    riepilogo = esamina_tutti(app, rispezzare=False)

    assert riepilogo["errori"] == []
    assert riepilogo["chunk_da_scartare"] == 1, riepilogo["messaggio"]
    assert riepilogo["documenti_coinvolti"] == 1


def _documento_con_chunk_gigante(service: LocalAIService, cartella: Path, numero: int) -> str:
    percorso = cartella / f"atto-{numero}.txt"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(TESTO_ATTO, encoding="utf-8")
    esito = service.index_file(
        source_type="fascicolo_documento",
        source_id=f"DOC-{numero}",
        practice_id="FASC-1",
        file_path=str(percorso),
        title=f"Atto {numero}",
    )
    document_id = str(esito["document_id"])
    with service._connect() as conn:
        conn.execute(
            """
            INSERT INTO rag_chunks (
                id, document_id, practice_id, section_type, ordinal, page_from, page_to,
                token_estimate, text, metadata_json, embedding_state, created_at, updated_at
            ) VALUES (?, ?, 'FASC-1', 'corpo', 99, 1, 1, ?, ?, '{}', 'pending', ?, ?)
            """,
            (
                f"gigante-{numero}",
                document_id,
                _RAG_MAX_CHUNK_CHARS,  # come lo scriveva lo splitter vecchio: ceil(caratteri / 4)
                "parola " * (_RAG_MAX_CHUNK_CHARS * 4 // 7),
                "2026-09-01T00:00:00",
                "2026-09-01T00:00:00",
            ),
        )
        conn.commit()
    return document_id


def test_rispezza_lavora_a_passate_e_dice_quanti_restano(tmp_path: Path):
    """Seimila documenti non stanno in una richiesta HTTP: si va a lotti."""

    service = _servizio(tmp_path)
    for numero in range(4):
        _documento_con_chunk_gigante(service, tmp_path / "documenti", numero)

    prima = rispezza(service, studio="studio-test", massimo_documenti=2)

    assert prima.documenti_coinvolti == 4
    assert prima.documenti_rifatti == 2
    assert prima.documenti_restanti == 2, "deve dire quanti ne restano"

    seconda = rispezza(service, studio="studio-test", massimo_documenti=2)

    assert seconda.documenti_rifatti == 2
    assert seconda.documenti_restanti == 0
    assert chunk_da_scartare(service)[0] == [], "dopo le due passate non resta niente da scartare"


def test_rispezza_si_ferma_allo_scadere_del_tempo(tmp_path: Path):
    """Il tetto non e' solo sul numero: su documenti lenti conta il tempo."""

    service = _servizio(tmp_path)
    for numero in range(3):
        _documento_con_chunk_gigante(service, tmp_path / "documenti", numero)

    esito = rispezza(service, studio="studio-test", massimo_documenti=99, budget_secondi=0.0)

    assert esito.documenti_rifatti == 0, "con budget zero non si lavora"
    assert esito.documenti_restanti == 3


def test_rispezza_non_dipende_dal_censimento_completo(tmp_path: Path, monkeypatch):
    """La passata non deve rileggere il testo di tutto l'archivio per partire.

    In produzione quel censimento costa un minuto e mezzo — piu' del tempo che
    il server concede all'intera richiesta — e la prima passata rifece un solo
    documento su seimila.
    """

    import pct.manutenzione_chunk_rag as modulo

    service = _servizio(tmp_path)
    for numero in range(2):
        _documento_con_chunk_gigante(service, tmp_path / "documenti", numero)

    def _vietato(*args, **kwargs):
        raise AssertionError("la rispezzatura non deve passare dal censimento completo")

    monkeypatch.setattr(modulo, "chunk_da_scartare", _vietato)

    esito = modulo.rispezza(service, studio="studio-test")

    assert esito.documenti_rifatti == 2
    assert esito.documenti_restanti == 0


def test_la_via_veloce_dichiara_il_suo_limite(tmp_path: Path):
    """Un chunk senza conteggio token sfugge alla via veloce, non al censimento.

    La rispezzatura si fida di `token_estimate` per non leggere il testo. Se
    quel conteggio manca, il documento non entra nel lotto: lo ritrova
    l'analisi completa, e il validatore lo scarta comunque prima del modello.
    """

    from pct.manutenzione_chunk_rag import documenti_fuori_misura

    service = _servizio(tmp_path)
    document_id, _ = _documento_indicizzato(service, tmp_path)
    with service._connect() as conn:
        conn.execute(
            """
            INSERT INTO rag_chunks (
                id, document_id, practice_id, section_type, ordinal, page_from, page_to,
                token_estimate, text, metadata_json, embedding_state, created_at, updated_at
            ) VALUES ('senza-conteggio', ?, 'FASC-1', 'corpo', 98, 1, 1, 0, ?, '{}', 'pending', ?, ?)
            """,
            (document_id, "x" * (_RAG_MAX_CHUNK_CHARS * 3), "2026-09-01T00:00:00", "2026-09-01T00:00:00"),
        )
        conn.commit()

    assert documenti_fuori_misura(service) == [], "senza conteggio la via veloce non lo vede"
    scarti, _ = chunk_da_scartare(service)
    assert any(s["chunk"] == "senza-conteggio" for s in scarti), "il censimento completo lo trova"
