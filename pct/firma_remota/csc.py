"""Cloud Signature Consortium (CSC API v1 e v2): firma remota con lo standard europeo.

Fonti: CSC API v1.0.4.0 e v2.0.0.2 (cloudsignatureconsortium.org, riferimenti in
docs/specs/ministero/fonti_ufficiali/2026-09-28/firma/README.md). Flusso:

1. ``auth/login`` (Basic utente:password) → ``access_token`` del servizio;
2. ``credentials/list`` → ``credentialIDs``; ``credentials/info`` → certificato e catena;
3. ``credentials/sendOTP`` quando l'OTP è inviato dal servizio (v1, OTP «online»);
4. ``credentials/authorize`` con PIN e OTP → ``SAD`` legato all'impronta;
5. ``signatures/signHash`` → firma PKCS#1 dell'impronta SHA-256.

L'indirizzo del servizio lo rilascia il prestatore con il contratto e termina con
``/csc/v1`` o ``/csc/v2`` (la versione si legge da lì).
"""

from __future__ import annotations

import base64
from typing import Any

from pct.firma_remota.base import (
    CertificatoRemoto,
    CredenzialiFirmaRemota,
    FirmaRemotaError,
    FirmaRemotaNonConfigurata,
    FirmatarioRemoto,
)
from pct.firma_remota.soap import TIMEOUT_SECONDI, valida_endpoint

OID_SHA256 = "2.16.840.1.101.3.4.2.1"
OID_RSA = "1.2.840.113549.1.1.1"


def _decodifica(valore: str) -> bytes:
    """Base64 standard o base64url (v2), con o senza riempimento."""
    valore = valore.strip() + "=" * (-len(valore.strip()) % 4)
    return base64.urlsafe_b64decode(valore) if ("-" in valore or "_" in valore) else base64.b64decode(valore)


class CscFirmatario(FirmatarioRemoto):
    protocollo = "csc"

    def __init__(self, endpoint: str, *, credential_id: str = "", sessione=None):
        indirizzo = str(endpoint or "").strip().rstrip("/")
        if not indirizzo:
            raise FirmaRemotaNonConfigurata("Manca l'indirizzo del servizio CSC rilasciato dal prestatore.")
        valida_endpoint(indirizzo)
        if indirizzo.endswith("/csc/v2"):
            self.versione = 2
        elif indirizzo.endswith("/csc/v1"):
            self.versione = 1
        else:
            raise FirmaRemotaError("L'indirizzo del servizio CSC deve terminare con /csc/v1 o /csc/v2.")
        self.endpoint = indirizzo
        self.credential_id = str(credential_id or "").strip()
        self._sessione = sessione
        self._token = ""
        self._info: dict[str, Any] = {}

    def _post(self, percorso: str, corpo: dict[str, Any], *, basic: tuple[str, str] | None = None) -> dict[str, Any]:
        import requests

        client = self._sessione or requests
        intestazioni = {"Content-Type": "application/json"}
        if self._token and basic is None:
            intestazioni["Authorization"] = f"Bearer {self._token}"
        try:
            risposta = client.post(f"{self.endpoint}/{percorso}", json=corpo, headers=intestazioni,
                                   auth=basic, timeout=TIMEOUT_SECONDI)
        except requests.RequestException as exc:
            raise FirmaRemotaError("Il servizio di firma remota non risponde: riprova tra qualche istante.") from exc
        try:
            dati = risposta.json() if risposta.content else {}
        except ValueError:
            dati = {}
        if risposta.status_code >= 400:
            dettaglio = str(dati.get("error_description") or dati.get("error") or f"HTTP {risposta.status_code}")
            raise FirmaRemotaError(f"Il prestatore ha rifiutato la richiesta ({percorso}): {dettaglio}")
        return dati if isinstance(dati, dict) else {}

    def _accedi(self, credenziali: CredenzialiFirmaRemota) -> None:
        if self._token:
            return
        if not credenziali.password:
            raise FirmaRemotaError("Serve la password del servizio di firma remota.")
        dati = self._post("auth/login", {"rememberMe": False}, basic=(credenziali.username, credenziali.password))
        self._token = str(dati.get("access_token") or "")
        if not self._token:
            raise FirmaRemotaError("Accesso al servizio di firma remota non riuscito.")

    def _credenziale(self, credenziali: CredenzialiFirmaRemota) -> str:
        if self.credential_id:
            return self.credential_id
        self._accedi(credenziali)
        elenco = self._post("credentials/list", {"maxResults": 10}).get("credentialIDs") or []
        if not elenco:
            raise FirmaRemotaError("Nessun certificato di firma remota associato all'utente.")
        self.credential_id = str(elenco[0])
        return self.credential_id

    def _informazioni(self, credenziali: CredenzialiFirmaRemota) -> dict[str, Any]:
        if not self._info:
            self._accedi(credenziali)
            corpo = {"credentialID": self._credenziale(credenziali), "certificates": "chain", "certInfo": True}
            if self.versione == 2:
                corpo["authInfo"] = True
            self._info = self._post("credentials/info", corpo)
        return self._info

    def richiedi_otp(self, credenziali: CredenzialiFirmaRemota) -> str:
        otp = self._informazioni(credenziali).get("OTP") or {}
        if self.versione == 1 and str(otp.get("type") or "").lower() == "online":
            self._post("credentials/sendOTP", {"credentialID": self._credenziale(credenziali)})
            return "Codice inviato dal prestatore."
        return "Apri l'app del prestatore e leggi il codice OTP."

    def certificato(self, credenziali: CredenzialiFirmaRemota) -> CertificatoRemoto:
        info = self._informazioni(credenziali)
        algoritmo = str((info.get("key") or {}).get("algo") or "")
        if algoritmo and algoritmo not in {OID_RSA, "1.2.840.113549.1.1.11"}:
            raise FirmaRemotaError("Il certificato di firma remota non usa una chiave RSA: non ancora supportato.")
        catena = [base64.b64decode(c) for c in ((info.get("cert") or {}).get("certificates") or [])]
        if not catena:
            raise FirmaRemotaError("Il prestatore non ha restituito il certificato di firma.")
        return CertificatoRemoto(der=catena[0], catena=catena[1:], riferimento=self._credenziale(credenziali))

    def _codifica(self, impronta: bytes) -> str:
        return (base64.urlsafe_b64encode(impronta) if self.versione == 2 else base64.b64encode(impronta)).decode("ascii")

    def firma_impronta(self, credenziali: CredenzialiFirmaRemota, impronta: bytes, certificato: CertificatoRemoto) -> bytes:
        self._accedi(credenziali)
        credenziale = self._credenziale(credenziali)
        pin = credenziali.pin or credenziali.password
        if self.versione == 2:
            autorizza = {"credentialID": credenziale, "numSignatures": 1, "hashes": [self._codifica(impronta)],
                         "hashAlgorithmOID": OID_SHA256,
                         "authData": [{"id": "PIN", "value": pin}, {"id": "OTP", "value": credenziali.otp}]}
        else:
            autorizza = {"credentialID": credenziale, "numSignatures": 1, "hash": [self._codifica(impronta)],
                         "PIN": pin, "OTP": credenziali.otp, "description": "Firma documento IUSENTRA"}
        sad = str(self._post("credentials/authorize", autorizza).get("SAD") or "")
        if not sad:
            raise FirmaRemotaError("Autorizzazione della firma non riuscita: controlla PIN e codice OTP.")
        chiave_hash = "hashes" if self.versione == 2 else "hash"
        chiave_algo = "hashAlgorithmOID" if self.versione == 2 else "hashAlgo"
        firme = self._post("signatures/signHash", {"credentialID": credenziale, "SAD": sad,
                                                   chiave_hash: [self._codifica(impronta)],
                                                   chiave_algo: OID_SHA256, "signAlgo": OID_RSA}).get("signatures") or []
        if not firme:
            raise FirmaRemotaError("Il prestatore non ha restituito la firma.")
        return _decodifica(str(firme[0]))

    def chiudi(self, credenziali: CredenzialiFirmaRemota) -> None:
        if self._token:
            try:
                self._post("auth/revoke", {"token": self._token})
            except FirmaRemotaError:
                pass
            self._token = ""


__all__ = ["CscFirmatario", "OID_RSA", "OID_SHA256"]
