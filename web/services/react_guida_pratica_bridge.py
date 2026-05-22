"""Bridge React/API per Guida Pratica fascicolo.

Il bridge resta sottile: risolve il fascicolo dai repository esistenti, usa il
codice materia quando presente o l'oggetto/titolo quando il codice non è stato
ancora salvato, e delega la conoscenza a `pct.guida_pratica.GuidaPraticaService`.
"""

from __future__ import annotations

from datetime import UTC, datetime
import unicodedata
from urllib.parse import urlencode
from typing import Any, Callable

from pct.guida_pratica import GuidaPraticaError, GuidaPraticaService, normalize_codice_materia


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text if text else default


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _normalizza_testo(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", _text(value).lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _short(value: Any, limit: int = 180) -> str:
    text = _text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _safe(label: str, func: Callable[[], Any], fallback: Any) -> Any:
    try:
        return func()
    except Exception:
        return fallback


def _document_context(doc: Any) -> dict[str, Any]:
    return {
        "id": _text(getattr(doc, "id", "")),
        "nome": _text(getattr(doc, "nome", ""), "Documento"),
        "tipo": _enum_value(getattr(doc, "tipo", "")),
        "data_documento": _text(getattr(doc, "data_documento", "")),
        "firmato": bool(getattr(doc, "firmato", False) or getattr(doc, "firmato_digitalmente", False)),
        "fonte": _text(getattr(doc, "fonte_documento", "")),
        "note": _short(getattr(doc, "note", "")),
    }


def _attivita_context(attivita: Any) -> dict[str, Any]:
    return {
        "id": _text(getattr(attivita, "id", "")),
        "tipo": _enum_value(getattr(attivita, "tipo", "")),
        "data": _text(getattr(attivita, "data", "")),
        "titolo": _text(getattr(attivita, "titolo", "")),
        "descrizione": _short(getattr(attivita, "descrizione", "")),
        "esito": _enum_value(getattr(attivita, "esito", "")),
        "luogo": _text(getattr(attivita, "luogo", "")),
        "note": _short(getattr(attivita, "note", "")),
        "id_documento": _text(getattr(attivita, "id_documento", "")),
        "id_deposito_pct": _text(getattr(attivita, "id_deposito_pct", "")),
    }


def _amount(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _fascicolo_lookup_keys(fascicolo: Any) -> set[str]:
    fields = (
        "id",
        "id_pratica",
        "numero",
        "numero_interno",
        "numero_rg",
        "riferimento",
        "reference",
        "codice",
        "codice_fascicolo",
        "source_external_id",
        "import_log_id",
    )
    keys = {_text(getattr(fascicolo, field, "")) for field in fields}
    keys.update({_text(getattr(fascicolo, "id", "")).upper(), _text(getattr(fascicolo, "id", "")).lower()})
    return {key for key in keys if key}


def resolve_fascicolo_for_guida(get_fascicoli: Callable[[], Any], requested_id: str) -> Any | None:
    repo = get_fascicoli()
    direct = _safe("fascicolo_direct", lambda: repo.get(requested_id), None)
    if direct:
        return direct
    wanted = _text(requested_id).casefold()
    if not wanted:
        return None
    for fascicolo in _safe("fascicoli_all", lambda: repo.tutti(), []):
        if wanted in {key.casefold() for key in _fascicolo_lookup_keys(fascicolo)}:
            return fascicolo
    return None


def fascicolo_guida_context(fascicolo: Any) -> dict[str, Any]:
    documenti = [_document_context(doc) for doc in list(getattr(fascicolo, "documenti", []) or [])[:40]]
    attivita = [_attivita_context(item) for item in list(getattr(fascicolo, "attivita", []) or [])[:60]]
    valore_preventivato = _amount(getattr(fascicolo, "valore_preventivato", 0))
    compenso_pattuito = _amount(getattr(fascicolo, "compenso_pattuito", 0))
    scadenze_date = [
        {"tipo": "prima_udienza", "data": _text(getattr(fascicolo, "data_prima_udienza", ""))},
        {"tipo": "notifica_citazione", "data": _text(getattr(fascicolo, "data_notifica_citazione", ""))},
        {"tipo": "prossima_udienza", "data": _text(getattr(fascicolo, "data_prossima_udienza", ""))},
    ]
    return {
        "id": _text(getattr(fascicolo, "id", "")),
        "id_cliente": _text(getattr(fascicolo, "id_cliente", "")),
        "titolo": _text(getattr(fascicolo, "titolo", "") or getattr(fascicolo, "oggetto", "")),
        "title": _text(getattr(fascicolo, "titolo", "") or getattr(fascicolo, "oggetto", "")),
        "oggetto": _text(getattr(fascicolo, "oggetto", "")),
        "object": _text(getattr(fascicolo, "oggetto", "")),
        "tipo": _enum_value(getattr(fascicolo, "tipo", "")),
        "stato": _enum_value(getattr(fascicolo, "stato", "")),
        "tipo_procedimento": _text(getattr(fascicolo, "tipo_procedimento", "")),
        "procedureType": _text(getattr(fascicolo, "tipo_procedimento", "")),
        "area_pratica": _text(getattr(fascicolo, "area_pratica", "")),
        "practiceArea": _text(getattr(fascicolo, "area_pratica", "")),
        "procedura_operativa_nome": _text(getattr(fascicolo, "procedura_operativa_nome", "")),
        "proceduraOperativaNome": _text(getattr(fascicolo, "procedura_operativa_nome", "")),
        "cliente": _text(getattr(fascicolo, "nome_cliente", "")),
        "controparte": _text(getattr(fascicolo, "controparte", "")),
        "parti": [
            {"ruolo": "Cliente", "nome": _text(getattr(fascicolo, "nome_cliente", ""))},
            {"ruolo": "Controparte", "nome": _text(getattr(fascicolo, "controparte", ""))},
        ],
        "tribunale": _text(getattr(fascicolo, "tribunale", "")),
        "ufficio": _text(getattr(fascicolo, "tribunale", "")),
        "numero_rg": _text(getattr(fascicolo, "numero_rg", "")),
        "anno_rg": _text(getattr(fascicolo, "anno_rg", "")),
        "codice_oggetto_pst": normalize_codice_materia(getattr(fascicolo, "codice_oggetto_pst", "")),
        "codiceOggettoPst": normalize_codice_materia(getattr(fascicolo, "codice_oggetto_pst", "")),
        "fonte_codice_oggetto": _text(getattr(fascicolo, "fonte_codice_oggetto", "")),
        "fonteCodiceOggetto": _text(getattr(fascicolo, "fonte_codice_oggetto", "")),
        "file_fonte_codice_oggetto": _text(getattr(fascicolo, "file_fonte_codice_oggetto", "")),
        "fileFonteCodiceOggetto": _text(getattr(fascicolo, "file_fonte_codice_oggetto", "")),
        "valore_causa": _text(getattr(fascicolo, "valore_causa", "")),
        "valore_preventivato": valore_preventivato,
        "compenso_pattuito": compenso_pattuito,
        "preventivo": {
            "presente": valore_preventivato > 0,
            "valore": valore_preventivato,
            "fonte": "fascicolo",
        },
        "conferimento_incarico": {
            "presente": compenso_pattuito > 0 or bool(_text(getattr(fascicolo, "id_pratica", ""))),
            "compenso_pattuito": compenso_pattuito,
            "id_pratica": _text(getattr(fascicolo, "id_pratica", "")),
        },
        "parcella": {
            "presente": bool(_text(getattr(fascicolo, "id_parcella", "") or getattr(fascicolo, "parcella_id", ""))),
            "id": _text(getattr(fascicolo, "id_parcella", "") or getattr(fascicolo, "parcella_id", "")),
        },
        "procura_delega": {
            "presente": any("procura" in _normalizza_testo(item.get("nome") or item.get("tipo")) for item in documenti),
        },
        "privacy": {"presente": any("privacy" in _normalizza_testo(item.get("nome") or item.get("tipo")) for item in documenti)},
        "antiriciclaggio": {
            "presente": any("antiriciclaggio" in _normalizza_testo(item.get("nome") or item.get("tipo")) for item in documenti),
        },
        "conflitto_interessi": {
            "presente": any("conflitto" in _normalizza_testo(item.get("nome") or item.get("note")) for item in documenti),
        },
        "documenti": documenti,
        "documenti_count": len(getattr(fascicolo, "documenti", []) or []),
        "attivita": attivita,
        "attivita_count": len(getattr(fascicolo, "attivita", []) or []),
        "scadenze": [item for item in scadenze_date if item["data"]],
        "note": _short(getattr(fascicolo, "note", ""), 600),
        "note_riservate_presenti": bool(_text(getattr(fascicolo, "note_riservate", ""))),
    }


def _template_search_tokens(guida: dict[str, Any], fascicolo: dict[str, Any]) -> list[str]:
    atto = guida.get("atto_principale") if isinstance(guida.get("atto_principale"), dict) else {}
    quick = guida.get("quick_help") if isinstance(guida.get("quick_help"), dict) else {}
    raw_values = [
        guida.get("codice"),
        guida.get("denominazione"),
        guida.get("categoria"),
        guida.get("sottocategoria"),
        atto.get("denominazione") if isinstance(atto, dict) else "",
        atto.get("tipo_atto") if isinstance(atto, dict) else "",
        quick.get("atto_da_redigere") if isinstance(quick, dict) else "",
        fascicolo.get("oggetto"),
        fascicolo.get("titolo"),
        fascicolo.get("tipo"),
        fascicolo.get("tipo_procedimento"),
        fascicolo.get("area_pratica"),
        fascicolo.get("procedura_operativa_nome"),
        fascicolo.get("tribunale"),
    ]
    tokens: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        normalized = _normalizza_testo(value)
        if not normalized:
            continue
        for token in normalized.replace("/", " ").replace(",", " ").split():
            if len(token) < 4 or token in seen:
                continue
            tokens.append(token)
            seen.add(token)
    return tokens[:30]


_TEMPLATE_GENERIC_TOKENS = {
    "atto",
    "atti",
    "citazione",
    "ricorso",
    "istanza",
    "sentenza",
    "ordinaria",
    "straordinaria",
    "procedimento",
    "civile",
    "art",
    "cpc",
    "c",
    "p",
    "ex",
    "per",
    "del",
    "della",
    "delle",
    "degli",
}


def _specific_template_tokens(guida: dict[str, Any], fascicolo: dict[str, Any]) -> list[str]:
    tokens = _template_search_tokens(guida, fascicolo)
    return [token for token in tokens if token not in _TEMPLATE_GENERIC_TOKENS and not token.isdigit()][:12]


def _template_row_text(row: dict[str, Any]) -> str:
    values: list[Any] = [
        row.get("codice"),
        row.get("titolo"),
        row.get("tipo_atto"),
        row.get("descrizione"),
        row.get("materia"),
        row.get("area"),
        row.get("macro_area"),
        row.get("sottobranca"),
        row.get("procedimento"),
        row.get("rito"),
        row.get("fase"),
        row.get("canale_deposito"),
        row.get("portale_deposito"),
    ]
    values.extend(row.get("tags") or [] if isinstance(row.get("tags"), list) else [])
    return _normalizza_testo(" ".join(_text(value) for value in values if _text(value)))


def _template_row_tokens(row: dict[str, Any]) -> set[str]:
    return {token for token in _template_row_text(row).split() if token}


def _template_row_primary_tokens(row: dict[str, Any]) -> set[str]:
    primary = " ".join(
        _text(value)
        for value in (row.get("titolo"), row.get("tipo_atto"), row.get("link_compilatore_code"))
        if _text(value)
    )
    return {token for token in _normalizza_testo(primary).split() if token}


def _score_template(row: dict[str, Any], guida: dict[str, Any], fascicolo: dict[str, Any], tokens: list[str]) -> tuple[int, list[str]]:
    row_text = _template_row_text(row)
    row_tokens = _template_row_tokens(row)
    if not row_text:
        return 0, []
    score = 0
    reasons: list[str] = []
    atto = guida.get("atto_principale") if isinstance(guida.get("atto_principale"), dict) else {}
    atto_name = _normalizza_testo((atto or {}).get("denominazione") or (atto or {}).get("tipo_atto") or "")
    if atto_name and atto_name in row_text:
        score += 12
        reasons.append("atto suggerito dalla guida")
    guida_name = _normalizza_testo(guida.get("denominazione"))
    if guida_name and any(part in row_tokens for part in guida_name.split() if len(part) >= 5):
        score += 4
        reasons.append("materia della guida")
    fasc_area = _normalizza_testo(fascicolo.get("area_pratica") or fascicolo.get("tipo") or "")
    if fasc_area and fasc_area in row_tokens:
        score += 3
        reasons.append("area del fascicolo")
    code = _normalizza_testo(guida.get("codice") or fascicolo.get("codice_oggetto_pst") or "")
    if code and code in row_text:
        score += 5
        reasons.append("codice pratica")
    hits = [token for token in tokens if token in row_tokens]
    if hits:
        score += min(10, len(hits) * 2)
        reasons.append("contesto pratica")
    if row.get("prefill_bindings") or row.get("required_prefill_fields"):
        score += 2
        reasons.append("precompilabile dal fascicolo")
    if row.get("link_compilatore_code"):
        score += 2
    return score, list(dict.fromkeys(reasons))


def _template_plan_record(row: dict[str, Any], score: int, reasons: list[str], fascicolo: dict[str, Any], guida: dict[str, Any]) -> dict[str, Any]:
    compiler_code = _text(row.get("link_compilatore_code") or row.get("codice"))
    query_params: dict[str, str] = {}
    fascicolo_id = _text(fascicolo.get("id"))
    guida_code = _text(guida.get("codice"))
    if fascicolo_id:
        query_params["id_fascicolo"] = fascicolo_id
    if guida_code:
        query_params["guida_pratica"] = guida_code
    query_params["origine"] = "guida_pratica"
    href = f"/template-atti/compila/{compiler_code}" if compiler_code else "/template-atti/catalogo"
    if query_params:
        href = f"{href}?{urlencode(query_params)}"
    return {
        "id": _text(row.get("codice")),
        "compilerCode": compiler_code,
        "title": _text(row.get("titolo") or row.get("name"), "Template atto"),
        "matter": _text(row.get("materia") or row.get("area")),
        "area": _text(row.get("area") or row.get("macro_area")),
        "channel": _text(row.get("canale_deposito") or row.get("portale_deposito")),
        "prefillStatus": "precompilabile" if row.get("prefill_bindings") else "da completare",
        "score": score,
        "reasons": reasons,
        "href": href,
        "editorHint": "Apre il compilatore con il fascicolo già selezionato e poi l'anteprima modificabile.",
    }


def build_document_plan_for_guida(guida: dict[str, Any] | None, fascicolo: dict[str, Any] | None) -> dict[str, Any]:
    guida = guida if isinstance(guida, dict) else {}
    fascicolo = fascicolo if isinstance(fascicolo, dict) else {}
    atto = guida.get("atto_principale") if isinstance(guida.get("atto_principale"), dict) else {}
    quick = guida.get("quick_help") if isinstance(guida.get("quick_help"), dict) else {}
    documento_suggerito = _text((atto or {}).get("denominazione") or quick.get("atto_da_redigere") or guida.get("denominazione"))
    try:
        from pct.template_catalog_service import build_template_catalog_items
    except Exception:
        return {
            "enabled": True,
            "documentoSuggerito": documento_suggerito,
            "template": {
                "status": "catalogo_non_disponibile",
                "autoLoad": False,
                "reason": "Catalogo template non disponibile nel runtime corrente.",
                "recommended": None,
                "alternatives": [],
            },
            "import": {"enabled": True, "formats": ["PDF", "Word"], "message": "Puoi importare un documento dello studio e collegarlo al passaggio della guida."},
        }
    tokens = _template_search_tokens(guida, fascicolo)
    specific_tokens = _specific_template_tokens(guida, fascicolo)
    candidates: list[tuple[int, list[str], dict[str, Any]]] = []
    for row in build_template_catalog_items():
        row_tokens = _template_row_tokens(row)
        if specific_tokens:
            specific_hits = [token for token in specific_tokens if token in row_tokens]
            if not specific_hits:
                continue
            primary_hits = [token for token in specific_hits if token in _template_row_primary_tokens(row)]
            if len(specific_hits) < 2 and not primary_hits:
                continue
        score, reasons = _score_template(row, guida, fascicolo, tokens)
        if score >= 6:
            candidates.append((score, reasons, row))
    candidates.sort(key=lambda item: (-item[0], _text(item[2].get("titolo")).casefold(), _text(item[2].get("codice"))))
    records = [
        _template_plan_record(row, score, reasons, fascicolo, guida)
        for score, reasons, row in candidates[:5]
    ]
    recommended = records[0] if records else None
    tied = len([item for item in records if recommended and item["score"] >= recommended["score"] - 2])
    auto_load = bool(recommended and tied == 1)
    status = "automatico" if auto_load else "scelta_assistita" if records else "non_collegato"
    reason = (
        "Template univoco filtrato su pratica, guida e atto suggerito."
        if auto_load
        else "Più template coerenti: mostra scelta assistita e motivata."
        if records
        else "Nessun template coerente trovato: l'avvocato può scegliere dal catalogo o importare un documento."
    )
    return {
        "enabled": True,
        "documentoSuggerito": documento_suggerito,
        "template": {
            "status": status,
            "autoLoad": auto_load,
            "reason": reason,
            "recommended": recommended,
            "alternatives": records[1:],
        },
        "import": {
            "enabled": True,
            "formats": ["PDF", "Word"],
            "message": "Puoi importare PDF o Word nell'anteprima: se editabile lo modifichi, altrimenti lo salvi come originale collegato.",
        },
    }


def build_react_guida_pratica_payload(*, codice: str, fascicolo: dict[str, Any] | None = None, service: GuidaPraticaService | None = None) -> dict[str, Any]:
    service = service or GuidaPraticaService()
    guida = service.get_guidance(codice, fascicolo=fascicolo or {})
    checklist = service.get_checklist(codice, {"fascicolo": fascicolo or {}})
    document_plan = build_document_plan_for_guida(guida, fascicolo or {})
    return {
        "ok": True,
        "source": "legal_knowledge_base_json_catalogo_xsd",
        "generatedAt": _now(),
        "guidaPraticaFacoltativa": True,
        "guidaPraticaDisponibile": True,
        "bloccaLavoro": False,
        "guida": guida,
        "checklist": checklist,
        "documentPlan": document_plan,
        "catalogoSize": service.catalog_size(),
    }


def _mark_suggested_code_payload(payload: dict[str, Any], match: dict[str, Any]) -> dict[str, Any]:
    message = "Guida pratica facoltativa suggerita dal contesto del fascicolo. Il fascicolo resta operativo; conferma una materia ufficiale solo se vuoi collegarla stabilmente."
    if isinstance(payload.get("guida"), dict):
        payload["guida"]["guida_pratica_suggerita"] = True
    checklist = payload.get("checklist")
    if isinstance(checklist, dict):
        checklist["guida_pratica_suggerita"] = True
        checklist["requires_code_confirmation"] = False
        checklist["blocca_lavoro"] = False
    payload["matchedFromFascicolo"] = match
    payload["message"] = message
    payload["guidaPraticaFacoltativa"] = True
    payload["guidaPraticaDisponibile"] = True
    payload["bloccaLavoro"] = False
    payload["source"] = "legal_knowledge_base_json_suggerimento_fascicolo"
    return payload


def build_react_guida_pratica_catalog_payload(*, query: str = "", coverage: str = "", limit: int = 500, service: GuidaPraticaService | None = None) -> dict[str, Any]:
    service = service or GuidaPraticaService()
    rows = service.list_guidance(query=query, coverage=coverage, limit=limit)
    counts: dict[str, int] = {}
    for row in rows:
        level = _text((row.get("coverage") or {}).get("level"), "sconosciuta") if isinstance(row.get("coverage"), dict) else "sconosciuta"
        counts[level] = counts.get(level, 0) + 1
    return {
        "ok": True,
        "source": "catalogo_xsd_e_kb",
        "generatedAt": _now(),
        "items": rows,
        "summary": {
            "total": len(rows),
            "catalogoSize": service.catalog_size(),
            "coverage": counts,
        },
    }


def build_react_fascicolo_guida_pratica_payload(*, get_fascicoli: Callable[[], Any], id_fasc: str, service: GuidaPraticaService | None = None) -> dict[str, Any]:
    service = service or GuidaPraticaService()
    fascicolo = resolve_fascicolo_for_guida(get_fascicoli, id_fasc)
    if not fascicolo:
        return {"ok": False, "generatedAt": _now(), "notFound": True, "message": "Fascicolo non trovato."}
    context = fascicolo_guida_context(fascicolo)
    codice = normalize_codice_materia(context.get("codice_oggetto_pst"))
    if not codice:
        match = service.suggest_guidance_from_fascicolo(context)
        if match:
            context["codice_oggetto_pst_suggerito"] = _text(match.get("codice"))
            context["codiceOggettoPstSuggerito"] = _text(match.get("codice"))
            payload = build_react_guida_pratica_payload(codice=_text(match.get("codice")), fascicolo=context, service=service)
            payload["fascicolo"] = context
            return _mark_suggested_code_payload(payload, match)
        return {
            "ok": True,
            "generatedAt": _now(),
            "fascicolo": context,
            "message": "Nessuna scheda pratica collegata al fascicolo. Puoi continuare a lavorare; se vuoi usare la guida, seleziona una materia nella scheda fascicolo.",
            "code": "guida_pratica_facoltativa_non_collegata",
            "source": "guida_pratica_facoltativa_non_collegata",
            "guidaPraticaFacoltativa": True,
            "guidaPraticaDisponibile": False,
            "bloccaLavoro": False,
            "documentPlan": build_document_plan_for_guida(None, context),
        }
    payload = build_react_guida_pratica_payload(codice=codice, fascicolo=context, service=service)
    payload["fascicolo"] = context
    return payload


def build_react_guida_pratica_checklist_payload(*, codice: str, dati: dict[str, Any], service: GuidaPraticaService | None = None) -> dict[str, Any]:
    service = service or GuidaPraticaService()
    checklist = service.get_checklist(codice, dati)
    return {"ok": True, "generatedAt": _now(), "checklist": checklist}


def guida_pratica_error_payload(error: Exception) -> dict[str, Any]:
    if isinstance(error, GuidaPraticaError):
        return {"ok": False, "code": "guida_pratica_error", "message": str(error), "generatedAt": _now()}
    return {"ok": False, "code": "guida_pratica_unavailable", "message": "Guida Pratica non disponibile.", "generatedAt": _now()}
