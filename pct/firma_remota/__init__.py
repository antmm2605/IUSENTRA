"""Firma remota qualificata: prestatori, protocolli (ARSS, SWS, CSC) e buste CAdES/PAdES.

- ``base``: credenziali mai salvate, errori, verifica della firma ricevuta;
- ``arss``, ``sws``, ``csc``: i servizi dei prestatori (Aruba e Actalis, Namirial, standard CSC);
- ``buste``: CAdES-BES e PAdES costruite in IUSENTRA, al prestatore va solo l'impronta;
- ``prestatori``: dalla configurazione dello studio al servizio da chiamare.
"""

from __future__ import annotations

from typing import Any

from pct.firma_remota.base import (
    FONTE_NORMATIVA,
    CertificatoRemoto,
    CredenzialiFirmaRemota,
    EsitoFirmaRemota,
    FirmaRemotaError,
    FirmaRemotaNonConfigurata,
    FirmaRemotaProvider,
    FirmatarioRemoto,
    verifica_firma_rsa,
)
from pct.firma_remota.prestatori import ProviderRemoto

PROVIDER_ARUBA = "aruba"
PROVIDER_MOCK = "mock"
PROVIDER_VALIDI = (PROVIDER_ARUBA, PROVIDER_MOCK)


class ArubaRemoteSignProvider(ProviderRemoto):
    """Aruba ARSS (ArubaSignService) configurato da variabili d'ambiente o dizionario.

    Senza l'indirizzo del servizio non firma nulla (fail-closed).
    """

    def __init__(self, *, endpoint: str = "", app_credentials: dict[str, str] | None = None, sessione=None):
        self.endpoint = str(endpoint or "").strip()
        self._app_credentials = dict(app_credentials or {})
        servizio = None
        if self.endpoint:
            from pct.firma_remota.arss import ArssFirmatario

            servizio = ArssFirmatario(self.endpoint, sessione=sessione)
        super().__init__(servizio, nome=PROVIDER_ARUBA)  # type: ignore[arg-type]

    def disponibile(self) -> bool:
        return bool(self.endpoint)

    def _richiede_configurazione(self) -> None:
        raise FirmaRemotaNonConfigurata(
            "Firma remota Aruba non attiva: manca l'indirizzo del servizio ARSS (ARUBA_ARSS_URL). "
            "Scegli Aruba in Impostazioni → Firma digitale → Firma remota: l'indirizzo pubblico è già noto."
        )

    def firma_cades(self, documento, credenziali, *, detached: bool = True, **visibile) -> EsitoFirmaRemota:
        if not self.disponibile():
            self._richiede_configurazione()
        return super().firma_cades(documento, credenziali, detached=detached, **visibile)

    def firma_pades(self, pdf, credenziali, **visibile) -> EsitoFirmaRemota:
        if not self.disponibile():
            self._richiede_configurazione()
        return super().firma_pades(pdf, credenziali, **visibile)


class MockFirmaRemotaProvider(FirmaRemotaProvider):
    """Provider finto per collaudare l'interfaccia. Mai valido legalmente."""

    nome = PROVIDER_MOCK

    def disponibile(self) -> bool:
        return True

    def _busta(self, contenuto: bytes, formato: str, credenziali: CredenzialiFirmaRemota) -> EsitoFirmaRemota:
        if not credenziali.otp:
            raise FirmaRemotaError("OTP mancante: la firma remota richiede il codice usa-e-getta del titolare.")
        return EsitoFirmaRemota(
            contenuto=b"IUSENTRA-MOCK-FIRMA-REMOTA-NON-VALIDA\n" + contenuto,
            formato=formato,
            provider=self.nome,
            valida_legalmente=False,
            dettagli={"avviso": "Firma di collaudo: NESSUN valore legale."},
        )

    def firma_cades(self, documento: bytes, credenziali: CredenzialiFirmaRemota, *, detached: bool = True) -> EsitoFirmaRemota:
        return self._busta(documento, "cades", credenziali)

    def firma_pades(self, pdf: bytes, credenziali: CredenzialiFirmaRemota) -> EsitoFirmaRemota:
        return self._busta(pdf, "pades", credenziali)


def get_firma_remota_provider(config: dict[str, Any] | None = None) -> FirmaRemotaProvider | None:
    """Provider da variabili d'ambiente o dizionario (installazioni senza impostazioni React).

    - ``PCT_FIRMA_REMOTA_PROVIDER``: "aruba" | "mock" | "" (default: nessuno)
    - ``ARUBA_ARSS_URL``: indirizzo del servizio ARSS
    Il provider di prova non è mai selezionato implicitamente.
    """
    import os

    cfg = dict(config or {})
    scelto = str(cfg.get("PCT_FIRMA_REMOTA_PROVIDER") or os.getenv("PCT_FIRMA_REMOTA_PROVIDER") or "").strip().lower()
    if not scelto:
        return None
    if scelto not in PROVIDER_VALIDI:
        raise FirmaRemotaError(f"Provider firma remota sconosciuto: {scelto!r} (ammessi: {', '.join(PROVIDER_VALIDI)}).")
    if scelto == PROVIDER_MOCK:
        return MockFirmaRemotaProvider()
    return ArubaRemoteSignProvider(endpoint=str(cfg.get("ARUBA_ARSS_URL") or os.getenv("ARUBA_ARSS_URL") or "").strip())


__all__ = [
    "FONTE_NORMATIVA", "PROVIDER_ARUBA", "PROVIDER_MOCK", "PROVIDER_VALIDI", "ArubaRemoteSignProvider",
    "CertificatoRemoto", "CredenzialiFirmaRemota", "EsitoFirmaRemota", "FirmaRemotaError", "FirmaRemotaNonConfigurata",
    "FirmaRemotaProvider", "FirmatarioRemoto", "MockFirmaRemotaProvider", "ProviderRemoto", "get_firma_remota_provider",
    "verifica_firma_rsa",
]
