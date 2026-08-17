"""Contratti della pagina React Controllo Studio."""

from pathlib import Path

from flask import Flask, g

import web.blueprints.api_v1_react as dashboard_api


REPO_ROOT = Path(__file__).resolve().parents[1]


class _PublicPage:
    def __init__(self, items):
        self.items = items

    def to_public_dict(self):
        return {"items": self.items}


class _PresidioRepository:
    def __init__(self, items):
        self.items = items

    def list_presidia(self, *, limit):
        assert limit >= 15
        return _PublicPage(self.items)


def test_controllo_studio_espone_presidio_notifica_reale(monkeypatch):
    monkeypatch.setattr(
        dashboard_api,
        "legal_notification_presidia_rollout",
        lambda **_kwargs: {"enabled": True},
    )
    monkeypatch.setattr(
        dashboard_api,
        "build_notification_presidio_repository",
        lambda: _PresidioRepository(
            [
                {
                    "id": "presidio-1",
                    "status": "READY_TO_SEND",
                    "notificationCase": "legal_notification_review",
                    "priority": "P1",
                    "recipientProgress": {"total": 2, "delivered": 0, "failed": 0},
                    "updatedAt": "2026-08-17T10:15:00+02:00",
                },
                {
                    "id": "presidio-chiuso",
                    "status": "CLOSED",
                    "notificationCase": "legal_notification_review",
                },
            ]
        ),
    )

    rows = dashboard_api._notification_presidia_rows(limit=5)

    assert len(rows) == 1
    assert rows[0]["title"] == "Notifica legale da verificare"
    assert rows[0]["badge"] == "Pronta per invio locale"
    assert "Esegui invio dal PC locale" in rows[0]["subtitle"]
    assert rows[0]["href"].endswith("section=presidi&coda=da-lavorare&presidio=presidio-1")


def test_controllo_studio_espone_parcella_e_azione_incasso(monkeypatch):
    monkeypatch.setattr(
        dashboard_api,
        "build_react_incassi_pagamenti_payload",
        lambda **_kwargs: {
            "records": [
                {
                    "id": "pagamento-1",
                    "invoiceId": "parcella-1",
                    "invoiceNumber": "12/2026",
                    "customerName": "Cliente Demo",
                    "amountDisplay": "€ 1.250,00",
                    "state": "ATTESO",
                    "stateLabel": "Da incassare",
                    "dueAt": "31/08/2026",
                }
            ]
        },
    )
    app = Flask(__name__)
    with app.app_context():
        g.utente_corrente = object()
        rows = dashboard_api._billing_work_rows(limit=5)

    assert len(rows) == 1
    assert rows[0]["title"] == "Parcella 12/2026"
    assert rows[0]["subtitle"] == "Cliente Demo · € 1.250,00"
    assert rows[0]["time"] == "31/08/2026"
    assert rows[0]["href"] == "/incassi-pagamenti?id_parcella=parcella-1#registra-incasso"


def test_payload_errore_mantiene_le_nuove_sezioni_vuote():
    payload = dashboard_api._dashboard_error_payload()

    assert payload["notification_presidia"] == []
    assert payload["billing_work"] == []


def test_interfaccia_controllo_studio_collega_tutte_le_azioni_reali():
    source = (REPO_ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")

    for expected in (
        "Controllo Studio",
        "Notifiche da presidiare",
        "Parcelle e incassi",
        '/notifiche-legali?section=operazioni',
        '/notifiche-legali?section=presidi',
        '/fatturazione/nuova',
        '/incassi-pagamenti#registra-incasso',
        "Bonifico o altro pagamento",
    ):
        assert expected in source
