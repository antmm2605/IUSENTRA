"""Payload React per l'archivio documentale aggregato dello studio."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Callable, Mapping

from pct.formatting import format_date_it, format_datetime_it


_TYPE_LABELS = {
    "ATTO_GIUDIZIARIO": "Atto giudiziario",
    "ATTO": "Atto",
    "RICORSO": "Ricorso",
    "CITAZIONE": "Atto di citazione",
    "COMPARSA": "Comparsa",
    "MEMORIA": "Memoria",
    "ISTANZA": "Istanza",
    "PROCURA": "Procura alle liti",
    "ALLEGATO": "Allegato",
    "SENTENZA": "Sentenza",
    "ORDINANZA": "Ordinanza",
    "DECRETO": "Decreto",
    "VERBALE": "Verbale",
    "COMUNICAZIONE": "Comunicazione",
    "PEC": "Comunicazione PEC",
    "DEPOSITO_PCT": "Deposito telematico",
    "NOTIFICA": "Notifica legale",
    "CONTRATTO": "Contratto",
    "PARCELLA": "Parcella",
    "ALTRO": "Altro documento",
}

_SOURCE_LABELS = {
    "IMPORT_ESTERNO": "Documento importato",
    "TEMPLATE_ATTI_COMPILATORE": "Redazione atti",
    "PORTALE_TELEMATICO": "Portale Servizi",
    "PST": "Portale Servizi",
    "POLISWEB": "Portale Servizi",
    "CARICAMENTO_STUDIO": "Studio",
    "PEC_CANCELLERIA": "PEC di cancelleria",
    "PEC_AUDIT_PIPELINE": "Presidio PEC",
    "PEC_AUDIT_NOTIFICATION_RECEIPT": "Ricevuta di notifica PEC",
    "PAGOPA_RT_PEC": "Ricevuta pagoPA via PEC",
    "NOTIFICA_LEGALE": "Notifica legale",
    "REDAZIONE_STUDIO": "Redazione dello studio",
    "EDITOR_AI_LEX": "Editor con Lex",
    "DOCUMENTI_AI_SERVER": "Lettura assistita",
    "APERTURA_FASCICOLO_VELOCE": "Apertura del fascicolo",
    "COPIA_RUOTATA_DA_LETTORE": "Copia ruotata dal lettore",
    "CTU_LIQUIDAZIONE": "Liquidazione CTU",
}

# Formati riconosciuti: il suffisso del nome conta come formato solo se è un'estensione di file
# reale. Nomi come «Ricorso 23.11.2025» o «atto ric. Compagnone» non hanno estensione.
_FORMATI_NOTI = frozenset(
    "pdf p7m p7s m7m tsd tsr xml eml msg doc docx docm odt rtf txt html htm zip rar 7z enc "
    "jpg jpeg png gif bmp tif tiff webp heic svg xls xlsx xlsm ods csv ppt pptx odp json ics vcf "
    "mp3 mp4 m4a wav ogg mov avi".split()
)
# Marcatori tecnici che le pipeline scrivono in testa alle note (es. «IUSENTRA_PROVVEDIMENTO_CANCELLERIA:<id>»):
# servono al software per l'idempotenza, non all'avvocato.
_MARCATORE_NOTE = re.compile(r"^IUSENTRA_[A-Z_]+:\S*\s*$")
_DATA_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def _text(value: Any, default: str = "") -> str:
    current = str(value if value is not None else default).strip()
    return current or default


def _enum_value(value: Any) -> str:
    return _text(getattr(value, "value", value)).upper()


def _format_name(*values: Any) -> str:
    """Formato dal primo nome con un'estensione riconosciuta (nome, nome originale, percorso)."""
    for value in values:
        name = _text(value).lower()
        for compound in (".pdf.p7m", ".xml.p7m", ".docx.p7m", ".doc.p7m"):
            if name.endswith(compound):
                return compound[1:].upper()
        match = re.search(r"\.([a-z0-9]{1,5})$", name)
        if match and match.group(1) in _FORMATI_NOTI:
            return match.group(1).upper()
    return "ALTRO"


def _public_notes(value: Any) -> str:
    """Note leggibili: senza marcatori tecnici e con le date in formato italiano."""
    righe = [riga for riga in _text(value).splitlines() if not _MARCATORE_NOTE.match(riga.strip())]
    testo = "\n".join(righe).strip()
    testo = re.sub(r"^IUSENTRA_[A-Z_]+:\S+\s*", "", testo)
    return _DATA_ISO.sub(lambda m: f"{m.group(3)}/{m.group(2)}/{m.group(1)}", testo)


def _bytes_label(value: Any) -> str:
    try:
        size = max(0, int(value or 0))
    except (TypeError, ValueError):
        size = 0
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB".replace(".", ",")
    return f"{size / (1024 * 1024):.1f} MB".replace(".", ",")


def _matter_ref(fascicolo: Any) -> str:
    numero_rg = _text(getattr(fascicolo, "numero_rg", ""))
    anno_rg = _text(getattr(fascicolo, "anno_rg", ""))
    rg = f"RG {numero_rg}/{anno_rg}" if numero_rg and anno_rg else numero_rg
    return _text(getattr(fascicolo, "numero", "")) or rg or _text(getattr(fascicolo, "id", ""))


def _source_label(documento: Any) -> str:
    source = _enum_value(getattr(documento, "fonte_documento", ""))
    return _SOURCE_LABELS.get(source, source.replace("_", " ").title() if source else "Studio")


def _row(fascicolo: Any, documento: Any, *, in_trash: bool) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    did = _text(getattr(documento, "id", ""))
    raw_type = _enum_value(getattr(documento, "tipo", "ALTRO")) or "ALTRO"
    name = _text(getattr(documento, "nome", ""), "Documento")
    uploaded_at = _text(getattr(documento, "data_caricamento", ""))
    document_date = _text(getattr(documento, "data_documento", ""))
    eliminated_at = _text(getattr(documento, "eliminato_il", ""))
    matter_status = _enum_value(getattr(fascicolo, "stato", ""))
    base = f"/fascicoli/{fid}/documenti/{did}"
    actions = {
        "matter": f"/fascicoli/{fid}",
        "preview": "" if in_trash else f"{base}/visualizza",
        "download": "" if in_trash else f"{base}/scarica",
        "edit": "" if in_trash else f"{base}/editor",
        "sign": "" if in_trash else f"{base}/firma",
        "rename": "" if in_trash else f"{base}/rinomina",
        "delete": "" if in_trash else f"{base}/elimina",
        "restore": f"{base}/ripristina" if in_trash else "",
        "permanentDelete": f"{base}/elimina-definitivamente" if in_trash else "",
    }
    return {
        "id": did,
        "matterId": fid,
        "matterRef": _matter_ref(fascicolo),
        "matterTitle": _text(getattr(fascicolo, "titolo", ""), "Fascicolo"),
        "matterClient": _text(getattr(fascicolo, "nome_cliente", "")),
        "matterStatus": matter_status,
        "matterArchived": matter_status == "ARCHIVIATO",
        "name": name,
        "originalName": _text(getattr(documento, "nome_originale", "")),
        "type": raw_type,
        "typeLabel": _TYPE_LABELS.get(raw_type, raw_type.replace("_", " ").title()),
        "format": _format_name(name, getattr(documento, "nome_originale", ""), getattr(documento, "percorso", "")),
        "size": _bytes_label(getattr(documento, "dimensione_bytes", 0)),
        "sizeBytes": int(getattr(documento, "dimensione_bytes", 0) or 0),
        "uploadedAt": format_datetime_it(uploaded_at),
        "uploadedAtIso": uploaded_at,
        "documentDate": format_date_it(document_date),
        "documentDateIso": document_date,
        "notes": _public_notes(getattr(documento, "note", "")),
        "tags": [_text(tag) for tag in (getattr(documento, "tags", []) or []) if _text(tag)],
        "source": _source_label(documento),
        "inTrash": in_trash,
        "deletedAt": format_datetime_it(eliminated_at),
        "deletedAtIso": eliminated_at,
        "deletedBy": _text(getattr(documento, "eliminato_da", "")),
        "actions": actions,
        "_sortAt": eliminated_at or uploaded_at or document_date,
    }


def _facet(counter: Counter[str], label_map: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    labels = label_map or {}
    return [
        {"value": value, "label": labels.get(value, value), "count": count}
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        if value
    ]


def build_react_document_archive_payload(
    *,
    get_fascicoli: Callable[[], Any],
    query: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggrega i documenti reali dei fascicoli senza creare un secondo archivio."""

    params = query or {}
    scope = _text(params.get("scope"), "attivi").lower()
    if scope not in {"attivi", "cestino"}:
        scope = "attivi"
    search = _text(params.get("q")).casefold()
    type_filter = _text(params.get("tipo")).upper()
    format_filter = _text(params.get("formato")).upper()
    matter_filter = _text(params.get("fascicolo"))
    try:
        page = max(1, int(params.get("page") or 1))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = min(100, max(20, int(params.get("per_page") or 50)))
    except (TypeError, ValueError):
        per_page = 50

    gestore = get_fascicoli()
    fascicoli = list(gestore.tutti(archiviati=True))
    active_rows: list[dict[str, Any]] = []
    trash_rows: list[dict[str, Any]] = []
    for fascicolo in fascicoli:
        active_rows.extend(_row(fascicolo, doc, in_trash=False) for doc in (getattr(fascicolo, "documenti", []) or []))
        trash_rows.extend(_row(fascicolo, doc, in_trash=True) for doc in (getattr(fascicolo, "documenti_cestino", []) or []))

    source_rows = trash_rows if scope == "cestino" else active_rows
    type_counts = Counter(row["type"] for row in source_rows)
    format_counts = Counter(row["format"] for row in source_rows)
    matter_counts = Counter(row["matterId"] for row in source_rows)
    matter_labels = {
        row["matterId"]: ' · '.join(part for part in [row['matterRef'], row['matterClient'], row['matterTitle']] if part)
        for row in source_rows
    }
    matter_clients = {row['matterId']: row['matterClient'] for row in source_rows}

    filtered = []
    for row in source_rows:
        if type_filter and row["type"] != type_filter:
            continue
        if format_filter and row["format"] != format_filter:
            continue
        if matter_filter and row["matterId"] != matter_filter:
            continue
        if search:
            haystack = " ".join(
                [
                    row["name"],
                    row["originalName"],
                    row["typeLabel"],
                    row["format"],
                    row["matterRef"],
                    row["matterTitle"],
                    row["matterClient"],
                    row["notes"],
                    row["source"],
                    " ".join(row["tags"]),
                ]
            ).casefold()
            if search not in haystack:
                continue
        filtered.append(row)

    filtered.sort(key=lambda row: (row["_sortAt"], row["name"].casefold()), reverse=True)
    total = len(filtered)
    pages = max(1, math.ceil(total / per_page))
    page = min(page, pages)
    start = (page - 1) * per_page
    items = filtered[start : start + per_page]
    for row in items:
        row.pop("_sortAt", None)

    return {
        "source": "fascicoli_tenant",
        "contracts": {"mockFallback": False, "readOnly": False},
        "summary": {
            "active": len(active_rows),
            "trash": len(trash_rows),
            "matters": len({row["matterId"] for row in active_rows}),
            "formats": len({row["format"] for row in active_rows}),
        },
        "filters": {
            "scope": scope,
            "q": _text(params.get("q")),
            "type": type_filter,
            "format": format_filter,
            "matter": matter_filter,
        },
        "facets": {
            "types": _facet(type_counts, _TYPE_LABELS),
            "formats": _facet(format_counts, {"ALTRO": "Altro formato"}),
            "matters": [{**facet, 'client': matter_clients.get(facet['value'], '')} for facet in _facet(matter_counts, matter_labels)],
        },
        "pagination": {
            "page": page,
            "perPage": per_page,
            "pages": pages,
            "total": total,
            "from": start + 1 if total else 0,
            "to": min(start + per_page, total),
        },
        "items": items,
        "actions": {
            "newDocument": "/template-atti/editor",
            "openMatters": "/fascicoli",
            "searchStudio": "/global-search?tipo=documenti",
        },
    }
