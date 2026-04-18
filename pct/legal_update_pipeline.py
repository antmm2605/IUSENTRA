from __future__ import annotations

from email.utils import parsedate_to_datetime
import hashlib
import json
import re
from typing import Any, Callable
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import requests
from lxml import html as lxml_html

from pct.giurisprudenza import GestioneGiurisprudenza
from pct.legal_update_ai import analyze_document
from pct.legal_update_repository import LegalUpdateDbConfig, LegalUpdateRepository


RequestGet = Callable[..., Any]

DEFAULT_SOURCE_ROWS: tuple[dict[str, Any], ...] = (
    {
        "name": "Gazzetta Ufficiale",
        "code": "gazzetta_ufficiale",
        "category": "normativa",
        "base_url": "https://www.gazzettaufficiale.it/",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 60,
        "parser_type": "html",
        "notes": "Fonte primaria ufficiale per nuove leggi, decreti e regolamenti.",
    },
    {
        "name": "Normattiva",
        "code": "normattiva",
        "category": "normativa",
        "base_url": "https://www.normattiva.it/",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 360,
        "parser_type": "html",
        "notes": "Testo vigente, storico e multivigente.",
    },
    {
        "name": "Dati Normattiva",
        "code": "dati_normattiva",
        "category": "normativa",
        "base_url": "https://dati.normattiva.it/",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "html",
        "notes": "Canale tecnico/open data per integrazione normativa.",
    },
    {
        "name": "Corte Costituzionale",
        "code": "corte_costituzionale",
        "category": "giurisprudenza",
        "base_url": "https://www.cortecostituzionale.it/",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 120,
        "parser_type": "html",
        "notes": "Sentenze, comunicati e depositi della Corte costituzionale.",
    },
    {
        "name": "Cassazione Massimario",
        "code": "cassazione_massimario",
        "category": "giurisprudenza",
        "base_url": "https://www.cortedicassazione.it/",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 180,
        "parser_type": "html",
        "notes": "Massimario e raccolte della Cassazione.",
    },
    {
        "name": "Giustizia Amministrativa",
        "code": "giustizia_amministrativa",
        "category": "giurisprudenza",
        "base_url": "https://www.giustizia-amministrativa.it/",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 180,
        "parser_type": "html",
        "notes": "Provvedimenti di TAR e Consiglio di Stato.",
    },
    {
        "name": "EUR-Lex",
        "code": "eur_lex",
        "category": "ue",
        "base_url": "https://eur-lex.europa.eu/",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 360,
        "parser_type": "html",
        "notes": "Normativa e giurisprudenza UE.",
    },
    {
        "name": "Agenzia Entrate",
        "code": "agenzia_entrate",
        "category": "prassi",
        "base_url": "https://www.agenziaentrate.gov.it/",
        "source_type": "web",
        "trust_class": "B",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 240,
        "parser_type": "html",
        "notes": "Circolari, risoluzioni, interpelli e provvedimenti.",
    },
    {
        "name": "Ministero del Lavoro",
        "code": "ministero_lavoro",
        "category": "prassi",
        "base_url": "https://www.lavoro.gov.it/",
        "source_type": "web",
        "trust_class": "B",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 240,
        "parser_type": "html",
        "notes": "Prassi, decreti e circolari del lavoro.",
    },
)

HTML_DATE_RE = re.compile(r"\b([0-3]?\d/[01]?\d/[12]\d{3})\b")


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _truncate(value: str, limit: int = 240) -> str:
    cleaned = _clean_spaces(value)
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3].rstrip() + "..."


def _sha256(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _parse_pub_date(value: Any) -> str:
    text = _clean_spaces(value)
    if not text:
        return ""
    try:
        return parsedate_to_datetime(text).date().isoformat()
    except (TypeError, ValueError, IndexError, OverflowError):
        pass
    match = HTML_DATE_RE.search(text)
    if not match:
        return ""
    day, month, year = match.group(1).split("/")
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _looks_like_feed(content: str, content_type: str) -> bool:
    return "xml" in (content_type or "").lower() or content.lstrip().startswith("<rss") or content.lstrip().startswith("<feed")


def _extract_feed_items(source: dict[str, Any], base_url: str, content: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []
    docs: list[dict[str, Any]] = []
    for item in root.findall(".//item") + root.findall(".//{*}entry"):
        title = _clean_spaces(item.findtext("title") or item.findtext("{*}title"))
        link = _clean_spaces(item.findtext("link") or item.findtext("{*}link"))
        if not link:
            link_node = item.find("{*}link")
            if link_node is not None:
                link = _clean_spaces(link_node.attrib.get("href") or link_node.text)
        summary = _clean_spaces(item.findtext("description") or item.findtext("{*}summary") or item.findtext("{*}content"))
        published_at = _parse_pub_date(item.findtext("pubDate") or item.findtext("{*}published") or item.findtext("{*}updated"))
        if not title and not link:
            continue
        absolute_url = urljoin(base_url, link or source.get("base_url") or "")
        docs.append(
            {
                "external_id": _sha256(f"{source.get('code')}|{absolute_url}|{title}"),
                "source_url": absolute_url,
                "title": title or absolute_url,
                "published_at": published_at,
                "raw_html": "",
                "raw_text": summary,
                "body_short": _truncate(summary or title),
            }
        )
    return docs


def _extract_html_items(source: dict[str, Any], base_url: str, content: str) -> list[dict[str, Any]]:
    try:
        tree = lxml_html.fromstring(content)
    except (ValueError, TypeError):
        return []
    docs: list[dict[str, Any]] = []
    for anchor in tree.xpath("//a[@href]")[:120]:
        title = _clean_spaces(anchor.text_content())
        href = _clean_spaces(anchor.attrib.get("href"))
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        if len(title) < 12:
            continue
        absolute_url = urljoin(base_url, href)
        context = _clean_spaces(" ".join(anchor.xpath(".//text()"))) or title
        row_text = _clean_spaces(
            " ".join(anchor.xpath("./ancestor::*[self::li or self::article or self::div][1]//text()"))
        ) or context
        published_at = _parse_pub_date(row_text)
        docs.append(
            {
                "external_id": _sha256(f"{source.get('code')}|{absolute_url}|{title}"),
                "source_url": absolute_url,
                "title": title,
                "published_at": published_at,
                "raw_html": "",
                "raw_text": row_text,
                "body_short": _truncate(row_text or title),
            }
        )
    if docs:
        unique: dict[str, dict[str, Any]] = {}
        for row in docs:
            unique[row["external_id"]] = row
        return list(unique.values())[:40]
    plain = _clean_spaces(" ".join(tree.xpath("//body//text()")))
    return [
        {
            "external_id": _sha256(f"{source.get('code')}|{base_url}|fallback"),
            "source_url": base_url,
            "title": _clean_spaces(tree.findtext(".//title")) or source.get("name") or base_url,
            "published_at": "",
            "raw_html": content,
            "raw_text": plain,
            "body_short": _truncate(plain),
        }
    ]


class LegalUpdatePipeline:
    def __init__(
        self,
        intelligence_db_path: str,
        *,
        giurisprudenza_db_path: str = "",
        ai_base_url: str = "",
        ai_model: str = "",
    ) -> None:
        self.intelligence_db_path = str(intelligence_db_path or "").strip()
        self.giurisprudenza_db_path = str(giurisprudenza_db_path or "").strip()
        self.ai_base_url = str(ai_base_url or "").strip()
        self.ai_model = str(ai_model or "").strip() or "mistral"
        cfg = LegalUpdateDbConfig.from_anchor(self.intelligence_db_path)
        self.repository = LegalUpdateRepository(cfg.db_path, json_path=cfg.json_path)
        self.repository.upsert_sources(list(DEFAULT_SOURCE_ROWS))

    def list_sources(self, *, enabled_only: bool = True) -> list[dict[str, Any]]:
        return self.repository.list_sources(enabled_only=enabled_only)

    def get_source(self, source_id: int) -> dict[str, Any] | None:
        return self.repository.get_source_by_id(source_id)

    def _fetch_source(self, source: dict[str, Any], *, request_get: RequestGet) -> list[dict[str, Any]]:
        response = request_get(
            source["base_url"],
            timeout=25,
            headers={"User-Agent": "IUSENTRA-Legal-Updates/1.0"},
        )
        content_type = getattr(response, "headers", {}).get("content-type", "")
        text = ""
        if hasattr(response, "text"):
            text = str(response.text or "")
        elif hasattr(response, "content"):
            text = bytes(response.content or b"").decode("utf-8", errors="ignore")
        if _looks_like_feed(text, content_type):
            docs = _extract_feed_items(source, source["base_url"], text)
        else:
            docs = _extract_html_items(source, source["base_url"], text)
        if not docs:
            docs = [
                {
                    "external_id": _sha256(f"{source['code']}|{source['base_url']}|empty"),
                    "source_url": source["base_url"],
                    "title": source["name"],
                    "published_at": "",
                    "raw_html": text[:20000],
                    "raw_text": _truncate(text, limit=4000),
                    "body_short": _truncate(text),
                }
            ]
        for row in docs:
            row.setdefault("raw_html", text[:20000])
            row.setdefault("raw_text", row.get("body_short") or "")
            row["content_hash"] = _sha256(json.dumps(row, ensure_ascii=False, sort_keys=True))
            row["http_status"] = int(getattr(response, "status_code", 200) or 0)
            row["fetch_status"] = "fetched" if row["http_status"] < 400 else "error"
        return docs

    def _normalize_document(self, source: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
        body_text = _clean_spaces(raw.get("raw_text") or raw.get("title"))
        title = _clean_spaces(raw.get("title"))
        issuer = source.get("name") or ""
        document_type_guess = source.get("category") or ""
        return {
            "title": title or source.get("name") or raw.get("source_url") or "Documento acquisito",
            "body_text": body_text,
            "body_short": _truncate(body_text or title),
            "language": "it",
            "issuer": issuer,
            "document_date": _clean_spaces(raw.get("published_at")),
            "document_type_guess": document_type_guess,
            "attachments_json": [],
            "normalized_hash": _sha256(f"{title}|{body_text}|{issuer}|{document_type_guess}"),
        }

    def _match_target(self, analysis: dict[str, Any]) -> dict[str, Any]:
        classification = str(analysis.get("classification_type") or "")
        if classification in {"NORMATIVA_NUOVA", "NORMATIVA_AGGIORNAMENTO"}:
            match = self.repository.find_normative_match(
                str(analysis.get("norm_type") or ""),
                str(analysis.get("norm_number") or ""),
                str(analysis.get("norm_year") or ""),
                str(analysis.get("issuer") or ""),
            )
            if match:
                return {"entity_type": "normative", "entity": match}
        if classification == "GIURISPRUDENZA":
            match = self.repository.find_jurisprudence_match(
                str(analysis.get("court_name") or ""),
                str(analysis.get("decision_number") or ""),
                str(analysis.get("decision_year") or ""),
            )
            if match:
                return {"entity_type": "jurisprudence", "entity": match}
        if classification == "PRASSI":
            match = self.repository.find_prassi_match(
                str(analysis.get("issuer") or ""),
                str(analysis.get("norm_type") or ""),
                str(analysis.get("norm_number") or ""),
                str(analysis.get("norm_year") or ""),
            )
            if match:
                return {"entity_type": "prassi", "entity": match}
        return {"entity_type": "", "entity": None}

    def _review_priority(self, source: dict[str, Any], analysis: dict[str, Any], proposed_action: str) -> int:
        priority = 35
        if source.get("is_official"):
            priority += 15
        if proposed_action in {"UPDATE_NORMATIVE", "NEW_NORMATIVE", "NEW_CASE_LAW"}:
            priority += 20
        if str(analysis.get("impact_level") or "") == "alto":
            priority += 15
        priority += int(float(analysis.get("confidence_score") or 0) * 10)
        return max(10, min(priority, 100))

    def _decide_proposal(self, source: dict[str, Any], analysis: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
        classification = str(analysis.get("classification_type") or "INCERTO")
        confidence = float(analysis.get("confidence_score") or 0)
        has_norm_key = all(analysis.get(field) for field in ("norm_type", "norm_number", "norm_year"))
        has_judgment_key = all(analysis.get(field) for field in ("court_name", "decision_number", "decision_year"))
        is_official = bool(source.get("is_official"))

        proposed_action = "NEEDS_REVIEW"
        target_entity_type = str(target.get("entity_type") or "")
        target_entity = target.get("entity") or {}
        target_entity_id = target_entity.get("id")
        status = "pending"

        if classification in {"NEWS", "COMMENTO"}:
            proposed_action = "NEWS_ONLY"
        elif classification == "GIURISPRUDENZA":
            if target_entity_id:
                proposed_action = "DUPLICATE"
                status = "closed"
            elif is_official and has_judgment_key:
                proposed_action = "NEW_CASE_LAW"
        elif classification == "PRASSI":
            if target_entity_id:
                proposed_action = "DUPLICATE"
                status = "closed"
            elif is_official and analysis.get("norm_number") and analysis.get("norm_year"):
                proposed_action = "NEW_PRASSI"
        elif classification in {"NORMATIVA_NUOVA", "NORMATIVA_AGGIORNAMENTO"}:
            if target_entity_id:
                proposed_action = "UPDATE_NORMATIVE"
                target_entity_type = "normative"
            elif is_official and has_norm_key:
                proposed_action = "NEW_NORMATIVE"
        elif classification == "DUPLICATO":
            proposed_action = "DUPLICATE"
            status = "closed"

        if proposed_action == "NEWS_ONLY" and confidence >= 0.9 and is_official:
            status = "approved"
        if proposed_action in {"NEW_NORMATIVE", "UPDATE_NORMATIVE", "NEW_CASE_LAW", "NEW_PRASSI"} and confidence < 0.8:
            status = "pending"

        return {
            "proposed_action": proposed_action,
            "target_entity_type": target_entity_type,
            "target_entity_id": target_entity_id,
            "review_status": status,
            "priority": self._review_priority(source, analysis, proposed_action),
        }

    def _build_review_payload(
        self,
        source: dict[str, Any],
        normalized: dict[str, Any],
        analysis: dict[str, Any],
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "source": {
                "code": source.get("code"),
                "name": source.get("name"),
                "category": source.get("category"),
                "trust_class": source.get("trust_class"),
                "is_official": bool(source.get("is_official")),
            },
            "document": {
                "title": normalized.get("title"),
                "document_date": normalized.get("document_date"),
                "issuer": normalized.get("issuer"),
                "body_short": normalized.get("body_short"),
            },
            "analysis": {
                "classification_type": analysis.get("classification_type"),
                "summary_short": analysis.get("summary_short"),
                "summary_long": analysis.get("summary_long"),
                "what_changes": analysis.get("what_changes"),
                "confidence_score": analysis.get("confidence_score"),
                "matter_slug": analysis.get("matter_slug"),
                "submatter_slug": analysis.get("submatter_slug"),
            },
            "decision": decision,
        }

    def process_document(self, source: dict[str, Any], raw_payload: dict[str, Any]) -> dict[str, Any]:
        raw_saved = self.repository.save_raw_document(
            {
                "source_id": source["id"],
                **raw_payload,
            }
        )
        normalized_payload = self._normalize_document(source, raw_saved)
        normalized_saved = self.repository.save_normalized_document(int(raw_saved["id"]), normalized_payload)
        analysis_payload = analyze_document(
            normalized_saved,
            source,
            ai_base_url=self.ai_base_url,
            ai_model=self.ai_model,
        )
        target = self._match_target(analysis_payload)
        decision = self._decide_proposal(source, analysis_payload, target)
        analysis_saved = self.repository.save_analysis(
            int(normalized_saved["id"]),
            {
                **analysis_payload,
                "proposed_action": decision["proposed_action"],
                "target_entity_type": decision["target_entity_type"],
                "target_entity_id": decision["target_entity_id"],
            },
        )
        review = self.repository.upsert_review_item(
            {
                "normalized_document_id": int(normalized_saved["id"]),
                "analysis_id": int(analysis_saved["id"]),
                "proposal_type": str(analysis_saved.get("classification_type") or "").lower(),
                "proposed_action": decision["proposed_action"],
                "target_entity_type": decision["target_entity_type"],
                "target_entity_id": decision["target_entity_id"],
                "proposal_payload_json": self._build_review_payload(source, normalized_saved, analysis_saved, decision),
                "status": decision["review_status"],
                "priority": decision["priority"],
            }
        )
        return {
            "raw": raw_saved,
            "normalized": normalized_saved,
            "analysis": analysis_saved,
            "review": review,
        }

    def analyze_raw_document(self, raw_document_id: int) -> dict[str, Any]:
        raw_saved = self.repository.get_raw_document(raw_document_id)
        if not raw_saved:
            raise ValueError("Documento raw non trovato.")
        source = self.repository.get_source_by_id(int(raw_saved["source_id"]))
        if not source:
            raise ValueError("Fonte associata non trovata.")
        raw_payload = {
            "external_id": raw_saved.get("external_id"),
            "source_url": raw_saved.get("source_url"),
            "title": raw_saved.get("title"),
            "published_at": raw_saved.get("published_at"),
            "raw_html": raw_saved.get("raw_html"),
            "raw_text": raw_saved.get("raw_text"),
            "raw_pdf_path": raw_saved.get("raw_pdf_path"),
            "content_hash": raw_saved.get("content_hash"),
            "fetch_status": raw_saved.get("fetch_status"),
            "http_status": raw_saved.get("http_status"),
        }
        return self.process_document(source, raw_payload)

    def scan_source(self, source_code: str, *, request_get: RequestGet = requests.get, auto_publish: bool = True) -> dict[str, Any]:
        source = self.repository.get_source_by_code(source_code)
        if not source:
            raise ValueError(f"Fonte non configurata: {source_code}")
        documents = self._fetch_source(source, request_get=request_get)
        processed: list[dict[str, Any]] = []
        for document in documents:
            processed.append(self.process_document(source, document))
        autopublished = {"count": 0, "items": []}
        if auto_publish:
            autopublished = self.publish_auto_news(limit=20)
        self.repository.export_repository_json()
        return {
            "source": source_code,
            "documents_found": len(documents),
            "processed": len(processed),
            "autopublished": autopublished,
        }

    def fetch_source_by_id(self, source_id: int, *, auto_publish: bool = True, request_get: RequestGet = requests.get) -> dict[str, Any]:
        source = self.repository.get_source_by_id(source_id)
        if not source:
            raise ValueError("Fonte non trovata.")
        return self.scan_source(str(source["code"]), request_get=request_get, auto_publish=auto_publish)

    def run_cycle(
        self,
        *,
        source_codes: list[str] | None = None,
        request_get: RequestGet = requests.get,
        auto_publish: bool = True,
    ) -> dict[str, Any]:
        self.repository.upsert_sources(list(DEFAULT_SOURCE_ROWS))
        selected = source_codes or [row["code"] for row in self.repository.list_sources(enabled_only=True)]
        reports: list[dict[str, Any]] = []
        for source_code in selected:
            try:
                reports.append(self.scan_source(source_code, request_get=request_get, auto_publish=False))
            except Exception as exc:
                reports.append({"source": source_code, "error": str(exc), "documents_found": 0, "processed": 0})
        autopublished = self.publish_auto_news(limit=40) if auto_publish else {"count": 0, "items": []}
        self.repository.export_repository_json()
        return {
            "ok": True,
            "sources": selected,
            "reports": reports,
            "autopublished": autopublished,
            "dashboard": self.repository.dashboard_snapshot(),
        }

    def approve_review(self, review_id: int, *, reviewer: str, notes: str = "") -> dict[str, Any] | None:
        return self.repository.set_review_status(review_id, "approved", reviewer=reviewer, notes=notes)

    def reject_review(self, review_id: int, *, reviewer: str, notes: str = "") -> dict[str, Any] | None:
        return self.repository.set_review_status(review_id, "rejected", reviewer=reviewer, notes=notes)

    def edit_and_approve_review(self, review_id: int, *, reviewer: str, review_notes: str, summary_short: str, what_changes: str) -> dict[str, Any] | None:
        review = self.repository.get_review_item(review_id)
        if not review:
            return None
        proposal = dict(review.get("proposal_payload_json") or {})
        analysis = dict(proposal.get("analysis") or {})
        if summary_short:
            analysis["summary_short"] = _clean_spaces(summary_short)
        if what_changes:
            analysis["what_changes"] = _clean_spaces(what_changes)
        proposal["analysis"] = analysis
        self.repository.upsert_review_item(
            {
                "normalized_document_id": int(review["normalized_document_id"]),
                "analysis_id": int(review["analysis_id"]),
                "proposal_type": review["proposal_type"],
                "proposed_action": review["proposed_action"],
                "target_entity_type": review["target_entity_type"],
                "target_entity_id": review.get("target_entity_id"),
                "proposal_payload_json": proposal,
                "status": "approved",
                "priority": int(review.get("priority") or 50),
                "review_notes": review_notes,
                "reviewed_by": reviewer,
                "reviewed_at": review.get("reviewed_at") or "",
            }
        )
        return self.repository.set_review_status(review_id, "approved", reviewer=reviewer, notes=review_notes)

    def _news_type_for(self, classification_type: str, proposed_action: str) -> str:
        if classification_type == "GIURISPRUDENZA":
            return "giurisprudenza"
        if classification_type == "PRASSI":
            return "prassi"
        if proposed_action == "UPDATE_NORMATIVE":
            return "aggiornamento"
        if classification_type in {"NORMATIVA_NUOVA", "NORMATIVA_AGGIORNAMENTO"}:
            return "normativa"
        if classification_type == "COMMENTO":
            return "commento"
        return "focus"

    def _publish_news_only(self, review: dict[str, Any], *, reviewer: str) -> dict[str, Any]:
        payload = self.repository.create_or_update_news(
            {
                "title": review.get("title"),
                "short_summary": review.get("summary_short"),
                "content": review.get("what_changes") or review.get("summary_long") or review.get("body_text"),
                "news_type": self._news_type_for(str(review.get("classification_type") or ""), str(review.get("proposed_action") or "")),
                "matter_slug": review.get("matter_slug"),
                "submatter_slug": review.get("submatter_slug"),
                "source_url": review.get("source_url"),
                "source_document_id": review.get("normalized_document_id"),
                "is_auto_generated": True,
                "publication_status": "published",
                "published_at": review.get("published_at") or "",
            },
            performed_by=reviewer,
        )
        self.repository.set_review_status(int(review["id"]), "published", reviewer=reviewer, notes="News pubblicata.")
        return {"news": payload}

    def publish_review(self, review_id: int, *, reviewer: str = "admin") -> dict[str, Any]:
        review = self.repository.get_review_item(review_id)
        if not review:
            raise ValueError("Review non trovata.")
        proposed_action = str(review.get("proposed_action") or "")
        classification = str(review.get("classification_type") or "")
        result: dict[str, Any] = {}

        if proposed_action in {"NEWS_ONLY", "DUPLICATE"}:
            result = self._publish_news_only(review, reviewer=reviewer)
        elif proposed_action in {"NEW_NORMATIVE", "UPDATE_NORMATIVE"}:
            normative = self.repository.create_or_update_normative(
                {
                    "title": review.get("title"),
                    "slug": review.get("title"),
                    "norm_type": review.get("norm_type"),
                    "norm_number": review.get("norm_number"),
                    "norm_year": review.get("norm_year"),
                    "issuer": review.get("issuer") or review.get("source_name"),
                    "publication_date": review.get("document_date") or review.get("published_at"),
                    "effective_date": review.get("effective_date") or review.get("document_date"),
                    "status": "vigente",
                    "matter_slug": review.get("matter_slug"),
                    "submatter_slug": review.get("submatter_slug"),
                    "source_url": review.get("source_url"),
                    "source_document_id": review.get("normalized_document_id"),
                    "text_official": review.get("body_text"),
                    "text_current": review.get("body_text"),
                    "summary": review.get("summary_long") or review.get("summary_short"),
                    "notes": review.get("what_changes"),
                    "version_label": review.get("document_date") or "versione corrente",
                },
                performed_by=reviewer,
            )
            news = self.repository.create_or_update_news(
                {
                    "title": review.get("title"),
                    "short_summary": review.get("summary_short"),
                    "content": review.get("what_changes") or review.get("summary_long"),
                    "news_type": self._news_type_for(classification, proposed_action),
                    "matter_slug": review.get("matter_slug"),
                    "submatter_slug": review.get("submatter_slug"),
                    "related_normative_id": normative.get("id"),
                    "source_url": review.get("source_url"),
                    "source_document_id": review.get("normalized_document_id"),
                    "is_auto_generated": True,
                    "publication_status": "published",
                },
                performed_by=reviewer,
            )
            self.repository.set_review_status(int(review_id), "published", reviewer=reviewer, notes="Normativa pubblicata.")
            result = {"normative": normative, "news": news}
        elif proposed_action == "NEW_CASE_LAW":
            jurisprudence = self.repository.create_or_update_jurisprudence(
                {
                    "title": review.get("title"),
                    "slug": review.get("title"),
                    "court_name": review.get("court_name") or review.get("source_name"),
                    "decision_number": review.get("decision_number"),
                    "decision_year": review.get("decision_year"),
                    "decision_date": review.get("document_date") or review.get("published_at"),
                    "publication_date": review.get("published_at") or review.get("document_date"),
                    "matter_slug": review.get("matter_slug"),
                    "submatter_slug": review.get("submatter_slug"),
                    "principle_of_law": review.get("what_changes"),
                    "summary": review.get("summary_long") or review.get("summary_short"),
                    "full_text": review.get("body_text"),
                    "source_url": review.get("source_url"),
                    "source_document_id": review.get("normalized_document_id"),
                },
                performed_by=reviewer,
            )
            if self.giurisprudenza_db_path:
                try:
                    GestioneGiurisprudenza(db_path=self.giurisprudenza_db_path).salva(
                        {
                            "titolo": review.get("title"),
                            "fonte": review.get("court_name") or review.get("source_name"),
                            "materia": review.get("matter_name") or review.get("matter_slug"),
                            "riassunto": review.get("summary_short"),
                            "principio_di_diritto": review.get("what_changes"),
                            "link": review.get("source_url"),
                            "numero": review.get("decision_number"),
                            "anno": review.get("decision_year"),
                            "testo_integrale": review.get("body_text"),
                        }
                    )
                except Exception:
                    pass
            news = self.repository.create_or_update_news(
                {
                    "title": review.get("title"),
                    "short_summary": review.get("summary_short"),
                    "content": review.get("what_changes") or review.get("summary_long"),
                    "news_type": "giurisprudenza",
                    "matter_slug": review.get("matter_slug"),
                    "submatter_slug": review.get("submatter_slug"),
                    "related_jurisprudence_id": jurisprudence.get("id"),
                    "source_url": review.get("source_url"),
                    "source_document_id": review.get("normalized_document_id"),
                    "is_auto_generated": True,
                    "publication_status": "published",
                },
                performed_by=reviewer,
            )
            self.repository.set_review_status(int(review_id), "published", reviewer=reviewer, notes="Giurisprudenza pubblicata.")
            result = {"jurisprudence": jurisprudence, "news": news}
        elif proposed_action == "NEW_PRASSI":
            prassi = self.repository.create_or_update_prassi(
                {
                    "title": review.get("title"),
                    "slug": review.get("title"),
                    "issuing_body": review.get("issuer") or review.get("source_name"),
                    "act_type": review.get("norm_type"),
                    "act_number": review.get("norm_number"),
                    "act_year": review.get("norm_year"),
                    "act_date": review.get("document_date") or review.get("published_at"),
                    "matter_slug": review.get("matter_slug"),
                    "submatter_slug": review.get("submatter_slug"),
                    "summary": review.get("summary_long") or review.get("summary_short"),
                    "full_text": review.get("body_text"),
                    "source_url": review.get("source_url"),
                    "source_document_id": review.get("normalized_document_id"),
                },
                performed_by=reviewer,
            )
            news = self.repository.create_or_update_news(
                {
                    "title": review.get("title"),
                    "short_summary": review.get("summary_short"),
                    "content": review.get("what_changes") or review.get("summary_long"),
                    "news_type": "prassi",
                    "matter_slug": review.get("matter_slug"),
                    "submatter_slug": review.get("submatter_slug"),
                    "related_prassi_id": prassi.get("id"),
                    "source_url": review.get("source_url"),
                    "source_document_id": review.get("normalized_document_id"),
                    "is_auto_generated": True,
                    "publication_status": "published",
                },
                performed_by=reviewer,
            )
            self.repository.set_review_status(int(review_id), "published", reviewer=reviewer, notes="Prassi pubblicata.")
            result = {"prassi": prassi, "news": news}
        else:
            raise ValueError(f"Azione di pubblicazione non supportata: {proposed_action}")

        self.repository.export_repository_json()
        return result

    def publish_auto_news(self, *, limit: int = 20) -> dict[str, Any]:
        items = self.repository.list_review_queue(statuses=("approved", "pending"), limit=limit)
        published: list[int] = []
        for row in items:
            if str(row.get("proposed_action") or "") != "NEWS_ONLY":
                continue
            if not row.get("source_code"):
                continue
            source = self.repository.get_source_by_code(str(row["source_code"]))
            if not source or not source.get("is_official"):
                continue
            if float(row.get("confidence_score") or 0) < 0.9:
                continue
            self.publish_review(int(row["id"]), reviewer="system")
            published.append(int(row["id"]))
        return {"count": len(published), "items": published}

    def dashboard_snapshot(self) -> dict[str, Any]:
        return self.repository.dashboard_snapshot()


def build_legal_update_pipeline(
    intelligence_db_path: str,
    *,
    giurisprudenza_db_path: str = "",
    ai_base_url: str = "",
    ai_model: str = "",
) -> LegalUpdatePipeline:
    return LegalUpdatePipeline(
        intelligence_db_path,
        giurisprudenza_db_path=giurisprudenza_db_path,
        ai_base_url=ai_base_url,
        ai_model=ai_model,
    )
