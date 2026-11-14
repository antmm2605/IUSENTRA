"""Quale parte difende lo studio: si propongono solo i termini che spettano al cliente.

Caso reale (Tribunale di Vicenza, sezione lavoro, RG 901/2026): lo studio difende il ricorrente, ma
dal decreto di fissazione dell'udienza (art. 415 c.p.c.) veniva proposta anche la «Costituzione del
convenuto con memoria difensiva» (art. 416 c.p.c.), che è un onere della controparte. Ogni regola della
tabella ``provvedimenti_regole`` dichiara ``chi`` deve agire: le regole di una parte determinata si
propongono solo se il cliente ha quel ruolo; quelle delle «parti», del giudice o della cancelleria
restano sempre. Se il ruolo del cliente non è certo, nessuna regola si scarta (fail-closed: meglio una
bozza in più da scartare che un termine del cliente perduto).

Il ruolo si ricava dalle parti scritte dalla cancelleria nella Comunicazione.xml («Ricorr. principale»,
«Resist. principale», art. 16 D.L. 179/2012; specifiche DGSIA) confrontate col cliente del fascicolo,
come fa la lettura del fascicolo (``pct/fascicolo_lettura/percorso._ruolo_cliente``).
"""

from __future__ import annotations

import re
from typing import Any

ATTIVO = "ricorrente"
PASSIVO = "resistente"

#: chi promuove il giudizio o l'impugnazione
_CHI_ATTIVI = frozenset({"ricorrente", "attore", "appellante", "opponente", "reclamante", "richiedente"})
#: chi lo subisce
_CHI_PASSIVI = frozenset({"convenuto", "resistente", "ingiunto", "appellato", "opposto", "reclamato"})


def _parole(nome: Any) -> set[str]:
    return {p for p in re.split(r"[^\wÀ-ÿ']+", str(nome or "").lower()) if len(p) > 1}


def _stessa_persona(a: Any, b: Any) -> bool:
    pa, pb = _parole(a), _parole(b)
    return bool(pa and pb) and (pa <= pb or pb <= pa)


def ruolo_cliente(cliente: Any, *, attore: Any = "", convenuto: Any = "", controparte: Any = "") -> str:
    """«ricorrente», «resistente» o "" se non si sa con certezza."""
    attivo = _stessa_persona(cliente, attore)
    passivo = _stessa_persona(cliente, convenuto)
    if attivo != passivo:
        return ATTIVO if attivo else PASSIVO
    if not attivo and controparte:
        contro_attivo, contro_passivo = _stessa_persona(controparte, attore), _stessa_persona(controparte, convenuto)
        if contro_attivo != contro_passivo:
            return PASSIVO if contro_attivo else ATTIVO
    return ""


_RE_RELATA = re.compile(r"relata\s+di\s+notific", re.I)
_RE_DIFENSORE_DI = re.compile(r"difensor[ei]\b[^.;]{0,60}?\bd[ie]l?l?[a']?\s*:?\s*(?P<parte>[^;\n(]{3,80})", re.I)
_RE_SOTTOSCRITTO = re.compile(r"\b(?:io\s+)?sottoscritt[oa]\b", re.I)
_RE_HO_NOTIFICATO = re.compile(r"\bho\s+notificato\b|\bnotifico\b", re.I)
_RE_ATTO_INTRODUTTIVO = re.compile(r"\b(?:ricorso|atto\s+di\s+citazione|citazione)\b", re.I)


#: tetti per il testo PEC non fidato: lunghezza esaminata e dichiarazioni «sottoscritto» provate
_MASSIMO_TESTO = 200_000
_MASSIME_DICHIARAZIONI = 20
_FINESTRA_DICHIARAZIONE = 1200
_RE_INDIRIZZO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
def notifica_uscente_dello_studio(*, casella: Any, cartella: Any = "", **_ignorati: Any) -> bool:
    """La PEC è verificabilmente partita dalla casella dello studio; altrimenti False (ruolo incerto).

    Fail-closed: l'unica prova accettata è l'origine IMAP del record dalla cartella degli inviati della casella
    dello studio (regola di ``pct.email_client._cartella_interna_da_imap``). Non bastano l'intestazione From di un
    messaggio ricevuto, il testo del corpo, né un daticert.xml o uno smime.p7s presi dagli allegati (un allegato o
    un messaggio annidato si falsificano). La ricevuta del gestore varrà come prova solo con un verificatore S/MIME
    vero della busta (PKCS#7 sulla parte firmata, certificato del gestore iscritto nell'elenco AgID, dominio
    coerente: art. 6 D.P.R. 68/2005; regole tecniche D.M. 2/11/2005), che oggi il software non ha.
    """
    propria = str(casella or "").strip().casefold()
    if not propria or not _RE_INDIRIZZO.fullmatch(propria) or not str(cartella or "").strip():
        return False
    from pct.email_client import CartellaEmail, _cartella_interna_da_imap

    return _cartella_interna_da_imap(str(cartella)) == CartellaEmail.INVIATI


def ruolo_da_relata(testo: Any, cliente: Any) -> str:
    """«ricorrente» se il testo è la relata con cui il difensore del cliente notifica l'atto introduttivo, altrimenti "".

    Chi notifica il ricorso con il decreto di fissazione dell'udienza è l'attore (art. 415, comma 4, c.p.c.:
    «deve essere notificato al convenuto, a cura dell'attore»); chi notifica l'atto di citazione è l'attore
    (artt. 163 e 163-bis c.p.c.). La relata dell'avvocato (art. 3-bis L. 53/1994) nomina la parte assistita
    («difensore per mandato come in atti di: …»): se è il cliente del fascicolo e l'atto notificato è il ricorso o
    la citazione, il cliente è la parte che promuove il giudizio. Nessuna deduzione se la relata non nomina il
    cliente o non riguarda l'atto introduttivo. Il chiamante la usa solo per una notifica verificabilmente uscente
    dallo studio (``notifica_uscente_dello_studio``): la relata in sé non prova chi l'ha scritta.

    Testo non fidato: lunghezza e numero di dichiarazioni esaminate hanno un tetto, ogni ricerca ha una finestra.
    """
    testo = str(testo or "")[:_MASSIMO_TESTO]
    if not cliente or not _RE_RELATA.search(testo):
        return ""
    # Solo la dichiarazione del notificante («Io sottoscritto Avv. … difensore … di: …» fino a «HO NOTIFICATO»):
    # il «difensore di» scritto accanto al destinatario è il difensore della controparte.
    for numero, inizio in enumerate(_RE_SOTTOSCRITTO.finditer(testo)):
        if numero >= _MASSIME_DICHIARAZIONI:
            break
        fine = _RE_HO_NOTIFICATO.search(testo, inizio.end(), inizio.end() + _FINESTRA_DICHIARAZIONE)
        if fine is None:
            continue
        dichiarazione = testo[inizio.end():fine.start()]
        if any(_stessa_persona(cliente, t.group("parte")) for t in _RE_DIFENSORE_DI.finditer(dichiarazione)) \
                and _RE_ATTO_INTRODUTTIVO.search(testo, fine.end(), fine.end() + 3000):
            return ATTIVO
    return ""


def spetta_al_cliente(chi: Any, ruolo: str) -> bool:
    """La regola di ``chi`` riguarda il cliente con ``ruolo`` (sempre vero se il ruolo non è noto)."""
    soggetto = str(chi or "").strip().lower()
    if ruolo == ATTIVO:
        return soggetto not in _CHI_PASSIVI
    if ruolo == PASSIVO:
        return soggetto not in _CHI_ATTIVI
    return True


__all__ = ["ATTIVO", "PASSIVO", "ruolo_cliente", "notifica_uscente_dello_studio", "ruolo_da_relata", "spetta_al_cliente"]
