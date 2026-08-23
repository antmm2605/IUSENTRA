from __future__ import annotations

from pct.telematico_truth_registry import (
    build_capability_truth_registry,
    build_telematico_sentinel,
)


def test_truth_registry_separa_prontezza_piattaforma_e_prerequisiti_studio() -> None:
    registry = build_capability_truth_registry(
        [
            {
                "capability_id": "pct_deposito_civile",
                "label": "Deposito civile via PEC + busta .enc",
                "channel": "PEC + busta .enc",
                "operational_text": "Deposito civile",
            },
            {
                "capability_id": "pst_consultazione_fascicoli",
                "label": "Consultazione fascicoli PST",
                "channel": "PolisWeb / PST",
                "operational_text": "Consultazione",
            },
        ],
        [{"source_id": "pst_servizi_web", "status": "ok", "last_check": "2026-08-23T10:00:00+02:00"}],
    )

    deposito = next(item for item in registry["entries"] if item["id"] == "pct_deposito_civile")
    consultazione = next(item for item in registry["entries"] if item["id"] == "pst_consultazione_fascicoli")

    assert deposito["platformStatus"] == "condizionata"
    assert "PEC locale" in deposito["studioRequirement"]
    assert "non viene dichiarato valido" in deposito["limit"]
    assert consultazione["platformStatus"] == "pronta"
    assert registry["summary"]["conditional"] == 1
    assert registry["summary"]["ready"] == 1


def test_sentinella_collega_variazione_ufficiale_alle_funzioni_coinvolte() -> None:
    registry = build_capability_truth_registry(
        [
            {
                "capability_id": "xsd_monitoraggio",
                "label": "Monitoraggio canali XSD",
                "channel": "PST / XSD",
            },
            {
                "capability_id": "pct_deposito_civile",
                "label": "Deposito civile via PEC + busta .enc",
                "channel": "PEC + busta .enc",
            },
        ],
        [],
    )

    sentinel = build_telematico_sentinel(
        registry,
        [
            {
                "source_id": "pst_xsd_sici",
                "status": "ok",
                "changed": True,
                "last_check": "2026-08-23T10:00:00+02:00",
            }
        ],
        [{"source_id": "pst_xsd_sici", "nome": "Canale SICI", "official_url": "https://pst.giustizia.it"}],
    )

    assert sentinel["status"] == "attenzione"
    assert sentinel["summary"]["changes"] == 1
    alert = sentinel["alerts"][0]
    assert alert["title"] == "Variazione ufficiale rilevata"
    assert "Deposito civile via PEC + busta .enc" in alert["affected"]
    assert alert["href"] == "https://pst.giustizia.it"


def test_sentinella_non_dichiara_sana_una_fonte_in_errore() -> None:
    registry = build_capability_truth_registry(
        [{"capability_id": "wsdl_monitoraggio", "label": "Catalogo WSDL", "channel": "PST / WSDL"}],
        [],
    )
    sentinel = build_telematico_sentinel(
        registry,
        [{"source_id": "pst_servizi_web", "status": "errore", "status_code": 503, "last_check": "2026-08-23T10:00:00+02:00"}],
        [{"source_id": "pst_servizi_web", "nome": "Servizi web PST"}],
    )

    assert sentinel["summary"]["blocked"] == 1
    assert sentinel["alerts"][0]["tone"] == "danger"

def test_sentinella_non_dichiara_presidiata_una_fonte_non_acquisita() -> None:
    registry = build_capability_truth_registry(
        [{"capability_id": "pst_consultazione_fascicoli", "label": "Consultazione PST"}],
        [],
        [{"source_id": "pst_giustizia", "nome": "PST Giustizia", "official_url": "https://pst.giustizia.it/PST/"}],
    )
    sentinel = build_telematico_sentinel(registry, [], [{"source_id": "pst_giustizia", "nome": "PST Giustizia"}])

    assert sentinel["status"] == "da_presidiare"
    assert sentinel["summary"]["attention"] >= 1
