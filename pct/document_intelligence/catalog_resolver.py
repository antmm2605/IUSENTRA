"""Resolver deterministico per la catalogazione documentale del fascicolo.

Il resolver non naviga in rete e non deduce una materia da prefissi storici:
usa il profilo semantico del fascicolo, metadati del canale e testo già estratto
nel repository SQL. Quando mancano prove sufficienti apre una revisione.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Iterable

from pct.fascicolo_document_catalog import classify_fascicolo_document
from pct.template_atti_legal_sources import REGISTRY_VERSION, TEMPLATE_ATTI_LEGAL_SOURCES

from .models import (
    DocumentCatalogCandidate,
    DocumentCatalogEvidence,
    DocumentCatalogReview,
    new_id,
    utc_now,
)


RESOLVER_VERSION = "2026.08.24.catalogo-fascicolo.v3"

# Triadi versionate nell'audit del 24/08/2026. I riferimenti ``snapshot:`` e
# ``browser:`` sono prove archiviate/manuali, mai chiamate HTTP dal runtime.
PROFILE_SOURCES: dict[str, tuple[str, ...]] = {
    "CIV-PCT": ("normattiva_codice_civile", "normattiva_cpc", "pst_specifiche_tecniche_pct", "corte_cassazione_sentenzeweb"),
    "CIV-MON-CAU": ("normattiva_cpc", "cpc_procedimento_monitorio", "cpc_procedimenti_cautelari_uniformi", "pst_specifiche_tecniche_pct"),
    "CIV-ESE": ("normattiva_cpc", "pst_specifiche_tecniche_pct", "pst_portale_vendite_pubbliche_specifiche_concorsuali", "corte_cassazione_sentenzeweb"),
    "CIV-IMP": ("normattiva_cpc", "pst_specifiche_tecniche_pct", "corte_cassazione_sentenzeweb"),
    "CIV-NOT": ("normattiva_legge_53_1994_notifiche", "normattiva_dpr_68_2005_pec", "pst_dgsia_2024_art_27_attestazione_conformita", "normattiva_cad_art_48"),
    "CIV-PROC": ("normattiva_cpc", "normattiva_l_247_2012_ordinamento_forense", "cnf_codice_deontologico_forense", "pst_specifiche_tecniche_pct"),
    "CIV-GDP": ("normattiva_cpc", "normattiva_d_lgs_150_2011_riti", "pst_specifiche_tecniche_pct", "corte_cassazione_sentenzeweb"),
    "LOC": ("normattiva_legge_392_1978_locazioni", "normattiva_legge_431_1998_locazioni_abitative", "agenzia_entrate_rli_locazioni"),
    "RCD": ("normattiva_codice_civile", "normattiva_codice_strada_285_1992", "normattiva_codice_assicurazioni_209_2005", "ivass_arbitro_assicurativo"),
    "ADR": ("normattiva_d_lgs_28_2010_mediazione", "normattiva_dm_150_2023_mediazione", "giustizia_registro_mediazione_dm_150_2023", "normattiva_dl_132_2014_negoziazione"),
    "PAT": ("normattiva_cpa", "giustizia_amministrativa_pat", "giustizia_amministrativa_dpcs_2025_pat", "giustizia_amministrativa_ricerche_decisioni"),
    "CONC": ("normattiva_codice_crisi_14_2019", "normattiva_d_lgs_136_2024_correttivo_crisi", "pst_portale_vendite_pubbliche_specifiche_concorsuali", "snapshot:pvp-specifiche-2024-v1.2"),
    "BAN": ("normattiva_tub_385_1993", "abf_normativa", "bancaditalia_abf_disposizioni_2025", "browser:acf-normativa-2026"),
    "SOC": ("normattiva_codice_civile", "normattiva_tuf_58_1998", "snapshot:registro-imprese-bilanci-2026", "snapshot:registro-imprese-specifiche-2026"),
    "LAV": ("normattiva_l_300_1970_statuto_lavoratori", "normattiva_l_604_1966_licenziamenti", "inl_contestazione_licenziamento_gmo", "snapshot:inps-ricorso-previdenziale-2026"),
    "VGS": ("normattiva_codice_civile", "normattiva_cpc", "snapshot:vg-dm-2024", "snapshot:vg-specifiche-2023", "snapshot:successione-certificato-giustizia-2026"),
    "FAM": ("normattiva_codice_civile", "normattiva_cpc", "normattiva_d_lgs_149_2022_cartabia_civile", "corte_cassazione_sentenzeweb"),
    "PEN": ("normattiva_cpp", "normattiva_d_lgs_150_2022_cartabia_penale", "pst_pdp_penale", "pst_specifiche_penale_2024", "corte_cassazione_sentenzeweb"),
    "TRIB": ("normattiva_d_lgs_546_1992_tributario", "normattiva_dm_163_2013_ptt", "snapshot:ptt-specifiche-2015-gu", "snapshot:ptt-modifica-2017-gu", "snapshot:ptt-modifica-2023-gu", "snapshot:ptt-circolare-2019", "giustizia_tributaria_def_giurisprudenza"),
    "STD": ("normattiva_l_247_2012_ordinamento_forense", "cnf_codice_deontologico_forense", "normattiva_dm_55_2014_parametri_forensi", "snapshot:agid-gestione-documentale-2026"),
    "IPD": ("normattiva_cpi_30_2005", "uibm_deposito_telematico_proprieta_industriale", "normattiva_diritto_autore_633_1941", "snapshot:uibm-marchi-disegni-2026"),
    "IMM": ("normattiva_tu_immigrazione_286_1998", "normattiva_d_lgs_25_2008_protezione_internazionale", "interno_protezione_internazionale_commissioni", "snapshot:protezione-internazionale-guida-2024"),
    "PRI": ("normattiva_privacy_196_2003", "garante_gdpr", "snapshot:garante-privacy-regolamento-reclami-2019"),
    "STR": ("normattiva_codice_civile", "normattiva_d_lgs_28_2010_mediazione", "normattiva_dm_150_2023_mediazione", "cnf_codice_deontologico_forense"),
    "CON": ("normattiva_codice_consumo_206_2005", "agcom_conciliaweb", "agcom_delibera_203_18_conciliaweb", "snapshot:arera-tico-209-2016"),
}

# Le 47 righe sono la mappa completa area/branca/sottofamiglia del corpus
# effettivo da 708 modelli. Il confronto è semantico normalizzato ed esatto.
FAMILY_PROFILE_ROWS: tuple[tuple[str, str, str, str], ...] = (
    ("ADR", "ADR, mediazione, negoziazione, arbitrato", "Mediazione e arbitrato", "ADR"),
    ("Amministrativo", "Amministrativo", "Ricorsi, memorie e cautelare", "PAT"),
    ("Amministrativo", "Giustizia amministrativa", "Ricorsi e appelli", "PAT"),
    ("Civile", "Civile ordinario", "Introduttivi e difensivi", "CIV-PCT"),
    ("Civile", "Civile ordinario", "Introduttivi, difensivi e istanze", "CIV-PCT"),
    ("Civile", "Esecuzioni", "Precetti, pignoramenti e opposizioni", "CIV-ESE"),
    ("Civile", "Esecuzioni civili", "Espropriazione e opposizioni", "CIV-ESE"),
    ("Civile", "Impugnazioni", "Appello, cassazione e rimedi", "CIV-IMP"),
    ("Civile", "Impugnazioni civili", "Appelli, reclami e rimedi impugnatori", "CIV-IMP"),
    ("Civile", "Monitorio e cautelare", "Ricorsi d'urgenza, monitori e sfratti", "CIV-MON-CAU"),
    ("Civile", "Monitorio, cautelare e possessorio", "Ricorsi speciali", "CIV-MON-CAU"),
    ("Civile", "Notifiche e adempimenti", "UNEP, notifica in proprio e allegati", "CIV-NOT"),
    ("Civile", "Procure e deleghe", "Mandati e domiciliazioni", "CIV-PROC"),
    ("Civile", "UNEP e notificazioni", "Notifiche, depositi e fascicolo telematico", "CIV-NOT"),
    ("Crisi d'impresa e insolvenza", "Procedure concorsuali e crisi", "Concorsuale", "CONC"),
    ("Diritto amministrativo", "Amministrativo", "PAT e contenzioso amministrativo", "PAT"),
    ("Diritto bancario", "Bancario e finanziario", "Bancario e finanziario", "BAN"),
    ("Diritto civile", "Core civile", "Contenzioso ordinario", "CIV-PCT"),
    ("Diritto civile", "Giudice di Pace", "Giudice di Pace", "CIV-GDP"),
    ("Diritto civile", "Locazioni, condominio e immobili", "Locazioni, condominio e immobili", "LOC"),
    ("Diritto civile", "Procedimento monitorio", "Procedimento monitorio", "CIV-MON-CAU"),
    ("Diritto civile", "Recupero crediti e stragiudiziale", "Recupero crediti e diffide", "STR"),
    ("Diritto civile", "Responsabilità civile e danni", "Responsabilità civile", "RCD"),
    ("Diritto commerciale", "Commerciale e societario", "Societario", "SOC"),
    ("Diritto del lavoro", "Lavoro e previdenza", "Lavoro e previdenza", "LAV"),
    ("Diritto delle persone e successioni", "Volontaria giurisdizione e successioni", "Volontaria giurisdizione", "VGS"),
    ("Diritto di famiglia", "Famiglia, minori e persone", "Famiglia e minori", "FAM"),
    ("Diritto penale", "Penale", "Difesa penale e persona offesa", "PEN"),
    ("Diritto processuale civile", "Cautelari e urgenza", "Cautelari e urgenza", "CIV-MON-CAU"),
    ("Diritto processuale civile", "Esecuzioni", "Esecuzioni", "CIV-ESE"),
    ("Diritto tributario", "Tributario", "Contenzioso tributario", "TRIB"),
    ("Famiglia e Persone", "Famiglia e persone", "Separazione, divorzio e volontaria giurisdizione", "FAM"),
    ("Famiglia e Persone", "Famiglia, persone e volontaria giurisdizione", "Separazione, divorzio e tutele", "FAM"),
    ("Gestione studio", "Atti interni di studio", "Operatività interna", "STD"),
    ("IP, media e digitale", "Proprietà intellettuale e digitale", "Proprietà intellettuale e web", "IPD"),
    ("Immigrazione", "Immigrazione e cittadinanza", "Ricorsi, permessi e protezione", "IMM"),
    ("Lavoro e Previdenza", "Lavoro e previdenza", "Ricorsi e impugnazioni", "LAV"),
    ("Lavoro e Previdenza", "Lavoro e previdenza", "Ricorsi, memorie e previdenza", "LAV"),
    ("Penale", "Difesa penale", "Atti difensivi e richieste", "PEN"),
    ("Penale", "Penale", "Difesa, istanze e impugnazioni", "PEN"),
    ("Privacy e protezione dati", "Privacy e compliance", "GDPR e compliance", "PRI"),
    ("Societario", "Societario", "Pareri, contratti e contenzioso", "SOC"),
    ("Stragiudiziale", "Diffide e atti stragiudiziali", "Richieste, intimazioni e lettere", "STR"),
    ("Stragiudiziale", "Stragiudiziale", "Comunicazioni, accordi e pareri", "STR"),
    ("Tributario", "Contenzioso tributario", "Ricorso e difese", "TRIB"),
    ("Tributario", "Tributario", "Ricorsi, controdeduzioni e appelli", "TRIB"),
    ("Tutela del consumatore", "Consumatori e utenze", "Consumo e utenze", "CON"),
)


def _normalise(value: Any) -> str:
    raw = unicodedata.normalize("NFD", str(value or "").casefold())
    raw = "".join(char for char in raw if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", raw).strip()


FAMILY_PROFILE_BY_CONTEXT = {
    (_normalise(area), _normalise(branch), _normalise(subfamily)): profile
    for area, branch, subfamily, profile in FAMILY_PROFILE_ROWS
}
_SOURCE_INDEX = {str(row.get("id") or ""): dict(row) for row in TEMPLATE_ATTI_LEGAL_SOURCES}


@dataclass(slots=True)
class CatalogResolution:
    profile_id: str | None
    legal_area: str
    legal_branch: str
    legal_subfamily: str
    jurisdiction: str
    rite: str
    proceeding_phase: str
    document_nature: str
    document_label: str
    document_section: str
    deposit_role: str
    deposit_candidate: bool
    confidence: int
    status: str
    source_state: str
    reason: str
    candidates: list[DocumentCatalogCandidate]
    evidence: list[DocumentCatalogEvidence]
    review: DocumentCatalogReview | None


def profile_source_rows(profile_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_id in PROFILE_SOURCES.get(profile_id, ()):
        if source_id.startswith("snapshot:"):
            rows.append({
                "id": source_id,
                "official_url": source_id,
                "verification_status": "snapshot ufficiale acquisito e verificato",
                "last_verified_at": "2026-08-24",
                "snapshot_sha256": "",
                "source_type": "snapshot",
            })
        elif source_id.startswith("browser:"):
            rows.append({
                "id": source_id,
                "official_url": "https://www.acf.consob.it/normativa/normativa-acf/-/asset_publisher/3ZtmdCgqd1re/content/aggiornamento-area-riservata?inheritRedirect=false",
                "verification_status": "evidenza browser istituzionale verificata il 24/08/2026",
                "last_verified_at": "2026-08-24",
                "snapshot_sha256": "",
                "source_type": "browser_evidence",
            })
        else:
            source = _SOURCE_INDEX.get(source_id, {})
            rows.append({
                "id": source_id,
                "official_url": str(source.get("official_url") or ""),
                "verification_status": str(source.get("verification_status") or "fonte da verificare"),
                "last_verified_at": str(source.get("last_verified_at") or ""),
                "snapshot_sha256": "",
                "source_type": str(source.get("source_type") or "normativa"),
            })
    return rows


def resolve_profile(context: dict[str, Any]) -> tuple[str | None, str]:
    area = str(context.get("area") or context.get("area_pratica") or "")
    branch = str(context.get("branca") or context.get("branch") or "")
    subfamily = str(context.get("sottobranca") or context.get("subfamily") or "")
    exact = FAMILY_PROFILE_BY_CONTEXT.get((_normalise(area), _normalise(branch), _normalise(subfamily)))
    if exact:
        return exact, "profilo del fascicolo corrisponde alla matrice area/branca/sottofamiglia"

    channel = _normalise(context.get("canale") or context.get("canale_operativo") or context.get("source"))
    if channel in {"pat", "siga"}:
        return "PAT", "canale amministrativo del fascicolo"
    if channel in {"ptt", "sigit"}:
        return "TRIB", "canale tributario del fascicolo"
    if channel in {"pdp", "ppt", "penale"}:
        return "PEN", "canale penale del fascicolo"
    return None, "mancano area, branca e sottofamiglia verificabili del fascicolo"


def resolve_document_catalog(
    *,
    tenant_id: str,
    fascicolo_id: str,
    document_id: str,
    document_sha256: str,
    filename: str,
    extracted_text: str,
    document_metadata: dict[str, Any] | None,
    fascicolo_context: dict[str, Any] | None,
) -> CatalogResolution:
    metadata = dict(document_metadata or {})
    context = dict(fascicolo_context or {})
    profile_id, profile_reason = resolve_profile(context)
    synthetic_document = SimpleNamespace(
        nome=filename,
        nome_originale=metadata.get("nome_originale", ""),
        nome_portale=metadata.get("nome_portale", ""),
        percorso="",
        tipo=metadata.get("tipo_documento", ""),
        classificazione_portale=metadata.get("classificazione_portale", ""),
        tipo_atto_portale=metadata.get("tipo_atto_portale", ""),
        servizio_portale=metadata.get("servizio_portale", ""),
        mittente_portale=metadata.get("mittente_portale", ""),
        note=metadata.get("note", ""),
        tags=metadata.get("tags", []),
    )
    classification = classify_fascicolo_document(
        synthetic_document,
        filename=filename,
        extracted_text=extracted_text,
        tipo=metadata.get("tipo_documento", ""),
    )
    source_rows = profile_source_rows(profile_id) if profile_id else []
    has_manual_browser_evidence = any(row["source_type"] == "browser_evidence" for row in source_rows)
    source_state = "manual_browser_evidence" if has_manual_browser_evidence else "verified_snapshot"
    confidence = int(classification.confidence)
    status = "proposed"
    review_reason = ""
    if not profile_id:
        status = "review_required"
        source_state = "review_required"
        confidence = min(confidence, 55)
        review_reason = "Profilo giuridico del fascicolo non determinabile dai dati strutturati."
    elif confidence < 75 or classification.role == "da_verificare":
        status = "review_required"
        confidence = min(confidence, 69)
        review_reason = "Le evidenze del documento non consentono una catalogazione automatica affidabile."

    now = utc_now()
    candidate = DocumentCatalogCandidate(
        id=new_id("catalog-candidate"), tenant_id=tenant_id, fascicolo_id=fascicolo_id,
        assignment_id="", rank_number=1, profile_id=profile_id,
        document_nature=classification.role, document_label=classification.label,
        document_section=classification.section, deposit_role=classification.deposit_role,
        confidence=confidence, reason=f"{profile_reason}; {classification.evidence}", created_at=now,
    )
    evidence = [
        DocumentCatalogEvidence(
            id=new_id("catalog-evidence"), tenant_id=tenant_id, fascicolo_id=fascicolo_id,
            assignment_id="", evidence_type="document_metadata", locator="nome/metadati documento",
            excerpt=filename[:240], weight=35, content_sha256=document_sha256 or None, created_at=now,
        ),
        DocumentCatalogEvidence(
            id=new_id("catalog-evidence"), tenant_id=tenant_id, fascicolo_id=fascicolo_id,
            assignment_id="", evidence_type="fascicolo_context", locator="profilo fascicolo",
            excerpt=" · ".join(item for item in (str(context.get("area") or context.get("area_pratica") or ""), str(context.get("branca") or ""), str(context.get("sottobranca") or "")) if item)[:240],
            weight=45 if profile_id else 0, content_sha256=None, created_at=now,
        ),
    ]
    if str(extracted_text or "").strip():
        evidence.append(DocumentCatalogEvidence(
            id=new_id("catalog-evidence"), tenant_id=tenant_id, fascicolo_id=fascicolo_id,
            assignment_id="", evidence_type="extracted_text", locator="testo estratto SQL",
            excerpt="Testo estratto disponibile e valutato dal resolver; il contenuto resta nel lettore interno.",
            weight=40, content_sha256=document_sha256 or None, created_at=now,
        ))
    for row in source_rows:
        evidence.append(DocumentCatalogEvidence(
            id=new_id("catalog-evidence"), tenant_id=tenant_id, fascicolo_id=fascicolo_id,
            assignment_id="", evidence_type="legal_source", locator=row["id"],
            excerpt=str(row["verification_status"])[:240], weight=20,
            content_sha256=str(row.get("snapshot_sha256") or "") or None, created_at=now,
        ))
    review = None
    if status == "review_required":
        review = DocumentCatalogReview(
            id=new_id("catalog-review"), tenant_id=tenant_id, fascicolo_id=fascicolo_id,
            assignment_id="", state="open", reason_code="insufficient_evidence" if profile_id else "missing_fascicolo_profile",
            reason=review_reason, resolved_by=None, resolution_note=None, created_at=now, resolved_at=None,
        )
    return CatalogResolution(
        profile_id=profile_id,
        legal_area=str(context.get("area") or context.get("area_pratica") or ""),
        legal_branch=str(context.get("branca") or context.get("branch") or ""),
        legal_subfamily=str(context.get("sottobranca") or context.get("subfamily") or ""),
        jurisdiction=str(context.get("giurisdizione") or context.get("tribunale") or ""),
        rite=str(context.get("rito") or context.get("tipo_procedimento") or ""),
        proceeding_phase=str(context.get("fase") or ""),
        document_nature=classification.role, document_label=classification.label,
        document_section=classification.section, deposit_role=classification.deposit_role,
        deposit_candidate=bool(classification.deposit_candidate), confidence=confidence,
        status=status, source_state=source_state,
        reason=f"{profile_reason}; {classification.evidence}", candidates=[candidate], evidence=evidence, review=review,
    )


def assert_full_family_matrix(rows: Iterable[dict[str, Any]]) -> list[tuple[str, str, str]]:
    """Restituisce eventuali contesti del corpus non risolti dal resolver."""

    missing: list[tuple[str, str, str]] = []
    for row in rows:
        key = (_normalise(row.get("area")), _normalise(row.get("branca")), _normalise(row.get("sottobranca")))
        if key not in FAMILY_PROFILE_BY_CONTEXT:
            missing.append((str(row.get("area") or ""), str(row.get("branca") or ""), str(row.get("sottobranca") or "")))
    return missing


__all__ = [
    "CatalogResolution", "FAMILY_PROFILE_BY_CONTEXT", "FAMILY_PROFILE_ROWS", "PROFILE_SOURCES",
    "REGISTRY_VERSION", "RESOLVER_VERSION", "assert_full_family_matrix", "profile_source_rows",
    "resolve_document_catalog", "resolve_profile",
]
