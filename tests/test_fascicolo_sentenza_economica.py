from pathlib import Path
from types import SimpleNamespace

from pct.fascicoli import StatoFascicolo
from pct.fascicolo_sentenza_economica import (
    AUTOMATION_KEY,
    ORIGIN,
    SENTENZA_VECTOR_SCHEMA_VERSION,
    SentenzaAutomationOutcome,
    analyze_sentenza_tribunale_text,
    apply_sentenza_tribunale_automation,
)
from pct.fatturazione import GestioneFatturazione, StatoParcella, VoceParcella
from web.services.react_fascicoli_bridge import update_react_fascicolo_payment


SENTENZA_TEXT = """
Tribunale di Palmi
Sentenza n. 230/2024 pubbl. il 07/05/2024
RG n. 1548/2023
condanna il Ministero alla rifusione delle spese di lite sostenute dai ricorrenti
liquidando la complessiva somma di € 1.100,00, oltre ad € 98,00 per spese
(sommatoria di tutti i c.u. versati dai ricorrenti), con maggiorazione di spese
generali ed accessori di legge (iva e cpa) e con distrazione della somma in favore
del difensore dichiaratosi antistatario.
"""


class FakeFascicoliRepository:
    def __init__(self):
        self.fascicolo = SimpleNamespace(
            id="FASC-1",
            id_cliente="CLI-1",
            titolo="Spagnolo Sara c. MIM",
            numero_rg="1548/2023",
            tipo_procedimento="Lavoro",
            valore_causa=0,
            stato=StatoFascicolo.IN_CORSO,
            data_prossima_udienza="n.d.",
            data_chiusura="",
            pagamenti={},
            avanzamento=[],
        )

    def get(self, fascicolo_id: str):
        return self.fascicolo if fascicolo_id == self.fascicolo.id else None

    def aggiorna(self, fascicolo_id: str, **fields):
        if fascicolo_id != self.fascicolo.id:
            raise KeyError(fascicolo_id)
        for key, value in fields.items():
            setattr(self.fascicolo, key, value)
        return self.fascicolo


def test_estrazione_sentenza_tribunale_con_cu_liquidazione_e_fondo_spese():
    extraction = analyze_sentenza_tribunale_text(
        SENTENZA_TEXT + "\nFondo spese riconosciuto pari a € 250,00.",
        {"tipo_documento": "provvedimento Sentenza Tribunale"},
    )

    assert extraction.found is True
    assert extraction.sentence_date == "2024-05-07"
    assert extraction.sentence_number == "230"
    assert extraction.rg_number == "1548"
    assert extraction.liquidazione_importo == 1100.00
    assert extraction.contributo_unificato_importo == 98.00
    assert extraction.fondo_spese_importo == 250.00
    assert extraction.spese_generali is True
    assert extraction.antistatario is True


def test_estrazione_rg_preferisce_intestazione_sentenza():
    text = """
    Nel corpo della motivazione viene richiamato il precedente RG n. 4593/2022.

    Tribunale di Palmi
    Sentenza n. 230/2024 pubbl. il 07/05/2024
    RG n. 1548/2023
    condanna il Ministero liquidando la complessiva somma di € 1.100,00.
    """

    extraction = analyze_sentenza_tribunale_text(
        text,
        {"tipo_documento": "provvedimento Sentenza Tribunale"},
    )

    assert extraction.found is True
    assert extraction.rg_number == "1548"
    assert extraction.rg_year == "2023"


def test_estrazione_sentenza_ufficiale_senza_parola_tribunale():
    text = """
    Firmato Da: CARUSO GIUSEPPE Emesso Da: TRUSTPRO QUALIFIED CA Serial#: 123
    Sentenza n. 376/2026 pubbl. il 13/05/2026
    RG n. 2962/2023
    Sentenza n. cronol. 2516/2026 del 13/05/2026
    P.Q.M. condanna la resistente liquidando la complessiva somma di € 500,00.
    """

    extraction = analyze_sentenza_tribunale_text(text, {})

    assert extraction.found is True
    assert extraction.sentence_number == "376"
    assert extraction.sentence_date == "2026-05-13"
    assert extraction.rg_number == "2962"


def test_estrazione_non_scambia_citazione_cassazione_per_sentenza_fascicolo():
    text = """
    Atto di diffida in riferimento alla sentenza n. 16715/2024 della Corte Suprema
    di Cassazione Sezione Lavoro, pubblicata il 17/06/2024.
    La parte chiede il riconoscimento delle somme dovute.
    """

    extraction = analyze_sentenza_tribunale_text(text, {})

    assert extraction.found is False


def test_applicazione_sentenza_aggiorna_fascicolo_e_crea_una_sola_proforma(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))

    first = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=SENTENZA_TEXT,
        document_metadata={"document_id": "DOC-1", "filename": "sentenza.pdf", "tipo_documento": "Sentenza Tribunale"},
        actor="Lex AI",
    )
    second = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=SENTENZA_TEXT,
        document_metadata={"document_id": "DOC-1", "filename": "sentenza.pdf", "tipo_documento": "Sentenza Tribunale"},
        actor="Lex AI",
    )

    fascicolo = fascicoli.get("FASC-1")
    assert first.applied is True
    assert second.applied is False
    assert second.changes["alreadyProcessed"] is True
    assert second.message == "Sentenza Tribunale già applicata al fascicolo."
    assert fascicolo.data_prossima_udienza == "2024-05-07"
    assert fascicolo.data_chiusura == "2024-05-07"
    assert getattr(fascicolo.stato, "value", fascicolo.stato) == StatoFascicolo.DEFINITO.value
    assert fascicolo.pagamenti["contributo_unificato"]["status"] == "pagato"
    assert fascicolo.pagamenti["contributo_unificato"]["importo"] == 98.00
    assert fascicolo.pagamenti["liquidazione_giudice"]["status"] == "pagato"
    assert fascicolo.pagamenti["liquidazione_giudice"]["importo"] == 1100.00
    assert fascicolo.pagamenti["parcella"]["status"] == "da_emettere"
    assert fascicolo.pagamenti["parcella"]["proforma_id"] == first.proforma_id

    proforme = fatturazione.per_fascicolo("FASC-1")
    assert len(proforme) == 1
    assert proforme[0].numero == "2024/001"
    assert proforme[0].origine == ORIGIN
    assert proforme[0].dati_personalizzati["document"]["documento_operativo"] == "PROFORMA"


def test_documento_duplicato_stessa_sentenza_riusa_proforma_esistente(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))

    first = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=SENTENZA_TEXT,
        document_metadata={"document_id": "DOC-1", "filename": "sentenza.pdf", "tipo_documento": "Sentenza Tribunale"},
        actor="Lex AI",
    )
    duplicate = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=SENTENZA_TEXT,
        document_metadata={"document_id": "DOC-2", "filename": "sentenza-copia.pdf", "tipo_documento": "Sentenza Tribunale"},
        actor="Lex AI",
    )

    automation = fascicoli.get("FASC-1").pagamenti[AUTOMATION_KEY]
    assert first.proforma_id
    assert duplicate.proforma_id == first.proforma_id
    assert duplicate.changes["proformaCreated"] is False
    assert len(fatturazione.per_fascicolo("FASC-1")) == 1
    assert set(automation["processed_documents"]) == {"document_id:DOC-1", "document_id:DOC-2"}
    assert automation["proforme"]["document_id:DOC-2"] == first.proforma_id


def test_numerazione_configurata_e_conversione_proforma(tmp_path: Path):
    manager = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    numbering = manager.configura_numerazione(2024, 15, updated_by="admin")
    assert numbering["prossimoNumero"] == "2024/016"

    proforma = manager.crea(
        id_cliente="CLI-1",
        id_fascicolo="FASC-1",
        data_emissione="2024-05-07",
        voci=[VoceParcella(descrizione="Compenso", prezzo_unitario=100.0)],
        dati_personalizzati={"document": {"documento_operativo": "PROFORMA", "tipo_documento_label": "Proforma"}},
    )
    assert proforma.numero == "2024/016"
    assert manager.carica_numerazione(2024)["prossimoNumero"] == "2024/017"

    manager.cambia_stato(proforma.id, StatoParcella.EMESSA)
    converted = manager.get(proforma.id)
    assert converted.stato == StatoParcella.EMESSA
    assert converted.dati_personalizzati["document"]["documento_operativo"] == "FATTURA"
    assert converted.dati_personalizzati["document"]["tipo_documento_label"] == "Fattura"


def test_pagamento_parcella_fascicolo_marca_proforma_collegata_pagata(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    proforma = fatturazione.crea(
        id_cliente="CLI-1",
        id_fascicolo="FASC-1",
        data_emissione="2024-05-07",
        voci=[VoceParcella(descrizione="Compenso", prezzo_unitario=100.0)],
        dati_personalizzati={"document": {"documento_operativo": "PROFORMA", "tipo_documento_label": "Proforma"}},
    )
    fascicoli.fascicolo.pagamenti = {
        "parcella": {
            "status": "da_emettere",
            "proforma_id": proforma.id,
            "proforma_number": proforma.numero,
            "origine": ORIGIN,
        }
    }

    result, status = update_react_fascicolo_payment(
        get_fascicoli=lambda: fascicoli,
        get_fatturazione=lambda: fatturazione,
        id_fasc="FASC-1",
        kind="parcella",
        payload={"status": "pagato", "dataPagamento": "2024-05-10", "metodo": "Bonifico bancario"},
        actor="Avv. Test",
    )

    updated = fatturazione.get(proforma.id)
    assert status == 200
    assert result["ok"] is True
    assert result["linkedProforma"]["ok"] is True
    assert updated.stato == StatoParcella.PAGATA
    assert updated.data_pagamento == "2024-05-10"
    assert updated.dati_personalizzati["document"]["documento_operativo"] == "FATTURA"
    assert fascicoli.fascicolo.pagamenti["parcella"]["proforma_id"] == proforma.id


def test_sentenza_gia_applicata_alimenta_vector_db_una_sola_volta(tmp_path: Path, monkeypatch):
    from web.services import document_intelligence_runtime as runtime

    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    metadata = {"document_id": "DOC-1", "filename": "sentenza.pdf", "tipo_documento": "Sentenza Tribunale"}
    apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=SENTENZA_TEXT,
        document_metadata=metadata,
        actor="Lex AI",
    )

    class FakeLocalAI:
        def __init__(self):
            self.calls = 0

        def index_text_document(self, **kwargs):
            self.calls += 1
            assert kwargs["source_type"] == "lex_sentenza_tribunale"
            assert kwargs["metadata"]["tipo_documento"] == "sentenza_tribunale"
            assert kwargs["metadata"]["importo_liquidazione"] == 1100.00
            return {"status": "created", "document_id": "rag-sentenza-1", "chunk_count": 2}

        def embed_all_pending_chunks(self, **kwargs):
            assert kwargs["document_id"] == "rag-sentenza-1"
            return {"embedded": 2}

    local_ai = FakeLocalAI()
    monkeypatch.setattr(runtime, "get_fascicoli", lambda: fascicoli)
    monkeypatch.setattr(runtime, "get_fatturazione", lambda: fatturazione)
    monkeypatch.setattr("lex.providers.local_ai_service.get_local_ai_service", lambda: local_ai)

    first = runtime.apply_sentenza_automation_for_document_text(
        fascicolo_id="FASC-1",
        tenant_id="tenant-a",
        document_id="DOC-1",
        text=SENTENZA_TEXT,
        metadata=metadata,
        actor="Lex AI",
    )
    second = runtime.apply_sentenza_automation_for_document_text(
        fascicolo_id="FASC-1",
        tenant_id="tenant-a",
        document_id="DOC-1",
        text=SENTENZA_TEXT,
        metadata=metadata,
        actor="Lex AI",
    )

    vector_key = "document_id:DOC-1"
    vector_state = fascicoli.fascicolo.pagamenti[AUTOMATION_KEY]["vector_indexes"][vector_key]
    assert first["applied"] is False
    assert first["vector_index"]["document_id"] == "rag-sentenza-1"
    assert second["applied"] is False
    assert second["vector_index"]["document_id"] == "rag-sentenza-1"
    assert vector_state["ok"] is True
    assert vector_state["schema_version"] == SENTENZA_VECTOR_SCHEMA_VERSION
    assert local_ai.calls == 1


def test_sentenza_vector_runtime_usa_estratto_compatto():
    from web.services.document_intelligence_runtime import _sentenza_vector_text

    long_text = SENTENZA_TEXT + (" motivazione istruttoria" * 2500)
    extraction = analyze_sentenza_tribunale_text(long_text, {"tipo_documento": "Sentenza Tribunale"})
    fascicolo = SimpleNamespace(
        id="FASC-1",
        titolo="Spagnolo Sara c. MIM",
        numero_rg="1548/2023",
        nome_cliente="Spagnolo Sara",
    )
    outcome = SentenzaAutomationOutcome(applied=False, extraction=extraction, proforma_id="PRO-1")

    vector_text = _sentenza_vector_text(
        extraction,
        fascicolo,
        {"document_id": "DOC-1", "filename": "sentenza.pdf"},
        outcome,
        long_text,
    )

    assert len(vector_text) < 14000
    assert "Estratto sentenza rilevante:" in vector_text
    assert "Sentenza n. 230/2024" in vector_text
    assert "1.100,00" in vector_text
