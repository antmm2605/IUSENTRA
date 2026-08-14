"""Firma remota qualificata: astrazione provider (QTSP) con adapter Aruba.

Base normativa: Reg. eIDAS 910/2014 (firma elettronica qualificata, anche con
dispositivo gestito da un QTSP per conto del firmatario, art. 29 e All. II);
CAD D.Lgs. 82/2005 art. 20 (efficacia della firma qualificata); D.M. 44/2011
art. 12 (firma degli atti nel deposito telematico). La firma remota produce le
stesse buste CAdES (.p7m) e PAdES della firma con smart card: cambia solo il
luogo della chiave (HSM del QTSP) e l'autenticazione (credenziale + OTP).

Regole di sicurezza NON derogabili di questo modulo:
- il gestionale NON memorizza mai password di firma ne' OTP: le credenziali
  viaggiano per singola richiesta e non vengono serializzate ne' loggate;
- fail-closed: nessun provider configurato → nessuna firma remota, con
  messaggio operativo (mai fallback silenzioso a un provider di prova);
- il provider mock e' riconoscibile e dichiara che l'output NON ha valore
  legale: esiste solo per collaudi dell'interfaccia.

Stato dell'adapter Aruba: predisposto per il servizio ARSS (Aruba Remote
Signing Service). L'attivazione richiede l'accordo commerciale con Aruba e le
credenziali applicative di test/produzione: finche' non sono configurate,
l'adapter risponde con ``FirmaRemotaNonConfigurata`` e istruzioni operative.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

FONTE_NORMATIVA = (
    "Reg. eIDAS 910/2014 art. 29 e All. II; CAD D.Lgs. 82/2005 art. 20; "
    "D.M. 44/2011 art. 12"
)

PROVIDER_ARUBA = "aruba"
PROVIDER_MOCK = "mock"
PROVIDER_VALIDI = (PROVIDER_ARUBA, PROVIDER_MOCK)


class FirmaRemotaError(RuntimeError):
    """Errore operativo della firma remota."""


class FirmaRemotaNonConfigurata(FirmaRemotaError):
    """Provider selezionato ma non attivabile: configurazione mancante."""


@dataclass
class CredenzialiFirmaRemota:
    """Credenziali per UNA richiesta di firma. Mai persistite ne' loggate.

    ``otp`` e' il codice usa-e-getta del titolare (app/SMS/token del QTSP);
    ``password`` e' la password di firma remota del titolare. Entrambi sono
    campi ``repr=False``: non compaiono in log, stacktrace o serializzazioni
    accidentali.
    """

    username: str
    password: str = field(repr=False, default="")
    otp: str = field(repr=False, default="")
    tipo_otp: str = "app"  # app | sms | token — dominio ARSS

    def __post_init__(self) -> None:
        if not str(self.username or "").strip():
            raise ValueError("La firma remota richiede lo username del titolare.")

    def __str__(self) -> str:  # difesa in profondita' contro log accidentali
        return f"CredenzialiFirmaRemota(username={self.username!r}, password=***, otp=***)"


@dataclass
class EsitoFirmaRemota:
    """Risultato di una firma remota."""

    contenuto: bytes
    formato: str  # "cades" | "pades"
    provider: str
    valida_legalmente: bool = True
    dettagli: dict[str, Any] = field(default_factory=dict)


class FirmaRemotaProvider(ABC):
    """Interfaccia dei provider di firma remota qualificata (QTSP)."""

    nome: str = ""

    @abstractmethod
    def disponibile(self) -> bool:
        """True se il provider e' configurato e attivabile."""

    @abstractmethod
    def firma_cades(
        self,
        documento: bytes,
        credenziali: CredenzialiFirmaRemota,
        *,
        detached: bool = True,
    ) -> EsitoFirmaRemota:
        """Busta CAdES (.p7m) firmata dall'HSM del QTSP."""

    @abstractmethod
    def firma_pades(
        self,
        pdf: bytes,
        credenziali: CredenzialiFirmaRemota,
    ) -> EsitoFirmaRemota:
        """PDF firmato PAdES dall'HSM del QTSP."""


class ArubaRemoteSignProvider(FirmaRemotaProvider):
    """Adapter per Aruba ARSS (Aruba Remote Signing Service).

    Predisposto e fail-closed: senza endpoint e credenziali applicative
    dell'accordo Aruba non esegue nulla. Quando l'accordo sara' attivo si
    configurano ``ARUBA_ARSS_URL`` (endpoint del servizio) e le credenziali
    applicative dello studio; le operazioni da mappare sul servizio sono la
    firma PKCS#7/CAdES e PAdES con autenticazione titolare (username +
    password di firma + OTP) secondo la documentazione ARSS consegnata con
    l'accordo — i payload NON vengono improvvisati qui (principio delle fonti
    certe: si implementano dalle specifiche ufficiali Aruba).
    """

    nome = PROVIDER_ARUBA

    def __init__(self, *, endpoint: str = "", app_credentials: dict[str, str] | None = None):
        self.endpoint = str(endpoint or "").strip()
        self._app_credentials = dict(app_credentials or {})

    def disponibile(self) -> bool:
        return bool(self.endpoint and self._app_credentials)

    def _richiede_configurazione(self) -> None:
        raise FirmaRemotaNonConfigurata(
            "Firma remota Aruba non ancora attiva: servono l'endpoint ARSS e le "
            "credenziali applicative dell'accordo con Aruba (variabili "
            "ARUBA_ARSS_URL e ARUBA_ARSS_APP_*). Una volta ricevute dal "
            "commerciale Aruba, configurarle in Impostazioni → Firma digitale; "
            "l'adapter va completato dalle specifiche ufficiali ARSS."
        )

    def firma_cades(
        self,
        documento: bytes,
        credenziali: CredenzialiFirmaRemota,
        *,
        detached: bool = True,
    ) -> EsitoFirmaRemota:
        if not self.disponibile():
            self._richiede_configurazione()
        # L'implementazione delle chiamate ARSS si scrive dalle specifiche
        # ufficiali Aruba consegnate con l'accordo (vedi docstring di classe).
        raise FirmaRemotaNonConfigurata(
            "Adapter ARSS predisposto ma non ancora implementato: completare "
            "dalle specifiche ufficiali Aruba prima dell'uso."
        )

    def firma_pades(
        self,
        pdf: bytes,
        credenziali: CredenzialiFirmaRemota,
    ) -> EsitoFirmaRemota:
        if not self.disponibile():
            self._richiede_configurazione()
        raise FirmaRemotaNonConfigurata(
            "Adapter ARSS predisposto ma non ancora implementato: completare "
            "dalle specifiche ufficiali Aruba prima dell'uso."
        )


class MockFirmaRemotaProvider(FirmaRemotaProvider):
    """Provider finto per collaudare l'interfaccia. MAI valido legalmente."""

    nome = PROVIDER_MOCK

    def disponibile(self) -> bool:
        return True

    def _busta(self, contenuto: bytes, formato: str, credenziali: CredenzialiFirmaRemota) -> EsitoFirmaRemota:
        if not credenziali.otp:
            raise FirmaRemotaError("OTP mancante: la firma remota richiede il codice usa-e-getta del titolare.")
        finta = b"IUSENTRA-MOCK-FIRMA-REMOTA-NON-VALIDA\n" + contenuto
        return EsitoFirmaRemota(
            contenuto=finta,
            formato=formato,
            provider=self.nome,
            valida_legalmente=False,
            dettagli={"avviso": "Firma di collaudo: NESSUN valore legale."},
        )

    def firma_cades(
        self,
        documento: bytes,
        credenziali: CredenzialiFirmaRemota,
        *,
        detached: bool = True,
    ) -> EsitoFirmaRemota:
        return self._busta(documento, "cades", credenziali)

    def firma_pades(self, pdf: bytes, credenziali: CredenzialiFirmaRemota) -> EsitoFirmaRemota:
        return self._busta(pdf, "pades", credenziali)


def get_firma_remota_provider(config: dict[str, Any] | None = None) -> FirmaRemotaProvider | None:
    """Risolve il provider dalla configurazione. Fail-closed: default nessuno.

    Config attese (da variabili d'ambiente o config studio):
    - ``PCT_FIRMA_REMOTA_PROVIDER``: "aruba" | "mock" | "" (default: disattiva)
    - ``ARUBA_ARSS_URL`` + ``ARUBA_ARSS_APP_ID``/``ARUBA_ARSS_APP_SECRET``
    Il mock non e' mai selezionabile implicitamente.
    """

    import os

    cfg = dict(config or {})
    scelto = str(cfg.get("PCT_FIRMA_REMOTA_PROVIDER") or os.getenv("PCT_FIRMA_REMOTA_PROVIDER") or "").strip().lower()
    if not scelto:
        return None
    if scelto not in PROVIDER_VALIDI:
        raise FirmaRemotaError(
            f"Provider firma remota sconosciuto: {scelto!r} (ammessi: {', '.join(PROVIDER_VALIDI)})."
        )
    if scelto == PROVIDER_MOCK:
        return MockFirmaRemotaProvider()
    app_credentials = {
        chiave: valore
        for chiave, valore in {
            "app_id": str(cfg.get("ARUBA_ARSS_APP_ID") or os.getenv("ARUBA_ARSS_APP_ID") or "").strip(),
            "app_secret": str(cfg.get("ARUBA_ARSS_APP_SECRET") or os.getenv("ARUBA_ARSS_APP_SECRET") or "").strip(),
        }.items()
        if valore
    }
    return ArubaRemoteSignProvider(
        endpoint=str(cfg.get("ARUBA_ARSS_URL") or os.getenv("ARUBA_ARSS_URL") or "").strip(),
        app_credentials=app_credentials if len(app_credentials) == 2 else None,
    )
