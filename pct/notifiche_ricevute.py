"""Notifiche ricevute dalla controparte: quale atto, da quando decorre, quale termine si apre.

Una PEC con oggetto «Notificazione ai sensi della legge n. 53 del 1994» può essere
inviata dallo studio (si attendono RAC e RdAC per ogni destinatario) oppure
ricevuta dalla controparte: in questo secondo caso è l'atto notificato al cliente,
e da quel momento decorrono i termini per difendersi.

Base normativa:

- art. 3-bis L. 53/1994 e art. 147, comma 3, c.p.c.: per il destinatario la notifica
  si perfeziona quando è generata la ricevuta di avvenuta consegna; se cade fra le 21
  e le 7 si perfeziona alle 7 (calcolo in `pct.calcolatori.perfezionamento_notifica`);
- art. 641 c.p.c.: opposizione a decreto ingiuntivo entro 40 giorni dalla notifica;
- art. 325 c.p.c.: appello 30 giorni e ricorso per cassazione 60 giorni dalla notifica
  della sentenza;
- art. 370 c.p.c.: controricorso entro 40 giorni dalla notifica del ricorso per cassazione;
- art. 480 c.p.c.: termine di almeno 10 giorni per adempiere al precetto; art. 617 c.p.c.:
  opposizione agli atti esecutivi entro 20 giorni dalla notifica del precetto;
- art. 166 c.p.c.: costituzione del convenuto almeno 70 giorni prima dell'udienza indicata
  nell'atto di citazione; artt. 343 e 347 c.p.c.: costituzione dell'appellato, con l'eventuale
  appello incidentale, almeno 20 giorni prima dell'udienza indicata nell'atto di appello.

Il modulo propone: ogni termine resta da confermare dall'avvocato, che verifica validità
della notifica, destinatario e atto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable

from pct.ora_italiana import ROME_TZ

ORA_CHIUSURA = time(21, 0)

_OGGETTO_L53 = re.compile(r"notificazione\s+ai\s+sensi\s+della\s+legge\s+(?:n\.?\s*)?53\s+del\s+1994", re.IGNORECASE)
_DATA = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
_UDIENZA = re.compile(r"\budienza\b[^.\n]{0,80}?\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{4})\b", re.IGNORECASE)


@dataclass(frozen=True)
class Termine:
    codice: str
    azione: str
    norma: str
    giorni: int
    verso: str = "forward"  # forward: dalla notifica; backward: prima dell'udienza indicata nell'atto


@dataclass(frozen=True)
class AttoNotificato:
    codice: str
    etichetta: str
    riconoscimento: re.Pattern[str]
    termini: tuple[Termine, ...]


# L'ordine conta: il decreto ingiuntivo cita il ricorso, l'appello cita la sentenza impugnata.
ATTI: tuple[AttoNotificato, ...] = (
    AttoNotificato(
        "decreto_ingiuntivo", "Decreto ingiuntivo",
        re.compile(r"\bdecreto\s+ingiuntivo\b|\bingiunge\b", re.IGNORECASE),
        (Termine("opposizione_decreto_ingiuntivo", "Opposizione a decreto ingiuntivo", "art. 641 c.p.c.", 40),),
    ),
    AttoNotificato(
        "atto_di_precetto", "Atto di precetto",
        re.compile(r"\batto\s+di\s+precetto\b|\bintima\s+e\s+fa\s+precetto\b", re.IGNORECASE),
        (
            Termine("termine_adempimento_precetto", "Termine per adempiere al precetto", "art. 480 c.p.c.", 10),
            Termine("opposizione_atti_esecutivi_precetto", "Opposizione agli atti esecutivi (vizi del precetto)",
                    "art. 617 c.p.c.", 20),
        ),
    ),
    AttoNotificato(
        "ricorso_per_cassazione", "Ricorso per cassazione",
        re.compile(r"\bricorso\s+per\s+cassazione\b|\bcorte\s+suprema\s+di\s+cassazione\b", re.IGNORECASE),
        (Termine("controricorso", "Controricorso", "art. 370 c.p.c.", 40),),
    ),
    AttoNotificato(
        "atto_di_appello", "Atto di appello",
        re.compile(r"\batto\s+di\s+appello\b|\bpropone\s+appello\b|\bappello\s+avverso\b", re.IGNORECASE),
        (Termine("costituzione_appellato", "Costituzione dell'appellato ed eventuale appello incidentale",
                 "artt. 343 e 347 c.p.c.", 20, "backward"),),
    ),
    AttoNotificato(
        "atto_di_citazione", "Atto di citazione",
        re.compile(r"\batto\s+di\s+citazione\b|\bcita\s+a\s+comparire\b", re.IGNORECASE),
        (Termine("costituzione_convenuto", "Costituzione del convenuto", "art. 166 c.p.c.", 70, "backward"),),
    ),
    AttoNotificato(
        "sentenza", "Sentenza",
        re.compile(r"\bsentenza\b", re.IGNORECASE),
        (),  # termine scelto in base al giudice che l'ha pronunciata: vedi `_termini_sentenza`
    ),
)


def oggetto_di_notifica_l53(oggetto: str) -> bool:
    return bool(_OGGETTO_L53.search(str(oggetto or "")))


def _carattere_indirizzo(carattere: str, *, locale: bool) -> bool:
    return carattere.isalnum() or carattere in ("_.-+" if locale else "_.-")


def _indirizzo(valore: Any) -> str:
    """Il primo indirizzo email del testo (es. «Nome <a@b.it>»), altrimenti il testo normalizzato.

    Scansione lineare attorno alla «@»: niente espressione regolare non ancorata,
    che su un'intestazione costruita ad arte cresce in tempo quadratico (ReDoS).
    """
    testo = str(valore or "").strip().casefold()
    posizione = testo.find("@")
    while posizione != -1:
        inizio = posizione
        while inizio > 0 and _carattere_indirizzo(testo[inizio - 1], locale=True):
            inizio -= 1
        fine = posizione + 1
        while fine < len(testo) and _carattere_indirizzo(testo[fine], locale=False):
            fine += 1
        if inizio < posizione and fine > posizione + 1:
            return testo[inizio:fine]
        posizione = testo.find("@", posizione + 1)
    return testo


def direzione_notifica(*, casella: str, mittente: str, cartella: str = "") -> str:
    """«inviata» se la PEC parte dalla casella dello studio, «ricevuta» se vi arriva da un altro indirizzo."""
    casella_norm, mittente_norm = _indirizzo(casella), _indirizzo(mittente)
    if not casella_norm or not mittente_norm:
        return ""
    if mittente_norm == casella_norm:
        return "inviata"
    if re.search(r"\b(?:sent|inviat|posta\s+inviata)", str(cartella or ""), re.IGNORECASE):
        return "inviata"
    return "ricevuta"


def perfezionamento_destinatario(consegna: datetime) -> date:
    """Giorno di perfezionamento per il destinatario (art. 147, comma 3, c.p.c.): dopo le 21 è il giorno dopo."""
    momento = consegna.replace(tzinfo=ROME_TZ) if consegna.tzinfo is None else consegna.astimezone(ROME_TZ)
    return momento.date() + timedelta(days=1) if momento.time() >= ORA_CHIUSURA else momento.date()


def atto_notificato(testo: str, nomi_allegati: Iterable[str] = ()) -> AttoNotificato | None:
    """L'atto notificato, letto prima dai nomi degli allegati e poi dal testo."""
    for sorgente in (" ".join(str(nome or "") for nome in nomi_allegati), str(testo or "")):
        normalizzata = re.sub(r"[_\-]+", " ", sorgente)
        for atto in ATTI:
            if atto.riconoscimento.search(normalizzata):
                return atto
    return None


def _termini_sentenza(testo: str) -> tuple[Termine, ...]:
    if re.search(r"\bcorte\s+d.?\s*appello\b|\bcorte\s+di\s+appello\b", testo, re.IGNORECASE):
        return (Termine("ricorso_cassazione_breve", "Ricorso per cassazione (termine breve)", "art. 325 c.p.c.", 60),)
    return (Termine("appello_breve", "Appello (termine breve)", "art. 325 c.p.c.", 30),)


def _udienza_indicata(testo: str) -> date | None:
    trovata = _UDIENZA.search(str(testo or ""))
    if not trovata:
        return None
    giorno, mese, anno = (int(parte) for parte in _DATA.search(trovata.group(1)).groups())
    try:
        return date(anno, mese, giorno)
    except ValueError:
        return None


def termini_da_notifica_ricevuta(
    testo: str, *, consegna: datetime, nomi_allegati: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Proposte di scadenza per l'atto notificato al cliente; vuoto se l'atto non si riconosce."""
    nomi = list(nomi_allegati)
    atto = atto_notificato(testo, nomi)
    if atto is None:
        return []
    perfezionata = perfezionamento_destinatario(consegna)
    termini = _termini_sentenza(" ".join([*nomi, str(testo or "")]).replace("_", " ")) if atto.codice == "sentenza" else atto.termini
    proposte: list[dict[str, Any]] = []
    for termine in termini:
        if termine.verso == "backward":
            udienza = _udienza_indicata(testo)
            if udienza is None:
                continue
            decorrenza, tipo = udienza, "udienza"
        else:
            decorrenza, tipo = perfezionata, "notificazione"
        proposte.append({
            "deadline_type": f"{termine.azione} — notifica ricevuta: {atto.etichetta.lower()}",
            "norma": termine.norma,
            "duration_value": termine.giorni,
            "duration_unit": "giorni",
            "dies_a_quo_type": tipo,
            "dies_a_quo_date": decorrenza.isoformat(),
            "direction": termine.verso,
            "peremptory": True,
            "suggested_priority": "P0",
            "create_in_scadenziario": True,
            "requires_deterministic_calculation": True,
            "human_review_required": True,
            "codice_termine": termine.codice,
            "atto_notificato": atto.codice,
            "evidence": [{
                "source": "notifica ricevuta (L. 53/1994)",
                "text": (f"{atto.etichetta} notificato al cliente; notifica perfezionata per il destinatario il "
                         f"{perfezionata.strftime('%d/%m/%Y')} (art. 147, comma 3, c.p.c.)."),
                "confidence": 0.85,
            }],
        })
    return proposte


__all__ = [
    "ATTI", "AttoNotificato", "Termine", "atto_notificato", "direzione_notifica", "oggetto_di_notifica_l53",
    "perfezionamento_destinatario", "termini_da_notifica_ricevuta",
]
