"""Servizi di firma remota simulati per i test: ARSS, SWS e CSC con una vera chiave RSA.

Rispondono come descritto dai WSDL pubblici (ARSS, SWS) e dalla specifica CSC:
il test esercita l'XML/JSON che IUSENTRA invia e la firma che riceve.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
from cryptography.x509.oid import NameOID
from lxml import etree

SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"


def chiave_e_certificato(nome: str = "ROSSI MARIO", *, scaduto: bool = False):
    chiave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    adesso = datetime.now(timezone.utc)
    inizio, fine = (adesso - timedelta(days=400), adesso - timedelta(days=1)) if scaduto else (adesso - timedelta(days=1), adesso + timedelta(days=365))
    soggetto = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nome), x509.NameAttribute(NameOID.COUNTRY_NAME, "IT")])
    emittente = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Prestatore Qualificato di Prova")])
    certificato = (
        x509.CertificateBuilder().subject_name(soggetto).issuer_name(emittente).public_key(chiave.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(inizio).not_valid_after(fine)
        .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=True, key_encipherment=False,
                                     data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False,
                                     encipher_only=False, decipher_only=False), critical=True)
        .sign(chiave, hashes.SHA256())
    )
    return chiave, certificato.public_bytes(serialization.Encoding.DER)


def firma(chiave, impronta: bytes) -> bytes:
    return chiave.sign(impronta, padding.PKCS1v15(), utils.Prehashed(hashes.SHA256()))


class _Risposta:
    def __init__(self, contenuto: bytes, stato: int = 200):
        self.content = contenuto
        self.status_code = stato

    def json(self):
        return json.loads(self.content or b"{}")


def _busta_soap(namespace: str, operazione: str, corpo: str) -> bytes:
    return (f'<soap:Envelope xmlns:soap="{SOAP_ENV}"><soap:Body><ns:{operazione}Response xmlns:ns="{namespace}">'
            f"{corpo}</ns:{operazione}Response></soap:Body></soap:Envelope>").encode()


def _fault(testo: str) -> bytes:
    return (f'<soap:Envelope xmlns:soap="{SOAP_ENV}"><soap:Body><soap:Fault><faultcode>soap:Server</faultcode>'
            f"<faultstring>{testo}</faultstring></soap:Fault></soap:Body></soap:Envelope>").encode()


class ServizioSimulato:
    """Una sessione ``requests`` finta: registra le chiamate e risponde come il prestatore."""

    def __init__(self, *, otp: str = "123456", password: str = "Firma!2026", firma_sbagliata: bool = False):
        self.chiave, self.cert_der = chiave_e_certificato()
        self.otp, self.password, self.firma_sbagliata = otp, password, firma_sbagliata
        self.chiamate: list[tuple[str, object]] = []

    def _firma(self, impronta: bytes) -> bytes:
        if self.firma_sbagliata:
            impronta = bytes(32)
        return firma(self.chiave, impronta)

    # --- SOAP (ARSS / SWS) -----------------------------------------------------------
    def post(self, url, data=None, json=None, headers=None, auth=None, timeout=None):
        if json is not None or auth is not None:
            return self._csc(url, json or {}, headers or {}, auth)
        radice = etree.fromstring(data)
        richiesta = radice.find(f"{{{SOAP_ENV}}}Body")[0]
        namespace, operazione = etree.QName(richiesta).namespace, etree.QName(richiesta).localname
        self.chiamate.append((operazione, richiesta))
        return _Risposta(getattr(self, f"_soap_{operazione}")(namespace, richiesta))

    def _soap_listCert(self, ns, r):
        valore = base64.b64encode(self.cert_der).decode()
        return _busta_soap(ns, "listCert", f"<return><app1><id>AS0</id><value>{valore}</value></app1><status>OK</status></return>")

    def _soap_sendCredential(self, ns, r):
        return _busta_soap(ns, "sendCredential", "<return><status>OK</status><return_code>0000</return_code></return>")

    def _soap_signhash(self, ns, r):
        req = r.find("SignHashRequest")
        identita = req.find("identity")
        if identita.findtext("otpPwd") != self.otp or identita.findtext("userPWD") != self.password:
            return _busta_soap(ns, "signhash", "<return><status>KO</status><return_code>0003</return_code>"
                                               "<description>Credenziali non valide</description></return>")
        impronta = base64.b64decode(req.findtext("hash"))
        valore = base64.b64encode(self._firma(impronta)).decode()
        return _busta_soap(ns, "signhash", f"<return><signature>{valore}</signature><status>OK</status></return>")

    def _soap_getOTPList(self, ns, r):
        return _busta_soap(ns, "getOTPList", "<return><idOtp>7</idOtp><serialNumber>X1</serialNumber><type>SMS</type></return>")

    def _soap_sendOtpBySMS(self, ns, r):
        return _busta_soap(ns, "sendOtpBySMS", "")

    def _soap_getCertificate(self, ns, r):
        return _busta_soap(ns, "getCertificate", f"<return>{base64.b64encode(self.cert_der).decode()}</return>")

    def _soap_signPkcs1(self, ns, r):
        cred = r.find("credentials")
        if cred.findtext("otp") != self.otp or cred.findtext("password") != self.password:
            return _fault("Invalid OTP code")
        impronta = base64.b64decode(r.findtext("hash"))
        return _busta_soap(ns, "signPkcs1", f"<return>{base64.b64encode(self._firma(impronta)).decode()}</return>")

    # --- CSC -------------------------------------------------------------------------
    def _csc(self, url, corpo, headers, auth):
        percorso = url.split("/csc/")[1].split("/", 1)[1]
        self.chiamate.append((percorso, corpo))
        v2 = "/csc/v2/" in url
        if percorso == "auth/login":
            if auth != ("avv.rossi", "Accesso!1"):
                return _Risposta(b'{"error":"invalid_request","error_description":"Credenziali errate"}', 400)
            return _Risposta(b'{"access_token":"tok-1","expires_in":3600}')
        if headers.get("Authorization") != "Bearer tok-1":
            return _Risposta(b'{"error":"invalid_token"}', 401)
        if percorso == "credentials/list":
            return _Risposta(b'{"credentialIDs":["CRED-1"]}')
        if percorso == "credentials/info":
            dati = {"key": {"status": "enabled", "algo": ["1.2.840.113549.1.1.1"][0], "len": 2048},
                    "cert": {"status": "valid", "certificates": [base64.b64encode(self.cert_der).decode()]},
                    "OTP": {"presence": "true", "type": "online"}}
            return _Risposta(json.dumps(dati).encode())
        if percorso == "credentials/sendOTP":
            return _Risposta(b"", 204)
        if percorso == "credentials/authorize":
            if v2:
                valori = {a["id"]: a["value"] for a in corpo.get("authData", [])}
                pin, otp = valori.get("PIN"), valori.get("OTP")
            else:
                pin, otp = corpo.get("PIN"), corpo.get("OTP")
            if pin != self.password or otp != self.otp:
                return _Risposta(b'{"error":"invalid_otp","error_description":"PIN o OTP errati"}', 400)
            return _Risposta(b'{"SAD":"sad-1","expiresIn":300}')
        if percorso == "signatures/signHash":
            chiave = "hashes" if v2 else "hash"
            codificata = corpo[chiave][0]
            impronta = base64.urlsafe_b64decode(codificata) if v2 else base64.b64decode(codificata)
            return _Risposta(json.dumps({"signatures": [base64.b64encode(self._firma(impronta)).decode()]}).encode())
        if percorso == "auth/revoke":
            return _Risposta(b"", 204)
        return _Risposta(b'{"error":"not_found"}', 404)
