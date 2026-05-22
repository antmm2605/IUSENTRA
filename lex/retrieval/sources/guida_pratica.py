"""Sorgente Lex per la Guida Pratica IUSENTRA.

La sorgente espone a Lex il knowledge base operativo della guida pratica senza
trasformarlo in un requisito bloccante per il fascicolo. Il codice ufficiale di
deposito resta una proprietà separata e viene sempre marcato nei metadati.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Any

from lex.contracts import EvidenceItem
from pct.guida_pratica.service import GuidaPraticaError, GuidaPraticaService, normalize_codice_materia

_CODE_RE = re.compile(r"\b(?:\d{5,6}|GUIDA_[A-Z0-9_]{4,})\b", re.IGNORECASE)
_GUIDE_HINTS = (
    "guida pratica",
    "scheda pratica",
    "guida operativa",
    "checklist",
    "cosa verificare",
    "come procedere",
    "come affrontare",
    "atto da redigere",
    "allegati obbligatori",
    "campi obbligatori",
    "adempimenti",
    "codice oggetto",
    "pst",
    "xsd",
    "deposito",
)
_STOPWORDS = {
    "alla",
    "alle",
    "anche",
    "atto",
    "atti",
    "codice",
    "come",
    "con",
    "cosa",
    "da",
    "del",
    "della",
    "delle",
    "devo",
    "fare",
    "fascicolo",
    "guida",
    "il",
    "in",
    "la",
    "per",
    "pratica",
    "procedere",
    "scheda",
    "studio",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value or []) if isinstance(value, list) else []


def _fold(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", _clean(value).casefold())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9_]+", " ", ascii_text).strip()


def _tokens(*values: Any) -> set[str]:
    out: set[str] = set()
    for value in values:
        for token in _fold(value).split():
            if token.isdigit() or len(token) < 3 or token in _STOPWORDS:
                continue
            out.add(token)
    return out


def _field(payload: dict[str, Any], *names: str) -> str:
    for name in names:
        value = _clean(payload.get(name))
        if value:
            return value
    return ""


def _structured_context(context: Any) -> dict[str, Any]:
    payload = _as_dict(context)
    structured = payload.get("structured_context")
    return _as_dict(structured) if isinstance(structured, dict) else payload


def _active_context(request: Any, context: Any) -> dict[str, Any]:
    metadata = _as_dict(getattr(request, "metadata", {}) or {})
    active = metadata.get("active_context") if isinstance(metadata.get("active_context"), dict) else {}
    ctx_active = _as_dict(_as_dict(context).get("active_context"))
    return {**ctx_active, **_as_dict(active)}


def _fascicolo_context(request: Any, context: Any) -> dict[str, Any]:
    structured = _structured_context(context)
    metadata = _as_dict(getattr(request, "metadata", {}) or {})
    active = _active_context(request, context)
    fascicolo = _as_dict(structured.get("fascicolo"))
    metadata_fascicolo = metadata.get("fascicolo") if isinstance(metadata.get("fascicolo"), dict) else {}
    out = {**_as_dict(metadata_fascicolo), **fascicolo}
    for source in (active, metadata):
        for key in (
            "id",
            "title",
            "titolo",
            "oggetto",
            "object",
            "codice_oggetto_pst",
            "codiceOggettoPst",
            "codice_materia",
            "codiceMateria",
            "tipo_procedimento",
            "procedureType",
            "area_pratica",
            "practiceArea",
        ):
            if _clean(source.get(key)) and not _clean(out.get(key)):
                out[key] = source.get(key)
    if getattr(request, "fascicolo_id", None) and not _clean(out.get("id")):
        out["id"] = getattr(request, "fascicolo_id", "")
    return out


def _extract_codes(request: Any, context: Any, queries: list[str]) -> list[str]:
    values: list[Any] = [*queries, getattr(request, "query", "")]
    metadata = _as_dict(getattr(request, "metadata", {}) or {})
    active = _active_context(request, context)
    fascicolo = _fascicolo_context(request, context)
    for source in (metadata, active, fascicolo):
        for key in (
            "codice_oggetto_pst",
            "codiceOggettoPst",
            "codice_materia",
            "codiceMateria",
            "codice_pratica",
            "practiceCode",
            "matter_code",
            "guida_pratica_codice",
            "guidaPraticaCodice",
        ):
            values.append(source.get(key))
    codes: list[str] = []
    for value in values:
        text = _clean(value)
        if not text:
            continue
        direct = normalize_codice_materia(text)
        if direct and (direct.isdigit() or direct.startswith("GUIDA_")):
            codes.append(direct)
        for match in _CODE_RE.findall(text):
            codes.append(normalize_codice_materia(match))
    out: list[str] = []
    for code in codes:
        if code and code not in out:
            out.append(code)
    return out


def _should_search_text(text: str, *, has_context: bool) -> bool:
    folded = _fold(text)
    if not folded:
        return False
    if _CODE_RE.search(text):
        return True
    if any(hint in folded for hint in _GUIDE_HINTS):
        return True
    if has_context and any(token in folded for token in ("allegati", "adempimenti", "redigere", "verificare")):
        return True
    return len(_tokens(text)) >= 2 and any(token in folded for token in ("licenziamento", "tutela", "divisione", "compravendita", "sfratto", "ingiuntivo"))


def _item_to_text(value: Any) -> str:
    if isinstance(value, dict):
        parts = [
            value.get("step"),
            value.get("fonte"),
            value.get("articolo"),
            value.get("label"),
            value.get("azione"),
            value.get("termine"),
            value.get("sezione"),
            value.get("contenuto"),
            value.get("descrizione"),
            value.get("note"),
        ]
        text = " - ".join(_clean(part) for part in parts if _clean(part))
        if not text and value:
            text = ", ".join(f"{key}: {_clean(item)}" for key, item in value.items() if _clean(item))
        return text
    return _clean(value)


def _section(label: str, values: Any, *, limit: int = 24) -> str:
    if isinstance(values, dict):
        flat: list[Any] = []
        for key, value in values.items():
            if isinstance(value, list):
                flat.extend(value)
            elif _clean(value):
                flat.append({key: value})
        values = flat
    items = [_item_to_text(item) for item in _as_list(values)]
    items = [item for item in items if item]
    if not items:
        return ""
    shown = items[:limit]
    suffix = f"; altri elementi presenti: {len(items) - limit}" if len(items) > limit else ""
    return f"{label}: " + "; ".join(shown) + suffix + "."


def _quick_line(guidance: dict[str, Any]) -> str:
    quick = _as_dict(guidance.get("quick_help"))
    parts = [
        f"prima verifica: {_clean(quick.get('prima_cosa_da_fare'))}" if _clean(quick.get("prima_cosa_da_fare")) else "",
        f"atto da preparare: {_clean(quick.get('atto_da_redigere'))}" if _clean(quick.get("atto_da_redigere")) else "",
        f"campi obbligatori: {quick.get('totale_campi_obbligatori')}" if quick.get("totale_campi_obbligatori") is not None else "",
        f"allegati obbligatori: {quick.get('totale_allegati_obbligatori')}" if quick.get("totale_allegati_obbligatori") is not None else "",
    ]
    return "; ".join(part for part in parts if part)


def _guidance_content(guidance: dict[str, Any], *, matched_by: str) -> str:
    atto = _as_dict(guidance.get("atto_principale"))
    deposito = _as_dict(guidance.get("codice_deposito"))
    coverage = _as_dict(guidance.get("coverage"))
    lines = [
        f"Guida pratica interna facoltativa: {_clean(guidance.get('denominazione'))}.",
        f"Codice guida: {_clean(guidance.get('codice'))}.",
        f"Motivo aggancio Lex: {matched_by}." if matched_by else "",
        f"Categoria: {_clean(guidance.get('categoria'))}." if _clean(guidance.get("categoria")) else "",
        f"Sottocategoria: {_clean(guidance.get('sottocategoria'))}." if _clean(guidance.get("sottocategoria")) else "",
        f"Rito: {_clean(guidance.get('rito'))}." if _clean(guidance.get("rito")) else "",
        f"Competenza: {_clean(guidance.get('competenza'))}." if _clean(guidance.get("competenza")) else "",
        f"Uffici destinatari: {', '.join(_clean(item) for item in _as_list(guidance.get('uffici_destinatari')) if _clean(item))}." if _as_list(guidance.get("uffici_destinatari")) else "",
        "Codice deposito: ufficiale PST/XSD caricato." if deposito.get("depositabile") else "Codice deposito: guida interna non depositabile; per il deposito selezionare il codice ministeriale ufficiale nella scheda fascicolo.",
        f"Copertura: {_clean(coverage.get('level'))} - {_clean(coverage.get('message'))}." if coverage else "",
        _quick_line(guidance),
        _section("Normativa letta dalla scheda", guidance.get("normativa"), limit=28),
        _section("Presupposti sostanziali", guidance.get("presupposti_sostanziali") or guidance.get("presupposti_sostanziali_gmo"), limit=24),
        _section("Adempimenti propedeutici", guidance.get("adempimenti_propedeutici"), limit=24),
        f"Atto principale: {_clean(atto.get('denominazione') or atto.get('tipo_atto'))}." if atto else "",
        f"Schema XSD indicato: {_clean(atto.get('schema_xsd_ministeriale'))}." if _clean(atto.get("schema_xsd_ministeriale")) else "",
        _section("Struttura obbligatoria dell'atto", atto.get("struttura_obbligatoria"), limit=24),
        _section("Campi obbligatori o chiave", atto.get("campi_obbligatori") or atto.get("campi_chiave") or atto.get("campi_specifici"), limit=28),
        _section("Avvertimenti redazionali obbligatori", atto.get("avvertimenti_obbligatori"), limit=24),
        _section("Allegati obbligatori", guidance.get("allegati_obbligatori"), limit=28),
        _section("Adempimenti fiscali e telematici", guidance.get("adempimenti_fiscali_telematici") or guidance.get("adempimenti_fiscali"), limit=20),
        _section("Termini processuali", guidance.get("termini_processuali"), limit=20),
        _section("Atti collegati", guidance.get("atti_collegati"), limit=20),
        _section("Esiti processuali tipici", guidance.get("esiti_processuali_tipici"), limit=20),
        _section("Avvertenze redazionali", guidance.get("avvertenze_redazionali"), limit=24),
        f"Nota integrazione: {_clean(guidance.get('nota_integrazione_iusentra'))}." if _clean(guidance.get("nota_integrazione_iusentra")) else "",
    ]
    original = _clean(guidance.get("codice_originale_ricevuto"))
    if original:
        lines.append(f"Codice ricevuto in origine: {original}; non viene forzato come codice ufficiale se non combacia con il catalogo ministeriale locale.")
    related = [_clean(item) for item in _as_list(guidance.get("codici_ufficiali_correlati_da_valutare")) if _clean(item)]
    if related:
        lines.append("Codici ufficiali correlati da valutare nella scheda fascicolo: " + ", ".join(related) + ".")
    return "\n".join(line for line in lines if _clean(line))


def _compact_metadata(guidance: dict[str, Any]) -> dict[str, Any]:
    deposito = _as_dict(guidance.get("codice_deposito"))
    coverage = _as_dict(guidance.get("coverage"))
    atto = _as_dict(guidance.get("atto_principale"))
    return {
        "codice": _clean(guidance.get("codice")),
        "denominazione": _clean(guidance.get("denominazione")),
        "categoria": _clean(guidance.get("categoria")),
        "sottocategoria": _clean(guidance.get("sottocategoria")),
        "coverage_level": _clean(coverage.get("level")),
        "coverage_message": _clean(coverage.get("message")),
        "deposit_code_official": bool(deposito.get("ufficiale")),
        "depositable": bool(deposito.get("depositabile")),
        "deposit_code_message": _clean(deposito.get("messaggio")),
        "schema_xsd": _clean(atto.get("schema_xsd_ministeriale")),
        "atto_principale": _clean(atto.get("denominazione") or atto.get("tipo_atto")),
        "codice_originale_ricevuto": _clean(guidance.get("codice_originale_ricevuto")),
        "codici_ufficiali_correlati_da_valutare": [
            _clean(item) for item in _as_list(guidance.get("codici_ufficiali_correlati_da_valutare")) if _clean(item)
        ],
        "guida_pratica_facoltativa": True,
        "full_guidance_available": True,
        "linguistic_profile": "conversazionale_avvocato",
    }


@lru_cache(maxsize=1)
def _default_service() -> GuidaPraticaService:
    return GuidaPraticaService()


class GuidaPraticaSource:
    source_name = "guida_pratica"

    def __init__(self, *, limit: int = 5, service: GuidaPraticaService | None = None) -> None:
        self.limit = max(1, min(int(limit or 5), 10))
        self.service = service or _default_service()

    def search(self, queries, request, context):
        metadata = _as_dict(getattr(request, "metadata", {}) or {})
        if _clean(metadata.get("disable_guida_pratica_source")).lower() in {"1", "true", "vero", "si"}:
            return []
        query_values = [_clean(item) for item in list(queries or []) if _clean(item)]
        if _clean(getattr(request, "query", "")) not in query_values:
            query_values.insert(0, _clean(getattr(request, "query", "")))
        fascicolo = _fascicolo_context(request, context)
        seen: set[str] = set()
        results: list[EvidenceItem] = []

        for code in _extract_codes(request, context, query_values):
            self._append_code(results, seen, code, fascicolo=fascicolo, matched_by="codice indicato o presente nel fascicolo")
            if len(results) >= self.limit:
                return results

        suggestion = self._suggest_from_fascicolo(fascicolo)
        if suggestion:
            self._append_code(
                results,
                seen,
                _clean(suggestion.get("codice")),
                fascicolo=fascicolo,
                matched_by=f"suggerimento da {suggestion.get('source_field') or 'oggetto fascicolo'}",
                extra_metadata={"suggested_from_fascicolo": True, "suggestion": suggestion},
            )

        should_search = any(_should_search_text(query, has_context=bool(fascicolo)) for query in query_values)
        if should_search:
            for code, reason in self._search_codes(query_values):
                self._append_code(results, seen, code, fascicolo=fascicolo, matched_by=reason)
                if len(results) >= self.limit:
                    return results
        return results

    def _known_code(self, code: str) -> bool:
        kb_index = getattr(self.service, "_kb_index", {}) or {}
        catalog_index = getattr(self.service, "_catalog_index", {}) or {}
        return code in kb_index or code in catalog_index

    def _append_code(
        self,
        results: list[EvidenceItem],
        seen: set[str],
        code: str,
        *,
        fascicolo: dict[str, Any],
        matched_by: str,
        extra_metadata: dict[str, Any] | None = None,
    ) -> None:
        normalized = normalize_codice_materia(code)
        if not normalized or normalized in seen or not self._known_code(normalized):
            return
        try:
            guidance = self.service.get_guidance(normalized, fascicolo=fascicolo)
        except (GuidaPraticaError, ValueError):
            return
        deposito = _as_dict(guidance.get("codice_deposito"))
        metadata = _compact_metadata(guidance)
        metadata.update(extra_metadata or {})
        metadata["authority"] = "iusentra_guida_pratica"
        metadata["matched_by"] = matched_by
        metadata["source_registry_key"] = "iusentra_guida_pratica"
        metadata["source_category"] = "knowledge_base_interna"
        metadata["source_access_status"] = "available"
        metadata["guidance_payload"] = guidance
        results.append(
            EvidenceItem(
                source_type="guida_pratica",
                source_id=normalized,
                title=f"Guida pratica - {_clean(guidance.get('denominazione')) or normalized}",
                content=_guidance_content(guidance, matched_by=matched_by),
                score=0.94 if deposito.get("depositabile") else 0.88,
                metadata=metadata,
                trust_class="B",
                source_level=3,
                trust_score=0.88,
                freshness_score=0.82,
                context_fit_score=0.9,
                consensus_score=0.78,
                verified_reference=True,
                authority="iusentra_guida_pratica",
            )
        )
        seen.add(normalized)

    def _suggest_from_fascicolo(self, fascicolo: dict[str, Any]) -> dict[str, Any] | None:
        if not fascicolo:
            return None
        if _clean(
            fascicolo.get("codice_oggetto_pst")
            or fascicolo.get("codiceOggettoPst")
            or fascicolo.get("codice_materia")
            or fascicolo.get("codiceMateria")
        ):
            return None
        try:
            return self.service.suggest_guidance_from_fascicolo(fascicolo)
        except Exception:
            return None

    def _search_codes(self, query_values: list[str]) -> list[tuple[str, str]]:
        rows = self.service.list_guidance(limit=5000)
        query_text = " ".join(query_values)
        query_tokens = _tokens(query_text)
        query_folded = _fold(query_text)
        scored: list[tuple[float, str, str]] = []
        if not query_tokens and not _CODE_RE.search(query_text):
            return []
        for row in rows:
            code = normalize_codice_materia(row.get("codice"))
            if not code:
                continue
            label = " ".join(
                _clean(row.get(key))
                for key in ("codice", "denominazione", "area", "area_label", "parent_label", "registri", "file_fonte")
                if _clean(row.get(key))
            )
            hay_tokens = _tokens(label)
            hay_folded = _fold(label)
            if code.lower() in query_folded:
                scored.append((1.0, code, "codice cercato nella domanda"))
                continue
            if not hay_tokens:
                continue
            overlap = query_tokens & hay_tokens
            if not overlap:
                continue
            recall = len(overlap) / max(1, len(query_tokens))
            precision = len(overlap) / max(1, len(hay_tokens))
            phrase_bonus = 0.15 if len(query_folded) >= 12 and (query_folded in hay_folded or hay_folded in query_folded) else 0.0
            score = 0.42 + (recall * 0.38) + (precision * 0.22) + phrase_bonus
            if score < 0.62:
                continue
            reason = "termini della domanda presenti nella guida: " + ", ".join(sorted(overlap)[:6])
            scored.append((min(score, 0.99), code, reason))
        scored.sort(key=lambda item: item[0], reverse=True)
        out: list[tuple[str, str]] = []
        seen: set[str] = set()
        for _score, code, reason in scored:
            if code in seen:
                continue
            seen.add(code)
            out.append((code, reason))
            if len(out) >= self.limit:
                break
        return out
