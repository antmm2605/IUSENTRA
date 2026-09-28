"""Namirial Sign Web Services (SWS): firma remota Namirial.

Fonte: WSDL pubblico (namespace ``http://service.ws.nam/``) e SWS Integration Guide,
copie e riferimenti in docs/specs/ministero/fonti_ufficiali/2026-09-28/firma/. Operazioni usate:

- ``getOTPList(credentials)`` → dispositivi OTP del titolare (``idOtp``, ``type``);
- ``sendOtpBySMS(credentials)`` / ``sendOtpByPUSH(credentials, title, body)`` → invio del codice;
- ``getCertificate(credentials)`` → certificato di firma;
- ``signPkcs1(credentials, hash, preferences)`` → firma PKCS#1 dell'impronta.

``credentials``: ``idOtp``, ``otp``, ``password`` (PIN del dispositivo remoto),
``securityCode``, ``sessionKey``, ``username`` (codice del dispositivo, es. RHI...).
"""

from __future__ import annotations

import base64

from pct.firma_remota.base import (
    CertificatoRemoto,
    CredenzialiFirmaRemota,
    FirmaRemotaError,
    FirmaRemotaNonConfigurata,
    FirmatarioRemoto,
)
from pct.firma_remota.soap import chiama, elemento

NAMESPACE = "http://service.ws.nam/"


def _credenziali(credenziali: CredenzialiFirmaRemota, *, id_otp: int | None = None, con_otp: bool = False):
    # Ordine della sequenza ``credentials`` nello schema SWS.
    return elemento("credentials", [
        ("idOtp", id_otp),
        ("otp", credenziali.otp if con_otp and credenziali.otp else None),
        ("password", credenziali.password or None),
        ("username", credenziali.username),
    ])


class SwsFirmatario(FirmatarioRemoto):
    protocollo = "sws"

    def __init__(self, endpoint: str, *, sessione=None):
        if not str(endpoint or "").strip():
            raise FirmaRemotaNonConfigurata("Manca l'indirizzo del servizio SWS del prestatore.")
        self.endpoint = str(endpoint).strip()
        self._sessione = sessione
        self._id_otp: int | None = None

    def _chiama(self, operazione: str, argomenti):
        return chiama(self.endpoint, NAMESPACE, operazione, argomenti, sessione=self._sessione)

    def _dispositivo_otp(self, credenziali: CredenzialiFirmaRemota) -> int | None:
        if self._id_otp is not None:
            return self._id_otp
        esito = self._chiama("getOTPList", [("credentials", _credenziali(credenziali))])
        voci = [(int(nodo.findtext("idOtp") or 0), str(nodo.findtext("type") or "").lower())
                for nodo in esito.findall("return") if (nodo.findtext("idOtp") or "").strip().isdigit()]
        if not voci:
            return None
        preferito = {"sms": "sms", "notifica": "push", "app": "app"}.get(credenziali.tipo_otp, "")
        self._id_otp = next((i for i, tipo in voci if preferito and preferito in tipo), voci[0][0])
        return self._id_otp

    def richiedi_otp(self, credenziali: CredenzialiFirmaRemota) -> str:
        id_otp = self._dispositivo_otp(credenziali)
        if credenziali.tipo_otp == "sms":
            self._chiama("sendOtpBySMS", [("credentials", _credenziali(credenziali, id_otp=id_otp))])
            return "Codice inviato per SMS."
        if credenziali.tipo_otp == "notifica":
            self._chiama("sendOtpByPUSH", [("credentials", _credenziali(credenziali, id_otp=id_otp)),
                                           ("title", "IUSENTRA"), ("body", "Codice per la firma del documento")])
            return "Notifica inviata all'app Namirial OTP."
        return "Apri l'app Namirial OTP e leggi il codice."

    def certificato(self, credenziali: CredenzialiFirmaRemota) -> CertificatoRemoto:
        esito = self._chiama("getCertificate", [("credentials", _credenziali(credenziali))])
        valore = str(esito.findtext("return") or "").strip()
        if not valore:
            raise FirmaRemotaError("Il prestatore non ha restituito il certificato di firma.")
        grezzo = base64.b64decode(valore)
        if grezzo.lstrip().startswith(b"-----BEGIN"):
            from cryptography import x509
            from cryptography.hazmat.primitives.serialization import Encoding

            grezzo = x509.load_pem_x509_certificate(grezzo).public_bytes(Encoding.DER)
        return CertificatoRemoto(der=grezzo, riferimento=credenziali.username)

    def firma_impronta(self, credenziali: CredenzialiFirmaRemota, impronta: bytes, certificato: CertificatoRemoto) -> bytes:
        if not credenziali.otp:
            raise FirmaRemotaError("Serve il codice OTP per firmare.")
        esito = self._chiama("signPkcs1", [
            ("credentials", _credenziali(credenziali, id_otp=self._dispositivo_otp(credenziali), con_otp=True)),
            ("hash", base64.b64encode(impronta).decode("ascii")),
            ("preferences", elemento("p", [("hashAlgorithm", "SHA256")])),
        ])
        valore = str(esito.findtext("return") or "").strip()
        if not valore:
            raise FirmaRemotaError("Il prestatore non ha restituito la firma.")
        return base64.b64decode(valore)


__all__ = ["NAMESPACE", "SwsFirmatario"]
