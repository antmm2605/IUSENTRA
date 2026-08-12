"""Sincronizzazione on-demand di un fascicolo dai registri (Fase 0 sync Polisweb).

Verifica il doppio canale conforme: con certificato dello studio configurato
sul server (auth_mode="reale") il fascicolo viene interrogato e aggiornato con
watermark last_sync_at/sync_status; con solo smart card (auth_mode="pkcs11")
non si interroga in autonomia ma si guida verso il percorso assistito; RG
mancante blocca con messaggio operativo. Mai il ramo demo su superfici reali.
"""

from __future__ import annotations

from types import SimpleNamespace

import pct.polisWeb as polisweb_module
from web.services import polisweb_fascicolo_sync as sync_module


class _FakeFascicoliManager:
    def __init__(self, fascicolo):
        self._fascicolo = fascicolo
        self.updated = {}

    def get(self, _id):
        return self._fascicolo

    def aggiorna(self, _id, **campi):
        for key, value in campi.items():
            setattr(self._fascicolo, key, value)
        self.updated.update(campi)
        return self._fascicolo


def _fascicolo(**overrides):
    base = dict(
        id="F1",
        numero_rg="1234",
        anno_rg=2026,
        codice_ufficio_portale="",
        tribunale="MILANO",
        tipo_registro="",
        registro_portale="",
        servizio_pst="",
        ruolo_polisweb="AVV",
        last_sync_at="",
        sync_status="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_rg_mancante_blocca_con_messaggio(monkeypatch):
    fascicolo = _fascicolo(numero_rg="", tribunale="")
    manager = _FakeFascicoliManager(fascicolo)

    esito = sync_module.sincronizza_fascicolo_da_registro(
        "F1",
        get_fascicoli=lambda: manager,
        get_clienti=lambda: None,
        auth_mode="reale",
    )

    assert esito["ok"] is False
    assert esito["rg_mancante"] is True
    assert "numero di ruolo" in esito["message"]


def test_senza_certificato_server_guida_al_local_signer():
    fascicolo = _fascicolo()
    manager = _FakeFascicoliManager(fascicolo)

    esito = sync_module.sincronizza_fascicolo_da_registro(
        "F1",
        get_fascicoli=lambda: manager,
        get_clienti=lambda: None,
        auth_mode="pkcs11",
    )

    assert esito["ok"] is False
    assert esito["requires_local_signer"] is True
    assert "smart card" in esito["message"]


def test_canale_reale_interroga_e_scrive_watermark(monkeypatch):
    fascicolo = _fascicolo()
    manager = _FakeFascicoliManager(fascicolo)
    fascicolo_pw = object()

    class _FakeClient:
        def ricerca_fascicoli(self, ufficio, **kwargs):
            assert ufficio == "MILANO"
            assert kwargs["numero_rg"] == "1234"
            assert kwargs["anno_rg"] == 2026
            return [fascicolo_pw]

        def sincronizza_fascicolo_esistente(self, pw, locale, gestione_fascicoli, clienti, **kwargs):
            assert pw is fascicolo_pw
            # simula l'effetto reale: watermark aggiornato dal percorso polisWeb
            gestione_fascicoli.aggiorna(locale.id, last_sync_at="2026-08-12T22:40:00", sync_status="SINCRONIZZATO")
            return SimpleNamespace(
                successo=True,
                messaggio="Pratica RG 1234/2026 sincronizzata.",
                avvisi=[],
                depositi_importati=2,
                documenti_importati=5,
            )

    monkeypatch.setattr(sync_module, "crea_client", lambda demo=False: _FakeClient())

    esito = sync_module.sincronizza_fascicolo_da_registro(
        "F1",
        get_fascicoli=lambda: manager,
        get_clienti=lambda: None,
        auth_mode="reale",
    )

    assert esito["ok"] is True
    assert esito["depositi_importati"] == 2
    assert esito["last_sync_at"] == "2026-08-12T22:40:00"
    assert esito["sync_status"] == "SINCRONIZZATO"


def test_client_demo_mai_usato_su_superfici_reali(monkeypatch):
    fascicolo = _fascicolo()
    manager = _FakeFascicoliManager(fascicolo)
    monkeypatch.setattr(sync_module, "crea_client", lambda demo=False: polisweb_module.ClientPolisWebDemo())

    esito = sync_module.sincronizza_fascicolo_da_registro(
        "F1",
        get_fascicoli=lambda: manager,
        get_clienti=lambda: None,
        auth_mode="reale",
    )

    assert esito["ok"] is False
    assert "non configurato" in esito["message"]


def test_default_base_url_non_e_piu_legacy():
    # Fase 0: senza PCT_PST_BASE_URL il client punta al proxy moderno, non a wspa.
    assert polisweb_module._WSP_BASE == polisweb_module._PST_PROXY_ROOT
    assert "wspa.giustizia.it" not in polisweb_module._WSP_BASE
