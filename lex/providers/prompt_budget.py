"""Costruzione del prompt RAG di Lex entro il budget di contesto del modello.

Responsabilità:
- formato unico e ricco delle evidenze ("[n] Fonte · art. · URN/ECLI · vigenza · data");
- estratto compatto e pertinente dei dati dello studio (mai nei workflow giuridici,
  mai codici fiscali, partite IVA o IBAN);
- budget di token applicato in Python prima della chiamata: se si sfora si
  tolgono prima le evidenze meno rilevanti (in coda alla lista ordinata dal
  retrieval), mai il system prompt o la domanda;
- rimozione dei blocchi di ragionamento <think>...</think> (anche non chiusi);
- controllo a posteriori di `prompt_eval_count` per segnalare un possibile
  troncamento silenzioso da parte di Ollama.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from lex.prompts.legal_rag_prompt import is_legal_rag_workflow
from lex.settings import LexGenerationSettings

logger = logging.getLogger("lex.prompt_budget")

# Stima prudente per l'italiano con i tokenizer dei modelli locali (Qwen, Gemma):
# circa 3,5 caratteri per token.
CHARS_PER_TOKEN = 3.5

_SEPARATORE = " · "

# ---------------------------------------------------------------------------
# Stima dei token
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    value = str(text or "")
    if not value:
        return 0
    return int(math.ceil(len(value) / CHARS_PER_TOKEN))


def _chars_for_tokens(tokens: int) -> int:
    return max(int(tokens * CHARS_PER_TOKEN), 0)


# ---------------------------------------------------------------------------
# Dati personali da non inviare mai al modello
# ---------------------------------------------------------------------------

_CODICE_FISCALE_RE = re.compile(r"\b[A-Z]{6}\d{2}[A-EHLMPR-T]\d{2}[A-Z]\d{3}[A-Z]\b", re.IGNORECASE)
_IBAN_RE = re.compile(r"\bIT\s?\d{2}\s?[A-Z](?:\s?[0-9A-Z]){22}\b", re.IGNORECASE)
_PARTITA_IVA_RE = re.compile(
    r"(?i)\b(partita\s+iva|p\.?\s?iva|codice\s+fiscale|c\.?\s?f\.?)\s*[:=]?\s*(?=[0-9A-Z]*\d)[0-9A-Z]{11,16}\b"
)
_SENSITIVE_KEYS = {
    "codice_fiscale",
    "cod_fiscale",
    "cf",
    "partita_iva",
    "p_iva",
    "piva",
    "iban",
    "password",
    "pec_password",
    "smtp_password",
    "token",
    "api_key",
    "numero_documento",
    "documento_identita",
    "data_nascita",
    "luogo_nascita",
}


def scrub_personal_data(text: str) -> str:
    value = str(text or "")
    if not value:
        return ""
    value = _PARTITA_IVA_RE.sub(lambda m: f"{m.group(1)}: [omesso]", value)
    value = _CODICE_FISCALE_RE.sub("[codice fiscale omesso]", value)
    value = _IBAN_RE.sub("[IBAN omesso]", value)
    return value


# ---------------------------------------------------------------------------
# Formato delle evidenze
# ---------------------------------------------------------------------------


def _item_get(item: Any, *keys: str) -> Any:
    """Cerca il primo valore non vuoto fra attributi, metadata e metadata annidati."""
    sources: list[Any] = []
    if isinstance(item, dict):
        sources.append(item)
        meta = item.get("metadata")
    else:
        sources.append({key: getattr(item, key, None) for key in keys})
        meta = getattr(item, "metadata", None)
    if isinstance(meta, dict):
        sources.append(meta)
        nested = meta.get("metadata")
        if isinstance(nested, dict):
            sources.append(nested)
    for key in keys:
        for source in sources:
            value = source.get(key) if isinstance(source, dict) else None
            if value not in (None, "", [], {}):
                return value
    return None


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _data_italiana(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        try:
            giorno = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            return giorno.strftime("%d/%m/%Y")
        except ValueError:
            return text[:10]
    return text[:40]


def _riferimento(item: Any, fonte: str = "") -> str:
    """Estremi (articolo o numero/anno, sezione); non ripete il numero se il titolo lo contiene gia'."""
    article = _clean(_item_get(item, "articolo", "article", "article_number", "numero_articolo"))
    if article:
        return article if article.lower().startswith("art") else f"art. {article}"
    numero = _clean(_item_get(item, "numero_sentenza", "numero_decisione", "numero_provvedimento"))
    anno = _clean(_item_get(item, "anno_sentenza", "anno_decisione", "anno"))
    if numero:
        rif = f"n. {numero}/{anno}" if anno and "/" not in numero else f"n. {numero}"
        if fonte and re.search(rf"(?<![\w/]){re.escape(rif)}(?![\w/])", fonte, re.IGNORECASE):
            rif = ""
        sezione = _clean(_item_get(item, "sezione"))
        if sezione:
            return f"{rif}, sez. {sezione}" if rif else f"sez. {sezione}"
        return rif
    return ""


def _identificativo(item: Any) -> str:
    ecli = _clean(_item_get(item, "ecli"))
    if ecli:
        return ecli
    urn = _clean(_item_get(item, "urn"))
    if urn:
        return urn
    origine = _clean(_item_get(item, "url_origine"))
    if origine.lower().startswith("urn:"):
        return origine
    return ""


def _vigenza(item: Any) -> str:
    value = _item_get(item, "vigenza", "stato_vigenza", "vigente")
    if value is True:
        return "vigente"
    if value is False:
        return "non vigente"
    text = _clean(value).lower()
    if not text:
        return ""
    return {"originale": "testo originale", "true": "vigente", "false": "non vigente"}.get(text, text)


def _data(item: Any) -> str:
    return _data_italiana(
        _item_get(
            item,
            "data",
            "data_atto",
            "data_deposito",
            "data_decisione",
            "data_pubblicazione",
            "published_at",
        )
    )


def _fonte(item: Any) -> str:
    title = _clean(_item_get(item, "title", "titolo", "citation"))
    provenienza = _clean(_item_get(item, "fonte", "organo", "authority"))
    if not title:
        return provenienza or "Fonte"
    # Le etichette tecniche interne (studio_context, knowledge_base, ...) non
    # dicono nulla all'avvocato: si mostra solo una provenienza leggibile.
    if "_" in provenienza:
        provenienza = ""
    if provenienza and provenienza.lower() not in title.lower() and len(provenienza) <= 60:
        return f"{title} ({provenienza})"
    return title


def _testo(item: Any) -> str:
    content = _clean(_item_get(item, "content", "excerpt", "testo", "text"))
    extra: list[str] = []
    for label, keys in (
        ("Dispositivo", ("dispositivo",)),
        ("Principio", ("principio_sintetico", "massima_ufficiale")),
    ):
        value = _clean(_item_get(item, *keys))
        # gia' presente nel testo (anche solo l'inizio, se il retrieval l'ha accorciato): non si ripete
        if value and value[:200].lower() not in content.lower():
            extra.append(f"{label}: {value}")
    return " ".join(part for part in [content, *extra] if part)


def _tronca(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    cut = text[: max(max_chars - 1, 0)]
    space = cut.rfind(" ")
    if space > max_chars * 0.6:
        cut = cut[:space]
    return cut.rstrip(" ,;:") + "…", True


def evidence_header(index: int, item: Any) -> str:
    fonte = _fonte(item)
    parts = [fonte, _riferimento(item, fonte), _identificativo(item), _vigenza(item), _data(item)]
    return f"[{index}] " + _SEPARATORE.join(part for part in parts if part)


def format_evidence_item(index: int, item: Any, *, max_chars: int = 1600) -> tuple[str, bool]:
    """Ritorna (blocco formattato, troncato?) oppure ("", False) se senza testo."""
    testo = scrub_personal_data(_testo(item))
    if not testo:
        return "", False
    testo, troncato = _tronca(testo, max_chars)
    return f"{scrub_personal_data(evidence_header(index, item))}\n{testo}", troncato


def evidence_items(evidence: Any) -> list[Any]:
    if isinstance(evidence, dict):
        return list(evidence.get("items") or [])
    items = getattr(evidence, "items", None)
    if callable(items):
        return []
    return list(items or [])


# ---------------------------------------------------------------------------
# Dati dello studio (solo workflow sui dati dello studio)
# ---------------------------------------------------------------------------

# Sezioni del prompt_block dello studio che non servono a rispondere: canali e
# credenziali, impostazioni anagrafiche, policy già coperte dal system prompt.
_SEZIONI_STUDIO_ESCLUSE = {
    "PEC E CANALI EMAIL",
    "IMPOSTAZIONI STUDIO",
    "PROFILO STUDIO",
    "RAG DOCUMENTALE LOCALE",
    "POLICY FONTI E AFFIDABILITA",
    "POLICY ESECUTIVA LEX",
}
_CAMPI_FASCICOLO = (
    "titolo",
    "numero_rg",
    "anno_rg",
    "rg",
    "numero",
    "tribunale",
    "ufficio",
    "stato",
    "cliente",
    "nome_cliente",
    "controparte",
    "oggetto",
    "materia",
    "data_prossima_udienza",
    "prossima_udienza",
    "giudice",
)
_RUMORE_CONTESTO = {
    "workflow",
    "utente",
    "permessi",
    "sessione",
    "runtime",
    "sources",
    "citations",
    "engine_ids",
    "source_ids",
    "request_metadata",
    "execution_policy",
    "request_profile",
    "source_policy_summary",
    "best_practice",
    "telematico",
    "free_web",
}
_INDIZI_DATI_STUDIO = (
    "cliente",
    "clienti",
    "fascicol",
    "pratica",
    "udienz",
    "scadenz",
    "agenda",
    "appuntament",
    "studio",
    "r.g.",
    "rg ",
    "deposit",
    "preventiv",
    "parcell",
    "fattur",
)


def _filtra_prompt_block(block: str) -> str:
    righe: list[str] = []
    esclusa = False
    for riga in str(block or "").splitlines():
        intestazione = re.match(r"^===\s*(.+?)\s*===$", riga.strip())
        if intestazione:
            esclusa = intestazione.group(1).upper() in _SEZIONI_STUDIO_ESCLUSE
        if esclusa:
            continue
        if riga.strip():
            righe.append(riga.rstrip())
        elif righe and righe[-1]:
            righe.append("")
    return "\n".join(righe).strip()


def _compatta(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return None
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, sub in value.items():
            nome = str(key)
            if nome.lower() in _SENSITIVE_KEYS or nome in _RUMORE_CONTESTO:
                continue
            compact = _compatta(sub, depth=depth + 1)
            if compact not in (None, "", [], {}):
                out[nome] = compact
        return out
    if isinstance(value, (list, tuple)):
        return [x for x in (_compatta(v, depth=depth + 1) for v in list(value)[:8]) if x not in (None, "", [], {})]
    if isinstance(value, str):
        text = _clean(value)
        return text if len(text) <= 300 else text[:299] + "…"
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _clean(value)[:300]


def _fascicolo_compatto(fascicolo: Any) -> str:
    if not isinstance(fascicolo, dict) or not fascicolo:
        return ""
    righe = []
    for key in _CAMPI_FASCICOLO:
        value = _clean(fascicolo.get(key))
        if value:
            righe.append(f"- {key.replace('_', ' ')}: {value[:200]}")
    return ("Fascicolo:\n" + "\n".join(righe)) if righe else ""


def question_mentions_studio_data(question: str) -> bool:
    text = f" {str(question or '').lower()} "
    return any(indizio in text for indizio in _INDIZI_DATI_STUDIO)


def studio_context_needed(workflow: str, question: str, context: Any) -> bool:
    """I dati dello studio servono solo nei workflow che li riguardano."""
    if is_legal_rag_workflow(workflow):
        return False
    if not context:
        return False
    if str(workflow or "").strip().lower() in {"chat", "question_answering"}:
        fascicolo = (context or {}).get("fascicolo") if isinstance(context, dict) else None
        return bool(fascicolo) or question_mentions_studio_data(question)
    return True


def compact_studio_context(context: Any, *, max_chars: int) -> str:
    """Estratto pertinente dei dati dello studio, senza dati personali superflui."""
    if max_chars <= 0 or not context:
        return ""
    if isinstance(context, str):
        testo = context.strip()
    else:
        ctx = dict(context) if isinstance(context, dict) else {}
        studio = ctx.get("studio") if isinstance(ctx.get("studio"), dict) else {}
        structured = ctx.get("structured_context") or studio.get("structured_context") or {}
        if not isinstance(structured, dict):
            structured = {}
        parti: list[str] = []
        lettura = ctx.get("lettura_fascicolo") or structured.get("lettura_fascicolo") or {}
        narrativa = _clean(lettura.get("narrativa")) if isinstance(lettura, dict) else ""
        if narrativa:
            parti.append("Lettura del fascicolo:\n" + str(lettura.get("narrativa")).strip())
        fascicolo = ctx.get("fascicolo") or structured.get("fascicolo")
        fascicolo_txt = _fascicolo_compatto(fascicolo)
        if fascicolo_txt:
            parti.append(fascicolo_txt)
        block = _filtra_prompt_block(str(studio.get("prompt_block") or ""))
        if block:
            parti.append(block)
        if not parti:
            compatto = _compatta({k: v for k, v in ctx.items() if k not in _RUMORE_CONTESTO and k != "studio"})
            if structured and not compatto:
                compatto = _compatta(structured)
            if compatto:
                parti.append(json.dumps(compatto, ensure_ascii=False, separators=(",", ":"), default=str))
        testo = "\n\n".join(parti)
    testo = scrub_personal_data(testo)
    testo, _ = _tronca(testo, max_chars)
    return testo


# ---------------------------------------------------------------------------
# Messaggio utente entro il budget
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PromptPlan:
    system_prompt: str
    user_message: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def messages(self) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_message},
        ]


def build_rag_prompt(
    *,
    system_prompt: str,
    question: str,
    evidence: Any,
    workflow: str,
    context: Any,
    settings: LexGenerationSettings,
) -> PromptPlan:
    """Messaggio "Domanda / [Dati dello studio] / Fonti" entro il budget di token."""
    domanda = _clean(question) or "Richiesta senza testo."
    domanda_blocco = f"Domanda:\n{domanda}"
    budget = settings.input_budget_tokens
    fissi = estimate_tokens(system_prompt) + estimate_tokens(domanda_blocco) + estimate_tokens("\n\nFonti:\n")
    disponibili = budget - fissi

    studio_txt = ""
    studio_incluso = False
    if studio_context_needed(workflow, domanda, context):
        # I dati dello studio non possono occupare piu' di meta' dello spazio
        # residuo: il resto e' per le fonti.
        tetto = min(settings.studio_context_max_chars, _chars_for_tokens(max(disponibili // 2, 0)))
        studio_txt = compact_studio_context(context, max_chars=tetto)
        if studio_txt:
            studio_incluso = True
            disponibili -= estimate_tokens(f"\n\nDati dello studio:\n{studio_txt}")

    items = evidence_items(evidence)[: max(settings.max_evidence_items, 0)]
    blocchi: list[str] = []
    inclusi: list[int] = []
    esclusi_budget: list[int] = []
    senza_testo: list[int] = []
    troncati: list[int] = []
    mappa: dict[str, int] = {}
    budget_esaurito = False
    for posizione, item in enumerate(items, start=1):
        if budget_esaurito:
            esclusi_budget.append(posizione)
            continue
        numero = len(blocchi) + 1
        blocco, troncato = format_evidence_item(numero, item, max_chars=settings.evidence_max_chars)
        if not blocco:
            senza_testo.append(posizione)
            continue
        costo = estimate_tokens(blocco) + 1
        if costo > disponibili:
            # Ultima fonte ammessa: si accorcia se resta uno spazio utile,
            # altrimenti si escludono questa e tutte le meno rilevanti.
            spazio = _chars_for_tokens(disponibili - 1) - len(evidence_header(numero, item)) - 1
            if spazio >= 300:
                blocco, _ = format_evidence_item(numero, item, max_chars=spazio)
                troncato = True
                costo = estimate_tokens(blocco) + 1
            if costo > disponibili or spazio < 300:
                budget_esaurito = True
                esclusi_budget.append(posizione)
                continue
        blocchi.append(blocco)
        inclusi.append(posizione)
        mappa[str(numero)] = posizione
        if troncato:
            troncati.append(numero)
        disponibili -= costo

    sezioni = [domanda_blocco]
    if studio_incluso:
        sezioni.append(f"Dati dello studio:\n{studio_txt}")
    sezioni.append("Fonti:\n" + ("\n\n".join(blocchi) if blocchi else "Nessuna fonte disponibile."))
    user_message = "\n\n".join(sezioni)

    system_tokens = estimate_tokens(system_prompt)
    user_tokens = estimate_tokens(user_message)
    stimati = system_tokens + user_tokens
    metadata = {
        "num_ctx": settings.num_ctx,
        "num_predict": settings.num_predict,
        "budget_input_tokens": budget,
        "system_tokens_stimati": system_tokens,
        "user_tokens_stimati": user_tokens,
        "prompt_tokens_stimati": stimati,
        "user_chars": len(user_message),
        "evidenze_disponibili": len(evidence_items(evidence)),
        "evidenze_incluse": inclusi,
        "evidenze_escluse_budget": esclusi_budget,
        "evidenze_senza_testo": senza_testo,
        "evidenze_troncate": troncati,
        "mappa_citazioni": mappa,
        "contesto_studio_incluso": studio_incluso,
        "contesto_studio_chars": len(studio_txt),
        "budget_superato": stimati > budget,
    }
    if stimati > budget:
        # Succede solo se system prompt + domanda superano da soli il budget:
        # non si tagliano mai, si segnala.
        logger.warning(
            "Lex: system prompt e domanda superano il budget di contesto (%s > %s token stimati).",
            stimati,
            budget,
        )
    return PromptPlan(system_prompt=system_prompt, user_message=user_message, metadata=metadata)


# ---------------------------------------------------------------------------
# Controllo del troncamento dopo la risposta
# ---------------------------------------------------------------------------


def check_prompt_eval(plan_metadata: dict[str, Any], stats: dict[str, Any]) -> dict[str, Any]:
    """Confronta `prompt_eval_count` di Ollama con la stima e segnala troncamenti.

    Si confronta con la stima del solo messaggio utente: il system prompt fisso
    può essere servito dalla cache del prefisso e non contare in
    `prompt_eval_count`, mentre il messaggio utente cambia sempre.
    """
    result: dict[str, Any] = {}
    try:
        count = int(stats.get("prompt_eval_count"))
    except (TypeError, ValueError):
        return result
    result["prompt_eval_count"] = count
    for key in ("eval_count", "total_duration", "prompt_eval_duration", "eval_duration", "load_duration"):
        if stats.get(key) is not None:
            result[key] = stats.get(key)
    atteso = int(plan_metadata.get("user_tokens_stimati") or 0)
    if atteso >= 256 and count < atteso * 0.5:
        result["possibile_troncamento"] = True
        logger.warning(
            "Lex: possibile troncamento del prompt da parte del modello "
            "(prompt_eval_count=%s, token stimati del messaggio=%s, num_ctx=%s).",
            count,
            atteso,
            plan_metadata.get("num_ctx"),
        )
    else:
        result["possibile_troncamento"] = False
    return result


# ---------------------------------------------------------------------------
# Rimozione del ragionamento <think>
# ---------------------------------------------------------------------------

_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.IGNORECASE | re.DOTALL)
_THINK_OPEN_RE = re.compile(r"<think\b[^>]*>", re.IGNORECASE)
_THINK_CLOSE_RE = re.compile(r"</think\s*>", re.IGNORECASE)


def strip_think(text: str) -> str:
    """Toglie i blocchi <think>...</think>, anche non chiusi o senza apertura."""
    value = str(text or "")
    if not value:
        return ""
    value = _THINK_BLOCK_RE.sub("", value)
    # Chiusura senza apertura (il template del modello apre il blocco): tutto
    # quello che precede l'ultima chiusura è ragionamento.
    closes = list(_THINK_CLOSE_RE.finditer(value))
    if closes:
        value = value[closes[-1].end():]
    # Apertura senza chiusura (risposta interrotta): si scarta dal tag in poi.
    opened = _THINK_OPEN_RE.search(value)
    if opened:
        value = value[: opened.start()]
    return value.strip()


class ThinkStreamFilter:
    """Filtro incrementale per lo streaming: non emette mai il contenuto di <think>."""

    _OPEN = "<think>"
    _CLOSE = "</think>"

    def __init__(self) -> None:
        self._buffer = ""
        self._inside = False

    @staticmethod
    def _partial_suffix(text: str, tag: str) -> int:
        lower = text.lower()
        for size in range(min(len(tag) - 1, len(text)), 0, -1):
            if tag.startswith(lower[-size:]):
                return size
        return 0

    def feed(self, chunk: str) -> str:
        self._buffer += str(chunk or "")
        out: list[str] = []
        while self._buffer:
            lower = self._buffer.lower()
            if self._inside:
                end = lower.find(self._CLOSE)
                if end < 0:
                    keep = self._partial_suffix(self._buffer, self._CLOSE)
                    self._buffer = self._buffer[len(self._buffer) - keep:] if keep else ""
                    break
                self._buffer = self._buffer[end + len(self._CLOSE):]
                self._inside = False
                continue
            start = lower.find(self._OPEN)
            if start < 0:
                keep = self._partial_suffix(self._buffer, self._OPEN)
                emit = self._buffer[: len(self._buffer) - keep] if keep else self._buffer
                out.append(emit)
                self._buffer = self._buffer[len(emit):]
                break
            out.append(self._buffer[:start])
            self._buffer = self._buffer[start + len(self._OPEN):]
            self._inside = True
        return "".join(out)

    def flush(self) -> str:
        rest = "" if self._inside else self._buffer
        self._buffer = ""
        return rest


__all__ = [
    "CHARS_PER_TOKEN",
    "PromptPlan",
    "ThinkStreamFilter",
    "build_rag_prompt",
    "check_prompt_eval",
    "compact_studio_context",
    "estimate_tokens",
    "evidence_header",
    "evidence_items",
    "format_evidence_item",
    "question_mentions_studio_data",
    "scrub_personal_data",
    "strip_think",
    "studio_context_needed",
]
