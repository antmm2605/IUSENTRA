"""Correla gli EML storici del fascicolo per riscontrare un invio ex L. 53/1994.

Il riscontro attesta la corrispondenza documentale e la catena alla data
indicata nel daticert. L'esito legale richiede ancora la verifica delle
revoche storiche e della relata, dei destinatari e del domicilio digitale.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from cryptography import x509
from defusedxml import ElementTree

from pct.pec_contenuto_firmato import estrai_contenuto_cms
from pct.pec_oggetti_ufficiali import istante_daticert
from pct.sdi_pec_trust import PecTrustError, trust_certificates

_PARSER = BytesParser(policy=policy.default)
_NOTIFICA = re.compile(r"\bnotificazione ai sensi della legge n\.?\s*53\b.*\b1994\b", re.I)
_ROME = ZoneInfo("Europe/Rome")
_MASSIMO_EML = 32 * 1024 * 1024


def _indirizzi(valori) -> frozenset[str]:
    return frozenset(indirizzo.casefold() for _, indirizzo in getaddresses(valori)
                     if re.fullmatch(r"[^@\s<>]+@[^@\s<>]+", indirizzo))


def _id(valore) -> str:
    return str(valore or "").strip().strip("<>")


def _impronte(messaggio: EmailMessage) -> frozenset[str]:
    return frozenset(hashlib.sha256(data).hexdigest() for parte in messaggio.iter_attachments()
                     if not parte.is_multipart() and (data := parte.get_payload(decode=True)))


@dataclass(frozen=True)
class Ricevuta:
    tipo: str
    identificativo: str
    message_id: str
    data: datetime
    mittenti: frozenset[str]
    destinatari: frozenset[str]
    consegna: str
    impronte: frozenset[str]
    notifica_l53: bool = False


def leggi_daticert_firmato(contenuto: bytes) -> Ricevuta:
    """Interpreta solo il daticert al primo livello del contenuto verificato."""
    mime = _PARSER.parsebytes(contenuto)
    parti = tuple(mime.iter_parts())
    xml = [p for p in parti if (p.get_filename() or "").casefold() == "daticert.xml"]
    if len(xml) != 1:
        raise ValueError("Dati di certificazione non univoci.")
    raw = xml[0].get_payload(decode=True) or b""
    if len(raw) > 128 * 1024:
        raise ValueError("Dati di certificazione troppo grandi.")
    root = ElementTree.fromstring(raw, forbid_dtd=True)
    tipo = root.get("tipo", "")
    if root.tag != "postacert" or root.get("errore") != "nessuno" or tipo not in {"accettazione", "avvenuta-consegna"}:
        raise ValueError("La ricevuta non attesta accettazione o consegna.")
    mittenti = _indirizzi([root.findtext("./intestazione/mittente", "")])
    destinatari = _indirizzi([n.text or "" for n in root.findall("./intestazione/destinatari")
                             if n.get("tipo") == "certificato"])
    provider_id = _id(root.findtext("./dati/identificativo"))
    message_id = _id(root.findtext("./dati/msgid"))
    data = root.find("./dati/data")
    if data is None or len(mittenti) != 1 or not destinatari or not provider_id or not message_id:
        raise ValueError("Dati di certificazione incompleti.")
    istante = istante_daticert(raw)
    if istante is None:
        raise ValueError("Data, ora e zona del daticert non valide.")
    consegna, impronte = "", frozenset()
    notifica_l53 = bool(_NOTIFICA.search(root.findtext("./intestazione/oggetto", "")))
    if tipo == "avvenuta-consegna":
        recapito = _indirizzi([root.findtext("./dati/consegna", "")])
        formato = root.find("./dati/ricevuta")
        originali = [p for p in parti if p.get_content_type() == "message/rfc822"
                     and (p.get_filename() or "").casefold() == "postacert.eml"]
        if len(recapito) != 1 or not recapito <= destinatari or formato is None or formato.get("tipo") != "completa" or len(originali) != 1:
            raise ValueError("Serve la ricevuta completa del destinatario certificato.")
        incapsulati = originali[0].get_payload()
        if not isinstance(incapsulati, list) or len(incapsulati) != 1:
            raise ValueError("Messaggio originale non univoco.")
        originale = incapsulati[0]
        if _id(originale["Message-ID"]) not in {provider_id, message_id} or _indirizzi(originale.get_all("From", [])) != mittenti:
            raise ValueError("Il messaggio incapsulato non coincide con il daticert.")
        consegna, impronte = next(iter(recapito)), _impronte(originale)
        notifica_l53 = notifica_l53 and bool(_NOTIFICA.search(str(originale["Subject"] or "")))
    return Ricevuta(tipo, provider_id, message_id, istante, mittenti, destinatari, consegna, impronte, notifica_l53)


def verifica_ricevuta_storica(raw: bytes) -> Ricevuta:
    """Verifica il firmatario alla data dichiarata, senza attestare la revoca storica."""
    executable = shutil.which("openssl")
    if not executable:
        raise PecTrustError("verifier_unavailable", "Verificatore PEC non disponibile.", retryable=True)
    ca, radice = trust_certificates()
    with TemporaryDirectory(prefix="iusentra-pec-storica-") as directory:
        folder = Path(directory)
        eml, content, signer = (folder / nome for nome in ("originale.eml", "contenuto.mime", "firmatario.pem"))
        eml.write_bytes(raw)
        estrai_contenuto_cms(executable, eml, content, signer)
        if len(x509.load_pem_x509_certificates(signer.read_bytes())) != 1:
            raise ValueError("Firmatario della ricevuta non univoco.")
        ricevuta = leggi_daticert_firmato(content.read_bytes())
        ca_path, root_path = folder / "agid.pem", folder / "root.pem"
        ca_path.write_bytes(ca)
        root_path.write_bytes(radice)
        verifica = subprocess.run(
            [executable, "verify", "-purpose", "smimesign", "-no-CApath", "-no-CAstore",
             "-CAfile", str(root_path), "-untrusted", str(ca_path), "-attime", str(int(ricevuta.data.timestamp())), str(signer)],
            capture_output=True, timeout=12, check=False,
        )
        if verifica.returncode:
            raise ValueError("Catena PEC non verificabile alla data della ricevuta.")
        return ricevuta


def riscontra_invio_storico(invio: bytes, ricevute: list[tuple[str, Ricevuta]]) -> dict:
    messaggio = _PARSER.parsebytes(invio)
    if not _NOTIFICA.search(str(messaggio["Subject"] or "")) or messaggio.get_all("Bcc"):
        return {}
    mid = _id(messaggio["Message-ID"])
    mittenti = _indirizzi(messaggio.get_all("From", []))
    destinatari = _indirizzi(messaggio.get_all("To", []) + messaggio.get_all("Cc", []))
    impronte = _impronte(messaggio)
    if not mid or len(mittenti) != 1 or not destinatari or not impronte:
        return {}
    correlate = [(oid, r) for oid, r in ricevute
                 if r.message_id == mid and r.mittenti == mittenti and r.destinatari == destinatari]
    accettazioni = [(oid, r) for oid, r in correlate if r.tipo == "accettazione"]
    if len(accettazioni) != 1:
        return {}
    id_rac, rac = accettazioni[0]
    consegne = [(oid, r) for oid, r in correlate if r.tipo == "avvenuta-consegna"
                and r.identificativo == rac.identificativo and r.data >= rac.data and r.impronte == impronte]
    if len(consegne) != len(destinatari) or {r.consegna for _, r in consegne} != destinatari:
        return {}
    return _descrivi_riscontro(id_rac, rac, consegne, impronte)


def _descrivi_riscontro(id_rac, rac, consegne, impronte) -> dict:
    return {
        "accettazione_id": id_rac,
        "accettazione_data": rac.data.astimezone(_ROME).isoformat(),
        "consegne": [{"documento_id": oid, "data": r.data.astimezone(_ROME).isoformat()} for oid, r in consegne],
        "impronte_allegati": sorted(impronte),
    }


def riscontri_da_ricevute_storiche(ricevute: list[tuple[str, Ricevuta]]) -> dict[str, dict]:
    """Correla le buste firmate quando l'originale è conservato soltanto dentro la RdAC completa."""
    spedizioni: dict[str, list[tuple[str, Ricevuta]]] = {}
    for oid, ricevuta in ricevute:
        if ricevuta.notifica_l53:
            spedizioni.setdefault(ricevuta.identificativo, []).append((oid, ricevuta))
    riscontri = {}
    for spedizione in spedizioni.values():
        accettazioni = [(oid, r) for oid, r in spedizione if r.tipo == "accettazione"]
        if len(accettazioni) != 1:
            continue
        id_rac, rac = accettazioni[0]
        # Un gestore può inserire spazi di formattazione nel proprio daticert.
        # Il confronto si applica solo a ricevute già firmate con lo stesso identificativo PEC.
        message_id = re.sub(r"[ \t\r\n]+", "", rac.message_id)
        consegne = [(oid, r) for oid, r in spedizione if r.tipo == "avvenuta-consegna"
                    and re.sub(r"[ \t\r\n]+", "", r.message_id) == message_id
                    and r.mittenti == rac.mittenti and r.destinatari == rac.destinatari
                    and r.data >= rac.data and r.impronte]
        insiemi_allegati = {r.impronte for _, r in consegne}
        if (not message_id or len(insiemi_allegati) != 1 or len(consegne) != len(rac.destinatari)
                or {r.consegna for _, r in consegne} != rac.destinatari):
            continue
        prova = _descrivi_riscontro(id_rac, rac, consegne, next(iter(insiemi_allegati)))
        riscontri[id_rac] = {**prova, "originale_nella_ricevuta": True}
    return riscontri


def tipo_eml_storico(raw: bytes) -> str:
    """Preselezione economica. Gli header esterni non valgono come prova."""
    if not raw or len(raw) > _MASSIMO_EML:
        return ""
    header = _PARSER.parsebytes(raw[:65536], headersonly=True)
    if header.get_content_type() == "multipart/signed":
        tipo = str(header["X-Ricevuta"] or "").casefold()
        return "ricevuta" if tipo in {"accettazione", "avvenuta-consegna"} else ""
    return "invio" if _NOTIFICA.search(str(header["Subject"] or "")) else ""
