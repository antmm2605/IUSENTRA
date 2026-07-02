"""Sentenza Economic Control V1 — motore di controllo economico-probatorio.

Prima di alimentare qualunque contesto economico, il motore **dimostra** che la
sentenza appartiene al fascicolo (uguaglianza RG + punteggio cliente/ufficio),
poi estrae il dato economico (spese liquidate, distrazione ex art. 93 c.p.c.,
contributo unificato) e propone azioni **solo da confermare**.

Modulo puro e deterministico: nessuna dipendenza dal repository o da Flask, così
è testabile in isolamento. Riusa gli estrattori esistenti (`legal_ocr.ner_legal`,
`legal_regex.rules`) e lo scorer di identità del presidio PEC (`pct.email_client`),
senza reimplementarli.

Fonti: art. 91, 93, 133, 325 c.p.c.; D.M. 55/2014; D.P.R. 115/2002 (artt. 9, 13,
14, 15, 16, 248, 82-85). Le keyword operative vivono nel ruleset versionato
`pct/data/economic_legal_rules_v2026_07.json`.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from legal_ocr.ner_legal import extract_numero_ruolo, extract_uffici
from legal_regex.rules import validate_regex_pack
from pct.email_client import _normalizza_testo_email_match, _tokenizza_email_match


DEFAULT_RULESET_PATH = Path(__file__).with_name("data") / "economic_legal_rules_v2026_07.json"
_RULESET_CACHE: dict[str, dict[str, Any]] = {}


def load_ruleset(path: str | Path | None = None) -> dict[str, Any]:
    """Carica il ruleset civile versionato (cache per path)."""

    resolved = str(path or DEFAULT_RULESET_PATH)
    cached = _RULESET_CACHE.get(resolved)
    if cached is None:
        cached = json.loads(Path(resolved).read_text(encoding="utf-8"))
        _RULESET_CACHE[resolved] = cached
    return cached


# --------------------------------------------------------------------------- #
# Dataclass                                                                     #
# --------------------------------------------------------------------------- #


@dataclass
class SentenzaIdentityMatch:
    fascicolo_id: str = ""
    documento_id: str = ""
    rg_fascicolo: str = ""
    rg_rilevato: str = ""
    anno_rg_fascicolo: str = ""
    anno_rg_rilevato: str = ""
    cliente_fascicolo: str = ""
    cliente_rilevato: str = ""
    tribunale_fascicolo: str = ""
    tribunale_rilevato: str = ""
    controparte_fascicolo: str = ""
    controparte_rilevata: str = ""
    rg_match: bool = False
    rg_score: float = 0.0
    cliente_score: float = 0.0
    tribunale_score: float = 0.0
    controparte_score: float = 0.0
    overall_score: float = 0.0
    safe_to_attach: bool = False
    human_review_required: bool = True
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SpeseLiquidate:
    presente: bool = False
    testo_capo_spese: str = ""
    condanna_spese: bool = False
    spese_compensate: bool = False
    compensazione_parziale: bool = False
    distrazione_spese: bool = False
    antistatario: bool = False
    gratuito_patrocinio: bool = False
    beneficiario_credito: str = "incerto"  # cliente | avvocato | erario | incerto
    pagatore: str = "incerto"              # controparte | cliente | erario | incerto
    importi_rilevati: list[float] = field(default_factory=list)
    totale_stimato: float | None = None
    spese_generali_15: float | None = None
    cpa: float | None = None
    iva: float | None = None
    ritenuta: float | None = None
    human_review_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SentenzaEconomicExtraction:
    tipo_provvedimento: str = "incerto"  # sentenza | ordinanza | decreto | incerto
    esito: str = "incerto"               # favorevole | sfavorevole | parziale | incerto
    rg_numero: str = ""
    rg_anno: str = ""
    ufficio: str = ""
    provvisoria_esecutivita: bool = False
    titolo_esecutivo: bool = False
    spese_liquidate: SpeseLiquidate = field(default_factory=SpeseLiquidate)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


@dataclass
class ContributoUnificatoAudit:
    status: str = "incerto"  # pagato|non_dovuto|esente|prenotato_a_debito|mancante|insufficiente|da_integrare|incerto
    importo_pagato: float | None = None
    importo_atteso: float | None = None
    differenza: float | None = None
    iuv: str = ""
    ricevuta_id: str = ""
    data_pagamento: str = ""
    pagatore: str = ""
    fonte_prova: str = "nessuna"
    evidence_document_id: str = ""
    evidence_hash_sha256: str = ""
    invito_pagamento_rilevato: bool = False
    termine_deposito_ricevuta: str = ""
    human_review_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EconomicAction:
    type: str
    label: str
    priority: str = "P2"
    amount: float | None = None
    beneficiary_type: str = ""
    requires_confirmation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SentenzaEconomicAudit:
    fascicolo_id: str = ""
    documento_id: str = ""
    fonte: str = ""
    document_hash_sha256: str = ""
    message_id: str = ""
    match: SentenzaIdentityMatch = field(default_factory=SentenzaIdentityMatch)
    sentenza: SentenzaEconomicExtraction = field(default_factory=SentenzaEconomicExtraction)
    contributo_unificato: ContributoUnificatoAudit = field(default_factory=ContributoUnificatoAudit)
    azioni: list[EconomicAction] = field(default_factory=list)
    safe_to_attach: bool = False
    human_review_required: bool = True
    status: str = "to_review"
    ruleset_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


# --------------------------------------------------------------------------- #
# Helper testo                                                                  #
# --------------------------------------------------------------------------- #


def _normalize(value: str) -> str:
    return _normalizza_testo_email_match(value)


def _contains_any(text_norm: str, keywords: list[str]) -> bool:
    return any(_normalize(kw) in text_norm for kw in keywords if kw)


def _parse_importo_it(value: str) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    raw = raw.replace(".", "").replace(",", ".")
    try:
        return round(float(raw), 2)
    except ValueError:
        return None


def _importi_rilevati(text: str) -> list[float]:
    matches = validate_regex_pack(text).get("matches", {}).get("importi", [])
    out: list[float] = []
    for raw in matches:
        parsed = _parse_importo_it(raw)
        if parsed is not None:
            out.append(parsed)
    return out


# --------------------------------------------------------------------------- #
# Fase 2 — verifica identità (RG + cliente + ufficio)                           #
# --------------------------------------------------------------------------- #


def _norm_rg_numero(value: str) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits.lstrip("0") or ("0" if digits else "")


def build_identity_match(fascicolo: Any, testo: str, *, documento_id: str = "", ruleset: dict[str, Any] | None = None) -> SentenzaIdentityMatch:
    """Confronta la sentenza col fascicolo. RG = uguaglianza esatta (regola forte)."""

    rules = ruleset or load_ruleset()
    soglia_doc = float(rules.get("match", {}).get("soglia_documento", 0.75))
    soglia_cliente = float(rules.get("match", {}).get("soglia_cliente", 0.30))

    testo_norm = _normalize(testo)
    tokens = _tokenizza_email_match(testo)

    rg_fasc = _norm_rg_numero(getattr(fascicolo, "numero_rg", ""))
    anno_fasc = str(getattr(fascicolo, "anno_rg", "") or "").strip()
    ruoli = extract_numero_ruolo(testo)
    rg_ril, anno_ril = "", ""
    rg_match = False
    for ruolo in ruoli:
        num = _norm_rg_numero(ruolo.get("numero", ""))
        anno = str(ruolo.get("anno", "") or "").strip()
        if not rg_ril:
            rg_ril, anno_ril = num, anno
        if rg_fasc and num == rg_fasc and anno_fasc and (anno == anno_fasc or anno[-2:] == anno_fasc[-2:]):
            rg_ril, anno_ril = num, anno
            rg_match = True
            break

    uffici = extract_uffici(testo)
    match = SentenzaIdentityMatch(
        fascicolo_id=str(getattr(fascicolo, "id", "") or ""),
        documento_id=str(documento_id or ""),
        rg_fascicolo=rg_fasc,
        rg_rilevato=rg_ril,
        anno_rg_fascicolo=anno_fasc,
        anno_rg_rilevato=anno_ril,
        cliente_fascicolo=str(getattr(fascicolo, "nome_cliente", "") or ""),
        tribunale_fascicolo=str(getattr(fascicolo, "tribunale", "") or ""),
        controparte_fascicolo=str(getattr(fascicolo, "controparte", "") or ""),
        tribunale_rilevato=uffici[0] if uffici else "",
        rg_match=rg_match,
        rg_score=1.0 if rg_match else 0.0,
    )

    # Punteggio cliente (riuso pesi del presidio PEC: substring + overlap token).
    nome = match.cliente_fascicolo.strip()
    cliente_points = 0
    if nome:
        if _normalize(nome) and _normalize(nome) in testo_norm:
            cliente_points += 55
            match.cliente_rilevato = nome
        overlap = _tokenizza_email_match(nome) & tokens
        if len(overlap) >= 2:
            cliente_points += 35
        elif len(overlap) == 1:
            cliente_points += 15
    match.cliente_score = round(min(1.0, cliente_points / 90.0), 2)

    controparte = match.controparte_fascicolo.strip()
    if controparte:
        overlap_cp = _tokenizza_email_match(controparte) & tokens
        match.controparte_score = 1.0 if len(overlap_cp) >= 2 else (0.5 if len(overlap_cp) == 1 else 0.0)
        if overlap_cp:
            match.controparte_rilevata = controparte

    tribunale = match.tribunale_fascicolo.strip()
    if tribunale:
        overlap_tr = _tokenizza_email_match(tribunale) & tokens
        match.tribunale_score = 1.0 if overlap_tr else 0.0

    match.overall_score = round(
        0.5 * match.rg_score
        + 0.25 * match.cliente_score
        + 0.15 * match.tribunale_score
        + 0.10 * match.controparte_score,
        2,
    )

    # Regola forte: RG diverso => non alimentare, revisione umana (regola #1).
    match.safe_to_attach = bool(
        match.rg_match and match.cliente_score >= soglia_cliente and match.overall_score >= soglia_doc
    )
    match.human_review_required = not (
        match.rg_match and match.overall_score >= 0.90 and match.cliente_score >= 0.60
    )

    if not match.rg_match:
        if rg_fasc and rg_ril:
            match.issues.append(f"RG rilevato {rg_ril}/{anno_ril or '?'} diverso dal fascicolo {rg_fasc}/{anno_fasc or '?'}.")
        elif not rg_ril:
            match.issues.append("Numero di ruolo generale non rilevato nel testo del provvedimento.")
        else:
            match.issues.append("RG del fascicolo mancante: impossibile riconciliare.")
    if nome and match.cliente_score < soglia_cliente:
        match.issues.append("Nome cliente non riscontrato con sufficiente confidenza nel testo.")
    return match


# --------------------------------------------------------------------------- #
# Fase 3 — lettura economica                                                    #
# --------------------------------------------------------------------------- #


def extract_economics(testo: str, *, ruleset: dict[str, Any] | None = None) -> SentenzaEconomicExtraction:
    rules = ruleset or load_ruleset()
    text_norm = _normalize(testo)
    spese_rules = rules.get("spese", {})

    provv = rules.get("provvedimento", {})
    tipo = "incerto"
    if _contains_any(text_norm, provv.get("sentenza_keywords", [])):
        tipo = "sentenza"
    elif _contains_any(text_norm, provv.get("ordinanza_keywords", [])):
        tipo = "ordinanza"
    elif _contains_any(text_norm, provv.get("decreto_keywords", [])):
        tipo = "decreto"

    esito_rules = rules.get("esito", {})
    esito = "incerto"
    if _contains_any(text_norm, esito_rules.get("parziale_keywords", [])):
        esito = "parziale"
    elif _contains_any(text_norm, esito_rules.get("favorevole_keywords", [])):
        esito = "favorevole"
    elif _contains_any(text_norm, esito_rules.get("sfavorevole_keywords", [])):
        esito = "sfavorevole"

    condanna = _contains_any(text_norm, spese_rules.get("condanna_keywords", []))
    compensate = _contains_any(text_norm, spese_rules.get("compensazione_keywords", []))
    compensate_parziale = _contains_any(text_norm, spese_rules.get("compensazione_parziale_keywords", []))
    distrazione = _contains_any(text_norm, spese_rules.get("distrazione_keywords", []))
    gratuito = _contains_any(text_norm, spese_rules.get("gratuito_patrocinio_keywords", []))

    # Beneficiario del credito: mai "avvocato" senza distrazione (regola #2).
    if gratuito:
        beneficiario = "erario"
        pagatore = "erario"
    elif distrazione:
        beneficiario = "avvocato"
        pagatore = "controparte"
    elif compensate and not compensate_parziale:
        beneficiario = "incerto"
        pagatore = "incerto"
    elif condanna:
        beneficiario = "cliente"
        pagatore = "controparte"
    else:
        beneficiario = "incerto"
        pagatore = "incerto"

    importi = _importi_rilevati(testo)
    spese = SpeseLiquidate(
        presente=bool(condanna or compensate or distrazione or gratuito),
        condanna_spese=condanna,
        spese_compensate=compensate,
        compensazione_parziale=compensate_parziale,
        distrazione_spese=distrazione,
        antistatario=distrazione,
        gratuito_patrocinio=gratuito,
        beneficiario_credito=beneficiario,
        pagatore=pagatore,
        importi_rilevati=importi,
        totale_stimato=max(importi) if importi else None,
        human_review_required=True,  # gli importi sono sempre "stimati e da confermare" (regola #4)
    )

    esec = rules.get("esecutivita", {})
    return SentenzaEconomicExtraction(
        tipo_provvedimento=tipo,
        esito=esito,
        provvisoria_esecutivita=_contains_any(text_norm, esec.get("provvisoria_esecutivita_keywords", [])),
        titolo_esecutivo=_contains_any(text_norm, esec.get("titolo_esecutivo_keywords", [])),
        spese_liquidate=spese,
    )


# --------------------------------------------------------------------------- #
# Fase 4 — contributo unificato                                                 #
# --------------------------------------------------------------------------- #


def _contributo_atteso(valore_causa: float, cu_tiers: list[tuple[float, float]] | None) -> float | None:
    if not cu_tiers or valore_causa <= 0:
        return None
    for limit, amount in sorted(cu_tiers, key=lambda t: t[0]):
        if valore_causa <= limit:
            return float(amount)
    return float(cu_tiers[-1][1]) if cu_tiers else None


def assess_contributo_unificato(
    testo: str,
    *,
    valore_causa: float = 0.0,
    cu_tiers: list[tuple[float, float]] | None = None,
    evidence: dict[str, Any] | None = None,
    ruleset: dict[str, Any] | None = None,
) -> ContributoUnificatoAudit:
    rules = ruleset or load_ruleset()
    cu_rules = rules.get("contributo_unificato", {})
    text_norm = _normalize(testo)
    evidence = dict(evidence or {})

    invito = _contains_any(text_norm, cu_rules.get("invito_keywords", []))
    importo_pagato = evidence.get("importo_pagato")
    iuv = str(evidence.get("iuv", "") or "")
    data_pagamento = str(evidence.get("data_pagamento", "") or "")
    # rule #5: "pagato" mai dal solo nome file: serve prova (importo + IUV/data).
    corroborato = bool(importo_pagato and (iuv or data_pagamento))

    if _contains_any(text_norm, cu_rules.get("prenotato_debito_keywords", [])):
        status = "prenotato_a_debito"
    elif _contains_any(text_norm, cu_rules.get("esente_keywords", [])):
        status = "esente"
    elif _contains_any(text_norm, cu_rules.get("insufficiente_keywords", [])):
        status = "insufficiente"
    elif invito:
        status = "da_integrare"
    elif _contains_any(text_norm, cu_rules.get("pagato_keywords", [])):
        status = "pagato" if corroborato else "incerto"
    else:
        status = "incerto"

    atteso = _contributo_atteso(float(valore_causa or 0.0), cu_tiers)
    differenza = None
    if importo_pagato is not None and atteso is not None:
        differenza = round(float(importo_pagato) - float(atteso), 2)

    # rule #9: mai chiudere senza ricevuta o stato esente/prenotato a debito.
    human_review = status not in {"esente", "prenotato_a_debito"} and not (status == "pagato" and corroborato)

    return ContributoUnificatoAudit(
        status=status,
        importo_pagato=float(importo_pagato) if importo_pagato is not None else None,
        importo_atteso=atteso,
        differenza=differenza,
        iuv=iuv,
        data_pagamento=data_pagamento,
        fonte_prova=str(evidence.get("fonte_prova", "") or ("ricevuta_pagamento" if corroborato else "nessuna")),
        evidence_document_id=str(evidence.get("evidence_document_id", "") or ""),
        evidence_hash_sha256=str(evidence.get("evidence_hash_sha256", "") or ""),
        invito_pagamento_rilevato=invito,
        human_review_required=human_review,
    )


# --------------------------------------------------------------------------- #
# Orchestrazione + azioni proposte (mai definitive: regola #4)                  #
# --------------------------------------------------------------------------- #


def build_audit(
    *,
    fascicolo: Any,
    testo: str,
    fonte: str = "FASCICOLO",
    documento_id: str = "",
    document_hash_sha256: str = "",
    message_id: str = "",
    valore_causa: float = 0.0,
    cu_tiers: list[tuple[float, float]] | None = None,
    cu_evidence: dict[str, Any] | None = None,
    ruleset: dict[str, Any] | None = None,
) -> SentenzaEconomicAudit:
    rules = ruleset or load_ruleset()
    match = build_identity_match(fascicolo, testo, documento_id=documento_id, ruleset=rules)
    sentenza = extract_economics(testo, ruleset=rules)
    cu = assess_contributo_unificato(
        testo, valore_causa=valore_causa, cu_tiers=cu_tiers, evidence=cu_evidence, ruleset=rules
    )

    azioni: list[EconomicAction] = []

    if not match.rg_match:
        # Regola #1: RG diverso => non alimentare il contesto economico.
        azioni.append(EconomicAction(
            type="verifica_riconciliazione",
            label="Documento non riconciliato al fascicolo: verifica RG/cliente prima di ogni azione economica.",
            priority="P0",
        ))
        status = "needs_reconciliation"
    else:
        spese = sentenza.spese_liquidate
        importo = spese.totale_stimato
        if spese.beneficiario_credito == "avvocato" and spese.distrazione_spese:
            azioni.append(EconomicAction(
                type="apri_credito_avvocato_antistatario",
                label="Spese distratte in favore dell'avvocato ex art. 93 c.p.c. (da confermare).",
                priority="P1", amount=importo, beneficiary_type="avvocato",
            ))
        elif spese.beneficiario_credito == "cliente" and spese.condanna_spese:
            azioni.append(EconomicAction(
                type="apri_credito_cliente",
                label="Spese liquidate in favore del cliente ex art. 91 c.p.c. (da confermare).",
                priority="P1", amount=importo, beneficiary_type="cliente",
            ))
        if spese.gratuito_patrocinio:
            azioni.append(EconomicAction(
                type="monitora_decreto_gratuito_patrocinio",
                label="Gratuito patrocinio: compenso liquidato con decreto di pagamento, importi prenotati a debito.",
                priority="P1", beneficiary_type="erario",
            ))
        if cu.status in {"mancante", "insufficiente", "da_integrare", "incerto"}:
            azioni.append(EconomicAction(
                type="verifica_contributo_unificato",
                label=f"Contributo unificato da verificare (stato: {cu.status}).",
                priority="P0",
            ))
        if cu.invito_pagamento_rilevato:
            azioni.append(EconomicAction(
                type="scadenza_invito_cu",
                label="Invito al pagamento del contributo unificato ex art. 248 D.P.R. 115/2002: deposita la ricevuta nei termini.",
                priority="P0",
            ))
        status = "to_review" if (match.human_review_required or sentenza.spese_liquidate.human_review_required or cu.human_review_required) else "verified"

    human_review = not match.rg_match or match.human_review_required or sentenza.spese_liquidate.human_review_required or cu.human_review_required

    return SentenzaEconomicAudit(
        fascicolo_id=str(getattr(fascicolo, "id", "") or ""),
        documento_id=str(documento_id or ""),
        fonte=str(fonte or "FASCICOLO"),
        document_hash_sha256=str(document_hash_sha256 or ""),
        message_id=str(message_id or ""),
        match=match,
        sentenza=sentenza,
        contributo_unificato=cu,
        azioni=azioni,
        safe_to_attach=match.safe_to_attach,
        human_review_required=human_review,
        status=status,
        ruleset_version=str(rules.get("version", "")),
    )


__all__ = [
    "load_ruleset",
    "SentenzaIdentityMatch",
    "SpeseLiquidate",
    "SentenzaEconomicExtraction",
    "ContributoUnificatoAudit",
    "EconomicAction",
    "SentenzaEconomicAudit",
    "build_identity_match",
    "extract_economics",
    "assess_contributo_unificato",
    "build_audit",
]
