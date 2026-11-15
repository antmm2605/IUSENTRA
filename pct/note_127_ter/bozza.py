"""Dati e testo iniziale delle note ricavati dai riscontri già salvati."""

from collections import Counter
from datetime import date
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
        })
    per_giorno = Counter(voce["termine"] for voce in proposte)
    return sorted(
        (voce for voce in proposte if per_giorno[voce["termine"]] == 1),
        key=lambda voce: voce["termine"],
    )


def testo_note(
    proposta: dict[str, str],
    *,
    ufficio: str,
    rg: str,
    giudice: str,
    parte: str,
    controparte: str,
    difensore: str,
) -> str:
    """Schema dell'atto, con istanze e conclusioni riservate al difensore."""
    termine = format_date_it(proposta["termine"])
    righe = [
        f"# {ufficio or '[Ufficio giudiziario]'}",
        f"R.G. {rg or '[Numero e anno]'}",
        f"Giudice: {giudice or '[Indicare il giudice]'}",
        "## Note per la trattazione scritta ex art. 127-ter c.p.c.",
        f"Parte assistita: {parte or '[Indicare la parte assistita]'}",
        f"Difensore: {difensore or '[Indicare il difensore costituito]'}",
        f"Controparte: {controparte or '[Indicare la controparte]'}",
    ]
    if udienza := proposta.get("udienza_sostituita"):
        righe.append(f"Udienza sostituita indicata nel provvedimento: {udienza}.")
    righe.extend((
        f"Termine per il deposito delle note, che vale come data d’udienza: {termine}.",
        "### Istanze e conclusioni",
        "[Inserire le sole istanze e conclusioni relative all’udienza sostituita.]",
        "[Data e firma del difensore]",
    ))
    return "\n\n".join(righe)
