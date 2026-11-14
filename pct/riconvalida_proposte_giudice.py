"""Riconvalida delle proposte nate dai provvedimenti del giudice letti nelle PEC (bozze ``PEC_TERMINE_PROPOSTO``).

Le regole di lettura dei provvedimenti si sono corrette (2.488+, collaudo del 10/11/2026, Tribunale di Vicenza
sez. lavoro); le bozze già create con le regole vecchie si ripassano qui, da sole, senza passaggi dell'avvocato:

* **Costituzione del convenuto contata da un rinvio** (``LAV_416_COSTITUZIONE``): il decreto ex art. 415 c.p.c.
  fissa la prima udienza e il convenuto si costituisce almeno dieci giorni prima di **quella** (art. 416,
  comma 1, c.p.c.), con le decadenze dei commi 2 e 3. Una bozza contata dall'udienza di rinvio del fascicolo
  è un termine che la legge non prevede: si annulla con il motivo (``coerenza_termini.motivo_416_su_rinvio``).
* **Termine della controparte** (``coerenza_termini.parte_onerata``): se il ruolo del cliente è certo e la
  bozza è a carico dell'altra parte, non è un termine dello studio: si annulla con il motivo.
* **Titolo del deposito senza oggetto** («Termine assegnato dal giudice: deposito (ricorrente)»): il titolo
  prende ciò che il provvedimento ordina di depositare, dalle parole citate nella bozza
  (``coerenza_termini.titolo_deposito``; art. 421 c.p.c. nel rito del lavoro, art. 175 c.p.c. negli altri).

Solo bozze automatiche intatte: stato BOZZA, marcatore ``PEC_TERMINE_PROPOSTO`` e titolo non scelto
dall'avvocato (``pct.scadenze_titolo_avvocato``). Le scadenze confermate, completate o annullate non si toccano.
Nulla si cancella: l'annullamento resta nello storico con la riga di traccia (art. 20 CAD).
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any

from pct.ora_italiana import ROME_TZ
from pct.provvedimenti.coerenza_termini import CONTROPARTE, motivo_416_su_rinvio, parte_onerata, titolo_deposito

logger = logging.getLogger(__name__)

MARCATORE = "PEC_TERMINE_PROPOSTO:"
MARCATORE_RICONVALIDA = "RICONVALIDA_PROPOSTA_GIUDICE"
ANNULLA, TITOLO = "annulla", "titolo"
LIMITE_PREDEFINITO = 500

_RE_DATA = r"(\d{2}/\d{2}/\d{4})"
_RE_EVENTO_PEC = re.compile(r"^[^.]*?\b(?:al|del)\s+" + _RE_DATA + r"[^.]*?comunicat[ao]\s+via\s+PEC", re.I)
_RE_CALCOLO_DA = re.compile(r"a\s+ritroso\s+dall'evento\s+del\s+" + _RE_DATA, re.I)
_RE_A_CARICO = re.compile(r"a\s+carico\s+di:\s*([^.\n]+)", re.I)
_RE_CITAZIONE = re.compile(r"Dal\s+provvedimento:\s*«([^»]+)»", re.I)
_RE_TITOLO_GENERICO = re.compile(r"^Termine assegnato dal giudice:\s*deposito\b", re.I)
_RE_RG = re.compile(r"\s-\sRG\s+\S+$")


def _valore(oggetto: Any, nome: str) -> str:
    valore = getattr(oggetto, nome, "")
    return str(getattr(valore, "value", valore) or "")


def _giorno(testo: str) -> date | None:
    try:
        return datetime.strptime(testo, "%d/%m/%Y").date()
    except (TypeError, ValueError):
        return None


def _intatta(scadenza: Any) -> bool:
    if _valore(scadenza, "stato") != "BOZZA" or MARCATORE not in _valore(scadenza, "note"):
        return False
    if MARCATORE_RICONVALIDA in _valore(scadenza, "note"):
        return False
    try:
        from pct.scadenze_titolo_avvocato import titolo_scelto_da_avvocato

        return not titolo_scelto_da_avvocato(scadenza)
    except Exception:  # pragma: no cover - provenienza illeggibile: prudenza, non si tocca
        return False


def esito_proposta(scadenza: Any, *, ruolo_cliente: str = "") -> tuple[str, str]:
    """Che cosa fare della bozza: (``annulla``, motivo), (``titolo``, nuovo titolo) oppure ("", "")."""
    if not _intatta(scadenza):
        return "", ""
    codice = _valore(scadenza, "deadline_profile_code")
    descrizione = _valore(scadenza, "descrizione")
    evento = _RE_EVENTO_PEC.search(descrizione)
    calcolo = _RE_CALCOLO_DA.search(descrizione)
    motivo = motivo_416_su_rinvio(
        codice,
        udienza_di_calcolo=_giorno(calcolo.group(1)) if calcolo else None,
        udienza_del_decreto=_giorno(evento.group(1)) if evento else None,
    )
    if motivo:
        return ANNULLA, motivo
    chi = _RE_A_CARICO.search(descrizione)
    if chi and parte_onerata(chi.group(1).strip(), ruolo_cliente) == CONTROPARTE:
        return ANNULLA, (f"Termine a carico della controparte ({chi.group(1).strip()}): lo studio assiste il "
                         f"{ruolo_cliente}, non è un termine dello studio.")
    titolo = _valore(scadenza, "titolo")
    citazione = _RE_CITAZIONE.search(descrizione)
    if codice == "PROVV_DEPOSITO" and _RE_TITOLO_GENERICO.search(titolo) and citazione:
        nuovo = titolo_deposito(citazione.group(1), chi.group(1).strip() if chi else "")
        if nuovo:
            rg = _RE_RG.search(titolo)
            return TITOLO, (nuovo + (rg.group(0) if rg else ""))[:180]
    return "", ""


def riconvalida_proposte_giudice(scadenziario: Any, *, ruoli: dict[str, str] | None = None,
                                 limite: int = LIMITE_PREDEFINITO) -> dict[str, Any]:
    """Applica ``esito_proposta`` alle bozze dello scadenziario, a lotti; idempotente.

    ``ruoli``: fascicolo → ruolo certo del cliente («ricorrente»/«resistente»), se il chiamante lo conosce.
    """
    from pct.scadenziario import StatoTermine

    ruoli = ruoli or {}
    esito: dict[str, Any] = {"annullate": 0, "titoli": 0, "restanti": 0, "errori": 0, "ids": []}
    for scadenza in list(scadenziario.bozze()):
        azione, dettaglio = esito_proposta(scadenza, ruolo_cliente=ruoli.get(_valore(scadenza, "id_fascicolo"), ""))
        if not azione:
            continue
        if esito["annullate"] + esito["titoli"] >= max(0, limite):
            esito["restanti"] += 1
            continue
        id_sc = _valore(scadenza, "id")
        note = _valore(scadenza, "note")
        adesso = datetime.now(ROME_TZ).replace(tzinfo=None, microsecond=0)
        try:
            if azione == ANNULLA:
                scadenziario.aggiorna(id_sc, stato=StatoTermine.ANNULLATO, completata_il=adesso.isoformat(),
                                      note=f"{note}\n{MARCATORE_RICONVALIDA}: proposta annullata il {adesso:%d/%m/%Y}: {dettaglio}".strip())
                esito["annullate"] += 1
            else:
                scadenziario.aggiorna(id_sc, titolo=dettaglio,
                                      note=f"{note}\n{MARCATORE_RICONVALIDA}: titolo precisato il {adesso:%d/%m/%Y} con "
                                           f"l'oggetto del deposito scritto nel provvedimento.".strip())
                esito["titoli"] += 1
            esito["ids"].append(id_sc)
        except Exception:  # una bozza non aggiornabile non blocca le altre
            esito["errori"] += 1
            logger.exception("[riconvalida proposte giudice] bozza %s non aggiornata", id_sc)
    esito["ids"] = esito["ids"][:50]
    return esito


__all__ = ["ANNULLA", "MARCATORE_RICONVALIDA", "TITOLO", "esito_proposta", "riconvalida_proposte_giudice"]
