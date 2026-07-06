from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from pct.fascicolo_operational_presidio import build_fascicolo_operational_presidio


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
