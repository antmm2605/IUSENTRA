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


# --- Decisione del software e messaggio per Lex ------------------------------------------------------------
# Banco v2 (21/10/2026, 23 schede mai viste in addestramento): con le scadenze già calcolate il modello le
# riporta tutte giuste, ma non si astiene quando manca un documento obbligatorio (0 su 12) e inventa le domande
# (47 su 304 coincidono con la scheda). Per questo domande e astensione le decide il software dalla scheda;
# Lex riceve la scheda risolta e scrive soltanto i blocchi di testo dell'atto.

ASTENSIONE = "non determinabile con le fonti disponibili"
MANCANTE = "[DATO MANCANTE: {}]"


def mancanti_bloccanti(risolta: dict[str, Any]) -> list[dict[str, str]]:
    """Dati obbligatori senza i quali la scheda prescrive l'astensione («se manca: astensione…»)."""
    out = []
    for d in risolta.get("domande", []):
        motivo = str(d.get("se_manca", ""))
        if d.get("obbligatorio") and motivo.lower().startswith("astensione"):
            etichetta = next((c["etichetta"] for c in risolta.get("campi", []) if c["campo"] == d["campo"]), d["campo"])
            out.append({"campo": d["campo"], "etichetta": etichetta, "motivo": motivo.split(":", 1)[-1].strip()})
    return out


def decisione(risolta: dict[str, Any]) -> dict[str, Any]:
    """Cosa fa la redazione guidata: astenersi, chiedere i dati obbligatori o far scrivere Lex.

    Le domande sono quelle della scheda, nell'ordine della scheda: Lex non ne aggiunge e non ne toglie.
    """
    bloccanti = mancanti_bloccanti(risolta)
    if bloccanti:
        elenco = "; ".join(f"{b['etichetta']} ({b['motivo']})" for b in bloccanti)
        return {"esito": "astensione", "messaggio": f"Redazione {ASTENSIONE}: manca {elenco}.",
                "bloccanti": bloccanti, "domande": risolta.get("domande", []), "scadenze": scadenze_calcolate(risolta)}
    obbligatorie = [d for d in risolta.get("domande", []) if d.get("obbligatorio")]
    return {"esito": "domande" if obbligatorie else "redazione", "domande": risolta.get("domande", []),
            "scadenze": scadenze_calcolate(risolta), "blocchi": risolta.get("scrive_lex", [])}


def blocco_scheda(risolta: dict[str, Any]) -> str:
    """La scheda risolta come la legge Lex: dati con la loro fonte, dati mancanti, scadenze."""
    righe = [f"Scheda: {risolta.get('titolo', risolta.get('scheda', ''))}"]
    fonti = {"compilato": "gestionale", "da_confermare": "letto nei documenti, da confermare",
             "documento_presente": "documento del fascicolo, da verificare nel contenuto", "proposta_lex": "da proporre"}
    for c in risolta.get("campi", []):
        if c["stato"] in fonti and c.get("valore"):
            righe.append(f"- {c['etichetta']}: {c['valore']} ({fonti[c['stato']]})")
    mancanti = [c["etichetta"] for c in risolta.get("campi", []) if c["stato"] == "da_chiedere"]
    if mancanti:
        righe.append("Dati mancanti (nel testo scrivi " + MANCANTE.format("…") + ", non inventarli): " + "; ".join(mancanti))
    scad = blocco_scadenze(risolta)
    return "\n".join(righe + ([scad] if scad else []))


def messaggio_blocco(risolta: dict[str, Any], blocco: dict[str, str], fonti: str) -> str:
    """Messaggio per far scrivere a Lex un blocco dell'atto con i soli dati della scheda e le Fonti date."""
    return (f"Domanda:\nScrivi il blocco «{blocco['blocco']}» di: {risolta.get('titolo', '')}. Contenuto: {blocco['compito']}. "
            "Usa solo i dati della scheda e le Fonti; cita le norme con [n].\n\n"
            f"{blocco_scheda(risolta)}\n\nFonti:\n{fonti}")
