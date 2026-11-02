"""Registro attività leggibile: esiti ricondotti, azioni e dettagli in italiano (verifica visiva ADM, 02/11/2026)."""

from __future__ import annotations

import json
from types import SimpleNamespace

from web.services import audit_leggibile as leggibile
from web.services.react_audit_bridge import build_react_audit_payload


def test_esiti_sinonimi_ricondotti_ai_tre_valori_del_registro():
    assert leggibile.esito_registro("SUCCESSO") == "OK"
    assert leggibile.esito_registro("ok") == "OK"
    assert leggibile.esito_registro("") == "OK"
    assert leggibile.esito_registro("DENIED") == "NEGATO"
    assert leggibile.esito_registro("failed") == "ERRORE"


def test_azioni_e_risorse_in_italiano_anche_senza_voce_dedicata():
    assert leggibile.etichetta_azione("fascicolo.giudice_da_fonte") == "Giudice del fascicolo letto dal provvedimento"
    assert leggibile.etichetta_azione("scadenziario.collaudo_metadati") == "Scadenziario · collaudo metadati"
    assert "_" not in leggibile.etichetta_azione("dominio_nuovo.azione_mai_vista")
    assert leggibile.etichetta_risorsa("config_studio") == "Impostazioni studio"
    assert "_" not in leggibile.etichetta_risorsa("risorsa_nuova")


def test_dettagli_json_lunghi_diventano_testo_senza_parentesi():
    dettagli = json.dumps({"giudice": "Mario Rossi", "data": "2026-11-02T10:30:00", "lungo": "x " * 800})
    testo = leggibile.testo_dettagli(dettagli)
    assert testo.startswith("Giudice: Mario Rossi · Data: 02/11/2026 10:30")
    assert "{" not in testo and '"' not in testo
    assert len(testo) <= 601


def test_conteggi_della_pagina_comprendono_esiti_sinonimi():
    eventi = [
        SimpleNamespace(to_dict=lambda: {"id": "1", "azione": "fascicolo.giudice_da_fonte", "esito": "SUCCESSO", "dettagli": "{}"}),
        SimpleNamespace(to_dict=lambda: {"id": "2", "azione": "policy_denied.tenant_isolation", "esito": "DENIED", "dettagli": ""}),
    ]

    class Utenti:
        def audit_log(self, **_kwargs):
            return eventi

        def tutti(self):
            return []

    payload = build_react_audit_payload(get_utenti=Utenti)
    metriche = {m["id"]: m["value"] for m in payload["metrics"]}
    assert metriche["ok"] == 1
    assert metriche["negati"] == 1
    azioni = [r["action"] for r in payload["records"]]
    assert "Accesso negato: dati di un altro studio" in azioni
