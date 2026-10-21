"""Scadenze delle schede consegnate a Lex già calcolate, e controllo della risposta.

Le scadenze le calcola il software (``pct/schede_termini.py``: art. 155 c.p.c., L. 742/1969); Lex le riceve nel
messaggio come dato e deve riportarle identiche. Sul banco di prova del pilota (ottobre 2026) tutti gli errori del
modello erano date ricalcolate con uno o tre giorni di scarto: per questo la data non si chiede mai al modello e
la risposta viene controllata prima di mostrarla all'avvocato.
"""
from __future__ import annotations

import re
from typing import Any

INTESTAZIONE = "Scadenze calcolate dal software (riportale identiche, non ricalcolarle):"
DATA = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def scadenze_calcolate(risolta: dict[str, Any]) -> list[dict[str, Any]]:
    """Le scadenze che il software ha calcolato per la scheda risolta.

    Un «primo giorno utile» (termine dilatorio) non scade: passato quel giorno l’atto si può compiere.
    """
    return [{"campo": c["campo"], "etichetta": c["etichetta"], "valore": c["valore"], "spiegazione": c.get("spiegazione", ""),
             "scaduto": bool(c.get("scaduto")) and not c["etichetta"].lower().startswith("primo giorno"),
             "verifica_avvocato": bool(c.get("verifica_avvocato"))}
            for c in risolta.get("campi", []) if c.get("stato") == "calcolato" and c.get("valore")]


def blocco_scadenze(risolta: dict[str, Any]) -> str:
    """Sezione del messaggio per Lex con le scadenze già pronte; vuota se non ce ne sono."""
    righe = []
    for s in scadenze_calcolate(risolta):
        riga = f"- {s['etichetta']}: {s['valore']}"
        if s["spiegazione"]:
            riga += f" ({s['spiegazione']})"
        if s["verifica_avvocato"]:
            riga += " — calcolo da verificare con la fonte: non presentarlo come confermato"
        if s["scaduto"]:
            riga += " — termine già scaduto"
        righe.append(riga)
    return "\n".join([INTESTAZIONE, *righe]) if righe else ""


def _normalizza(data: re.Match) -> str:
    g, m, a = data.groups()
    return f"{int(g):02d}/{int(m):02d}/{a}"


def controlla_risposta(risposta: str, risolta: dict[str, Any], messaggio: str = "") -> dict[str, Any]:
    """Scadenze calcolate assenti dalla risposta e date che non vengono né dal messaggio né dal calcolo."""
    attese = {s["valore"] for s in scadenze_calcolate(risolta)}
    presenti = {_normalizza(m) for m in DATA.finditer(risposta)}
    note = {_normalizza(m) for m in DATA.finditer(messaggio)} | attese
    return {"mancanti": sorted(attese - presenti), "estranee": sorted(presenti - note),
            "ok": attese <= presenti and presenti <= note}


def ripara_risposta(risposta: str, risolta: dict[str, Any], messaggio: str = "") -> str:
    """Se il modello ha omesso o cambiato una scadenza, la risposta riporta in coda quelle del software."""
    esito = controlla_risposta(risposta, risolta, messaggio)
    if esito["ok"]:
        return risposta
    blocco = blocco_scadenze(risolta).replace(INTESTAZIONE, "Scadenze calcolate dal software (prevalgono su date diverse indicate sopra):")
    avviso = ""
    if esito["estranee"]:
        avviso = "\nDate da verificare perché non risultano dai dati né dal calcolo: " + ", ".join(esito["estranee"]) + "."
    return f"{risposta.rstrip()}\n\n{blocco}{avviso}" if blocco else f"{risposta.rstrip()}{avviso}"
