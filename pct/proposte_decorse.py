"""Proposte di scadenza mai confermate il cui termine è già decorso.

Le date lette dalle PEC e dai registri entrano nello scadenziario come proposte in BOZZA e
diventano operative solo con la conferma dell'avvocato. Quando il giorno del termine è già
passato (fuso Europe/Rome) la proposta non è più azionabile: chiederne la conferma come se
fosse una scadenza futura è fuorviante.

Base normativa:
- artt. 152-155 c.p.c.: i termini processuali si computano a giorni e il termine scade con
  l'ultimo giorno utile (art. 155); decorso quel giorno l'atto non è più tempestivo. I termini
  perentori non sono prorogabili (art. 153) e il loro mancato rispetto produce decadenza;
- art. 127-ter c.p.c.: l'opposizione alla trattazione scritta va proposta entro cinque giorni
  dalla comunicazione (comma 2) e le note si depositano entro il termine assegnato, che vale
  come data dell'udienza (comma 1). Decorsi, la proposta non ha più oggetto.

Regola prudente (nulla si cancella, nulla si conferma al posto dell'avvocato):
- proposta in BOZZA con termine futuro o senza data leggibile: invariata;
- proposta 127-ter decorsa (opposizione o note scritte): chiusa come «superata», con la riga
  di traccia nelle note e il marcatore ``PROPOSTA_SUPERATA``;
- proposta perentoria decorsa il cui mancato rispetto produce decadenza (impugnazioni,
  costituzione, decadenze, prescrizioni, termini perentori): resta in BOZZA, marcata
  ``PROPOSTA_DECORSA_DA_VERIFICARE``, e si mostra nel gruppo «Termini proposti già decorsi —
  verifica dell'avvocato», mai fra le urgenze;
- ogni altra proposta decorsa: chiusa come «superata».
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from pct.ora_italiana import ROME_TZ, giorno_italiano, oggi_roma

logger = logging.getLogger(__name__)

MARCATORE_SUPERATA = "PROPOSTA_SUPERATA"
MARCATORE_DA_VERIFICARE = "PROPOSTA_DECORSA_DA_VERIFICARE"
AZIONABILE, SUPERATA, DA_VERIFICARE = "azionabile", "superata", "da_verificare"
GRUPPO_DA_VERIFICARE = "Termini proposti già decorsi — verifica dell'avvocato"

CODICI_127_TER = frozenset({"CIV_OPPOSIZIONE_127_TER", "NOTE_127_TER"})
_RE_127_TER = re.compile(r"127\s*-?\s*ter|trattazione\s+scritta|note\s+scritte", re.I)
#: tipi il cui mancato rispetto comporta la perdita del potere o del diritto (art. 153 c.p.c.)
TIPI_CON_DECADENZA = frozenset({"IMPUGNAZIONE", "DECADENZA", "PRESCRIZIONE", "TERMINE_PERENTORIO"})
_RE_DECADENZA = re.compile(r"costituzion|impugnaz|appello|cassazione|reclamo|revocazion|decadenz", re.I)
LIMITE_PREDEFINITO = 500


def _valore(oggetto: Any, nome: str) -> str:
    valore = getattr(oggetto, nome, "")
    return str(getattr(valore, "value", valore) or "")


def giorno_termine(scadenza: Any) -> date | None:
    """Il giorno del termine in ora italiana; ``None`` se la data non è leggibile."""
    for campo in ("data_scadenza", "legal_due_at"):
        testo = giorno_italiano(_valore(scadenza, campo))
        try:
            return date.fromisoformat(testo[:10])
        except ValueError:
            continue
    return None


def e_127_ter(scadenza: Any) -> bool:
    """Opposizione alla trattazione scritta o deposito delle note (art. 127-ter c.p.c.)."""
    if _valore(scadenza, "deadline_profile_code").upper() in CODICI_127_TER:
        return True
    note = _valore(scadenza, "note")
    if any(f":{codice}" in note for codice in CODICI_127_TER):
        return True
    return _valore(scadenza, "tipo") != "UDIENZA" and bool(_RE_127_TER.search(_valore(scadenza, "titolo")))


def produce_decadenza(scadenza: Any) -> bool:
    """Termine perentorio il cui mancato rispetto produce decadenza: lo giudica l'avvocato."""
    tipo = _valore(scadenza, "tipo")
    if tipo == "UDIENZA" or e_127_ter(scadenza):
        return False
    return (
        tipo in TIPI_CON_DECADENZA
        or bool(getattr(scadenza, "perentorio", False))
        or bool(_RE_DECADENZA.search(_valore(scadenza, "titolo")))
    )


def classifica(scadenza: Any, oggi: date | None = None) -> str:
    """``azionabile`` (da confermare), ``superata`` o ``da_verificare`` per una proposta in BOZZA."""
    giorno = giorno_termine(scadenza)
    if _valore(scadenza, "stato") != "BOZZA" or giorno is None or giorno >= (oggi or oggi_roma()):
        return AZIONABILE
    return DA_VERIFICARE if produce_decadenza(scadenza) else SUPERATA


def dividi_proposte(bozze: Iterable[Any], oggi: date | None = None) -> tuple[list[Any], list[Any]]:
    """(da confermare, decorse da verificare); le superate in attesa di chiusura non si mostrano."""
    oggi = oggi or oggi_roma()
    azionabili: list[Any] = []
    da_verificare: list[Any] = []
    for voce in bozze:
        esito = classifica(voce, oggi)
        if esito == AZIONABILE:
            azionabili.append(voce)
        elif esito == DA_VERIFICARE:
            da_verificare.append(voce)
    return azionabili, da_verificare


def riga_superata(scadenza: Any, oggi: date) -> str:
    giorno = giorno_termine(scadenza)
    norma = "art. 127-ter c.p.c.; artt. 152-155 c.p.c." if e_127_ter(scadenza) else "artt. 152-155 c.p.c."
    return (f"{MARCATORE_SUPERATA}: Termine decorso senza conferma: proposta superata il {oggi:%d/%m/%Y} "
            f"(termine proposto per il {giorno:%d/%m/%Y}; {norma}).")


def riga_da_verificare(scadenza: Any) -> str:
    giorno = giorno_termine(scadenza)
    return (f"{MARCATORE_DA_VERIFICARE}: Termine proposto decorso il {giorno:%d/%m/%Y} senza conferma: verificare se "
            "l'atto è stato compiuto in tempo o se è maturata una decadenza (artt. 152-155 c.p.c.).")


def riconvalida_proposte_decorse(scadenziario: Any, *, oggi: date | None = None,
                                 limite: int = LIMITE_PREDEFINITO) -> dict[str, Any]:
    """Applica la regola alle proposte esistenti, a lotti; idempotente.

    Una proposta superata passa ad ANNULLATO (resta nello storico con la riga di traccia); una
    proposta da verificare resta in BOZZA e riceve una sola volta il marcatore. ``restanti``
    conta le proposte rinviate al giro successivo perché il lotto è pieno.
    """
    from pct.scadenziario import StatoTermine

    oggi = oggi or oggi_roma()
    esito: dict[str, Any] = {"superate": 0, "da_verificare": 0, "restanti": 0, "errori": 0, "ids_superate": []}
    for scadenza in list(scadenziario.bozze()):
        stato = classifica(scadenza, oggi)
        note = _valore(scadenza, "note")
        if stato == AZIONABILE or (stato == DA_VERIFICARE and MARCATORE_DA_VERIFICARE in note):
            continue
        if esito["superate"] + esito["da_verificare"] >= max(0, limite):
            esito["restanti"] += 1
            continue
        id_sc = _valore(scadenza, "id")
        try:
            if stato == SUPERATA:
                scadenziario.aggiorna(
                    id_sc, stato=StatoTermine.ANNULLATO, completata_il=datetime.now(ROME_TZ).replace(tzinfo=None, microsecond=0).isoformat(),
                    note=f"{note}\n{riga_superata(scadenza, oggi)}".strip(),
                )
                esito["superate"] += 1
                esito["ids_superate"].append(id_sc)
                logger.info("[proposte decorse] proposta %s superata (termine %s)", id_sc, giorno_termine(scadenza))
            else:
                scadenziario.aggiorna(id_sc, note=f"{note}\n{riga_da_verificare(scadenza)}".strip())
                esito["da_verificare"] += 1
                logger.info("[proposte decorse] proposta %s decorsa da verificare", id_sc)
        except Exception:  # una proposta non aggiornabile non blocca le altre
            esito["errori"] += 1
            logger.exception("[proposte decorse] proposta %s non aggiornata", id_sc)
    esito["ids_superate"] = esito["ids_superate"][:50]
    return esito


__all__ = [
    "AZIONABILE", "DA_VERIFICARE", "GRUPPO_DA_VERIFICARE", "MARCATORE_DA_VERIFICARE", "MARCATORE_SUPERATA",
    "SUPERATA", "classifica", "dividi_proposte", "e_127_ter", "giorno_termine", "produce_decadenza",
    "riconvalida_proposte_decorse",
]


#: margine massimo fra comunicazione e termine di opposizione: 5 giorni (art. 127-ter, comma 2,
#: c.p.c.), proroga al primo giorno non festivo (art. 155 c.p.c.) e sospensione feriale dal 1° al
#: 31 agosto (art. 1 L. 742/1969). Oltre questo margine la data registrata non può essere giusta.
MARGINE_OPPOSIZIONE_127_TER_GIORNI = 45


def opposizione_127_ter_incoerente(scadenza: Any) -> bool:
    """Opposizione alla trattazione scritta con data lontana dalla comunicazione da cui decorre.

    Il termine è di cinque giorni dalla comunicazione (art. 127-ter, comma 2, c.p.c.): una data
    a mesi di distanza è quasi sempre la data dell'udienza sostituita letta al posto del termine.
    Non si corregge nulla: la voce va segnalata come «data da verificare».
    """
    codice = _valore(scadenza, "deadline_profile_code").upper()
    titolo = _valore(scadenza, "titolo").lower()
    if codice != "CIV_OPPOSIZIONE_127_TER" and not ("opposizion" in titolo and _RE_127_TER.search(titolo)):
        return False
    giorno = giorno_termine(scadenza)
    if giorno is None:
        return False
    for campo in ("data_decorrenza", "source_event_at", "creata_il"):
        testo = giorno_italiano(_valore(scadenza, campo))
        try:
            base = date.fromisoformat(testo[:10])
        except ValueError:
            continue
        return (giorno - base).days > MARGINE_OPPOSIZIONE_127_TER_GIORNI
    return False
