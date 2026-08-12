"""Ricerca RG nel registro per agganciare il numero di ruolo (Fase 4 sync Polisweb)."""

from __future__ import annotations

from types import SimpleNamespace

from web.services import polisweb_fascicolo_sync as sync_module


class _FakeFascicoli:
    def __init__(self, fascicolo):
        self._fascicolo = fascicolo
        self.updated = {}

    def get(self, _id):
        return self._fascicolo

    def aggiorna(self, _id, **campi):
        self.updated.update(campi)
        return self._fascicolo


def _fascicolo(**overrides):
    base = dict(id="F1", codice_ufficio_portale="0580010", tribunale="MILANO", nome_cliente="Rossi Mario", cf_cliente="RSSMRA80A01F205X", tipo_registro="")
    base.update(overrides)
    return SimpleNamespace(**base)


def test_ricerca_richiede_ufficio_e_parte():
    manager = _FakeFascicoli(_fascicolo(codice_ufficio_portale="", tribunale=""))
    esito = sync_module.cerca_rg_nel_registro("F1", get_fascicoli=lambda: manager, get_clienti=lambda: None, auth_mode="reale")
    assert esito["ok"] is False
    assert "ufficio" in esito["message"]


def test_ricerca_senza_certificato_guida_local_signer():
    manager = _FakeFascicoli(_fascicolo())
    esito = sync_module.cerca_rg_nel_registro("F1", get_fascicoli=lambda: manager, get_clienti=lambda: None, auth_mode="pkcs11")
    assert esito["ok"] is False
    assert esito["requires_local_signer"] is True


def test_ricerca_restituisce_candidati(monkeypatch):
    manager = _FakeFascicoli(_fascicolo())

    class _FakeClient:
        def ricerca_fascicoli(self, ufficio, **kwargs):
            assert ufficio == "0580010"
            assert kwargs["nome_parte"] == "Rossi Mario"
            return [
                SimpleNamespace(numero_rg="1234", anno_rg=2026, nome_ufficio="Tribunale di Milano", oggetto="Contratti", parti="Rossi / Bianchi"),
                SimpleNamespace(numero_rg="", anno_rg=2026),  # senza RG → escluso
            ]

    monkeypatch.setattr(sync_module, "crea_client", lambda demo=False: _FakeClient())
    esito = sync_module.cerca_rg_nel_registro("F1", get_fascicoli=lambda: manager, get_clienti=lambda: None, auth_mode="reale")
    assert esito["ok"] is True
    assert len(esito["candidati"]) == 1
    assert esito["candidati"][0]["numeroRg"] == "1234"
    assert esito["candidati"][0]["attachHref"] == "/fascicoli/F1/aggancia-rg"
