"""Audit PEC 29/10/2026: ricevute, classificazione legale, fasi deposito, allegati, doppioni.

Ogni caso riproduce un difetto verificato con PEC dal formato reale: daticert.xml con il tipo
nell'ATTRIBUTO di <postacert> (d.m. 2/11/2005, allegato § 2.1.1), oggetti a prefisso fisso dei
gestori (d.P.R. 68/2005), biglietti di cancelleria (art. 16 d.l. 179/2012).
"""

from __future__ import annotations

import importlib.util
import os
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from types import SimpleNamespace

import pytest

from pct.pec_control_tower import classify_legal, classify_technical, parse_pec_mime
from pct.pec_legal_workflow import classifica_pec_legale, estrai_registri
from pct.pec_oggetti_ufficiali import (
    classifica_ricevuta_pec,
    normalizza_tipo_ricevuta,
    tipo_daticert,
    tipo_ricevuta_da_oggetto,
)
from pct.pec_pipeline import (
    AttachmentPayload,
    PecAuditRepository,
    ROME_TZ,
    _deadline_identity_line,
    _unlinked_deadline_duplicate,
    classify_attachment,
    detect_pct_deposit_stage,
    parse_pec_message,
    receipt_type_from_text,
)
from pct.pec_notification_presidio import ReceiptKind

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Fixture PEC in formato reale
# ---------------------------------------------------------------------------


def _daticert(tipo: str, *, oggetto: str = "Notificazione ai sensi della legge n. 53 - 1994 [Notifica_ID:N1]") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<postacert tipo="{tipo}" errore="nessuno">
  <intestazione>
    <mittente>studio@pec.it</mittente>
    <destinatari tipo="certificato">controparte@pec.it</destinatari>
    <risposte>studio@pec.it</risposte>
    <oggetto>{oggetto}</oggetto>
  </intestazione>
  <dati>
    <gestore-emittente>ARUBA PEC S.p.A.</gestore-emittente>
    <data zona="+0100"><giorno>28/10/2026</giorno><ora>10:15:00</ora></data>
    <identificativo>opec123.20261028@pec.aruba.it</identificativo>
    <msgid>&lt;orig-notifica-1@studio.pec.it&gt;</msgid>
    <consegna>controparte@pec.it</consegna>
  </dati>
</postacert>"""


def _receipt_eml(subject: str, body: str, tipo: str, *, headers: dict[str, str] | None = None) -> bytes:
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = "posta-certificata@pec.aruba.it"
    msg["To"] = "studio@pec.it"
    msg["Date"] = "Wed, 28 Oct 2026 10:15:00 +0100"
    msg["Message-ID"] = f"<rcpt-{abs(hash((subject, tipo)))}@pec.aruba.it>"
    for key, value in (headers or {}).items():
        msg[key] = value
    msg.attach(MIMEText(body, "plain", "utf-8"))
    xml = MIMEApplication(_daticert(tipo).encode("utf-8"), "xml")
    xml.add_header("Content-Disposition", "attachment", filename="daticert.xml")
    msg.attach(xml)
    return msg.as_bytes()


RECEIPTS = [
    # (daticert tipo, oggetto, corpo, etichetta attesa, tipo tecnico control tower, evento workflow, esito presidio)
    (
        "errore-consegna",
        "AVVISO DI MANCATA CONSEGNA: Notificazione ai sensi della legge n. 53 - 1994 [Notifica_ID:N1]",
        "Errore nella consegna\nIl giorno 28/10/2026 alle ore 10:15:00 (+0100) nel messaggio è stato rilevato un "
        "errore 5.1.1 - casella inesistente. Il messaggio non è stato consegnato.",
        "mancata_consegna",
        "PEC_RECEIPT_FAILED_DELIVERY",
        "mancata_consegna_pec",
        ReceiptKind.FAILURE,
    ),
    (
        "non-accettazione",
        "AVVISO DI NON ACCETTAZIONE: Notificazione ai sensi della legge n. 53 - 1994 [Notifica_ID:N1]",
        "Errore di accettazione\nIl giorno 28/10/2026 nel messaggio è stato rilevato un problema che ne impedisce "
        "l'accettazione.",
        "non_accettazione",
        "PEC_RECEIPT_NON_ACCEPTANCE",
        "mancata_consegna_pec",
        ReceiptKind.FAILURE,
    ),
    (
        "avvenuta-consegna",
        "CONSEGNA: Contestazione per mancata consegna merce e non accettazione dell'eredità [Notifica_ID:N1]",
        "Ricevuta di avvenuta consegna\nIl giorno 28/10/2026 il messaggio è stato consegnato nella casella di destinazione.",
        "avvenuta_consegna",
        "PEC_RECEIPT_DELIVERY",
        "ricevuta_consegna_pec",
        ReceiptKind.RDAC,
    ),
    (
        "accettazione",
        "ACCETTAZIONE: Rinuncia e non accettazione eredità - avviso di mancata consegna merce [Notifica_ID:N1]",
        "Ricevuta di accettazione\nIl giorno 28/10/2026 il messaggio è stato accettato dal sistema ed inoltrato.",
        "accettazione",
        "PEC_RECEIPT_ACCEPTANCE",
        "ricevuta_accettazione_pec",
        ReceiptKind.RAC,
    ),
    # Oggetto non standard (inoltro): decide il daticert.
    (
        "errore-consegna",
        "Fwd: ricevuta PEC notifica [Notifica_ID:N1]",
        "Il messaggio è stato consegnato? No: vedere allegato.",
        "mancata_consegna",
        "PEC_RECEIPT_FAILED_DELIVERY",
        "mancata_consegna_pec",
        ReceiptKind.FAILURE,
    ),
]


@pytest.mark.parametrize("tipo,subject,body,label,technical,event,kind", RECEIPTS)
def test_d1_a7_ricevuta_reale_coerente_in_pipeline_control_tower_workflow_e_presidio(
    tipo, subject, body, label, technical, event, kind
):
    raw = _receipt_eml(subject, body, tipo)

    parsed = parse_pec_message(raw)
    assert parsed["pec_receipt"]["type"] == label
    assert parsed["fields"]["tipo_ricevuta"]["value"] == label
    assert parsed["fields"]["tipo_ricevuta"]["confidence"] >= 0.9  # letto dall'XML
    assert parsed["legal_workflow"]["event_type"] == event
    assert parsed["legal_workflow"]["receipt_type"] == label

    profile = PecAuditRepository._notification_receipt_profile(parsed, {})
    assert profile.get("kind") == kind

    tower = parse_pec_mime(raw)
    assert classify_technical(tower)["technical_type"] == technical


def test_d1_posta_certificata_in_arrivo_non_e_una_ricevuta():
    raw = _receipt_eml(
        "POSTA CERTIFICATA: Comunicazione di cancelleria RG 1234/2026",
        "Tribunale di Milano. Si comunica il deposito della sentenza n. 55/2026 nel procedimento RG 1234/2026. "
        "Consegna copia in cancelleria. Ricevuta di accettazione del deposito allegata.",
        "posta-certificata",
    )
    parsed = parse_pec_message(raw)
    assert parsed["pec_receipt"]["type"] == ""
    assert PecAuditRepository._notification_receipt_profile(parsed, {})["skipped"] is True
    assert classify_technical(parse_pec_mime(raw))["technical_type"] == "PEC_INBOUND_CERTIFIED"


def test_d1_tipo_daticert_attributo_e_normalizzazione():
    assert tipo_daticert(_daticert("errore-consegna")) == "errore-consegna"
    assert tipo_daticert("<postacert><dati><tipo>accettazione</tipo></dati></postacert>") == "accettazione"
    assert tipo_daticert("<EsitoAtto><tipo>accettazione</tipo></EsitoAtto>") == ""
    assert normalizza_tipo_ricevuta("non-accettazione") == "non_accettazione"
    assert normalizza_tipo_ricevuta("errore-consegna") == "mancata_consegna"
    assert normalizza_tipo_ricevuta("preavviso-errore-consegna") == "preavviso_mancata_consegna"
    assert normalizza_tipo_ricevuta("posta-certificata") == ""


@pytest.mark.parametrize(
    "text,expected",
    [
        ("AVVISO DI NON ACCETTAZIONE: Invio documenti\nErrore nell'accettazione del messaggio", "non_accettazione"),
        ("AVVISO DI NON ACCETTAZIONE PER VIRUS: Invio documenti\nIl messaggio contiene un virus", "non_accettazione"),
        ("AVVISO DI MANCATA CONSEGNA: Invio documenti\nIl messaggio non è stato consegnato", "mancata_consegna"),
        (
            "AVVISO DI MANCATA CONSEGNA PER SUPERAMENTO TEMPI MASSIMI: Invio documenti\nNon consegnato entro 12 ore",
            "preavviso_mancata_consegna",
        ),
        ("PROBLEMA DI SICUREZZA: Invio documenti\nRilevazione virus nel messaggio", "rilevazione_virus"),
        ("PRESA IN CARICO: Invio documenti\nRicevuta di presa in carico", "presa_in_carico"),
        ("CONSEGNA: Accettazione eredità con beneficio d'inventario\nRicevuta di avvenuta consegna", "avvenuta_consegna"),
        ("ACCETTAZIONE: Invio documenti\nRicevuta di accettazione", "accettazione"),
        ("Comunicazione\nSi segnala la mancata accettazione del messaggio da parte del gestore.", "non_accettazione"),
        ("Diffida ad adempiere\nIn mancanza di accettazione della proposta si procederà.", ""),
        ("Offerta speciale toner\nConsegna gratuita in 24h, prodotto consegnato a domicilio.", ""),
        ("Ricevuta di consegna 1234567890\nIl file IT01234567890_00001.xml.p7m è stato consegnato", ""),
        ("Diffida\nNonostante l'avvenuta consegna della merce il pagamento non è stato eseguito", ""),
    ],
)
def test_a1_a2_receipt_type_from_text_negativi_prima_e_parole_intere(text, expected):
    assert receipt_type_from_text(text)[0] == expected


def test_a2_prefisso_inoltrato_vale_solo_per_ricevute_negative():
    assert tipo_ricevuta_da_oggetto("Fwd: AVVISO DI MANCATA CONSEGNA: Diffida", consenti_inoltro=True) == "mancata_consegna"
    assert tipo_ricevuta_da_oggetto("I: CONSEGNA: Diffida", consenti_inoltro=True) == ""
    assert classifica_ricevuta_pec("Re: invio atti", "", daticert_tipo="non-accettazione") == ("non_accettazione", "daticert")


# ---------------------------------------------------------------------------
# Control tower (A3-A6, A18) e legale (A14/A15)
# ---------------------------------------------------------------------------


def _ct(subject: str, body: str = "", *, sender: str = "posta-certificata@pec.aruba.it", headers=None, tipo: str = ""):
    parsed = {
        "subject": subject,
        "sender": sender,
        "body": body,
        "search_text": f"{subject} {sender} {body}",
        "headers": dict(headers or {}),
        "daticert": {"tipo": tipo} if tipo else {},
    }
    technical = classify_technical(parsed)
    return technical, classify_legal(parsed, technical)


@pytest.mark.parametrize(
    "header,technical,role",
    [
        ("accettazione", "PEC_RECEIPT_ACCEPTANCE", "acceptance"),
        ("non-accettazione", "PEC_RECEIPT_NON_ACCEPTANCE", "failed_delivery"),
        ("presa-in-carico", "PEC_RECEIPT_TAKEN_IN_CHARGE", "acceptance"),
        ("avvenuta-consegna", "PEC_RECEIPT_DELIVERY", "delivery"),
        ("errore-consegna", "PEC_RECEIPT_FAILED_DELIVERY", "failed_delivery"),
        ("preavviso-errore-consegna", "PEC_RECEIPT_FAILED_DELIVERY", "failed_delivery"),
        ("rilevazione-virus", "PEC_VIRUS_WARNING", "failed_delivery"),
    ],
)
def test_a3_a5_x_ricevuta_mappata_esplicitamente(header, technical, role):
    # Oggetto neutro: decide l'intestazione, mai «x-ricevuta presente = consegna».
    result, _legal = _ct("Invio documenti", "Messaggio del gestore.", headers={"x-ricevuta": header})
    assert result["technical_type"] == technical
    assert result["receipt_role"] == role


def test_a4_oggetto_originale_dopo_il_prefisso_non_decide():
    technical, _ = _ct(
        "CONSEGNA: Contestazione per mancata consegna merce",
        "Ricevuta di avvenuta consegna",
        headers={"x-ricevuta": "avvenuta-consegna"},
    )
    assert technical["technical_type"] == "PEC_RECEIPT_DELIVERY"
    technical, _ = _ct("CONSEGNA: Dichiarazione di non accettazione dell'eredità", "Ricevuta di avvenuta consegna")
    assert technical["technical_type"] == "PEC_RECEIPT_DELIVERY"


def test_a6_diffida_in_arrivo_con_accettazione_nel_testo_resta_inbound():
    technical, legal = _ct(
        "Diffida ad adempiere",
        "Con la presente si diffida al pagamento. In mancanza di accettazione della proposta, nonostante "
        "l'avvenuta consegna della merce, si agirà in giudizio.",
        sender="avv.rossi@pec.it",
        headers={"x-trasporto": "posta-certificata"},
        tipo="posta-certificata",
    )
    assert technical["technical_type"] == "PEC_INBOUND_CERTIFIED"
    assert technical["receipt_role"] == ""
    assert legal["legal_category"] == "DIFFIDA_MESSA_IN_MORA"


def test_a18_quarta_pec_esito_intervento_cancelleria_non_e_ricevuta():
    technical, legal = _ct(
        "POSTA CERTIFICATA: ESITO INTERVENTO CANCELLERIA",
        "Esito intervento cancelleria: accettazione deposito. Il deposito è stato accettato dalla cancelleria. "
        "RG 1234/2025",
        sender="tribunale.milano@civile.ptel.giustiziacert.it",
        tipo="posta-certificata",
    )
    assert technical["technical_type"] == "PEC_INBOUND_CERTIFIED"
    assert legal["legal_category"] == "CANCELLERIA_PCT"


@pytest.mark.parametrize(
    "subject,body,sender,category",
    [
        ("Ricevuta di consegna 1234567890", "Il file IT01234567890_00001.xml.p7m è stato consegnato",
         "sdi01@pec.fatturapa.it", "FATTURA_SDI"),
        ("Notifica di scarto 1234567890", "Il file è stato scartato: errore 00404 fattura duplicata",
         "sdi01@pec.fatturapa.it", "FATTURA_SDI"),
        ("Esito committente", "Notifica del Sistema di Interscambio", "sdi22@pec.fatturapa.it", "FATTURA_SDI"),
        ("Avviso FISSAZIONE UDIENZA per il ricorso 1234/2025 COD.tarla", "Segreteria TAR Lazio",
         "tarla@ga-cert.it", "CANCELLERIA_PCT"),
        ("Avviso DEPOSITO SENTENZA per il ricorso 1234/2025 codtarmi", "", "tarmi@ga-cert.it",
         "PROVVEDIMENTO_GIUDIZIARIO"),
    ],
)
def test_a14_a15_classify_legal_oggetti_ufficiali_prima_delle_parole_chiave(subject, body, sender, category):
    technical, legal = _ct(subject, body, sender=sender, tipo="posta-certificata")
    assert technical["technical_type"] == "PEC_INBOUND_CERTIFIED"
    assert legal["legal_category"] == category


# ---------------------------------------------------------------------------
# Fasi del deposito telematico (A8)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        "Esito intervento cancelleria: il deposito non è stato accettato dalla cancelleria per errata individuazione del fascicolo.",
        "Deposito non accettato dalla cancelleria: atto rifiutato.",
        "Mancata accettazione deposito da parte della cancelleria.",
        "Esito: RIFIUTO DEPOSITO. Motivo: fascicolo errato.",
    ],
)
def test_a8_deposito_non_accettato_e_rifiuto(body):
    stage = detect_pct_deposit_stage(
        {"headers": {"subject": "POSTA CERTIFICATA: ESITO INTERVENTO CANCELLERIA"}, "body": {"text": body}}
    )
    assert stage["id"] == "rifiuto_deposito"
    assert stage["status"] == "danger"


def test_a8_deposito_accettato_resta_accettazione():
    stage = detect_pct_deposit_stage(
        {
            "headers": {"subject": "POSTA CERTIFICATA: ESITO INTERVENTO CANCELLERIA"},
            "body": {"text": "Esito intervento cancelleria: accettazione deposito. Il deposito è stato accettato."},
        }
    )
    assert stage["id"] == "accettazione_deposito"


def test_a8_avviso_di_non_accettazione_del_deposito_non_e_fase_di_accettazione():
    stage = detect_pct_deposit_stage(
        {
            "headers": {"subject": "AVVISO DI NON ACCETTAZIONE: DEPOSITO ATTO - Memoria 171-ter"},
            "body": {"text": "Errore nell'accettazione del messaggio"},
            "fields": {"tipo_ricevuta": {"value": "non_accettazione"}},
        }
    )
    assert stage["id"] == "mancata_consegna_pec"
    assert stage["status"] == "danger"


# ---------------------------------------------------------------------------
# Workflow legale (A9-A13)
# ---------------------------------------------------------------------------

GIUSTIZIA = "tribunale.roma@civile.ptel.giustiziacert.it"


def test_a9_esito_cancelleria_non_accettato_prima_delle_frasi_di_accettazione():
    result = classifica_pec_legale(
        subject="POSTA CERTIFICATA: ESITO INTERVENTO CANCELLERIA",
        body="Esito intervento cancelleria: Il deposito non è stato accettato dalla cancelleria per errata "
        "individuazione del fascicolo. Accettazione deposito: NO.",
        sender=GIUSTIZIA,
    )
    assert result["event_type"] == "rifiuto_deposito"


def test_a10_tribunale_nel_mittente_non_rende_l_udienza_in_presenza():
    result = classifica_pec_legale(
        subject="POSTA CERTIFICATA: Comunicazione di cancelleria RG 555/2024",
        body="Si comunica udienza fissata al 12/05/2026 ore 10:00.",
        sender=GIUSTIZIA,
    )
    assert result["event_type"] == "udienza_fissata"
    assert result["udienza"]["modalita"] == "da verificare"


@pytest.mark.parametrize(
    "body",
    [
        "Si comunica che l'udienza è rinviata al 15/06/2026.",
        "Si comunica il rinvio d'ufficio dell'udienza al 15/06/2026.",
    ],
)
def test_a11_rinvio_udienza(body):
    result = classifica_pec_legale(
        subject="POSTA CERTIFICATA: Comunicazione di cancelleria RG 555/2024", body=body, sender=GIUSTIZIA
    )
    assert result["event_type"] == "rinvio_udienza"


def test_a12_trattazione_scritta_127_ter_prima_delle_regole_udienza():
    result = classifica_pec_legale(
        subject="POSTA CERTIFICATA: Comunicazione di cancelleria RG 555/2024",
        body="Il giudice dispone che l'udienza del 10/04/2026 in aula 3 sia sostituita dal deposito di note scritte "
        "ai sensi dell'art. 127-ter c.p.c.",
        sender=GIUSTIZIA,
    )
    assert result["event_type"] == "udienza_sostituita_da_note_scritte"
    assert result["creates_deadline"] is True


def test_a12_decreto_171_bis():
    result = classifica_pec_legale(
        subject="POSTA CERTIFICATA: Comunicazione di cancelleria RG 555/2024",
        body="Decreto ex art. 171-bis c.p.c.: il giudice conferma la data della prima udienza e assegna i termini "
        "per le memorie 171-ter.",
        sender=GIUSTIZIA,
    )
    assert result["event_type"] == "decreto_171_bis"


@pytest.mark.parametrize("ruolo", ["1234/2025/GDP", "RG 1234/2025 GDP"])
def test_a13_ruolo_giudice_di_pace(ruolo):
    registri = estrai_registri(f"Procedimento {ruolo}")
    assert [(item["numero"], item["anno"], item["registro_normalizzato"]) for item in registri] == [
        ("1234", "2025", "SIGP")
    ]
    result = classifica_pec_legale(
        subject=f"POSTA CERTIFICATA: Notificazione di cancelleria {ruolo}",
        body="Si comunica fissazione udienza al 03/03/2026",
        sender="gdp.roma@giustiziacert.it",
    )
    assert result["family"] == "comunicazione_giudice_pace"


def test_a13_giudice_di_pace_nel_testo():
    result = classifica_pec_legale(
        subject="POSTA CERTIFICATA: Notificazione di cancelleria",
        body="Giudice di Pace di Roma. Si comunica fissazione udienza al 03/03/2026",
        sender="gdp.roma@giustiziacert.it",
    )
    assert result["family"] == "comunicazione_giudice_pace"


def test_workflow_ricevuta_con_oggetto_originale_ingannevole():
    result = classifica_pec_legale(
        subject="CONSEGNA: Contestazione per mancata consegna merce",
        body="Ricevuta di avvenuta consegna. Il messaggio è stato consegnato nella casella di destinazione.",
        sender="posta-certificata@pec.aruba.it",
    )
    assert result["event_type"] == "ricevuta_consegna_pec"


# ---------------------------------------------------------------------------
# Allegati (A16/A17)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename,mime,expected",
    [
        ("EsitoAtto.xml", "application/xml", "tecnico"),
        ("DatiAtto.xml", "application/xml", "tecnico"),
        ("IndiceBusta.xml", "text/xml", "tecnico"),
        ("Comunicazione.xml", "application/xml", "tecnico"),
        ("atto.pdf.p7s", "application/pkcs7-signature", "firma"),
        ("smime.p7s", "application/pkcs7-signature", "firma"),
        ("contratto_locazione.pdf", "application/pdf", "da confermare"),
        ("estratto_conto.pdf", "application/pdf", "da confermare"),
        ("raccomandata_ar.pdf", "application/pdf", "da confermare"),
        ("fattura_esito.pdf", "application/pdf", "da confermare"),
        ("mandato_pagamento.pdf", "application/pdf", "da confermare"),
        ("sentenza_123_2026.pdf", "application/pdf", "atto"),
        ("ordinanza_cautelare.pdf", "application/pdf", "atto"),
        ("decreto_ingiuntivo.pdf.p7m", "application/pkcs7-mime", "atto"),
        ("verbale_udienza.pdf", "application/pdf", "atto"),
        ("procura_alle_liti.pdf.p7m", "application/pkcs7-mime", "procura"),
        ("mandato.pdf", "application/pdf", "procura"),
        ("ricevuta_accettazione.pdf", "application/pdf", "ricevute"),
        ("daticert.xml", "application/xml", "daticert"),
    ],
)
def test_a16_a17_classify_attachment_a_parole_intere(filename, mime, expected):
    label, _score, _reason = classify_attachment(
        AttachmentPayload(0, filename, mime, b"x" * 2000), "Deposito telematico daticert.xml postacert.eml"
    )
    assert label == expected


# ---------------------------------------------------------------------------
# D5: doppioni di termini perentori senza fascicolo collegato
# ---------------------------------------------------------------------------


def _item(**values):
    base = {
        "id": "S1",
        "stato": "APERTO",
        "note": "PEC_AUDIT:pec_primo",
        "source_message_id": "pec_primo",
        "data_scadenza": "2026-11-09",
        "deadline_profile_code": "CIV_OPPOSIZIONE_127_TER",
        "titolo": "Opposizione alla trattazione scritta ex art. 127-ter c.p.c.",
    }
    base.update(values)
    return SimpleNamespace(**base)


def _identity(rg="4321/2026", ufficio="tribunale.milano@civile.ptel.giustiziacert.it", code="CIV_OPPOSIZIONE_127_TER"):
    return _deadline_identity_line(rg=rg, ufficio=ufficio, profile_code=code, due_date="2026-11-09")


def test_d5_identita_completa_e_uguale_accorpa():
    existing = _item(note="PEC_AUDIT:pec_primo\n" + _identity())
    same, doubtful = _unlinked_deadline_duplicate(
        [existing], identity_line=_identity(), title="altro titolo", source_message_id="pec_secondo",
        marker="PEC_AUDIT:pec_secondo",
    )
    assert same is existing and doubtful is None


def test_d5_nel_dubbio_tiene_entrambe_e_marca():
    existing = _item(note="PEC_AUDIT:pec_primo\n" + _identity(ufficio=""))
    same, doubtful = _unlinked_deadline_duplicate(
        [existing], identity_line=_identity(ufficio=""), title=existing.titolo, source_message_id="pec_secondo",
        marker="PEC_AUDIT:pec_secondo",
    )
    assert same is None and doubtful is existing
    # scadenza precedente all'identita' (senza riga): stesso titolo, codice e data = possibile doppione
    legacy = _item()
    same, doubtful = _unlinked_deadline_duplicate(
        [legacy], identity_line=_identity(), title=legacy.titolo, source_message_id="pec_secondo",
        marker="PEC_AUDIT:pec_secondo",
    )
    assert same is None and doubtful is legacy


def test_d5_rg_diverso_o_annullata_non_e_doppione():
    other_rg = _item(note="PEC_AUDIT:pec_primo\n" + _identity(rg="1111/2026"))
    cancelled = _item(stato="ANNULLATO", note="PEC_AUDIT:pec_primo\n" + _identity())
    same, doubtful = _unlinked_deadline_duplicate(
        [other_rg, cancelled], identity_line=_identity(), title="x", source_message_id="pec_secondo",
        marker="PEC_AUDIT:pec_secondo",
    )
    assert same is None and doubtful is None


def _court_mime(subject: str, body: str, message_id: str) -> bytes:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "Cancelleria <tribunale.milano@civile.ptel.giustiziacert.it>"
    msg["To"] = "studio@pec.example.test"
    msg["Date"] = "Mon, 02 Nov 2026 08:30:00 +0100"
    msg["Message-ID"] = message_id
    msg.set_content(body)
    return msg.as_bytes(policy=policy.SMTP)


def test_d5_127_ter_reinviata_con_altro_message_id_senza_fascicolo_non_raddoppia(tmp_path):
    from pct.scadenziario import GestioneScadenziario

    scad_db = tmp_path / "scadenziario" / "scadenze.json"
    repo = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="audit",
        scadenziario_db_path=scad_db,
        agenda_db_path=tmp_path / "agenda" / "appuntamenti.json",
        fascicoli_db_path=tmp_path / "fascicoli" / "fascicoli.json",
        fascicoli_docs_path=tmp_path / "fascicoli" / "documenti",
        now_provider=lambda: datetime(2026, 11, 2, 9, 0, tzinfo=ROME_TZ),
    )
    subject = "Comunicazione di cancelleria - trattazione scritta ex art. 127-ter c.p.c. - RG 4321/2026"
    body = (
        "Tribunale di Milano. Nel procedimento RG 4321/2026 il giudice dispone la trattazione scritta con note "
        "scritte in sostituzione dell'udienza ai sensi dell'art. 127-ter c.p.c. Le parti possono opporsi."
    )
    for index, message_id in enumerate(("<127ter@giustiziacert.it>", "<127ter-bis@giustiziacert.it>")):
        repo.ingest_mime(_court_mime(subject, body, message_id), account_email="studio@pec.example.test",
                         folder="INBOX", imap_uid=f"u{index}")
        repo.run_pending_jobs(limit=50, actor="audit")

    deadlines = [
        item for item in GestioneScadenziario(str(scad_db)).tutte(solo_aperte=False)
        if item.deadline_profile_code == "CIV_OPPOSIZIONE_127_TER"
    ]
    assert len(deadlines) == 1
    deadline = deadlines[0]
    # Policy invariata: il 127-ter resta APERTO e perentorio, data calcolata come prima.
    assert getattr(deadline.stato, "value", deadline.stato) == "APERTO"
    assert deadline.perentorio is True
    assert deadline.data_scadenza[:10] == "2026-11-09"
    assert "PEC_DOPPIONE_DI:" in deadline.note


# ---------------------------------------------------------------------------
# D6: verifica_catena_pec trova anche termini proposti e ricezioni
# ---------------------------------------------------------------------------


def _load_verifica_catena():
    spec = importlib.util.spec_from_file_location("verifica_catena_pec_audit", ROOT / "scripts" / "verifica_catena_pec.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_d6_verifica_catena_cerca_tutti_i_marcatori(tmp_path):
    from pct.scadenziario import GestioneScadenziario, TipoTermine

    module = _load_verifica_catena()
    scad_db = tmp_path / "scadenze.json"
    manager = GestioneScadenziario(str(scad_db))
    manager.nuova("Impugnazione sentenza - termine lungo", TipoTermine.IMPUGNAZIONE, "2027-05-03",
                  note="PEC_TERMINE_PROPOSTO:pec_abc:CIV_APPELLO_LUNGO")
    manager.nuova("Promemoria ricezione", TipoTermine.ADEMPIMENTO, "2026-11-10", note="PEC_RICEZIONE:pec_abc")
    manager.nuova("Altra PEC", TipoTermine.ADEMPIMENTO, "2026-11-10", note="PEC_AUDIT:pec_abcdef")

    found = module._scadenze_del_messaggio({"SCADENZIARIO_DB": str(scad_db)}, "pec_abc")
    assert sorted(item["titolo"] for item in found) == ["Impugnazione sentenza - termine lungo", "Promemoria ricezione"]
    assert module._contiene_marcatore("uid PEC_AUDIT:pec_abc:hearing:1", module._marcatori_del_messaggio("pec_abc"))
