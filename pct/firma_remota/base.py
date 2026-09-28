"""Firma remota qualificata: tipi comuni, errori e credenziali.

Base normativa: Reg. eIDAS 910/2014 (firma elettronica qualificata, anche con
dispositivo gestito da un prestatore qualificato per conto del firmatario, art. 29
e All. II); CAD D.Lgs. 82/2005 art. 20 (efficacia della firma qualificata);
D.M. 44/2011 art. 12 (firma degli atti nel deposito telematico). La firma remota
produce le stesse buste CAdES (.p7m) e PAdES della firma con smart card: cambia
solo il luogo della chiave (HSM del prestatore) e l'autenticazione (password di
firma + codice OTP del titolare).

Regole di sicurezza non derogabili:
- il gestionale non memorizza mai password di firma né OTP: le credenziali
  viaggiano per singola richiesta e non vengono serializzate né registrate;
- fail-closed: nessun prestatore configurato, nessuna firma remota;
- il provider di prova è riconoscibile e dichiara che l'output non ha valore legale;
- ogni firma ricevuta dal prestatore si verifica con la chiave pubblica del
  certificato prima di chiudere la busta: una risposta sbagliata non diventa un
  documento «firmato».
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

FONTE_NORMATIVA = (
    "Reg. eIDAS 910/2014 art. 29 e All. II; CAD D.Lgs. 82/2005 art. 20; "
    "D.M. 44/2011 art. 12"
)


class FirmaRemotaError(RuntimeError):
    """Errore operativo della firma remota (messaggio pronto per l'avvocato)."""


class FirmaRemotaNonConfigurata(FirmaRemotaError):
    """Prestatore scelto ma non attivabile: configurazione mancante."""


@dataclass
class CredenzialiFirmaRemota:
    """Credenziali per una sola richiesta di firma. Mai persistite né registrate.

    ``password`` è la password (o PIN) di firma remota del titolare, ``otp`` il
    codice usa-e-getta (app, SMS, chiamata), ``pin`` il PIN della credenziale quando
    il servizio (CSC) lo distingue dalla password di accesso. Tutti ``repr=False``.
    """

    username: str
    password: str = field(repr=False, default="")
    otp: str = field(repr=False, default="")
    tipo_otp: str = "app"
    dominio: str = ""
    pin: str = field(repr=False, default="")

    def __post_init__(self) -> None:
        if not str(self.username or "").strip():
            raise ValueError("La firma remota richiede lo username del titolare.")
        self.username = str(self.username).strip()
        self.otp = str(self.otp or "").strip()

    def __str__(self) -> str:  # difesa in profondità contro log accidentali
        return f"CredenzialiFirmaRemota(username={self.username!r}, password=***, otp=***)"


@dataclass
class CertificatoRemoto:
    """Certificato di firma del titolare, letto dal prestatore prima di firmare."""

    der: bytes
    catena: list[bytes] = field(default_factory=list)
    riferimento: str = ""

    def x509(self):
        from cryptography import x509

        return x509.load_der_x509_certificate(self.der)

    @property
    def intestatario(self) -> str:
        from cryptography.x509.oid import NameOID

        soggetto = self.x509().subject
        nomi = soggetto.get_attributes_for_oid(NameOID.COMMON_NAME)
        return str(nomi[0].value).strip() if nomi else soggetto.rfc4514_string()

    @property
    def emittente(self) -> str:
        from cryptography.x509.oid import NameOID

        nomi = self.x509().issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
        return str(nomi[0].value).strip() if nomi else ""


@dataclass
class EsitoFirmaRemota:
    """Risultato di una firma remota."""

    contenuto: bytes
    formato: str  # "cades" | "pades"
    provider: str
    valida_legalmente: bool = True
    dettagli: dict[str, Any] = field(default_factory=dict)


class FirmatarioRemoto(ABC):
    """Il servizio del prestatore visto dal gestionale: certificato, OTP e firma di un'impronta.

    Ogni protocollo (ARSS, SWS, CSC) lo implementa; le buste CAdES e PAdES si
    costruiscono in IUSENTRA (``pct.firma_remota.buste``) e al prestatore arriva
    solo l'impronta SHA-256 da firmare, mai il documento.
    """

    protocollo: str = ""

    def richiedi_otp(self, credenziali: CredenzialiFirmaRemota) -> str:
        """Chiede al prestatore di inviare il codice (SMS, notifica). Restituisce il messaggio per l'avvocato."""
        return "Apri l'app del prestatore e leggi il codice OTP."

    @abstractmethod
    def certificato(self, credenziali: CredenzialiFirmaRemota) -> CertificatoRemoto:
        """Il certificato di firma del titolare (e la catena, se il prestatore la fornisce)."""

    @abstractmethod
    def firma_impronta(self, credenziali: CredenzialiFirmaRemota, impronta: bytes, certificato: CertificatoRemoto) -> bytes:
        """Firma RSA PKCS#1 v1.5 dell'impronta SHA-256 (32 byte)."""

    def chiudi(self, credenziali: CredenzialiFirmaRemota) -> None:
        """Chiude l'eventuale sessione aperta presso il prestatore."""


class FirmaRemotaProvider(ABC):
    """Interfaccia dei provider di firma remota qualificata (prestatori)."""

    nome: str = ""

    @abstractmethod
    def disponibile(self) -> bool:
        """True se il provider è configurato e attivabile."""

    @abstractmethod
    def firma_cades(
        self,
        documento: bytes,
        credenziali: CredenzialiFirmaRemota,
        *,
        detached: bool = True,
    ) -> EsitoFirmaRemota:
        """Busta CAdES (.p7m) firmata dall'HSM del prestatore."""

    @abstractmethod
    def firma_pades(
        self,
        pdf: bytes,
        credenziali: CredenzialiFirmaRemota,
    ) -> EsitoFirmaRemota:
        """PDF firmato PAdES dall'HSM del prestatore."""


def verifica_firma_rsa(certificato_der: bytes, impronta: bytes, firma: bytes) -> None:
    """La firma restituita dal prestatore deve verificare con la chiave del certificato."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
    from cryptography import x509

    chiave = x509.load_der_x509_certificate(certificato_der).public_key()
    if not isinstance(chiave, rsa.RSAPublicKey):
        raise FirmaRemotaError(
            "Il certificato di firma remota usa una chiave non RSA: questa versione di IUSENTRA "
            "costruisce buste CAdES e PAdES solo con chiavi RSA."
        )
    try:
        chiave.verify(firma, impronta, padding.PKCS1v15(), utils.Prehashed(hashes.SHA256()))
    except InvalidSignature as exc:
        raise FirmaRemotaError(
            "La firma restituita dal prestatore non corrisponde al certificato: il documento non è stato firmato."
        ) from exc


__all__ = [
    "FONTE_NORMATIVA", "CertificatoRemoto", "CredenzialiFirmaRemota", "EsitoFirmaRemota", "FirmaRemotaError",
    "FirmaRemotaNonConfigurata", "FirmaRemotaProvider", "FirmatarioRemoto", "verifica_firma_rsa",
]
