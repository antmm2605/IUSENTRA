"""Orchestratore applicativo del Procedure Completion Engine.

Collega catalogo PST, knowledge pipeline, template atti e fonti governate al
repository delle schede. Le scritture critiche (approve/publish) sono
fail-closed: richiedono validazione e revisione avvocato; nessuna scheda
diventa published senza fonti ufficiali/tecniche e citazioni verificabili.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from pct.procedure_completion.fusion import fuse_card
from pct.procedure_completion.models import (
    ProcedureCompletionCard,
    card_summary,
)
from pct.procedure_completion.repository import ProcedureCompletionRepository
from pct.procedure_completion.schema import (
    normalize_request,
    publish_blockers,
    validate_request,
)
from pct.procedure_completion.source_plan import (
    SourcePlanSettings,
    build_source_plan,
)
from pct.procedure_completion.validator import validate_card

PERMESSO_LEGGI = "procedure_completion.leggi"
PERMESSO_ESEGUI = "procedure_completion.esegui"
PERMESSO_APPROVA = "procedure_completion.approva"
PERMESSO_PUBBLICA = "procedure_completion.pubblica"
PERMESSO_ESPORTA = "procedure_completion.esporta"


class ProcedureCompletionError(ValueError):
    """Errore applicativo con messaggio mostrabile all'utente."""


def _context_value(context: dict[str, Any] | None, key: str) -> str:
    if not isinstance(context, dict):
        return ""
    return str(context.get(key) or "").strip()


def _context_permissions(context: dict[str, Any] | None) -> set[str]:
    if not isinstance(context, dict):
        return set()
    raw = context.get("permissions") or ()
    return {str(item).strip() for item in raw if str(item).strip()}


def _require_permission(context: dict[str, Any] | None, permesso: str) -> None:
    permessi = _context_permissions(context)
    if permessi and permesso not in permessi:
        raise ProcedureCompletionError(f"Permesso mancante: {permesso}.")


class ProcedureCompletionService:
    def __init__(
        self,
        repository: ProcedureCompletionRepository,
        *,
        settings: SourcePlanSettings | None = None,
        catalog_lookup: Optional[Callable[[str], Optional[dict[str, Any]]]] = None,
        template_search: Optional[Callable[..., dict[str, Any]]] = None,
        lifecycle_steps_loader: Optional[Callable[[dict[str, Any]], list[dict[str, Any]]]] = None,
        knowledge_card_loader: Optional[Callable[[str], Optional[dict[str, Any]]]] = None,
        lifecycle_evidence_loader: Optional[Callable[[str, str], list[dict[str, Any]]]] = None,
    ):
        self.repository = repository
        self.settings = settings or SourcePlanSettings()
        self._catalog_lookup = catalog_lookup
        self._template_search = template_search
        self._lifecycle_steps_loader = lifecycle_steps_loader
        self._knowledge_card_loader = knowledge_card_loader
        self._lifecycle_evidence_loader = lifecycle_evidence_loader

    # ------------------------------------------------------------- helpers

    def _lifecycle_steps(self, xsd_object: dict[str, Any]) -> list[dict[str, Any]]:
        if not xsd_object:
            return []
        loader = self._lifecycle_steps_loader
        if loader is None:
            try:
                from pct.procedure_lifecycle_templates import build_lifecycle_steps_for_xsd as loader  # type: ignore[assignment]
            except Exception:
                return []
        try:
            return list(loader(xsd_object) or [])
        except Exception:
            return []

    def _template_result(self, request_question: str, *, area: str, rito: str, template_code: str) -> dict[str, Any]:
        search = self._template_search
        if search is None:
            return {}
        try:
            return dict(
                search(
                    request_question,
                    area=area,
                    rito=rito,
                    template_code=template_code,
                )
                or {}
            )
        except TypeError:
            try:
                return dict(search(request_question) or {})
            except Exception:
                return {}
        except Exception:
            return {}

    def _knowledge_card(self, procedure_code: str) -> Optional[dict[str, Any]]:
        loader = self._knowledge_card_loader
        if loader is None or not procedure_code:
            return None
        try:
            return loader(procedure_code)
        except Exception:
            return None

    def _persist_card(self, card: ProcedureCompletionCard, *, actor: str) -> None:
        self.repository.save_card(card, actor=actor)
        for src in card.sources:
            self.repository.add_source(card.id, src, tenant_id=card.tenant_id)
        for cit in card.citations:
            self.repository.add_citation(card.id, cit, tenant_id=card.tenant_id)
        for gap in card.gap_evidenza:
            self.repository.add_gap(card.id, gap, tenant_id=card.tenant_id)
        selezionato_id = str(card.template_selected.get("template_id") or "")
        for cand in card.template_candidates:
            self.repository.link_template(
                card.id,
                cand,
                selezionato=bool(selezionato_id and cand.get("template_id") == selezionato_id),
                tenant_id=card.tenant_id,
            )
        report = validate_card(card)
        self.repository.save_validation_report(card.id, report.to_dict())

    # ------------------------------------------------------------ workflow

    def preview_completion(self, payload: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Costruisce e salva la scheda in bozza (run read-only: nessuna pubblicazione)."""
        _require_permission(context, PERMESSO_ESEGUI)
        request = normalize_request(payload)
        errori = validate_request(request)
        if errori:
            raise ProcedureCompletionError(" ".join(errori))
        tenant_id = _context_value(context, "tenant_id")
        actor = _context_value(context, "user_id")
        run_id = self.repository.create_run(
            procedure_code=request.codice or request.denominazione[:40],
            request_payload=request.to_dict(),
            tenant_id=tenant_id,
            requested_by=actor,
            mode="preview",
            template_code=request.template_code,
        )
        plan = build_source_plan(
            request,
            settings=self.settings,
            catalog_lookup=self._catalog_lookup,
            lifecycle_evidence_loader=self._lifecycle_evidence_loader,
        )
        question = " ".join(parte for parte in (request.denominazione, request.categoria, request.rito) if parte)
        template_result = self._template_result(
            question or request.codice,
            area=request.categoria,
            rito=request.rito,
            template_code=request.template_code,
        )
        card = fuse_card(
            request,
            plan,
            template_result=template_result,
            lifecycle_steps=self._lifecycle_steps(plan.xsd_object),
            knowledge_card=self._knowledge_card(request.codice),
            tenant_id=tenant_id,
            run_id=run_id,
        )
        self._persist_card(card, actor=actor)
        report = validate_card(card)
        return {
            "ok": True,
            "runId": run_id,
            "card": card.to_dict(),
            "summary": card_summary(card),
            "validation": report.to_dict(),
        }

    def complete_procedure(self, payload: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.preview_completion(payload, context)

    def get_card(self, card_id: str, context: dict[str, Any] | None = None) -> ProcedureCompletionCard:
        _require_permission(context, PERMESSO_LEGGI)
        card = self.repository.get_card(card_id, tenant_id=_context_value(context, "tenant_id"))
        if card is None:
            raise ProcedureCompletionError("Scheda non trovata o non accessibile dal contesto corrente.")
        return card

    def validate_completion(self, card: ProcedureCompletionCard) -> dict[str, Any]:
        report = validate_card(card)
        self.repository.save_validation_report(card.id, report.to_dict())
        return report.to_dict()

    def submit_for_review(self, card_id: str, context: dict[str, Any] | None = None, *, reason: str = "") -> dict[str, Any]:
        _require_permission(context, PERMESSO_ESEGUI)
        tenant_id = _context_value(context, "tenant_id")
        actor = _context_value(context, "user_id")
        card = self.repository.submit_for_review(card_id, requested_by=actor, reason=reason, tenant_id=tenant_id)
        report = validate_card(card)
        self.repository.save_validation_report(card.id, report.to_dict())
        return {"ok": True, "card": card.to_dict(), "validation": report.to_dict()}

    def approve_completion(self, card_id: str, *, reviewer: str, reason: str = "", context: dict[str, Any] | None = None) -> dict[str, Any]:
        _require_permission(context, PERMESSO_APPROVA)
        tenant_id = _context_value(context, "tenant_id")
        card = self.get_card(card_id, context)
        report = validate_card(card)
        if not report.approvable:
            motivi = report.errors + report.blocking_errors
            raise ProcedureCompletionError(
                "Approvazione bloccata: " + " ".join(motivi[:3] or ["validazione non superata."])
            )
        approvata = self.repository.approve_card(card_id, reviewer=reviewer, reason=reason, tenant_id=tenant_id)
        report_finale = validate_card(approvata)
        self.repository.save_validation_report(approvata.id, report_finale.to_dict())
        return {"ok": True, "card": approvata.to_dict(), "validation": report_finale.to_dict()}

    def publish_completion(self, card_id: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        _require_permission(context, PERMESSO_PUBBLICA)
        tenant_id = _context_value(context, "tenant_id")
        card = self.get_card(card_id, context)
        report = validate_card(card)
        blockers = publish_blockers(card, report.to_dict())
        if blockers:
            raise ProcedureCompletionError("Pubblicazione bloccata: " + " ".join(blockers[:3]))
        pubblicata = self.repository.publish_card(
            card_id,
            reviewer=_context_value(context, "user_id"),
            tenant_id=tenant_id,
        )
        report_finale = validate_card(pubblicata)
        self.repository.save_validation_report(pubblicata.id, report_finale.to_dict())
        return {"ok": True, "card": pubblicata.to_dict(), "validation": report_finale.to_dict()}

    # ------------------------------------------------------------- letture

    def search_cards(self, *, query: str = "", status: str = "", context: dict[str, Any] | None = None, limit: int = 30) -> list[dict[str, Any]]:
        _require_permission(context, PERMESSO_LEGGI)
        cards = self.repository.list_cards(
            tenant_id=_context_value(context, "tenant_id"),
            status=status,
            query=query,
            limit=limit,
        )
        return [card_summary(card) for card in cards]

    def list_gaps(self, *, severita: str = "", card_id: str = "", context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        _require_permission(context, PERMESSO_LEGGI)
        return self.repository.list_gaps(
            tenant_id=_context_value(context, "tenant_id"),
            severita=severita,
            card_id=card_id,
        )

    def explain_article(self, card_id: str, article_ref: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Spiegazione sintetica SOLO dalle citazioni gia' collegate (no consulenza)."""
        _require_permission(context, PERMESSO_LEGGI)
        card = self.get_card(card_id, context)
        chiave = str(article_ref or "").strip().lower()
        if not chiave:
            raise ProcedureCompletionError("Indica il riferimento dell'articolo da spiegare.")
        trovate = [
            cit for cit in card.citations
            if chiave in str(cit.get("riferimento") or "").lower()
        ]
        if not trovate:
            return {
                "ok": False,
                "needs_review": True,
                "riferimento": article_ref,
                "spiegazione": "",
                "citations": [],
                "next_actions": [
                    "Il riferimento non risulta tra le citazioni della scheda: verificarlo su fonte ufficiale prima dell'uso.",
                ],
            }
        sintesi = next(
            (
                voce.get("sintesi")
                for voce in card.sintesi_articoli
                if chiave in str(voce.get("riferimento") or "").lower() and voce.get("sintesi")
            ),
            "",
        )
        return {
            "ok": True,
            "needs_review": card.status not in {"approved", "published"},
            "riferimento": trovate[0].get("riferimento"),
            "spiegazione": sintesi or "Passaggio recuperato dalle fonti collegate: vedere snippet nelle citazioni.",
            "citations": trovate[:5],
            "disclaimer": "Sintesi documentale da fonti collegate: non costituisce consulenza legale.",
            "next_actions": [] if card.status in {"approved", "published"} else ["Completare la revisione avvocato della scheda."],
        }

    def suggest_template(self, card_id: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        _require_permission(context, PERMESSO_LEGGI)
        card = self.get_card(card_id, context)
        gaps = [gap for gap in card.gap_evidenza if gap.get("codice_gap") == "template_mancante"]
        return {
            "ok": True,
            "cardId": card.id,
            "templateSelected": card.template_selected,
            "candidates": card.template_candidates,
            "gaps": gaps,
            "needs_review": not bool(card.template_selected.get("template_id")),
        }


def default_template_search(question: str, *, area: str = "", rito: str = "", template_code: str = "") -> dict[str, Any]:
    """Ricerca template reale sul repository del catalogo atti (riuso)."""
    from pct.template_atti import GestioneTemplateAtti

    manager = GestioneTemplateAtti()
    repo = getattr(manager, "repository", None)
    if repo is None or not hasattr(repo, "select_best_templates"):
        return {}
    return repo.select_best_templates(question, area=area, rito=rito, limit=4)


__all__ = [
    "ProcedureCompletionService",
    "ProcedureCompletionError",
    "default_template_search",
    "PERMESSO_LEGGI",
    "PERMESSO_ESEGUI",
    "PERMESSO_APPROVA",
    "PERMESSO_PUBBLICA",
    "PERMESSO_ESPORTA",
]
