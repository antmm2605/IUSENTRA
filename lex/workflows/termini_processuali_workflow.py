"""Workflow calcolo termini processuali — deterministico e normativo."""

from __future__ import annotations

from datetime import date
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
        # L. 742/1969, art. 3: la sospensione feriale non si applica alle controversie di lavoro.
        "sospensione_feriale": False,
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
        "norma": "art. 7 D.Lgs. 150/2011 (già art. 22 L. 689/1981)",
        "nota": "60 giorni se il ricorrente risiede all'estero.",
    },
    "ricorso_tar": {
        "giorni": 60,
        "label": "Ricorso al TAR",
        "norma": "art. 29 D.Lgs. 104/2010",
    },
    "appello_tar": {
        "giorni": 60,
        "label": "Appello al Consiglio di Stato",
        "norma": "art. 92 D.Lgs. 104/2010",
        "nota": "Termine dimezzato a 30 giorni nei riti abbreviati (art. 119 c.p.a.); termine lungo di 6 mesi dalla pubblicazione.",
    },
    "reclamo_cautelare": {
        "giorni": 15,
        "label": "Reclamo cautelare",
        "norma": "art. 669-terdecies c.p.c.",
    },
    "opposizione_atti_esecutivi": {
        "giorni": 20,
        "label": "Opposizione agli atti esecutivi",
        "norma": "art. 617 c.p.c.",
        "nota": "L'opposizione all'esecuzione (art. 615 c.p.c.) non ha un termine in giorni: va proposta prima della vendita o dell'assegnazione.",
    },
    "costituzione_convenuto": {
        "giorni": 70,
        "label": "Costituzione del convenuto",
        "norma": "art. 166 c.p.c.",
        "direzione": "ritroso",
        "nota": "Almeno 70 giorni prima dell'udienza indicata nell'atto di citazione: la data da indicare è quella dell'udienza.",
    },
    "iscrizione_ruolo_civile": {
        "giorni": 10,
        "label": "Iscrizione a ruolo causa civile",
        "norma": "art. 165 c.p.c.",
    },
    "riassunzione_causa": {
        "giorni": 0,
        "mesi": 3,
        "label": "Riassunzione causa interrotta o sospesa",
        "norma": "artt. 297, 305 e 307 c.p.c.",
    },
    "querela": {
        "giorni": 90,
        "label": "Querela di parte",
        "norma": "art. 124 c.p.",
        # Termine sostanziale, non processuale: non si sospende ad agosto.
        "sospensione_feriale": False,
    },
    "impugnazione_decreto_penale": {
        "giorni": 15,
        "label": "Opposizione a decreto penale di condanna",
        "norma": "art. 461 c.p.p.",
    },
    "appello_sentenza_penale": {
        "giorni": 15,
        "label": "Appello contro la sentenza penale",
        "norma": "art. 585 c.p.p.",
        "penale": "impugnazione_sentenza",
    },
    "ricorso_cassazione_penale": {
        "giorni": 15,
        "label": "Ricorso per cassazione contro la sentenza penale",
        "norma": "art. 585 c.p.p.",
        "penale": "impugnazione_sentenza",
    },
}
_TERMINI["impugnazione_decreto_penale"]["penale"] = "opposizione_decreto_penale"


def _termine_penale(info: dict, decorrenza: date) -> str:
    """Termini penali col motore deterministico (art. 172 c.p.p., L. 742/1969, art. 585 c.p.p.)."""
    from pct.termini_penali import impugnazioni

    righe = [f"**{info['label']}** ({info['norma']})", ""]
    if info["penale"] == "impugnazione_sentenza":
        righe.append("Il termine dipende da come è stata depositata la motivazione (art. 585 c. 1 c.p.p.):")
        for modo, testo in (("contestuale", "motivazione letta in udienza: 15 giorni dalla lettura"),
                            ("quindici_giorni", "motivazione entro 15 giorni (art. 544 c. 2): 30 giorni dalla scadenza del deposito")):
            esito = impugnazioni.calcola({"tp_atto": "impugnazione_sentenza", "tp_motivazione": modo,
                                          "tp_data_evento": decorrenza.isoformat()})
            righe.append(f"- {testo}: scadenza **{esito['scadenza']}**")
        righe.append("- termine più lungo fissato dal giudice (art. 544 c. 3): 45 giorni dalla sua scadenza")
        righe.append("- +15 giorni per il difensore dell'imputato giudicato in assenza (art. 585 c. 1-bis)")
    else:
        esito = impugnazioni.calcola({"tp_atto": info["penale"], "tp_data_evento": decorrenza.isoformat()})
        righe.append(f"- Decorrenza: {_format_data(decorrenza)}")
        righe.append(f"- Scadenza: **{esito['scadenza']}**")
    righe += ["", "Calcolo con art. 172 c.p.p. (proroga se festivo, il sabato non lo è) e sospensione feriale dal "
              "1° al 31 agosto (L. 742/1969). Per i casi particolari usa Strumenti forensi → «Impugnazioni e opposizioni penali»."]
    return "\n".join(righe)


def _scadenza(decorrenza: date, *, giorni: int, mesi: int, info: dict) -> date:
    """La scadenza col motore unico dei termini: dies a quo escluso, sospensione feriale (L. 742/1969) se
    applicabile, proroga al primo giorno non festivo (art. 155 c.p.c.); a ritroso si anticipa."""
    from pct.termini_processuali import ItalianDeadlineCalculator

    esito = ItalianDeadlineCalculator().calculate(
        decorrenza, mesi or giorni, direction="backward" if info.get("direzione") == "ritroso" else "forward",
        period_type="months" if mesi else "days", suspend_august=bool(info.get("sospensione_feriale", True)),
    )
    return date.fromisoformat(esito["deadline"])


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

    from pct.ora_italiana import oggi_roma

    oggi = oggi_roma()
    if data_decorrenza_iso:
        try:
            from datetime import datetime
            decorrenza = datetime.strptime(data_decorrenza_iso, "%Y-%m-%d").date()
        except Exception:
            decorrenza = oggi
    else:
        decorrenza = oggi

    if info.get("penale") and giorni_override is None:
        return _termine_penale(info, decorrenza)
    giorni = giorni_override if giorni_override is not None else int(info["giorni"])
    mesi = 0 if giorni_override is not None else int(info.get("mesi") or 0)
    scadenza = _scadenza(decorrenza, giorni=giorni, mesi=mesi, info=info)
    restanti = (scadenza - oggi).days
    ritroso = info.get("direzione") == "ritroso"

    lines = [
        f"**{info['label']}** ({info['norma']})",
        "",
        f"- {'Udienza' if ritroso else 'Decorrenza'}: {_format_data(decorrenza)}",
        f"- Termine: {f'{mesi} mesi' if mesi else f'{giorni} giorni'}{' prima' if ritroso else ''}",
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
