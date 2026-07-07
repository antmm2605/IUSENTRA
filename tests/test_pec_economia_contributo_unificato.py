"""Test classificazione contributo unificato nel presidio PEC.

Copre le tre evidenze del D.P.R. 115/2002 (ricevuta di pagamento,
esenzione/autocertificazione, richiesta di versamento) e l'integrazione
nello schema `iusentra.pec.legal_event_understanding.v2`.
"""

from __future__ import annotations

from pct.pec_economia import (
    CATEGORIA_ESENZIONE,
    CATEGORIA_RICEVUTA_PAGAMENTO,
    CATEGORIA_RICHIESTA_VERSAMENTO,
    classifica_contributo_unificato_pec,
    payment_record_contributo_unificato,
)
from pct.pec_legal_event_understanding import build_legal_event_understanding


RICEVUTA_PAGOPA = (
    "Ricevuta telematica di pagamento pagoPA. "
    "Identificativo Univoco Versamento IUV 01234567890123456. "
    "Tipo pagamento: contributo unificato. "
    "Esito pagamento: eseguito. Importo totale versato: € 259,00."
)

AUTOCERTIFICAZIONE_ESENZIONE = (
    "Dichiarazione sostitutiva di certificazione (autocertificazione) resa ai sensi "
    "del D.P.R. 445/2000. Il sottoscritto dichiara che il reddito del nucleo familiare "
    "non supera la soglia di legge e di essere esente dal pagamento del contributo "
    "unificato ai sensi dell'art. 9 comma 1-bis del D.P.R. 115/2002."
)

AVVISO_PAGAMENTO = (
    "Avviso di pagamento del contributo unificato per iscrizione a ruolo. "
    "Importo da pagare: € 98,00. Si invita la parte a pagare entro trenta giorni."
)

SENTENZA_CON_CU = (
    "Sentenza n. 512/2026 pubblicata il 15/05/2026, R.G. 1234/2025. "
    "Il Tribunale, definitivamente pronunciando, condanna la convenuta alla rifusione "
    "delle spese di lite liquidando la complessiva somma di € 2.500,00 per compensi, "
    "oltre al contributo unificato pari ad € 259,00."
)


def _parsed(subject: str, body: str = "") -> dict:
    return {
        "headers": {"subject": subject, "date": "2026-06-10", "message_id": "<cu-test@example.test>"},
        "legal_workflow": {
            "family": "comunicazione_cancelleria_civile",
            "family_label": "Cancelleria civile",
            "event_type": "comunicazione_generica",
            "event_label": "Comunicazione",
            "priority": "media",
        },
        "body": {"text": body, "html_text": "", "href_urls": [], "ics_text": ""},
        "fields": {"data_consegna": {"value": "2026-06-10"}},
        "pct_deposit_receipt": {},
    }


def test_ricevuta_pagopa_classificata_come_pagamento():
    esito = classifica_contributo_unificato_pec(
        "",
        attachments=[{"filename": "ricevuta_pagopa_cu.pdf", "ocr_text": RICEVUTA_PAGOPA}],
    )
    assert esito is not None
    assert esito.categoria == CATEGORIA_RICEVUTA_PAGAMENTO
    assert esito.importo == 259.0
    assert esito.fonte == "ricevuta_pagopa_cu.pdf"


def test_autocertificazione_classificata_come_esenzione_senza_importo():
    esito = classifica_contributo_unificato_pec(
        "",
        attachments=[{"filename": "autocertificazione_esenzione_cu.pdf", "ocr_text": AUTOCERTIFICAZIONE_ESENZIONE}],
    )
    assert esito is not None
    assert esito.categoria == CATEGORIA_ESENZIONE
    assert esito.esente is True
    assert esito.importo is None


def test_avviso_di_pagamento_classificato_come_richiesta_versamento():
    esito = classifica_contributo_unificato_pec(
        "",
        attachments=[{"filename": "avviso_pagamento_cu.pdf", "ocr_text": AVVISO_PAGAMENTO}],
    )
    assert esito is not None
    assert esito.categoria == CATEGORIA_RICHIESTA_VERSAMENTO
    assert esito.importo == 98.0


def test_ricevuta_prevale_su_richiesta_di_versamento():
    esito = classifica_contributo_unificato_pec(
        "",
        attachments=[
            {"filename": "avviso_pagamento_cu.pdf", "ocr_text": AVVISO_PAGAMENTO},
            {"filename": "ricevuta_pagopa_cu.pdf", "ocr_text": RICEVUTA_PAGOPA},
        ],
    )
    assert esito is not None
    assert esito.categoria == CATEGORIA_RICEVUTA_PAGAMENTO


def test_pec_ordinaria_senza_cu_non_classificata():
    esito = classifica_contributo_unificato_pec(
        "Comunicazione di cancelleria: rinvio udienza al 10/09/2026 ore 09:30.",
        attachments=[],
    )
    assert esito is None


def test_payment_record_esenzione_non_apre_incasso_con_importo():
    esito = classifica_contributo_unificato_pec(
        "",
        attachments=[{"filename": "autocertificazione_esenzione_cu.pdf", "ocr_text": AUTOCERTIFICAZIONE_ESENZIONE}],
    )
    record = payment_record_contributo_unificato(esito)
    assert record["payment_event_type"] == "contributo_unificato_esente"
    assert record["amounts"]["totale_testuale"] is None
    assert record["human_review_required"] is True
    assert "esenzione" in record["workflow_action"].casefold()


def test_understanding_ricevuta_pagopa_genera_evento_e_pagamento():
    u = build_legal_event_understanding(
        _parsed("Deposito ricevuta contributo unificato"),
        None,
        attachments=[{"filename": "ricevuta_pagopa_cu.pdf", "ocr_text": RICEVUTA_PAGOPA}],
    )
    assert "ricevuta_pagamento_contributo_unificato" in u["classification"]["events"]
    tipi = [p["payment_event_type"] for p in u["payments"]]
    assert "contributo_unificato_pagato" in tipi
    assert "contributo_unificato" not in tipi
    titoli = [a["title"] for a in u["actions"] if a["action_type"] == "incasso"]
    assert "Contributo unificato pagato da registrare" in titoli
    assert u["human_review_required"] is True


def test_understanding_autocertificazione_genera_evento_esenzione():
    u = build_legal_event_understanding(
        _parsed("Deposito autocertificazione esenzione"),
        None,
        attachments=[{"filename": "autocertificazione_esenzione_cu.pdf", "ocr_text": AUTOCERTIFICAZIONE_ESENZIONE}],
    )
    assert "esenzione_contributo_unificato" in u["classification"]["events"]
    pagamenti = {p["payment_event_type"]: p for p in u["payments"]}
    assert "contributo_unificato_esente" in pagamenti
    assert pagamenti["contributo_unificato_esente"]["amounts"]["totale_testuale"] is None


def test_understanding_avviso_pagamento_genera_richiesta_versamento():
    u = build_legal_event_understanding(
        _parsed("Invito al pagamento contributo unificato"),
        None,
        attachments=[{"filename": "avviso_pagamento_cu.pdf", "ocr_text": AVVISO_PAGAMENTO}],
    )
    assert "richiesta_versamento_contributo_unificato" in u["classification"]["events"]
    tipi = [p["payment_event_type"] for p in u["payments"]]
    assert "contributo_unificato_da_versare" in tipi


def test_understanding_sentenza_con_cu_nel_dispositivo_resta_generico():
    u = build_legal_event_understanding(
        _parsed("Comunicazione deposito sentenza", body=SENTENZA_CON_CU),
        None,
    )
    tipi = [p["payment_event_type"] for p in u["payments"]]
    assert "contributo_unificato" in tipi
    assert "contributo_unificato_pagato" not in tipi


def test_rulepack_v2026_08_contiene_eventi_contributo_unificato():
    from pct.pec_legal_event_understanding import RULEPACK_VERSION, load_rulepack

    assert RULEPACK_VERSION == "legal_pec_rules_v2026_08"
    rules = load_rulepack()
    assert rules["version"] == "legal_pec_rules_v2026_08"
    for code in (
        "ricevuta_pagamento_contributo_unificato",
        "esenzione_contributo_unificato",
        "richiesta_versamento_contributo_unificato",
    ):
        assert code in rules["events"]
    assert "contributo_unificato_spese_giustizia" in rules["families"]
