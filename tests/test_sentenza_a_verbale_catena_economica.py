"""La sentenza a verbale ex art. 127-ter c.p.c. deve arrivare fino alla parcella.

Regressione costruita sul dispositivo reale di una comunicazione di cancelleria
(Tribunale di Vicenza, sezione lavoro): tre forme che il software non leggeva e
che spezzavano la catena economica in tre punti diversi.

- il numero di ruolo con il marcatore DOPO il numero ("n. 523/2026 R.G. lav.");
- il capo spese nella forma diretta ("liquida in euro 500,00");
- la data in calce in forma numerica ("Vicenza, 2/8/2026"), unica data di una
  sentenza a verbale, che non ha l'intestazione "Sentenza n. X pubbl. il ...".

Fonti: artt. 91, 93, 127-ter, 133 c.p.c.; D.M. 55/2014 per gli accessori.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from legal_ocr.ner_legal import extract_numero_ruolo
from pct.fascicoli import StatoFascicolo
from pct.fascicolo_sentenza_economica import (
    AUTOMATION_KEY,
    analyze_sentenza_tribunale_text,
    apply_sentenza_tribunale_automation,
)
from pct.fatturazione import GestioneFatturazione
from pct.sentenza_economic_audit import build_audit
from pct.spese_liquidate_lettura import estrai_spese_liquidate

# Testo ridotto alla struttura del provvedimento reale: intestazione, citazione
# normativa con l'importo di legge, dispositivo con i due capi (beneficio al
# cliente e spese liquidate al difensore), luogo e data in calce.
SENTENZA_A_VERBALE = """n. 523 /2026 R.G. lav.
REPUBBLICA ITALIANA
TRIBUNALE ORDINARIO di VICENZA
- PRIMA SEZIONE CIVILE -
Settore delle controversie di lavoro e di previdenza
IN NOME DEL POPOLO ITALIANO
Il Tribunale, nella persona del Giudice dott.ssa Giulia Beltrame
Lette le note ex art. 127ter cpc ha pronunciato la seguente
SENTENZA
nella causa civile di Primo Grado iscritta al n. 523 /2026 RG Lav. promossa da:
BARILARO FRANCESCO, con l'avv. MONTAGNESE GIUSEPPE
ricorrente
contro
MINISTERO DELL'ISTRUZIONE E DEL MERITO, contumace
rilevato che l'art. 1 co. 121 l. n. 107/2015 istituisce la Carta elettronica per
l'aggiornamento e la formazione del docente per un importo di euro 500 annui;
ogni diversa domanda ed eccezione disattesa o assorbita:
- condanna il Ministero all'accredito sulla Carta elettronica per l'aggiornamento
e la formazione del docente in dotazione alla ricorrente della somma pari ad euro
1.000,00 da spendersi non oltre il 24 mese decorrente dalla costituzione;
- condanna il Ministero alla rifusione delle spese di lite in favore della parte
ricorrente, che liquida in euro 500,00 oltre spese generali, iva e cpa, con
distrazione della somma in favore del procuratore antistatario.
Vicenza, 2/8/2026
Il Giudice
dott.ssa Giulia Beltrame
"""

METADATA = {
    "tipo_documento": "provvedimento Sentenza Tribunale",
    "filename": "23343018s.pdf",
    "document_id": "DOC-SENT-1",
}


class _RepositoryFascicoli:
    def __init__(self) -> None:
        self.fascicolo = SimpleNamespace(
            id="FASC-1",
            id_cliente="CLI-1",
            titolo="Barilaro c. Ministero",
            numero_rg="523/2026",
            nome_cliente="BARILARO FRANCESCO",
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

    def aggiorna(self, fascicolo_id: str, **campi):
        if fascicolo_id != self.fascicolo.id:
            raise KeyError(fascicolo_id)
        for chiave, valore in campi.items():
            setattr(self.fascicolo, chiave, valore)
        return self.fascicolo


def _fascicolo_audit() -> SimpleNamespace:
    return SimpleNamespace(
        id="FASC-1",
        numero_rg="523",
        anno_rg=2026,
        nome_cliente="BARILARO FRANCESCO",
        tribunale="Tribunale di Vicenza",
        controparte="Ministero dell'Istruzione e del Merito",
        valore_causa=0.0,
    )


# ── Le tre letture che si erano rotte ──────────────────────────────────────


def test_ruolo_generale_con_marcatore_dopo_il_numero():
    ruoli = extract_numero_ruolo(SENTENZA_A_VERBALE)

    assert {"numero": "523", "anno": "2026"} in [
        {"numero": r["numero"], "anno": r["anno"]} for r in ruoli
    ]


def test_ruolo_generale_non_confonde_una_data_o_un_importo():
    assert extract_numero_ruolo("udienza del 12/2026 rinviata") == []
    assert extract_numero_ruolo("la somma di 500/2026 euro") == []


def test_capo_spese_nella_forma_diretta():
    importo, brano = estrai_spese_liquidate(SENTENZA_A_VERBALE)

    assert importo == 500.00
    # La fonte deve restare visibile: e' il brano che l'avvocato controlla.
    assert "liquida in euro 500,00" in brano


def test_capo_spese_ignora_gli_importi_che_non_sono_compensi():
    assert estrai_spese_liquidate("liquida in euro 800,00 per esborsi")[0] is None
    assert estrai_spese_liquidate("spese compensate integralmente tra le parti")[0] is None


def test_sentenza_a_verbale_riconosciuta_dalla_data_in_calce():
    estrazione = analyze_sentenza_tribunale_text(SENTENZA_A_VERBALE, METADATA)

    assert estrazione.found is True
    assert estrazione.sentence_date == "2026-08-02"
    assert (estrazione.rg_number, estrazione.rg_year) == ("523", "2026")


# ── Importi attribuiti alla persona giusta ─────────────────────────────────


def test_il_beneficio_del_cliente_non_e_l_importo_di_legge_citato():
    estrazione = analyze_sentenza_tribunale_text(SENTENZA_A_VERBALE, METADATA)

    # 500 e' l'importo annuo citato dall'art. 1 co. 121 l. 107/2015; il giudice
    # ne ha riconosciuti 1.000,00.
    assert estrazione.beneficio_cliente_importo == 1000.00
    assert estrazione.liquidazione_importo == 500.00
    assert estrazione.antistatario is True


def test_audit_economico_apre_il_credito_dell_avvocato_antistatario():
    audit = build_audit(fascicolo=_fascicolo_audit(), testo=SENTENZA_A_VERBALE)

    assert audit.match.rg_match is True
    assert audit.status != "needs_reconciliation"
    spese = audit.sentenza.spese_liquidate
    # Non l'importo piu' alto del testo (1.000,00 al cliente) ma il capo spese.
    assert spese.totale_stimato == 500.00
    assert spese.testo_capo_spese
    crediti = [azione for azione in audit.azioni if azione.type == "apri_credito_avvocato_antistatario"]
    assert len(crediti) == 1
    assert crediti[0].amount == 500.00
    assert crediti[0].beneficiary_type == "avvocato"


# ── La catena arriva alla proforma ─────────────────────────────────────────


def test_la_catena_arriva_alla_proforma_nello_stesso_pannello():
    repository = _RepositoryFascicoli()
    with tempfile.TemporaryDirectory() as cartella:
        fatturazione = GestioneFatturazione(Path(cartella) / "parcelle.json")
        esito = apply_sentenza_tribunale_automation(
            fascicoli_repository=repository,
            fatturazione_repository=fatturazione,
            fascicolo_id="FASC-1",
            text=SENTENZA_A_VERBALE,
            document_metadata=METADATA,
            actor="presidio-pec",
        )

    assert esito.applied is True
    assert esito.changes["proformaCreated"] is True

    pagamenti = repository.fascicolo.pagamenti
    assert AUTOMATION_KEY in pagamenti
    # Liquidazione e parcella vivono nello stesso pannello del fascicolo.
    assert pagamenti["liquidazione_giudice"]["importo"] == 500.00
    parcella = pagamenti["parcella"]
    assert parcella["proforma_id"]
    # 500 + 15% spese generali + 4% cpa + 22% iva (D.M. 55/2014).
    assert parcella["importo"] == 729.56
    assert repository.fascicolo.stato == StatoFascicolo.DEFINITO


# ── Allegato del provvedimento nella busta PCT ─────────────────────────────


def test_il_provvedimento_dentro_lo_zip_pct_non_viene_scartato():
    """Il PCT consegna la sentenza come `nome.pdf.zip`: era scartata dal filtro."""

    from web.services.pec_pipeline_runtime import _sentenza_ocr_text

    detail = {
        "attachments": [
            {"filename": "daticert.xml", "classification": "daticert", "ocr_text": "x" * 900},
            {"filename": "23343018s.pdf.zip", "classification": "atto",
             "content_type": "application/zip", "ocr_text": SENTENZA_A_VERBALE, "sha256": "abc"},
        ]
    }
    testo, impronta = _sentenza_ocr_text(detail)

    assert "liquida in euro 500,00" in testo
    assert impronta == "abc"


# ── Contributo unificato nello stesso pannello ─────────────────────────────

SENTENZA_CU = """TRIBUNALE ORDINARIO di VICENZA
SENTENZA
nella causa iscritta al n. 700 /2026 RG Lav. promossa da: MARIO ROSSI
contro MINISTERO
- condanna il Ministero alla rifusione delle spese di lite, che liquida in euro 600,00
oltre spese generali, iva e cpa, con distrazione in favore del procuratore antistatario.
Vicenza, 2/8/2026
"""


class _RepositoryCU(_RepositoryFascicoli):
    def __init__(self) -> None:
        super().__init__()
        self.fascicolo.numero_rg = "700/2026"
        self.fascicolo.nome_cliente = "MARIO ROSSI"


def _applica(metadata: dict) -> dict:
    repository = _RepositoryCU()
    with tempfile.TemporaryDirectory() as cartella:
        apply_sentenza_tribunale_automation(
            fascicoli_repository=repository,
            fatturazione_repository=GestioneFatturazione(Path(cartella) / "parcelle.json"),
            fascicolo_id="FASC-1",
            text=SENTENZA_CU,
            document_metadata=metadata,
            actor="test",
        )
    return repository.fascicolo.pagamenti


def test_contributo_unificato_esente_per_reddito_risulta_non_dovuto():
    """Esenzione ex art. 9 co. 1-bis D.P.R. 115/2002: nessun importo da recuperare."""

    pagamenti = _applica({
        "tipo_documento": "provvedimento Sentenza Tribunale",
        "document_id": "D-ESENTE",
        "contributo_unificato_pdf": {
            "esente": True,
            "natura": "esenzione_contributo_unificato",
            "label": "Contributo unificato esente",
            "titolo": "il reddito non supera il limite previsto: esente dal contributo unificato",
            "importo": None,
        },
    })

    contributo = pagamenti["contributo_unificato"]
    assert contributo["status"] == "non_previsto"
    assert contributo["previsto"] is False
    assert contributo["importo"] is None
    assert contributo["natura"] == "esenzione_contributo_unificato"
    # 600 + 15% + 4% cpa + 22% iva, senza recupero del contributo.
    assert pagamenti["parcella"]["importo"] == 875.47


def test_contributo_unificato_pagato_entra_col_suo_valore_e_nella_parcella():
    pagamenti = _applica({
        "tipo_documento": "provvedimento Sentenza Tribunale",
        "document_id": "D-RICEVUTA",
        "contributo_unificato_pdf": {
            "importo": 43.0,
            "natura": "pdf_contributo_unificato",
            "label": "Contributo unificato da ricevuta di pagamento",
            "status": "pagato",
            "titolo": "ricevuta pagoPA contributo unificato 43,00",
        },
    })

    contributo = pagamenti["contributo_unificato"]
    assert contributo["status"] == "pagato"
    assert contributo["importo"] == 43.00
    # Il contributo anticipato viene recuperato in parcella (875,47 + 43,00).
    assert pagamenti["parcella"]["importo"] == 918.47
