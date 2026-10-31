"""Termine lungo di impugnazione (art. 327 c.p.c.) dalla data di deposito della sentenza.

Base normativa:

- art. 133 c.p.c.: la sentenza è resa pubblica con il deposito in cancelleria; da quel
  giorno decorre il termine lungo di sei mesi dell'art. 327 c.p.c., che vale se la sentenza
  non viene notificata (con la notifica decorre il termine breve dell'art. 325 c.p.c.);
- la comunicazione di cancelleria non fa decorrere alcun termine: serve solo a sapere che
  la sentenza è stata depositata;
- art. 1 L. 742/1969: sospensione feriale dal 1° al 31 agosto, esclusa per lavoro e
  previdenza (art. 3 L. 742/1969).

La data di deposito si legge dal testo della comunicazione o dai documenti del fascicolo
(timbro di pubblicazione della sentenza, letto dall'archivio delle letture). Se le date
lette sono più d'una e non si distinguono, non si sceglie: resta il promemoria senza data.
Il termine calcolato è una bozza da confermare dall'avvocato.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Iterable

from pct.termini_processuali import ItalianDeadlineCalculator

_DATA = r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})"
_PUBBLICAZIONE = re.compile(
    r"\b(?:depositat[ao]|pubblicat[ao]|pubbl\.(?:\s+il)?|data\s+(?:di\s+|del\s+)?(?:deposito|pubblicazione))"
    r"[^.\n]{0,40}?\b" + _DATA + r"\b"
    r"|\bin\s+data\s+" + _DATA + r"\s*,?\s*(?:è|e'|e)\s+stat[ao]\s+(?:depositat[ao]|pubblicat[ao])\b",
    re.IGNORECASE,
)
_NUMERO = re.compile(r"\bsentenza\s+(?:definitiva\s+|non\s+definitiva\s+)?n\.?\s*(\d{1,6}\s*/\s*\d{4})\b", re.IGNORECASE)
_DI_SENTENZA = re.compile(r"\bsentenz[ae]\b", re.IGNORECASE)
_DI_DEPOSITO = re.compile(r"\bdeposit|\bpubbl", re.IGNORECASE)
_CORTE_APPELLO = re.compile(r"\bcorte\s+d.?\s*appello\b|\bcorte\s+di\s+appello\b", re.IGNORECASE)
_CAMPI_DATA = {"deposito", "provvedimento"}
MARCATORE = "SENTENZA_327:{comunicazione}"


_DELLA_SENTENZA = re.compile(
    # «Sentenza n. 254/2026 pubblicata il …»: il punto delle abbreviazioni (n., nr., num.) non chiude la frase.
    r"\bsentenza\b(?:[^.\n]|(?<=\bn)\.|(?<=\bnr)\.|(?<=\bnum)\.){0,80}?\b(?:pubbl(?:\.|icat[ao])|depositat[ao])(?:\s+in\s+cancelleria)?\s+(?:il|in\s+data)?\s*"
    + _DATA + r"\b|\bpubbl\.\s+il\s+" + _DATA + r"\b",
    re.IGNORECASE,
)


def _date_trovate(espressione: re.Pattern[str], testo: str) -> set[date]:
    trovate: set[date] = set()
    for trovata in espressione.finditer(str(testo or "")):
        giorno, mese, anno = (int(parte) for parte in trovata.groups() if parte is not None)
        try:
            trovate.add(date(anno, mese, giorno))
        except ValueError:
            continue
    return trovate


def data_pubblicazione(testo: str, *, comunicazione: bool = True) -> date | None:
    """La data di deposito della sentenza scritta nel testo, solo se univoca.

    Prima il timbro o la frase legata alla parola «sentenza»; nel testo della comunicazione di
    cancelleria, che parla solo della sentenza, vale anche «depositata il …». Negli atti allegati
    no: «ricorso depositato il …» non è il deposito della sentenza.
    """
    for espressione in (_DELLA_SENTENZA, _PUBBLICAZIONE) if comunicazione else (_DELLA_SENTENZA,):
        trovate = _date_trovate(espressione, testo)
        if trovate:
            return next(iter(trovate)) if len(trovate) == 1 else None
    return None


def numero_sentenza(testo: str) -> str:
    trovato = _NUMERO.search(str(testo or ""))
    return re.sub(r"\s+", "", trovato.group(1)) if trovato else ""


def _giorno(valore: Any) -> date | None:
    try:
        return date.fromisoformat(str(valore or "")[:10])
    except ValueError:
        return None


def data_pubblicazione_da_fatti(fatti: Iterable[Any], *, numero: str = "") -> date | None:
    """Data di deposito della sentenza letta nei documenti del fascicolo, solo se univoca.

    Vale una data ancorata al deposito o alla pubblicazione di una sentenza; se la
    comunicazione indica il numero della sentenza, contano solo le date vicine a quel numero.
    """
    candidate: dict[str, set[date]] = {"numero": set(), "tutte": set()}
    for fatto in fatti:
        if str(getattr(fatto, "categoria", "")) != "data" or str(getattr(fatto, "campo", "")) not in _CAMPI_DATA:
            continue
        if str(getattr(fatto, "verifica", "")) == "respinto":
            continue
        contesto = str(getattr(fatto, "contesto", "") or "")
        giorno = _giorno(getattr(fatto, "valore", ""))
        if giorno is None or not _DI_SENTENZA.search(contesto) or not _DI_DEPOSITO.search(contesto):
            continue
        candidate["tutte"].add(giorno)
        if numero and numero in re.sub(r"\s+", "", contesto):
            candidate["numero"].add(giorno)
    scelte = candidate["numero"] if numero and candidate["numero"] else candidate["tutte"]
    return next(iter(scelte)) if len(scelte) == 1 else None


def scadenza_termine_lungo(pubblicazione: date, *, lavoro: bool) -> dict[str, Any]:
    """Sei mesi dal deposito col motore unico dei termini (art. 155 c.p.c. e sospensione feriale)."""
    return ItalianDeadlineCalculator().calculate(
        pubblicazione, 6, direction="forward", period_type="months", suspend_august=not lavoro,
        reference_law="Art. 327 c.p.c.",
    )


def proponi_termine_lungo(
    scadenziario: Any, *, fascicolo_id: str, comunicazione_id: str, testo: str, pubblicazione: date,
    lavoro: bool, oggi: date, origine: str,
) -> bool:
    """Bozza «termine lungo» nello scadenziario; False se c'è già o se il termine è passato."""
    from pct.scadenziario import StatoTermine, TipoTermine

    marcatore = MARCATORE.format(comunicazione=comunicazione_id)
    esistenti = scadenziario.tutte(solo_aperte=False, id_fascicolo=fascicolo_id)
    if any(marcatore in str(getattr(scadenza, "note", "") or "") for scadenza in esistenti):
        return False
    esito = scadenza_termine_lungo(pubblicazione, lavoro=lavoro)
    if esito["deadline"] < oggi.isoformat():
        return False
    azione = "Ricorso per cassazione" if _CORTE_APPELLO.search(str(testo or "")) else "Appello"
    numero = numero_sentenza(testo)
    scadenza = scadenziario.nuova(
        titolo=f"{azione} — termine lungo art. 327 c.p.c." + (f" (sentenza n. {numero})" if numero else ""),
        tipo=TipoTermine.TERMINE_PERENTORIO, data_scadenza=esito["deadline"], id_fascicolo=fascicolo_id,
        descrizione=(f"Sei mesi dal deposito della sentenza del {pubblicazione.strftime('%d/%m/%Y')}"
                     f"{'' if lavoro else ', con la sospensione feriale'}. Se la sentenza viene notificata vale il "
                     "termine breve dell'art. 325 c.p.c. dalla notifica."),
        data_decorrenza=pubblicazione.isoformat(), perentorio=True, source_event_type="deposito_sentenza",
        source_event_at=pubblicazione.isoformat(), raw_due_at=esito["rawDeadline"], legal_due_at=esito["deadline"],
    )
    scadenziario.aggiorna(
        scadenza.id, stato=StatoTermine.BOZZA.value,
        note=(f"{marcatore} deposito={pubblicazione.isoformat()}\nData di deposito letta da: {origine}. "
              "La comunicazione di cancelleria non fa decorrere il termine: verificare la data e confermare."),
    )
    return True


def completa_termini_lunghi(
    comunicazioni: Iterable[dict[str, Any]], scadenziario: Any, fatti_del_fascicolo: Any, *, oggi: date,
) -> dict[str, int]:
    """Per ogni comunicazione di deposito sentenza collegata a un fascicolo propone il termine lungo.

    `comunicazioni`: dict con `id`, `fascicolo_id`, `testo`, `lavoro`; `fatti_del_fascicolo(id)` dà i fatti letti.
    """
    esito = {"proposte": 0, "senza_data": 0}
    for comunicazione in comunicazioni:
        fascicolo_id = str(comunicazione.get("fascicolo_id") or "")
        testo = str(comunicazione.get("testo") or "")
        if not fascicolo_id:
            continue
        pubblicazione, origine = data_pubblicazione(testo), "testo della comunicazione di cancelleria"
        if pubblicazione is None:
            pubblicazione = data_pubblicazione_da_fatti(fatti_del_fascicolo(fascicolo_id), numero=numero_sentenza(testo))
            origine = "documenti del fascicolo (deposito della sentenza)"
        if pubblicazione is None:
            esito["senza_data"] += 1
            continue
        esito["proposte"] += proponi_termine_lungo(
            scadenziario, fascicolo_id=fascicolo_id, comunicazione_id=str(comunicazione.get("id") or ""),
            testo=testo, pubblicazione=pubblicazione, lavoro=bool(comunicazione.get("lavoro")), oggi=oggi,
            origine=origine,
        )
    return esito


__all__ = [
    "MARCATORE", "completa_termini_lunghi", "data_pubblicazione", "data_pubblicazione_da_fatti", "numero_sentenza",
    "proponi_termine_lungo", "scadenza_termine_lungo",
]
