"""Date lette che non possono essere quello che sembrano: decorrenze anteriori all'atto che le fa decorrere.

Funzione pura per la riconvalida dei fatti già registrati e per il motore del ragionamento processuale.

Regola. Un termine processuale decorre da un evento — la notificazione, la comunicazione, la pubblicazione
(artt. 155, 326, 327, 641 c.p.c.). Il giorno da cui il termine decorre (*dies a quo*, escluso dal computo:
art. 155, comma 1, c.p.c.) non è la scadenza e non è un'udienza. Se il testo dice che il termine decorre da
una data **anteriore** all'atto che lo fa decorrere, scritto nello stesso documento (es. istanza di
esecutorietà ex art. 647 c.p.c.: «decreto notificato il 23/12/2024 … termine di quaranta giorni ex art. 641
decorrente dal 10/02/2024»), la data è un errore materiale: non è un termine, si segnala come incoerente
perché l'avvocato la corregga nell'atto, e non entra mai nello scadenziario.

Testi riscontrati nell'archivio Normattiva del software il 10/11/2026 (art. 155 e art. 641 c.p.c.).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Iterable

#: la data che segue queste parole è il giorno da cui il termine decorre
RE_DECORRENZA = re.compile(
    r"(?:decorren(?:te|ti|za)|a\s+decorrere|che\s+decorre|decorre|decorrono)\s+(?:dal(?:la\s+data\s+del)?|da|dalla)\s*$",
    re.I,
)
#: gli eventi da cui un termine processuale può decorrere, nell'ordine in cui il documento li racconta
_EVENTI = frozenset({"notifica", "comunicazione"})
#: la decorrenza deve riguardare un termine del processo, non un contratto o un rapporto
_RE_TERMINE_PRIMA = re.compile(r"\btermin[ei]\b", re.I)
_RE_NON_PROCESSUALE = re.compile(r"contratt|rapporto|servizio|assunzion|incarico|locazion|supplenz|tramutament|nomina", re.I)


def _giorno(valore: Any) -> date | None:
    testo = str(valore or "").split("T")[0][:10]
    try:
        return date.fromisoformat(testo)
    except ValueError:
        return None


def e_decorrenza(contesto: str, valore_letto: str) -> bool:
    """La data letta è il giorno da cui decorre un termine del processo («il termine … decorrente dal …»).

    Non vale per la decorrenza di un contratto, di un rapporto o di un incarico («contratto a tempo determinato
    decorrente dal …»): quella non è un termine processuale e non ha un atto processuale che la faccia decorrere.
    """
    contesto, letto = str(contesto or ""), str(valore_letto or "").strip()
    if not letto:
        return False
    for trovata in re.finditer(re.escape(letto), contesto):
        prima = contesto[max(0, trovata.start() - 120):trovata.start()]
        if RE_DECORRENZA.search(prima[-60:]) and _RE_TERMINE_PRIMA.search(prima) and not _RE_NON_PROCESSUALE.search(prima):
            return True
    return False


def motivo_incoerenza(fatto: Any, fatti_stesso_oggetto: Iterable[Any]) -> str:
    """Perché il fatto è una decorrenza incoerente; stringa vuota se non c'è incoerenza dimostrata.

    Vale per i fatti di data con campo ``termine``/``decorrenza``/``udienza``/``costituzione`` la cui data
    è introdotta da una formula di decorrenza di un termine ed è anteriore alla notificazione o alla
    comunicazione letta nello **stesso documento** (gli eventi da cui i termini processuali decorrono): l'atto che fa decorrere il
    termine non può essere successivo al giorno da cui il termine decorre.
    """
    if getattr(fatto, "categoria", "") != "data" or getattr(fatto, "campo", "") not in {"termine", "decorrenza", "udienza", "costituzione"}:
        return ""
    giorno = _giorno(getattr(fatto, "valore", ""))
    if giorno is None or not e_decorrenza(getattr(fatto, "contesto", ""), getattr(fatto, "valore_letto", "")):
        return ""
    eventi = sorted(
        (g, str(getattr(altro, "campo", "")))
        for altro in fatti_stesso_oggetto
        if getattr(altro, "categoria", "") == "data" and getattr(altro, "campo", "") in _EVENTI
        and getattr(altro, "oggetto_id", "") == getattr(fatto, "oggetto_id", "")
        and getattr(altro, "verifica", "") in {"verificata", "corretta", "plausibile"}
        and (g := _giorno(getattr(altro, "valore", ""))) is not None and g > giorno
    )
    if not eventi:
        return ""
    evento, campo = eventi[0]
    return (
        f"Decorrenza incoerente: il termine decorrerebbe dal {giorno:%d/%m/%Y}, data anteriore all'atto che lo fa decorrere "
        f"({campo} del {evento:%d/%m/%Y}) letto nello stesso documento. È un errore materiale dell'atto da correggere, "
        "non un termine (art. 155, comma 1, c.p.c.: il giorno iniziale è escluso dal computo e non è la scadenza)."
    )


__all__ = ["RE_DECORRENZA", "e_decorrenza", "motivo_incoerenza"]
