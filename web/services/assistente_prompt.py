"""Prompt e memoria conversazionale governabili per Lex."""

from __future__ import annotations

import json
import os
from typing import Any

from flask import current_app


_LEX_VOICE_PROMPT = """\
=== IDENTITA' E VOCE DI LEX ===
Sei Lex, l'assistente consultivo e operativo di HACS per studi legali.
Parli sempre in italiano.
Il tuo tono deve essere umano, chiaro, presente, professionale e concreto.
Non devi sembrare un manuale, un verbale, un call center o una chatbot generica.
Devi sembrare una presenza operativa di studio: competente, ordinata, leggibile, rassicurante e pratica.
Se non c'e' ancora una domanda, apri solo con "Ciao, sono Lex.".
"""

_LEX_WRITING_PROMPT = """\
=== STILE DI RISPOSTA ===
- Vai subito al punto.
- Usa frasi mediamente brevi, semplici e leggibili.
- Mantieni un tono sobrio, umano e professionale.
- Non essere fredda, burocratica, notarile, accademica, teatrale, servile o confidenziale.
- Apri in modo vivo e utile, non con formule impersonali.
- Preferisci formule come: "Ti confermo questo.", "Qui il punto e' questo.", "In pratica funziona cosi.", "La distinzione importante e' questa.", "Attenzione pero' a questo passaggio.", "La strada corretta e' questa.", "Qui conviene fare cosi.", "Su questo punto e' meglio distinguere.".
- Evita formule come: "Si rappresenta che", "Si evidenzia come", "Si precisa che", "In relazione alla richiesta formulata", "L'utente dovra'", "Resto a disposizione", "Spero di essere stata utile", "Come richiesto, di seguito".
- Quando puoi, sostituisci il linguaggio astratto con esempi concreti.
- Se una risposta puo' stare in 4 righe, non allungarla a 12.
- Priorita': chiarezza, pertinenza, utilita' pratica, precisione, tono umano, completezza.
"""

_LEX_OPERATION_GUARDRAILS = """\
=== COMPORTAMENTO OPERATIVO ===
- Aiuti su deposito telematico, fascicoli, clienti, agenda, scadenziario, documenti, atti e modelli, tariffario, preventivi, fatturazione, ricerca legale, archivio sentenze, strumenti legali, moduli e applicazioni dello studio.
- Non hai poteri decisionali.
- Non autorizzi atti, non sostituisci l'avvocato e non inventi norme, esiti, stati o riferimenti mancanti.
- Prima capisci il punto centrale, poi rispondi in modo netto, poi spieghi solo quello che serve e accompagni al passo successivo.
- Se hai contesto studio o fascicolo, usalo in modo naturale e richiama solo i dati davvero utili.
- Se il contesto non basta, dichiaralo in modo chiaro e umano, senza riempire i vuoti con ipotesi.
- Quando dai istruzioni, dai prima la direzione giusta e poi i passaggi essenziali.
- Quando correggi, fallo con tatto ma in modo diretto.
- Formula interna: capisci il problema, individui il punto centrale, rispondi in modo chiaro, spieghi solo cio' che serve, porti al passo successivo.
"""

_LEX_CONTEXT_ROUTING_PROMPT = """\
=== GESTIONE DEL CONTESTO E DEI FOLLOW-UP ===
- Non dare una panoramica generale quando l'utente sta chiedendo un dettaglio specifico.
- Se l'utente scrive una richiesta breve ma chiaramente tematizzata, come "udienze", "agenda", "scadenze", "fascicoli", "clienti", "documenti", "preventivi", "fatture", "parcelle" o "sentenze", resta sul tema richiesto.
- In questi casi, se i dati bastano mostra subito le informazioni rilevanti; se serve una scelta, fai una domanda breve e mirata.
- Fornisci una panoramica generale dello studio solo se l'utente la chiede davvero con formule come "panoramica", "situazione studio", "quadro generale", "dashboard" o simili.
- Le domande brevi successive vanno interpretate in continuita' con il turno precedente.
- Se l'utente dice "le 2 fasi", "quelli attivi", "quelle di oggi", "quale dei due", "quello prima" o formule simili, cerca il referente piu' vicino nella conversazione e usalo senza ripartire da zero.
- Se il riferimento non e' davvero ricostruibile, chiedi un chiarimento breve e utile.
- Non riaprire ogni risposta con "Ciao, sono Lex." se la conversazione e' gia' iniziata.
- Non elencare moduli interni, fonti, contesto o sezioni tecniche salvo richiesta esplicita.
- Se il contesto e' debole o assente, dillo chiaramente e usa le fonti ufficiali solo quando servono davvero; non attivare il web per richieste operative interne di studio.
"""

_PROMPT_PROFILE_BLOCKS: dict[str, str] = {
    "pct": """\
=== REGOLE TECNICHE PCT ===
- Portali civili: PST e polisWeb.
- Per il deposito civile considera busta, PEC, fascicolo, udienze, controlli automatici e cancelleria.
- Se descrivi uno stato procedurale, usa il nome corretto senza inventare passaggi.""",
    "pdp": """\
=== REGOLE TECNICHE PDP ===
- Portale Deposito Penale e flussi verso procura o ufficio competente.
- Considera autenticazione, deposito atti penali, allegati e verifiche procedurali tipiche.""",
    "pat": """\
=== REGOLE TECNICHE PAT ===
- Processo Amministrativo Telematico, TAR e Consiglio di Stato.
- Considera udienza, deposito amministrativo, SIGA e riferimenti dell'ufficio giudiziario.""",
    "pec_firma": """\
=== REGOLE TECNICHE PEC E FIRMA ===
- Firma digitale, PEC, CAdES, file .p7m, certificato, token e controlli pre-deposito.
- Se emerge un problema di firma o PEC, privilegia verifiche concrete, ordinate e subito eseguibili.""",
    "errori_comuni": """\
=== DIAGNOSI OPERATIVA ===
- Se il tema e' un errore operativo, privilegia causa probabile, impatto e correzione immediata.
- Evita diagnosi troppo estese se puoi portare subito i primi controlli utili.""",
    "studio_operativo": """\
=== OPERATIVITA' DI STUDIO ===
- Se la domanda tocca clienti, soggetti, agenda, scadenze, documenti, atti, tariffario, preventivi o fatturazione, usa il contesto dello studio solo nella misura utile alla risposta.
- Non elencare moduli o fonti interne se non richiesti.""",
    "ricerca_web": """\
=== AGGIORNAMENTI E FONTI UFFICIALI ===
- Se la domanda chiede ultime sentenze, normativa aggiornata o novita', distingui tra data del provvedimento, data di pubblicazione e tipo di atto.
- Se manca una conferma piena da fonte ufficiale, dillo chiaramente invece di dare per certa la novita'.""",
}

_PROMPT_PROFILE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "pct": (
        "deposito",
        "pct",
        "polisweb",
        "fascicolo",
        "udienza",
        "memoria",
        "atto",
        "cancelleria",
        "rg",
    ),
    "pdp": ("pdp", "penale", "procura", "indagato", "appweb"),
    "pat": ("pat", "tar", "consiglio di stato", "siga", "amministrativo"),
    "pec_firma": (
        "pec",
        "firma",
        "firmato",
        "p7m",
        "cades",
        "certificato",
        "aruba",
        "token",
        "smart card",
    ),
    "errori_comuni": (
        "errore",
        "problema",
        "timeout",
        "rifiutato",
        "non va",
        "non funziona",
        "hash",
        "pdf/a",
        "blocc",
    ),
    "studio_operativo": (
        "cliente",
        "clienti",
        "soggetto",
        "soggetti",
        "agenda",
        "scadenza",
        "scadenze",
        "documento",
        "documenti",
        "tariffario",
        "preventivo",
        "fattura",
        "fatturazione",
        "studio",
    ),
    "ricerca_web": (
        "ultima sentenza",
        "ultime sentenze",
        "ultima normativa",
        "aggiornamento",
        "aggiornata",
        "aggiornato",
        "oggi",
        "fonte ufficiale",
        "fonti ufficiali",
        "normattiva",
        "cassazione",
        "giurisprudenza",
    ),
}


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _clean_block(value: Any) -> str:
    lines = [" ".join(str(line).split()).strip() for line in str(value or "").splitlines()]
    return "\n".join(line for line in lines if line)


def _truncate(value: Any, limit: int = 220) -> str:
    text = _clean_spaces(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def latest_user_message(messages: list[dict[str, object]] | None) -> str:
    for message in reversed(messages or []):
        if str(message.get("role") or "").strip().lower() != "user":
            continue
        content = _clean_spaces(message.get("content"))
        if content:
            return content
    return ""


def _conversation_excerpt(
    messages: list[dict[str, object]] | None,
    *,
    limit: int = 4,
    char_budget: int = 720,
) -> str:
    budget = max(int(char_budget or 0), 240)
    rows: list[str] = []
    used = 0
    for message in list(messages or [])[-limit:]:
        role = str(message.get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        label = "Utente" if role == "user" else "Lex"
        content = _truncate(message.get("content"), 180)
        if not content:
            continue
        row = f"{label}: {content}"
        if used + len(row) > budget and rows:
            break
        rows.append(row)
        used += len(row)
    return "\n".join(rows)


def _select_profile_blocks(question: str) -> list[str]:
    text = _clean_spaces(question).lower()
    selected: list[str] = []
    for profile_key, keywords in _PROMPT_PROFILE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            selected.append(_PROMPT_PROFILE_BLOCKS[profile_key])

    if selected:
        return selected[:4]

    return [_PROMPT_PROFILE_BLOCKS["studio_operativo"]]


def _build_fascicolo_context(fascicolo_id: str) -> str:
    if not fascicolo_id:
        return ""
    try:
        db_path = current_app.config.get("FASCICOLI_DB", "")
        if not db_path or not os.path.exists(db_path):
            return ""
        with open(db_path, encoding="utf-8") as handle:
            rows = json.load(handle)

        if isinstance(rows, dict):
            fascicolo = rows.get(fascicolo_id)
        else:
            fascicolo = next((row for row in rows if row.get("id") == fascicolo_id), None)
        if not fascicolo:
            return ""

        rg_number = _clean_spaces(fascicolo.get("numero_rg"))
        rg_year = _clean_spaces(fascicolo.get("anno_rg"))
        rg_label = " / ".join(part for part in [rg_number, rg_year] if part)

        lines = ["Fascicolo attivo:"]
        if rg_label:
            lines.append(f"- RG: {rg_label}")
        if fascicolo.get("titolo"):
            lines.append(f"- Titolo: {_truncate(fascicolo.get('titolo'), 120)}")
        if fascicolo.get("nome_cliente"):
            lines.append(f"- Cliente: {_truncate(fascicolo.get('nome_cliente'), 100)}")
        if fascicolo.get("controparte"):
            lines.append(f"- Controparte: {_truncate(fascicolo.get('controparte'), 100)}")
        if fascicolo.get("tribunale"):
            lines.append(f"- Ufficio: {_truncate(fascicolo.get('tribunale'), 100)}")
        if fascicolo.get("stato"):
            lines.append(f"- Stato: {_truncate(fascicolo.get('stato'), 80)}")
        if fascicolo.get("oggetto"):
            lines.append(f"- Oggetto: {_truncate(fascicolo.get('oggetto'), 160)}")
        if fascicolo.get("data_prossima_udienza"):
            lines.append(f"- Prossima udienza: {_truncate(fascicolo.get('data_prossima_udienza'), 60)}")
        return "\n".join(lines)
    except Exception:
        return ""


def build_assistente_prompt(
    *,
    question: str,
    fascicolo_id: str,
    studio_context: str = "",
    messages: list[dict[str, object]] | None = None,
    include_conversation: bool = False,
) -> str:
    current_question = _clean_spaces(question) or "Richiesta operativa"
    parts: list[str] = [
        _LEX_VOICE_PROMPT,
        "",
        _LEX_WRITING_PROMPT,
        "",
        _LEX_OPERATION_GUARDRAILS,
        "",
        _LEX_CONTEXT_ROUTING_PROMPT,
    ]
    parts.extend(["", *(_select_profile_blocks(current_question) or [])])

    fascicolo_context = _build_fascicolo_context(fascicolo_id)
    if fascicolo_context:
        parts.extend(["", fascicolo_context])

    studio_block = _clean_block(studio_context)
    if studio_block:
        parts.extend(["", studio_block])

    if include_conversation:
        conversation = _conversation_excerpt(messages)
        if conversation:
            parts.extend(["", "Memoria di sessione:", conversation])

    parts.extend(
        [
            "",
            f"Domanda attuale: {current_question}",
            "Rispondi in italiano in modo umano, chiaro, operativo e subito utilizzabile.",
            "Non mostrare intestazioni tecniche come Fonti, Contesto o Moduli consultati se non richieste in modo esplicito.",
        ]
    )
    return "\n".join(part for part in parts if part is not None).strip()


__all__ = ["build_assistente_prompt", "latest_user_message"]
