"""Stato idempotente dei presidi documentali.

Il modulo contiene solo helper puri: non legge file, non apre database e non
avvia OCR. I runner dei singoli presidi gli passano impronta, metadati ed
evidenze già calcolati, poi salvano l'esito nel proprio repository.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


UNRESOLVED_CU_REASON = (
    "Presidio documentale eseguito: nei documenti del fascicolo e nei documenti indicizzati in archivio centrale "
    "non risulta una ricevuta, un'autocertificazione di esenzione o un invito al pagamento "
    "del contributo unificato leggibile."
)


def _text(value: Any, default: str = "") -> str:
    value = str(value or "").strip()
    return value or default


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_document_source(value: Any, *, default: str = "Documento indicizzato del fascicolo") -> str:
    source = _text(value)
    if not source:
        return default
    name = Path(source.replace("\\", "/")).name
    if not name:
        return default
    marker = source.casefold()
    stem = Path(name).stem.casefold()
    if marker.startswith(("document_id:", "documento_id:", "docai-", "docai_", "doc-", "doc_")):
        return default
    if stem.isdigit() and len(stem) >= 10:
        return default
    return source


def marker_is_current(marker: Mapping[str, Any] | None, fingerprint: str) -> bool:
    if not isinstance(marker, Mapping):
        return False
    status = _text(marker.get("status") or marker.get("stato")).casefold()
    cached = _text(marker.get("fingerprint") or marker.get("documentFingerprint"))
    return status == "aggiornato" and bool(cached) and cached == _text(fingerprint)


def marker_state(
    marker: Mapping[str, Any] | None,
    fingerprint: str,
    *,
    related_count: int = 0,
) -> dict[str, Any]:
    marker = marker if isinstance(marker, Mapping) else {}
    cached = _text(marker.get("fingerprint") or marker.get("documentFingerprint"))
    status_raw = _text(marker.get("status") or marker.get("stato")).casefold()
    unresolved_kinds = _normalise_unresolved_kinds(marker.get("unresolvedKinds") or marker.get("unresolved_kinds") or marker.get("da_verificare"))
    if status_raw == "stale":
        status = "da_rianalizzare"
        label = "Da rianalizzare"
        reason = _text(marker.get("reason"), "Sono entrati nuovi documenti o è cambiato il fascicolo.")
    elif cached and cached == _text(fingerprint) and unresolved_kinds:
        status = "aggiornato_con_rilievi"
        label = "Documenti controllati"
        reason = _unresolved_reason(marker, unresolved_kinds)
    elif cached and cached == _text(fingerprint):
        status = "aggiornato"
        label = "Aggiornato"
        reason = _text(marker.get("reason"), "Analisi allineata ai documenti presenti.")
    elif cached:
        status = "da_rianalizzare"
        label = "Da rianalizzare"
        reason = "Sono entrati nuovi documenti o è cambiato il fascicolo."
    else:
        status = "da_analizzare"
        label = "Da analizzare"
        reason = "Nessuna impronta di analisi consolidata sui documenti del fascicolo e sui documenti indicizzati in archivio centrale."
    return {
        "status": status,
        "statusLabel": label,
        "tone": "warning" if status in {"da_rianalizzare", "da_analizzare", "aggiornato_con_rilievi"} else "success",
        "reason": reason,
        "fingerprint": _text(fingerprint),
        "lastAnalyzedAt": _text(marker.get("updated_at") or marker.get("updatedAt") or marker.get("lastAnalyzedAt")),
        "relatedDuplicateFascicoli": max(0, int(related_count or 0)),
        "unresolvedKinds": unresolved_kinds,
    }


def _normalise_unresolved_kinds(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]
    elif isinstance(value, (list, tuple, set)):
        values = [str(item or "").strip() for item in value if str(item or "").strip()]
    else:
        values = []
    return sorted(dict.fromkeys(values))


def _normalise_read_documents(value: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for raw in value or []:
        if not isinstance(raw, Mapping):
            continue
        document_id = _text(raw.get("id") or raw.get("documentId") or raw.get("document_id") or raw.get("documento_id"))
        sha256 = _text(raw.get("sha256") or raw.get("hash_sha256")).lower()
        filename = _text(raw.get("nome") or raw.get("filename") or raw.get("documentoFonte") or raw.get("source"))
        source = _text(raw.get("source") or raw.get("readSource") or raw.get("lettura"), "unknown")
        fascicolo_id = _text(raw.get("fascicoloId") or raw.get("fascicolo_id"))
        mode = _text(raw.get("mode") or raw.get("readMode"), "text")
        key = (fascicolo_id, document_id, sha256, source)
        if key in seen or not any(key):
            continue
        seen.add(key)
        try:
            chars = max(0, int(raw.get("chars") or raw.get("textChars") or 0))
        except Exception:
            chars = 0
        rows.append(
            {
                "fascicoloId": fascicolo_id,
                "documentId": document_id,
                "filename": filename,
                "sha256": sha256,
                "source": source,
                "mode": mode,
                "textChars": chars,
            }
        )
    return sorted(rows, key=lambda item: (item["fascicoloId"], item["documentId"], item["sha256"], item["source"]))


def _read_documents_fingerprint(rows: Iterable[Mapping[str, Any]]) -> str:
    payload = json.dumps(list(rows or []), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _unresolved_reason(marker: Mapping[str, Any], unresolved_kinds: list[str]) -> str:
    if "contributo_unificato" in unresolved_kinds:
        return UNRESOLVED_CU_REASON
    return _text(
        marker.get("reason"),
        "Presidio documentale eseguito: alcuni dati non risultano dai documenti del fascicolo o dai documenti indicizzati in archivio centrale.",
    )


#  ---------------------------------------------------------------------------
#  Inventario dei documenti gia' letti
#
#  Il presidio economico girava ogni quarto d'ora e rileggeva gli stessi
#  documenti all'infinito: sul server questo significava CPU a un core pieno e
#  raffiche di lettura da disco a 300 MB/s, con l'applicazione che non
#  rispondeva piu' al controllo di salute e rispondeva 503.
#
#  Il marcatore diceva soltanto "l'analisi e' allineata", un'informazione
#  ricavata dall'esito economico: se il contributo unificato non risultava dai
#  documenti, il fascicolo sembrava sempre da lavorare. Qui il presidio tiene
#  invece l'elenco dei documenti che ha davvero letto, con la loro identita' di
#  contenuto. Un documento gia' letto e immutato non si rilegge: quando sono
#  stati letti tutti, il giro successivo non ha piu' niente da fare e finisce
#  subito.
#
#  L'inventario non contiene il testo dei documenti: solo identificativo, nome,
#  hash, dimensione, da dove e' arrivata la lettura e quanti caratteri sono
#  stati letti.
#  ---------------------------------------------------------------------------

READ_DOCUMENTS_KEY = "readDocuments"
READ_DOCUMENTS_VERSION_KEY = "readDocumentsVersion"
MAX_READ_DOCUMENTS = 400


def read_document_entry(
    *,
    document_id: Any,
    nome: Any = "",
    sha256: Any = "",
    size: Any = 0,
    source: Any = "",
    chars: Any = 0,
) -> dict[str, Any]:
    """Una riga dell'inventario: cosa e' stato letto, non cosa c'era scritto."""

    return {
        "id": _text(document_id),
        "nome": _text(nome),
        "sha256": _text(sha256),
        "size": max(0, int(size or 0)),
        "source": _text(source, "sconosciuta"),
        "chars": max(0, int(chars or 0)),
    }


def document_read_key(*, sha256: Any = "", size: Any = 0) -> str:
    """Identita' di contenuto di un documento gia' letto.

    L'hash e' la firma buona. Dove manca resta la dimensione: grossolana, ma
    e' l'unico segnale di contenuto disponibile e non cambia da sola come
    farebbe una data di aggiornamento.
    """

    digest = _text(sha256)
    if digest:
        return f"sha256:{digest.casefold()}"
    return f"size:{max(0, int(size or 0))}"


def read_inventory(marker: Mapping[str, Any] | None, *, analysis_version: str = "") -> dict[str, str]:
    """Documenti gia' letti: id documento -> identita' di contenuto.

    Se il marcatore e' stato scritto con una versione del lettore diversa da
    quella attuale l'inventario non vale piu': le regole di lettura sono
    cambiate e i documenti vanno riletti.
    """

    if not isinstance(marker, Mapping):
        return {}
    atteso = _text(analysis_version)
    if atteso:
        registrata = _text(
            marker.get(READ_DOCUMENTS_VERSION_KEY)
            or marker.get("analysisVersion")
            or marker.get("analysis_version")
        )
        if registrata != atteso:
            return {}
    righe = marker.get(READ_DOCUMENTS_KEY)
    if not isinstance(righe, (list, tuple)):
        return {}
    out: dict[str, str] = {}
    for riga in righe:
        if not isinstance(riga, Mapping):
            continue
        document_id = _text(riga.get("id") or riga.get("document_id") or riga.get("documento_id"))
        if not document_id:
            continue
        out[document_id] = document_read_key(sha256=riga.get("sha256"), size=riga.get("size"))
    return out


def unread_document_ids(
    documents: Iterable[Mapping[str, Any]],
    marker: Mapping[str, Any] | None,
    *,
    analysis_version: str = "",
) -> list[str]:
    """Documenti nuovi o cambiati rispetto all'ultima lettura.

    `documents` sono righe `{"id", "sha256", "size"}` costruite dal chiamante:
    questo modulo non conosce il modello dei documenti e non legge nulla.
    """

    letti = read_inventory(marker, analysis_version=analysis_version)
    out: list[str] = []
    visti: set[str] = set()
    for row in documents or []:
        if not isinstance(row, Mapping):
            continue
        document_id = _text(row.get("id") or row.get("document_id") or row.get("documento_id"))
        if not document_id or document_id in visti:
            continue
        visti.add(document_id)
        atteso = document_read_key(sha256=row.get("sha256"), size=row.get("size"))
        if letti.get(document_id) != atteso:
            out.append(document_id)
    return out


def merge_read_inventory(
    marker: Mapping[str, Any] | None,
    entries: Iterable[Mapping[str, Any]],
    *,
    analysis_version: str = "",
    known_document_ids: Iterable[Any] | None = None,
    limit: int = MAX_READ_DOCUMENTS,
) -> list[dict[str, Any]]:
    """Aggiorna l'inventario con le letture appena fatte.

    Le letture nuove sostituiscono quelle vecchie sullo stesso documento. Se il
    chiamante dichiara quali documenti esistono ora, le righe dei documenti
    spariti vengono tolte, cosi' l'inventario non cresce senza fine.
    """

    precedenti: dict[str, dict[str, Any]] = {}
    if isinstance(marker, Mapping) and _text(analysis_version) and read_inventory(
        marker, analysis_version=analysis_version
    ):
        for riga in marker.get(READ_DOCUMENTS_KEY) or []:
            if not isinstance(riga, Mapping):
                continue
            document_id = _text(riga.get("id") or riga.get("document_id") or riga.get("documento_id"))
            if document_id:
                precedenti[document_id] = dict(riga)

    for entry in entries or []:
        if not isinstance(entry, Mapping):
            continue
        document_id = _text(entry.get("id") or entry.get("document_id") or entry.get("documento_id"))
        if not document_id:
            continue
        precedenti[document_id] = read_document_entry(
            document_id=document_id,
            nome=entry.get("nome") or entry.get("filename"),
            sha256=entry.get("sha256"),
            size=entry.get("size"),
            source=entry.get("source"),
            chars=entry.get("chars"),
        )

    if known_document_ids is not None:
        ammessi = {_text(value) for value in known_document_ids if _text(value)}
        precedenti = {key: value for key, value in precedenti.items() if key in ammessi}

    righe = [precedenti[key] for key in sorted(precedenti)]
    massimo = max(1, int(limit or MAX_READ_DOCUMENTS))
    return righe[:massimo]


def metadata_rule_hits(
    metadata_rows: Iterable[Mapping[str, Any]],
    *,
    readable_source: Callable[[Any], str] = default_document_source,
    limit: int = 60,
) -> list[dict[str, Any]]:
    try:
        from pct.presidio_processuale_ruleset import presidio_rule_hits
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for metadata in metadata_rows or []:
        document_id = _text(metadata.get("document_id") or metadata.get("documento_id"))
        if not document_id:
            continue
        for hit in presidio_rule_hits("", dict(metadata)):
            key = (document_id, _text(hit.get("code") or hit.get("classification")))
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "documentId": document_id,
                    "documentoFonte": readable_source(metadata.get("filename") or document_id),
                    "code": _text(hit.get("code")),
                    "sector": _text(hit.get("sector")),
                    "label": _text(hit.get("label")),
                    "classification": _text(hit.get("classification")),
                    "legalBasis": list(hit.get("legalBasis") or []),
                    "parserFields": list(hit.get("parserFields") or []),
                    "source": "metadati_documento",
                }
            )
            if len(out) >= limit:
                return out
    return out


def automatic_economic_hits(
    automatic_sources: Mapping[str, Mapping[str, Any]] | None,
    *,
    readable_source: Callable[[Any], str] = default_document_source,
    normalise_kind: Callable[[Any], str] | None = None,
    normalise_status: Callable[[Any], str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(automatic_sources, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for kind, source in automatic_sources.items():
        if not isinstance(source, Mapping):
            continue
        normalized_kind = normalise_kind(kind) if callable(normalise_kind) else _text(kind)
        status = normalise_status(source.get("status") or source.get("stato")) if callable(normalise_status) else _text(source.get("status") or source.get("stato"))
        nature = _text(source.get("natura"))
        document_source = readable_source(source.get("documento_fonte") or source.get("document_id") or source.get("filename"))
        if normalized_kind == "contributo_unificato":
            if status == "non_previsto" or nature == "esenzione_contributo_unificato":
                code = "contributo_unificato_esenzione"
                classification = "contributo_unificato_esente"
                label = "Contributo unificato esente o non dovuto"
            elif status == "da_registrare":
                code = "contributo_unificato_invito"
                classification = "contributo_unificato_da_regolarizzare"
                label = "Contributo unificato da registrare o regolarizzare"
            else:
                code = "contributo_unificato_pagamento"
                classification = "contributo_unificato"
                label = "Contributo unificato pagato"
            rows.append(
                {
                    "documentoFonte": document_source,
                    "code": code,
                    "sector": "economico",
                    "label": label,
                    "classification": classification,
                    "legalBasis": ["D.P.R. 115/2002"],
                    "parserFields": ["amount", "iuv", "payment_date", "esito"],
                    "source": "parser_economico",
                }
            )
        elif normalized_kind in {"liquidazione_giudice", "spese_esborsi", "parcella"}:
            rows.append(
                {
                    "documentoFonte": document_source,
                    "code": "spese_liquidazione",
                    "sector": "economico",
                    "label": "Liquidazione spese e compensi",
                    "classification": "sentenza_economica",
                    "legalBasis": ["artt. 91-93 c.p.c.", "D.M. 55/2014"],
                    "parserFields": ["liquidazione", "compensi", "esborsi", "spese_generali"],
                    "source": "parser_economico",
                }
            )
    return rows


def build_marker(
    *,
    fingerprint: str,
    actor: str,
    document_count: int,
    metadata_rows: Iterable[Mapping[str, Any]] = (),
    automatic_sources: Mapping[str, Mapping[str, Any]] | None = None,
    read_documents: Iterable[Mapping[str, Any]] = (),
    readable_source: Callable[[Any], str] = default_document_source,
    normalise_kind: Callable[[Any], str] | None = None,
    normalise_status: Callable[[Any], str] | None = None,
    status: str = "aggiornato",
    reason: str = "Analisi documentale completata e salvata nel fascicolo.",
) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for hit in [
        *automatic_economic_hits(
            automatic_sources,
            readable_source=readable_source,
            normalise_kind=normalise_kind,
            normalise_status=normalise_status,
        ),
        *metadata_rule_hits(metadata_rows, readable_source=readable_source),
    ]:
        key = (_text(hit.get("documentId") or hit.get("documentoFonte")), _text(hit.get("code")), _text(hit.get("classification")))
        if key in seen:
            continue
        seen.add(key)
        hits.append(hit)
    read_rows = _normalise_read_documents(read_documents)
    return {
        "status": status,
        "fingerprint": _text(fingerprint),
        "updated_at": _now(),
        "updated_by": _text(actor, "IUSENTRA"),
        "reason": reason,
        "document_count": max(0, int(document_count or 0)),
        "readDocumentCount": len(read_rows),
        "readDocumentsFingerprint": _read_documents_fingerprint(read_rows),
        "readDocuments": read_rows[:500],
        "classifications": hits[:80],
        "coverage": ["documenti_fascicolo", "economia", "contributo_unificato", "sentenze"],
    }


__all__ = [
    "MAX_READ_DOCUMENTS",
    "READ_DOCUMENTS_KEY",
    "READ_DOCUMENTS_VERSION_KEY",
    "automatic_economic_hits",
    "build_marker",
    "default_document_source",
    "document_read_key",
    "marker_is_current",
    "marker_state",
    "merge_read_inventory",
    "metadata_rule_hits",
    "read_document_entry",
    "read_inventory",
    "unread_document_ids",
]
