"""
pct/workflow_onboarding.py - Helper di onboarding tra preventivi, conferimenti e fascicoli.

Costruisce un contesto guidato per l'apertura del fascicolo partendo dai dati gia
raccolti in fase commerciale/contrattuale, in modo da ridurre click e duplicazioni.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pct.checklist_atti import CANALE_LABEL, get_template
from pct.fascicoli import TipoFascicolo
from pct.motore_preventivo import get_tipo_pratica
from pct.preventivi import label_modello_clausola_controversie
from pct.practice_profiles import get_practice_profile
from pct.legal_platform_catalog import build_operational_fields


_MAP_AREE_TO_TIPO = {
    "Civile": TipoFascicolo.CIVILE,
    "Penale": TipoFascicolo.PENALE,
    "Amministrativo": TipoFascicolo.AMMINISTRATIVO,
    "Tributario": TipoFascicolo.TRIBUTARIO,
    "Stragiudiziale": TipoFascicolo.STRAGIUDIZIALE,
    "Lavoro e previdenza": TipoFascicolo.LAVORO,
    "Speciali": TipoFascicolo.ALTRO,
}

_CHECKLIST_TEMPLATE_BY_PRACTICE = {
    "comparsa_risposta": "comparsa_risposta",
    "decreto_ingiuntivo": "decreto_ingiuntivo",
    "appello_civile": "ricorso_appello",
    "opposizione_di": "opposizione_decreto_ingiuntivo",
    "mediazione": "mediazione",
    "ricorso_tributario": "ricorso_tributario",
    "appello_tributario": "appello_tributario",
    "nomina_difensore": "nomina_difensore",
}

_SMART_WORKFLOW_PROFILES: Dict[str, Dict[str, Any]] = {
    "comparsa_risposta": {
        "checklist": [
            "verificare subito il termine di costituzione del convenuto almeno 70 giorni prima dell'udienza (art. 166 c.p.c.)",
            "prendere posizione in modo chiaro e specifico sui fatti allegati dall'attore e definire eccezioni, riconvenzionale e mezzi di prova (art. 167 c.p.c.)",
            "raccogliere copia della citazione notificata, procura alle liti e documenti difensivi da depositare con la comparsa",
            "valutare immediatamente se occorre chiamare un terzo e chiedere lo spostamento dell'udienza nella stessa comparsa (art. 269 c.p.c.)",
        ],
        "activities": [
            {
                "title": "Verificare termine di costituzione e decadenze ex artt. 166-167 c.p.c.",
                "description": (
                    "Controllare la data della prima udienza, presidiare il termine di costituzione "
                    "del convenuto e verificare da subito tutte le difese soggette a decadenza."
                ),
                "activity_type": "TERMINE_SCADENZA",
                "due_in_days": 1,
                "deadline_type": "TERMINE_PERENTORIO",
                "perentorio": True,
                "note": "Controllo intelligente iniziale: artt. 166 e 167 c.p.c. nel rito ordinario vigente.",
            },
            {
                "title": "Acquisire citazione notificata, procura e documenti difensivi",
                "description": (
                    "Raccogliere la citazione notificata, la procura alle liti, i documenti offerti in "
                    "comunicazione e gli elementi utili alla comparsa di risposta."
                ),
                "activity_type": "CONSULTAZIONE",
                "due_in_days": 3,
                "deadline_type": "ADEMPIMENTO",
                "note": "Preparazione documentale iniziale per la comparsa e per il successivo deposito telematico.",
            },
            {
                "title": "Impostare eccezioni, riconvenzionale e mezzi istruttori",
                "description": (
                    "Definire le prese di posizione sui fatti allegati dall'attore, le eccezioni "
                    "processuali e di merito, l'eventuale riconvenzionale, la chiamata del terzo e i mezzi di prova."
                ),
                "activity_type": "DEPOSITO_ATTI",
                "due_in_days": 5,
                "deadline_type": "DEPOSITO_ATTO",
                "perentorio": True,
                "note": "Controllo intelligente iniziale: artt. 167 e 269 c.p.c.; verificare anche i documenti da offrire in comunicazione.",
            },
        ],
    },
}


def _infer_tipo_fascicolo(id_pratica: str = "", area_pratica: str = "", tipo_procedimento: str = "") -> TipoFascicolo:
    if id_pratica:
        key = id_pratica.lower()
        if any(token in key for token in ("separazione", "divorzio", "famiglia", "minori")):
            return TipoFascicolo.FAMIGLIA
        if any(token in key for token in ("succession", "eredit")):
            return TipoFascicolo.SUCCESSIONI
        if any(token in key for token in ("consulenza", "parere")):
            return TipoFascicolo.CONSULENZA
    if area_pratica in _MAP_AREE_TO_TIPO:
        return _MAP_AREE_TO_TIPO[area_pratica]

    lowered = (tipo_procedimento or "").lower()
    if "penal" in lowered:
        return TipoFascicolo.PENALE
    if "amministrativ" in lowered or "tar" in lowered or "consiglio di stato" in lowered:
        return TipoFascicolo.AMMINISTRATIVO
    if "tribut" in lowered or "cgt" in lowered:
        return TipoFascicolo.TRIBUTARIO
    if "lavoro" in lowered or "previdenz" in lowered:
        return TipoFascicolo.LAVORO
    if "mediazion" in lowered or "negoziazion" in lowered or "stragiud" in lowered:
        return TipoFascicolo.STRAGIUDIZIALE
    return TipoFascicolo.CIVILE


def _titolo_default(nome_cliente: str, oggetto: str, tipo_label: str) -> str:
    base = (oggetto or "").strip()
    if not base:
        base = tipo_label or "Nuovo incarico"
    if nome_cliente:
        return f"{nome_cliente} - {base}"
    return base


def _normalize_oggetto_workflow(oggetto: str, tipo_label: str = "") -> str:
    raw = str(oggetto or "").strip()
    if not raw:
        return tipo_label.strip()
    prefixes = [
        "conferimento incarico - ",
        "preventivo professionale per ",
        "preventivo per ",
    ]
    changed = True
    while changed and raw:
        changed = False
        lower = raw.lower()
        for prefix in prefixes:
            if lower.startswith(prefix):
                raw = raw[len(prefix):].strip(" -")
                changed = True
                break
    if tipo_label and raw.lower() == tipo_label.lower():
        return tipo_label
    return raw or tipo_label.strip()


def _merge_unique_rows(*groups: List[str]) -> List[str]:
    rows: List[str] = []
    seen = set()
    for group in groups:
        for item in group or []:
            text = str(item or "").strip()
            key = text.lower()
            if not text or key in seen:
                continue
            seen.add(key)
            rows.append(text)
    return rows


def _template_for_practice(id_pratica: str):
    # Prima controlla il registry centralizzato, poi il mapping legacy
    profile = get_practice_profile(id_pratica or "")
    if profile and profile.checklist_template_id:
        return get_template(profile.checklist_template_id)
    template_id = _CHECKLIST_TEMPLATE_BY_PRACTICE.get(id_pratica or "")
    return get_template(template_id) if template_id else None


def _template_checklist_rows(template, limit: int = 4) -> List[str]:
    if not template:
        return []
    rows: List[str] = []
    critical_rows = [item for item in template.checklist if getattr(item, "critico", False)]
    for item in critical_rows[:limit]:
        text = str(getattr(item, "testo", "")).strip()
        note = str(getattr(item, "note", "")).strip()
        if note:
            text = f"{text} - {note}"
        rows.append(text)
    return rows


def _template_required_documents_row(template, limit: int = 3) -> str:
    if not template:
        return ""
    docs = [
        str(doc.descrizione).strip()
        for doc in template.documenti
        if getattr(doc, "obbligatorio", False)
    ][:limit]
    if not docs:
        return ""
    return "raccogliere i documenti essenziali: " + ", ".join(docs)


def _generic_activity_plan(template, checklist: List[str]) -> List[Dict[str, Any]]:
    activities: List[Dict[str, Any]] = []
    channel_label = CANALE_LABEL.get(getattr(template, "canale", ""), "")
    if checklist:
        activities.append(
            {
                "title": "Verificare il primo controllo iniziale della pratica",
                "description": checklist[0],
                "activity_type": "TERMINE_SCADENZA",
                "due_in_days": 2,
                "deadline_type": "ADEMPIMENTO",
                "note": f"Canale operativo previsto: {channel_label}." if channel_label else "",
            }
        )
    doc_row = _template_required_documents_row(template)
    if doc_row:
        activities.append(
            {
                "title": "Raccogliere i documenti essenziali",
                "description": doc_row,
                "activity_type": "CONSULTAZIONE",
                "due_in_days": 4,
                "deadline_type": "ADEMPIMENTO",
                "note": "Controllo intelligente iniziale: documenti obbligatori del canale di lavoro selezionato.",
            }
        )
    if len(checklist) > 1:
        activities.append(
            {
                "title": "Impostare il primo adempimento operativo",
                "description": checklist[1],
                "activity_type": "DEPOSITO_ATTI",
                "due_in_days": 7,
                "deadline_type": "DEPOSITO_ATTO",
                "note": f"Canale operativo: {channel_label}." if channel_label else "",
            }
        )
    third_description = checklist[2] if len(checklist) > 2 else "Impostare le prossime scadenze e il primo passo di lavoro sul fascicolo."
    activities.append(
        {
            "title": "Organizzare agenda, scadenze e primo piano di lavoro",
            "description": third_description,
            "activity_type": "ALTRO",
            "due_in_days": 10,
            "deadline_type": "ADEMPIMENTO",
            "note": "Controllo intelligente iniziale: trasformare la checklist in attivita operative e scadenze monitorabili.",
        }
    )
    return activities


def _build_activity_plan(id_pratica: str, template, checklist: List[str]) -> List[Dict[str, Any]]:
    smart = _SMART_WORKFLOW_PROFILES.get(id_pratica or "")
    if smart:
        return [dict(item) for item in smart.get("activities", [])]
    return _generic_activity_plan(template, checklist)


def _build_deadline_plan(activity_plan: List[Dict[str, Any]], titolo_fascicolo: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in activity_plan[:3]:
        rows.append(
            {
                "title": str(item.get("title") or "Attivita iniziale").strip(),
                "description": str(item.get("description") or f"Controllo iniziale per {titolo_fascicolo}.").strip(),
                "due_in_days": int(item.get("due_in_days") or 3),
                "deadline_type": str(item.get("deadline_type") or "ADEMPIMENTO").strip().upper(),
                "perentorio": bool(item.get("perentorio")),
                "note": str(item.get("note") or "Scadenza iniziale generata automaticamente dal workflow intelligente.").strip(),
            }
        )
    return rows


def build_fascicolo_onboarding(
    *,
    cliente: Any,
    preventivo: Optional[Any] = None,
    conferimento: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Restituisce un dizionario pronto per precompilare il form fascicolo.

    Il dato piu specifico e il conferimento; in assenza, usa il preventivo.
    """
    sorgente = conferimento or preventivo
    if sorgente is None:
        raise ValueError("Serve almeno un preventivo o un conferimento per l'onboarding del fascicolo.")

    id_pratica = getattr(conferimento, "id_pratica", "") or getattr(preventivo, "id_pratica", "")
    area_pratica = getattr(conferimento, "area_pratica", "") or getattr(preventivo, "area_pratica", "")
    tipo_procedimento = getattr(conferimento, "tipo_procedimento", "") or getattr(preventivo, "tipo_procedimento", "")
    scheda = get_tipo_pratica(id_pratica) if id_pratica else None
    tipo_fascicolo = _infer_tipo_fascicolo(id_pratica=id_pratica, area_pratica=area_pratica, tipo_procedimento=tipo_procedimento)

    nome_cliente = getattr(cliente, "nome_completo", "") if cliente else ""
    oggetto = _normalize_oggetto_workflow(
        getattr(sorgente, "oggetto", "") or "",
        getattr(scheda, "label", "") if scheda else "",
    ) or (scheda.label if scheda else "")
    operational_fields = build_operational_fields(
        procedure_code=(
            getattr(conferimento, "procedura_operativa_codice", "")
            or getattr(preventivo, "procedura_operativa_codice", "")
        ),
        practice_id=id_pratica,
        area_pratica=area_pratica,
        tipo_procedimento=tipo_procedimento,
        oggetto=oggetto,
    )
    operational_profile = operational_fields.get("procedura_operativa", {}) or {}
    avvocato_referente = (
        getattr(conferimento, "avvocato_referente", "")
        or getattr(cliente, "avvocato_referente", "")
        or ""
    )
    valore_causa = float(getattr(preventivo, "valore_controversia", 0) or 0)
    compenso_pattuito = float(getattr(conferimento, "compenso_pattuito", 0) or 0)
    if not compenso_pattuito:
        # fallback al totale del preventivo se il conferimento non specifica un compenso
        compenso_pattuito = float(getattr(preventivo, "totale", 0) or 0)
    valore_preventivato = compenso_pattuito

    source_label = "Conferimento incarico" if conferimento else "Preventivo"
    source_number = getattr(sorgente, "numero", "")
    titolo = _titolo_default(nome_cliente, oggetto, scheda.label if scheda else tipo_procedimento)

    template = _template_for_practice(id_pratica)
    smart_profile = _SMART_WORKFLOW_PROFILES.get(id_pratica or "", {})
    documenti_operativi = list(operational_profile.get("required_documents", []) or [])
    checklist = _merge_unique_rows(
        list(smart_profile.get("checklist", []) or []),
        list(operational_profile.get("checklist", []) or []),
        ([f"raccogliere i documenti operativi essenziali: {', '.join(documenti_operativi[:3])}"] if documenti_operativi else []),
        _template_checklist_rows(template),
        list(getattr(scheda, "checklist_iniziale", []) or []),
    )
    if not checklist:
        checklist = [
            "verificare i dati essenziali di cliente, controparte e oggetto dell'incarico",
            "collegare il fascicolo al preventivo e ai documenti iniziali gia disponibili",
            "impostare subito le prossime scadenze e il primo passo operativo",
        ]
    attivita_iniziali = _build_activity_plan(id_pratica, template, checklist)
    scadenze_iniziali = _build_deadline_plan(attivita_iniziali, oggetto or titolo)

    notes = [
        f"Apertura guidata da {source_label.lower()} {source_number}.".strip(),
        f"Tipologia collegata: {scheda.label}." if scheda else "",
        f"Motore preventivo: {scheda.motore_label}." if scheda and scheda.motore_label else "",
        f"Procedura operativa: {operational_fields.get('procedura_operativa_nome', '')}." if operational_fields.get('procedura_operativa_nome') else "",
        f"Canale operativo atteso: {operational_fields.get('canale_operativo', '')}." if operational_fields.get('canale_operativo') else "",
        (
            "Clausola controversie attiva: "
            + label_modello_clausola_controversie(
                getattr(sorgente, "clausola_controversie_modello", "")
            )
            + "."
        )
        if getattr(sorgente, "clausola_controversie_attiva", False)
        else "",
        (
            "Workflow interno avviato con fascicolo da verificare anche dal Responsabile di conformita."
        )
        if getattr(sorgente, "clausola_controversie_attiva", False)
        else "",
        "Checklist iniziale:",
    ]
    notes.extend([f"- {item}" for item in checklist])
    if attivita_iniziali:
        notes.append("Controlli intelligenti iniziali:")
        notes.extend([f"- {item['title']}" for item in attivita_iniziali[:3]])
    note_text = "\n".join([line for line in notes if line]).strip()

    # Dati aggiuntivi dal registry centralizzato
    profile = get_practice_profile(id_pratica) if id_pratica else None
    canale_operativo = CANALE_LABEL.get(getattr(template, "canale", ""), "") if template else ""
    if not canale_operativo and profile:
        from pct.checklist_atti import CANALE_LABEL as _CL
        canale_operativo = _CL.get(profile.channel, "")

    return {
        "source_label": source_label,
        "source_number": source_number,
        "summary": getattr(scheda, "summary", "") if scheda else "",
        "when_to_use": getattr(scheda, "when_to_use", "") if scheda else "",
        "checklist": checklist,
        "titolo": titolo,
        "tipo": tipo_fascicolo.value,
        "oggetto": oggetto,
        "avvocato_referente": avvocato_referente,
        "valore_causa": valore_causa,
        "valore_preventivato": valore_preventivato,
        "compenso_pattuito": compenso_pattuito,
        "note": note_text,
        "tipo_procedimento": tipo_procedimento,
        "id_pratica": id_pratica,
        "area_pratica": area_pratica,
        "procedura_operativa_codice": operational_fields.get("procedura_operativa_codice", ""),
        "procedura_operativa_nome": operational_fields.get("procedura_operativa_nome", ""),
        "subbranch_operativa_codice": operational_fields.get("subbranch_operativa_codice", ""),
        "workflow_operativo_codice": operational_fields.get("workflow_operativo_codice", ""),
        "copertura_operativa": operational_fields.get("copertura_operativa", ""),
        "canale_operativo": operational_fields.get("canale_operativo", "") or canale_operativo,
        "registro_operativo": operational_fields.get("registro_operativo", ""),
        "procedura_operativa": operational_profile,
        "documenti_operativi": documenti_operativi,
        "attivita_iniziali": attivita_iniziali,
        "scadenze_iniziali": scadenze_iniziali,
        "template_checklist_id": getattr(template, "id", ""),
        # campi arricchiti dal PracticeProfile
        "practice_channel": profile.channel if profile else "",
        "practice_registry": profile.registry if profile else "",
        "practice_grade": profile.grade if profile else "",
        "practice_office_scope": profile.office_scope if profile else "",
        "practice_rito": profile.rito if profile else "",
        "practice_taxonomy_path": profile.taxonomy_path if profile else [],
        "practice_requires_deposit": profile.requires_deposit if profile else False,
        "practice_workflow_profile_id": profile.workflow.workflow_profile_id if profile else "",
        "practice_next_step_hint": profile.workflow.next_step_hint if profile else "",
    }
