"""La prova di una notificazione PEC eseguita fuori dal registro, dalle ricevute verificate del gestore.

Una notificazione in proprio a mezzo PEC (art. 3-bis L. 53/1994) si perfeziona per il destinatario con la
ricevuta di avvenuta consegna (comma 3); le ricevute sono prova solo se firmate dal gestore e con i dati di
certificazione corrispondenti al messaggio spedito (D.P.R. 68/2005, artt. 6 e 9). Qui si decide, per ogni
spedizione, se le ricevute già verificate una per una (``pct/ricevute_pec_gestore.py``) provano la notifica
dell'atto elencato nella relata, oppure perché non la provano.

Regole, tutte obbligatorie (fail-closed):

1. **messaggio inviato**: il messaggio spedito dallo studio (cartella Inviati della casella o sua copia tra i
   documenti) con Message-ID uguale al ``msgid`` certificato, mittente la casella dello studio, oggetto di
   notificazione ex L. 53/1994 (comma 4), senza copie nascoste;
2. **accettazione**: una sola ricevuta di accettazione verificata per quel ``msgid``, con gli stessi
   destinatari del messaggio;
3. **consegna**: per **ogni** destinatario una ricevuta di avvenuta consegna completa verificata, della stessa
   spedizione (identificativo del gestore), non anteriore all'accettazione e con gli stessi allegati inviati;
4. **relata**: il file della relata è tra gli allegati consegnati, è firmato digitalmente (firma integra) dallo
   stesso avvocato indicato nella relata, e gli indirizzi dei destinatari della relata sono quelli consegnati;
5. **atto**: l'atto notificato è quello elencato nella relata («File: ...»), allegato al messaggio, ed è nel
   fascicolo con la **stessa impronta** SHA-256 del file consegnato.

Modulo puro: riceve contenuti già letti e restituisce la prova o il dubbio con il motivo. Non scrive nulla.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import timedelta
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses
from typing import Callable, Iterable, Mapping
from zoneinfo import ZoneInfo

from pct.notifica_atto_l53 import NORMA as NORMA_L53
from pct.notifica_atto_l53 import chiave_nome, e_notificazione_l53, leggi_relata
from pct.destinatari_notifica_pa import ruolo_destinatario, voci_relata
from pct.ricevute_pec_gestore import EsitoRicevuta

_PARSER = BytesParser(policy=policy.default)
_ROMA = ZoneInfo("Europe/Rome")
_INDIRIZZO_RELATA = re.compile(r"indirizzo\s+(?:pec|di\s+posta\s+elettronica\s+certificata)\s*:?\s*([^\s;,<>()]+@[^\s;,<>()]+)", re.IGNORECASE)
_SOTTOSCRITTO = re.compile(r"\bsottoscritt[oa]\b.{0,160}?\bC\.?\s*F\.?\s*[:.]?\s*([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])", re.IGNORECASE | re.DOTALL)
_ATTESTAZIONE_COPIA = re.compile(r"\bconforme\s+(?:all[ao']\s*)?(?:copia|originale|atto)\b", re.IGNORECASE)


@dataclass(frozen=True)
class LetturaRelata:
    """Il file della relata letto: testo e firma (``pct/firma.analizza_firma_documento``)."""

    testo: str
    firma_integra: bool
    codice_fiscale_firmatario: str = ""


LettoreRelata = Callable[[bytes, str], LetturaRelata]


@dataclass(frozen=True)
class Invio:
    """Un messaggio inviato dallo studio: dalla cartella Inviati o copia tra i documenti del fascicolo."""

    riferimento: str
    raw: bytes
    fonte: str = "documento"  # «documento» o «casella»


@dataclass
class EsitoSpedizione:
    msgid: str
    provata: bool = False
    motivo: str = ""
    identificativo: str = ""
    invio: dict = field(default_factory=dict)
    accettazione: dict = field(default_factory=dict)
    consegne: list[dict] = field(default_factory=list)
    relata: dict = field(default_factory=dict)
    atti: list[dict] = field(default_factory=list)  # {"documento_id", "file", "titolo", "sha256", "copia_attestata"}
    destinatari: list[str] = field(default_factory=list)
    data_consegna: str = ""  # giorno (Europe/Rome) comune a tutte le consegne

    def come_dizionario(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def _id(valore: object) -> str:
    return re.sub(r"[\s<>]+", "", str(valore or "")).casefold()


def _indirizzi(valori: Iterable[str]) -> frozenset[str]:
    return frozenset(indirizzo.strip().casefold() for _, indirizzo in getaddresses(list(valori))
                     if re.fullmatch(r"[^@\s<>]+@[^@\s<>]+", indirizzo.strip()))


def _allegati(messaggio: EmailMessage) -> list[tuple[str, bytes]]:
    out = []
    for parte in messaggio.iter_attachments():
        if parte.is_multipart():
            continue
        data = parte.get_payload(decode=True)
        if data:
            out.append((str(parte.get_filename() or ""), data))
    return out


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _giorno_roma(istante) -> str:
    """Giorno in cui la consegna perfeziona la notifica per il destinatario: dopo le 21 vale alle 7 del giorno
    successivo (art. 147, terzo comma, c.p.c., richiamato dall'art. 3-bis, comma 3, L. 53/1994)."""
    locale = istante.astimezone(_ROMA)
    giorno = locale.date() + timedelta(days=1) if locale.hour >= 21 else locale.date()
    return giorno.isoformat()


def _blocco_destinatari(testo: str) -> str:
    """Il passo «HO NOTIFICATO A ... I seguenti atti» della relata (art. 3-bis, comma 5, lett. c-d): non la
    dichiarazione finale sull'indirizzo del notificante."""
    inizio = re.search(r"\bHO\s+NOTIFICATO\s+A\b", testo, re.IGNORECASE)
    if not inizio:
        return ""
    fine = re.search(r"\bI\s+seguenti\s+atti\s*:|\bDICHIARO\b", testo[inizio.end():], re.IGNORECASE)
    return testo[inizio.end():inizio.end() + fine.start()] if fine else ""


def _blocco_atto(testo: str, nome_file: str) -> str:
    """Il passo della relata che descrive l'atto («A) - ... (File: x) Natura ... Attesto ...»)."""
    inizio = testo.find(nome_file)
    if inizio < 0:
        return ""
    seguito = testo[inizio:inizio + 1200]
    fine = re.search(r"(?m)^\s*[A-Z]\)\s*-|\bDICHIARO\b", seguito[len(nome_file):])
    return seguito[:len(nome_file) + fine.start()] if fine else seguito


def prova_spedizioni(
    ricevute: Iterable[EsitoRicevuta],
    invii: Iterable[Invio],
    *,
    casella_studio: str,
    documenti: Mapping[str, str],
    leggi_relata_file: LettoreRelata,
    originali: Mapping[str, Invio] | None = None,
) -> list[EsitoSpedizione]:
    """Una prova (o un dubbio motivato) per ogni spedizione L. 53/1994 di cui ci sono ricevute verificate.

    ``documenti``: documento del fascicolo → impronta SHA-256 del contenuto (dal registro delle letture).
    ``originali``: identificativo del messaggio → messaggio originale contenuto (``postacert.eml``) in una ricevuta
    di avvenuta consegna completa verificata. Vale come prova del contenuto spedito quando manca la copia in
    Inviati: la ricevuta completa è firmata dal gestore e lo contiene (D.P.R. 68/2005, art. 6, comma 3).
    """
    casella = casella_studio.strip().casefold()
    verificate = [r for r in ricevute if r.verificata and r.ricevuta is not None]
    per_msgid: dict[str, list[EsitoRicevuta]] = {}
    for esito in verificate:
        per_msgid.setdefault(_id(esito.ricevuta.message_id), []).append(esito)
    invii_per_msgid: dict[str, list[tuple[Invio, EmailMessage]]] = {}
    for invio in invii:
        try:
            messaggio = _PARSER.parsebytes(invio.raw)
        except Exception:
            continue
        invii_per_msgid.setdefault(_id(messaggio["Message-ID"]), []).append((invio, messaggio))
    per_impronta: dict[str, list[str]] = {}
    for documento, impronta in documenti.items():
        if impronta:
            per_impronta.setdefault(str(impronta).lower(), []).append(documento)
    esiti = []
    for msgid, gruppo in sorted(per_msgid.items()):
        if not msgid or not any(r.ricevuta.notifica_l53 for r in gruppo):
            continue  # una ricevuta senza oggetto di notificazione non è una notifica (art. 3-bis, c. 4)
        candidati = invii_per_msgid.get(msgid, [])
        originale = (originali or {}).get(msgid)
        if originale is not None:
            try:
                candidati = candidati + [(originale, _PARSER.parsebytes(originale.raw))]
            except Exception:
                pass
        esiti.append(_prova(msgid, gruppo, candidati, casella, per_impronta, leggi_relata_file))
    return esiti


def _prova(msgid, gruppo, candidati, casella, per_impronta, leggi_relata_file) -> EsitoSpedizione:
    esito = EsitoSpedizione(msgid=msgid)

    def dubbio(motivo: str) -> EsitoSpedizione:
        esito.motivo = motivo
        return esito

    # 1. Il messaggio inviato dallo studio.
    propri = [(i, m) for i, m in candidati if _indirizzi(m.get_all("From", [])) == {casella}]
    # Prima la copia di Inviati o dei documenti; senza, l'originale certificato dentro la ricevuta completa.
    distinti = {_sha(i.raw): (i, m) for i, m in propri if i.fonte != "ricevuta_completa"} or \
        {_sha(i.raw): (i, m) for i, m in propri if i.fonte == "ricevuta_completa"}
    if not distinti:
        return dubbio("Manca il messaggio inviato dallo studio (cartella Inviati, copia tra i documenti o originale "
                      "nella ricevuta completa del gestore) con lo stesso identificativo delle ricevute.")
    # Copie identiche della stessa spedizione contano una volta; contenuti diversi non sono univoci.
    if len({_sha(b"".join(d for _, d in _allegati(m))) for i, m in distinti.values()}) != 1:
        return dubbio("Il messaggio inviato con questo identificativo non è univoco: allegati diversi.")
    invio, messaggio = sorted(distinti.values(), key=lambda v: (v[0].fonte != "casella", v[0].riferimento))[0]
    if not e_notificazione_l53(str(messaggio["Subject"] or "")):
        return dubbio("Il messaggio inviato non ha l'oggetto della notificazione ai sensi della L. 53/1994 (art. 3-bis, comma 4).")
    if messaggio.get_all("Bcc"):
        return dubbio("Il messaggio inviato ha destinatari in copia nascosta: la notifica non è ricostruibile.")
    indirizzati = _indirizzi(messaggio.get_all("To", []) + messaggio.get_all("Cc", []))
    allegati = _allegati(messaggio)
    impronte = frozenset(_sha(d) for _, d in allegati)
    esito.invio = {"riferimento": invio.riferimento, "fonte": invio.fonte, "sha256": _sha(invio.raw),
                   "message_id": str(messaggio["Message-ID"] or "").strip() or f"<{msgid}>", "oggetto": " ".join(str(messaggio["Subject"] or "").split()),
                   "destinatari": sorted(indirizzati)}
    # 2. L'accettazione.
    accettazioni = {r.ricevuta.identificativo: r for r in gruppo if r.ricevuta.tipo == "accettazione"}
    if not accettazioni:
        return dubbio("Manca la ricevuta di accettazione verificata del gestore per questa spedizione.")
    if len(accettazioni) != 1:
        return dubbio("Più ricevute di accettazione con identificativi diversi per lo stesso messaggio.")
    rac = next(iter(accettazioni.values()))
    # I destinatari della notifica sono le caselle certificate attestate dal gestore; un indirizzo ordinario in più nel
    # messaggio non riceve ricevuta di consegna e non è notificato: si dichiara, e la relata deve escluderlo.
    destinatari = rac.ricevuta.destinatari
    if not destinatari or not destinatari <= indirizzati:
        return dubbio("I destinatari certificati nell'accettazione non coincidono con quelli del messaggio inviato.")
    esito.invio["destinatari_non_certificati"] = sorted(indirizzati - destinatari)
    esito.identificativo = rac.ricevuta.identificativo
    esito.accettazione = {"riferimento": rac.riferimento, "sha256": rac.impronta, "data": rac.ricevuta.data.isoformat(),
                          "identificativo": rac.ricevuta.identificativo, "gestore": rac.firmatario.get("soggetto", "")}
    # 3. Una consegna completa per ogni destinatario.
    consegne = []
    for destinatario in sorted(destinatari):
        proprie = {r.impronta: r for r in gruppo if r.ricevuta.tipo == "avvenuta-consegna"
                   and r.ricevuta.consegna == destinatario}
        valide = [r for r in proprie.values() if r.ricevuta.identificativo == rac.ricevuta.identificativo
                  and r.ricevuta.data >= rac.ricevuta.data and r.ricevuta.destinatari == destinatari]
        if not valide:
            return dubbio(f"Manca la ricevuta di avvenuta consegna verificata per {destinatario}.")
        if len(valide) != 1:
            return dubbio(f"Più ricevute di avvenuta consegna diverse per {destinatario}: consegna non univoca.")
        rdac = valide[0]
        if rdac.ricevuta.impronte != impronte:
            return dubbio(f"La ricevuta completa di consegna a {destinatario} non contiene gli stessi allegati inviati.")
        consegne.append({"destinatario": destinatario, "riferimento": rdac.riferimento, "sha256": rdac.impronta,
                         "data": rdac.ricevuta.data.isoformat(), "gestore": rdac.firmatario.get("soggetto", "")})
    giorni = {_giorno_roma(r.ricevuta.data) for r in gruppo if r.ricevuta.tipo == "avvenuta-consegna"
              and any(c["sha256"] == r.impronta for c in consegne)}
    # 4. La relata, firmata e con gli stessi destinatari.
    relate = [(nome, data) for nome, data in allegati if "relata" in nome.casefold()]
    if len(relate) != 1:
        return dubbio("Il messaggio inviato non contiene uno e un solo file di relata di notifica.")
    nome_relata, dati_relata = relate[0]
    try:
        lettura = leggi_relata_file(dati_relata, nome_relata)
    except Exception:
        return dubbio("La relata non è leggibile.")
    sottoscritto = _SOTTOSCRITTO.search(lettura.testo or "")
    if not lettura.firma_integra:
        return dubbio("La relata non è firmata digitalmente o la firma non è integra.")
    if not sottoscritto or sottoscritto.group(1).upper() != str(lettura.codice_fiscale_firmatario or "").upper():
        return dubbio("La relata non è firmata dall'avvocato che la sottoscrive (codice fiscale diverso o assente).")
    indirizzi_relata = frozenset(a.strip(".;,").casefold() for a in _INDIRIZZO_RELATA.findall(_blocco_destinatari(lettura.testo or "")))
    # Ogni casella consegnata deve essere un destinatario della relata. Un destinatario della relata senza casella
    # certificata (indirizzo errato o non PEC: il gestore non lo certifica) non è notificato: la notifica agli altri si
    # perfeziona comunque destinatario per destinatario (art. 3-bis, comma 3), e il mancato recapito si dichiara.
    if not destinatari <= indirizzi_relata or not indirizzi_relata <= indirizzati:
        return dubbio("Gli indirizzi dei destinatari nella relata non coincidono con quelli della consegna.")
    # Il ruolo di ciascun destinatario (Avvocatura, difensore, amministrazione) decide gli effetti verso la P.A.
    voci = voci_relata(_blocco_destinatari(lettura.testo or ""))
    for consegna in consegne:
        voce = voci.get(consegna["destinatario"], "")
        consegna["ruolo"] = ruolo_destinatario(consegna["destinatario"], voce)
        consegna["voce_relata"] = voce[:300]
    atti_relata, nomi_destinatari = leggi_relata(lettura.testo or "")
    esito.relata = {"file": nome_relata, "sha256": _sha(dati_relata), "codice_fiscale": sottoscritto.group(1).upper(),
                    "documento_id": next(iter(per_impronta.get(_sha(dati_relata), [])), ""), "destinatari": nomi_destinatari,
                    "destinatari_non_consegnati": sorted(indirizzi_relata - destinatari)}
    # 5. Gli atti della relata, nel fascicolo con la stessa impronta del file consegnato.
    per_nome = {}
    for nome, data in allegati:
        per_nome.setdefault(chiave_nome(nome), []).append(data)
    atti = []
    for voce in atti_relata:
        file_consegnati = {_sha(d) for d in per_nome.get(chiave_nome(voce["file"]), [])}
        if len(file_consegnati) != 1:
            continue
        impronta = next(iter(file_consegnati))
        blocco = _blocco_atto(lettura.testo or "", voce["file"])
        for documento in per_impronta.get(impronta, []):
            atti.append({"documento_id": documento, "file": voce["file"], "titolo": voce["titolo"], "sha256": impronta,
                         "copia_attestata": bool(re.search(r"\bcopia\b", blocco, re.IGNORECASE) and _ATTESTAZIONE_COPIA.search(blocco))})
    if not atti:
        return dubbio("Nessun atto elencato nella relata è nel fascicolo con la stessa impronta del file consegnato.")
    esito.atti, esito.consegne, esito.destinatari = atti, consegne, sorted(destinatari)
    if len(giorni) != 1:
        return dubbio("Le consegne ai destinatari sono avvenute in giorni diversi: la decorrenza non è univoca.")
    esito.data_consegna = next(iter(giorni))
    esito.provata = True
    return esito


NORMA = f"{NORMA_L53}, commi 3-5; D.P.R. 68/2005, artt. 6 e 9"

__all__ = ["EsitoSpedizione", "Invio", "LetturaRelata", "NORMA", "prova_spedizioni"]
