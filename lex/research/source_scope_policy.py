"""Policy di separazione forte tra fonti interne studio e fonti pubbliche legali.

Classifica ogni richiesta Lex in uno scope preciso:

- studio_internal       → dati studio (clienti, fascicoli, agenda, scadenze, fatture)
- public_legal_source   → fonti pubbliche (sentenze, normativa, giurisprudenza)
- mixed_private_public  → fascicolo + ricerca pubblica (query da separare)
- diagnostic            → diagnostica Lex, correzioni, feedback
- operational_no_web    → redazione atti, bozze, PEC — no web salvo normativa specifica

Regole invarianti:
- studio_internal NON usa web
- public_legal_source FORZA web ufficiale
- mixed_private_public separa query interna e pubblica anonimizzata
- diagnostic NON usa fonti casuali
- operational_no_web NON usa web salvo normativa specifica esplicita
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Tipi di scope
# ---------------------------------------------------------------------------

SCOPE_STUDIO_INTERNAL = "studio_internal"
SCOPE_PUBLIC_LEGAL = "public_legal_source"
SCOPE_MIXED = "mixed_private_public"
SCOPE_DIAGNOSTIC = "diagnostic"
SCOPE_OPERATIONAL_NO_WEB = "operational_no_web"

ALL_SCOPES = (
    SCOPE_STUDIO_INTERNAL,
    SCOPE_PUBLIC_LEGAL,
    SCOPE_MIXED,
    SCOPE_DIAGNOSTIC,
    SCOPE_OPERATIONAL_NO_WEB,
)


# ---------------------------------------------------------------------------
# Pattern di classificazione
# ---------------------------------------------------------------------------

_STUDIO_INTERNAL_PATTERNS = (
    r"\b(cliente|clienti|assistito|assistita)\b",
    r"\b(anagrafica|anagrafiche|recapit[io]|scheda cliente)\b",
    r"\b(codice fiscale|cf|c\.f\.|partita iva|p\.iva|piva)\b",
    r"\b(pec del cliente|email del cliente|telefono del cliente)\b",
    r"\b(fascicolo|fascicoli|rg\s*\d|pratica|causa mia)\b",
    r"\b(agenda|appuntamento|udienza di oggi|prossime udienze)\b",
    r"\b(scadenza|scadenze|termine del fascicolo)\b",
    r"\b(parcella|fattura|preventivo|onorario mio)\b",
    r"\b(cosa ho oggi|cosa ho domani|prossimi appuntamenti)\b",
    r"\b(dati di|dati del|dati della|scheda di)\b",
    r"\b(trova il cliente|cerca il cliente|mostrami il cliente)\b",
    r"\b(dammi i dati|mostrami i dati|dimmi i dati)\b",
)

_PUBLIC_LEGAL_PATTERNS = (
    r"\bsentenza\s+n[°\.]?\s*\d+",
    r"\bsentenza\s+del\s+\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}",
    r"\bsentenza\s+n[°\.]?\s*\d+\s+del\s+\d",
    r"\bcass(?:azione)?\.?\s+(?:civ|pen|sez)\.?\s",
    r"\bcorte\s+di\s+cassazione\b",
    r"\bgiurisprudenza\s+su\b",
    r"\bnormativa\s+su\b",
    r"\bart(?:icolo)?\.?\s*\d+\s+c\.?\s*(?:p\.?\s*c|p\.?\s*p|c\.?)\.",
    r"\blegge\s+n\.?\s*\d+",
    r"\bd\.?\s*lgs\.?\s*\d+",
    r"\bdecreto\s+legislativo\b",
    r"\bgazzetta\s+ufficiale\b",
    r"\bnormattiva\b",
    r"\beur-?lex\b",
    r"\bgiustizia[-\s]amministrativa\b",
    r"\btar\s+[a-z]",
    r"\bcorte\s+costituzionale\b",
    r"\bcedu\b",
    r"\bcuria\s+europea\b",
    r"\bprescrizione\s+del\s+(?:reato|credito|diritto)\b",
    r"\btrova\s+(?:la\s+)?(?:questa\s+)?sentenza\b",
    r"\bcerca\s+(?:la\s+)?(?:questa\s+)?sentenza\b",
)

_OPERATIONAL_NO_WEB_PATTERNS = (
    r"\bscrivi\s+(?:una\s+)?(?:diffida|lettera|pec|bozza|atto)\b",
    r"\bbozza\s+(?:di\s+)?(?:lettera|atto|diffida|contratto|ricorso)\b",
    r"\bredigi\s+",
    r"\bprepara\s+(?:una\s+)?(?:lettera|bozza|atto)\b",
    r"\bmessa\s+in\s+mora\b",
    r"\bdiffida\s+formale\b",
    r"\bmodello\s+di\s+(?:lettera|atto|diffida)\b",
    r"\bdeposito\s+telematico\b",
    r"\bchecklist\s+deposito\b",
    r"\berrore\s+(?:pst|pdp|pat|ptt)\b",
    r"\btermini?\s+(?:per|processual)\b",
    r"\bgiorni\s+dalla\s+notifica\b",
    r"\bscadenza\s+(?:per\s+l[\'']appello|del\s+ricorso)\b",
)

_DIAGNOSTIC_PATTERNS = (
    r"\bnon\s+(?:hai\s+)?capit[oa]\b",
    r"\bsei\s+fuori\s+strada\b",
    r"\briprova\b",
    r"\bcorreggi(?:ti)?\b",
    r"\bhai\s+sbagliato\b",
    r"\bnon\s+è\s+quello\s+che\s+(?:ho\s+)?chiesto\b",
    r"\blex\s+non\s+funziona\b",
    r"\bnon\s+hai\s+(?:trovato|letto|capito)\b",
    r"\bperché\s+non\s+(?:trovi|cerchi|leggi)\b",
    r"\bnon\s+(?:riesci|puoi)\s+(?:a\s+)?(?:cercare|trovare|leggere)\b",
)

_MIXED_PATTERNS = (
    r"\bnel\s+fascicolo\s+.{1,40}\btrov[a-z]+\s+(?:sentenza|normativa|giurisprudenza|casistica)\b",
    r"\bnel\s+(?:caso|procedimento)\s+.{1,40}\bgiurisprudenza\b",
    r"\b(?:per\s+)?questo\s+fascicolo\s+.{0,30}\bnormativa\b",
    r"\bpuò?\s+eccepire\b",
    r"\bprescrizione\s+nel\s+(?:fascicolo|caso|mio)\b",
    r"\bstategia\s+per\s+il\s+fascicolo\b",
)


def _clean(text: str) -> str:
    return " ".join(str(text or "").lower().split()).strip()


def _match_any(text: str, patterns: tuple[str, ...]) -> bool:
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


# ---------------------------------------------------------------------------
# Dataclass risultato
# ---------------------------------------------------------------------------

@dataclass
class SourceScope:
    """Classificazione dello scope di una richiesta Lex."""

    scope: str
    confidence: float               # 0.0–1.0
    requires_studio_data: bool      # usa dati interni studio
    requires_public_web: bool       # forza ricerca web pubblica
    public_query_safe: bool         # la query pubblica non contiene dati sensibili
    anonymize_before_web: bool      # serve anonimizzare prima di usare web
    exact_legal_reference: bool     # contiene riferimento esatto (sentenza n. xxx)
    studio_entity_hint: str         # nome/CF/PIVA estratto dalla query
    web_blocked_reason: str         # motivo per cui il web è bloccato (se applicable)
    debug_log: list[str] = field(default_factory=list)

    @property
    def is_studio_only(self) -> bool:
        return self.scope == SCOPE_STUDIO_INTERNAL

    @property
    def is_public_only(self) -> bool:
        return self.scope == SCOPE_PUBLIC_LEGAL

    @property
    def is_mixed(self) -> bool:
        return self.scope == SCOPE_MIXED

    @property
    def reason(self) -> str:
        """Motivo sintetico compatibile con i payload debug esistenti."""
        if self.web_blocked_reason:
            return self.web_blocked_reason
        return "; ".join(self.debug_log or [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "confidence": round(self.confidence, 3),
            "requires_studio_data": self.requires_studio_data,
            "requires_public_web": self.requires_public_web,
            "public_query_safe": self.public_query_safe,
            "anonymize_before_web": self.anonymize_before_web,
            "exact_legal_reference": self.exact_legal_reference,
            "studio_entity_hint": self.studio_entity_hint,
            "web_blocked_reason": self.web_blocked_reason,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Classificatore
# ---------------------------------------------------------------------------

def classify_source_scope(
    question: str,
    *,
    workflow: str = "",
    intent: str = "",
    metadata: dict[str, Any] | None = None,
) -> SourceScope:
    """Classifica la richiesta in uno scope sorgente preciso.

    Args:
        question: Domanda dell'utente normalizzata.
        workflow: Workflow già risolto dal router (opzionale).
        intent: Intent già classificato dal request_profile (opzionale).

    Returns:
        SourceScope con tutti i metadati di classificazione.
    """
    text = _clean(question)
    debug: list[str] = []

    # ── Override da workflow già risolto ─────────────────────────────────────
    if workflow in ("lex_feedback_diagnostico",) or intent in ("lex_feedback_diagnostico",):
        return SourceScope(
            scope=SCOPE_DIAGNOSTIC,
            confidence=0.98,
            requires_studio_data=False,
            requires_public_web=False,
            public_query_safe=True,
            anonymize_before_web=False,
            exact_legal_reference=False,
            studio_entity_hint="",
            web_blocked_reason="workflow diagnostico: nessuna fonte esterna",
            debug_log=["override: workflow=lex_feedback_diagnostico"],
        )

    if workflow in ("drafting_legal_letter", "lettera", "bozza_lettera", "atto", "bozza_atto", "pec_comunicazioni"):
        return SourceScope(
            scope=SCOPE_OPERATIONAL_NO_WEB,
            confidence=0.95,
            requires_studio_data=False,
            requires_public_web=False,
            public_query_safe=True,
            anonymize_before_web=False,
            exact_legal_reference=False,
            studio_entity_hint="",
            web_blocked_reason="workflow redazione: nessuna fonte web salvo normativa specifica",
            debug_log=[f"override: workflow={workflow}"],
        )

    if workflow in ("deposito_telematico", "telematico_status", "termini_processuali"):
        return SourceScope(
            scope=SCOPE_OPERATIONAL_NO_WEB,
            confidence=0.95,
            requires_studio_data=False,
            requires_public_web=False,
            public_query_safe=True,
            anonymize_before_web=False,
            exact_legal_reference=False,
            studio_entity_hint="",
            web_blocked_reason="workflow operativo: nessuna fonte web",
            debug_log=[f"override: workflow={workflow}"],
        )

    if workflow in ("giurisprudenza_specifica",) or intent in ("giurisprudenza_specifica",):
        debug.append("override: workflow=giurisprudenza_specifica → public_legal_source")
        return SourceScope(
            scope=SCOPE_PUBLIC_LEGAL,
            confidence=0.97,
            requires_studio_data=False,
            requires_public_web=True,
            public_query_safe=True,
            anonymize_before_web=False,
            exact_legal_reference=True,
            studio_entity_hint="",
            web_blocked_reason="",
            debug_log=debug,
        )

    if workflow in ("studio_data_lookup", "cliente_anagrafica") or intent in ("cliente_anagrafica", "studio_context_lookup"):
        entity = _extract_studio_entity_hint(text)
        return SourceScope(
            scope=SCOPE_STUDIO_INTERNAL,
            confidence=0.97,
            requires_studio_data=True,
            requires_public_web=False,
            public_query_safe=False,
            anonymize_before_web=True,
            exact_legal_reference=False,
            studio_entity_hint=entity,
            web_blocked_reason="workflow dati studio: nessun dato sensibile verso web",
            debug_log=[f"override: workflow={workflow}, entity_hint={entity!r}"],
        )

    # ── Pattern matching ──────────────────────────────────────────────────────
    is_diagnostic = _match_any(text, _DIAGNOSTIC_PATTERNS)
    is_studio = _match_any(text, _STUDIO_INTERNAL_PATTERNS)
    is_public = _match_any(text, _PUBLIC_LEGAL_PATTERNS)
    is_operational = _match_any(text, _OPERATIONAL_NO_WEB_PATTERNS)
    is_mixed = _match_any(text, _MIXED_PATTERNS)

    debug.append(f"patterns: diagnostic={is_diagnostic} studio={is_studio} public={is_public} operational={is_operational} mixed={is_mixed}")

    # Diagnostico
    if is_diagnostic:
        return SourceScope(
            scope=SCOPE_DIAGNOSTIC,
            confidence=0.90,
            requires_studio_data=False,
            requires_public_web=False,
            public_query_safe=True,
            anonymize_before_web=False,
            exact_legal_reference=False,
            studio_entity_hint="",
            web_blocked_reason="richiesta diagnostica: nessuna fonte esterna",
            debug_log=debug,
        )

    # Misto: fascicolo + ricerca pubblica
    if is_mixed or (is_studio and is_public):
        entity = _extract_studio_entity_hint(text)
        return SourceScope(
            scope=SCOPE_MIXED,
            confidence=0.85,
            requires_studio_data=True,
            requires_public_web=True,
            public_query_safe=False,  # contiene riferimenti privati
            anonymize_before_web=True,
            exact_legal_reference=_has_exact_legal_ref(text),
            studio_entity_hint=entity,
            web_blocked_reason="",
            debug_log=debug,
        )

    # Solo fonti pubbliche
    if is_public:
        exact = _has_exact_legal_ref(text)
        return SourceScope(
            scope=SCOPE_PUBLIC_LEGAL,
            confidence=0.90 if exact else 0.80,
            requires_studio_data=False,
            requires_public_web=True,
            public_query_safe=True,
            anonymize_before_web=False,
            exact_legal_reference=exact,
            studio_entity_hint="",
            web_blocked_reason="",
            debug_log=debug,
        )

    # Solo dati studio
    if is_studio:
        entity = _extract_studio_entity_hint(text)
        return SourceScope(
            scope=SCOPE_STUDIO_INTERNAL,
            confidence=0.90,
            requires_studio_data=True,
            requires_public_web=False,
            public_query_safe=False,
            anonymize_before_web=True,
            exact_legal_reference=False,
            studio_entity_hint=entity,
            web_blocked_reason="richiesta dati studio: nessun dato verso web",
            debug_log=debug,
        )

    # Operativo (bozze, redazione)
    if is_operational:
        return SourceScope(
            scope=SCOPE_OPERATIONAL_NO_WEB,
            confidence=0.85,
            requires_studio_data=False,
            requires_public_web=False,
            public_query_safe=True,
            anonymize_before_web=False,
            exact_legal_reference=False,
            studio_entity_hint="",
            web_blocked_reason="redazione/operativo: nessuna fonte web salvo normativa specifica",
            debug_log=debug,
        )

    # Fallback: pubblico (chat generica su diritto)
    debug.append("fallback: nessun pattern forte → public_legal_source con confidence bassa")
    return SourceScope(
        scope=SCOPE_PUBLIC_LEGAL,
        confidence=0.50,
        requires_studio_data=False,
        requires_public_web=False,  # non forzato — attivato solo se trigger legali presenti
        public_query_safe=True,
        anonymize_before_web=False,
        exact_legal_reference=False,
        studio_entity_hint="",
        web_blocked_reason="",
        debug_log=debug,
    )


# ---------------------------------------------------------------------------
# Helper: exact legal reference detector
# ---------------------------------------------------------------------------

_EXACT_LEGAL_REF_PATTERNS = (
    r"\bsentenza\b.{0,90}\bn[°\.]?\s*\d{1,6}",
    r"\bsentenza\b.{0,90}\bn[°\.]?\s*\d+\s+del\s+\d",
    r"\bprovvedimento\s+n[°\.]?\s*\d+",
    r"\bordinanza\s+n[°\.]?\s*\d+",
    r"\bdecreto\s+n[°\.]?\s*\d+",
    r"\bcass(?:azione)?\.?\s*n[°\.]?\s*\d+",
    r"\bcass(?:azione)?\.?\s+(?:civ|pen|sez)\.?\s+\d+[/\-]\d+",
)


def _has_exact_legal_ref(text: str) -> bool:
    """Ritorna True se il testo contiene un riferimento legale preciso (numero sentenza)."""
    for pattern in _EXACT_LEGAL_REF_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


# ---------------------------------------------------------------------------
# Helper: entity hint extractor
# ---------------------------------------------------------------------------

_ENTITY_STOP_WORDS = frozenset({
    "il", "la", "lo", "le", "i", "gli", "un", "una", "del", "della", "dello",
    "dei", "delle", "degli", "al", "alla", "allo", "ai", "alle", "agli",
    "nel", "nella", "nello", "nei", "nelle", "negli", "sul", "sulla",
    "per", "di", "da", "a", "in", "con", "su", "tra", "fra",
    "dammi", "dami", "mostrami", "trova", "cerca", "dati", "cliente",
    "fascicolo", "anagrafica", "scheda", "informazioni", "recapiti",
    "questo", "questa", "quello", "quella", "che", "chi", "come", "quando",
})


def _extract_studio_entity_hint(text: str) -> str:
    """Estrae un possibile nome/identificatore di entità dalla query studio."""
    # CF pattern
    cf_match = re.search(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b", text.upper())
    if cf_match:
        return cf_match.group(0)

    # PIVA
    piva_match = re.search(r"\b\d{11}\b", text)
    if piva_match:
        return piva_match.group(0)

    # Email
    email_match = re.search(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,6}\b", text, re.IGNORECASE)
    if email_match:
        return email_match.group(0)

    # Nome proprio (parole con iniziale maiuscola consecutive, max 3)
    words = text.split()
    capitalized: list[str] = []
    for word in words:
        clean_w = re.sub(r"[^a-zA-ZÀ-ú]", "", word)
        if (
            clean_w
            and len(clean_w) >= 2
            and clean_w[0].isupper()
            and clean_w.lower() not in _ENTITY_STOP_WORDS
        ):
            capitalized.append(clean_w)
        else:
            if len(capitalized) >= 2:
                break
            capitalized = []

    if len(capitalized) >= 2:
        return " ".join(capitalized[:3])
    if len(capitalized) == 1:
        return capitalized[0]

    # Fallback: ultima parola significativa dopo "di/del/della"
    match = re.search(r"\b(?:di|del|della)\s+([A-Za-zÀ-ú]{3,}(?:\s+[A-Za-zÀ-ú]{2,})?)", text, re.IGNORECASE)
    if match:
        candidate = match.group(1).strip()
        if candidate.lower() not in _ENTITY_STOP_WORDS:
            return candidate.title()

    return ""
