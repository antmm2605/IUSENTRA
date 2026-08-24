from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from pct.fascicolo_document_presidio import analyze_fascicolo_document_texts
from pct.fascicolo_operational_presidio import build_fascicolo_operational_presidio
from web.services.react_fascicoli_bridge import (
    _activities,
    _technical_activity_records,
    _visible_activity_records,
)


def test_presidio_operativo_unifica_documenti_pec_relata_economia_e_doppioni():
    fascicolo = SimpleNamespace(id="FASC-3950")
    payload = build_fascicolo_operational_presidio(
        fascicolo=fascicolo,
        document_presidio={
            "status": "presidiato",
            "tone": "warning",
            "summary": "Decreto udienza letto dal fascicolo.",
            "actions": [
                {
                    "type": "note_127_ter",
                    "title": "Depositare note scritte in sostituzione dell'udienza",
                    "description": "Il giudice ha assegnato termine per note scritte.",
                    "dateIso": "2026-07-20",
                    "peremptory": True,
                    "requiresCommunicationDate": False,
                    "source": "Decreto fissazione udienza.PDF",
                },
                {
                    "type": "richiesta_presenza_127_bis",
                    "title": "Valutare richiesta di trattazione in presenza",
                    "description": "Termine collegato alla comunicazione del decreto.",
                    "dateIso": "",
                    "peremptory": False,
                    "requiresCommunicationDate": True,
                    "source": "Decreto fissazione udienza (1).PDF",
                },
            ],
            "sources": [{"name": "Decreto fissazione udienza.PDF"}],
        },
        notification_relata={
            "status": "da_acquisire",
            "tone": "warning",
            "statusLabel": "Prova notifica da acquisire",
            "systemNotification": "Scarica RAC e RdAC prima del deposito.",
            "primaryHref": "/notifiche-legali",
            "proofDocuments": 0,
        },
        payment_summary={
            "stato": "da_presidiare",
            "statoLabel": "Da presidiare",
            "tone": "warning",
            "totaleRegistratoLabel": "€ 0,00",
            "anticipazioniDaRecuperareLabel": "€ 98,00",
            "items": {
                "contributo_unificato": {
                    "label": "Contributo unificato",
                    "status": "da_registrare",
                    "tone": "warning",
                    "importoLabel": "€ 98,00",
                    "note": "Ricevuta o prova pagamento da registrare.",
                    "documentoFonte": "Ricevuta contributo unificato.pdf",
                },
                "liquidazione_giudice": {
                    "label": "Liquidazione",
                    "status": "da_registrare",
                    "tone": "warning",
                    "importoLabel": "€ 1.100,00",
                    "note": "Importo liquidato dal giudice da confermare.",
                    "documentoFonte": "Sentenza.pdf",
                },
                "parcella": {
                    "label": "Parcella",
                    "status": "da_emettere",
                    "tone": "warning",
                    "importoLabel": "€ 1.320,00",
                    "note": "Parcella da emettere dopo controllo sentenza.",
                },
            },
        },
        deposits=[{"status": "rifiutato", "tone": "danger", "message": "Esito deposito rifiutato", "source": "PEC cancelleria"}],
        duplicate_group={"count": 2, "label": "Spagnolo Sara / RG 3950/2026", "href": "/fascicoli?rg=3950", "refs": ["2026/308", "2026/335"]},
        sentenze_economiche={"totals": {"sentenze_lette": 1, "da_verificare": 1}, "worklist": [{"label": "Liquidazione"}]},
        today=date(2026, 7, 6),
    )

    sectors = {sector["id"]: sector for sector in payload["sectors"]}
    action_titles = [action["title"] for action in payload["actions"]]

    assert payload["status"] == "critico"
    assert payload["nextAction"]["sector"] == "pec"
    assert "Esito deposito rifiutato" in payload["nextAction"]["reason"]
    assert set(sectors) == {"pec", "documenti", "relata", "economico", "doppioni"}
    assert any("Depositare note scritte" in title for title in action_titles)
    assert any("Confermare la data di comunicazione PEC" in title for title in action_titles)
    assert any("Registrare contributo unificato" in title and "€ 98,00" in title for title in action_titles)
    assert any("Registrare liquidazione del giudice" in title and "€ 1.100,00" in title for title in action_titles)
    assert any("Verificare importi liquidati in sentenza" in title for title in action_titles)
    assert any("Riconciliare pratiche doppie" in title for title in action_titles)
    assert sectors["economico"]["questions"]
    assert any("Contributo, esborsi, liquidazione" in question for question in payload["questions"])


def test_presidio_operativo_non_attribuisce_controlli_senza_prova_o_dati_identificativi():
    fascicolo = SimpleNamespace(id="FASC-3951")
    payload = build_fascicolo_operational_presidio(
        fascicolo=fascicolo,
        document_presidio={
            "status": "aggiornato",
            "tone": "success",
            "summary": "Documenti controllati: non risultano ulteriori decreti, udienze o termini processuali da presidiare.",
            "actions": [],
            "sources": [],
            "warnings": [],
        },
        notification_relata={
            "status": "nessuna_notifica",
            "tone": "neutral",
            "statusLabel": "Nessuna notifica in lavorazione",
            "systemNotification": "Nessuna notifica, relata o prova collegata da completare nel fascicolo.",
        },
        payment_summary={
            "stato": "da_presidiare",
            "statoLabel": "Da presidiare",
            "tone": "warning",
            "totaleRegistratoLabel": "€ 0,00",
            "anticipazioniDaRecuperareLabel": "€ 0,00",
            "items": {
                "contributo_unificato": {
                    "status": "da_registrare",
                    "tone": "warning",
                    "note": "Non risulta una ricevuta di pagamento nel fascicolo.",
                },
            },
        },
        deposits=[],
        duplicate_group=None,
        duplicate_scope_count=0,
        duplicate_check_ready=False,
        duplicate_check_reason="Cliente e numero R.G. devono essere completi per confrontare il fascicolo con l'archivio dello studio.",
        today=date(2026, 8, 24),
    )

    sectors = {sector["id"]: sector for sector in payload["sectors"]}

    assert sectors["documenti"]["statusLabel"] == "Nessun documento procedurale da analizzare"
    assert sectors["pec"]["statusLabel"] == "Verifica PEC necessaria"
    assert sectors["pec"]["actions"][0]["href"].endswith("#cancelleria")
    assert sectors["relata"]["statusLabel"] == "Nessuna notifica in lavorazione"
    assert sectors["relata"]["actions"] == []
    assert sectors["economico"]["statusLabel"] == "1 controllo economico aperto"
    assert sectors["doppioni"]["statusLabel"] == "Controllo doppioni non eseguibile"
    assert sectors["doppioni"]["actions"][0]["href"].endswith("#profilo")


def test_presidio_operativo_documenta_perimetro_del_controllo_doppioni_completato():
    fascicolo = SimpleNamespace(id="FASC-3952")
    payload = build_fascicolo_operational_presidio(
        fascicolo=fascicolo,
        document_presidio={},
        notification_relata={"status": "nessuna_notifica", "statusLabel": "Nessuna notifica in lavorazione"},
        payment_summary={},
        deposits=[{"status": "depositato", "source": "Ricevuta PCT"}],
        duplicate_group=None,
        duplicate_scope_count=17,
        duplicate_check_ready=True,
    )

    sectors = {sector["id"]: sector for sector in payload["sectors"]}

    assert sectors["pec"]["statusLabel"] == "Nessuna anomalia negli esiti letti"
    assert sectors["doppioni"]["statusLabel"] == "Controllo doppioni completato"
    assert "17 fascicoli disponibili nello studio" in sectors["doppioni"]["summary"]


def test_documento_collegato_senza_rg_diventa_verifica_e_non_viene_ignorato():
    fascicolo = SimpleNamespace(
        id="FASC-3953",
        numero_rg="3953",
        anno_rg="2026",
        nome_cliente="Montagnese Elisabetta",
        controparte="Stillitano Francesco",
    )

    payload = analyze_fascicolo_document_texts(
        fascicolo,
        {"decreto-1": "Il Giudice rinvia la causa all'udienza del 14/10/2026."},
        {"decreto-1": {"filename": "Decreto_28147819.pdf"}},
        today=date(2026, 8, 24),
    )

    assert payload["status"] == "da_verificare"
    assert payload["tone"] == "warning"
    assert payload["sources"] == [{"documentId": "decreto-1", "name": "Decreto_28147819.pdf"}]
    assert payload["actions"][0]["type"] == "verifica_collegamento_documento"
    assert payload["actions"][0]["documentId"] == "decreto-1"
    assert "Nessun termine è escluso" in payload["summary"]
    assert all("ignorato" not in warning for warning in payload["warnings"])

    operational = build_fascicolo_operational_presidio(
        fascicolo=fascicolo,
        document_presidio=payload,
        notification_relata={},
        payment_summary={},
        deposits=[],
        duplicate_group=None,
        duplicate_scope_count=1,
        duplicate_check_ready=True,
        today=date(2026, 8, 24),
    )
    document_sector = next(sector for sector in operational["sectors"] if sector["id"] == "documenti")
    assert document_sector["status"] == "da_verificare"
    assert document_sector["statusLabel"] == "1 documento da verificare"
    assert document_sector["actions"][0]["href"].endswith("#documenti")


def test_acquisizioni_tecniche_non_si_presentano_come_attivita_processuali():
    acquisizione = SimpleNamespace(
        id="SYNC-1",
        tipo="CONSULTAZIONE",
        titolo="Acquisizione file ufficiali — Decreto",
        descrizione="1 file ufficiali acquisiti localmente da PolisWeb / PST. Download ufficiale completo via Local Signer / PST.",
        data="2026-04-04",
        creato_il="2026-04-04T10:30:00",
        esito="IN_ATTESA",
    )
    udienza = SimpleNamespace(
        id="UDIENZA-1",
        tipo="UDIENZA",
        titolo="Udienza (importata da PolisWeb)",
        descrizione="Udienza automaticamente sincronizzata da PolisWeb — RG 1025/2024",
        data="2026-12-12",
        creato_il="2026-04-04T10:31:00",
        esito="IN_ATTESA",
    )
    fascicolo = SimpleNamespace(id="FASC-EVENTI", attivita=[acquisizione, udienza])

    visible = _visible_activity_records(fascicolo)
    technical = _technical_activity_records(fascicolo)
    assert [record.id for record in visible] == ["UDIENZA-1"]
    assert [record.id for record in technical] == ["SYNC-1"]

    processual_payload = _activities(fascicolo, records=visible)
    technical_payload = _activities(fascicolo, records=technical, technical=True)
    assert processual_payload[0]["result"] == "REGISTRATO"
    assert processual_payload[0]["updateAction"] == ""
    assert technical_payload[0]["result"] == "REGISTRATO"
    assert technical_payload[0]["updateAction"] == ""
    assert technical_payload[0]["deleteAction"] == ""


def test_attivita_derivata_da_documento_espone_fonte_interna_e_nasconde_il_marcatore_tecnico():
    attivita = SimpleNamespace(
        id="UDIENZA-SORGENTE-1",
        tipo="UDIENZA",
        titolo="Rinvio udienza",
        descrizione=(
            "Attività per l'avvocato: udienza rinviata. "
            "Fonte documentale: Decreto rinvio udienza.pdf.p7m "
            "Contesto letto: Il Giudice rinvia la causa all'udienza del 17/04/2026."
        ),
        note="PEC_DOCUMENT_PRESIDIO:docpresidio:FASC-SORGENTE:DOC-UDIENZA:udienza:17/04/2026",
        data="2026-04-17",
        esito="IN_ATTESA",
    )
    fascicolo = SimpleNamespace(id="FASC-SORGENTE", attivita=[attivita])

    payload = _activities(fascicolo)

    assert payload[0]["sourceDocumentId"] == "DOC-UDIENZA"
    assert payload[0]["sourceDocumentHref"] == "/fascicoli/FASC-SORGENTE/documenti/DOC-UDIENZA/visualizza"
    assert payload[0]["sourceDocumentDownloadHref"] == "/fascicoli/FASC-SORGENTE/documenti/DOC-UDIENZA/scarica"
    assert payload[0]["sourceDocumentLabel"] == "Decreto rinvio udienza.pdf.p7m"
    assert payload[0]["sourceExcerpt"] == "Il Giudice rinvia la causa all'udienza del 17/04/2026"
    assert payload[0]["sourceIsDerived"] is True
    assert payload[0]["readOnly"] is True
    assert payload[0]["updateAction"] == ""
    assert payload[0]["deleteAction"] == ""
    assert "PEC_DOCUMENT_PRESIDIO" not in payload[0]["notes"]


def test_udienza_rilevata_storica_non_espone_comandi_di_stato_o_eliminazione():
    attivita = SimpleNamespace(
        id="UDIENZA-STORICA-1",
        tipo="UDIENZA",
        titolo="Udienza rilevata",
        data="2023-03-01",
        esito="IN_ATTESA",
    )
    fascicolo = SimpleNamespace(id="FASC-STORICO", attivita=[attivita])

    payload = _activities(fascicolo)

    assert payload[0]["readOnly"] is True
    assert payload[0]["sourceDocumentHref"] == ""
    assert payload[0]["updateAction"] == ""
    assert payload[0]["deleteAction"] == ""
