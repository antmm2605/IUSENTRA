"""Verifica crittografica di una ricevuta PEC del gestore (accettazione o avvenuta consegna).

Una ricevuta PEC vale come prova solo se è il messaggio firmato dal gestore (D.P.R. 68/2005, art. 6;
regole tecniche D.M. 2/11/2005, §§ 7.3-7.4): la busta ``multipart/signed`` con la firma S/MIME del
gestore e, al primo livello del contenuto firmato, il ``daticert.xml`` con tipo, mittente, destinatari,
identificativo e ``msgid`` del messaggio originale. La ricevuta di avvenuta consegna «completa» contiene
anche il messaggio originale (``postacert.eml``) con i suoi allegati.

Controlli, tutti obbligatori (fail-closed: al primo che non passa la ricevuta resta non verificata, con
il motivo preciso):

1. **firma**: la firma PKCS#7 della busta copre il contenuto (``openssl cms -verify``), un solo firmatario;
2. **gestore**: il certificato del firmatario è emesso dalla CA AgID dei gestori PEC («AgID CA1», copia
   fissata con impronta, vedi ``pct/sdi_pec_trust.py``; CPS AgID CA1 § 1.3.3: certificati di firma
   destinati ai soli gestori PEC), la catena arriva alla radice Actalis del sistema, la finalità è la firma
   S/MIME e il certificato era valido all'istante dichiarato nel daticert;
3. **revoche**: il certificato del gestore e la CA AgID non risultano revocati nelle liste ufficiali (CRL
   firmate, in corso di validità); una revoca successiva alla ricevuta è ammessa solo per motivi che non
   toccano la chiave (sostituzione, cessazione, cambio di affiliazione);
4. **daticert**: uno e uno solo, al primo livello del contenuto firmato (mai uno annidato in un allegato),
   tipo ``accettazione`` o ``avvenuta-consegna``, senza errori; per la consegna serve la ricevuta completa;
5. **mittente**: il mittente certificato è la casella PEC dello studio.

La correlazione con il messaggio inviato, la relata e l'atto è in ``pct/notifiche_pec_storiche_prova.py``.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, Iterable

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization

from pct.pec_contenuto_firmato import estrai_contenuto_cms
from pct.pec_ricevute_archivio import Ricevuta, leggi_daticert_firmato, tipo_eml_storico
from pct.sdi_pec_trust import PecTrustError

VERSIONE = "ricevute_pec_gestore_v1"
NORMA = "D.P.R. 68/2005, artt. 6 e 9; D.M. 2/11/2005, §§ 7.3-7.4"
LIVELLO = ("firma S/MIME del gestore verificata; certificato emesso dalla CA AgID dei gestori PEC (AgID CA1, chiave "
           "fissata; versioni precedenti della stessa CA accettate solo con la stessa chiave e firmate dalla radice) con "
           "catena alla radice Actalis, valido all'istante della ricevuta; revoche controllate sulle CRL ufficiali "
           "AgID CA1 e Actalis")

# Revoche che non riguardano la compromissione della chiave: non travolgono una firma anteriore.
_REVOCHE_SENZA_COMPROMISSIONE = {
    x509.ReasonFlags.superseded,
    x509.ReasonFlags.cessation_of_operation,
    x509.ReasonFlags.affiliation_changed,
}

MOTIVI = {
    "non_ricevuta": "Il file non è una ricevuta PEC firmata di accettazione o di avvenuta consegna.",
    "verificatore_assente": "Verificatore della firma PEC non disponibile: la verifica sarà ripetuta.",
    "fiducia_non_disponibile": "Certificati di fiducia della CA AgID dei gestori PEC non disponibili: la verifica sarà ripetuta.",
    "firma_non_valida": "Firma del gestore non verificabile: la busta della ricevuta non supera la verifica di integrità.",
    "firmatario_non_univoco": "Firma del gestore non verificabile: la ricevuta non ha un solo firmatario.",
    "daticert_assente": "Dati di certificazione (daticert.xml) assenti o non al primo livello della busta firmata.",
    "daticert_non_valido": "Dati di certificazione non validi: la ricevuta non attesta accettazione o consegna senza errori.",
    "consegna_non_completa": "Ricevuta di consegna non completa: manca il messaggio originale certificato (postacert.eml).",
    "gestore_non_riconosciuto": "Gestore non riconosciuto: il certificato del firmatario non è emesso dalla CA AgID dei gestori PEC.",
    "catena_non_valida": "Gestore non riconosciuto: la catena del certificato non è valida all'istante della ricevuta.",
    "revoche_non_verificabili": "Revoche del certificato del gestore non verificabili ora: la verifica sarà ripetuta.",
    "certificato_revocato": "Certificato del gestore revocato: la ricevuta non è una prova affidabile.",
    "mittente_diverso": "Il mittente certificato non è la casella PEC dello studio.",
    "casella_non_configurata": "Casella PEC dello studio non configurata: la ricevuta non può essere attribuita allo studio.",
}
# Esiti che dipendono da un servizio momentaneamente non disponibile: si ripete la verifica.
RIPETIBILI = {"verificatore_assente", "fiducia_non_disponibile", "revoche_non_verificabili"}


@dataclass(frozen=True)
class EsitoRicevuta:
    riferimento: str  # documento del fascicolo o messaggio della casella
    impronta: str  # SHA-256 dell'EML
    codice: str = ""  # vuoto = verificata
    ricevuta: Ricevuta | None = None
    firmatario: dict = field(default_factory=dict)
    revoche: dict = field(default_factory=dict)

    @property
    def verificata(self) -> bool:
        return not self.codice and self.ricevuta is not None

    @property
    def motivo(self) -> str:
        return MOTIVI.get(self.codice, self.codice)

    @property
    def ripetibile(self) -> bool:
        return self.codice in RIPETIBILI

    def come_dizionario(self) -> dict:
        r = self.ricevuta
        return {
            "riferimento": self.riferimento, "impronta": self.impronta, "verificata": self.verificata,
            "codice": self.codice, "motivo": self.motivo if self.codice else "",
            "tipo": r.tipo if r else "", "identificativo": r.identificativo if r else "",
            "msgid": r.message_id if r else "", "data": r.data.isoformat() if r else "",
            "mittenti": sorted(r.mittenti) if r else [], "destinatari": sorted(r.destinatari) if r else [],
            "consegna": r.consegna if r else "", "impronte_allegati": sorted(r.impronte) if r else [],
            "notifica_l53": bool(r and r.notifica_l53),
            "firmatario": dict(self.firmatario), "revoche": dict(self.revoche),
        }


@dataclass(frozen=True)
class Fiducia:
    """CA dei gestori PEC (intermedia) e radice: in produzione ``sdi_pec_trust.trust_certificates()``."""

    ca_pem: bytes
    radice_pem: bytes


Revoche = Callable[[Fiducia], Iterable[x509.CertificateRevocationList]]


def originale_certificato(raw: bytes) -> bytes | None:
    """Il messaggio originale (``postacert.eml``) contenuto in una ricevuta di avvenuta consegna completa,
    estratto dal solo contenuto coperto dalla firma del gestore. Il chiamante usa solo ricevute già verificate
    con la stessa impronta."""
    executable = shutil.which("openssl")
    if not executable:
        return None
    from email import policy as _policy
    from email.parser import BytesParser as _Parser

    with TemporaryDirectory(prefix="iusentra-originale-pec-") as directory:
        cartella = Path(directory)
        (cartella / "r.eml").write_bytes(raw)
        try:
            estrai_contenuto_cms(executable, cartella / "r.eml", cartella / "c.mime", cartella / "s.pem")
            contenuto = _Parser(policy=_policy.default).parsebytes((cartella / "c.mime").read_bytes())
        except Exception:
            return None
    originali = [p for p in contenuto.iter_parts() if p.get_content_type() == "message/rfc822"
                 and (p.get_filename() or "").casefold() == "postacert.eml"]
    if len(originali) != 1 or not isinstance(originali[0].get_payload(), list) or len(originali[0].get_payload()) != 1:
        return None
    return originali[0].get_payload()[0].as_bytes()


def esito_da_dizionario(dati: dict) -> EsitoRicevuta:
    """L'esito salvato di una ricevuta già verificata (stessa impronta e stessa versione del verificatore)."""
    ricevuta = None
    if dati.get("verificata"):
        ricevuta = Ricevuta(
            str(dati["tipo"]), str(dati["identificativo"]), str(dati["msgid"]), datetime.fromisoformat(str(dati["data"])),
            frozenset(dati.get("mittenti") or ()), frozenset(dati.get("destinatari") or ()), str(dati.get("consegna") or ""),
            frozenset(dati.get("impronte_allegati") or ()), bool(dati.get("notifica_l53")),
        )
    return EsitoRicevuta(str(dati["riferimento"]), str(dati["impronta"]), str(dati.get("codice") or ""), ricevuta,
                         dict(dati.get("firmatario") or {}), dict(dati.get("revoche") or {}))


def fiducia_ufficiale() -> Fiducia:
    from pct.sdi_pec_trust import trust_certificates

    ca, radice = trust_certificates()
    return Fiducia(ca, radice)


def revoche_ufficiali(fiducia: Fiducia) -> list[x509.CertificateRevocationList]:
    """CRL pubblicate da AgID CA1 e dalla radice Actalis, con firma e periodo di validità controllati."""
    from pct.sdi_pec_trust import revocation_bundle

    pem, _evidenze = revocation_bundle(fiducia.ca_pem, fiducia.radice_pem, datetime.now(timezone.utc))
    blocchi = [b"-----BEGIN X509 CRL-----" + parte for parte in pem.split(b"-----BEGIN X509 CRL-----")[1:]]
    return [x509.load_pem_x509_crl(blocco) for blocco in blocchi]


def _normale(indirizzo: str) -> str:
    return str(indirizzo or "").strip().strip("<>").casefold()


def _descrivi(certificato: x509.Certificate) -> dict:
    return {
        "soggetto": certificato.subject.rfc4514_string(),
        "emittente": certificato.issuer.rfc4514_string(),
        "seriale": format(certificato.serial_number, "x"),
        "sha256": certificato.fingerprint(hashes.SHA256()).hex(),
        "valido_dal": certificato.not_valid_before_utc.isoformat(),
        "valido_al": certificato.not_valid_after_utc.isoformat(),
    }


def _revocato(crls: list[x509.CertificateRevocationList], certificato: x509.Certificate,
              emittente: x509.Certificate, istante: datetime) -> tuple[bool, dict]:
    lista = [c for c in crls if c.issuer == emittente.subject]
    if not lista:
        raise PecTrustError("revoche_non_verificabili", "CRL dell'emittente non disponibile.", retryable=True)
    for crl in lista:
        if not crl.is_signature_valid(emittente.public_key()):
            raise PecTrustError("revoche_non_verificabili", "CRL non firmata dall'emittente.", retryable=True)
    crl = max(lista, key=lambda c: c.last_update_utc)
    voce = crl.get_revoked_certificate_by_serial_number(certificato.serial_number)
    descrizione = {"emittente": emittente.subject.rfc4514_string(),
                   "aggiornata_il": crl.last_update_utc.isoformat(),
                   "prossima": crl.next_update_utc.isoformat() if crl.next_update_utc else "",
                   "sha256": hashlib.sha256(crl.public_bytes(serialization.Encoding.DER)).hexdigest()}
    if voce is None:
        return False, {**descrizione, "esito": "non revocato"}
    try:
        motivo = voce.extensions.get_extension_for_class(x509.CRLReason).value.reason
    except x509.ExtensionNotFound:
        motivo = x509.ReasonFlags.unspecified
    descrizione.update({"esito": "revocato", "revocato_il": voce.revocation_date_utc.isoformat(), "motivo": motivo.value})
    revocato = voce.revocation_date_utc <= istante or motivo not in _REVOCHE_SENZA_COMPROMISSIONE
    return revocato, descrizione


def _versioni_ca(raw: bytes, ca: x509.Certificate, radice: x509.Certificate) -> list[x509.Certificate]:
    """La CA fissata e le sue versioni precedenti incluse nella firma della ricevuta.

    AgID ha rinnovato il certificato «AgID CA1» con la stessa chiave (versione fissata: dal 20/02/2025); le ricevute
    firmate prima portano nella busta il certificato della CA allora in vigore. Si accetta solo un certificato con lo
    stesso soggetto e la **stessa chiave pubblica** della CA fissata, emesso e firmato dalla radice: è la stessa CA
    dei gestori PEC in un periodo di validità diverso, non una CA nuova.
    """
    import warnings
    from email import policy as _policy
    from email.parser import BytesParser as _Parser

    from cryptography.hazmat.primitives.serialization import pkcs7

    versioni = [ca]
    chiave = ca.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    try:
        messaggio = _Parser(policy=_policy.compat32).parsebytes(raw)
        firme = [p.get_payload(decode=True) for p in messaggio.walk()
                 if p.get_content_type() in {"application/pkcs7-signature", "application/x-pkcs7-signature"}]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            inclusi = [c for dati in firme if dati for c in pkcs7.load_der_pkcs7_certificates(dati)]
    except Exception:
        return versioni
    for certificato in inclusi:
        stessa = (certificato.subject == ca.subject and certificato.issuer == radice.subject
                  and certificato.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo) == chiave)
        if not stessa or any(v.serial_number == certificato.serial_number for v in versioni):
            continue
        try:
            certificato.verify_directly_issued_by(radice)
        except Exception:
            continue
        versioni.append(certificato)
    return versioni


def _catena_valida(executable: str, cartella: Path, firmatario: Path, versioni: list[x509.Certificate],
                   fiducia: Fiducia, istante: datetime) -> bool:
    ca_path, root_path = cartella / "ca.pem", cartella / "radice.pem"
    ca_path.write_bytes(b"".join(v.public_bytes(serialization.Encoding.PEM) for v in versioni))
    root_path.write_bytes(fiducia.radice_pem)
    esito = subprocess.run(
        [executable, "verify", "-purpose", "smimesign", "-no-CApath", "-no-CAstore",
         "-CAfile", str(root_path), "-untrusted", str(ca_path), "-attime", str(int(istante.timestamp())), str(firmatario)],
        capture_output=True, timeout=12, check=False,
    )
    return esito.returncode == 0


def verifica_ricevuta_gestore(raw: bytes, *, riferimento: str, casella_studio: str,
                              fiducia: Fiducia | None = None, revoche: Revoche | None = None) -> EsitoRicevuta:
    """Verifica una ricevuta PEC; non solleva mai: l'esito porta il codice del controllo non superato."""
    impronta = hashlib.sha256(raw or b"").hexdigest()

    def esito(codice: str, **altro) -> EsitoRicevuta:
        return EsitoRicevuta(riferimento, impronta, codice, **altro)

    if tipo_eml_storico(raw) != "ricevuta":
        return esito("non_ricevuta")
    casella = _normale(casella_studio)
    if not casella:
        return esito("casella_non_configurata")
    executable = shutil.which("openssl")
    if not executable:
        return esito("verificatore_assente")
    try:
        fiducia = fiducia or fiducia_ufficiale()
        ca = x509.load_pem_x509_certificate(fiducia.ca_pem)
        radice = x509.load_pem_x509_certificate(fiducia.radice_pem)
    except (PecTrustError, ValueError, OSError):
        return esito("fiducia_non_disponibile")
    with TemporaryDirectory(prefix="iusentra-ricevuta-pec-") as directory:
        cartella = Path(directory)
        eml, contenuto, firmatario = cartella / "ricevuta.eml", cartella / "contenuto.mime", cartella / "firmatario.pem"
        eml.write_bytes(raw)
        try:
            estrai_contenuto_cms(executable, eml, contenuto, firmatario)
        except (PecTrustError, subprocess.TimeoutExpired, OSError):
            return esito("firma_non_valida")
        try:
            certificati = x509.load_pem_x509_certificates(firmatario.read_bytes())
        except (ValueError, OSError):
            return esito("firmatario_non_univoco")
        if len(certificati) != 1:
            return esito("firmatario_non_univoco")
        certificato = certificati[0]
        descrizione = _descrivi(certificato)
        try:
            ricevuta = leggi_daticert_firmato(contenuto.read_bytes())
        except ValueError as exc:
            testo = str(exc)
            codice = ("daticert_assente" if "non univoci" in testo
                      else "consegna_non_completa" if "completa" in testo or "originale" in testo
                      else "daticert_non_valido")
            return esito(codice, firmatario=descrizione)
        except Exception:  # XML malformato o pericoloso (defusedxml)
            return esito("daticert_non_valido", firmatario=descrizione)
        # Il firmatario deve essere emesso direttamente dalla CA AgID dei gestori PEC, non da altre CA della radice.
        try:
            certificato.verify_directly_issued_by(ca)
        except Exception:  # firma del certificato non della CA, emittente diverso, algoritmo non ammesso
            return esito("gestore_non_riconosciuto", firmatario=descrizione)
        versioni = _versioni_ca(raw, ca, radice)
        if not _catena_valida(executable, cartella, firmatario, versioni, fiducia, ricevuta.data):
            return esito("catena_non_valida", firmatario=descrizione)
        # La versione della CA in vigore all'istante della ricevuta è quella da controllare nelle revoche.
        in_vigore = [v for v in versioni if v.not_valid_before_utc <= ricevuta.data <= v.not_valid_after_utc]
    try:
        crls = list((revoche or revoche_ufficiali)(fiducia))
        revocato_firmatario, revoca_firmatario = _revocato(crls, certificato, ca, ricevuta.data)
        esiti_ca = [_revocato(crls, v, radice, ricevuta.data) for v in in_vigore]
        revocata_ca = not esiti_ca or all(revocata for revocata, _ in esiti_ca)
        revoca_ca = [{**d, "seriale": format(v.serial_number, "x")} for v, (_, d) in zip(in_vigore, esiti_ca)]
    except (PecTrustError, ValueError, OSError):
        return esito("revoche_non_verificabili", firmatario=descrizione)
    stato_revoche = {"firmatario": revoca_firmatario, "ca": revoca_ca,
                     "certificato_scaduto_alla_verifica": certificato.not_valid_after_utc < datetime.now(timezone.utc)}
    if revocato_firmatario or revocata_ca:
        return esito("certificato_revocato", firmatario=descrizione, revoche=stato_revoche)
    if {_normale(m) for m in ricevuta.mittenti} != {casella}:
        return esito("mittente_diverso", ricevuta=None, firmatario=descrizione, revoche=stato_revoche)
    return EsitoRicevuta(riferimento, impronta, "", ricevuta, descrizione, stato_revoche)


__all__ = ["EsitoRicevuta", "Fiducia", "LIVELLO", "MOTIVI", "NORMA", "RIPETIBILI", "VERSIONE",
           "esito_da_dizionario", "fiducia_ufficiale", "originale_certificato", "revoche_ufficiali", "verifica_ricevuta_gestore"]
