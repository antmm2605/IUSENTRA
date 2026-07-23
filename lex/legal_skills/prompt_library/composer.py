"""Compositore dei prompt LegalSkills Italia nelle varie forme.

Ogni forma corrisponde a un formato di lavoro della prassi forense
(redazione atto, parere, checklist, lettera, ricerca). Il testo composto
richiama sempre i riferimenti normativi della voce e l'obbligo di
revisione dell'avvocato: il prompt non autorizza mai l'invenzione di
norme o giurisprudenza (principio delle fonti certe).
"""

from __future__ import annotations

from typing import Any

from .models import AreaPrompt, VocePrompt


FORME: dict[str, dict[str, str]] = {
    "redazione_atto": {
        "label": "Redazione atto",
        "descrizione": "Bozza di atto o documento secondo la prassi forense italiana.",
    },
    "parere": {
        "label": "Parere legale",
        "descrizione": "Parere motivato con inquadramento normativo e rischi.",
    },
    "checklist": {
        "label": "Checklist operativa",
        "descrizione": "Elenco di controllo per adempimenti, documenti e termini.",
    },
    "lettera": {
        "label": "Lettera o diffida",
        "descrizione": "Comunicazione professionale a controparte, cliente o ente.",
    },
    "ricerca": {
        "label": "Ricerca normativa e giurisprudenziale",
        "descrizione": "Impostazione della ricerca su norme e orientamenti da verificare su fonti ufficiali.",
    },
}

_AVVERTENZA = (
    "Avvertenza: l'output è una bozza destinata alla revisione obbligatoria dell'avvocato. "
    "Non inventare norme, articoli o precedenti: se una fonte non è certa, segnalala come da verificare "
    "su fonti ufficiali (Normattiva, portali istituzionali, banche dati giurisprudenziali)."
)


def _intestazione(area: AreaPrompt, voce: VocePrompt) -> str:
    riferimenti = "; ".join(voce.riferimenti) if voce.riferimenti else "da individuare su fonti ufficiali"
    return (
        f"Agisci come avvocato esperto di {area.nome.lower()} nell'ordinamento italiano.\n"
        f"Tema: {voce.nome} — {voce.descrizione}\n"
        f"Riferimenti normativi di partenza: {riferimenti} (verifica sempre la vigenza del testo applicabile)."
    )


def _corpo(forma: str, voce: VocePrompt) -> str:
    if forma == "redazione_atto":
        return (
            f"Redigi una bozza completa relativa a: {voce.nome}.\n"
            "Dati del caso da utilizzare: [FATTI], [PARTI], [DOCUMENTI DISPONIBILI], [AUTORITÀ O UFFICIO COMPETENTE].\n"
            "Struttura richiesta: intestazione, premesse in fatto, motivi in diritto con richiami normativi, "
            "conclusioni/richieste, elenco allegati. Evidenzia tra parentesi quadre ogni dato mancante da chiedere al cliente."
        )
    if forma == "parere":
        return (
            f"Redigi un parere legale motivato su: {voce.nome}.\n"
            "Quesito e fatti rilevanti: [QUESITO], [FATTI], [DOCUMENTI].\n"
            "Struttura richiesta: sintesi della risposta, inquadramento normativo, analisi del caso concreto, "
            "profili di rischio e orientamenti da verificare, conclusioni operative con eventuali alternative."
        )
    if forma == "checklist":
        return (
            f"Prepara una checklist operativa per: {voce.nome}.\n"
            "Contesto dello studio: [TIPO DI INCARICO], [SCADENZE NOTE], [DOCUMENTI GIÀ ACQUISITI].\n"
            "Organizza la checklist per fasi (istruttoria, adempimenti, termini processuali o amministrativi, "
            "documenti da acquisire, verifiche finali) indicando per ogni punto la base normativa pertinente."
        )
    if forma == "lettera":
        return (
            f"Redigi una lettera professionale relativa a: {voce.nome}.\n"
            "Destinatario e contesto: [DESTINATARIO], [FATTI], [RICHIESTA O INTIMAZIONE], [TERMINE ASSEGNATO].\n"
            "Tono formale e cortese ma fermo; richiama la base normativa, quantifica le richieste dove possibile "
            "e indica le conseguenze del mancato riscontro, con riserva di ogni azione."
        )
    return (
        f"Imposta una ricerca normativa e giurisprudenziale su: {voce.nome}.\n"
        "Quesito di ricerca: [QUESITO], [CONTESTO DEL CASO].\n"
        "Indica: le disposizioni da esaminare partendo dai riferimenti sopra, le parole chiave per le banche dati, "
        "gli orientamenti contrapposti da verificare e come citarli solo dopo controllo su fonti ufficiali."
    )


def componi_testo(area: AreaPrompt, voce: VocePrompt, forma: str) -> str:
    """Compone il testo integrale del prompt per la forma richiesta."""
    if forma not in FORME:
        raise KeyError(f"Forma prompt sconosciuta: {forma}")
    return "\n\n".join([_intestazione(area, voce), _corpo(forma, voce), _AVVERTENZA])


def titolo_prompt(voce: VocePrompt, forma: str) -> str:
    label = FORME.get(forma, {}).get("label", forma)
    return f"{voce.nome} — {label}"


def forme_public() -> list[dict[str, Any]]:
    return [
        {"forma_id": forma_id, "label": info["label"], "descrizione": info["descrizione"]}
        for forma_id, info in FORME.items()
    ]


__all__ = ["FORME", "componi_testo", "forme_public", "titolo_prompt"]
