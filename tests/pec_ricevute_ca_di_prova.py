"""CA di prova e ricevute PEC vere (firma S/MIME, daticert, postacert) per i test delle notifiche storiche.

Struttura come quella reale: radice → «CA dei gestori PEC» (come AgID CA1) → certificato di firma del gestore.
Le ricevute sono buste ``multipart/signed`` firmate con PKCS#7 distaccato sul contenuto, con il daticert.xml al
primo livello e, per la consegna completa, il messaggio originale ``postacert.eml``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.mime.application import MIMEApplication
from email.mime.message import MIMEMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.parser import BytesParser
from email import policy

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from pct.ricevute_pec_gestore import Fiducia

INIZIO = datetime(2025, 1, 1, tzinfo=timezone.utc)
FINE = datetime(2030, 1, 1, tzinfo=timezone.utc)
STUDIO = "studio@pec.example.test"


def _nome(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, "IT"), x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _certificato(cn, chiave, emittente_nome, chiave_emittente, *, ca: bool, seriale: int, inizio=INIZIO, fine=FINE):
    costruttore = (x509.CertificateBuilder().subject_name(_nome(cn)).issuer_name(emittente_nome)
                   .public_key(chiave.public_key()).serial_number(seriale)
                   .not_valid_before(inizio).not_valid_after(fine)
                   .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
    if ca:
        costruttore = costruttore.add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False, data_encipherment=False,
            key_agreement=False, key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
    else:
        costruttore = (costruttore.add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=True, key_encipherment=False, data_encipherment=False,
            key_agreement=False, key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False))
    return costruttore.sign(chiave_emittente, hashes.SHA256())


@dataclass
class Pki:
    radice: x509.Certificate
    chiave_radice: object
    ca: x509.Certificate
    chiave_ca: object
    gestore: x509.Certificate
    chiave_gestore: object
    estraneo: x509.Certificate
    chiave_estraneo: object

    @property
    def fiducia(self) -> Fiducia:
        pem = serialization.Encoding.PEM
        return Fiducia(self.ca.public_bytes(pem), self.radice.public_bytes(pem))

    def crl(self, emittente: str = "ca", revocati: tuple[tuple[int, datetime, x509.ReasonFlags], ...] = ()):
        certificato, chiave = (self.ca, self.chiave_ca) if emittente == "ca" else (self.radice, self.chiave_radice)
        costruttore = (x509.CertificateRevocationListBuilder().issuer_name(certificato.subject)
                       .last_update(datetime.now(timezone.utc) - timedelta(hours=1))
                       .next_update(datetime.now(timezone.utc) + timedelta(days=1)))
        for seriale, quando, motivo in revocati:
            costruttore = costruttore.add_revoked_certificate(
                x509.RevokedCertificateBuilder().serial_number(seriale).revocation_date(quando)
                .add_extension(x509.CRLReason(motivo), critical=False).build())
        return costruttore.sign(chiave, hashes.SHA256())

    def revoche(self, revocati_ca=()):
        return lambda _fiducia: [self.crl("ca", revocati_ca), self.crl("radice")]


def pki() -> Pki:
    chiavi = [ec.generate_private_key(ec.SECP256R1()) for _ in range(4)]
    radice = _certificato("Radice di prova", chiavi[0], _nome("Radice di prova"), chiavi[0], ca=True, seriale=1)
    ca = _certificato("CA dei gestori PEC di prova", chiavi[1], radice.subject, chiavi[0], ca=True, seriale=2)
    gestore = _certificato("Gestore PEC di prova", chiavi[2], ca.subject, chiavi[1], ca=False, seriale=3)
    estraneo = _certificato("Firmatario estraneo", chiavi[3], radice.subject, chiavi[0], ca=False, seriale=4)
    return Pki(radice, chiavi[0], ca, chiavi[1], gestore, chiavi[2], estraneo, chiavi[3])


def pki_rinnovata() -> tuple[Pki, x509.Certificate]:
    """CA dei gestori rinnovata con la stessa chiave: la versione fissata vale da dopo la ricevuta, la precedente
    (inclusa dal gestore nella firma, come nelle ricevute reali anteriori al 20/02/2025) copriva la data."""
    p = pki()
    nuova = _certificato("CA dei gestori PEC di prova", p.chiave_ca, p.radice.subject, p.chiave_radice, ca=True, seriale=20,
                         inizio=datetime(2026, 6, 1, tzinfo=timezone.utc))
    vecchia = _certificato("CA dei gestori PEC di prova", p.chiave_ca, p.radice.subject, p.chiave_radice, ca=True, seriale=10)
    p.ca = nuova
    return p, vecchia


def messaggio_inviato(destinatari: list[str], allegati: dict[str, bytes], *, message_id="<invio-1@studio.test>",
                      mittente=STUDIO, oggetto="Notificazione ai sensi della legge n. 53/1994 [Notifica_ID:Prova123]") -> bytes:
    invio = EmailMessage()
    invio["From"] = mittente
    invio["To"] = ", ".join(destinatari)
    invio["Subject"] = oggetto
    invio["Message-ID"] = message_id
    invio["Date"] = "Mon, 20 Apr 2026 10:16:58 +0200"
    invio.set_content("Relata nel file allegato.")
    for nome, dati in allegati.items():
        invio.add_attachment(dati, maintype="application", subtype="pdf", filename=nome)
    return invio.as_bytes()


def daticert(tipo: str, *, destinatari: list[str], msgid: str, consegna: str = "", mittente: str = STUDIO,
             ora: str = "10:17:11", identificativo: str = "gestore-1@pec.example.test",
             oggetto: str = "Notificazione ai sensi della legge n. 53/1994 [Notifica_ID:Prova123]") -> bytes:
    righe = "".join(f'<destinatari tipo="certificato">{d}</destinatari>' for d in destinatari)
    extra = f'<ricevuta tipo="completa" /><consegna>{consegna}</consegna>' if tipo == "avvenuta-consegna" else ""
    msgid_xml = msgid.replace("<", "&lt;").replace(">", "&gt;")
    return (f'<?xml version="1.0" encoding="UTF-8"?><postacert tipo="{tipo}" errore="nessuno"><intestazione>'
            f"<mittente>{mittente}</mittente>{righe}<oggetto>{oggetto}</oggetto></intestazione><dati>"
            f'<gestore-emittente>Gestore di prova</gestore-emittente><data zona="+0200"><giorno>20/04/2026</giorno>'
            f"<ora>{ora}</ora></data><identificativo>{identificativo}</identificativo><msgid>{msgid_xml}</msgid>{extra}"
            f"</dati></postacert>").encode()


def _contenuto(xml: bytes, originale: bytes | None, *, annidato: bool) -> bytes:
    corpo = MIMEMultipart("mixed")
    corpo.attach(MIMEText("Ricevuta del gestore di prova.", "plain", "us-ascii"))
    if originale is not None:
        parte = MIMEMessage(BytesParser(policy=policy.compat32).parsebytes(originale))
        parte.add_header("Content-Disposition", "attachment", filename="postacert.eml")
        corpo.attach(parte)
    allegato = MIMEApplication(xml, "xml")
    allegato.add_header("Content-Disposition", "attachment", filename="daticert.xml")
    if annidato:
        interno = MIMEMultipart("mixed")
        interno.attach(allegato)
        corpo.attach(interno)
    else:
        corpo.attach(allegato)
    return corpo.as_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def ricevuta(p: Pki, tipo: str, xml: bytes, *, originale: bytes | None = None, annidato: bool = False,
             firmatario: str = "gestore", msgid: str = "<invio-1@studio.test>", inclusi=()) -> bytes:
    certificato, chiave = (p.gestore, p.chiave_gestore) if firmatario == "gestore" else (p.estraneo, p.chiave_estraneo)
    costruttore = (pkcs7.PKCS7SignatureBuilder().set_data(_contenuto(xml, originale, annidato=annidato))
                   .add_signer(certificato, chiave, hashes.SHA256()))
    for incluso in inclusi:
        costruttore = costruttore.add_certificate(incluso)
    firmato = (costruttore
               .sign(serialization.Encoding.SMIME, [pkcs7.PKCS7Options.DetachedSignature]))
    prefisso = "ACCETTAZIONE" if tipo == "accettazione" else "CONSEGNA"
    intestazioni = (f"From: posta-certificata@pec.example.test\r\nTo: {STUDIO}\r\n"
                    f"Subject: {prefisso}: Notificazione ai sensi della legge n. 53/1994 [Notifica_ID:Prova123]\r\n"
                    f"Message-ID: <{tipo}-{hashlib.sha256(xml).hexdigest()[:8]}@pec.example.test>\r\n"
                    f"X-Ricevuta: {tipo}\r\nX-Riferimento-Message-ID: {msgid}\r\n").encode()
    return intestazioni + firmato.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
