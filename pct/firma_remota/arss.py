"""ArubaSignService (ARSS): firma remota di Aruba e di Actalis.

Fonte: WSDL pubblico del servizio (namespace ``http://arubasignservice.arubapec.it/``),
copie datate in docs/specs/ministero/fonti_ufficiali/2026-09-28/firma/. Operazioni usate:

- ``listCert(Identity)`` → certificati del titolare (``app1``/``app2``: ``id`` e ``value``);
- ``sendCredential(Identity, type)`` → invio del codice via ``SMS`` o ``ARUBACALL``;
- ``signhash(SignHashRequest)`` → firma dell'impronta (``certID``, ``hash``,
  ``hashtype``, ``identity``, ``requirecert``) con ``signature`` e ``cert`` in risposta.

L'identità (tipo ``auth``) porta utente, password di firma (``userPWD``), codice OTP
(``otpPwd``), dominio del contratto (``typeOtpAuth``) e tipo di HSM (``typeHSM``).
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
from pct.firma_remota.soap import chiama, elemento, testo

NAMESPACE = "http://arubasignservice.arubapec.it/"
TIPO_HSM = "COSIGN"
CERT_ID_PREDEFINITO = "AS0"
TIPI_INVIO_OTP = {"sms": "SMS", "chiamata": "ARUBACALL"}


def _identita(credenziali: CredenzialiFirmaRemota, *, con_otp: bool) -> object:
    # Ordine della sequenza ``auth`` nello schema ARSS.
    return elemento("identity", [
        ("otpPwd", credenziali.otp if con_otp and credenziali.otp else None),
        ("typeHSM", TIPO_HSM),
        ("typeOtpAuth", credenziali.dominio or None),
        ("user", credenziali.username),
        ("userPWD", credenziali.password or None),
    ])


def _controlla(esito, operazione: str) -> None:
    stato = testo(esito, "return/status").upper()
    if stato and stato != "OK":
        dettaglio = testo(esito, "return/description") or testo(esito, "return/return_code") or "errore"
        raise FirmaRemotaError(f"Firma remota: {operazione} non riuscita ({dettaglio}).")


def _uso_firma(der: bytes) -> bool:
    from cryptography import x509

    try:
        uso = x509.load_der_x509_certificate(der).extensions.get_extension_for_class(x509.KeyUsage).value
        return bool(uso.content_commitment)
    except Exception:
        return False


class ArssFirmatario(FirmatarioRemoto):
    protocollo = "arss"

    def __init__(self, endpoint: str, *, cert_id: str = CERT_ID_PREDEFINITO, sessione=None):
        if not str(endpoint or "").strip():
            raise FirmaRemotaNonConfigurata("Manca l'indirizzo del servizio ARSS del prestatore.")
        self.endpoint = str(endpoint).strip()
        self.cert_id = str(cert_id or CERT_ID_PREDEFINITO).strip()
        self._sessione = sessione

    def _chiama(self, operazione: str, argomenti):
        return chiama(self.endpoint, NAMESPACE, operazione, argomenti, sessione=self._sessione)

    def richiedi_otp(self, credenziali: CredenzialiFirmaRemota) -> str:
        tipo = TIPI_INVIO_OTP.get(credenziali.tipo_otp)
        if not tipo:
            return "Apri l'app OTP di Aruba e leggi il codice."
        esito = self._chiama("sendCredential", [("Identity", _identita(credenziali, con_otp=False)), ("type", tipo)])
        _controlla(esito, "invio del codice")
        return "Codice inviato per SMS." if tipo == "SMS" else "Riceverai una chiamata con il codice."

    def certificato(self, credenziali: CredenzialiFirmaRemota) -> CertificatoRemoto:
        esito = self._chiama("listCert", [("Identity", _identita(credenziali, con_otp=False))])
        _controlla(esito, "lettura del certificato")
        certificati = []
        for nodo in esito.iter():
            valore = nodo.findtext("value") if nodo.find("value") is not None else None
            if valore:
                certificati.append((str(nodo.findtext("id") or "").strip(), base64.b64decode(valore)))
        if not certificati:
            raise FirmaRemotaError("Il prestatore non ha restituito il certificato di firma: controlla utente e dominio.")
        scelto = next((c for c in certificati if c[0] == self.cert_id), None) \
            or next((c for c in certificati if _uso_firma(c[1])), certificati[0])
        return CertificatoRemoto(der=scelto[1], riferimento=scelto[0] or self.cert_id)

    def firma_impronta(self, credenziali: CredenzialiFirmaRemota, impronta: bytes, certificato: CertificatoRemoto) -> bytes:
        if not credenziali.otp:
            raise FirmaRemotaError("Serve il codice OTP per firmare.")
        esito = self._chiama("signhash", [("SignHashRequest", elemento("r", [
            ("certID", certificato.riferimento or self.cert_id),
            ("hash", base64.b64encode(impronta).decode("ascii")),
            ("hashtype", "SHA256"),
            ("identity", _identita(credenziali, con_otp=True)),
            ("requirecert", True),
        ]))])
        _controlla(esito, "firma")
        firma = testo(esito, "return/signature")
        if not firma:
            raise FirmaRemotaError("Il prestatore non ha restituito la firma.")
        return base64.b64decode(firma)


__all__ = ["ArssFirmatario", "NAMESPACE"]
