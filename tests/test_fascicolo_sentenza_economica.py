from pathlib import Path
from types import SimpleNamespace

from pct.fascicoli import StatoFascicolo
from pct.fascicolo_sentenza_economica import (
    AUTOMATION_KEY,
    ORIGIN,
    SENTENZA_VECTOR_SCHEMA_VERSION,
    SentenzaAutomationOutcome,
    analyze_sentenza_tribunale_text,
    apply_contributo_unificato_pdf_evidence,
    apply_sentenza_tribunale_automation,
    extract_contributo_unificato_document_evidence,
)
from pct.fatturazione import GestioneFatturazione, StatoParcella, VoceParcella
from web.services.react_fascicoli_bridge import payment_summary_for_fascicolo, update_react_fascicolo_payment


SENTENZA_TEXT = """
Tribunale di Palmi
Sentenza n. 230/2024 pubbl. il 07/05/2024
RG n. 1548/2023
nel procedimento promosso da Spagnolo Sara contro Ministero dell'Istruzione e del Merito
condanna il Ministero alla rifusione delle spese di lite sostenute dai ricorrenti
liquidando la complessiva somma di € 1.100,00, oltre ad € 98,00 per spese
(sommatoria di tutti i c.u. versati dai ricorrenti), con maggiorazione di spese
generali ed accessori di legge (iva e cpa) e con distrazione della somma in favore
del difensore dichiaratosi antistatario.
"""

MONTAGNESE_TEXT = """
N. R.G 697/2025
REPUBBLICA ITALIANA
IN NOME DEL POPOLO ITALIANO
TRIBUNALE ORDINARIO di VICENZA
Il Tribunale, nella persona del Giudice dott. Caterina Neri ha pronunciato la seguente
SENTENZA
nella causa di lavoro di I Grado iscritta al n. r.g. 697/2025 promossa da:
ROBERTA MONTAGNESE (C.F. MNTRRT98P65G791Q), con il patrocinio dell'avv.
MONTAGNESE GIUSEPPE
P.Q.M.
Il Giudice del Lavoro, definitivamente pronunciando:
- condanna il Ministero a costituire in favore di parte ricorrente la Carta elettronica
con accredito/assegnazione della somma pari a complessivi euro 500,00;
- condanna parte resistente alla rifusione delle spese di lite sostenute dalla parte ricorrente
a tale titolo liquidando la complessiva somma di € 321,50, di cui € 21,50 per esborsi,
oltre a spese generali ed accessori di legge (iva e cpa), con distrazione in favore
del difensore antistatario.
Sentenza resa ex art. 127 ter c.p.c.
Vicenza, 23 settembre 2025
Sentenza n. 465/2025 pubbl. il 23/09/2025
RG n. 697/2025
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
    metadata = {
        "tipo_documento": "provvedimento Sentenza Tribunale",
        "contributo_unificato_pdf": {
            "importo": 98.00,
            "filename": "CU.pdf",
            "natura": "pdf_contributo_unificato",
            "label": "Contributo unificato da PDF",
        },
    }
    extraction = analyze_sentenza_tribunale_text(
        SENTENZA_TEXT + "\nFondo spese riconosciuto pari a € 250,00.",
        metadata,
    )
    apply_contributo_unificato_pdf_evidence(extraction, metadata)

    assert extraction.found is True
    assert extraction.sentence_date == "2024-05-07"
    assert extraction.sentence_number == "230"
    assert extraction.rg_number == "1548"
    assert extraction.liquidazione_importo == 1100.00
    assert extraction.contributo_unificato_importo == 98.00
    assert extraction.fondo_spese_importo == 250.00
    assert extraction.spese_generali is True
    assert extraction.antistatario is True


def test_sentenza_non_porta_cu_senza_documento_fascicolo():
    extraction = analyze_sentenza_tribunale_text(
        SENTENZA_TEXT,
        {"tipo_documento": "provvedimento Sentenza Tribunale"},
    )

    assert extraction.found is True
    assert extraction.liquidazione_importo == 1100.00
    assert extraction.contributo_unificato_importo is None
    assert extraction.contributo_unificato_natura == ""


def test_estrazione_contributo_unificato_non_prende_importo_liquidazione():
    text = """
    Firmato Da: CARUSO GIUSEPPE Emesso Da: TRUSTPRO QUALIFIED CA Serial#: 123
    Sentenza n. 2208/2026 pubbl. il 28/04/2026
    RG n. 3685/2026
    condanna il Ministero alla rifusione in favore di parte ricorrente delle spese di lite,
    liquidate in complessivi € 1.100,00 oltre spese generali 15% e accessori di legge,
    oltre rimborso del contributo unificato.
    """

    extraction = analyze_sentenza_tribunale_text(text, {})

    assert extraction.found is True
    assert extraction.liquidazione_importo == 1100.00
    assert extraction.contributo_unificato_importo is None


def test_estrazione_liquidazione_quattro_cifre_senza_punto_migliaia():
    text = """
    Firmato Da: GIUDICE TEST Emesso Da: TRUSTPRO QUALIFIED CA Serial#: 123
    Sentenza n. 588/2025 pubbl. il 04/11/2025
    RG n. 1916/2024
    condanna la resistente alla rifusione delle spese sostenute dalla parte ricorrente
    a tale titolo liquidando la complessiva somma di € 1030,00, oltre a spese
    generali ed accessori di legge.
    """

    extraction = analyze_sentenza_tribunale_text(text, {})

    assert extraction.found is True
    assert extraction.liquidazione_importo == 1030.00


def test_estrazione_liquidazione_preferisce_compensi_professionali_al_totale():
    text = """
    Tribunale di Palmi
    Sentenza n. 10/2026 pubbl. il 01/02/2026
    RG n. 466/2023
    nel procedimento promosso da Rossi Mario contro Ministero dell'Istruzione.
    P.Q.M. condanna al pagamento delle spese processuali che liquida in complessivi
    Euro 2.454,68, di cui Euro 125,00 per spese ed Euro 1.500,00 per compensi
    professionali ed Euro 829,68 per spese generali e accessori.
    """

    extraction = analyze_sentenza_tribunale_text(text, {"tipo_documento": "Sentenza Tribunale"})

    assert extraction.found is True
    assert extraction.liquidazione_importo == 1500.00
    assert extraction.contributo_unificato_importo is None
    assert extraction.spese_esborsi_importo == 125.00


def test_estrazione_sentenza_carta_docente_con_esborsi_senza_prendere_beneficio():
    extraction = analyze_sentenza_tribunale_text(
        MONTAGNESE_TEXT,
        {"tipo_documento": "provvedimento Sentenza Tribunale", "filename": "Sentenza.pdf"},
    )

    assert extraction.found is True
    assert extraction.sentence_date == "2025-09-23"
    assert extraction.sentence_number == "465"
    assert extraction.rg_number == "697"
    assert extraction.liquidazione_importo == 321.50
    assert extraction.contributo_unificato_importo is None
    assert extraction.spese_esborsi_importo == 21.50
    assert extraction.beneficio_cliente_importo == 500.00
    assert extraction.beneficio_cliente_tipo == "carta_docente"
    assert extraction.fondo_spese_importo is None
    assert extraction.spese_generali is True
    assert extraction.antistatario is True


def test_estrazione_sentenza_carta_docente_con_quota_spese_senza_prendere_beneficio():
    text = MONTAGNESE_TEXT.replace("per esborsi", "per spese")

    extraction = analyze_sentenza_tribunale_text(
        text,
        {"tipo_documento": "provvedimento Sentenza Tribunale", "filename": "Sentenza.pdf"},
    )

    assert extraction.found is True
    assert extraction.sentence_date == "2025-09-23"
    assert extraction.rg_number == "697"
    assert extraction.liquidazione_importo == 321.50
    assert extraction.contributo_unificato_importo is None
    assert extraction.spese_esborsi_importo == 21.50
    assert extraction.fondo_spese_importo is None


def test_pdf_contributo_unificato_fornisce_doppia_prova_senza_carta_docente():
    evidence = extract_contributo_unificato_document_evidence(
        "Ricevuta pagamento PagoPA Contributo unificato. Importo versato euro 21,50.",
        {"filename": "CU.pdf", "document_id": "DOC-CU"},
    )
    carta = extract_contributo_unificato_document_evidence(
        "Accredito Carta elettronica docente con importo euro 500,00.",
        {"filename": "Bonifico carta docente.pdf", "document_id": "DOC-CARTA"},
    )

    assert evidence["importo"] == 21.50
    assert evidence["natura"] == "pdf_contributo_unificato"
    assert evidence["document_id"] == "DOC-CU"
    assert carta == {}


def test_pdf_contributo_rifiuta_scaglione_e_riporta_esenzione_cu():
    scaglione = extract_contributo_unificato_document_evidence(
        """
        Ricevuta contributo unificato: si dichiara che il valore della domanda e'
        compreso nello scaglione tra euro 5.200,00 ed euro 26.000,00.
        Il contributo unificato dovuto e versato e' pari ad euro.
        """,
        {"filename": "CU-scaglione.pdf", "document_id": "DOC-CU-SCAGLIONE"},
    )
    esente = extract_contributo_unificato_document_evidence(
        "Contributo unificato non dovuto: parte esente dal pagamento.",
        {"filename": "CU-esente.pdf", "document_id": "DOC-CU-ESENTE"},
    )
    patrocinio = extract_contributo_unificato_document_evidence(
        "Decreto di ammissione al patrocinio a spese dello Stato della parte ricorrente.",
        {"filename": "patrocinio-stato.pdf", "document_id": "DOC-PSS"},
    )

    assert scaglione == {}
    assert esente["esente"] is True
    assert esente["importo"] is None
    assert esente["natura"] == "esenzione_contributo_unificato"
    assert esente["label"] == "Contributo unificato esente"
    assert patrocinio["esente"] is True
    assert patrocinio["importo"] is None


def test_esenzione_cu_da_pdf_viene_salvata_senza_importo_e_senza_voce_proforma(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    metadata = {
        "document_id": "DOC-ESENTE",
        "filename": "sentenza.pdf",
        "tipo_documento": "Sentenza Tribunale",
        "contributo_unificato_pdf": {
            "esente": True,
            "importo": None,
            "titolo": "Contributo unificato non dovuto: parte esente dal pagamento.",
            "filename": "CU-esente.pdf",
            "natura": "esenzione_contributo_unificato",
            "label": "Contributo unificato esente",
        },
    }

    outcome = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=SENTENZA_TEXT,
        document_metadata=metadata,
        actor="Lex AI",
    )

    fascicolo = fascicoli.get("FASC-1")
    cu = fascicolo.pagamenti["contributo_unificato"]
    assert outcome.applied is True
    assert outcome.extraction.contributo_unificato_esente is True
    assert outcome.extraction.contributo_unificato_importo is None
    assert cu["status"] == "non_previsto"
    assert cu["previsto"] is False
    assert cu["importo"] is None
    assert cu["natura"] == "esenzione_contributo_unificato"
    assert cu["label"] == "Contributo unificato esente"
    proforma = fatturazione.per_fascicolo("FASC-1")[0]
    assert all("contributo" not in voce.descrizione.casefold() for voce in proforma.voci)


def test_pdf_contributo_non_sovrascrive_esborsi_sentenza_se_importo_diverge():
    extraction = analyze_sentenza_tribunale_text(
        MONTAGNESE_TEXT,
        {"tipo_documento": "provvedimento Sentenza Tribunale", "filename": "Sentenza.pdf"},
    )

    apply_contributo_unificato_pdf_evidence(
        extraction,
        {
            "contributo_unificato_pdf": {
                "importo": 49.00,
                "filename": "CU.pdf",
                "natura": "pdf_contributo_unificato",
                "label": "Contributo unificato da PDF",
            }
        },
    )

    assert extraction.contributo_unificato_importo == 49.00
    assert extraction.contributo_unificato_natura == "pdf_contributo_unificato"
    assert extraction.contributo_unificato_label == "Contributo unificato da PDF"
    assert extraction.spese_esborsi_importo == 21.50
    assert "contributo_unificato_pdf_distinto_da_spese_sentenza" in extraction.warnings


def test_pdf_contributo_riclassifica_esborsi_identici_senza_duplicarli():
    extraction = analyze_sentenza_tribunale_text(
        MONTAGNESE_TEXT,
        {"tipo_documento": "provvedimento Sentenza Tribunale", "filename": "Sentenza.pdf"},
    )

    apply_contributo_unificato_pdf_evidence(
        extraction,
        {
            "contributo_unificato_pdf": {
                "importo": 21.50,
                "filename": "CU.pdf",
                "natura": "pdf_contributo_unificato",
                "label": "Contributo unificato da PDF",
            }
        },
    )

    assert extraction.contributo_unificato_importo == 21.50
    assert extraction.contributo_unificato_natura == "pdf_contributo_unificato"
    assert extraction.contributo_unificato_label == "Contributo unificato da PDF"
    assert extraction.spese_esborsi_importo is None
    assert "spese_esborsi_riclassificate_cu_pdf" in extraction.warnings
    assert "contributo_unificato_da_pdf" in extraction.warnings


def test_estrazione_sentenza_resa_con_data_testuale_e_rg_iniziale():
    text = """
    N. R.G 697/2025
    TRIBUNALE ORDINARIO di VICENZA
    SENTENZA
    ROBERTA MONTAGNESE contro MINISTERO DELL'ISTRUZIONE E DEL MERITO
    Il Giudice del Lavoro, definitivamente pronunciando:
    condanna parte resistente a tale titolo liquidando la complessiva somma di € 321,50,
    di cui € 21,50 per esborsi, oltre a spese generali ed accessori di legge.
    Sentenza resa ex art. 127 ter c.p.c.
    Vicenza, 23 settembre 2025.
    """

    extraction = analyze_sentenza_tribunale_text(text, {"tipo_documento": "Sentenza Tribunale"})

    assert extraction.found is True
    assert extraction.sentence_date == "2025-09-23"
    assert extraction.sentence_number == ""
    assert extraction.rg_number == "697"
    assert extraction.liquidazione_importo == 321.50
    assert extraction.contributo_unificato_importo is None
    assert extraction.spese_esborsi_importo == 21.50


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
    metadata = {
        "document_id": "DOC-1",
        "filename": "sentenza.pdf",
        "tipo_documento": "Sentenza Tribunale",
        "contributo_unificato_pdf": {
            "importo": 98.00,
            "filename": "CU.pdf",
            "natura": "pdf_contributo_unificato",
            "label": "Contributo unificato da PDF",
        },
    }

    first = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=SENTENZA_TEXT,
        document_metadata=metadata,
        actor="Lex AI",
    )
    second = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=SENTENZA_TEXT,
        document_metadata=metadata,
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


def test_sentenza_gia_processata_completa_esborsi_e_importo_parcella(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fascicoli.fascicolo.titolo = "Montagnese Roberta c. MIM"
    fascicoli.fascicolo.nome_cliente = "Montagnese Roberta"
    fascicoli.fascicolo.numero_rg = "697"
    fascicoli.fascicolo.anno_rg = 2025
    fascicoli.fascicolo.stato = StatoFascicolo.DEFINITO
    fascicoli.fascicolo.data_prossima_udienza = "2025-09-23"
    document_key = "document_id:DOC-MONTAGNESE"
    fascicoli.fascicolo.pagamenti = {
        "liquidazione_giudice": {
            "kind": "liquidazione_giudice",
            "status": "pagato",
            "importo": 321.50,
            "data_pagamento": "2025-09-23",
        },
        "parcella": {
            "kind": "parcella",
            "status": "da_emettere",
            "importo": None,
            "data_pagamento": "2025-09-23",
        },
        AUTOMATION_KEY: {"processed_documents": [document_key], "proforme": {}},
    }
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    proforma = fatturazione.crea(
        id_cliente="CLI-1",
        id_fascicolo="FASC-1",
        data_emissione="2025-09-23",
        voci=[VoceParcella(descrizione="Compensi liquidati in sentenza", prezzo_unitario=321.50)],
        percentuale_spese_generali=15.0,
        origine=ORIGIN,
        dati_personalizzati={
            "document": {"documento_operativo": "PROFORMA", "tipo_documento_label": "Proforma"},
            "lex_sentenza": {"origin": ORIGIN, "document_key": document_key},
        },
    )
    fascicoli.fascicolo.pagamenti[AUTOMATION_KEY]["proforme"][document_key] = proforma.id

    outcome = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=MONTAGNESE_TEXT,
        document_metadata={"document_id": "DOC-MONTAGNESE", "filename": "Sentenza.pdf", "tipo_documento": "Sentenza Tribunale"},
        actor="Lex AI",
    )

    fascicolo = fascicoli.get("FASC-1")
    updated_proforma = fatturazione.get(proforma.id)
    assert outcome.applied is True
    assert "spese_esborsi" in outcome.changes["payments"]
    assert "parcella" in outcome.changes["payments"]
    assert "contributo_unificato" not in fascicolo.pagamenti
    assert fascicolo.pagamenti["spese_esborsi"]["status"] == "pagato"
    assert fascicolo.pagamenti["spese_esborsi"]["importo"] == 21.50
    assert fascicolo.pagamenti["spese_esborsi"]["natura"] == "spese_esborsi"
    assert fascicolo.pagamenti["spese_esborsi"]["label"] == "Spese/esborsi"
    react_payment = payment_summary_for_fascicolo(fascicolo)["items"]["spese_esborsi"]
    assert react_payment["label"] == "Spese/esborsi"
    assert react_payment["displayLabel"] == "Spese/esborsi"
    assert react_payment["natura"] == "spese_esborsi"
    assert fascicolo.pagamenti["parcella"]["importo"] == updated_proforma.totale
    assert any(
        voce.tipo == "ANTICIPO"
        and voce.prezzo_unitario == 21.50
        and "Spese ed esborsi" in voce.descrizione
        for voce in updated_proforma.voci
    )
    assert updated_proforma.dati_personalizzati["lex_sentenza"]["extraction"]["spese_esborsi_importo"] == 21.50


def test_sentenza_strategica_senza_nome_cliente_non_aggiorna_economia(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    sentenza_vicenza_strategica = """
    Tribunale di Vicenza
    Sentenza n. 99/2024 pubbl. il 10/04/2024
    RG n. 1548/2023
    La presente pronuncia viene prodotta come precedente utile alla strategia difensiva.
    Il Tribunale liquidando la complessiva somma di € 2.500,00, oltre rimborso del contributo unificato.
    """

    outcome = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=sentenza_vicenza_strategica,
        document_metadata={"document_id": "DOC-VICENZA", "filename": "Sentenza Tribunale Vicenza.pdf"},
        actor="Lex AI",
    )

    fascicolo = fascicoli.get("FASC-1")
    assert outcome.applied is False
    assert "cliente_non_presente_nella_sentenza" in outcome.warnings
    assert outcome.changes["context"]["cliente_match"] is False
    assert getattr(fascicolo.stato, "value", fascicolo.stato) == StatoFascicolo.IN_CORSO.value
    assert fascicolo.pagamenti == {}
    assert fatturazione.per_fascicolo("FASC-1") == []


def test_sentenza_con_cliente_ma_rg_diverso_non_aggiorna_economia(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    sentenza_altro_rg = """
    Tribunale di Palmi
    Sentenza n. 231/2024 pubbl. il 08/05/2024
    RG n. 9999/2023
    nel procedimento promosso da Spagnolo Sara contro Ministero dell'Istruzione e del Merito
    liquidando la complessiva somma di € 900,00, oltre ad € 49,00 per spese di c.u.
    """

    outcome = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=sentenza_altro_rg,
        document_metadata={"document_id": "DOC-RG-DIVERSO", "filename": "sentenza-altro-rg.pdf"},
        actor="Lex AI",
    )

    assert outcome.applied is False
    assert "rg_sentenza_non_coincidente_con_fascicolo" in outcome.warnings
    assert outcome.changes["context"]["rg_match"] is False
    assert fascicoli.get("FASC-1").pagamenti == {}
    assert fatturazione.per_fascicolo("FASC-1") == []


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
