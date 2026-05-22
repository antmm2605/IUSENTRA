from __future__ import annotations

import re

from .contracts import LexRequest
from .types import WorkflowType


class LexRouter:
    """Router intenti a 12 livelli di priorità.

    Priorità crescente (1 = massima):
    1. lex_feedback_diagnostico — l'utente corregge Lex
    2. risposta_in_italiano — richiesta linguistica esplicita
    3. redazione_legale — diffide, lettere, PEC, atti
    4. termini_processuali — calcolo scadenze e termini
    5. telematico_deposito — PST/PDP/PAT/PTT/SIGP
    6. pec_comunicazioni — PEC formali (non di diffida)
    7. giurisprudenza_specifica — sentenza con numero/data
    8. normativa/giurisprudenza/prassi — ricerca legale
    9. economico_forense — DM55/147/150, compensi
    10. fascicolo_operativo — sintesi/gestione pratica
    11. analisi_documentale — contratti, PDF
    12. cabina_studio — overview e operativo
    """

    # ------------------------------------------------------------------ #
    # Hint sets per routing testuale                                        #
    # ------------------------------------------------------------------ #
    _FEEDBACK_HINTS = (
        "non hai capito",
        "hai sbagliato",
        "risposta sbagliata",
        "sei fuori strada",
        "non è corretto",
        "non è giusto",
        "intendevo altro",
        "riprova",
        "hai frainteso",
        "non era questa la domanda",
        "correggiti",
        "lex ha sbagliato",
    )
    _LETTERA_HINTS = (
        "diffida",
        "messa in mora",
        "messa in mòra",
        "costituzione in mora",
        "costituzione in mòra",
        "intimazione",
        "invito e diffida",
        "formale diffida",
        "diffida formale",
        "sollecito formale",
        "lettera legale",
        "lettera di messa",
        "lettera di diffida",
        "lettera di sollecito",
        "atto di contestazione",
    )
    _TEMPLATE_ACT_HINTS = (
        "crea atto",
        "prepara atto",
        "compila atto",
        "crea bozza atto",
        "crea la bozza nell'editor",
        "crea bozza nell'editor",
        "usa template",
        "dal catalogo atti",
        "catalogo atti",
        "template atti",
        "template atto",
        "atto da catalogo",
        "atto di citazione",
        "ricorso",
        "comparsa",
        "diffida",
        "decreto ingiuntivo",
        "procura alle liti",
        "nomina difensore",
        "separazione",
    )
    _TEMPLATE_CONTEXT_HINTS = (
        "template",
        "catalogo",
        "compilatore",
        "modello",
        "atto",
        "fascicolo",
        "pratica",
        "cliente",
        "contro",
        "parte",
        "editor",
    )
    _COMMUNICATION_LOOKUP_HINTS = (
        "ultima pec",
        "ultime pec",
        "ultimo messaggio pec",
        "pec ricevut",
        "pec inviat",
        "ultima email",
        "ultime email",
        "email ricevut",
        "email inviat",
        "posta ordinaria",
        "allegati pec",
        "allegati email",
    )
    _PEC_HINTS = (
        "pec legale",
        "pec formale",
        "pec alla cancelleria",
        "invia pec",
        "manda pec",
        "bozza pec",
        "pec al debitore",
        "posta elettronica certificata",
    )
    _TERMINI_HINTS = (
        "calcola il termine",
        "termine per l'opposizione",
        "termine per appell",
        "termine per la notifica",
        "termine per la costituzione",
        "giorni dalla notifica",
        "scadenza del termine",
        "quando scade il termine",
        "termine processuale",
        "perentorio",
        "decadenza",
    )
    _TELEMATICO_HINTS = (
        "pst",
        "pat",
        "ptt",
        "sigit",
        "siga",
        "pdp",
        "deposito telematico",
        "errore telematico",
        "polisweb",
        "busta enc",
        "datiatto",
        "checklist deposito",
        "firma cades",
        "pdf/a",
    )
    _GIURISPRUDENZA_SPECIFICA_PATTERNS = (
        r"\bcass(?:azione)?\.?\s*(?:civ|pen|lav|sez)\.?\s*[\dn]",
        r"\bn\.\s*\d{3,}",
        r"\bsentenza\s+n\.\s*\d+",
        r"\bpronuncia\s+n\.\s*\d+",
        r"\bord(?:inanza)?\s+n\.\s*\d+",
    )
    _NORMATIVA_HINTS = (
        "norma",
        "normativa",
        "decreto",
        "legge",
        "articolo",
        "gazzetta ufficiale",
        "normattiva",
        "vigente",
        "d.m.",
        "d.lgs.",
        "c.c.",
        "c.p.c.",
        "codice civile",
        "codice penale",
        "codice di procedura",
    )
    _GIURISPRUDENZA_HINTS = (
        "sentenza",
        "sentenze",
        "giurisprudenza",
        "massima",
        "pronuncia",
        "cassazione",
        "tar",
        "consiglio di stato",
        "corte costituzionale",
        "corte d'appello",
    )
    _PRASSI_HINTS = (
        "circolare",
        "prassi",
        "interpello",
        "provvedimento",
        "linea guida",
        "faq ufficiale",
    )
    _ECONOMICO_HINTS = (
        "d.m. 55",
        "d.m. 147",
        "d.m. 150",
        "d.m.55",
        "d.m.147",
        "compenso",
        "onorario",
        "tariffa forense",
        "scaglione",
        "rimborso spese",
        "parcella",
        "fattura",
        "incasso",
        "preventivo forense",
    )
    _COMPLIANCE_HINTS = (
        "conforme",
        "compliance",
        "metadati",
        "allegati obbligatori",
        "controllo deposito",
        "verifica deposito",
    )
    _FASCICOLO_HINTS = (
        "fascicolo",
        "pratica",
        "stato del fascicolo",
        "sintesi fascicolo",
        "documenti fascicolo",
        "prossima udienza",
    )
    _CABINA_HINTS = (
        "cabina",
        "quadro operativo",
        "cosa c'è da fare",
        "situazione studio",
        "dashboard",
        "priorità di oggi",
        "agenda",
        "appuntamenti",
        "promemoria",
        "cosa devo fare",
        "da dove parto",
    )
    _FONTI_HINTS = ("fonte", "fonti", "riferimento bibliografico", "citazione ufficiale")
    _GUIDA_PRATICA_HINTS = (
        "guida pratica",
        "scheda pratica",
        "guida operativa",
        "checklist pratica",
        "cosa verificare per",
        "come procedere per",
        "atto da redigere",
        "allegati obbligatori",
        "campi obbligatori",
    )
    _CLIENTE_ANAGRAFICA_HINTS = (
        "mi dai i dati del cliente",
        "mi dati i dati del cliente",
        "dammi i dati del cliente",
        "dimmi i dati del cliente",
        "trova cliente",
        "cerca cliente",
        "dati del cliente",
        "dati di",
        "anagrafica",
        "recapiti",
        "email del cliente",
        "pec del cliente",
        "codice fiscale del cliente",
        "cf del cliente",
        "partita iva del cliente",
        "telefono del cliente",
        "indirizzo del cliente",
        "chi è il cliente",
        "scheda cliente",
        "contatti del cliente",
    )
    _CLIENTE_ANAGRAFICA_PATTERNS = (
        r"\b(?:mi\s+)?(?:dai|dati|dammi|dimmi)\s+(?:i\s+)?dati\s+(?:del|di|della|dell[o'])\s+cliente\b",
        r"\bdati\s+(?:del|di|della|dell[o'])\s+cliente\b",
        r"\banagrafica\s+(?:del|di|della|dell[o'])\b",
        r"\brecapiti\s+(?:del|di|della|dell[o'])\b",
        r"\bcontatti\s+(?:del|di|della|dell[o'])\b",
        r"\bemail\s+(?:del|di)\b.*\bcliente\b",
        r"\bpec\s+(?:del|di)\b.*\bcliente\b",
        r"\b(?:cf|codice\s+fiscale)\b.*\bcliente\b",
        r"\bcliente\b.*\b(?:email|pec|telefono|indirizzo|cf|codice\s+fiscale)\b",
        r"^\s*cliente\s+[a-z0-9àèéìòù' -]{2,}$",
        r"\b(?:trova|cerca)\s+cliente\s+[a-z0-9àèéìòù' -]{2,}",
        r"\bche\s+fascicoli\s+ha\s+[a-z0-9àèéìòù' -]{2,}",
    )

    def resolve_workflow(self, request: LexRequest) -> WorkflowType:  # noqa: C901
        hint = str(getattr(request, "workflow_hint", "") or "").strip().lower()
        if hint:
            return hint  # type: ignore[return-value]

        # ---- Livello 1: feedback e correzione ----
        intent = str(getattr(request, "intent", "") or "").strip()
        if intent == "lex_feedback_diagnostico":
            return "lex_feedback_diagnostico"

        # ---- Livello 2: richiesta linguistica esplicita ----
        if intent == "risposta_in_italiano":
            return "question_answering"

        # ---- Livello 3: redazione legale ----
        if intent in {"template_act_lookup", "template_act_prefill", "template_act_create"}:
            return "atto_da_template"
        if intent == "bozza_lettera":
            return "drafting_legal_letter"
        if intent == "bozza_atto":
            return "atto"
        if intent in {"draft_act_support", "validate_draft"}:
            return "atto"

        # ---- Livello 4: termini processuali ----
        if intent == "termini_processuali":
            return "termini_processuali"

        # ---- Livello 5: telematico deposito ----
        if intent == "explain_telematico_error":
            return "telematico_status"
        if intent == "deposito_telematico":
            return "deposito_telematico"

        # ---- Livello 6: PEC comunicazioni ----
        if intent == "studio_context_lookup":
            return "cabina"
        if intent == "comunicazioni_lookup":
            return "cabina"
        if intent == "pec_comunicazioni":
            return "drafting_legal_letter"

        # ---- Livello 7: giurisprudenza specifica ----
        if intent == "giurisprudenza_specifica":
            return "giurisprudenza_specifica"

        # ---- Livello 8: ricerca legale ----
        if intent == "research_normativa":
            return "normativa"
        if intent == "research_giurisprudenza":
            return "giurisprudenza"
        if intent == "research_prassi":
            return "prassi"
        if intent == "research_sources":
            return "fonti"

        # ---- Livello 9: economico ----
        if intent in {"evaluate_preventivo", "evaluate_tariffario", "evaluate_fatturazione"}:
            return "economico"

        # ---- Livello 10: fascicolo operativo ----
        if intent in {"summarize_fascicolo", "suggest_fascicolo_updates"}:
            return "fascicolo"

        # ---- Livello 10b: anagrafica cliente ----
        if intent == "cliente_anagrafica":
            return "studio_data_lookup"

        # ---- Livello 11: analisi documenti ----
        if intent in {"analyze_document", "compare_documents"}:
            return "documento"

        # ---- Livello 12: cabina / operativo ----
        if intent in {"resolve_operational_question", "suggest_next_action"}:
            return "cabina"
        if intent == "prepare_udienza":
            return "udienza"
        if intent in {"explain_normative_change", "summarize_legal_update"}:
            return "intelligence"
        if intent == "check_compliance":
            return "compliance"

        # ---- Routing testuale (fallback per intent non classificato) ----
        text = self._normalize(" ".join([
            str(getattr(request, "query", "") or ""),
            str((getattr(request, "metadata", {}) or {}).get("module") or ""),
            str((getattr(request, "metadata", {}) or {}).get("topic") or ""),
        ]))

        # P1: feedback
        if self._has_any(text, self._FEEDBACK_HINTS):
            return "lex_feedback_diagnostico"
        # P2b: lookup comunicazioni; non va trattato come redazione.
        if self._has_any(text, self._COMMUNICATION_LOOKUP_HINTS):
            return "cabina"
        # P3a: atti dal catalogo prima della redazione libera.
        if self._looks_like_template_act(text, getattr(request, "metadata", {}) or {}):
            return "atto_da_template"
        # P3: redazione
        if self._has_any(text, self._LETTERA_HINTS):
            return "drafting_legal_letter"
        # P4: termini
        if self._has_any(text, self._TERMINI_HINTS):
            return "termini_processuali"
        # Domande sulla base normativa di un canale telematico restano ricerca normativa,
        # non checklist operativa di deposito.
        if self._has_any(text, self._NORMATIVA_HINTS) and self._looks_like_telematico(text):
            return "normativa"
        # P5: telematico
        if self._looks_like_telematico(text):
            return "deposito_telematico"
        # P6: PEC formali
        if self._has_any(text, self._PEC_HINTS):
            return "drafting_legal_letter"
        # P7: giurisprudenza specifica (pattern regex)
        if self._looks_like_giurisprudenza_specifica(text):
            return "giurisprudenza_specifica"
        # P8: compliance
        if self._has_any(text, self._COMPLIANCE_HINTS):
            return "compliance"
        # P9: prassi
        if self._has_any(text, self._PRASSI_HINTS):
            return "prassi"
        # P9: giurisprudenza generica
        if self._has_any(text, self._GIURISPRUDENZA_HINTS):
            return "giurisprudenza"
        # P9: normativa
        if self._has_any(text, self._NORMATIVA_HINTS):
            return "normativa"
        # P9: fonti
        if self._has_any(text, self._FONTI_HINTS):
            return "fonti"
        # P9: economico
        if self._has_any(text, self._ECONOMICO_HINTS):
            return "economico"
        if self._has_any(text, self._GUIDA_PRATICA_HINTS) and not getattr(request, "fascicolo_id", None):
            return "question_answering"
        # P10: anagrafica cliente (ha priorità su fascicolo generico)
        if self._has_any(text, self._CLIENTE_ANAGRAFICA_HINTS) or self._looks_like_cliente_anagrafica(text):
            return "studio_data_lookup"
        # P10: fascicolo
        if getattr(request, "fascicolo_id", None):
            return "fascicolo"
        if self._has_any(text, self._FASCICOLO_HINTS):
            return "fascicolo"
        # P12: cabina
        if self._has_any(text, self._CABINA_HINTS):
            return "cabina"
        return "question_answering"

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip().lower()

    @staticmethod
    def _has_any(text: str, hints: tuple[str, ...]) -> bool:
        return any(hint in text for hint in hints)

    def _looks_like_cliente_anagrafica(self, text: str) -> bool:
        for p in self._CLIENTE_ANAGRAFICA_PATTERNS:
            if re.search(p, text):
                return True
        return False

    def _looks_like_template_act(self, text: str, metadata: dict | None = None) -> bool:
        metadata = dict(metadata or {})
        active = metadata.get("active_context") if isinstance(metadata.get("active_context"), dict) else {}
        context_type = str(active.get("context_type") or active.get("contextType") or "").strip().lower()
        if context_type == "template_act":
            return True
        if str(metadata.get("model_code") or active.get("model_code") or active.get("modelCode") or "").strip():
            return True
        if not self._has_any(text, self._TEMPLATE_ACT_HINTS):
            return False
        if "lettera generica" in text and not any(token in text for token in ("template", "catalogo", "diffida")):
            return False
        if any(
            known in text
            for known in (
                "atto di citazione",
                "decreto ingiuntivo",
                "procura alle liti",
                "nomina difensore",
                "diffida",
            )
        ):
            return True
        return self._has_any(text, self._TEMPLATE_CONTEXT_HINTS)

    @staticmethod
    def _looks_like_giurisprudenza_specifica(text: str) -> bool:
        patterns = (
            r"\bcass(?:azione)?\.?\s*(?:civ|pen|lav|sez)\.?\s*[\dn]",
            r"\bn\.\s*\d{3,}",
            r"\bsentenza\s+n\.\s*\d+",
            r"\bpronuncia\s+n\.\s*\d+",
            r"\bord(?:inanza)?\s+n\.\s*\d+",
            r"\bcass\.?\s*\d{4,}",
        )
        for p in patterns:
            if re.search(p, text):
                return True
        return False

    @staticmethod
    def _looks_like_telematico(text: str) -> bool:
        return any(
            token in text
            for token in (
                "pst",
                "pat",
                "ptt",
                "sigit",
                "siga",
                "pdp",
                "deposito telematico",
                "errore telematico",
                "poli sweb",
                "polisweb",
                "busta enc",
                "datiatto",
                "checklist deposito",
                "firma cades",
                "pdf/a",
            )
        )
