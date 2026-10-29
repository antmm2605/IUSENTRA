"""Regressioni audit economico 2026-10-29 (importi esatti, CU, spese, SdI).

Testi sintetici: nessun dato reale dello studio.
"""

from __future__ import annotations

import pytest

from pct.fascicolo_sentenza_economica import extract_contributo_unificato_document_evidence as cu_evidence
from pct.fatturazione_sdi_receipts import build_sdi_validation_report, parse_sdi_receipt
from pct.pec_economia import (
    CATEGORIA_ESENZIONE,
    CATEGORIA_RICEVUTA_PAGAMENTO,
    CATEGORIA_RICHIESTA_VERSAMENTO,
    classifica_contributo_unificato_pec,
)
from pct.pec_legal_event_understanding import _CU_RE, _ESBORSI_RE, _LIQUIDA_RE, _amount, _extract_payments
from pct.sentenza_economic_audit import _importi_rilevati, assess_contributo_unificato, extract_economics, load_ruleset

# --------------------------------------------------------------------------- C1


@pytest.mark.parametrize(
    "testo,atteso",
    [
        ("contributo unificato di € 1.686", 1686.00),
        ("contributo unificato di € 1.686,00", 1686.00),
        ("contributo unificato versato € 98,00", 98.00),
        ("contributo unificato versato euro 3.500,00", 3500.00),
        ("contributo unificato di € 1 200,00", 1200.00),
        ("contributo unificato di 518,00 euro", 518.00),
    ],
)
def test_c1_contributo_unificato_importo_esatto(testo, atteso):
    assert _amount(_CU_RE.search(testo)) == atteso


@pytest.mark.parametrize(
    "testo,atteso",
    [
        ("liquida le spese in € 1.200 oltre accessori", 1200.00),
        ("liquida le spese in € 1.686,00 oltre accessori", 1686.00),
        ("che liquida in € 1 200,00 per compensi", 1200.00),
        ("liquidate in euro 3.500,00 per compensi", 3500.00),
        ("liquidate in 3.500,00 euro per compensi", 3500.00),
        ("liquida in € 98,00", 98.00),
    ],
)
def test_c1_liquidazione_importo_esatto(testo, atteso):
    assert _amount(_LIQUIDA_RE.search(testo)) == atteso


def test_c1_esborsi_e_pagamento_cu_esatti():
    assert _amount(_ESBORSI_RE.search("€ 1.200 per esborsi")) == 1200.00
    assert _ESBORSI_RE.search("€ 1.200,00 spese generali") is None
    payments = _extract_payments("contributo unificato di € 1.686")
    cu = [p for p in payments if p["payment_event_type"] == "contributo_unificato"]
    assert cu and cu[0]["amounts"]["totale_testuale"] == 1686.00


# --------------------------------------------------------------------------- C2

INVITO_248 = (
    "Invito al pagamento del contributo unificato ai sensi dell'art. 248 D.P.R. 115/2002: "
    "si invita a versare la somma di € 1.686,00 entro 30 giorni."
)


def test_c2_invito_cu_con_dpr_115_non_e_gratuito_patrocinio():
    types = [p["payment_event_type"] for p in _extract_payments(INVITO_248)]
    assert "gratuito_patrocinio" not in types
    result = classifica_contributo_unificato_pec(INVITO_248)
    assert result.categoria == CATEGORIA_RICHIESTA_VERSAMENTO
    assert result.importo == 1686.00


@pytest.mark.parametrize(
    "testo",
    [
        "Parte ammessa al patrocinio a spese dello Stato: liquida in € 1.200,00 il compenso del difensore.",
        "Decreto di pagamento ex art. 82 D.P.R. 115/2002 in regime di gratuito patrocinio.",
    ],
)
def test_c2_patrocinio_esplicito_resta_gratuito_patrocinio(testo):
    assert "gratuito_patrocinio" in [p["payment_event_type"] for p in _extract_payments(testo)]


# --------------------------------------------------------------------------- C3

NEGATIVI = [
    "Ricevuta pagoPA. Causale: contributo unificato. Importo € 518,00. Esito: pagamento non eseguito.",
    "Ricevuta di pagamento. Contributo unificato. Importo € 518,00. Esito negativo: pagamento non eseguito.",
    "Ricevuta di pagamento pagoPA. Contributo unificato. Importo € 518,00. Esito: annullato.",
    "Ricevuta di pagamento pagoPA. Contributo unificato. Importo € 518,00. Pagamento rifiutato.",
    # percorso importo a ruolo ("Contributo unificato: € ...")
    "Contributo unificato: € 518,00. Ricevuta di pagamento. Pagamento eseguito. Stato: annullato.",
]


@pytest.mark.parametrize("testo", NEGATIVI)
def test_c3_esito_negativo_mai_pagato(testo):
    evidence = cu_evidence(testo, {})
    assert evidence["status"] == "pagamento_non_eseguito"
    assert evidence["importo"] is None
    assert evidence["importo_non_pagato"] == 518.00
    result = classifica_contributo_unificato_pec(testo)
    assert result.categoria == CATEGORIA_RICHIESTA_VERSAMENTO
    assert result.importo == 518.00
    assert "pagamento_contributo_unificato_non_eseguito" in result.warnings


def test_c3_importo_zero_annullato_usa_importo_dovuto():
    evidence = cu_evidence(
        "Contributo unificato importo pagato € 0,00 - transazione annullata, importo dovuto € 518,00", {}
    )
    assert evidence["status"] == "pagamento_non_eseguito"
    assert evidence["importo_non_pagato"] == 518.00


def test_c3_ricevuta_positiva_resta_pagata():
    testo = (
        "Ricevuta telematica di pagamento pagoPA. Causale: contributo unificato RG 1234/2025. "
        "Importo pagato: € 518,00. Esito: pagamento eseguito."
    )
    result = classifica_contributo_unificato_pec(testo)
    assert result.categoria == CATEGORIA_RICEVUTA_PAGAMENTO
    assert result.importo == 518.00


# --------------------------------------------------------------------------- C4


@pytest.mark.parametrize(
    "testo",
    [
        "Il procedimento non è esente dal contributo unificato; importo dovuto € 98,00",
        "Procedimento non esente dal contributo unificato; importo dovuto € 98,00",
        "Non sussiste esenzione dal contributo unificato; importo dovuto € 98,00",
    ],
)
def test_c4_negazione_esenzione(testo):
    evidence = cu_evidence(testo, {})
    assert evidence.get("esente") is not True
    assert evidence["importo"] == 98.00
    assert evidence["natura"] == "richiesta_versamento_contributo_unificato"


def test_c4_audit_non_esente():
    rules = load_ruleset()
    audit = assess_contributo_unificato("Il ricorrente non è esente dal contributo unificato.", ruleset=rules)
    assert audit.status != "esente"


# --------------------------------------------------------------------------- C5


@pytest.mark.parametrize(
    "testo,atteso",
    [
        ("Invito al pagamento: contributo unificato dovuto € 1.686 entro trenta giorni dalla notifica.", 1686.00),
        (INVITO_248, 1686.00),
        ("Contributo unificato: si invita a versare € 237,00 entro 30 giorni.", 237.00),
        ("Contributo unificato: versare la somma di € 759,00.", 759.00),
        ("Contributo unificato importo dovuto € 1.686,00.", 1686.00),
        ("Contributo unificato da versare € 98,00 entro 30 giorni.", 98.00),
        ("Si invita la parte all'integrazione del contributo unificato: € 241,00.", 241.00),
        ("Contributo unificato versato in misura insufficiente: differenza dovuta € 241,00.", 241.00),
    ],
)
def test_c5_richiesta_versamento_importo_esatto(testo, atteso):
    result = classifica_contributo_unificato_pec(testo)
    assert result is not None
    assert result.categoria == CATEGORIA_RICHIESTA_VERSAMENTO
    assert result.importo == atteso


# --------------------------------------------------------------------------- C6


@pytest.mark.parametrize(
    "testo",
    [
        "Contributo unificato prenotato a debito",
        "Spesa prenotata a debito ai sensi dell'art. 131 DPR 115/2002",
        "Contributo unificato prenotato a debito ai sensi dell'art. 131 DPR 115/2002 (patrocinio a spese dello Stato).",
    ],
)
def test_c6_prenotato_a_debito(testo):
    evidence = cu_evidence(testo, {})
    assert evidence["status"] == "prenotato_a_debito"
    assert evidence["prenotato_a_debito"] is True
    assert evidence["importo"] is None
    result = classifica_contributo_unificato_pec(testo)
    assert result.categoria == CATEGORIA_ESENZIONE
    assert result.stato == "prenotato_a_debito"


def test_c6_esenzione_resta_esente():
    evidence = cu_evidence("Contributo unificato: esente", {})
    assert evidence["status"] == "esente" and evidence["prenotato_a_debito"] is False


# --------------------------------------------------------------------------- C7


@pytest.mark.parametrize(
    "testo",
    [
        "P.Q.M. rigetta la domanda. Spese compensate.",
        "P.Q.M. rigetta la domanda e dichiara interamente compensate tra le parti le spese di lite.",
        "P.Q.M. rigetta la domanda; compensa integralmente tra le parti le spese del giudizio.",
    ],
)
def test_c7_compensazione_integrale_nessun_credito(testo):
    payments = _extract_payments(testo)
    assert [p["payment_event_type"] for p in payments] == ["nessuno"]


def test_c7_compensazione_per_meta_conserva_quota_liquidata():
    testo = (
        "P.Q.M. compensa per metà le spese di lite e condanna il convenuto alla rifusione della restante "
        "metà, che liquida in € 1.200,00 per compensi oltre spese generali 15%, IVA e CPA."
    )
    payments = _extract_payments(testo)
    assert payments[0]["payment_event_type"] == "spese_parte"
    assert payments[0]["amounts"]["totale_testuale"] == 1200.00


# --------------------------------------------------------------------------- C8

ORDINANZA = """TRIBUNALE ORDINARIO DI ROMA
SEZIONE II CIVILE
Il Giudice, letti gli atti del procedimento R.G. 1234/2025, ha pronunciato la seguente
ORDINANZA
richiamata la sentenza n. 45/2020 della Corte di Cassazione,
P.Q.M.
rigetta il ricorso e compensa le spese di lite."""

DECRETO = """TRIBUNALE ORDINARIO DI MILANO
DECRETO INGIUNTIVO N. 100/2025
Il Giudice, vista la sentenza n. 12/2019 richiamata dal ricorrente,
P.Q.M.
ingiunge a Beta S.r.l. di pagare € 5.000,00."""

SENTENZA = """REPUBBLICA ITALIANA
IN NOME DEL POPOLO ITALIANO
TRIBUNALE ORDINARIO DI MILANO
SENTENZA
definitivamente pronunciando, accoglie la domanda e condanna il convenuto alla rifusione delle spese di lite."""


def test_c8_tipo_da_intestazione():
    assert extract_economics(ORDINANZA).tipo_provvedimento == "ordinanza"
    assert extract_economics(DECRETO).tipo_provvedimento == "decreto"
    assert extract_economics(SENTENZA).tipo_provvedimento == "sentenza"


def test_c8_citazione_sentenza_nel_corpo_non_decide_il_tipo():
    testo = "Il Tribunale, vista la sentenza n. 45/2020, così provvede: P.Q.M. rigetta."
    assert extract_economics(testo).tipo_provvedimento == "ordinanza"


@pytest.mark.parametrize(
    "testo",
    [
        "P.Q.M. rigetta la domanda e dichiara interamente compensate tra le parti le spese di lite.",
        "P.Q.M. rigetta la domanda; compensa parzialmente le spese di lite.",
    ],
)
def test_c8_compensazione_non_e_condanna_ne_esito_parziale(testo):
    ext = extract_economics(testo)
    assert ext.esito != "parziale"
    assert ext.spese_liquidate.condanna_spese is False


def test_c8_compensazione_per_meta_e_parziale():
    ext = extract_economics(
        "P.Q.M. compensa per metà le spese di lite e condanna il convenuto alla rifusione della restante metà, "
        "che liquida in € 1.200,00 per compensi."
    )
    assert ext.spese_liquidate.compensazione_parziale is True
    assert ext.spese_liquidate.condanna_spese is True
    assert ext.spese_liquidate.totale_stimato == 1200.00


def test_c8_ruleset_versione_aggiornata():
    rules = load_ruleset()
    assert rules["version"] == "2026.10.29"
    assert "parzialmente" not in rules["esito"]["parziale_keywords"]
    assert "spese di lite" not in rules["spese"]["condanna_keywords"]


# --------------------------------------------------------------------------- C9


@pytest.mark.parametrize(
    "testo,atteso",
    [
        ("liquida in euro 1.200 per compensi ed euro 98 per esborsi", [1200.00, 98.00]),
        ("che liquida in € 1 200,00 per compensi oltre accessori", [1200.00]),
        ("somma di € 45.000,00 e spese in € 4.835,00", [45000.00, 4835.00]),
        ("liquidate in 3.500,00 euro per compensi", [3500.00]),
        ("contributo unificato di € 1.686", [1686.00]),
    ],
)
def test_c9_importi_rilevati_esatti(testo, atteso):
    assert _importi_rilevati(testo) == atteso


# --------------------------------------------------------------------------- C10

_NS = "http://www.fatturapa.gov.it/sdi/messaggi/v1.0"


def _notifica_esito(esito: str, descrizione: str = "") -> bytes:
    desc = f"<Descrizione>{descrizione}</Descrizione>" if descrizione else ""
    return (
        f'<types:NotificaEsito xmlns:types="{_NS}" versione="1.0">'
        "<IdentificativoSdI>111</IdentificativoSdI>"
        "<RiferimentoFattura><NumeroFattura>12/2026</NumeroFattura><AnnoFattura>2026</AnnoFattura></RiferimentoFattura>"
        "<NomeFile>IT01234567890_00001.xml</NomeFile>"
        f"<EsitoCommittente><IdentificativoSdI>111</IdentificativoSdI><Esito>{esito}</Esito>{desc}"
        "<MessageIdCommittente>55</MessageIdCommittente></EsitoCommittente>"
        "<MessageId>77</MessageId></types:NotificaEsito>"
    ).encode()


def test_c10_notifica_esito_ec01_accettata():
    receipt = parse_sdi_receipt(_notifica_esito("EC01"))
    assert receipt["kind"] == "NotificaEsito"
    assert receipt["status"] == "ACCETTATA"
    assert receipt["esito"] == "EC01"
    assert receipt["sdi_id"] == "111"
    assert receipt["riferimento_fattura"] == "12/2026"
    assert receipt["errors"] == []


def test_c10_notifica_esito_ec02_rifiutata_con_descrizione():
    receipt = parse_sdi_receipt(_notifica_esito("EC02", "Codice CIG mancante"))
    assert receipt["status"] == "RIFIUTATA"
    assert receipt["esito"] == "EC02"
    assert receipt["esito_descrizione"] == "Codice CIG mancante"
    report = build_sdi_validation_report({"sdi_receipts": [receipt]}, [])
    issue = next(item for item in report["issues"] if item["code"] == "sdi_rifiutata")
    assert issue["severity"] == "danger" and "Codice CIG mancante" in issue["detail"]


def test_c10_notifica_esito_sconosciuto_ignorata():
    assert parse_sdi_receipt(_notifica_esito("EC99")) is None
