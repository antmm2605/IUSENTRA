"""Dal prestatore scelto nelle impostazioni al servizio di firma remota da chiamare.

Il prestatore (catalogo AgID in ``pct.firma_catalogo``) dice quali protocolli di firma
remota espone pubblicamente; lo studio indica il protocollo, l'indirizzo quando il
prestatore lo rilascia con il contratto (CSC), l'utente, il dominio (ARSS) e il tipo di
codice OTP. Password, PIN e OTP non sono mai nella configurazione: li digita
l'avvocato a ogni firma.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pct import firma_catalogo
from pct.firma_remota.base import (
    CredenzialiFirmaRemota,
    EsitoFirmaRemota,
    FirmaRemotaError,
    FirmaRemotaNonConfigurata,
    FirmaRemotaProvider,
    FirmatarioRemoto,
)


@dataclass(frozen=True)
class ConfigurazioneRemota:
    prestatore: str
    protocollo: str
    endpoint: str
    utente: str = ""
    dominio: str = ""
    credenziale: str = ""
    tipo_otp: str = "app"

    @property
    def nome_prestatore(self) -> str:
        voce = firma_catalogo.prestatore(self.prestatore) or {}
        return str(voce.get("nome") or self.prestatore)


def configurazione_da_firma(cfg_firma: Any) -> ConfigurazioneRemota:
    """Legge ``ConfigFirma`` e completa l'indirizzo con quello pubblico del prestatore, se c'è."""
    prestatore = str(getattr(cfg_firma, "prestatore", "") or "").strip().lower()
    voce = firma_catalogo.prestatore(prestatore)
    if voce is None:
        raise FirmaRemotaNonConfigurata("Scegli il prestatore della firma remota in Impostazioni → Firma digitale.")
    protocolli = firma_catalogo.protocolli_remoti(prestatore)
    if not protocolli:
        nota = str((voce.get("remota") or {}).get("nota") or "")
        raise FirmaRemotaNonConfigurata(
            f"{voce['nome']} non pubblica un servizio di firma remota per i gestionali. {nota}".strip()
            + " Firma dall'app del prestatore e carica il file firmato con «Firma esterna»."
        )
    protocollo = str(getattr(cfg_firma, "remota_protocollo", "") or "").strip().lower() or protocolli[0]
    if protocollo not in protocolli:
        raise FirmaRemotaNonConfigurata(f"{voce['nome']} non usa il protocollo {protocollo.upper()}.")
    endpoint = str(getattr(cfg_firma, "remota_endpoint", "") or "").strip() \
        or firma_catalogo.endpoint_predefinito(prestatore, protocollo)
    if not endpoint:
        raise FirmaRemotaNonConfigurata(
            f"Manca l'indirizzo del servizio di firma remota di {voce['nome']}: lo rilascia il prestatore con il contratto."
        )
    return ConfigurazioneRemota(
        prestatore=prestatore, protocollo=protocollo, endpoint=endpoint,
        utente=str(getattr(cfg_firma, "remota_utente", "") or "").strip(),
        dominio=str(getattr(cfg_firma, "remota_dominio", "") or "").strip(),
        credenziale=str(getattr(cfg_firma, "remota_credenziale", "") or "").strip(),
        tipo_otp=str(getattr(cfg_firma, "remota_tipo_otp", "") or "app").strip().lower() or "app",
    )


def firmatario(configurazione: ConfigurazioneRemota, *, sessione=None) -> FirmatarioRemoto:
    if configurazione.protocollo == "arss":
        from pct.firma_remota.arss import CERT_ID_PREDEFINITO, ArssFirmatario

        return ArssFirmatario(configurazione.endpoint, cert_id=configurazione.credenziale or CERT_ID_PREDEFINITO,
                              sessione=sessione)
    if configurazione.protocollo == "sws":
        from pct.firma_remota.sws import SwsFirmatario

        return SwsFirmatario(configurazione.endpoint, sessione=sessione)
    if configurazione.protocollo == "csc":
        from pct.firma_remota.csc import CscFirmatario

        return CscFirmatario(configurazione.endpoint, credential_id=configurazione.credenziale, sessione=sessione)
    raise FirmaRemotaError(f"Protocollo di firma remota sconosciuto: {configurazione.protocollo!r}.")


class ProviderRemoto(FirmaRemotaProvider):
    """Firma CAdES e PAdES con un servizio di firma remota reale."""

    def __init__(self, servizio: FirmatarioRemoto, *, nome: str):
        self.servizio = servizio
        self.nome = nome

    def disponibile(self) -> bool:
        return True

    def firma_cades(self, documento: bytes, credenziali: CredenzialiFirmaRemota, *, detached: bool = True,
                    **visibile: str) -> EsitoFirmaRemota:
        from pct.firma_remota.buste import firma_cades

        try:
            busta, certificato = firma_cades(self.servizio, credenziali, documento, **visibile)
        finally:
            self.servizio.chiudi(credenziali)
        return EsitoFirmaRemota(contenuto=busta, formato="cades", provider=self.nome,
                                dettagli={"intestatario": certificato.intestatario, "emittente": certificato.emittente,
                                          "scadenza": certificato.x509().not_valid_after_utc.date().isoformat()})

    def firma_pades(self, pdf: bytes, credenziali: CredenzialiFirmaRemota, **visibile: str) -> EsitoFirmaRemota:
        from pct.firma_remota.buste import firma_pades

        try:
            firmato, certificato = firma_pades(self.servizio, credenziali, pdf, **visibile)
        finally:
            self.servizio.chiudi(credenziali)
        return EsitoFirmaRemota(contenuto=firmato, formato="pades", provider=self.nome,
                                dettagli={"intestatario": certificato.intestatario, "emittente": certificato.emittente,
                                          "scadenza": certificato.x509().not_valid_after_utc.date().isoformat()})


def provider_da_firma(cfg_firma: Any, *, sessione=None) -> tuple[ProviderRemoto, ConfigurazioneRemota]:
    configurazione = configurazione_da_firma(cfg_firma)
    return ProviderRemoto(firmatario(configurazione, sessione=sessione), nome=configurazione.prestatore), configurazione


__all__ = ["ConfigurazioneRemota", "ProviderRemoto", "configurazione_da_firma", "firmatario", "provider_da_firma"]
