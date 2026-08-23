from __future__ import annotations

from datetime import date, timedelta

from pct.guardiano_scadenze import build_guardiano_scadenze_payload
from pct.scadenziario import GestioneScadenziario, TipoTermine


def test_guardiano_evidenzia_termine_perentorio_non_assegnato_e_imminente(tmp_path) -> None:
    gestione = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    item = gestione.nuova(
        "Deposito memoria",
        TipoTermine.DEPOSITO_MEMORIA,
        (date(2026, 8, 25)).isoformat(),
        perentorio=True,
    )

    payload = build_guardiano_scadenze_payload([item], today=date(2026, 8, 23))

    assert payload["summary"]["critical"] == 1
    risk = payload["items"][0]
    assert risk["id"] == item.id
    assert risk["band"] == "critico"
    assert "Nessun responsabile assegnato" in [reason["label"] for reason in risk["reasons"]]
    assert risk["href"].endswith(f"/{item.id}/modifica")


def test_guardiano_porta_alla_fonte_quando_la_scadenza_derivata_non_e_confermata(tmp_path) -> None:
    gestione = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    item = gestione.nuova(
        "Termine da provvedimento",
        TipoTermine.ADEMPIMENTO,
        (date(2026, 9, 10)).isoformat(),
        id_utente_responsabile="avv-1",
        id_fascicolo="FASC-1",
        source_event_type="cancelleria_comunicazione",
        source_confidence=0.55,
    )

    payload = build_guardiano_scadenze_payload([item], today=date(2026, 8, 23))

    risk = payload["items"][0]
    codes = {reason["code"] for reason in risk["reasons"]}
    assert {"fonte_da_confermare", "prova_fonte_incompleta"}.issubset(codes)
    assert risk["href"].endswith(f"/{item.id}")
    assert payload["summary"]["sourceReview"] == 1


def test_guardiano_non_trasforma_un_presidio_notifica_in_un_termine_scaduto(tmp_path) -> None:
    gestione = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    item = gestione.nuova(
        "Preparare relata",
        TipoTermine.NOTIFICA,
        (date(2026, 8, 20)).isoformat(),
        source_event_type="legal_notification_presidio",
    )

    payload = build_guardiano_scadenze_payload([item], today=date(2026, 8, 23))

    assert payload["items"] == []
    assert payload["summary"]["total"] == 0
