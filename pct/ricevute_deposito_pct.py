"""Ricevute del deposito telematico civile: riconoscimento e collegamento rigoroso al deposito.

Base normativa:
- d.P.R. 68/2005 artt. 6 e 8 e regole tecniche del d.m. 2/11/2005 (ricevute del gestore PEC:
  accettazione, avviso di non accettazione, avvenuta consegna, avviso di mancata consegna; ogni
  ricevuta porta nell'intestazione ``X-Riferimento-Message-ID`` il Message-ID del messaggio a cui
  si riferisce);
- D.M. 44/2011 artt. 13-14 e Specifiche tecniche DGSIA ex art. 34 (provvedimento 7/8/2024, in vigore
  dal 30/09/2024, art. 17 commi 6-11): dopo le due ricevute PEC il gestore dei servizi telematici
  invia l'esito dei controlli automatici (anomalie WARN, ERROR, FATAL; con FATAL il deposito e'
  rifiutato) e l'esito dell'intervento della cancelleria (accettazione o rifiuto); il tracciato
  ``EsitoAtto.xml`` (DTD 2009-02-17) riporta in ``IdMsgMitt`` l'identificativo del messaggio del
  depositante, ``Eccezione.xml`` in ``IdMsgSMTP``;
- art. 196-sexies disp. att. c.p.c.: il deposito si ha per avvenuto alla ricevuta di avvenuta
  consegna; per questo uno stato «Consegnato» deve poggiare su una RdAC di QUEL deposito.

Regola fail-closed: una PEC entra nel deposito solo se porta un suo identificativo (Message-ID del
messaggio di deposito, IdBusta, RefID, codice del deposito nell'oggetto). Numero di ruolo, data,
nome dell'atto o parole generiche dell'oggetto non bastano mai; una PEC non collegata non cambia
nessuno stato.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from pct.pec_oggetti_ufficiali import classifica_ricevuta_pec

ROME_TZ = ZoneInfo("Europe/Rome")

# Tipi canonici delle quattro PEC di ritorno (e delle loro varianti negative).
ACCETTAZIONE = "accettazione"
NON_ACCETTAZIONE = "non_accettazione"
CONSEGNA = "avvenuta_consegna"
MANCATA_CONSEGNA = "mancata_consegna"
PREAVVISO_MANCATA_CONSEGNA = "preavviso_mancata_consegna"
ESITO_CONTROLLI = "esito_controlli"
ESITO_CANCELLERIA = "esito_cancelleria"

FASE = {
    ACCETTAZIONE: 1, NON_ACCETTAZIONE: 1,
    CONSEGNA: 2, MANCATA_CONSEGNA: 2, PREAVVISO_MANCATA_CONSEGNA: 2,
    ESITO_CONTROLLI: 3, ESITO_CANCELLERIA: 4,
}
ETICHETTA = {
    ACCETTAZIONE: "ricevuta di accettazione",
    NON_ACCETTAZIONE: "avviso di non accettazione",
    CONSEGNA: "ricevuta di avvenuta consegna",
    MANCATA_CONSEGNA: "avviso di mancata consegna",
    PREAVVISO_MANCATA_CONSEGNA: "preavviso di mancata consegna",
    ESITO_CONTROLLI: "esito dei controlli automatici",
    ESITO_CANCELLERIA: "esito dell'intervento della cancelleria",
}
_PEC_A_TIPO = {
    "accettazione": ACCETTAZIONE,
    "non_accettazione": NON_ACCETTAZIONE,
    "avvenuta_consegna": CONSEGNA,
    "mancata_consegna": MANCATA_CONSEGNA,
    "rilevazione_virus": MANCATA_CONSEGNA,
    "preavviso_mancata_consegna": PREAVVISO_MANCATA_CONSEGNA,
}

STATI_FINALI = frozenset({"ACCETTATO_CANCELLERIA", "RIFIUTATO_CANCELLERIA", "ERRORE"})

_POSTA_CERTIFICATA = re.compile(r"^\s*posta\s+certificata\s*:\s*", re.I)
_ESITO_CONTROLLI_OGG = re.compile(r"^\s*esito\s+(?:dei\s+)?controlli\s+automatici\b", re.I)
_ESITO_CANCELLERIA_OGG = re.compile(
    r"^\s*(?:accettazione\s+deposito\b|esito\s+intervento\s+(?:della\s+)?(?:cancelleria|ufficio|segreteria)\b|"
    r"rifiuto\s+(?:del\s+)?deposito\b)",
    re.I,
)
_RIFIUTO = re.compile(
    r"\brifiut(?:o|ato|ata)\b|\bnon\s+(?:[eè]\s+stat[oa]\s+)?accettat[oa]\b|\bnon\s+accettazione\s+(?:del\s+)?deposito\b",
    re.I,
)
_ACCETTATO = re.compile(r"\baccettazione\s+deposito\b|\baccettat[oa]\b", re.I)
_FATAL = re.compile(r"\bFATAL\b|\berrore\s+fatale\b", re.I)
_ERROR = re.compile(r"\bERROR\b")
_WARN = re.compile(r"\bWARN(?:ING)?\b")
_OK = re.compile(r"controlli\s+terminati\s+con\s+successo|esito\s+positivo\s+dei\s+controlli", re.I)

_MSGID_TAG = re.compile(r"<\s*(IdMsgMitt|IdMsgSMTP)\s*>\s*(.*?)\s*<\s*/\s*\1\s*>", re.I | re.S)
_IDBUSTA = (
    re.compile(r"<\s*IdBusta\s*>\s*([A-Za-z0-9._/-]{4,64})\s*<", re.I),
    re.compile(r"\bID\s*BUSTA\s*[:=]\s*([A-Za-z0-9._/-]{4,64})", re.I),
)
_REFID = (
    re.compile(r"\[(RefID[_-][A-Za-z0-9._-]{3,120})\]", re.I),
    re.compile(r"<\s*RefId\s*>\s*([A-Za-z0-9._-]{3,120})\s*<", re.I),
)
_MESSAGGIO_MSGID = re.compile(r"Message-ID(?:\s+deposito)?\s*:\s*<?([^\s<>]+@[^\s<>]+)>?", re.I)
_MARCATORE = re.compile(r"PEC_DEPOSIT_CORRELATION:(idbusta|refid|message-id):([^\s;,]+)", re.I)


def normalizza_message_id(valore: Any) -> str:
    """Message-ID senza parentesi angolari, parte locale intatta e dominio in minuscolo."""
    testo = html.unescape(str(valore or "")).strip().strip("<>").strip()
    if "@" not in testo or any(c.isspace() for c in testo):
        return ""
    locale, _, dominio = testo.rpartition("@")
    return f"{locale}@{dominio.casefold()}"


# ---------------------------------------------------------------------------
# Classificazione
# ---------------------------------------------------------------------------

def classifica(oggetto: Any, *, x_ricevuta: Any = "", testo: Any = "") -> tuple[str, str]:
    """(tipo, esito) della PEC; ("", "") se non e' una delle PEC di ritorno del deposito.

    ``esito`` vale OK/WARN/ERROR/FATAL per i controlli automatici, ACCETTATO/RIFIUTATO per la
    cancelleria, "" se il messaggio non lo dice in modo esplicito (mai un esito per difetto)."""
    ogg = " ".join(str(oggetto or "").split())
    x_ric = str(x_ricevuta or "").strip()
    busta_ministero = bool(_POSTA_CERTIFICATA.match(ogg)) or x_ric.casefold().replace("_", "-") == "posta-certificata"
    if not busta_ministero:
        etichetta, _fonte = classifica_ricevuta_pec(ogg, x_ricevuta=x_ric, usa_corpo=False)
        tipo = _PEC_A_TIPO.get(etichetta, "")
        if tipo:
            return tipo, ""
        if etichetta:
            return "", ""  # presa in carico, anomalia: non sono ricevute del deposito
    base = _POSTA_CERTIFICATA.sub("", ogg)
    corpo = str(testo or "")
    if _ESITO_CONTROLLI_OGG.match(base):
        return ESITO_CONTROLLI, _livello_controlli(f"{base}\n{corpo}")
    if _ESITO_CANCELLERIA_OGG.match(base):
        return ESITO_CANCELLERIA, _esito_cancelleria(base, corpo)
    return "", ""


def _livello_controlli(testo: str) -> str:
    """Anomalia piu' grave dichiarata (art. 17 c. 8 Specifiche DGSIA); "" se non dichiarata."""
    if _FATAL.search(testo):
        return "FATAL"
    if _ERROR.search(testo):
        return "ERROR"
    if _WARN.search(testo):
        return "WARN"
    if _OK.search(testo):
        return "OK"
    return ""


def _esito_cancelleria(oggetto_base: str, corpo: str) -> str:
    testo = f"{oggetto_base}\n{corpo}"
    if _RIFIUTO.search(testo):
        return "RIFIUTATO"
    if re.match(r"^\s*accettazione\s+deposito\b", oggetto_base, re.I) or _ACCETTATO.search(corpo):
        return "ACCETTATO"
    return ""


# ---------------------------------------------------------------------------
# Identificativi
# ---------------------------------------------------------------------------

def identificativi_ricevuta(ricevuta: dict) -> dict[str, set[str]]:
    """Identificativi del deposito portati dalla PEC (intestazioni, oggetto, testo, XML)."""
    testo = html.unescape(str(ricevuta.get("testo") or ""))
    oggetto = str(ricevuta.get("subject") or "")
    msgids = {normalizza_message_id(ricevuta.get("riferimento_message_id"))}
    msgids.update(normalizza_message_id(m.group(2)) for m in _MSGID_TAG.finditer(testo))
    idbusta = {m.group(1) for pat in _IDBUSTA for m in pat.finditer(f"{oggetto}\n{testo}")}
    refid = {m.group(1).casefold() for pat in _REFID for m in pat.finditer(f"{oggetto}\n{testo}")}
    return {"message_id": {v for v in msgids if v}, "idbusta": idbusta, "refid": refid}


def identificativi_deposito(dep: Any) -> dict[str, Any]:
    """Identificativi registrati sul deposito al momento dell'invio o da ricevute gia' collegate."""
    messaggio = str(getattr(dep, "messaggio", "") or "")
    note = str(getattr(dep, "note", "") or "")
    msgids = {normalizza_message_id(m.group(1).rstrip(".;,")) for m in _MESSAGGIO_MSGID.finditer(messaggio)}
    idbusta: set[str] = set()
    refid: set[str] = set()
    esterno = str(getattr(dep, "id_deposito_esterno", "") or "").strip()
    if esterno:
        idbusta.add(esterno)
    for m in _MARCATORE.finditer(note):
        tipo, valore = m.group(1).casefold(), m.group(2).strip()
        if tipo == "idbusta":
            idbusta.add(valore)
        elif tipo == "refid":
            refid.add(valore.casefold())
        else:
            msgids.add(normalizza_message_id(valore))
    codice = str(getattr(dep, "id", "") or "").strip()
    # Il codice interno conta solo se e' abbastanza specifico da non comparire per caso.
    codice_ok = len(codice) >= 8 and any(c.isdigit() for c in codice) and any(c.isalpha() for c in codice)
    return {
        "message_id": {v for v in msgids if v},
        "idbusta": idbusta,
        "refid": refid,
        "codice": codice if codice_ok else "",
    }


def criterio_collegamento(ricevuta: dict, dep: Any, ident_dep: dict | None = None) -> str:
    """Perche' la PEC appartiene al deposito, oppure "" (nessun collegamento certo)."""
    dep_id = ident_dep or identificativi_deposito(dep)
    ric_id = identificativi_ricevuta(ricevuta)
    if ric_id["message_id"] & dep_id["message_id"]:
        return "Message-ID del messaggio di deposito"
    if ric_id["idbusta"] & dep_id["idbusta"]:
        return "IdBusta"
    if ric_id["refid"] & dep_id["refid"]:
        return "RefID"
    codice = dep_id.get("codice") or ""
    if codice and re.search(rf"(?<![A-Za-z0-9]){re.escape(codice)}(?![A-Za-z0-9])", str(ricevuta.get("subject") or ""), re.I):
        return "codice del deposito nell'oggetto"
    return ""


INTESTAZIONI_IMAP = "SUBJECT FROM DATE MESSAGE-ID X-RICEVUTA X-TRASPORTO X-RIFERIMENTO-MESSAGE-ID"
_LIMITE_TESTO = 200_000


def _decodifica_intestazione(valore: Any) -> str:
    from email.header import decode_header

    try:
        parti = []
        for pezzo, charset in decode_header(str(valore or "")):
            parti.append(pezzo.decode(charset or "utf-8", errors="replace") if isinstance(pezzo, bytes) else pezzo)
        return "".join(parti).strip()
    except Exception:
        return str(valore or "").strip()


def ricevuta_da_intestazioni(msg: Any) -> dict:
    """Dizionario ricevuta dalle sole intestazioni (Subject, Date, Message-ID, X-Ricevuta, X-Riferimento)."""
    return {
        "subject": " ".join(_decodifica_intestazione(msg.get("Subject", "")).split()),
        "from": _decodifica_intestazione(msg.get("From", "")),
        "date": str(msg.get("Date", "") or ""),
        "message_id": str(msg.get("Message-ID", "") or "").strip(),
        "x_ricevuta": str(msg.get("X-Ricevuta", "") or "").strip(),
        "x_trasporto": str(msg.get("X-Trasporto", "") or "").strip(),
        "riferimento_message_id": str(msg.get("X-Riferimento-Message-ID", "") or "").strip(),
    }


def testo_messaggio(msg: Any) -> str:
    """Testo e XML del messaggio, comprese le parti annidate (postacert.eml, EsitoAtto.xml)."""
    pezzi: list[str] = []
    for parte in msg.walk():
        tipo = (parte.get_content_type() or "").lower()
        nome = str(parte.get_filename() or "").lower()
        if not (tipo.startswith("text/") or tipo.endswith("xml") or nome.endswith(".xml")):
            continue
        try:
            dati = parte.get_payload(decode=True)
        except Exception:
            dati = None
        if not dati:
            continue
        pezzi.append(dati.decode(parte.get_content_charset() or "utf-8", errors="replace"))
        if sum(len(p) for p in pezzi) > _LIMITE_TESTO:
            break
    return "\n".join(pezzi)[:_LIMITE_TESTO]


def serve_testo(ricevuta: dict) -> bool:
    """Il testo serve solo per esiti del Ministero: le ricevute PEC si collegano dall'intestazione."""
    tipo, _esito = classifica(ricevuta.get("subject"), x_ricevuta=ricevuta.get("x_ricevuta"))
    return tipo in {ESITO_CONTROLLI, ESITO_CANCELLERIA}


def mittenti_interni(msg: Any) -> list[str]:
    """Mittenti dei messaggi annidati (postacert.eml): per gli esiti e' l'ufficio che ha scritto."""
    mittenti: list[str] = []
    for parte in msg.walk():
        if (parte.get_content_type() or "").lower() != "message/rfc822":
            continue
        for interno in parte.get_payload() or []:
            if hasattr(interno, "get"):
                mittenti.append(_decodifica_intestazione(interno.get("From", "")))
    return mittenti


# ---------------------------------------------------------------------------
# Provenienza: chi puo' emettere ciascuna PEC di ritorno
# ---------------------------------------------------------------------------

_EMAIL = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
DOMINIO_MINISTERIALE = "giustiziacert.it"
_TIPI_GESTORE = {ACCETTAZIONE, NON_ACCETTAZIONE, CONSEGNA, MANCATA_CONSEGNA, PREAVVISO_MANCATA_CONSEGNA}
_TIPI_MINISTERO = {ESITO_CONTROLLI, ESITO_CANCELLERIA}
_CRITERIO_MSGID = "Message-ID del messaggio di deposito"


# Valori di X-Ricevuta emessi dai gestori (regole tecniche PEC, d.m. 2/11/2005, all. par. 3.1-3.3).
_X_RICEVUTA_GESTORE = {
    "accettazione", "non-accettazione", "presa-in-carico", "avvenuta-consegna", "posta-certificata",
    "errore-consegna", "preavviso-errore-consegna", "rilevazione-virus",
}
_PER_CONTO_DI = re.compile(r"per\s+conto\s+di\s*:?\s*", re.I)


def _indirizzi(valore: Any) -> set[str]:
    """Indirizzi effettivi (addr-spec) di un'intestazione From; il nome visualizzato non conta.

    Unica eccezione: il «Per conto di: <mittente>» che il gestore PEC scrive nel nome visualizzato della
    busta di trasporto, letto solo quando l'indirizzo effettivo è quello del gestore (posta-certificata@)."""
    trovati: set[str] = set()
    for nome, indirizzo in getaddresses([str(valore or "")]):
        indirizzo = indirizzo.strip().casefold()
        if not _EMAIL.fullmatch(indirizzo):
            continue
        trovati.add(indirizzo)
        if indirizzo.startswith("posta-certificata@") and _PER_CONTO_DI.search(nome or ""):
            conto = _PER_CONTO_DI.split(nome, maxsplit=1)[-1].strip().casefold()
            if _EMAIL.fullmatch(conto):
                trovati.add(conto)
    return trovati


def _ministeriale(indirizzo: str) -> bool:
    dominio = indirizzo.rpartition("@")[2]
    return dominio == DOMINIO_MINISTERIALE or dominio.endswith("." + DOMINIO_MINISTERIALE)


def _anomalia(ricevuta: dict) -> bool:
    """Messaggio non PEC imbustato dal nostro gestore come anomalia (X-Trasporto: errore): mittente non garantito."""
    return str(ricevuta.get("x_trasporto") or "").strip().casefold() == "errore"


def da_gestore_pec(ricevuta: dict) -> bool:
    """Ricevuta emessa dal gestore PEC: indirizzo effettivo «posta-certificata@» del gestore e, se presente,
    X-Ricevuta con un valore delle regole tecniche. Una e-mail qualunque con oggetto «CONSEGNA:» non lo è."""
    if _anomalia(ricevuta):
        return False
    x_ric = str(ricevuta.get("x_ricevuta") or "").strip().casefold()
    if x_ric and x_ric not in _X_RICEVUTA_GESTORE:
        return False
    return any(a.startswith("posta-certificata@") for a in _indirizzi(ricevuta.get("from")))


def _ufficio_ammesso(indirizzo: str, ufficio: str) -> bool:
    return bool(indirizzo) and (indirizzo == ufficio or _ministeriale(indirizzo))


def motivo_non_applicabile(rc: "RicevutaCollegata", dep: Any) -> str:
    """"" se la PEC puo' cambiare lo stato del deposito; altrimenti il motivo (fail-closed)."""
    r = rc.ricevuta
    if rc.tipo in _TIPI_GESTORE:
        if not da_gestore_pec(r):
            return "non emessa dal gestore PEC"
        if rc.criterio != _CRITERIO_MSGID:
            return "non riferita al Message-ID del messaggio di deposito"
        return ""
    if rc.tipo in _TIPI_MINISTERO:
        if rc.criterio != _CRITERIO_MSGID:
            return f"collegata solo per {rc.criterio}, non per l'identificativo del messaggio di deposito (IdMsgMitt)"
        if _anomalia(r):
            return "messaggio non PEC (anomalia del gestore): mittente non garantito"
        ufficio = str(getattr(dep, "pec_destinatario", "") or "").strip().casefold()
        esterni = _indirizzi(r.get("from"))
        if not any(_ufficio_ammesso(a, ufficio) for a in esterni):
            return "mittente diverso dall'ufficio del deposito o da un indirizzo ministeriale"
        interni = [_indirizzi(m) for m in r.get("mittenti_interni") or [] if str(m or "").strip()]
        if not interni:
            return "messaggio interno (postacert.eml) assente: mittente dell'ufficio non verificabile"
        if any(not any(_ufficio_ammesso(a, ufficio) for a in gruppo) for gruppo in interni):
            return "messaggio interno (postacert.eml) non inviato dall'ufficio"
        return ""
    return "tipo di PEC non riconosciuto"


def _data_ricevuta(ricevuta: dict) -> datetime | None:
    try:
        valore = parsedate_to_datetime(str(ricevuta.get("date") or ""))
    except (TypeError, ValueError, IndexError):
        return None
    if valore is None:
        return None
    return valore.replace(tzinfo=ROME_TZ) if valore.tzinfo is None else valore.astimezone(ROME_TZ)


def _data_deposito(dep: Any) -> datetime | None:
    try:
        valore = datetime.fromisoformat(str(getattr(dep, "timestamp", "") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return valore.replace(tzinfo=ROME_TZ) if valore.tzinfo is None else valore.astimezone(ROME_TZ)


@dataclass
class RicevutaCollegata:
    ricevuta: dict
    tipo: str
    esito: str
    criterio: str
    fase: int = field(init=False)

    def __post_init__(self) -> None:
        self.fase = FASE.get(self.tipo, 9)


def ricevute_del_deposito(dep: Any, ricevute: Iterable[dict]) -> list[RicevutaCollegata]:
    """Solo le PEC di ritorno collegate al deposito per identificativo, in ordine di fase."""
    ident = identificativi_deposito(dep)
    inviato_il = _data_deposito(dep)
    collegate: list[RicevutaCollegata] = []
    for ricevuta in ricevute or []:
        tipo, esito = classifica(
            ricevuta.get("subject"), x_ricevuta=ricevuta.get("x_ricevuta"), testo=ricevuta.get("testo"),
        )
        if not tipo:
            continue
        criterio = criterio_collegamento(ricevuta, dep, ident)
        if not criterio:
            continue
        arrivata = _data_ricevuta(ricevuta)
        if inviato_il and arrivata and arrivata < inviato_il.replace(second=0, microsecond=0):
            continue  # una ricevuta anteriore all'invio non puo' riguardare questo deposito
        collegate.append(RicevutaCollegata(ricevuta, tipo, esito, criterio))
    collegate.sort(key=lambda r: (r.fase, str(r.ricevuta.get("date") or "")))
    return collegate


# ---------------------------------------------------------------------------
# Applicazione al deposito
# ---------------------------------------------------------------------------

def _prova(rc: RicevutaCollegata) -> str:
    r = rc.ricevuta
    righe = [
        f"{ETICHETTA[rc.tipo][:1].upper()}{ETICHETTA[rc.tipo][1:]}",
        f"Oggetto: {str(r.get('subject') or '')[:300]}",
    ]
    if r.get("date"):
        righe.append(f"Data: {r.get('date')}")
    if r.get("message_id"):
        righe.append(f"Message-ID ricevuta: {r.get('message_id')}")
    if rc.esito:
        righe.append(f"Esito: {rc.esito}")
    righe.append(f"Collegata al deposito per: {rc.criterio}")
    return "\n".join(righe)


_STATO_DA_CONTROLLI = {
    "OK": "CONTROLLI_SUPERATI",
    "WARN": "WARN_CONTROLLI",
    "ERROR": "ERRORE_CONTROLLI",
    "FATAL": "ERRORE_CONTROLLI",
}


def applica_ricevute(dep: Any, ricevute: Iterable[dict], *, adesso: datetime | None = None) -> dict[str, Any]:
    """Aggiorna stato e ricevute del deposito con le sole PEC collegate; mai stati dedotti.

    Restituisce {"aggiornato", "stato_precedente", "stato", "eventi": [...]}. Le avvertenze gia'
    annotate nel deposito non si ripetono: un controllo periodico non riscrive le note."""
    stato_iniziale = str(getattr(dep, "stato", "") or "")
    eventi: list[str] = []
    avvertenze: list[str] = []
    for rc in ricevute_del_deposito(dep, ricevute):
        motivo = motivo_non_applicabile(rc, dep)
        if motivo:
            if rc.tipo in _TIPI_MINISTERO:
                avvertenze.append(
                    f"{ETICHETTA[rc.tipo]} da verificare, stato non modificato: {motivo} "
                    f"(oggetto «{str(rc.ricevuta.get('subject') or '')[:120]}»)"
                )
            continue
        stato = str(getattr(dep, "stato", "") or "")
        prova = _prova(rc)
        if rc.tipo == ACCETTAZIONE:
            if not dep.ricevuta_accettazione:
                dep.ricevuta_accettazione = prova
                eventi.append("ricevuta di accettazione registrata")
            if stato == "INVIATO":
                dep.stato = "ACCETTATO_PEC"
        elif rc.tipo == NON_ACCETTAZIONE:
            if stato in {"INVIATO", "ACCETTATO_PEC"}:
                dep.stato = "ERRORE"
                eventi.append("avviso di non accettazione: il messaggio di deposito non e' partito, ripetere il deposito")
        elif rc.tipo == CONSEGNA:
            if not dep.ricevuta_consegna:
                dep.ricevuta_consegna = prova
                eventi.append("ricevuta di avvenuta consegna registrata (art. 196-sexies disp. att. c.p.c.)")
            if stato in {"INVIATO", "ACCETTATO_PEC"}:
                dep.stato = "CONSEGNATO"
        elif rc.tipo == MANCATA_CONSEGNA:
            if stato in {"INVIATO", "ACCETTATO_PEC"} and not dep.ricevuta_consegna:
                dep.stato = "ERRORE"
                eventi.append(
                    "avviso di mancata consegna: deposito non perfezionato (art. 196-sexies disp. att. c.p.c.), "
                    "ripetere il deposito entro il termine"
                )
        elif rc.tipo == PREAVVISO_MANCATA_CONSEGNA:
            avvertenze.append("preavviso di mancata consegna: verificare la consegna del deposito")
        elif rc.tipo == ESITO_CONTROLLI:
            if not dep.ricevuta_controlli_automatici:
                dep.ricevuta_controlli_automatici = prova
                if rc.esito:
                    dep.esito_controlli = rc.esito
                    if stato not in STATI_FINALI:
                        dep.stato = _STATO_DA_CONTROLLI[rc.esito]
                eventi.append(f"esito dei controlli automatici registrato ({rc.esito or 'livello da leggere nel messaggio'})")
                if rc.esito == "FATAL":
                    eventi.append("anomalia FATAL: deposito rifiutato dal sistema, ripetere il deposito")
        elif rc.tipo == ESITO_CANCELLERIA:
            if not rc.esito:
                avvertenze.append("esito della cancelleria arrivato ma non leggibile: verifica manuale")
            elif not dep.ricevuta_cancelleria:
                dep.ricevuta_cancelleria = prova
                if stato not in STATI_FINALI and str(getattr(dep, "esito_controlli", "") or "") != "FATAL":
                    dep.stato = "ACCETTATO_CANCELLERIA" if rc.esito == "ACCETTATO" else "RIFIUTATO_CANCELLERIA"
                eventi.append(f"esito della cancelleria registrato ({rc.esito.lower()})")
    note_attuali = str(getattr(dep, "note", "") or "")
    eventi.extend(a for a in dict.fromkeys(avvertenze) if a not in note_attuali)
    aggiornato = bool(eventi) or dep.stato != stato_iniziale
    if aggiornato:
        quando = (adesso or datetime.now(ROME_TZ)).strftime("%d/%m/%Y %H:%M")
        riepilogo = "; ".join(eventi or [f"stato {dep.stato}"])
        dep.note = (note_attuali + f"\n[AUTO {quando}] Ricevute collegate: {riepilogo}").strip()
    return {"aggiornato": aggiornato, "stato_precedente": stato_iniziale, "stato": dep.stato, "eventi": eventi}


