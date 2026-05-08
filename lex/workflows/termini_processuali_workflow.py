"""Workflow calcolo termini processuali — deterministico e normativo."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


SYSTEM_PROMPT = (
    "Sei Lex, il modulo di calcolo termini processuali di IUSENTRA.\n\n"
    "REGOLE ASSOLUTE:\n"
    "• Rispondi SEMPRE e SOLO in italiano.\n"
    "• Fornisci la scadenza calcolata con la base normativa (articolo di legge) e le avvertenze operative.\n"
    "• Non inventare termini: se il tipo di termine non è in elenco, dì quale norma va verificata.\n"
    "• Ricorda SEMPRE la sospensione feriale agosto (art. 155 c.p.c.) e le festività.\n"
    "• Struttura: Scadenza calcolata → Normativa → Avvertenze → Prossima azione.\n"
    "• Non aggiungere disclaimer generici né rimandare l'utente a terzi.\n"
    "• Non iniziare con saluti: vai subito al risultato.\n"
)


# Termini processuali italiani con base normativa
_TERMINI: dict[str, dict[str, Any]] = {
    "opposizione_decreto_ingiuntivo": {
        "giorni": 40,
        "label": "Opposizione a decreto ingiuntivo",
        "norma": "art. 641-645 c.p.c.",
    },
    "appello_sentenza_civile": {
        "giorni": 30,
        "label": "Appello sentenza civile (termine breve)",
        "norma": "art. 325 c.p.c.",
        "nota": "Termine lungo: 6 mesi dalla pubblicazione se la sentenza non è stata notificata.",
    },
    "appello_sentenza_lavoro": {
        "giorni": 30,
        "label": "Appello sentenza lavoro",
        "norma": "art. 434 c.p.c.",
    },
    "ricorso_cassazione": {
        "giorni": 60,
        "label": "Ricorso in Cassazione",
        "norma": "art. 325 c.p.c.",
        "nota": "Termine lungo: 6 mesi dalla pubblicazione.",
    },
    "opposizione_sanzione_amministrativa": {
        "giorni": 30,
        "label": "Opposizione a sanzione amministrativa",
        "norma": "art. 22 L. 689/1981",
    },
    "ricorso_tar": {
        "giorni": 60,
        "label": "Ricorso al TAR",
        "norma": "art. 29 D.Lgs. 104/2010",
    },
    "appello_tar": {
        "giorni": 30,
        "label": "Appello al Consiglio di Stato",
        "norma": "art. 91 D.Lgs. 104/2010",
    },
    "reclamo_cautelare": {
        "giorni": 15,
        "label": "Reclamo cautelare",
        "norma": "art. 669-terdecies c.p.c.",
    },
    "opposizione_esecuzione": {
        "giorni": 20,
        "label": "Opposizione all'esecuzione",
        "norma": "art. 615 c.p.c.",
    },
    "costituzione_convenuto": {
        "giorni": 20,
        "label": "Costituzione del convenuto",
        "norma": "art. 166 c.p.c.",
    },
    "iscrizione_ruolo_civile": {
        "giorni": 10,
        "label": "Iscrizione a ruolo causa civile",
        "norma": "art. 165 c.p.c.",
    },
    "riassunzione_causa": {
        "giorni": 90,
        "label": "Riassunzione causa interrotta o sospesa",
        "norma": "art. 307 c.p.c.",
    },
    "querela": {
        "giorni": 90,
        "label": "Querela di parte",
        "norma": "art. 124 c.p.",
    },
    "impugnazione_decreto_penale": {
        "giorni": 15,
        "label": "Opposizione a decreto penale di condanna",
        "norma": "art. 461 c.p.p.",
    },
    "appello_sentenza_penale": {
        "giorni": 15,
        "label": "Appello sentenza penale (termine breve)",
        "norma": "art. 585 c.p.p.",
    },
    "ricorso_cassazione_penale": {
        "giorni": 30,
        "label": "Ricorso in Cassazione penale",
        "norma": "art. 585 c.p.p.",
    },
}


def _format_data(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def calcola_termine(
    tipo: str,
    *,
    data_decorrenza_iso: str = "",
    giorni_override: int | None = None,
) -> str:
    """Risposta testuale italiana con scadenza calcolata."""
    info = _TERMINI.get(tipo)
    if info is None:
        return (
            f"Il tipo di termine '{tipo}' non è nel mio elenco.\n"
            "Indicami il numero di giorni e la norma di riferimento, "
            "così posso calcolare la scadenza dalla data che mi indichi."
        )

    oggi = date.today()
    if data_decorrenza_iso:
        try:
            from datetime import datetime
            decorrenza = datetime.strptime(data_decorrenza_iso, "%Y-%m-%d").date()
        except Exception:
            decorrenza = oggi
    else:
        decorrenza = oggi

    giorni = giorni_override if giorni_override is not None else int(info["giorni"])
    scadenza = decorrenza + timedelta(days=giorni)
    restanti = (scadenza - oggi).days

    lines = [
        f"**{info['label']}** ({info['norma']})",
        "",
        f"- Decorrenza: {_format_data(decorrenza)}",
        f"- Termine: {giorni} giorni",
        f"- Scadenza: **{_format_data(scadenza)}**",
        f"- Giorni restanti: {'**SCADUTO**' if restanti < 0 else ('**URGENTE** — ' if restanti <= 7 else '') + str(restanti) + ' gg'}",
        "",
    ]
    if info.get("nota"):
        lines.append(f"Nota: {info['nota']}")
        lines.append("")

    lines += [
        "**Avvertenze operative:**",
        "- Verificare sospensione feriale agosto (1–31 agosto, art. 155 c.p.c.)",
        "- Verificare festività nazionali e locali",
        "- Il termine decorre dal giorno successivo alla notifica (dies a quo non computatur in termino)",
    ]
    return "\n".join(lines)


def lista_termini_disponibili() -> str:
    """Elenco italiano dei termini disponibili."""
    lines = ["**Tipi di termine processuale disponibili:**\n"]
    for key, info in _TERMINI.items():
        lines.append(f"- `{key}`: {info['label']} ({info['giorni']} gg) — {info['norma']}")
    return "\n".join(lines)


class TerminiProcessualiWorkflow:
    workflow_name = "termini_processuali"
    system_prompt = SYSTEM_PROMPT
