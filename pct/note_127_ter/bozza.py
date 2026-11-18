"""Dati e testo iniziale delle note ricavati dai riscontri già salvati."""

from collections import Counter
from datetime import date, time
import re
from typing import Any, Callable

from pct.formatting import format_date_it

MODALITA_NOTE = "sostituita da note scritte (art. 127-ter c.p.c.)"
SEGNAPOSTI_NOTE = {
    "ufficio giudiziario": "[Ufficio giudiziario]",
    "numero e anno di ruolo": "[Numero e anno]",
    "parte assistita": "[Parte assistita da identificare]",
    "difensore costituito": "[Indicare il difensore costituito]",
    "parte resistente": "[Parte resistente da identificare nell’atto introduttivo]",
    "istanze e conclusioni": "[Riprendere le sole istanze e conclusioni dell’atto introduttivo e degli scritti successivi pertinenti.]",
    "data dell’atto": "[Data dell’atto]",
}
CAMPI_NOTE_EDITOR = {
    "note_127ter.ruolo": ("Numero e anno di ruolo", "rg"),
    "note_127ter.sezione": ("Sezione del provvedimento", "sezione"),
    "note_127ter.parte_assistita": ("Parte assistita", "parte"),
    "note_127ter.difensore": ("Difensore costituito", "difensore"),
    "note_127ter.controparte": ("Parte resistente", "controparte"),
    "note_127ter.difesa_controparte": ("Difesa della parte resistente", "difensore_controparte"),
    "note_127ter.udienza": ("Udienza sostituita dalle note", "udienza_sostituita"),
    "note_127ter.termine": ("Termine di deposito delle note", "termine_deposito"),
}
_TITOLO_PROVVEDIMENTO = re.compile(r"\b(?:decreto|ordinanza|provvedimento|sentenza)\b", re.I)
_UFFICIO_NELL_INTESTAZIONE = re.compile(r"\b(?:tribunale|corte|giudice di pace)\b", re.I)
_SEZIONE_INTESTAZIONE = re.compile(
    r"\bsezione\s+((?:(?:prima|seconda|terza|quarta|quinta|sesta|settima|ottava|nona|decima|[IVX]{1,6}|\d{1,2})"
    r"(?:\s+(?:civile|lavoro|penale))?|(?:civile|lavoro|penale)))\s*$", re.I,
)


def sezione_del_provvedimento(testo: str) -> str:
    """Riprende la sezione dall'intestazione, anche quando l'indice ha appiattito le righe."""
    intestazione = " ".join(testo[:1000].split())
    titolo = _TITOLO_PROVVEDIMENTO.search(intestazione)
    if not titolo:
        return ""
    prima_del_titolo = intestazione[:titolo.start()]
    sezione = _SEZIONE_INTESTAZIONE.search(prima_del_titolo)
    if not sezione or not _UFFICIO_NELL_INTESTAZIONE.search(prima_del_titolo[:sezione.start()]):
        return ""
    denominazione = sezione.group(1)
    return "Sezione " + (denominazione.upper() if re.fullmatch(r"[IVX]{1,6}", denominazione, re.I) else denominazione.title())


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


def campi_note_mancanti(testo: str) -> list[str]:
    normalizzato = " ".join(testo.replace("’", "'").split()).casefold()
    campi = [nome for nome, segnaposto in SEGNAPOSTI_NOTE.items()
             if segnaposto.replace("’", "'").casefold() in normalizzato]
    if "[data e firma del difensore]" in normalizzato and "data dell’atto" not in campi:
        campi.append("data dell’atto")
    return campi


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
    associa: Callable[[str, str], str] | None = None,
) -> str:
    """Schema dell'atto, con istanze e conclusioni riservate al difensore."""
    def valore(chiave: str, testo: str) -> str:
        return associa(chiave, testo) if associa is not None else testo

    termine = valore("note_127ter.termine", termine_nelle_note(proposta))
    righe = [f"# {valore('fascicolo.tribunale', ufficio or SEGNAPOSTI_NOTE['ufficio giudiziario'])}"]
    if sezione:
        denominazione = sezione if sezione.casefold().startswith("sezione ") else f"Sezione {sezione}"
        righe.append(f"## {valore('note_127ter.sezione', denominazione)}")
    if giudice:
        righe.append(f"*Giudice: {valore('fascicolo.giudice', giudice)}*")
    if udienza := proposta.get("udienza_sostituita"):
        righe.append(f"*Udienza del {valore('note_127ter.udienza', format_date_it(udienza))}*")
    righe.extend((
        "## Note per la trattazione scritta ex art. 127-ter c.p.c.",
        f"**R.G. {valore('note_127ter.ruolo', rg or SEGNAPOSTI_NOTE['numero e anno di ruolo'])}**",
        "**Per**",
        valore("note_127ter.parte_assistita", parte or SEGNAPOSTI_NOTE["parte assistita"]),
        f"Difensore: {valore('note_127ter.difensore', difensore or SEGNAPOSTI_NOTE['difensore costituito'])}",
        "**contro**",
        valore("note_127ter.controparte", controparte or SEGNAPOSTI_NOTE["parte resistente"]),
    ))
    if difensore_controparte:
        righe.append(f"Difesa indicata nel fascicolo: {valore('note_127ter.difesa_controparte', difensore_controparte)}.")
    righe.extend((
        f"Termine per il deposito delle note, che vale come data d’udienza: {termine}.",
        "### Istanze e conclusioni",
        SEGNAPOSTI_NOTE["istanze e conclusioni"],
        valore("documento.data_atto", SEGNAPOSTI_NOTE["data dell’atto"]),
    ))
    return "\n\n".join(righe)


def testo_note_studio(associa: Callable[[str, str], str]) -> str:
    """Struttura grafica delle note di studio già depositate, con soli campi del nuovo fascicolo."""
    def campo(chiave: str, etichetta: str) -> str:
        return associa(chiave, f"[{etichetta}]")

    difensore = campo("note_127ter.difensore", "Difensore costituito")
    return "\n\n".join((
        f"# {campo('fascicolo.tribunale', 'Ufficio giudiziario')}",
        f"## {campo('note_127ter.sezione', 'Sezione del provvedimento')}",
        f"*{campo('fascicolo.giudice', 'Giudice')}*",
        f"*Udienza del {campo('note_127ter.udienza', 'Udienza sostituita dalle note')}*",
        "## Trattazione scritta",
        f"**R.G. {campo('note_127ter.ruolo', 'Numero e anno di ruolo')}**",
        "**Per**",
        f"**{campo('note_127ter.parte_assistita', 'Parte assistita')}**, c.f. "
        f"{campo('cliente.codice_fiscale', 'Codice fiscale')}, "
        f"difensore {difensore}, con recapiti dello studio "
        f"{campo('studio_timbro.riga_recapiti', 'Recapiti e PEC configurata')}.",
        "**contro**",
        f"**{campo('note_127ter.controparte', 'Parte resistente')}**, "
        f"difesa indicata nel fascicolo {campo('note_127ter.difesa_controparte', 'Difesa della parte resistente')}.",
        f"OGGETTO: {campo('fascicolo.oggetto', 'Oggetto')}",
        "✻✻✻✻✻✻✻✻✻✻✻✻✻",
        f"In osservanza del provvedimento di trattazione scritta ai sensi dell’art. 127-ter c.p.c., "
        f"con termine per il deposito al {campo('note_127ter.termine', 'Termine di deposito delle note')}, "
        "si formulano le seguenti istanze e conclusioni.",
        "### CONCLUSIONI",
        SEGNAPOSTI_NOTE["istanze e conclusioni"],
        f"{campo('studio.citta', 'Comune studio')}, {campo('documento.data_atto', 'Data dell’atto')} | {difensore}",
    ))
