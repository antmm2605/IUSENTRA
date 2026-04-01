"""
pct/workflow_onboarding.py - Helper di onboarding tra preventivi, conferimenti e fascicoli.

Costruisce un contesto guidato per l'apertura del fascicolo partendo dai dati gia
raccolti in fase commerciale/contrattuale, in modo da ridurre click e duplicazioni.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pct.fascicoli import TipoFascicolo
from pct.motore_preventivo import get_tipo_pratica


_MAP_AREE_TO_TIPO = {
    "Civile": TipoFascicolo.CIVILE,
    "Penale": TipoFascicolo.PENALE,
    "Amministrativo": TipoFascicolo.AMMINISTRATIVO,
    "Tributario": TipoFascicolo.TRIBUTARIO,
    "Stragiudiziale": TipoFascicolo.STRAGIUDIZIALE,
    "Lavoro e previdenza": TipoFascicolo.LAVORO,
    "Speciali": TipoFascicolo.ALTRO,
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
    oggetto = getattr(sorgente, "oggetto", "") or (scheda.label if scheda else "")
    avvocato_referente = (
        getattr(conferimento, "avvocato_referente", "")
        or getattr(cliente, "avvocato_referente", "")
        or ""
    )
    valore_causa = float(getattr(preventivo, "valore_controversia", 0) or 0)

    source_label = "Conferimento incarico" if conferimento else "Preventivo"
    source_number = getattr(sorgente, "numero", "")
    titolo = _titolo_default(nome_cliente, oggetto, scheda.label if scheda else tipo_procedimento)

    checklist = list(getattr(scheda, "checklist_iniziale", []) or [])
    if not checklist:
        checklist = [
            "Verificare i dati essenziali di cliente, controparte e oggetto dell'incarico.",
            "Collegare il fascicolo al preventivo e ai documenti iniziali gia disponibili.",
            "Impostare subito le prossime scadenze e il primo passo operativo.",
        ]

    notes = [
        f"Apertura guidata da {source_label.lower()} {source_number}.".strip(),
        f"Tipologia collegata: {scheda.label}." if scheda else "",
        f"Motore preventivo: {scheda.motore_label}." if scheda and scheda.motore_label else "",
        "Checklist iniziale:",
    ]
    notes.extend([f"- {item}" for item in checklist])
    note_text = "\n".join([line for line in notes if line]).strip()

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
        "note": note_text,
        "tipo_procedimento": tipo_procedimento,
        "id_pratica": id_pratica,
        "area_pratica": area_pratica,
    }
