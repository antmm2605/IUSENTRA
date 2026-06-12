"""Fusione dei layer (catalogo, template, knowledge, fonti) nella scheda operativa.

La scheda contiene solo dati provenienti dai layer governati; ogni assenza
diventa un gap dichiarato. La confidence non e' mai una certezza legale:
HIGH richiede fonti ufficiali + template + review avvocato.
"""

from __future__ import annotations

from typing import Any, Optional

from pct.procedure_completion.extractor import references_from_rows, summarize_passage
from pct.procedure_completion.models import (
    ProcedureCompletionCard,
    ProcedureCompletionGap,
    ProcedureCompletionRequest,
    ProcedureTemplateCandidate,
    assign_confidence,
    empty_review,
    now_iso,
)
from pct.procedure_completion.source_plan import SourcePlan

AVVERTIMENTO_BOZZA = (
    "Bozza per revisione avvocato: contenuti da verificare su fonti ufficiali prima dell'uso."
)
AVVERTIMENTO_NO_AUTOMAZIONE = (
    "Il motore non deposita atti, non invia PEC e non firma: ogni azione resta all'avvocato."
)

# Flusso PCT standard (D.M. 44/2011, artt. 12-15): valido solo per i codici
# oggetto del catalogo PST, che per definizione viaggiano sul canale telematico.
_FIRMA_PCT = {
    "richiesta": True,
    "formati": ["CAdES (.p7m)", "PAdES"],
    "base_normativa": "D.M. 44/2011, art. 12",
    "nota": "Verificare la scadenza del certificato prima della firma.",
}
_DEPOSITO_PCT = {
    "canale": "PCT - deposito telematico",
    "busta": "Busta telematica (DatiAtto.xml + atti firmati)",
    "base_normativa": "D.M. 44/2011, art. 14",
    "nota": "Dimensione massima busta e controlli automatici secondo le specifiche DGSIA vigenti.",
}
_RICEVUTE_PCT = [
    "Ricevuta di accettazione PEC (RdAC)",
    "Ricevuta di avvenuta consegna PEC",
    "Esito controlli automatici",
    "Accettazione della cancelleria",
]
_NOTIFICHE_BASE = {
    "modalita": "PEC ex L. 53/1994, art. 3-bis (quando ammessa) o UNEP",
    "base_normativa": "L. 53/1994; art. 196-undecies disp. att. c.p.c.",
}
_PROVA_NOTIFICA_BASE = {
    "elementi": ["Relata firmata", "Ricevuta di accettazione", "Ricevuta di avvenuta consegna"],
    "base_normativa": "L. 53/1994",
}


def _candidates_from_template_result(template_result: dict[str, Any] | None) -> list[ProcedureTemplateCandidate]:
    if not isinstance(template_result, dict):
        return []
    candidati: list[ProcedureTemplateCandidate] = []
    righe = []
    if template_result.get("best_template"):
        righe.append(template_result["best_template"])
    righe.extend(template_result.get("alternatives") or [])
    for riga in righe:
        if not isinstance(riga, dict):
            continue
        candidati.append(
            ProcedureTemplateCandidate(
                template_id=str(riga.get("id") or riga.get("template_id") or ""),
                titolo=str(riga.get("titolo") or riga.get("title") or ""),
                score=int(riga.get("match_score") or riga.get("score") or 0),
                canale=str(riga.get("canale_telematico") or riga.get("canale") or ""),
                area=str(riga.get("area") or ""),
                motivi=[str(m) for m in (riga.get("match_reasons") or riga.get("motivi") or [])][:6],
            )
        )
    return [c for c in candidati if c.template_id]


def _normalizza_lifecycle_steps(steps: list[Any]) -> list[dict[str, Any]]:
    """Accetta sia step-dict sia step-type stringa (build_lifecycle_steps_for_xsd)."""
    try:
        from pct.procedure_lifecycle_templates import STEP_LABELS
    except Exception:
        STEP_LABELS = {}
    normalizzati: list[dict[str, Any]] = []
    for step in steps or []:
        if isinstance(step, dict):
            normalizzati.append(step)
        else:
            chiave = str(step or "").strip()
            if chiave:
                normalizzati.append({"step_type": chiave, "label": str(STEP_LABELS.get(chiave, chiave))})
    return normalizzati


def _termini_da_lifecycle(steps: list[dict[str, Any]]) -> list[dict[str, str]]:
    termini: list[dict[str, str]] = []
    for step in steps or []:
        scadenza = step.get("deadline_rule") or step.get("termine") or step.get("deadline")
        if not scadenza:
            continue
        termini.append(
            {
                "termine": str(scadenza),
                "descrizione": str(step.get("label") or step.get("step_label") or ""),
                "base_normativa": str(step.get("legal_basis") or step.get("base_normativa") or ""),
                "fonte_id": str(step.get("source_id") or ""),
            }
        )
    return termini


def fuse_card(
    request: ProcedureCompletionRequest,
    plan: SourcePlan,
    *,
    template_result: Optional[dict[str, Any]] = None,
    lifecycle_steps: Optional[list[dict[str, Any]]] = None,
    knowledge_card: Optional[dict[str, Any]] = None,
    tenant_id: str = "",
    run_id: str = "",
) -> ProcedureCompletionCard:
    entry = plan.catalog_entry or {}
    catalogo_presente = bool(entry)

    card = ProcedureCompletionCard(
        run_id=run_id,
        tenant_id=tenant_id,
        codice=request.codice,
        denominazione=request.denominazione or str(entry.get("descrizione") or ""),
        categoria=request.categoria or str(entry.get("area_label") or entry.get("area") or ""),
        rito=request.rito,
        competenza=request.competenza,
        xsd_code=request.codice if catalogo_presente else "",
        last_checked_at=now_iso(),
        review_avvocato=empty_review(),
    )

    gaps: list[ProcedureCompletionGap] = list(plan.gaps)

    # Fonte catalogo + uffici destinatari (dal layer tecnico, mai dal client).
    if catalogo_presente:
        card.fonte_catalogo = {
            "catalogo": "Codici oggetto PST",
            "codice": str(entry.get("codice") or request.codice),
            "descrizione": str(entry.get("descrizione") or ""),
            "area": str(entry.get("area_label") or entry.get("area") or ""),
            "famiglia": str(entry.get("parent_label") or ""),
            "file_fonte": str(entry.get("file_fonte") or ""),
        }
        registri = entry.get("registri")
        if registri:
            if isinstance(registri, str):
                registri = [parte.strip() for parte in registri.split(",") if parte.strip()]
            card.uffici_destinatari = [str(item) for item in registri][:10]
        if not card.uffici_destinatari and request.competenza:
            card.uffici_destinatari = [request.competenza]
        card.firma_digitale = dict(_FIRMA_PCT)
        card.deposito_telematico = dict(_DEPOSITO_PCT)
        card.ricevute_attese = list(_RICEVUTE_PCT)
        card.notifiche = dict(_NOTIFICHE_BASE)
        card.prova_notifica = dict(_PROVA_NOTIFICA_BASE)
        card.status = "draft"
    else:
        card.status = "needs_review"
        if request.competenza:
            card.uffici_destinatari = [request.competenza]

    # Fonti e citazioni dal piano (solo passaggi realmente recuperati).
    card.sources = [src.to_dict() for src in plan.sources]
    card.source_hashes = sorted({src.source_hash for src in plan.sources if src.source_hash})
    citazioni = references_from_rows(plan.evidence_rows)
    card.citations = [cit.to_dict() for cit in citazioni]
    card.articoli_rilevanti = sorted({cit.riferimento for cit in citazioni})
    card.sintesi_articoli = [
        {
            "riferimento": cit.riferimento,
            "sintesi": summarize_passage(cit.snippet, max_chars=280),
            "fonte_url": cit.url,
        }
        for cit in citazioni[:30]
        if cit.snippet
    ]
    card.fonte_normativa = [
        {
            "titolo": src.title,
            "url": src.url,
            "autorita": src.authority,
            "trust_class": src.trust_class,
            "policy": src.copyright_policy,
        }
        for src in plan.sources
        if src.source_type == "official"
    ]

    # Condizioni di procedibilita' / guida pratica dalla knowledge card (se esiste).
    if isinstance(knowledge_card, dict) and knowledge_card:
        contenuto = knowledge_card.get("card_json") if isinstance(knowledge_card.get("card_json"), dict) else knowledge_card
        condizioni = contenuto.get("condizioni_procedibilita")
        if isinstance(condizioni, list):
            card.condizioni_procedibilita = [
                item if isinstance(item, dict) else {"condizione": str(item), "fonte_id": ""}
                for item in condizioni
            ]
        guida = contenuto.get("presupposti") or contenuto.get("guida_pratica")
        if isinstance(guida, list):
            card.guida_pratica = [str(item) for item in guida][:20]
        rischi = contenuto.get("rischi") or contenuto.get("errori_ricorrenti")
        if isinstance(rischi, list):
            card.rischi_operativi = [str(item) for item in rischi][:15]
        allegati = contenuto.get("allegati") or contenuto.get("documenti_necessari")
        if isinstance(allegati, list):
            card.allegati_obbligatori = [
                item if isinstance(item, dict) else {"allegato": str(item), "fonte_id": "", "evidenza": "knowledge_card"}
                for item in allegati
            ]
    if not card.guida_pratica and catalogo_presente:
        gaps.append(
            ProcedureCompletionGap(
                codice_gap="guida_pratica_mancante",
                descrizione="Guida pratica non ancora censita per questa procedura.",
                severita="warning",
                azione_suggerita="Completare la knowledge card nella Procedure Lifecycle Knowledge Pipeline.",
            )
        )
    if not card.condizioni_procedibilita and catalogo_presente:
        gaps.append(
            ProcedureCompletionGap(
                codice_gap="condizioni_procedibilita_da_verificare",
                descrizione="Condizioni di procedibilita' non censite da fonte: verifica in revisione.",
                severita="warning",
            )
        )

    # Adempimenti fiscali: solo da fonte fiscale (mai dedotti).
    card.adempimenti_fiscali = [
        {
            "adempimento": summarize_passage(str(row.get("extracted_principle") or row.get("title") or ""), max_chars=200),
            "fonte": str(row.get("source_url") or row.get("url") or ""),
            "fonte_titolo": str(row.get("source_title") or row.get("title") or ""),
        }
        for row in plan.fiscal_rows
        if row.get("source_url") or row.get("url")
    ]

    # Lifecycle e checklist dal layer procedurale.
    lifecycle_steps = _normalizza_lifecycle_steps(lifecycle_steps or [])
    card.lifecycle_steps = [
        {
            "ordine": idx + 1,
            "step": str(step.get("step_type") or step.get("type") or ""),
            "label": str(step.get("label") or step.get("step_label") or ""),
            "note": summarize_passage(str(step.get("notes") or step.get("note") or ""), max_chars=180),
        }
        for idx, step in enumerate(lifecycle_steps or [])
    ][:30]
    card.checklist_operativa = [
        {"voce": item["label"] or item["step"], "completata": False, "ordine": item["ordine"]}
        for item in card.lifecycle_steps
        if item.get("label") or item.get("step")
    ]
    card.termini_processuali = _termini_da_lifecycle(lifecycle_steps or [])
    if not card.lifecycle_steps and catalogo_presente:
        gaps.append(
            ProcedureCompletionGap(
                codice_gap="lifecycle_non_generato",
                descrizione="Passi del ciclo di vita non generati per questa famiglia XSD.",
                severita="info",
            )
        )

    # Template atti: candidates + selezione (atto principale collegato o needs_review).
    candidati = _candidates_from_template_result(template_result)
    card.template_candidates = [cand.to_dict() for cand in candidati]
    selezionato = next((cand for cand in candidati if cand.template_id == request.template_code), None)
    if selezionato is None and candidati:
        selezionato = candidati[0]
    if selezionato is not None:
        card.template_selected = selezionato.to_dict()
        card.atto_principale = {
            "titolo": selezionato.titolo,
            "template_id": selezionato.template_id,
            "stato": "collegato_a_template",
        }
    else:
        card.atto_principale = {"titolo": "", "template_id": "", "stato": "needs_review"}
        gaps.append(
            ProcedureCompletionGap(
                codice_gap="template_mancante",
                descrizione="Nessun template atti collegabile a questa procedura.",
                severita="warning",
                azione_suggerita="Creare o collegare un template nel catalogo atti.",
            )
        )
        if card.status == "draft":
            card.status = "needs_review"

    # Avvertimenti obbligatori sempre presenti.
    card.avvertimenti_obbligatori = [AVVERTIMENTO_BOZZA, AVVERTIMENTO_NO_AUTOMAZIONE]
    if not card.fonte_normativa:
        card.avvertimenti_obbligatori.append(
            "Nessuna fonte primaria collegata: il contenuto tecnico deriva dal solo catalogo ministeriale."
        )

    card.gap_evidenza = [gap.to_dict() for gap in gaps]
    blocking = any(gap.severita == "blocking" for gap in gaps)
    if blocking:
        card.status = "needs_review"
        card.risk_level = "high"
    elif card.status == "needs_review":
        card.risk_level = "medium"
    else:
        card.risk_level = "medium" if card.gap_evidenza else "low"
    card.confidence = assign_confidence(card)
    return card


__all__ = ["fuse_card", "AVVERTIMENTO_BOZZA", "AVVERTIMENTO_NO_AUTOMAZIONE"]
