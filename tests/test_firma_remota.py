"""Astrazione firma remota qualificata: registry fail-closed, credenziali mai
esposte, adapter Aruba predisposto, mock riconoscibile e mai valido legalmente.
"""

from __future__ import annotations

import pytest

from pct.firma_remota import (
    ArubaRemoteSignProvider,
    CredenzialiFirmaRemota,
    FirmaRemotaError,
    FirmaRemotaNonConfigurata,
    MockFirmaRemotaProvider,
    get_firma_remota_provider,
)


# --- Registry fail-closed ---------------------------------------------------------


def test_default_nessun_provider(monkeypatch):
    monkeypatch.delenv("PCT_FIRMA_REMOTA_PROVIDER", raising=False)
    assert get_firma_remota_provider({}) is None


def test_provider_sconosciuto_rifiutato():
    with pytest.raises(FirmaRemotaError, match="sconosciuto"):
        get_firma_remota_provider({"PCT_FIRMA_REMOTA_PROVIDER": "acme"})


def test_mock_mai_selezionato_implicitamente(monkeypatch):
    monkeypatch.delenv("PCT_FIRMA_REMOTA_PROVIDER", raising=False)
    assert get_firma_remota_provider(None) is None
    provider = get_firma_remota_provider({"PCT_FIRMA_REMOTA_PROVIDER": "mock"})
    assert isinstance(provider, MockFirmaRemotaProvider)


def test_aruba_da_config_completa():
    provider = get_firma_remota_provider(
        {
            "PCT_FIRMA_REMOTA_PROVIDER": "aruba",
            "ARUBA_ARSS_URL": "https://arss.example/service",
            "ARUBA_ARSS_APP_ID": "app-1",
            "ARUBA_ARSS_APP_SECRET": "s3cret",
        }
    )
    assert isinstance(provider, ArubaRemoteSignProvider)
    assert provider.disponibile() is True


# --- Credenziali mai esposte ------------------------------------------------------


def test_credenziali_mascherate_in_repr_e_str():
    credenziali = CredenzialiFirmaRemota(username="avv.rossi", password="Segreta1!", otp="123456")
    for resa in (repr(credenziali), str(credenziali)):
        assert "Segreta1!" not in resa
        assert "123456" not in resa
        assert "avv.rossi" in resa


def test_credenziali_richiedono_username():
    with pytest.raises(ValueError, match="username"):
        CredenzialiFirmaRemota(username="  ")


# --- Adapter Aruba fail-closed ----------------------------------------------------


def test_aruba_non_configurato_spiega_come_attivare():
    provider = ArubaRemoteSignProvider()
    assert provider.disponibile() is False
    credenziali = CredenzialiFirmaRemota(username="avv.rossi", otp="123456")
    with pytest.raises(FirmaRemotaNonConfigurata, match="ARUBA_ARSS_URL"):
        provider.firma_cades(b"%PDF-1.4", credenziali)
    with pytest.raises(FirmaRemotaNonConfigurata):
        provider.firma_pades(b"%PDF-1.4", credenziali)


def test_aruba_configurato_ma_adapter_da_completare():
    # Anche con endpoint e credenziali app, l'adapter non improvvisa payload:
    # va completato dalle specifiche ufficiali ARSS (principio fonti certe).
    provider = ArubaRemoteSignProvider(
        endpoint="https://arss.example/service",
        app_credentials={"app_id": "a", "app_secret": "b"},
    )
    with pytest.raises(FirmaRemotaNonConfigurata, match="specifiche ufficiali"):
        provider.firma_cades(b"doc", CredenzialiFirmaRemota(username="u", otp="1"))


# --- Mock riconoscibile -----------------------------------------------------------


def test_mock_firma_riconoscibile_e_non_valida():
    provider = MockFirmaRemotaProvider()
    esito = provider.firma_cades(b"contenuto", CredenzialiFirmaRemota(username="u", otp="123456"))
    assert esito.valida_legalmente is False
    assert esito.contenuto.startswith(b"IUSENTRA-MOCK-FIRMA-REMOTA-NON-VALIDA")
    assert esito.provider == "mock"
    assert "legale" in esito.dettagli["avviso"].lower()


def test_mock_richiede_otp():
    provider = MockFirmaRemotaProvider()
    with pytest.raises(FirmaRemotaError, match="OTP"):
        provider.firma_cades(b"doc", CredenzialiFirmaRemota(username="u"))
