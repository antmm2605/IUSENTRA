from __future__ import annotations

from types import SimpleNamespace

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
