"""Udienze superate da un provvedimento successivo: chiusura con traccia, mai doppioni.

Caso reale (fascicolo di lavoro, Tribunale di Palmi, RG 910/2026): il decreto di fissazione porta
l'udienza al 14/09/2027; un decreto successivo la **anticipa** al 15/12/2026; poi la cancelleria
comunica che l'udienza è **revocata** e sostituita dal termine per le note scritte del 15/12/2026
(art. 127-ter c.p.c.). Lo scadenziario teneva aperte tutte e tre le voci, come se ci fossero tre
udienze. Qui si decide, senza I/O, quali voci automatiche dello stesso fascicolo il nuovo
provvedimento supera:

* **anticipazione** (art. 81 disp. att. c.p.c.; art. 175 c.p.c.): l'udienza successiva alla nuova data;
* **rinvio o differimento** (artt. 81 e 82 disp. att. c.p.c.): l'udienza precedente alla nuova data;
* **revoca** dell'udienza con nuova data: l'unica altra udienza futura del fascicolo;
* **note in sostituzione** (art. 127-ter c.p.c.): l'udienza dello stesso giorno, sostituita dal
  termine perentorio per le note (il giorno di scadenza vale come data di udienza).

Fail-closed: si chiudono solo voci create in automatico (lettura di PEC o documenti), mai quelle
inserite o confermate dall'avvocato; se le candidate cadono in più giorni diversi non si sceglie
(«verificare quale udienza è superata»). Ogni chiusura porta la riga di traccia con l'origine.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

TRACCIA_PREFISSO = "UDIENZA_SUPERATA"
ANTICIPATA = "anticipata"
RINVIATA = "rinviata"
REVOCATA = "revocata"
NOTE_127_TER = "note_127_ter"

ETICHETTE = {
    ANTICIPATA: "anticipata",
    RINVIATA: "rinviata",
    REVOCATA: "revocata",
    NOTE_127_TER: "sostituita da note scritte (art. 127-ter c.p.c.)",
}

_CAMBI: tuple[tuple[str, re.Pattern[str]], ...] = (
    (ANTICIPATA, re.compile(r"\banticipa\w*\b.{0,40}\budienz|\budienz\w*\b.{0,40}\banticipat", re.I)),
    (RINVIATA, re.compile(
        r"\b(?:rinvi(?:o|a|at[oaie])|differi\w*|posticipa\w*|spostament\w*|spostat[oa])\b.{0,40}\budienz"
        r"|\budienz\w*\b.{0,40}\b(?:rinviat|differit|posticipat|spostat)",
        re.I,
    )),
    (REVOCATA, re.compile(r"\brevoc\w*\s+(?:dell['’]\s*|l['’]\s*)?udienz", re.I)),
)
#: voci create in automatico dalla lettura di PEC e documenti (pct.pec_pipeline, archivio delle letture)
_AUTOMATICA = ("PEC_AUDIT:", "Creata dalla lettura automatica")


def cambio_da_testo(*testi: Any) -> str:
    """Il cambio d'udienza che il testo dispone («decreto anticipazione udienza», «rinvia l'udienza»…)."""
    testo = " ".join(" ".join(str(t or "").split()) for t in testi)
    return next((nome for nome, regola in _CAMBI if regola.search(testo)), "")


def _campo(voce: Any, nome: str) -> str:
    valore = voce.get(nome) if isinstance(voce, dict) else getattr(voce, nome, "")
    return str(getattr(valore, "value", valore) or "").strip()


def _giorno(voce: Any) -> date | None:
    try:
        return date.fromisoformat(_campo(voce, "data_scadenza")[:10])
    except ValueError:
        return None


def e_automatica(voce: Any) -> bool:
    nota = _campo(voce, "note")
    return any(segno in nota for segno in _AUTOMATICA)


@dataclass(frozen=True)
class Esito:
    voci: tuple[Any, ...]
    motivo: str


def udienze_superate(
    scadenze: Iterable[Any],
    *,
    fascicolo_id: str,
    nuova_data: date,
    cambio: str,
    oggi: date,
    escludi: Iterable[str] = (),
) -> Esito:
    """Le voci UDIENZA aperte dello stesso fascicolo che il provvedimento supera."""
    if not fascicolo_id or cambio not in ETICHETTE:
        return Esito((), "")
    esclusi = {str(i) for i in escludi if i}
    candidate: list[tuple[date, Any]] = []
    for voce in scadenze or []:
        if _campo(voce, "id") in esclusi or _campo(voce, "id_fascicolo") != fascicolo_id:
            continue
        if _campo(voce, "tipo").upper() != "UDIENZA" or _campo(voce, "stato").upper() != "APERTO":
            continue
        if not e_automatica(voce) or TRACCIA_PREFISSO in _campo(voce, "note"):
            continue
        giorno = _giorno(voce)
        if giorno is None or giorno < oggi:
            continue
        if cambio == ANTICIPATA and giorno > nuova_data:
            candidate.append((giorno, voce))
        elif cambio == RINVIATA and giorno < nuova_data:
            candidate.append((giorno, voce))
        elif cambio == REVOCATA and giorno != nuova_data:
            candidate.append((giorno, voce))
        elif cambio == NOTE_127_TER and giorno == nuova_data:
            candidate.append((giorno, voce))
    if not candidate:
        return Esito((), "nessuna udienza superata nello scadenziario del fascicolo")
    giorni = {giorno for giorno, _voce in candidate}
    if len(giorni) > 1:
        elenco = ", ".join(f"{g:%d/%m/%Y}" for g in sorted(giorni))
        return Esito((), f"più udienze candidate ({elenco}): verificare quale è superata")
    return Esito(tuple(voce for _giorno_voce, voce in candidate), f"udienza del {min(giorni):%d/%m/%Y} {ETICHETTE[cambio]}")


def riga_traccia(*, origine: str, cambio: str, nuova_data: date, nuova_voce: str = "") -> str:
    """La riga che resta nella voce chiusa: chi l'ha superata, come e con quale nuova data."""
    seguito = f", sostituita dalla voce {nuova_voce}" if nuova_voce else ""
    return (
        f"{TRACCIA_PREFISSO}:{origine} Udienza {ETICHETTE.get(cambio, cambio)}: nuova data {nuova_data:%d/%m/%Y}"
        f"{seguito}. Chiusa in automatico dal provvedimento successivo; riaprirla se non è superata."
    )


__all__ = [
    "ANTICIPATA", "ETICHETTE", "Esito", "NOTE_127_TER", "REVOCATA", "RINVIATA", "TRACCIA_PREFISSO",
    "cambio_da_testo", "e_automatica", "riga_traccia", "udienze_superate",
]
