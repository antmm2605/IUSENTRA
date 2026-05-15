"""Dati operativi per le superfici Studio e Amministrazione.

Le pagine usano archivi e percorsi operativi esistenti: la pagina mostra
dati reali e invia le scritture ai comandi tracciati.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from pct.applicazioni_catalogo import catalogo_applicazioni
from pct.applicazioni_runtime import TOOL_PRESET_OVERRIDES, TOOL_SCHEMAS, resolve_runtime
from pct.strumenti_legali import GestioneStrumentiLegali


def _safe(label: str, loader: Callable[[], Any], fallback: Any) -> Any:
    try:
        return loader()
    except Exception:
        return fallback


def _text(value: Any, fallback: str = "") -> str:
    raw = str(value if value is not None else fallback).strip()
    return raw or fallback


def _enum(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _date_it(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    for sample in (raw[:19], raw[:10]):
        try:
            parsed = datetime.fromisoformat(sample)
            return parsed.strftime("%d/%m/%Y %H:%M") if "T" in sample else parsed.strftime("%d/%m/%Y")
        except ValueError:
            continue
    return raw


def _euro(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return "EUR " + f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    text = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {text}"
    return f"€ {text}"


def _record(
    record_id: Any,
    title: Any,
    subtitle: Any = "",
    *,
    badge: Any = "",
    href: str = "",
    meta: Any = "",
) -> dict[str, str]:
    return {
        "id": _text(record_id, "record"),
        "title": _text(title, "Elemento"),
        "subtitle": _text(subtitle),
        "badge": _text(badge),
        "href": href,
        "meta": _text(meta),
    }


_BLOCKED_VISIBLE_RECORD_TERMS = ("demo", "sample")


def _is_visible_record(record: dict[str, str]) -> bool:
    text = " ".join(
        _text(record.get(key, ""))
        for key in ("title", "subtitle", "badge", "meta")
    ).lower()
    return not any(term in text for term in _BLOCKED_VISIBLE_RECORD_TERMS)


def _metric(label: str, value: Any, note: str = "") -> dict[str, str]:
    return {"label": label, "value": _text(value), "note": _text(note)}


def _action(label: str, href: str, *, method: str = "GET", tone: str = "primary") -> dict[str, str]:
    return {"label": label, "href": href, "method": method, "tone": tone}


def _field(
    name: str,
    label: str,
    field_type: str = "text",
    *,
    required: bool = False,
    options: list[dict[str, str]] | None = None,
    value: Any = "",
    step: str = "",
    min_value: str = "",
    max_value: str = "",
) -> dict[str, Any]:
    return {
        "name": name,
        "label": label,
        "type": field_type,
        "required": required,
        "options": options or [],
        "value": value,
        "step": step,
        "min": min_value,
        "max": max_value,
    }


def _operation(
    operation_id: str,
    title: str,
    body: str,
    *,
    metrics: list[dict[str, str]] | None = None,
    records: list[dict[str, str]] | None = None,
    actions: list[dict[str, str]] | None = None,
    form: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    tool: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": operation_id,
        "title": title,
        "body": body,
        "metrics": metrics or [],
        "records": records or [],
        "actions": actions or [],
        "form": form,
        "warnings": warnings or [],
        "tool": tool,
    }


def _roles_options() -> list[dict[str, str]]:
    return [
        {"value": "AMMINISTRATORE", "label": "Amministratore"},
        {"value": "AVVOCATO", "label": "Avvocato"},
        {"value": "COLLABORATORE", "label": "Collaboratore"},
        {"value": "PRATICANTE", "label": "Praticante"},
        {"value": "SEGRETERIA", "label": "Segreteria"},
        {"value": "CONTABILE", "label": "Contabile"},
    ]


def _option(value: Any, label: Any | None = None) -> dict[str, str]:
    raw = _text(value)
    return {"value": raw, "label": _text(label, raw)}


def _cliente_options(clienti: list[Any]) -> list[dict[str, str]]:
    return [
        _option(getattr(cliente, "id", ""), getattr(cliente, "nome_completo", "") or getattr(cliente, "nome", ""))
        for cliente in clienti
        if getattr(cliente, "id", "")
    ][:120]


def _fascicolo_options(fascicoli: list[Any]) -> list[dict[str, str]]:
    return [
        _option(
            getattr(fascicolo, "id", ""),
            " - ".join(
                part
                for part in [
                    getattr(fascicolo, "numero_rg", ""),
                    getattr(fascicolo, "titolo", ""),
                    getattr(fascicolo, "tribunale", ""),
                ]
                if _text(part)
            ) or getattr(fascicolo, "titolo", "") or getattr(fascicolo, "id", ""),
        )
        for fascicolo in fascicoli
        if getattr(fascicolo, "id", "")
    ][:120]


def _studio_forense(config: dict[str, Any], get_config_studio: Callable[[], Any] | None = None) -> dict[str, str]:
    data = {
        "avvocato": _text(config.get("STUDIO_AVVOCATO") or config.get("PCT_STUDIO_AVVOCATO")),
        "numero_iscrizione_albo": _text(config.get("STUDIO_NUMERO_ISCRIZIONE_ALBO")),
        "ordine_avvocati": _text(config.get("STUDIO_ORDINE_AVVOCATI")),
    }
    if callable(get_config_studio):
        try:
            studio = getattr(getattr(get_config_studio(), "config", None), "studio", None)
            data["avvocato"] = _text(getattr(studio, "avvocato", ""), data["avvocato"])
            data["numero_iscrizione_albo"] = _text(
                getattr(studio, "numero_iscrizione_albo", ""),
                data["numero_iscrizione_albo"],
            )
            data["ordine_avvocati"] = _text(getattr(studio, "ordine_avvocati", ""), data["ordine_avvocati"])
        except Exception:
            pass
    return data


def _current_path(query: dict[str, Any] | None) -> str:
    return _text((query or {}).get("path"))


def _query_value(query: dict[str, Any] | None, key: str, fallback: str = "") -> str:
    value = (query or {}).get(key)
    if isinstance(value, list):
        value = value[0] if value else ""
    return _text(value, fallback)


def _slug(value: Any) -> str:
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFD", _text(value).lower())
    ascii_text = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"(^-+|-+$)", "", re.sub(r"[^a-z0-9]+", "-", ascii_text)) or "operazione"


def _strumenti_studio_context(
    config: dict[str, Any],
    get_config_studio: Callable[[], Any] | None = None,
) -> dict[str, str]:
    studio_forense = _studio_forense(config, get_config_studio)
    data = {
        "nome": _text(config.get("STUDIO_NOME"), "IUSENTRA"),
        "avvocato": studio_forense["avvocato"],
        "cf": _text(config.get("STUDIO_CF")),
        "piva": _text(config.get("STUDIO_PIVA")),
        "indirizzo": _text(config.get("STUDIO_INDIRIZZO")),
        "pec": _text(config.get("SMTP_FROM") or config.get("PEC_EMAIL")),
        "fax": _text(config.get("STUDIO_FAX")),
        "luogo": _text(config.get("STUDIO_LUOGO")),
    }
    if callable(get_config_studio):
        try:
            studio = getattr(getattr(get_config_studio(), "config", None), "studio", None)
            data["nome"] = _text(getattr(studio, "nome", ""), data["nome"])
            data["cf"] = _text(getattr(studio, "codice_fiscale", ""), data["cf"])
            data["piva"] = _text(getattr(studio, "partita_iva", ""), data["piva"])
            data["indirizzo"] = _text(getattr(studio, "indirizzo", ""), data["indirizzo"])
            data["pec"] = _text(getattr(studio, "pec", ""), data["pec"])
            data["luogo"] = _text(getattr(studio, "luogo", ""), data["luogo"])
        except Exception:
            pass
    return data


def _fascicoli_tutti(get_fascicoli: Callable[[], Any]) -> list[Any]:
    repo = get_fascicoli()
    try:
        return list(repo.tutti(archiviati=True))
    except TypeError:
        return list(repo.tutti())


def _tool_options_map(gestore: GestioneStrumentiLegali) -> dict[str, list[dict[str, str]]]:
    usura_options = [
        _option(row.get("category", ""), row.get("label") or row.get("category", ""))
        for row in gestore.norme.usura_categorie()
        if row.get("category")
    ]
    onorari = gestore.opzioni_onorari_forensi()
    return {
        "contributo_unificato": [
            _option(row.get("value", ""), row.get("label", ""))
            for row in gestore.opzioni_contributo_unificato()
        ],
        "usura": usura_options,
        "onorari_materie": list(onorari.get("materie", [])),
        "onorari_gradi": list(onorari.get("gradi", [])),
        "onorari_complessita": list(onorari.get("complessita", [])),
        "onorari_fasi": list(onorari.get("fasi", [])),
    }


def _tool_fields(
    schema: dict[str, Any],
    defaults: dict[str, Any],
    options_map: dict[str, list[dict[str, str]]],
) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for source_field in list(schema.get("fields") or []):
        field = dict(source_field)
        options_source = field.get("options")
        options = options_map.get(options_source, []) if isinstance(options_source, str) else list(options_source or [])
        field_type = _text(field.get("type"), "text")
        value = defaults.get(field.get("name", ""), [] if field_type == "multiselect" else "")
        if field_type == "multiselect" and not value:
            value = ["STUDIO", "INTRODUTTIVA", "ISTRUTTORIA", "DECISIONALE"]
        fields.append(
            _field(
                _text(field.get("name")),
                _text(field.get("label"), "Campo"),
                field_type,
                required=field.get("required") is True,
                options=[_option(row.get("value", ""), row.get("label", "")) for row in options],
                value=value,
                step=_text(field.get("step")),
                min_value=_text(field.get("min")),
                max_value=_text(field.get("max")),
            )
        )
    return fields


def _tool_catalog_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for entry in catalogo_applicazioni():
        runtime = resolve_runtime(entry)
        if runtime.get("kind") != "tool":
            continue
        entries.append({"entry": entry, "runtime": runtime})
    return entries


def _build_strumenti_forensi(
    config: dict[str, Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    *,
    get_config_studio: Callable[[], Any] | None = None,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gestore = GestioneStrumentiLegali(
        normative_db_path=config.get("NORMATIVE_TABLES_DB", "./intelligence/tabelle_normative.json")
    )
    clienti = _safe("clienti", lambda: list(get_clienti().tutti()), [])
    fascicoli = _safe("fascicoli", lambda: _fascicoli_tutti(get_fascicoli), [])
    clienti_map = {getattr(cliente, "id", ""): cliente for cliente in clienti if getattr(cliente, "id", "")}
    id_fascicolo = _query_value(query, "id_fascicolo")
    fascicolo_sel = None
    cliente_sel = None
    if id_fascicolo:
        try:
            fascicolo_sel = get_fascicoli().get(id_fascicolo)
            cliente_sel = clienti_map.get(getattr(fascicolo_sel, "id_cliente", ""))
        except Exception:
            fascicolo_sel = None
            cliente_sel = None

    defaults = gestore.build_form_state(
        gestore.build_prefill(
            fascicolo=fascicolo_sel,
            cliente=cliente_sel,
            studio=_strumenti_studio_context(config, get_config_studio),
        ),
        None,
    )
    selected_app_id = _query_value(query, "app")
    selected_tool_id = _query_value(query, "tool")
    catalog_entries = _tool_catalog_entries()
    entries_by_tool: dict[str, list[dict[str, Any]]] = {}
    selected_entry: dict[str, Any] | None = None
    for item in catalog_entries:
        tool_id = _text(item["runtime"].get("tool_id"))
        entries_by_tool.setdefault(tool_id, []).append(item)
        if item["entry"].get("id") == selected_app_id:
            selected_entry = item
            selected_tool_id = tool_id
    if selected_app_id:
        defaults.update(dict(TOOL_PRESET_OVERRIDES.get(selected_app_id, {})))

    all_records = [
        _record(
            item["entry"].get("id"),
            item["entry"].get("title"),
            item["entry"].get("summary") or item["runtime"].get("schema", {}).get("subtitle", ""),
            badge=item["entry"].get("section_title") or item["entry"].get("workspace_kind_label", ""),
            href=(
                "/strumenti-legali/"
                f"?app={item['entry'].get('id')}&tool={item['runtime'].get('tool_id')}#funzione-operativa"
            ),
            meta=item["entry"].get("workspace_kind_label", "Calcolo"),
        )
        for item in catalog_entries
    ]
    all_records = [record for record in all_records if _is_visible_record(record)]
    options_map = _tool_options_map(gestore)
    module_by_tool = {row["id"]: row for row in gestore.catalogo_moduli()}

    operations: list[dict[str, Any]] = [
        _operation(
            "suite-strumenti",
            "Suite strumenti",
            "Scegli una funzione: la pagina apre il modulo collegato e calcola in questa scheda.",
            metrics=[
                _metric("Funzioni catalogate", len(catalog_entries)),
                _metric("Calcolatori", len(module_by_tool)),
                _metric("Pratiche collegabili", len(fascicoli)),
            ],
            records=all_records,
            actions=[_action("Compensi forensi", "/compensi-forensi"), _action("Preventivo da calcolo", "/preventivi/wizard")],
        )
    ]

    ordered_tool_ids = [row["id"] for row in gestore.catalogo_moduli() if row["id"] in TOOL_SCHEMAS]
    for tool_id in ordered_tool_ids:
        schema = dict(TOOL_SCHEMAS[tool_id])
        tool_entries = entries_by_tool.get(tool_id, [])
        tool_records = [
            _record(
                item["entry"].get("id"),
                item["entry"].get("title"),
                item["entry"].get("summary") or schema.get("subtitle", ""),
                badge=item["entry"].get("section_title", ""),
                href=(
                    "/strumenti-legali/"
                    f"?app={item['entry'].get('id')}&tool={tool_id}#funzione-operativa"
                ),
                meta="Pronto",
            )
            for item in tool_entries
        ]
        entry_for_tool = selected_entry if selected_tool_id == tool_id and selected_entry else (tool_entries[0] if tool_entries else None)
        title = _text(
            entry_for_tool["entry"].get("title") if entry_for_tool else "",
            schema.get("title", module_by_tool[tool_id]["title"]),
        )
        subtitle = _text(schema.get("subtitle") or module_by_tool[tool_id].get("subtitle"), "Modulo operativo collegato ai dati inseriti.")
        form_fields = [
            _field("tool_id", "Strumento", "hidden", value=tool_id),
            _field("app_id", "Funzione", "hidden", value=_text(entry_for_tool["entry"].get("id")) if entry_for_tool else tool_id),
        ]
        if id_fascicolo:
            form_fields.append(_field("id_fascicolo", "Pratica", "hidden", value=id_fascicolo))
        form_fields.extend(_tool_fields(schema, defaults, options_map))
        operations.append(
            _operation(
                _slug(module_by_tool[tool_id]["title"]),
                title,
                subtitle,
                metrics=[_metric("Funzioni disponibili", len(tool_entries) or 1), _metric("Modulo", module_by_tool[tool_id]["categoria"])],
                records=tool_records,
                actions=[_action("Preventivo da risultato", "/preventivi/wizard", tone="secondary")],
                form={
                    "action": f"/api/v1/ui/strumenti-legali/{tool_id}",
                    "method": "POST",
                    "enctype": "multipart/form-data",
                    "submitLabel": _text(schema.get("submit_label"), "Calcola"),
                    "fields": form_fields,
                },
                warnings=[
                    "Verifica i dati prima di usare il risultato in atti o comunicazioni."
                ],
                tool={
                    "toolId": tool_id,
                    "appId": _text(entry_for_tool["entry"].get("id")) if entry_for_tool else tool_id,
                },
            )
        )

    return {
        "metrics": [
            _metric("Funzioni", len(catalog_entries), "catalogo operativo"),
            _metric("Calcolatori", len(module_by_tool), "moduli eseguibili"),
            _metric("Pratiche", len(fascicoli), "collegabili al calcolo"),
        ],
        "operations": operations,
    }


def _compenso_options() -> list[dict[str, str]]:
    return [
        _option("Compenso fisso"),
        _option("Compenso orario"),
        _option("Per fasi processuali (D.M. 55/2014)"),
        _option("Forfettario onnicomprensivo"),
        _option("Misto (fisso + quota sul risultato)"),
        _option("A liquidazione (parametri D.M. 55/2014)"),
    ]


def _procedimento_options() -> list[dict[str, str]]:
    return [
        _option("Civile - fase di cognizione"),
        _option("Civile - fase esecutiva"),
        _option("Penale"),
        _option("Amministrativo (TAR/CdS)"),
        _option("Stragiudiziale / Consulenza"),
        _option("Mediazione / Negoziazione assistita"),
        _option("Arbitrato"),
    ]


def _file_metric(path: Any) -> str:
    raw = _text(path)
    if not raw:
        return "non configurato"
    candidate = Path(raw)
    try:
        if not candidate.exists():
            return "non trovato"
        size = candidate.stat().st_size
        if size >= 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        if size >= 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size} B"
    except OSError:
        return "non leggibile"


def _build_utenti(get_utenti: Callable[[], Any]) -> dict[str, Any]:
    manager = get_utenti()
    utenti = _safe("utenti", lambda: manager.tutti(), [])
    stats = _safe("statistiche utenti", lambda: manager.statistiche(), {})
    records = [
        _record(
            getattr(user, "id", ""),
            getattr(user, "username", ""),
            getattr(user, "nome_completo", "") or getattr(user, "email", ""),
            badge=_enum(getattr(user, "ruolo", "")),
            href=f"/utenti/{getattr(user, 'id', '')}/modifica",
            meta="Attivo" if getattr(user, "attivo", False) else "Disabilitato",
        )
        for user in utenti[:25]
    ]
    role_counts = stats.get("per_ruolo", {}) if isinstance(stats, dict) else {}
    return {
        "metrics": [
            _metric("Utenti", stats.get("totale_utenti", len(utenti)) if isinstance(stats, dict) else len(utenti)),
            _metric("Attivi", stats.get("attivi", 0) if isinstance(stats, dict) else 0),
            _metric("Override", stats.get("con_override", 0) if isinstance(stats, dict) else 0),
        ],
        "operations": [
            _operation(
                "lista-utenti",
                "Lista utenti",
                "Archivio operatori dello studio con ruolo, stato e accesso.",
                records=records,
                metrics=[_metric(role, count) for role, count in sorted(role_counts.items())],
                actions=[_action("Aggiorna lista", "/utenti")],
            ),
            _operation(
                "nuovo-utente",
                "Nuovo utente",
                "Crea un operatore con il comando autorizzato.",
                form={
                    "action": "/utenti/nuovo",
                    "method": "POST",
                    "submitLabel": "Crea utente",
                    "fields": [
                        _field("username", "Username", required=True),
                        _field("password", "Password temporanea", "password", required=True),
                        _field("nome_completo", "Nome completo"),
                        _field("email", "Email", "email"),
                        _field("ruolo", "Ruolo", "select", required=True, options=_roles_options(), value="SEGRETERIA"),
                    ],
                },
                warnings=["La password temporanea verrà cambiata al primo accesso."],
            ),
            _operation(
                "profili-e-permessi",
                "Profili e permessi",
                "Matrice permessi e deroghe individuali collegati agli utenti.",
                records=[_record(role, role, f"{count} utenti", badge="Ruolo", href="/profili") for role, count in sorted(role_counts.items())],
                actions=[_action("Apri matrice ruoli", "/profili")],
            ),
        ],
    }


def _build_fatturazione(get_fatturazione: Callable[[], Any], get_clienti: Callable[[], Any]) -> dict[str, Any]:
    manager = get_fatturazione()
    anno = date.today().year
    parcelle = _safe("parcelle", lambda: manager.tutte(), [])
    stats = _safe("statistiche fatturazione", lambda: manager.statistiche(anno), {})
    clienti = {str(getattr(c, "id", "")): c for c in _safe("clienti", lambda: get_clienti().tutti(), [])}
    records = []
    for parcella in parcelle[:25]:
        cliente = clienti.get(str(getattr(parcella, "id_cliente", "")))
        records.append(_record(
            getattr(parcella, "id", ""),
            getattr(parcella, "numero", "Parcella"),
            getattr(cliente, "nome_completo", "") if cliente else "Cliente non collegato",
            badge=_enum(getattr(parcella, "stato", "")),
            href=f"/fatturazione/{getattr(parcella, 'id', '')}",
            meta=_euro(getattr(parcella, "totale", 0)),
        ))
    clienti_options = [
        {"value": str(getattr(cliente, "id", "")), "label": getattr(cliente, "nome_completo", "")}
        for cliente in clienti.values()
        if getattr(cliente, "id", "")
    ][:80]
    return {
        "metrics": [
            _metric("Fatturato anno", _euro(stats.get("totale_emesso", 0) if isinstance(stats, dict) else 0)),
            _metric("Incassato", _euro(stats.get("totale_pagato", 0) if isinstance(stats, dict) else 0)),
            _metric("Scadute", stats.get("scadute", 0) if isinstance(stats, dict) else 0),
        ],
        "operations": [
            _operation("elenco-parcelle", "Elenco parcelle", "Archivio economico con documenti, stati e importi reali.", records=records, actions=[_action("Esporta contabilità", "/export/fatturazione.csv")]),
            _operation(
                "nuova-parcella",
                "Nuova parcella",
                "Crea una parcella usando il percorso gia' controllato dello studio.",
                form={
                    "action": "/fatturazione/nuova",
                    "method": "POST",
                    "submitLabel": "Crea parcella",
                    "fields": [
                        _field("id_cliente", "Cliente", "select", required=True, options=clienti_options),
                        _field("voce_descr[]", "Descrizione voce", required=True),
                        _field("voce_qty[]", "Quantità", "number", required=True, value="1"),
                        _field("voce_prezzo[]", "Prezzo unitario", "number", required=True, value="0.00"),
                        _field("data_emissione", "Data emissione", "date", value=date.today().isoformat()),
                        _field("data_scadenza", "Data scadenza", "date"),
                        _field("note", "Note", "textarea"),
                    ],
                },
            ),
            _operation("incassi-e-pagamenti", "Incassi e pagamenti", "Canali, link pagamento e stato incassi collegati alle parcelle.", actions=[_action("Apri pagamenti", "/impostazioni?tab=pagamenti")]),
            _operation("esporta-contabilita", "Esporta contabilità", "Download CSV per controllo contabile.", actions=[_action("Scarica CSV", "/export/fatturazione.csv")]),
        ],
    }


def _build_preventivi(
    get_preventivi: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    config: dict[str, Any],
    *,
    query: dict[str, Any] | None = None,
    get_config_studio: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    manager = get_preventivi()
    preventivi = _safe("preventivi", lambda: manager.tutti_preventivi(), [])
    conferimenti = _safe("conferimenti", lambda: manager.tutti_conferimenti(), [])
    clienti = _safe("clienti", lambda: get_clienti().tutti(), [])
    fascicoli = _safe("fascicoli", lambda: get_fascicoli().tutti(), [])
    clienti_by_id = {str(getattr(cliente, "id", "")): cliente for cliente in clienti}
    studio = _studio_forense(config, get_config_studio)

    id_preventivo = _query_value(query, "id_preventivo")
    preventivo_pre = _safe("preventivo prefill", lambda: manager.get_preventivo(id_preventivo), None) if id_preventivo else None
    id_cliente_path = ""
    path = _current_path(query)
    marker = "/preventivi/conferimento/nuovo/"
    if marker in path:
        id_cliente_path = path.split(marker, 1)[1].split("/", 1)[0]
    cliente_default = (
        _text(getattr(preventivo_pre, "id_cliente", ""))
        or _query_value(query, "id_cliente")
        or id_cliente_path
    )
    fascicolo_default = _text(getattr(preventivo_pre, "id_fascicolo", "")) or _query_value(query, "id_fascicolo")
    oggetto_default = _text(getattr(preventivo_pre, "oggetto", ""))
    compenso_default = _text(getattr(preventivo_pre, "totale", "") or getattr(preventivo_pre, "totale_preventivo", ""))

    preventivo_options = [
        _option(
            getattr(item, "id", ""),
            f"{getattr(item, 'numero', 'Preventivo')} - {_text(getattr(clienti_by_id.get(str(getattr(item, 'id_cliente', ''))), 'nome_completo', '')) or 'Cliente'}",
        )
        for item in preventivi
        if getattr(item, "id", "")
    ][:120]

    preventivi_records = [
        _record(
            getattr(item, "id", ""),
            getattr(item, "numero", "Preventivo"),
            getattr(clienti_by_id.get(str(getattr(item, "id_cliente", ""))), "nome_completo", "Cliente non collegato"),
            badge=_enum(getattr(item, "stato", "")),
            href=f"/preventivi/p/{getattr(item, 'id', '')}",
            meta=_euro(getattr(item, "totale", 0)),
        )
        for item in preventivi[:30]
    ]
    conferimenti_records = [
        _record(
            getattr(item, "id", ""),
            getattr(item, "numero", "Conferimento"),
            getattr(clienti_by_id.get(str(getattr(item, "id_cliente", ""))), "nome_completo", "Cliente non collegato"),
            badge=_enum(getattr(item, "stato", "")),
            href=f"/preventivi/conferimento/{getattr(item, 'id', '')}",
            meta=_date_it(getattr(item, "data_incarico", "")),
        )
        for item in conferimenti[:30]
    ]
    scaduti = sum(1 for item in preventivi if _enum(getattr(item, "stato", "")) == "SCADUTO")
    accettati_senza_incarico = 0
    incarichi_by_preventivo = {str(getattr(item, "id_preventivo", "")) for item in conferimenti if getattr(item, "id_preventivo", "")}
    for item in preventivi:
        if _enum(getattr(item, "stato", "")) == "ACCETTATO" and str(getattr(item, "id", "")) not in incarichi_by_preventivo:
            accettati_senza_incarico += 1

    from_page = _query_value(query, "from_page", "react")
    today = date.today()
    in_30_days = today + timedelta(days=30)
    return {
        "metrics": [
            _metric("Preventivi", len(preventivi)),
            _metric("Conferimenti", len(conferimenti)),
            _metric("Da incarico", accettati_senza_incarico, "preventivi accettati senza conferimento"),
            _metric("Scaduti", scaduti),
        ],
        "operations": [
            _operation(
                "archivio-preventivi",
                "Archivio preventivi",
                "Preventivi e conferimenti reali con stato, cliente, importo e azioni operative.",
                records=preventivi_records,
                metrics=[_metric("Preventivi", len(preventivi)), _metric("Conferimenti", len(conferimenti))],
                actions=[_action("Aggiorna archivio", "/preventivi"), _action("Nuovo preventivo", "/preventivi/nuovo")],
            ),
            _operation(
                "nuovo-preventivo",
                "Nuovo preventivo",
                "Crea una proposta economica usando il percorso gia' controllato dello studio.",
                form={
                    "action": "/preventivi/nuovo",
                    "method": "POST",
                    "submitLabel": "Crea preventivo",
                    "fields": [
                        _field("from_page", "Origine", "hidden", value=from_page),
                        _field("id_cliente", "Cliente", "select", required=True, options=_cliente_options(clienti), value=cliente_default),
                        _field("id_fascicolo", "Fascicolo", "select", options=_fascicolo_options(fascicoli), value=fascicolo_default),
                        _field("oggetto", "Oggetto incarico", required=True, value=oggetto_default),
                        _field("data_emissione", "Data emissione", "date", value=today.isoformat()),
                        _field("data_scadenza", "Data scadenza", "date", value=in_30_days.isoformat()),
                        _field("tipo_compenso", "Tipo compenso", "select", options=_compenso_options(), value="Compenso fisso"),
                        _field("tipo_procedimento", "Tipo procedimento", "select", options=_procedimento_options(), value="Civile - fase di cognizione"),
                        _field("valore_controversia", "Valore controversia", "number", value="0"),
                        _field("complessita", "Complessità e note di stima", "textarea"),
                        _field("voce_descr[]", "Voce prestazione", required=True, value="Compenso professionale"),
                        _field("voce_tipo[]", "Tipo voce", "select", options=[_option("ONORARIO"), _option("ANTICIPAZIONE"), _option("SPESE")], value="ONORARIO"),
                        _field("voce_importo[]", "Importo voce", "number", required=True, value="0.00"),
                        _field("applica_cassa", "Applica Cassa Forense", "checkbox", value="1"),
                        _field("applica_iva", "Applica IVA", "checkbox", value="1"),
                        _field("anticipazioni_art15", "Anticipazioni art. 15", "number", value="0.00"),
                        _field("note", "Note", "textarea"),
                    ],
                },
                warnings=["Il calcolo finale viene eseguito dalla funzione gia' controllata dello studio."],
            ),
            _operation(
                "conferimento-incarico",
                "Conferimento incarico",
                "Predisponi l'incarico con dati studio precompilati da Impostazioni Studio e collegamento al preventivo.",
                records=conferimenti_records,
                form={
                    "action": "/preventivi/conferimento/nuovo",
                    "method": "POST",
                    "submitLabel": "Crea conferimento",
                    "fields": [
                        _field("from_page", "Origine", "hidden", value=from_page or "preventivo"),
                        _field("id_cliente", "Cliente", "select", required=True, options=_cliente_options(clienti), value=cliente_default),
                        _field("id_fascicolo", "Fascicolo", "select", options=_fascicolo_options(fascicoli), value=fascicolo_default),
                        _field("id_preventivo", "Preventivo collegato", "select", options=preventivo_options, value=id_preventivo),
                        _field("oggetto", "Oggetto incarico", required=True, value=oggetto_default),
                        _field("avvocato_referente", "Avvocato referente", required=True, value=studio["avvocato"]),
                        _field("numero_iscrizione_albo", "N. iscrizione Albo", value=studio["numero_iscrizione_albo"]),
                        _field("ordine_avvocati", "Ordine degli Avvocati", value=studio["ordine_avvocati"]),
                        _field("data_incarico", "Data incarico", "date", value=today.isoformat()),
                        _field("tipo_compenso", "Tipo compenso", "select", options=_compenso_options(), value=_text(getattr(preventivo_pre, "tipo_compenso", ""), "Compenso fisso")),
                        _field("tipo_procedimento", "Tipo procedimento", "select", options=_procedimento_options(), value=_text(getattr(preventivo_pre, "tipo_procedimento", ""), "Civile - fase di cognizione")),
                        _field("compenso_pattuito", "Compenso pattuito", "number", value=compenso_default or "0.00"),
                        _field("informativa_art13_resa", "Informativa privacy resa", "checkbox", value="1"),
                        _field("clausola_adr_resa", "Clausola ADR resa", "checkbox", value="1"),
                        _field("apri_fascicolo_guidato", "Apri fascicolo guidato dopo il salvataggio", "checkbox", value="0"),
                        _field("note", "Note incarico", "textarea", value=_text(getattr(preventivo_pre, "note", ""))),
                    ],
                },
                warnings=[
                    "Il conferimento resta bozza operativa: l'avvocato verifica e firma prima dell'uso.",
                    "N. iscrizione Albo e Ordine vengono letti da Impostazioni Studio quando disponibili.",
                ],
            ),
            _operation(
                "percorso-compensi",
                "Percorso compensi",
                "Calcolo guidato compensi forensi collegato a cliente, fascicolo e conferimento.",
                actions=[_action("Apri percorso", "/preventivi/wizard"), _action("Compensi Forensi", "/compensi-forensi")],
            ),
        ],
    }


def _build_timesheet(
    get_timesheet: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
) -> dict[str, Any]:
    manager = get_timesheet()
    entries = _safe("timesheet", lambda: manager.tutte(), [])
    stats = _safe("statistiche timesheet", lambda: manager.statistiche(entries), {})
    clienti = _safe("clienti", lambda: get_clienti().tutti(), [])
    fascicoli = _safe("fascicoli", lambda: get_fascicoli().tutti(), [])
    clienti_by_id = {str(getattr(cliente, "id", "")): cliente for cliente in clienti}
    fascicoli_by_id = {str(getattr(fascicolo, "id", "")): fascicolo for fascicolo in fascicoli}
    records = [
        _record(
            getattr(item, "id", ""),
            getattr(item, "descrizione", "Voce timesheet"),
            " - ".join(
                part
                for part in [
                    getattr(clienti_by_id.get(str(getattr(item, "id_cliente", ""))), "nome_completo", ""),
                    getattr(fascicoli_by_id.get(str(getattr(item, "id_fascicolo", ""))), "numero_rg", ""),
                ]
                if _text(part)
            ) or "Voce non collegata",
            badge=_enum(getattr(item, "stato", "")),
            href="/timesheet",
            meta=f"{getattr(item, 'minuti', 0)} min · {_euro(getattr(item, 'valore_totale', 0))}",
        )
        for item in entries[:30]
    ]
    return {
        "metrics": [
            _metric("Ore", str(stats.get("totale_ore", 0) if isinstance(stats, dict) else 0)),
            _metric("Valore", _euro(stats.get("valore_totale", 0) if isinstance(stats, dict) else 0)),
            _metric("Aperte", stats.get("aperte", 0) if isinstance(stats, dict) else 0),
            _metric("Validate", stats.get("validate", 0) if isinstance(stats, dict) else 0),
        ],
        "operations": [
            _operation(
                "cruscotto-tempi",
                "Cruscotto tempi",
                "Registro reale delle lavorazioni per cliente, fascicolo, stato e valore economico.",
                records=records,
                actions=[_action("Filtra registro", "/timesheet")],
            ),
            _operation(
                "nuova-attivita",
                "Nuova attività",
                "Registra una voce tempo usando il percorso gia' controllato dello studio.",
                form={
                    "action": "/timesheet/nuovo",
                    "method": "POST",
                    "submitLabel": "Registra tempo",
                    "fields": [
                        _field("from_page", "Origine", "hidden", value="timesheet"),
                        _field("descrizione", "Descrizione", "textarea", required=True),
                        _field("data_attivita", "Data attività", "date", value=date.today().isoformat()),
                        _field("minuti", "Minuti", "number", required=True, value="30"),
                        _field("id_cliente", "Cliente", "select", options=_cliente_options(clienti)),
                        _field("id_fascicolo", "Fascicolo", "select", options=_fascicolo_options(fascicoli)),
                        _field("valore_unitario", "Valore orario", "number", value="80"),
                        _field("fatturabile", "Fatturabile", "select", options=[_option("1", "Fatturabile"), _option("0", "Non fatturabile")], value="1"),
                        _field("note", "Note operative"),
                    ],
                },
            ),
            _operation(
                "genera-parcella",
                "Genera parcella",
                "Trasforma le voci validate in parcella usando il flusso economico già presente.",
                actions=[_action("Apri parcelle", "/fatturazione/nuova"), _action("Apri registro tempi", "/timesheet")],
                records=[record for record in records if record["badge"] == "VALIDATO"],
            ),
            _operation(
                "produttivita",
                "Produttività",
                "Leggi gli indicatori operativi collegati al lavoro registrato.",
                actions=[_action("Vedi statistiche", "/statistiche/?view=produttivita")],
            ),
        ],
    }


def _build_audit(get_utenti: Callable[[], Any]) -> dict[str, Any]:
    manager = get_utenti()
    events = _safe("audit", lambda: manager.audit_log(limit=50), [])
    records = [
        _record(
            getattr(event, "id", ""),
            getattr(event, "azione", ""),
            getattr(event, "username", "") or getattr(event, "risorsa_tipo", ""),
            badge=getattr(event, "esito", ""),
            href="/audit",
            meta=_date_it(getattr(event, "timestamp", "")),
        )
        for event in events[:30]
    ]
    return {
        "metrics": [_metric("Eventi", len(events)), _metric("Ultimo controllo", _date_it(getattr(events[0], "timestamp", "")) if events else "nessuno")],
        "operations": [
            _operation("registro-utenti", "Registro utenti", "Registro reale degli eventi applicativi e di sicurezza.", records=records, actions=[_action("Esporta CSV", "/audit/esporta.csv")]),
            _operation("esporta-registro", "Esporta registro", "Scarica il registro in formato CSV.", actions=[_action("Scarica CSV", "/audit/esporta.csv")]),
            _operation("osservabilita", "Osservabilità", "Superficie amministrativa per log e stato servizio.", actions=[_action("Apri osservabilità", "/admin/osservabilita")]),
        ],
    }


def _build_database(config: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "CLIENTI_DB",
        "FASCICOLI_DB",
        "AGENDA_DB",
        "SCADENZIARIO_DB",
        "EMAIL_CASELLA_DB",
        "MESSAGGI_DB",
        "UTENTI_DB",
    ]
    records = [
        _record(key, key, _text(config.get(key, "")), badge=_file_metric(config.get(key, "")), href="/admin/database")
        for key in keys
    ]
    return {
        "metrics": [_metric("Archivi", len(keys)), _metric("Cartella dati", _text(config.get("DATA_ROOT", "")) or _text(config.get("PCT_DATA_ROOT", "")) or "non indicata")],
        "operations": [
            _operation("stato-database", "Stato database", "Verifica archivi, dimensioni e percorsi governati.", records=records, actions=[_action("Apri backup", "/impostazioni?tab=backup"), _action("Registro attività", "/registro-attivita")]),
            _operation("backup", "Backup", "Controlla copie e ripristino prima delle operazioni delicate.", actions=[_action("Apri backup", "/impostazioni?tab=backup")]),
            _operation("registro-attivita", "Registro attività", "Registro collegato a dati e migrazioni.", actions=[_action("Apri registro", "/registro-attivita")]),
        ],
    }


def _build_gdpr(get_trattamenti: Callable[[], Any]) -> dict[str, Any]:
    trattamenti = _safe("trattamenti", lambda: get_trattamenti().tutti(), [])
    records = [
        _record(getattr(item, "id", ""), getattr(item, "nome", ""), getattr(item, "finalita", ""), badge=getattr(item, "base_giuridica", ""), href="/privacy/registro", meta="Attivo" if getattr(item, "attivo", False) else "Disattivo")
        for item in trattamenti[:30]
    ]
    return {
        "metrics": [_metric("Trattamenti", len(trattamenti)), _metric("Attivi", sum(1 for item in trattamenti if getattr(item, "attivo", False)))],
        "operations": [
            _operation("registro-trattamenti", "Registro trattamenti", "Registro privacy e trattamenti gestiti.", records=records, actions=[_action("Apri registro", "/privacy/registro")]),
            _operation(
                "nuovo-trattamento",
                "Nuovo trattamento",
                "Registra finalità, base giuridica, dati e misure.",
                form={
                    "action": "/privacy/registro/nuovo",
                    "method": "POST",
                    "submitLabel": "Salva trattamento",
                    "fields": [
                        _field("nome", "Nome trattamento", required=True),
                        _field("finalita", "Finalità", "textarea", required=True),
                        _field("categoria_dati", "Categoria dati"),
                        _field("base_giuridica", "Base giuridica"),
                        _field("soggetti_interessati", "Soggetti interessati"),
                        _field("destinatari", "Destinatari"),
                        _field("termine_conservazione", "Termine conservazione"),
                        _field("misure_sicurezza", "Misure sicurezza", "textarea"),
                    ],
                },
            ),
            _operation("registro-privacy", "Registro privacy", "Esporta e verifica attività collegate ai dati personali.", actions=[_action("Esporta registro", "/audit/esporta.csv")]),
        ],
    }


def _build_impostazioni(config: dict[str, Any]) -> dict[str, Any]:
    safe_rows = [
        _record("studio", "Studio", _text(config.get("STUDIO_NOME", "IUSENTRA")), badge="Dati", href="/impostazioni-studio#dati-studio"),
        _record("pec", "PEC", _text(config.get("PEC_HOST", "")) or _text(config.get("IMAP_HOST", "")) or "configurazione locale", badge="Canale", href="/impostazioni-studio#pec-e-smtp"),
        _record("smtp", "SMTP", _text(config.get("SMTP_HOST", "")) or "configurazione locale", badge="Invio", href="/impostazioni?tab=smtp"),
        _record("signer", "Local Signer", "http://127.0.0.1:27272", badge="Locale", href="/impostazioni-studio#firma-digitale"),
        _record("scheduler", "Scheduler", "backup, calendari e job pianificati", badge="Automazioni", href="/impostazioni-studio#scheduler"),
    ]
    return {
        "metrics": [_metric("Sezioni", 11), _metric("Firma locale", "Presente"), _metric("Password protette", "Si")],
        "operations": [
            _operation("dati-studio", "Dati studio", "Dati anagrafici e fiscali usati nei documenti.", records=safe_rows[:1]),
            _operation("pec-e-smtp", "PEC e SMTP", "Verifica canali senza esporre password nella UI.", records=safe_rows[1:3], actions=[_action("Test PEC/SMTP", "/impostazioni/test/pec-smtp", method="POST")]),
            _operation("firma-digitale", "Firma digitale", "Il dispositivo di firma si verifica dal browser tramite Local Signer sul PC dell'avvocato.", records=safe_rows[3:4], actions=[_action("Scarica Local Signer Windows", "/polisWeb/local-signer/setup/windows-exe")]),
            _operation("assistente-locale", "Assistente locale", "Assistente sul PC dello studio e aggiornamento documenti.", actions=[_action("Stato assistente", "/api/local-ai/status")]),
            _operation("whatsapp", "WhatsApp", "Canale, numeri e promemoria cliente.", actions=[_action("Apri WhatsApp", "/impostazioni?tab=whatsapp")]),
            _operation("scheduler", "Scheduler", "Automazioni, backup e sincronizzazione calendario.", records=safe_rows[4:]),
        ],
    }


_GENERIC_OPERATION_CATALOG: dict[str, list[tuple[str, str, str, list[tuple[str, str, str]]]]] = {
    "preventivi": [
        ("archivio-preventivi", "Archivio preventivi", "Apre la lista operativa di preventivi e conferimenti.", [("Apri archivio", "/preventivi", "GET")]),
        ("nuovo-preventivo", "Nuovo preventivo", "Invia al form operativo di creazione preventivo.", [("Crea preventivo", "/preventivi/nuovo", "GET")]),
        ("conferimento-incarico", "Conferimento incarico", "Predispone il conferimento partendo dal flusso controllato.", [("Crea incarico", "/preventivi/conferimento/nuovo", "GET")]),
        ("percorso-compensi", "Percorso compensi", "Apre il calcolo guidato per compensi e preventivo.", [("Apri percorso", "/preventivi/wizard", "GET")]),
    ],
    "compensi-forensi": [
        ("tariffario", "Tariffario", "Apre parametri forensi e calcoli DM 55.", [("Apri tariffario", "/tariffario", "GET")]),
        ("percorso-preventivo", "Percorso preventivo", "Trasforma il calcolo in preventivo operativo.", [("Genera preventivo", "/preventivi/wizard", "GET")]),
        ("strumenti-forensi", "Strumenti Forensi", "Apre la suite di calcolo forense.", [("Apri strumenti", "/strumenti-legali", "GET")]),
    ],
    "documenti": [
        ("documenti-fascicolo", "Fascicoli e documenti", "Apre i fascicoli con documenti, firme, upload e controlli collegati.", [("Apri fascicoli", "/fascicoli", "GET")]),
        ("catalogo-atti", "Catalogo atti", "Apre il catalogo modelli e le schede operative per la redazione.", [("Apri catalogo", "/template-atti/catalogo", "GET")]),
        ("redazione-atti", "Redazione atti", "Porta alla pagina di redazione e produzione atti dello studio.", [("Apri redazione", "/redazione-atti", "GET")]),
        ("ricerca-documenti", "Ricerca documenti", "Cerca documenti, comunicazioni e riferimenti collegati ai fascicoli.", [("Cerca documenti", "/global-search?tipo=documenti", "GET")]),
    ],
    "redazione-atti": [
        ("catalogo-atti", "Catalogo atti", "Apre catalogo, filtri e modelli dello studio.", [("Apri catalogo", "/template-atti/catalogo", "GET")]),
        ("nuovo-modello", "Nuovo modello", "Apre il form di creazione modello di studio.", [("Nuovo modello", "/template-atti/nuovo", "GET")]),
        ("checklist-deposito", "Checklist deposito", "Apre controlli atti e allegati prima del deposito.", [("Apri checklist", "/deposito/checklist", "GET")]),
        ("fascicoli", "Fascicoli", "Seleziona pratica, parti e documenti per la redazione.", [("Apri fascicoli", "/fascicoli", "GET")]),
    ],
    "pst-acquisizione": [
        ("acquisizione-pst", "Acquisizione PST", "Apre il percorso guidato per import autorizzato da PST.", [("Apri acquisizione", "/portali/pst/acquisizione", "GET")]),
        ("checklist-import-pst", "Checklist import PST", "Porta ai prerequisiti operativi del flusso PST.", [("Verifica flusso", "/portali/pst/acquisizione#checklist-operativa", "GET")]),
        ("fascicoli", "Fascicoli", "Controlla o crea la pratica locale prima dell'import.", [("Apri fascicoli", "/fascicoli", "GET")]),
        ("centro-telematico", "Centro telematico", "Rientra nel quadro unico dei servizi telematici.", [("Apri centro", "/telematico", "GET")]),
    ],
    "statistiche": [
        ("cruscotto-grafici", "Cruscotto grafici", "Apre indicatori, grafici e riepiloghi direzionali.", [("Apri cruscotto", "/statistiche", "GET")]),
        ("produttivita", "Produttività", "Filtra gli indicatori sul lavoro dello studio.", [("Vedi analisi", "/statistiche/?view=produttivita", "GET")]),
        ("depositi-trend", "Depositi trend", "Mostra andamento dei canali telematici.", [("Trend depositi", "/statistiche/?view=depositi", "GET")]),
    ],
    "ricerca-legale": [
        ("cruscotto-ricerca", "Cruscotto ricerca", "Apre monitor normativo e Ricerca legale.", [("Apri ricerca", "/legal-intelligence", "GET")]),
        ("news-legali", "News legali", "Consulta aggiornamenti e filtri per materia.", [("Apri news", "/legal-intelligence/news", "GET")]),
        ("registro-mediazione", "Registro mediazione", "Apre dati e aggiornamenti sulla mediazione.", [("Apri registro", "/legal-intelligence/mediazione", "GET")]),
    ],
    "giurisprudenza": [
        ("ricerca-sentenze", "Ricerca sentenze", "Apre archivio giurisprudenza e filtri.", [("Apri archivio", "/giurisprudenza", "GET")]),
        ("nuova-scheda", "Nuova scheda", "Registra manualmente una pronuncia.", [("Nuova scheda", "/giurisprudenza/nuova", "GET")]),
        ("importa-materiale", "Importa materiale", "Collega materiale e fonti all'archivio interno.", [("Importa", "/giurisprudenza", "GET")]),
    ],
    "strumenti-forensi": [
        ("suite-strumenti", "Suite strumenti", "Apre la suite degli strumenti forensi.", [("Apri suite", "/strumenti-legali", "GET")]),
        ("onorari-forensi", "Onorari forensi", "Apre il calcolo compensi forensi.", [("Calcola onorari", "/strumenti-legali/?tool=onorari_forensi", "GET")]),
        ("contributo-unificato", "Contributo unificato", "Apre il calcolo del contributo unificato.", [("Calcola CU", "/strumenti-legali/?tool=contributo_unificato", "GET")]),
        ("interessi-legali-e-mora", "Interessi legali e mora", "Calcola interessi per capitale, periodo e tasso applicabile.", [("Calcola interessi", "/strumenti-legali/?tool=interessi", "GET")]),
        ("rivalutazione-istat", "Rivalutazione ISTAT", "Aggiorna importi e indici per conteggi documentabili.", [("Rivaluta importo", "/strumenti-legali/?tool=rivalutazione_istat", "GET")]),
        ("verifica-usura", "Verifica usura", "Controlla soglie e dati del finanziamento prima del deposito in fascicolo.", [("Verifica usura", "/strumenti-legali/?tool=usura", "GET")]),
        ("piano-ammortamento", "Piano ammortamento", "Prepara rate, interessi e residuo per mutui e finanziamenti.", [("Crea piano", "/strumenti-legali/?tool=piano_ammortamento", "GET")]),
        ("danno-biologico", "Danno biologico", "Stima il danno con eta, invalidita e personalizzazione.", [("Calcola danno", "/strumenti-legali/?tool=danno_biologico", "GET")]),
        ("prescrizione-reati", "Prescrizione reati", "Valuta termini e sospensioni con una scheda riepilogativa.", [("Calcola termine", "/strumenti-legali/?tool=prescrizione_penale", "GET")]),
        ("successione-legittima", "Successione legittima", "Ripartisce quote ereditarie in base ai soggetti indicati.", [("Calcola quote", "/strumenti-legali/?tool=successione_legittima", "GET")]),
        ("cedolare-secca", "Cedolare secca", "Confronta canoni e imposta dovuta per locazioni.", [("Calcola imposta", "/strumenti-legali/?tool=cedolare_secca", "GET")]),
        ("trattamento-di-fine-rapporto", "Trattamento di fine rapporto", "Calcola quote, rivalutazione e riepilogo del rapporto.", [("Calcola TFR", "/strumenti-legali/?tool=tfr", "GET")]),
        ("compenso-ctu", "Compenso CTU", "Predispone compenso e spese per consulenze tecniche.", [("Calcola CTU", "/strumenti-legali/?tool=ctu", "GET")]),
        ("mediazione", "Mediazione", "Apre registro e riferimenti utili per costi e organismi.", [("Apri mediazione", "/legal-intelligence/mediazione", "GET")]),
        ("preventivo-da-calcolo", "Preventivo da calcolo", "Porta il risultato nel percorso guidato per preventivi e incarichi.", [("Crea preventivo", "/preventivi/wizard", "GET")]),
    ],
    "timesheet": [
        ("cruscotto-tempi", "Cruscotto tempi", "Apre riepilogo e filtri del timesheet.", [("Apri timesheet", "/timesheet", "GET")]),
        ("nuova-attivita", "Nuova attività", "Collega una voce tempo ad agenda, cliente o fascicolo.", [("Aggancia agenda", "/agenda", "GET")]),
        ("genera-parcella", "Genera parcella", "Porta alla creazione parcella dalle voci validate.", [("Crea parcella", "/fatturazione/nuova", "GET")]),
        ("produttivita", "Produttività", "Apre gli indicatori di produttività.", [("Vedi indicatori", "/statistiche/?view=produttivita", "GET")]),
    ],
    "cartelle-condivise": [
        ("cartelle-condivise", "Cartelle condivise", "Apre elenco accessi e cartelle cliente.", [("Apri cartelle", "/cartelle-condivise", "GET")]),
        ("clienti", "Clienti", "Seleziona cliente e cartella operativa.", [("Apri clienti", "/clienti", "GET")]),
        ("registro-attivita", "Registro attività", "Apre registro di condivisioni e accessi.", [("Apri registro", "/audit", "GET")]),
    ],
    "strumenti-operativi": [
        ("timesheet", "Timesheet", "Registra attività e valorizza lavoro fatturabile.", [("Apri timesheet", "/timesheet", "GET")]),
        ("export-dati", "Export dati", "Scarica dati economici per controlli.", [("Esporta", "/export/fatturazione.csv", "GET")]),
        ("condivisioni", "Condivisioni", "Gestisce cartelle condivise e accessi documentali.", [("Apri condivisioni", "/cartelle-condivise", "GET")]),
        ("regia-operativa", "Regia operativa", "Rientra nel quadro operativo dello studio.", [("Apri regia", "/workspace-intelligente", "GET")]),
        ("agenda", "Agenda", "Apre appuntamenti, udienze e calendario dello studio.", [("Apri agenda", "/agenda", "GET")]),
        ("nuovo-appuntamento", "Nuovo appuntamento", "Inserisce un impegno collegato a cliente o fascicolo.", [("Crea appuntamento", "/agenda/nuovo", "GET")]),
        ("ricerca-studio", "Ricerca studio", "Trova rapidamente fascicoli, clienti, scadenze, comunicazioni e documenti.", [("Cerca", "/global-search", "GET")]),
        ("scadenziario", "Scadenziario", "Controlla termini, stati e prossime azioni da completare.", [("Apri scadenze", "/scadenziario", "GET")]),
        ("messaggi-clienti", "Messaggi clienti", "Gestisce conversazioni, SMS e WhatsApp collegati allo studio.", [("Apri messaggi", "/messaggi", "GET")]),
        ("posta-ordinaria", "Posta ordinaria", "Apre email inviate e ricevute dal canale ordinario dello studio.", [("Apri posta", "/email-ordinaria/", "GET")]),
        ("pec", "PEC", "Controlla casella, allegati e messaggi rilevanti per le pratiche.", [("Apri PEC", "/email/", "GET")]),
        ("database", "Database", "Verifica archivi, integrita e manutenzione dei dati dello studio.", [("Apri database", "/admin/database", "GET")]),
        ("backup", "Backup", "Controlla copie, verifica e pianificazione nella scheda impostazioni.", [("Apri backup", "/impostazioni?tab=backup", "GET")]),
        ("calendari", "Calendari", "Gestisce link riservati e sincronizzazione agenda.", [("Apri calendari", "/impostazioni/calendario", "GET")]),
        ("contatti-sito", "Contatti sito", "Apre richieste e prenotazioni arrivate dal sito dello studio.", [("Apri contatti", "/sito-studio/contatti", "GET")]),
        ("registro-attivita", "Registro attivita", "Consulta eventi importanti e controlli amministrativi.", [("Apri registro", "/registro-attivita", "GET")]),
    ],
    "sito-studio": [
        ("cruscotto-sito", "Cruscotto sito", "Apre controllo contenuti e pubblicazione del sito.", [("Apri cruscotto", "/sito-studio", "GET")]),
        ("editor-sito", "Editor sito", "Apre la modifica visuale del sito.", [("Apri editor", "/sito-studio/builder", "GET")]),
        ("richieste-contatto", "Richieste contatto", "Apre lead e messaggi arrivati dal sito.", [("Apri contatti", "/sito-studio/contatti", "GET")]),
    ],
    "notifiche-whatsapp": [
        ("centro-notifiche", "Notifiche", "Apre messaggi e promemoria cliente.", [("Apri notifiche", "/impostazioni?tab=notifiche", "GET")]),
        ("configura-whatsapp", "Configura WhatsApp", "Apre le impostazioni del canale.", [("Apri configurazione", "/impostazioni?tab=whatsapp", "GET")]),
        ("messaggi-clienti", "Messaggi clienti", "Apre conversazioni e nuovo invio.", [("Apri messaggi", "/messaggi", "GET")]),
    ],
    "incassi-pagamenti": [
        ("impostazioni-pagamenti", "Impostazioni pagamenti", "Apre configurazione canali e preferenze.", [("Apri impostazioni", "/impostazioni?tab=pagamenti", "GET")]),
        ("parcelle-aperte", "Parcelle aperte", "Apre le parcelle da incassare.", [("Apri parcelle", "/fatturazione", "GET")]),
        ("statistiche-economiche", "Statistiche economiche", "Apre trend economici e incassi.", [("Apri statistiche", "/statistiche", "GET")]),
    ],
    "backup": [
        ("archivio-backup", "Archivio backup", "Apre lista backup, verifica e download.", [("Apri backup", "/impostazioni?tab=backup", "GET")]),
        ("scheduler-backup", "Scheduler backup", "Apre configurazione delle automazioni.", [("Apri scheduler", "/impostazioni?tab=scheduler", "GET")]),
        ("database", "Database", "Apre controllo archivi e copie.", [("Apri database", "/admin/database", "GET")]),
    ],
    "sincronizzazione-calendari": [
        ("pannello-calendario", "Pannello calendario", "Apre link riservati, calendari collegati e sincronizzazione.", [("Apri calendari", "/impostazioni/calendario", "GET")]),
        ("export-agenda", "Export agenda", "Scarica il file calendario degli appuntamenti.", [("Scarica agenda", "/agenda/export.ics", "GET")]),
        ("export-scadenze", "Export scadenze", "Scarica il file calendario delle scadenze.", [("Scarica scadenze", "/scadenziario/export.ics", "GET")]),
    ],
    "amministrazione": [
        ("utenti", "Utenti", "Apre gestione operatori e accessi.", [("Apri utenti", "/utenti", "GET")]),
        ("profili-e-permessi", "Profili e permessi", "Apre matrice ruoli e policy.", [("Apri permessi", "/profili", "GET")]),
        ("registro-attivita", "Registro attività", "Apre registro e controllo operativo.", [("Apri registro", "/registro-attivita", "GET")]),
        ("database-e-gdpr", "Database e GDPR", "Apre storage e registro trattamenti.", [("Apri database", "/admin/database", "GET")]),
    ],
    "profili": [
        ("matrice-ruoli", "Matrice ruoli", "Apre tabella profili e permessi.", [("Apri matrice", "/profili", "GET")]),
        ("utenti", "Utenti", "Apre operatori e override autorizzativi.", [("Apri utenti", "/utenti", "GET")]),
        ("registro-permessi", "Registro permessi", "Apre il registro dei cambi ruolo.", [("Apri registro", "/registro-attivita", "GET")]),
    ],
}


def _catalog_operations(module_id: str, records: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows = _GENERIC_OPERATION_CATALOG.get(module_id, [])
    return [
        _operation(
            operation_id,
            title,
            body,
            records=records if index == 0 else [],
            actions=[_action(label, href, method=method) for label, href, method in actions],
        )
        for index, (operation_id, title, body, actions) in enumerate(rows)
    ]


def _build_generic(module_id: str, get_clienti: Callable[[], Any], get_fascicoli: Callable[[], Any]) -> dict[str, Any]:
    clienti = _safe("clienti", lambda: get_clienti().tutti(), [])
    fascicoli = _safe("fascicoli", lambda: get_fascicoli().tutti(), [])
    records = [
        _record(
            getattr(item, "id", ""),
            getattr(item, "titolo", "") or getattr(item, "nome_completo", ""),
            getattr(item, "numero_rg", ""),
            href=f"/fascicoli/{getattr(item, 'id', '')}",
        )
        for item in fascicoli[:12]
    ]
    records = [record for record in records if _is_visible_record(record)]
    operations = _catalog_operations(module_id, records)
    if operations:
        return {
            "metrics": [_metric("Clienti", len(clienti)), _metric("Fascicoli", len(fascicoli))],
            "operations": operations,
        }
    return {
        "metrics": [_metric("Clienti", len(clienti)), _metric("Fascicoli", len(fascicoli))],
        "operations": [
            _operation(
                module_id,
                "Funzione operativa",
                "Questa funzione usa dati reali e azioni gia' collegate.",
                actions=[_action("Apri modulo", f"/{module_id}")],
                records=[
                    _record(getattr(item, "id", ""), getattr(item, "titolo", "") or getattr(item, "nome_completo", ""), getattr(item, "numero_rg", ""), href=f"/fascicoli/{getattr(item, 'id', '')}")
                    for item in fascicoli[:12]
                ],
            )
        ],
    }


def build_react_studio_module_payload(
    *,
    module_id: str,
    config: dict[str, Any],
    get_utenti: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_preventivi: Callable[[], Any] | None = None,
    get_timesheet: Callable[[], Any] | None = None,
    get_config_studio: Callable[[], Any] | None = None,
    get_trattamenti: Callable[[], Any] | None = None,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = _text(module_id).lower()
    if normalized == "utenti":
        data = _build_utenti(get_utenti)
    elif normalized == "fatturazione":
        data = _build_fatturazione(get_fatturazione, get_clienti)
    elif normalized == "preventivi" and get_preventivi:
        data = _build_preventivi(
            get_preventivi,
            get_clienti,
            get_fascicoli,
            config,
            query=query,
            get_config_studio=get_config_studio,
        )
    elif normalized == "timesheet" and get_timesheet:
        data = _build_timesheet(get_timesheet, get_clienti, get_fascicoli)
    elif normalized in {"registro-attivita", "audit"}:
        data = _build_audit(get_utenti)
    elif normalized == "database":
        data = _build_database(config)
    elif normalized in {"gdpr", "registro-gdpr"} and get_trattamenti:
        data = _build_gdpr(get_trattamenti)
    elif normalized == "impostazioni-studio":
        data = _build_impostazioni(config)
    elif normalized == "strumenti-forensi":
        data = _build_strumenti_forensi(
            config,
            get_clienti,
            get_fascicoli,
            get_config_studio=get_config_studio,
            query=query,
        )
    else:
        data = _build_generic(normalized, get_clienti, get_fascicoli)
    data.setdefault("metrics", [])
    data.setdefault("operations", [])
    return {
        "source": "repository_reali",
        "moduleId": normalized,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "contracts": {
            "mock_fallback": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
        },
        **data,
    }
