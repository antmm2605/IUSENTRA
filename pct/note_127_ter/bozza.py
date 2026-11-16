"""Dati e testo iniziale delle note ricavati dai riscontri già salvati."""

from collections import Counter
from datetime import date, time
from typing import Any

from pct.formatting import format_date_it

MODALITA_NOTE = "sostituita da note scritte (art. 127-ter c.p.c.)"


def proposte_note(lettura: dict[str, Any] | None, oggi: date) -> list[dict[str, str]]:
    if not lettura or lettura.get("aggiornamento_pendente"):
        return []
    if (lettura.get("stato_passi") or {}).get("attivi") is False:
        return []
    quadro = lettura.get("ragionamento") or {}
    if not quadro.get("impronta"):
        return []
    proposte = []
    for voce in quadro.get("conclusioni") or ():
        if (
            voce.get("codice") != "note_127ter"
            or voce.get("stato") != "da_fare"
            or voce.get("onerato_codice") not in {"noi", "tutte_le_parti"}
            or voce.get("dubbi")
        ):
            continue
        fonte = voce.get("letto") or {}
        data = (voce.get("termine") or {}).get("scadenza_iso") or ""
        if not fonte.get("documento_id") or fonte.get("tipo") != "documento":
            continue
        try:
            termine = date.fromisoformat(data)
        except ValueError:
            continue
        if termine < oggi:
            continue
        udienze = {
            u["data"] for u in quadro.get("udienze") or ()
            if u.get("documento_id") == fonte["documento_id"]
            and u.get("modalita") == MODALITA_NOTE and u.get("data")
        }
        data_sostituita = next(iter(udienze)) if len(udienze) == 1 else ""
        proposte.append({
            "termine": termine.isoformat(),
            "udienza_sostituita": data_sostituita,
            "documento_id": fonte["documento_id"],
            "documento": fonte.get("documento") or "",
            "titolo": "Note per la trattazione scritta",
            **({"ora": voce["termine"]["ora_assegnata"]} if voce["termine"].get("ora_assegnata") else {}),
        })
    per_giorno = Counter(voce["termine"] for voce in proposte)
    return sorted(
        (voce for voce in proposte if per_giorno[voce["termine"]] == 1),
        key=lambda voce: voce["termine"],
    )


def termine_nelle_note(proposta: dict[str, str]) -> str:
    giorno = format_date_it(proposta["termine"])
    ora = (proposta.get("ora") or "").replace(".", ":")
    if not ora:
        return giorno
    try:
        return f"{giorno} entro le ore {time.fromisoformat(ora):%H:%M}"
    except ValueError:
        return giorno


def testo_note(
    proposta: dict[str, str],
    *,
    ufficio: str,
    rg: str,
    giudice: str,
    parte: str,
    controparte: str,
    difensore: str,
    difensore_controparte: str = "",
    sezione: str = "",
) -> str:
    """Schema dell'atto, con istanze e conclusioni riservate al difensore."""
    termine = termine_nelle_note(proposta)
    righe = [f"# {ufficio or '[Ufficio giudiziario]'}"]
    if sezione:
        denominazione = sezione if sezione.casefold().startswith("sezione ") else f"Sezione {sezione}"
        righe.append(f"## {denominazione}")
    if giudice:
        righe.append(f"*Giudice: {giudice}*")
    if udienza := proposta.get("udienza_sostituita"):
        righe.append(f"*Udienza del {udienza}*")
    righe.extend((
        "## Note per la trattazione scritta ex art. 127-ter c.p.c.",
        f"**R.G. {rg or '[Numero e anno]'}**",
        "**Per**",
        parte or "[Parte assistita da identificare]",
        f"Difensore: {difensore or '[Indicare il difensore costituito]'}",
        "**contro**",
        controparte or "[Parte resistente da identificare nell’atto introduttivo]",
    ))
    if difensore_controparte:
        righe.append(f"Difesa indicata nel fascicolo: {difensore_controparte}.")
    righe.extend((
        f"Termine per il deposito delle note, che vale come data d’udienza: {termine}.",
        "### Istanze e conclusioni",
        "[Riprendere le sole istanze e conclusioni dell’atto introduttivo e degli scritti successivi pertinenti.]",
        "[Data e firma del difensore]",
    ))
    return "\n\n".join(righe)
