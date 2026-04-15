"""Runtime helpers for fascicoli management routes."""

from __future__ import annotations

from collections import Counter
from typing import Any


def build_quadro_fascicolo_context(
    *,
    app_config: dict[str, Any],
    id_fasc: str,
    fascicolo: Any,
    cliente: Any,
    get_scadenziario: Any,
    get_agenda: Any,
    get_soggetti: Any,
    build_responsabile_conformita_fascicolo: Any,
) -> dict[str, Any]:
    """Build the dashboard payload for the quadro fascicolo view."""
    from pct.fatturazione import GestioneFatturazione
    from pct.preventivi import GestionePreventivi

    gp = GestionePreventivi(app_config.get("PREVENTIVI_DB", "./preventivi/preventivi.json"))
    preventivi_fascicolo = gp.preventivi_per_fascicolo(id_fasc)
    conferimenti_fascicolo = gp.conferimenti_per_fascicolo(id_fasc)
    preventivo = preventivi_fascicolo[0] if preventivi_fascicolo else None
    conferimento = conferimenti_fascicolo[0] if conferimenti_fascicolo else None

    parcelle: list[Any] = []
    try:
        gfatt = GestioneFatturazione(
            db_path=app_config.get("FATTURAZIONE_DB", "./fatturazione/parcelle.json")
        )
        parcelle = gfatt.per_fascicolo(id_fasc)
    except Exception:
        parcelle = []

    scadenziario = get_scadenziario()
    scadenze_fascicolo = scadenziario.tutte(id_fascicolo=id_fasc, solo_aperte=False)
    agenda = get_agenda()
    apps = agenda.cerca(testo=fascicolo.numero_rg) if getattr(fascicolo, "numero_rg", "") else []

    parti = get_soggetti().parti_fascicolo(id_fasc)
    responsabile_conformita = build_responsabile_conformita_fascicolo(
        fascicolo=fascicolo,
        cliente=cliente,
        preventivo=preventivo,
        conferimento=conferimento,
        parti=parti,
    )

    importo_preventivo = getattr(preventivo, "totale", None) or 0.0
    importo_conferimento = getattr(conferimento, "onorario_pattuito", None) or 0.0

    totale_emesso = sum(p.totale for p in parcelle)
    totale_pagato = sum(
        p.totale
        for p in parcelle
        if getattr(p, "stato", None) and p.stato.value == "PAGATA"
    )
    n_parcelle_emesse = len(
        [p for p in parcelle if getattr(p, "stato", None) and p.stato.value != "BOZZA"]
    )
    n_parcelle_pagate = len(
        [p for p in parcelle if getattr(p, "stato", None) and p.stato.value == "PAGATA"]
    )
    n_parcelle_scadute = len(
        [p for p in parcelle if getattr(p, "stato", None) and p.stato.value == "SCADUTA"]
    )

    doc_per_tipo = Counter(
        getattr(doc.tipo, "value", str(doc.tipo)) for doc in (fascicolo.documenti or [])
    )
    n_doc_firmati = sum(
        1 for doc in (fascicolo.documenti or []) if getattr(doc, "firmato", False)
    )

    depositi = fascicolo.depositi_pct or []
    stati_depositi = Counter(dep.stato for dep in depositi)
    ultimo_deposito = depositi[-1] if depositi else None

    return {
        "preventivo": preventivo,
        "conferimento": conferimento,
        "parcelle": parcelle,
        "scadenze_fascicolo": scadenze_fascicolo,
        "apps": apps,
        "parti": parti,
        "responsabile_conformita": responsabile_conformita,
        "importo_preventivo": importo_preventivo,
        "importo_conferimento": importo_conferimento,
        "totale_emesso": totale_emesso,
        "totale_pagato": totale_pagato,
        "n_parcelle_emesse": n_parcelle_emesse,
        "n_parcelle_pagate": n_parcelle_pagate,
        "n_parcelle_scadute": n_parcelle_scadute,
        "doc_per_tipo": dict(doc_per_tipo),
        "n_doc_firmati": n_doc_firmati,
        "depositi": depositi,
        "stati_depositi": dict(stati_depositi),
        "ultimo_deposito": ultimo_deposito,
    }
