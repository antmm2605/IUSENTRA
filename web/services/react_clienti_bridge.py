"""Bridge dati per la pagina Anagrafica Clienti della shell React.

Normalizza i repository esistenti senza introdurre una seconda source of truth
frontend. La pagina resta in sola lettura durante la migrazione progressiva.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Any, Callable, Mapping

from pct.clienti import StatoCliente, TipoCliente, TipoDocumento
from pct.soggetti import RuoloSoggetto, TipoSoggetto


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _text(value: Any, fallback: str = "") -> str:
    return " ".join(str(value or fallback).split())


def _short(value: Any, limit: int = 120) -> str:
    text = _text(value)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _safe(label: str, func: Callable[[], Any], fallback: Any) -> Any:
    try:
        return func()
    except Exception:
        return fallback


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raw = str(value or "").strip()
    if not raw:
        return None
    for sample in (raw.replace("Z", "+00:00"), raw[:19], raw[:10]):
        try:
            return datetime.fromisoformat(sample).date()
        except ValueError:
            continue
    return None


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _status(cliente: Any) -> str:
    raw = _enum_value(getattr(cliente, "stato", "")).lower()
    if "archiv" in raw:
        return "archiviato"
    if "potenzial" in raw:
        return "potenziale"
    if "inatt" in raw:
        return "inattivo"
    return "attivo"


def _type(cliente: Any) -> str:
    raw = _enum_value(getattr(cliente, "tipo", "")).lower()
    if "giurid" in raw or "societ" in raw or raw == "pg":
        return "pg"
    return "pf"


def _tone(status: str) -> str:
    return {"attivo": "success", "potenziale": "warning", "archiviato": "neutral", "inattivo": "orange"}.get(status, "neutral")


def _recapiti(cliente: Any) -> tuple[str, str, str]:
    recapiti = getattr(cliente, "recapiti", None)
    phone = _text(getattr(recapiti, "cellulare", "") or getattr(recapiti, "telefono", ""))
    email = _text(getattr(recapiti, "email", ""))
    pec = _text(getattr(recapiti, "pec", ""))
    return phone, email, pec


def _fiscal_id(cliente: Any) -> str:
    return _text(getattr(cliente, "identificativo_fiscale", "") or getattr(cliente, "codice_fiscale", "") or getattr(cliente, "partita_iva", ""))


def _document_expired(cliente: Any) -> bool:
    documento = getattr(cliente, "documento", None)
    try:
        explicit = getattr(documento, "scaduto", None)
        if isinstance(explicit, bool):
            return explicit
    except Exception:
        explicit = None
    due = _parse_date(getattr(documento, "data_scadenza", ""))
    return bool(due and due < date.today())


def _cliente_key(value: Any) -> str:
    return _text(value).lower()


def _matter_groups(fascicoli_repo: Any) -> tuple[dict[str, list[Any]], dict[str, list[Any]]]:
    by_client_id: dict[str, list[Any]] = defaultdict(list)
    by_client_name: dict[str, list[Any]] = defaultdict(list)
    seen: set[str] = set()
    candidates: list[Any] = []
    for getter in (lambda: fascicoli_repo.tutti(archiviati=False), lambda: fascicoli_repo.tutti(archiviati=True), lambda: fascicoli_repo.tutti()):
        value = _safe("fascicoli", getter, [])
        if isinstance(value, list):
            candidates.extend(value)
    for item in candidates:
        item_id = _text(getattr(item, "id", "")) or _text(getattr(item, "numero", ""))
        if item_id in seen:
            continue
        seen.add(item_id)
        id_cliente = _text(getattr(item, "id_cliente", "") or getattr(item, "cliente_id", ""))
        nome_cliente = _cliente_key(getattr(item, "nome_cliente", "") or getattr(item, "cliente", ""))
        if id_cliente:
            by_client_id[id_cliente].append(item)
        if nome_cliente:
            by_client_name[nome_cliente].append(item)
    return by_client_id, by_client_name


def _matters_for(cliente: Any, by_client_id: dict[str, list[Any]], by_client_name: dict[str, list[Any]]) -> list[Any]:
    cliente_id = _text(getattr(cliente, "id", ""))
    nome = _cliente_key(getattr(cliente, "nome_completo", ""))
    items = list(by_client_id.get(cliente_id, []))
    known = {_text(getattr(item, "id", "")) for item in items}
    for item in by_client_name.get(nome, []):
        item_id = _text(getattr(item, "id", ""))
        if item_id not in known:
            items.append(item)
            known.add(item_id)
    return items


def _active_matter_count(items: list[Any]) -> int:
    total = 0
    for item in items:
        raw = _enum_value(getattr(item, "stato", "")).lower()
        archived = bool(getattr(item, "archiviato", False) or getattr(item, "is_archived", False) or "archiv" in raw)
        if not archived:
            total += 1
    return total


def _missing_fields(cliente: Any) -> list[str]:
    explicit = getattr(cliente, "campi_mancanti_per_conferimento", []) or []
    if isinstance(explicit, list):
        return [_text(item) for item in explicit if _text(item)]
    return []


def _subtitle(cliente: Any) -> str:
    parts = [_text(getattr(cliente, "provenienza", "")), _text(getattr(cliente, "forma_giuridica", "")), _short(getattr(cliente, "note", ""), 70)]
    return " - ".join(part for part in parts if part)


def _facet_rows(items: list[dict[str, Any]], key: str, labels: dict[str, str], all_label: str) -> list[dict[str, Any]]:
    rows = [{"value": "tutti", "label": all_label, "count": len(items)}]
    for value, label in labels.items():
        rows.append({"value": value, "label": label, "count": sum(1 for item in items if item.get(key) == value)})
    return rows


def _summary(items: list[dict[str, Any]]) -> dict[str, int]:
    statuses = Counter(item.get("status") for item in items)
    return {
        "total": len(items),
        "active": int(statuses.get("attivo", 0)),
        "potential": int(statuses.get("potenziale", 0)),
        "archived": int(statuses.get("archiviato", 0)),
        "withMatters": sum(1 for item in items if int(item.get("matters") or 0) > 0),
        "incomplete": sum(1 for item in items if item.get("missingFields")),
        "withoutContacts": sum(1 for item in items if not (item.get("email") or item.get("phone") or item.get("pec"))),
        "privacyMissing": sum(1 for item in items if not item.get("privacyOk")),
        "documentsExpired": sum(1 for item in items if item.get("documentExpired")),
    }


def build_react_clienti_payload(*, get_clienti: Callable[[], Any], get_fascicoli: Callable[[], Any]) -> dict[str, Any]:
    clienti_repo = get_clienti()
    fascicoli_repo = get_fascicoli()
    by_client_id, by_client_name = _matter_groups(fascicoli_repo)
    clienti = _safe("clienti", lambda: clienti_repo.tutti(), [])
    items: list[dict[str, Any]] = []

    for index, cliente in enumerate(clienti):
        item_id = _text(getattr(cliente, "id", "")) or f"cliente-{index}"
        status = _status(cliente)
        tipo = _type(cliente)
        phone, email, pec = _recapiti(cliente)
        linked_matters = _matters_for(cliente, by_client_id, by_client_name)
        procedimenti = getattr(cliente, "procedimenti", []) or []
        matters_count = max(len(linked_matters), len(procedimenti) if isinstance(procedimenti, list) else 0)
        active_count = max(_active_matter_count(linked_matters), len(getattr(cliente, "procedimenti_attivi", []) or []))
        tags = getattr(cliente, "tag", []) or []
        if not isinstance(tags, list):
            tags = []
        items.append({
            "id": item_id,
            "name": _text(getattr(cliente, "nome_completo", "")) or "Cliente senza nome",
            "subtitle": _subtitle(cliente),
            "type": tipo,
            "fiscalId": _fiscal_id(cliente) or "-",
            "email": email,
            "phone": phone,
            "pec": pec,
            "attorney": _text(getattr(cliente, "avvocato_referente", "")) or "-",
            "matters": matters_count,
            "activeMatters": active_count,
            "status": status,
            "missingFields": _missing_fields(cliente),
            "privacyOk": bool(getattr(cliente, "consenso_trattamento", False)),
            "documentExpired": _document_expired(cliente),
            "tags": [_text(tag) for tag in tags if _text(tag)],
            "lastUpdated": _text(getattr(cliente, "modificato_il", "") or getattr(cliente, "creato_il", "")),
            "href": f"/clienti/{item_id}",
            "editHref": f"/clienti/{item_id}/modifica",
            "folderHref": f"/clienti/{item_id}/cartella",
            "tone": _tone(status),
        })

    type_labels = {"pf": "Persone fisiche", "pg": "Persone giuridiche"}
    status_labels = {"attivo": "Attivi", "potenziale": "Potenziali", "archiviato": "Archiviati", "inattivo": "Inattivi"}
    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {"mock_fallback": False, "read_only": True},
        "summary": _summary(items),
        "items": items,
        "facets": {"types": _facet_rows(items, "type", type_labels, "Tutti i tipi"), "statuses": _facet_rows(items, "status", status_labels, "Tutti gli stati")},
    }


def _option(value: Any, *, label: str = "", subtitle: str = "", tone: str = "neutral", count: int | None = None) -> dict[str, Any]:
    raw = _enum_value(value)
    payload: dict[str, Any] = {
        "value": raw,
        "label": label or raw.replace("_", " ").title(),
        "tone": tone,
    }
    if subtitle:
        payload["subtitle"] = subtitle
    if count is not None:
        payload["count"] = count
    return payload


def _subject_type_tone(value: TipoSoggetto) -> str:
    return {
        TipoSoggetto.PERSONA_FISICA: "primary",
        TipoSoggetto.PERSONA_GIURIDICA: "purple",
        TipoSoggetto.PUBBLICA_AMMINISTRAZIONE: "info",
        TipoSoggetto.ENTE: "neutral",
        TipoSoggetto.CONDOMINIO: "orange",
        TipoSoggetto.ASSOCIAZIONE: "success",
        TipoSoggetto.PROFESSIONISTA: "primary",
    }.get(value, "neutral")


def _role_tone(value: RuoloSoggetto) -> str:
    return {
        RuoloSoggetto.ASSISTITO: "success",
        RuoloSoggetto.CONTROPARTE: "danger",
        RuoloSoggetto.DIFENSORE_CONTROPARTE: "danger",
        RuoloSoggetto.TESTIMONE: "warning",
        RuoloSoggetto.PERITO_CTP: "info",
        RuoloSoggetto.PERITO_CTU: "info",
        RuoloSoggetto.CORRISPONDENTE: "primary",
        RuoloSoggetto.NOTAIO: "purple",
        RuoloSoggetto.MEDIATORE: "success",
        RuoloSoggetto.GARANTE: "warning",
        RuoloSoggetto.INTERVENIENTE: "info",
        RuoloSoggetto.CREDITORE: "primary",
        RuoloSoggetto.DEBITORE: "danger",
    }.get(value, "neutral")


def _client_options(clienti: list[Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for cliente in clienti:
        recapiti = getattr(cliente, "recapiti", None)
        item_id = _text(getattr(cliente, "id", ""))
        if not item_id:
            continue
        rows.append({
            "id": item_id,
            "label": _text(getattr(cliente, "nome_completo", "")) or "Cliente senza nome",
            "taxCode": _fiscal_id(cliente),
            "email": _text(getattr(recapiti, "email", "")),
            "type": _enum_value(getattr(cliente, "tipo", "")),
        })
    return rows


def _clienti_nuovo_stats(clienti: list[Any], soggetti: list[Any]) -> dict[str, int]:
    return {
        "totalClients": len(clienti),
        "physicalClients": sum(1 for item in clienti if getattr(item, "tipo", None) == TipoCliente.PERSONA_FISICA),
        "legalClients": sum(1 for item in clienti if getattr(item, "tipo", None) == TipoCliente.PERSONA_GIURIDICA),
        "activeClients": sum(1 for item in clienti if getattr(item, "stato", None) == StatoCliente.ATTIVO),
        "potentialClients": sum(1 for item in clienti if getattr(item, "stato", None) == StatoCliente.POTENZIALE),
        "missingRegistry": sum(1 for item in clienti if _missing_fields(item)),
        "expiredDocuments": sum(1 for item in clienti if _document_expired(item)),
        "totalSubjects": len(soggetti),
        "subjectsWithoutClient": sum(1 for item in soggetti if not _text(getattr(item, "id_cliente", ""))),
    }


def build_react_clienti_nuovo_payload(
    *,
    get_clienti: Callable[[], Any],
    get_soggetti: Callable[[], Any],
    query: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    clienti = _safe("clienti", lambda: get_clienti().tutti(), [])
    soggetti = _safe("soggetti", lambda: get_soggetti().tutti(), [])
    query = query or {}
    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {"mock_fallback": False, "read_only": True, "writes": "legacy_routes"},
        "stats": _clienti_nuovo_stats(clienti, soggetti),
        "options": {
            "clientTypes": [
                _option(TipoCliente.PERSONA_FISICA, label="Persona fisica", subtitle="Privato, professionista o assistito", tone="primary"),
                _option(TipoCliente.PERSONA_GIURIDICA, label="Persona giuridica", subtitle="Societa, ente o organizzazione", tone="purple"),
            ],
            "clientStatuses": [_option(item, tone={"ATTIVO": "success", "POTENZIALE": "warning", "INATTIVO": "orange"}.get(item.value, "neutral")) for item in StatoCliente],
            "documentTypes": [_option(item) for item in TipoDocumento],
            "cieGenerations": [
                {"value": "elettronica", "label": "Elettronica dal 2016 con MRZ", "tone": "primary"},
                {"value": "plastificata", "label": "Plastificata 2000-2016", "tone": "neutral"},
                {"value": "cartacea", "label": "Cartacea pre-2000", "tone": "neutral"},
            ],
            "subjectTypes": [_option(item, tone=_subject_type_tone(item)) for item in TipoSoggetto],
            "subjectRoles": [_option(item, label=item.label, tone=_role_tone(item)) for item in RuoloSoggetto],
            "legalForms": [
                {"value": "", "label": "-"},
                *[{"value": item, "label": item} for item in ["Srl", "SpA", "Sas", "Snc", "Ss", "Impresa individuale", "Cooperativa", "Associazione", "Fondazione", "Ente pubblico", "Altro"]],
            ],
            "qualificationHints": [{"value": item, "label": item} for item in ["Avvocato", "Procuratore", "Notaio", "Geometra", "Ingegnere", "Architetto", "Medico", "Perito industriale", "Commercialista", "Consulente del lavoro", "Mediatore", "Curatore fallimentare", "Liquidatore", "Magistrato", "Pubblico Ministero"]],
        },
        "clientOptions": _client_options(clienti),
        "actions": {
            "newClient": "/clienti/nuovo",
            "newSubject": "/soggetti/nuovo",
            "clientsList": "/app-v2/clienti",
            "subjectsList": "/app-v2/soggetti",
            "legacyClientForm": "/clienti/nuovo",
            "legacySubjectForm": "/soggetti/nuovo",
        },
        "query": {
            "tab": _text(query.get("tab") or query.get("tipo")),
            "nextUrl": _text(query.get("next_url") or query.get("next")),
            "idCliente": _text(query.get("id_cliente")),
        },
        "insights": [
            "Prima del salvataggio controlla CF/P.IVA per prevenire duplicati.",
            "Per il conferimento incarico servono dati fiscali, recapiti e indirizzo.",
            "Il soggetto processuale usa il campo qualifica per restare compatibile con la UI storica.",
        ],
    }
