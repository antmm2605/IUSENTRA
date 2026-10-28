from __future__ import annotations

from pct.pec_legal_workflow import (
    classifica_pec_legale,
    estrai_registri,
    normalizza_oggetto_pec,
)
from pct.pec_pipeline import event_type_from_parsed


class _Attachment:
    def __init__(self, filename: str) -> None:
        self.filename = filename


def _classifica(subject: str, body: str = "", sender: str = "cancelleria@giustiziacert.it", attachments=None):
    return classifica_pec_legale(
        subject=subject,
        body=body,
        sender=sender,
        recipients=["studio@example.pec.it"],
        attachments=attachments or [{"filename": "Comunicazione.xml"}, {"filename": "daticert.xml"}],
        message_id="<msg-test@pec>",
    )


def test_registro_gdp_non_viene_trattato_come_cc():
    registri = estrai_registri("2962/2023/GDP deposito sentenza")
    assert registri[0]["suffisso"] == "GDP"
    assert registri[0]["registro_normalizzato"] == "SIGP"
    assert registri[0]["tabella_ministeriale"] == "SIGP_GIUDICE_DI_PACE"


def test_registri_duplicati_e_allegati_oggetto_non_duplicano_correlazione():
    registri = estrai_registri("274/2026/CC 274/2026/CC n. 1365_2016 RG APP n. 1365_2016 RG APP")

    assert [item["suffisso"] for item in registri] == ["CC", "RG_APP"]

    result = _classifica(
        "I: 274/2026/CC comunicazione controparte",
        sender="studio@example.pec.it",
        attachments=[_Attachment("documento.pdf")],
    )
    assert result["family"] == "pec_controparte"
    assert result["documents"]["has_pdf"] is True


def test_eventi_pec_richiesti_classificati_con_azione_operativa():
    cases = [
        ("2962/2023/GDP deposito sentenza", "deposito_sentenza", "comunicazione_giudice_pace"),
        ("274/2026/CC conferma udienza", "conferma_udienza", "comunicazione_cancelleria_civile"),
        ("139/2023/CC deposito CTU", "deposito_ctu", "comunicazione_cancelleria_civile"),
        ("12756/2026/PENALE AVVISO UDIENZA CASS", "udienza_fissata", "cassazione_penale"),
        ("63/2025/VG SOST. GIUDICE DA [ROSSI SIMONA] A [GELSO GIANLUCA]", "sostituzione_giudice", "volontaria_giurisdizione"),
        ("500/2026/LAV rinvio udienza", "rinvio_udienza", "comunicazione_lavoro"),
        ("121/2018/CC comunicazione generica", "pec_non_riconosciuta", "comunicazione_cancelleria_civile"),
    ]
    for subject, event_type, family in cases:
        result = _classifica(subject)
        assert result["event_type"] == event_type
        assert result["family"] == family
        assert result["azione_proposta"]


def test_deposito_ricorso_cassazione_penale_estrae_rg_app_e_rg_nr():
    result = _classifica(
        "FWD: I: Deposito ricorso per cassazione per FEO NATALE - proc. pen. n. 1365_2016 RG APP - n. 1364_2011 RG NR",
        attachments=[{"filename": "messaggio_originale.eml"}, {"filename": "ricorso.pdf.p7m"}],
    )
    assert result["normalized_subject"].startswith("Deposito ricorso per cassazione")
    assert result["family"] == "cassazione_penale"
    assert result["event_type"] == "deposito_ricorso_cassazione_penale"
    assert {item["suffisso"] for item in result["registri"]} == {"RG_APP", "RG_NR"}
    assert result["documents"]["has_original_eml"] is True
    assert result["documents"]["has_p7m"] is True


def test_deposito_atti_penali_cassazione_da_giustiziacert_resta_penale():
    result = classifica_pec_legale(
        subject=(
            "Deposito ricorso per cassazione (con n. 1 allegato) per FEO NATALE - "
            "proc. pen. n. 1365_2016 RG APP - n. 1364_2011 RG NR"
        ),
        sender="depositoattipenali.ca.reggiocalabria@giustiziacert.it",
        recipients=["studio@example.pec.it"],
        attachments=[{"filename": "messaggio_originale.eml"}, {"filename": "ricorso.pdf.p7m"}],
        message_id="<deposito-cassazione-penale@pec>",
    )

    assert result["family"] == "cassazione_penale"
    assert result["event_type"] == "deposito_ricorso_cassazione_penale"
    assert {item["suffisso"] for item in result["registri"]} == {"RG_APP", "RG_NR"}
    assert any(item["numero"] == "1365" and item["anno"] == "2016" for item in result["registri"])
    assert any(item["numero"] == "1364" and item["anno"] == "2011" for item in result["registri"])
    assert result["documents"]["has_original_eml"] is True
    assert result["documents"]["has_p7m"] is True
    assert "penale/Cassazione" in result["azione_proposta"]


def test_notifiche_penali_corte_appello_generale_estraggono_rg_app():
    result = classifica_pec_legale(
        subject="generale/2016/001365/Corte di Appello a carico di p.p. c/ Feo Natale.",
        sender="notifichepenali.ca.reggiocalabria@penale.ptel.giustiziacert.it",
        recipients=["studio@example.pec.it"],
        attachments=[{"filename": "Comunicazione.xml"}, {"filename": "daticert.xml"}],
        message_id="<notifiche-penali-ca-rc@pec>",
    )

    assert result["family"] == "deposito_penale_pdp"
    assert result["event_type"] == "comunicazione_penale_pdp"
    assert result["creates_deadline"] is False
    assert len(result["registri"]) == 1
    assert result["registri"][0]["numero"] == "1365"
    assert result["registri"][0]["anno"] == "2016"
    assert result["registri"][0]["suffisso"] == "RG_APP"
    assert result["registri"][0]["fonte_ruolo"] == "generale_corte_appello"
    assert result["documents"]["has_daticert"] is True
    assert result["documents"]["has_comunicazione_xml"] is True
    assert "fascicolo penale" in result["azione_proposta"]


def test_ricevuta_accettazione_non_chiude_deposito():
    result = _classifica("Ricevuta di accettazione del messaggio di deposito RG 274/2026/CC")
    assert result["event_type"] == "ricevuta_accettazione_pec"
    assert result["receipt"]["closes_deposit"] is False
    assert "non chiude" in result["receipt"]["does_not_close_deposit_reason"]


def test_fattura_sdi_mancata_consegna_non_crea_scadenza_processuale():
    result = _classifica(
        "Notifica di mancata consegna",
        sender="sdi44@pec.fatturapa.it",
        attachments=[{"filename": "IT01234567890_00001.xml"}],
    )
    assert result["family"] == "fattura_sdi"
    assert result["event_type"] == "fattura_sdi_mancata_consegna"
    assert result["creates_deadline"] is False
    assert "fatturazione" in result["azione_proposta"].lower()


def test_udienza_online_e_in_presenza_rilevano_modalita():
    online = _classifica("274/2026/CC udienza fissata", "Collegamento https://meet.google.com/abc-defg-hij")
    presenza = _classifica("274/2026/CC udienza in presenza", "Aula 3 secondo piano")
    assert online["event_type"] == "udienza_online"
    assert online["udienza"]["modalita"] == "online"
    assert online["udienza"]["link"].startswith("https://")
    assert presenza["event_type"] == "udienza_in_presenza"
    assert presenza["udienza"]["luogo"] == "Aula 3"


def test_prefissi_inoltro_non_creano_chiavi_correlazione_diverse():
    base = _classifica("Deposito ricorso per cassazione proc. pen. n. 1365_2016 RG APP")
    forwarded = _classifica("FWD: I: Deposito ricorso per cassazione proc. pen. n. 1365_2016 RG APP")
    assert normalizza_oggetto_pec("FWD: I: Deposito ricorso") == "Deposito ricorso"
    assert base["normalized_subject"] == forwarded["normalized_subject"]
    assert base["correlation_key"] == forwarded["correlation_key"]


def test_pipeline_event_type_usa_workflow_legale():
    parsed = {
        "headers": {"subject": "63/2025/VG SOST. GIUDICE"},
        "body": {"text": "SOST. GIUDICE DA [ROSSI] A [BIANCHI]"},
        "legal_workflow": _classifica("63/2025/VG SOST. GIUDICE"),
    }
    assert event_type_from_parsed(parsed, []) == "sostituzione_giudice"


def test_eventi_deposito_e_famiglie_legali_aggiuntive():
    cases = [
        ("Rifiuto deposito 274/2026/CC", {}, "rifiuto_deposito", "comunicazione_cancelleria_civile"),
        ("Accettazione deposito 274/2026/CC", {}, "accettazione_deposito", "comunicazione_cancelleria_civile"),
        ("Ricevuta di avvenuta consegna notifica L. 53/1994", {}, "ricevuta_consegna_pec", "notifica_avvocato"),
        ("Decreto da notificare 274/2026/CC", {}, "decreto_o_ricorso_da_notificare", "comunicazione_cancelleria_civile"),
        ("Revoca udienza 274/2026/CC", {}, "revoca_udienza", "comunicazione_cancelleria_civile"),
        ("Deposito telematico DatiAtto.xml 274/2026/CC", {}, "pec_non_riconosciuta", "deposito_pct_civile"),
        ("Deposito atti penali PDP proc. pen. n. 10/2026", {}, "pec_non_riconosciuta", "deposito_penale_pdp"),
        ("Cassazione civile comunicazione 55/2026/CASSCI", {}, "pec_non_riconosciuta", "cassazione_civile"),
        (
            "Comunicazione da giustiziacert con messaggio originale",
            {"sender": "cancelleria@giustiziacert.it", "attachments": [{"filename": "originale.eml"}]},
            "messaggio_originale_giustiziacert",
            "comunicazione_cancelleria_civile",
        ),
        ("PEC ordinaria da classificare", {"sender": "ordinaria@example.pec.it"}, "pec_non_riconosciuta", "pec_non_riconosciuta"),
    ]

    for subject, kwargs, event_type, family in cases:
        result = _classifica(subject, **kwargs)
        assert result["event_type"] == event_type
        assert result["family"] == family


def test_esito_controlli_automatici_non_e_udienza_ne_scadenza():
    # oggetti sintetici costruiti sui modelli reali (misura su replica studio, 27/10/2026)
    for oggetto in (
        "POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO Note scritte in sostituzione udienza 123/2026",
        "POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO - Memoria - Tribunale di Bari",
    ):
        esito = classifica_pec_legale(subject=oggetto, sender="tribunale.bari@civile.ptel.giustiziacert.it",
                                      attachments=["EsitoAtto.xml", "daticert.xml", "postacert.eml"])
        assert esito["event_type"] == "esito_controlli"
        assert esito["creates_deadline"] is False and esito["receipt"]["closes_deposit"] is False
    acc = classifica_pec_legale(subject="POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO Note in sostituzione udienza 1/2026")
    assert acc["event_type"] == "accettazione_deposito"


def _comunicazione(oggetto: str) -> str:
    # struttura di Comunicazione.xml (tag ministeriali); valori sintetici
    return (f"<Comunicazione><CodiceUG>0000000</CodiceUG><NumeroRuolo>1/2026</NumeroRuolo><Oggetto>{oggetto}</Oggetto>"
            "<Contenuto>Si comunica</Contenuto></Comunicazione>\n<mittente>tribunale.bari@civile.ptel.giustiziacert.it</mittente>")


def test_comunicazione_cancelleria_usa_l_oggetto_del_registro():
    attese = {
        "FISSAZIONE TERMINE PER NOTE IN SOSTITUZIONE UDIENZA": ("udienza_sostituita_da_note_scritte", True),
        "REVOCA UDIENZA E FISSAZIONE TERMINE PER NOTE IN SOST. UDIENZA": ("udienza_sostituita_da_note_scritte", True),
        "RINVIO AD ALTRA UDIENZA DI DISCUSSIONE": ("rinvio_udienza", True),
        "DIFFERIMENTO UDIENZA": ("rinvio_udienza", True),
        "FISSAZIONE UDIENZA DI DISCUSSIONE": ("udienza_fissata", True),
        "DESIGNAZIONE GIUDICE": ("designazione_giudice", False),
        "ANNOTAZIONE": ("comunicazione_cancelleria", False),
        "COSTITUZIONE PARTI": ("comunicazione_cancelleria", False),
    }
    for oggetto, (evento, scadenza) in attese.items():
        esito = classifica_pec_legale(subject="POSTA CERTIFICATA: COMUNICAZIONE 1/2026 Tribunale di Bari",
                                      body=_comunicazione(oggetto), attachments=["Comunicazione.xml", "daticert.xml"])
        assert (esito["event_type"], esito["creates_deadline"]) == (evento, scadenza), oggetto


def test_comunicazione_senza_ufficio_non_certifica_e_sentenze_restano_al_testo():
    senza = classifica_pec_legale(subject="COMUNICAZIONE", body="<Comunicazione><Oggetto>DIFFERIMENTO UDIENZA</Oggetto></Comunicazione>")
    assert senza["event_type"] != "rinvio_udienza"  # senza busta di un ufficio l'Oggetto non certifica nulla
    sent = classifica_pec_legale(subject="POSTA CERTIFICATA: COMUNICAZIONE 2/2026",
                                 body=_comunicazione("SENTENZA A VERBALE (art. 281 sexies cpc)") + "\nsentenza a verbale ex art. 281-sexies")
    assert sent["event_type"] != "comunicazione_cancelleria"


def test_oggetti_ufficiali_riconosciuti_senza_modelli():
    casi = {
        "POSTA CERTIFICATA: Notifica di scarto 12345678901": ("fattura_sdi", "fattura_sdi_scarto", False),
        "POSTA CERTIFICATA: Notifica di mancata consegna 12345678901": ("fattura_sdi", "fattura_sdi_mancata_consegna", False),
        "POSTA CERTIFICATA: Ricevuta di consegna 12345678901": ("fattura_sdi", "fattura_sdi", False),
        "POSTA CERTIFICATA: Ricevuta di Avvenuta protocollazione": ("ente_pubblico", "ricevuta_protocollazione", False),
        "POSTA CERTIFICATA: Notifica avvenuta registrazione protocollo n. 123 del 01-02-2026 - POSTA CERTIFICATA: Diffida":
            ("ente_pubblico", "ricevuta_protocollazione", False),
        "POSTA CERTIFICATA: Avviso FISSAZIONE UDIENZA per il ricorso 202600123 COD1tarve202600123_1":
            ("comunicazione_pat", "udienza_fissata", True),
        "POSTA CERTIFICATA: Avviso DEPOSITO SENTENZA per il ricorso 202600123 COD1tarrm202600123_1":
            ("comunicazione_pat", "deposito_sentenza", True),
        "POSTA CERTIFICATA: Avviso INVITO AL PAGAMENTO per il ricorso 202600123 COD1tarrc202600123_1":
            ("comunicazione_pat", "invito_pagamento_contributo", True),
        "POSTA CERTIFICATA: Avviso DEPOSITO MEMORIA per il ricorso 202600123 COD1tarve202600123_1":
            ("comunicazione_pat", "avviso_segreteria_tar", False),
        "POSTA CERTIFICATA: Registrazione 202600123 Istanza fissazione udienza - ricorso per ottemperanza":
            ("comunicazione_pat", "deposito_pat_registrato", False),
        "POSTA CERTIFICATA: Mancato deposito. Ricorso per l'ottemperanza": ("comunicazione_pat", "deposito_pat_non_riuscito", False),
        "POSTA CERTIFICATA: Ricevuta protocollo": ("ente_pubblico", "ricevuta_protocollazione", False),
        "POSTA CERTIFICATA: Protocollo nr: 1234 - del 01/02/2026 - AOOUSPRC - Contenzioso":
            ("ente_pubblico", "comunicazione_ente_protocollata", False),
        "POSTA CERTIFICATA: Hai terminato lo spazio su questa casella PEC": ("gestore_pec", "casella_pec_piena", False),
    }
    for oggetto, (famiglia, evento, scadenza) in casi.items():
        r = classifica_pec_legale(subject=oggetto, body=oggetto)
        assert (r["family"], r["event_type"], r["creates_deadline"]) == (famiglia, evento, scadenza), oggetto


def test_ricevuta_pec_di_un_messaggio_protocollato_resta_ricevuta():
    r = classifica_pec_legale(subject="ACCETTAZIONE: Protocollo nr: 12 - del 01/02/2026 - AOOUSPRC - Contenzioso",
                              body="Ricevuta di accettazione")
    assert r["event_type"] == "ricevuta_accettazione_pec"


def test_istanza_o_attesa_di_fissazione_non_e_un_udienza_fissata():
    for oggetto in ("ATTESA FISSAZIONE UDIENZA - pignoramento ex art. 543 bis", "Richiesta di fissazione udienza"):
        r = classifica_pec_legale(subject=oggetto, body=oggetto)
        assert r["event_type"] != "udienza_fissata" and not r["creates_deadline"]


def test_testi_fissi_di_sistema_esecuzioni_protocollo_e_reindirizzamento():
    casi = [
        ("POSTA CERTIFICATA: Avviso di Disponibilità", "Avviso di disponibilità Ministero della Giustizia UNEP - TRIBUNALE DI BARI l'atto di PIGNORAMENTO è disponibile alla restituzione",
         ("esecuzione", "atto_unep_disponibile", True)),
        ("POSTA CERTIFICATA: Invio Dichiarazione di Terzo", "Si trasmette la dichiarazione (ex art. 547 cpc)", ("esecuzione", "dichiarazione_terzo", False)),
        ("POSTA CERTIFICATA: Pratica 1 - Perdita di efficacia del pignoramento", "non ci risulta pervenuta alcuna notifica",
         ("esecuzione", "inefficacia_pignoramento_segnalata", False)),
        ("POSTA CERTIFICATA: Ricevuta protocollo - POSTA CERTIFICATA: Diffida", "ai sensi dell'art. 22 della legge 241/1990", ("ente_pubblico", "ricevuta_protocollazione", False)),
        ("POSTA CERTIFICATA: R: Notificazione", "Ricevuta Automatica di Protocollo Numero: X. I messaggi in ingresso non saranno letti",
         ("ente_pubblico", "ricevuta_protocollazione", False)),
        ("POSTA CERTIFICATA: Diffida e messa in mora", "La Pec deve essere ritrasmessa all'unico indirizzo di posta certificata",
         ("pec_da_reindirizzare", "pec_non_presa_in_carico", False)),
    ]
    for oggetto, corpo, (famiglia, evento, scadenza) in casi:
        r = classifica_pec_legale(subject=oggetto, body=corpo)
        assert (r["family"], r["event_type"], r["creates_deadline"]) == (famiglia, evento, scadenza), oggetto


def test_biglietto_di_cancelleria_usa_l_oggetto_del_registro():
    corpo = ("Tribunale di Bari -- Notificazione di cancelleria ai sensi del D.L. 179/2012 ... registro di cancelleria sono "
             "associati a: Data Evento: 01/02/2026 Tipo Evento: X Oggetto: FISSAZIONE TERMINE PER NOTE IN SOSTITUZIONE UDIENZA "
             "Descrizione: termine al 10/03/2026\nmittente@civile.ptel.giustiziacert.it")
    r = classifica_pec_legale(subject="POSTA CERTIFICATA: Tribunale di Bari Notificazione ai sensi del D.L. 179/2012", body=corpo)
    assert r["event_type"] == "udienza_sostituita_da_note_scritte" and r["creates_deadline"]
