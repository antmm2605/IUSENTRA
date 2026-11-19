from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from pct.fascicolo_operational_presidio import build_fascicolo_operational_presidio
from web.services.react_fascicoli_bridge import _notification_relata


def _doc(
    doc_id: str,
    nome: str,
    *,
    note: str = "",
    tipo: str = "COMUNICAZIONE",
    percorso: str = "",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=doc_id,
        nome=nome,
        nome_originale=nome,
        nome_portale=nome,
        tipo=tipo,
        tipo_atto_portale="",
        classificazione_portale="Gestionale precedente",
        note=note,
        tags=["quickorganizer", "import-pratiche"],
        percorso=percorso or f"FTEST/{doc_id}.eml",
        hash_sha256=doc_id * 8,
        prova_notifica=False,
    )


def test_due_consegne_della_stessa_notifica_restano_consultabili() -> None:
    from web.services.react_fascicoli_bridge import _notification_communication_documents

    prima = _doc("1", "CONSEGNA Notificazione ai sensi della legge n. 53.eml", note="Notifica ID: ABC123")
    seconda = _doc("2", prima.nome, note=prima.note)
    copia = _doc("3", prima.nome, note=prima.note)
    copia.hash_sha256 = prima.hash_sha256
    fascicolo = SimpleNamespace(documenti=[prima, seconda, copia])

    assert [doc.id for doc in _notification_communication_documents(fascicolo)] == ["1", "2"]


def test_copia_in_chiaro_del_deposito_non_e_l_atto_notificato() -> None:
    from web.services.react_fascicoli_bridge import _notification_communication_documents

    copia = _doc("1", "COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO: Ricorso (originale notificato).eml")
    atto = _doc("2", "Ricorso (originale notificato).pdf", tipo="RICORSO", percorso="FTEST/ricorso.pdf")
    assert [doc.id for doc in _notification_communication_documents(SimpleNamespace(documenti=[copia, atto]))] == ["2"]


def test_relata_storica_con_rac_rdac_e_deposito_non_diventa_da_firmare() -> None:
    fascicolo = SimpleNamespace(
        id="FTEST",
        documenti=[
            _doc(
                "1",
                "Ricorso Rossi (originale notificato).pdf",
                tipo="RICORSO",
                note="data notifica: 05/07/2023 ore: 18:15 Notifica ID: ABC123",
                percorso="FTEST/ricorso.pdf",
            ),
            _doc(
                "2",
                "Relata di notifica.pdf",
                tipo="NOTIFICA",
                note="data notifica: 05/07/2023 ore: 18:15 Notifica ID: ABC123",
                percorso="FTEST/relata.pdf",
            ),
            _doc(
                "3",
                "Notificazione ai sensi della legge n. 53 - 1994 [Notifica_ID:ABC123]",
                note="Email importata da QuickOrganizer.",
            ),
            _doc(
                "4",
                "ACCETTAZIONE: Notificazione ai sensi della legge n. 53 - 1994 [Notifica_ID:ABC123]",
                note="Email importata da QuickOrganizer.",
            ),
            _doc(
                "5",
                "CONSEGNA: Notificazione ai sensi della legge n. 53 - 1994 [Notifica_ID:ABC123]",
                note="Email importata da QuickOrganizer.",
            ),
            _doc(
                "6",
                "CONSEGNA_ DEPOSITO TELEMATICO_ Ricorso Rossi (originale notificato).pdf RG_ 1_2023 [RefID_001_TEST]",
                note="Import QuickOrganizer.",
                percorso="FTEST/deposito-prova.zip",
            ),
        ],
    )

    payload = _notification_relata(fascicolo, [])

    assert payload["status"] == "prova_depositata"
    assert payload["statusLabel"] == "Prova notifica depositata"
    assert payload["proofComplete"] is True
    assert payload["proofDeposited"] is True
    assert payload["primaryLabel"] == "Apri prova depositata"
    assert payload["primaryHref"] == "/fascicoli/FTEST/documenti/6/visualizza"
    assert next(passo for passo in payload["steps"] if passo["id"] == "acquisizione")["status"] == "superato"
    assert all(step["status"] != "da_firmare" for step in payload["steps"])
    assert "nessuna nuova notifica da preparare" in payload["systemNotification"]

    presidio = build_fascicolo_operational_presidio(
        fascicolo=fascicolo,
        document_presidio={},
        notification_relata=payload,
        payment_summary={},
        deposits=[],
        duplicate_group=None,
        sentenze_economiche=None,
    )
    relata_sector = next(sector for sector in presidio["sectors"] if sector["id"] == "relata")
    assert relata_sector["actions"] == []


def test_busta_con_refid_senza_ricevuta_non_prova_il_deposito():
    from web.services.react_fascicoli_bridge import _notification_proof_deposit_confirmed

    doc = _doc("B", "DEPOSITO TELEMATICO: Ricorso originale notificato [RefID_001_TEST].eml")
    assert not _notification_proof_deposit_confirmed(doc)


@pytest.mark.parametrize(("rg_busta", "id_ricevuta", "numero_consegne", "collegata"), [
    ("120/2026", "RinnovoA", 2, True),
    ("121/2026", "RinnovoA", 2, False),
    ("120/2026", "RinnovoB", 2, False),
    ("120/2026", "RinnovoA", 3, False),
])
def test_busta_di_rinnovazione_riusa_lo_stesso_riscontro_nel_presidio(rg_busta, id_ricevuta, numero_consegne, collegata):
    from pct.ragionamento.eventi import depositi_eseguiti
    from pct.ragionamento.modello import Atto
    from pct.ragionamento.regole.termini_assegnati import _busta_della_rinnovazione
    from web.services.pannelli_pronti_ricomposizione import allinea_relata_al_riscontro

    intestazione = (
        f"Oggetto: DEPOSITO TELEMATICO: Ricorso originale notificato.pdf RG: {rg_busta} [RefID_001_abc]\n"
        "Destinatari: tribunale.esempio@civile.ptel.giustiziacert.it\n"
    )
    inviata = Atto("BUSTA", "invio.eml", "messaggio_pec", "", testo=(
        intestazione + "Data: 12/04/2026 18:18\n\n[Allegato: Atto.enc]"))
    chiara = Atto("CHIARA", "copia.eml", "messaggio_pec", "", testo=(
        intestazione + "\n[Allegato: DatiAtto.xml.p7m; parte 1.2]\n"
        f"[Allegato: ACCETTAZIONE_ Notificazione ai sensi della legge 53 [Notifica_ID_{id_ricevuta}][1].eml; parte 1.3]\n"
        f"[Allegato: CONSEGNA_ Notificazione ai sensi della legge 53 [Notifica_ID_{id_ricevuta}][2].eml; parte 1.4]\n"
        f"[Allegato: CONSEGNA_ Notificazione ai sensi della legge 53 [Notifica_ID_{id_ricevuta}][3].eml; parte 1.5]"))
    notifica = Atto("PEC", "originale.eml", "messaggio_pec", "", testo=(
        "Oggetto: Notificazione ai sensi della legge 53 [Notifica_ID:RinnovoA]"))
    contesto = SimpleNamespace(rg="120/2026", oggi=date(2026, 11, 16), depositi=depositi_eseguiti([chiara, inviata], []))
    busta = _busta_della_rinnovazione(contesto, notifica, date(2026, 4, 12), numero_consegne)
    assert bool(busta) is collegata
    monitor = {"status": "prova_raccolta", "proofDeposited": False, "depositHref": "/prepara",
               "steps": [{"id": "prova"}]}
    lettura = {"ragionamento": {"conclusioni": [{
        "codice": "notifica_ordinata", "stato": "fatto", "prova_o_motivo": "Rinnovazione documentata.",
        "prova_notifica": {"invio_id": notifica.id, "deposito_inviato": busta},
    }]}}
    allinea_relata_al_riscontro({"notificationRelata": monitor}, lettura, "F1")
    assert monitor["proofDeposited"] is False
    if collegata:
        assert monitor["depositHref"] == "/fascicoli/F1/documenti/CHIARA/visualizza"
        assert monitor["depositLabel"] == "Apri busta già inviata"
        assert "12/04/2026" in monitor["steps"][0]["detail"]
    else:
        assert monitor["depositHref"] == "/prepara"
        assert "depositLabel" not in monitor


@pytest.mark.parametrize("altro_obbligo", [False, True])
def test_ricevute_storiche_restano_consultabili_senza_riproporre_il_deposito(monkeypatch, altro_obbligo):
    from web.services import obblighi_notifica_sintesi
    from web.services.pannelli_pronti_ricomposizione import allinea_relata_al_riscontro

    obblighi = [
        {"regola": "sentenza_notifica_breve", "stato": "da_verificare", "documenti": ["S1"]},
        {"regola": "ricorso_lavoro", "stato": "notificato", "documenti": ["D1"]},
    ]
    if altro_obbligo:
        obblighi.append({"regola": "sentenza_notifica_breve", "stato": "da_verificare", "documenti": ["S2"]})
    monkeypatch.setattr(obblighi_notifica_sintesi, "leggi", lambda _fid: {"obblighi": obblighi})
    monitor = {"status": "prova_raccolta", "depositHref": "/prepara", "proofDeposited": False,
               "documents": [{"id": "RDAC"}], "steps": [
                   {"id": "prova", "status": "da_completare"},
                   {"id": "firma", "status": "superato", "detail": "Notifica già eseguita."},
               ]}
    lettura = {"fase": {"codice": "chiusa"}, "ragionamento": {"versione": "1", "impronta": "fonti-correnti",
        "conclusioni": [{"codice": "notifica_sentenza", "stato": "non_dovuto", "letto": {"documento_id": "S1"}}]}}
    allinea_relata_al_riscontro({"notificationRelata": monitor}, lettura, "F1")
    assert monitor["documents"] == [{"id": "RDAC"}]
    assert monitor["proofDeposited"] is False
    if altro_obbligo:
        assert monitor["steps"][0]["status"] == "da_completare"
        assert monitor["steps"][1]["status"] == "superato"
        assert monitor["depositHref"] == "/prepara"
    else:
        assert monitor["steps"][0]["status"] == "monitorato"
        assert monitor["steps"][1]["status"] == "monitorato"
        assert "archiviate" in monitor["steps"][1]["detail"]
        assert monitor["depositHref"] == ""
        assert monitor["primaryHref"] == "/fascicoli/F1#lettura-fascicolo"


def test_solo_le_proposte_con_la_stessa_ordinanza_e_scadenza_si_chiudono(monkeypatch):
    import web.helpers
    from pct.scadenziario import StatoTermine
    from web.services.consegna_presidi_runtime import riconcilia_notifiche_ordinate

    def voce(oid, documento, data):
        return SimpleNamespace(id=oid, stato=StatoTermine.BOZZA, titolo="Rinnovazione della notifica",
                               data_scadenza=data, id_appuntamento="",
                               note=f"PEC_DOCUMENT_PRESIDIO:docpresidio:F1:{documento}:termine:{data}")

    scadenze = [voce("OK", "ORD1", "2026-06-01"), voce("ALTRO", "ORD2", "2026-06-01"),
                 voce("DATA_DIVERSA", "ORD1", "2026-06-02")]
    concluse = []

    def completa(oid, *, note):
        next(x for x in scadenze if x.id == oid).stato = StatoTermine.COMPLETATO
        concluse.append((oid, note))

    monkeypatch.setattr(web.helpers, "get_scadenziario", lambda: SimpleNamespace(tutte=lambda **kwargs: scadenze, completa=completa))
    monkeypatch.setattr(web.helpers, "get_agenda", lambda: SimpleNamespace())
    lettura = {"ragionamento": {"conclusioni": [{
        "codice": "notifica_ordinata", "stato": "fatto", "letto": {"documento_id": "ORD1"},
        "termine": {"scadenza_iso": "2026-06-01"}, "prova_o_motivo": "Rinnovazione documentata.",
        "prova_notifica": {"invio_id": "PEC1", "accettazione_id": "RAC1", "consegne_ids": ["RDAC1"]},
    }]}}
    fascicolo = SimpleNamespace(id="F1")
    assert riconcilia_notifiche_ordinate(fascicolo, lettura) == ["OK"]
    assert "RDAC1" in concluse[0][1]
    assert riconcilia_notifiche_ordinate(fascicolo, lettura) == []
    assert all(s.stato == StatoTermine.BOZZA for s in scadenze[1:])


def test_relata_storica_ante_cutoff_non_apre_firma_residua() -> None:
    fascicolo = SimpleNamespace(
        id="FLEGACY",
        documenti=[
            _doc(
                "7",
                "Ricorso Verdi (originale notificato).pdf",
                tipo="RICORSO",
                note="data notifica: 18/07/2026 ore: 10:20 Notifica ID: LEGACY",
                percorso="FLEGACY/ricorso-originale-notificato.pdf",
            ),
            _doc(
                "8",
                "Relata di notifica.pdf",
                tipo="NOTIFICA",
                note="data notifica: 18/07/2026 ore: 10:20 Notifica ID: LEGACY",
                percorso="FLEGACY/relata.pdf",
            ),
        ],
    )

    payload = _notification_relata(fascicolo, [])

    assert payload["status"] == "storico_gestito"
    assert payload["legacyAssumedHandled"] is True
    assert payload["historicalCutoff"] == "19/07/2026"
    assert all(step["status"] != "da_firmare" for step in payload["steps"])
    assert "nessuna nuova notifica da preparare" in payload["systemNotification"]

    presidio = build_fascicolo_operational_presidio(
        fascicolo=fascicolo,
        document_presidio={},
        notification_relata=payload,
        payment_summary={},
        deposits=[],
        duplicate_group=None,
        sentenze_economiche=None,
    )
    relata_sector = next(sector for sector in presidio["sectors"] if sector["id"] == "relata")
    assert relata_sector["actions"] == []


def test_provvedimento_successivo_al_cutoff_resta_da_notificare() -> None:
    fascicolo = SimpleNamespace(
        id="FNEW",
        documenti=[
            SimpleNamespace(
                id="9",
                nome="Provvedimento da notificare - decreto del 20/07/2026.pdf",
                nome_originale="Provvedimento da notificare - decreto del 20/07/2026.pdf",
                nome_portale="",
                tipo="PROVVEDIMENTO",
                tipo_atto_portale="Decreto",
                classificazione_portale="comunicazione_cancelleria",
                note="Provvedimento da notificare in data 20/07/2026.",
                tags=[],
                percorso="FNEW/provvedimento-20260720.pdf",
                hash_sha256="9" * 64,
                prova_notifica=False,
                data_documento="2026-07-20",
                data_deposito_portale="",
            )
        ],
    )

    payload = _notification_relata(fascicolo, [])

    assert payload["status"] == "da_preparare"
    assert payload["legacyAssumedHandled"] is False
    assert payload["strictNotificationSignals"] >= 1
    assert payload["primaryLabel"] == "Prepara relata"
    assert "id_fascicolo=FNEW" in payload["prepareHref"]
    assert "documenti=9" in payload["prepareHref"]
    assert "ingresso=presidio" in payload["prepareHref"]
    assert payload["primaryHref"] == payload["prepareHref"]


def test_le_ricevute_della_sentenza_non_usano_il_deposito_precedente_del_ricorso():
    acceptance = _doc("RAC", "ACCETTAZIONE: Notificazione ai sensi della legge n. 53 [Notifica_ID:APRILE]")
    delivery = _doc("RDAC", "CONSEGNA: Notificazione ai sensi della legge n. 53 [Notifica_ID:APRILE]")
    previous = _doc("OLD", "CONSEGNA: DEPOSITO TELEMATICO: Ricorso (originale notificato).pdf")
    acceptance.data_documento = delivery.data_documento = "2026-04-20"
    previous.data_documento = "2026-02-02"
    copia = _doc("COPY", "Sentenza (originale notificato).pdf", tipo="SENTENZA")
    copia.data_documento = "2026-05-31"
    case = SimpleNamespace(id="FTEST", documenti=[previous, acceptance, delivery, copia])
    result = _notification_relata(case, [])
    assert result["status"] == "prova_raccolta"
    assert result["proofComplete"] is True
    assert result["proofDeposited"] is False
    assert result["primaryHref"] == "/fascicoli/FTEST/documenti/RDAC/visualizza"
    passo = next(step for step in result["steps"] if step["id"] == "prova")
    assert passo["status"] == "da_completare"
    assert "collegamento alla notifica e il deposito" in passo["detail"]
