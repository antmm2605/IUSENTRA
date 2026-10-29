"""Audit del catalogo documentale del 29/10/2026.

Il titolo dell'atto prevale sulle parole del corpo, il rumore OCR del titolo
non produce etichette sbagliate proposte in automatico, e la seconda lettura
di Lex vale solo con una citazione letterale di cio' che ha letto davvero.
"""

from __future__ import annotations

import json
import re

import pytest

from pct.document_intelligence.catalog_lex import (
    CARATTERI_LETTI,
    citazione_nel_testo,
    leggi_con_lex,
    riscontro_natura_catalogo,
)
from pct.document_intelligence.catalog_resolver import resolve_document_catalog
from pct.fascicoli import TipoDocumento
from pct.fascicolo_document_catalog import classify_fascicolo_document, normalizza_ocr_titoli
from tests.dati_catalogo_titoli import CAMPIONI, CTX_CIVILE


def _risolvi(testo: str, nome: str = "documento.pdf"):
    return resolve_document_catalog(
        tenant_id="t", fascicolo_id="F", document_id=nome, document_sha256="", filename=nome,
        extracted_text=testo, document_metadata={}, fascicolo_context=dict(CTX_CIVILE),
    )


def _classifica(testo: str, nome: str = "documento.pdf"):
    return classify_fascicolo_document(extracted_text=testo, filename=nome)


CITAZIONE = (
    "TRIBUNALE DI BARI\nATTO DI CITAZIONE\nIl sig. Mario Rossi, rappresentato e difeso dall'avv. Luca Bianchi, "
    "CITA la Beta S.r.l. a comparire dinanzi al Tribunale di Bari all'udienza del 10/10/2026, con invito a "
    "costituirsi nel termine di settanta giorni. Come deciso con sentenza della Cassazione n. 123/2020."
)
COMPARSA_CON_SENTENZA = (
    "TRIBUNALE DI BARI - R.G. 1234/2026\nCOMPARSA DI COSTITUZIONE E RISPOSTA\n"
    "nell'interesse della Beta S.r.l., convenuta, che si costituisce nel giudizio e chiede il rigetto della domanda, "
    "come affermato dalla sentenza Cass. civ. n. 456/2021 e dall'ordinanza del Tribunale all'udienza del 01/03/2026."
)
RICORSO_DI_CON_OPPOSIZIONE = (
    "TRIBUNALE DI BARI\nRICORSO PER DECRETO INGIUNTIVO\nLa Alfa S.p.A. chiede l'emissione del decreto ingiuntivo "
    "provvisoriamente esecutivo ex art. 642 c.p.c., avvertendo che la controparte potrà proporre opposizione "
    "entro quaranta giorni."
)
DECRETO_INGIUNTIVO = (
    "TRIBUNALE DI BARI\nDECRETO INGIUNTIVO N. 123/2026\nIl Giudice, letto il ricorso, visti gli artt. 633 e ss. c.p.c., "
    "INGIUNGE alla Beta S.r.l. di pagare alla ricorrente la somma di euro 12.000,00 entro quaranta giorni dalla "
    "notifica, avvertendo che nello stesso termine può essere proposta opposizione."
)
CITAZIONE_OPPOSIZIONE_DI = (
    "TRIBUNALE DI BARI\nATTO DI CITAZIONE IN OPPOSIZIONE A DECRETO INGIUNTIVO\nex art. 645 c.p.c.\n"
    "La società Beta S.r.l. propone opposizione al decreto ingiuntivo n. 123/2026 emesso dal Tribunale di Bari e "
    "CITA la Alfa S.p.A. a comparire all'udienza del 10/10/2026."
)
VERBALE_429 = (
    "TRIBUNALE DI BARI - SEZIONE LAVORO\nVERBALE DI UDIENZA\nAll'udienza del 01/03/2026 sono comparsi i procuratori "
    "delle parti. Il Giudice, all'esito della discussione, pronuncia sentenza ex art. 429 c.p.c. dando lettura del "
    "dispositivo."
)
COMPARSA_CONCLUSIONALE = (
    "TRIBUNALE DI BARI - R.G. 1234/2026\nCOMPARSA CONCLUSIONALE\nnell'interesse della Beta S.r.l., convenuta. "
    "Si richiamano la comparsa di costituzione e risposta e le memorie ex art. 171-ter c.p.c. e si precisano "
    "le conclusioni."
)
MEMORIA_171_TER = (
    "TRIBUNALE DI BARI\nMEMORIA EX ART. 171-TER N. 1 C.P.C.\nnell'interesse di Mario Rossi. Con atto di citazione "
    "notificato il 01/02/2026 l'attore conveniva in giudizio la Beta S.r.l. e il decreto ingiuntivo n. 1/2025 ..."
)


# ── B1/B2: il titolo dell'atto di parte prevale sulle parole del corpo ──

def test_citazione_con_udienza_e_sentenza_nel_corpo_resta_citazione():
    storica = _classifica(CITAZIONE)
    assert storica.role == "atto_principale"
    assert storica.tipo_documento == TipoDocumento.CITAZIONE
    assert storica.section == "atti"
    risolta = _risolvi(CITAZIONE)
    assert risolta.status == "proposed"
    assert risolta.document_section == "atti"
    assert "citazione" in risolta.document_label.casefold()


def test_comparsa_che_cita_sentenza_e_ordinanza_resta_atto_di_parte():
    storica = _classifica(COMPARSA_CON_SENTENZA)
    assert storica.role == "atto_difensivo"
    assert storica.tipo_documento == TipoDocumento.COMPARSA
    risolta = _risolvi(COMPARSA_CON_SENTENZA)
    assert risolta.document_section == "atti"
    assert risolta.document_label not in {"Sentenza", "Ordinanza", "Verbale"}


def test_atto_di_parte_con_titolo_storpiato_dall_ocr_non_diventa_provvedimento():
    testo = COMPARSA_CON_SENTENZA.replace("COMPARSA DI COSTITUZIONE", "C0MPARSA Dl COSTlTUZIONE")
    storica = _classifica(testo)
    assert storica.role == "atto_difensivo"
    risolta = _risolvi(testo)
    assert risolta.document_label == "Comparsa di costituzione e risposta"
    assert risolta.status == "proposed"


def test_provvedimento_con_titolo_su_riga_propria_resta_provvedimento():
    sentenza = "TRlBUNALE Dl BARl\nSENTENZA N. 456/2026\nP.Q.M. il Tribunale condanna il convenuto alle spese."
    assert _classifica(sentenza).tipo_documento == TipoDocumento.SENTENZA
    risolta = _risolvi(sentenza)
    assert (risolta.status, risolta.document_label) == ("proposed", "Sentenza")


# ── B3: normalizzazione OCR e parole chiave del solo corpo ──

@pytest.mark.parametrize(
    ("grezzo", "atteso"),
    [
        ("ATTO Dl PRECETTO", "ATTO DI PRECETTO"),
        ("TRlBUNALE Dl BARl", "TRIBUNALE DI BARI"),
        ("C0MPARSA CONCLUSIONALE", "COMPARSA CONCLUSIONALE"),
        ("ISTANZA DI ACCESS0 AGLI ATTI", "ISTANZA DI ACCESSO AGLI ATTI"),
        ("ATTO DI CITA-\nZIONE", "ATTO DI CITAZIONE"),
        ("Atto Dl precetto", "Atto DI precetto"),
    ],
)
def test_normalizzazione_ocr_dei_titoli(grezzo, atteso):
    assert normalizza_ocr_titoli(grezzo) == atteso


@pytest.mark.parametrize(
    "testo",
    ["Il Giudice dell'esecuzione", "dell'atto e della sentenza", "Al Tribunale di Bari", "RG 1234/2026 IT01X0306909606100000063123"],
)
def test_normalizzazione_ocr_non_tocca_parole_minuscole_ne_codici(testo):
    assert normalizza_ocr_titoli(testo) == testo


def _varianti_ocr(testo: str) -> dict[str, str]:
    prima, _, resto = testo.partition("\n")

    def con(riga: str) -> str:
        return riga + "\n" + resto

    varianti = {
        "I_l_una": con(prima.replace("I", "l", 1)),
        "I_l_tutte": con(prima.replace("I", "l")),
        "O_0": con(prima.replace("O", "0", 1)),
        "DI_Dl": con(re.sub(r"\bDI\b", "Dl", prima)),
    }
    lunghe = re.findall(r"[A-Z]{8,}", prima)
    if lunghe:
        parola = lunghe[0]
        varianti["sillabazione"] = con(prima.replace(parola, parola[:-5] + "-\n" + parola[-5:], 1))
    return varianti


def test_rumore_ocr_nel_titolo_non_produce_etichette_sbagliate_proposte():
    """Prima dell'audit: 21 etichette sbagliate proposte con una sola I letta l."""
    sbagliate: list[tuple[str, str, str, str]] = []
    for regola, (testo, etichetta, _sezione) in CAMPIONI.items():
        for variante, rumoroso in _varianti_ocr(testo).items():
            esito = _risolvi(rumoroso, f"{regola}.pdf")
            if esito.status == "proposed" and esito.document_label != etichetta:
                sbagliate.append((regola, variante, esito.document_label, etichetta))
    assert sbagliate == []


@pytest.mark.parametrize(
    "testo",
    [
        "Il cliente chiede copia della sentenza n. 12/2024 e dell'ordinanza emessa all'udienza del 3 marzo.",
        "Si allega quanto richiesto: il compenso pattuito e la fattura del professionista.",
        "Promemoria interno: verificare il decreto e il verbale prima dell'udienza.",
    ],
)
def test_una_parola_chiave_nel_corpo_non_diventa_mai_una_proposta(testo):
    esito = _risolvi(testo)
    assert esito.status == "review_required"
    assert esito.confidence < 75
    assert esito.deposit_candidate is False


# ── B4: una parola del corpo non toglie il titolo ──

def test_ricorso_per_decreto_ingiuntivo_con_opposizione_nel_corpo():
    storica = _classifica(RICORSO_DI_CON_OPPOSIZIONE)
    assert (storica.label, storica.section, storica.tipo_documento) == (
        "Ricorso per decreto ingiuntivo", "atti", TipoDocumento.RICORSO,
    )
    risolta = _risolvi(RICORSO_DI_CON_OPPOSIZIONE)
    assert (risolta.status, risolta.document_label) == ("proposed", "Ricorso per decreto ingiuntivo")


# ── B5: verbale con sentenza contestuale ──

def test_verbale_lavoro_con_sentenza_ex_429_e_una_sentenza():
    storica = _classifica(VERBALE_429)
    assert storica.tipo_documento == TipoDocumento.SENTENZA
    assert storica.section == "provvedimenti"
    risolta = _risolvi(VERBALE_429)
    assert risolta.status == "proposed"
    assert risolta.document_section == "provvedimenti"
    assert "sentenza" in risolta.document_label.casefold()


def test_verbale_senza_decisione_resta_verbale():
    testo = VERBALE_429.replace(
        "pronuncia sentenza ex art. 429 c.p.c. dando lettura del dispositivo", "rinvia la causa all'udienza del 10/10/2026"
    )
    assert _classifica(testo).tipo_documento == TipoDocumento.VERBALE
    assert "sentenza" not in _risolvi(testo).document_label.casefold()


# ── B6: comparsa conclusionale e memoria 171-ter sono atti ──

@pytest.mark.parametrize("testo", [COMPARSA_CONCLUSIONALE, MEMORIA_171_TER])
def test_atti_di_parte_che_citano_171_ter_vanno_negli_atti(testo):
    storica = _classifica(testo)
    assert storica.section == "atti"
    assert storica.role == "atto_difensivo"
    assert _risolvi(testo).document_section == "atti"


# ── B7: ricorso monitorio, decreto e opposizione sono distinti ──

def test_ricorso_decreto_e_opposizione_monitoria_sono_ruoli_distinti():
    ricorso = _classifica(RICORSO_DI_CON_OPPOSIZIONE)
    decreto = _classifica(DECRETO_INGIUNTIVO)
    opposizione = _classifica(CITAZIONE_OPPOSIZIONE_DI)
    assert len({ricorso.label, decreto.label, opposizione.label}) == 3
    assert (ricorso.section, ricorso.role, ricorso.tipo_documento) == ("atti", "atto_principale", TipoDocumento.RICORSO)
    assert (opposizione.section, opposizione.role, opposizione.tipo_documento) == ("atti", "atto_principale", TipoDocumento.CITAZIONE)
    assert (decreto.section, decreto.role, decreto.tipo_documento) == ("provvedimenti", "provvedimento", TipoDocumento.DECRETO)
    assert _risolvi(DECRETO_INGIUNTIVO).document_section == "provvedimenti"


# ── F8/F9: la seconda lettura di Lex ──

NOTE_CON_RICHIAMI = (
    "NOTE DI TRATTAZIONE SCRITTA ex art. 127-ter c.p.c. nell'interesse di Alfa srl. "
    "Si richiama la sentenza del giudice di pace e il tribunale di Roma ha gia' deciso in senso conforme."
)


def test_citazione_cucita_da_parole_sparse_non_e_verificata():
    assert not citazione_nel_testo("Sentenza del Tribunale di Roma", NOTE_CON_RICHIAMI)


def test_citazione_letterale_con_rumore_ocr_e_riga_estranea_resta_valida():
    testo = "Il Giudice\nRINVIA Dl UFFICIO\nFirmato Da: MARIA NERI Emesso Da: CA DI FIRMA\nla causa all'udienza del 30.06.2026"
    assert citazione_nel_testo("RINVIA DI UFFICIO la causa all'udienza del 30.06.2026", testo)
    assert not citazione_nel_testo("RINVIA DI UFFICIO la causa al giudice", testo)


def test_parola_parziale_non_vale_come_citazione():
    assert not citazione_nel_testo("enza del giudice di pace", NOTE_CON_RICHIAMI)


def test_sentenza_richiede_la_formula_della_decisione():
    assert not riscontro_natura_catalogo("Sentenza", NOTE_CON_RICHIAMI)
    assert riscontro_natura_catalogo(
        "Sentenza", "TRIBUNALE DI BARI\nSENTENZA N. 1/2026\nIl Tribunale ... P.Q.M. accoglie la domanda."
    )
    assert riscontro_natura_catalogo("Sentenza", "REPUBBLICA ITALIANA\nIN NOME DEL POPOLO ITALIANO\nIl Tribunale di Bari")


def test_lex_che_legge_sentenza_in_note_non_e_verificata():
    esito = leggi_con_lex(
        NOTE_CON_RICHIAMI,
        genera=lambda domanda, schema: json.dumps(
            {"etichetta": "Sentenza", "citazione": "Si richiama la sentenza del giudice di pace", "motivo": "m"}
        ),
    )
    assert esito.stato == "non_verificata"


def test_citazione_oltre_i_caratteri_letti_non_conta():
    testo = "NOTE DI TRATTAZIONE SCRITTA. " + "x " * CARATTERI_LETTI + " REPUBBLICA ITALIANA IN NOME DEL POPOLO ITALIANO"
    esito = leggi_con_lex(
        testo,
        genera=lambda domanda, schema: json.dumps(
            {"etichetta": "Sentenza", "citazione": "IN NOME DEL POPOLO ITALIANO", "motivo": "m"}
        ),
    )
    assert esito.stato == "non_verificata"
