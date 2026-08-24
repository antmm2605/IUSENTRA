"""
Helper condivisi per il workflow commerciale:
preventivo -> conferimento -> fascicolo operativo.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional

from pct.economico_context import riepilogo_contesto_economico
from pct.fascicoli import GestioneFascicoli, TipoAttivita, TipoFascicolo
from pct.motore_preventivo import get_tipo_pratica
from pct.practice_engine import PracticeEngineRepository
from pct.practice_engine.evaluator import ensure_profile_for_fascicolo
from pct.practice_profiles import get_practice_profile
from pct.preventivi import GestionePreventivi
from pct.scadenziario import GestioneScadenziario, TipoTermine
from pct.workflow_onboarding import build_fascicolo_onboarding


_ATTIVITA_BY_KEY = {
    "DEPOSITO_ATTI": TipoAttivita.DEPOSITO_ATTI,
    "ISCRIZIONE_A_RUOLO": TipoAttivita.ISCRIZIONE_A_RUOLO,
    "NOTIFICA": TipoAttivita.NOTIFICA,
    "CONSULTAZIONE": TipoAttivita.CONSULTAZIONE,
    "TERMINE_SCADENZA": TipoAttivita.TERMINE_SCADENZA,
    "ACCESSO_ATTI": TipoAttivita.ACCESSO_ATTI,
    "MEDIAZIONE": TipoAttivita.MEDIAZIONE,
    "CTU": TipoAttivita.CTU,
    "PROVVEDIMENTO": TipoAttivita.PROVVEDIMENTO,
    "APPELLO": TipoAttivita.APPELLO,
    "ESECUZIONE": TipoAttivita.ESECUZIONE,
    "ACCORDO": TipoAttivita.ACCORDO,
    "RINVIO": TipoAttivita.RINVIO,
}

_SCADENZA_BY_KEY = {
    "DEPOSITO_MEMORIA": TipoTermine.DEPOSITO_MEMORIA,
    "DEPOSITO_ATTO": TipoTermine.DEPOSITO_ATTO,
    "NOTIFICA": TipoTermine.NOTIFICA,
    "IMPUGNAZIONE": TipoTermine.IMPUGNAZIONE,
    "RISPOSTA_ECCEZIONE": TipoTermine.RISPOSTA_ECCEZIONE,
    "PAGAMENTO": TipoTermine.PAGAMENTO,
    "PRESCRIZIONE": TipoTermine.PRESCRIZIONE,
    "DECADENZA": TipoTermine.DECADENZA,
    "ADEMPIMENTO": TipoTermine.ADEMPIMENTO,
    "TERMINE_PERENTORIO": TipoTermine.TERMINE_PERENTORIO,
    "TERMINE_ORDINATORIO": TipoTermine.TERMINE_ORDINATORIO,
    "ALTRO": TipoTermine.ALTRO,
}


def workflow_channel_label(value: str) -> str:
    return "Portale cliente" if str(value or "").strip().upper() == "ONLINE" else "Studio"


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "si", "s"}


def _source_label(preventivo: Optional[Any], conferimento: Optional[Any]) -> str:
    if conferimento:
        return f"Conferimento {getattr(conferimento, 'numero', '')}".strip()
    if preventivo:
        return f"Preventivo {getattr(preventivo, 'numero', '')}".strip()
    return "Workflow commerciale"


def _normative_refs(pratica) -> list[dict[str, str]]:
    refs = []
    seen = set()
    for ref in getattr(pratica, "normative_references", []) or []:
        row = {
            "title": str(ref.get("title") or "").strip(),
            "article": str(ref.get("article") or "").strip(),
            "url": str(ref.get("url") or "").strip(),
        }
        key = (row["title"], row["article"], row["url"])
        if not any(key) or key in seen:
            continue
        seen.add(key)
        refs.append(row)
    return refs


def build_workflow_summary(
    *,
    cliente: Any,
    preventivo: Optional[Any] = None,
    conferimento: Optional[Any] = None,
    fascicolo: Optional[Any] = None,
) -> Dict[str, Any]:
    pratica_id = (
        getattr(conferimento, "id_pratica", "")
        or getattr(preventivo, "id_pratica", "")
        or ""
    )
    pratica = get_tipo_pratica(pratica_id) if pratica_id else None
    onboarding = (
        build_fascicolo_onboarding(cliente=cliente, preventivo=preventivo, conferimento=conferimento)
        if cliente and (preventivo or conferimento)
        else {}
    )
    econ_summary = riepilogo_contesto_economico(getattr(preventivo, "log_calcolo", None))
    channel = (
        getattr(conferimento, "workflow_channel", "")
        or getattr(preventivo, "workflow_channel", "")
        or "STUDIO"
    )
    cliente_missing = list(getattr(cliente, "campi_mancanti_per_conferimento", []) or [])
    firma_ok = bool(getattr(conferimento, "firma_cliente_eseguita", False))
    accepted = str(getattr(getattr(preventivo, "stato", None), "value", getattr(preventivo, "stato", ""))) in {"ACCETTATO", "CONVERTITO"}

    steps = [
        {
            "key": "preventivo",
            "label": "Preventivo creato",
            "complete": bool(preventivo),
        },
        {
            "key": "accettazione",
            "label": "Accettazione cliente",
            "complete": accepted,
        },
        {
            "key": "conferimento",
            "label": "Conferimento generato",
            "complete": bool(conferimento),
        },
        {
            "key": "firma",
            "label": "Firma conferimento",
            "complete": firma_ok,
        },
        {
            "key": "fascicolo",
            "label": "Workflow fascicolo attivato",
            "complete": bool(fascicolo),
        },
    ]

    next_step_key = "accettazione"
    next_step_label = "Attendi o registra l'accettazione del preventivo."
    if not accepted:
        next_step_label = "Registra l'accettazione del preventivo per attivare il conferimento."
    elif not conferimento:
        next_step_key = "conferimento"
        next_step_label = "Genera il conferimento di incarico dallo stesso workflow."
    elif not firma_ok:
        next_step_key = "firma"
        next_step_label = "Raccogli la firma del conferimento per aprire la pratica in automatico."
    elif cliente_missing:
        next_step_key = "cliente"
        next_step_label = "Completa l'anagrafica cliente prima dell'apertura automatica del fascicolo."
    elif not fascicolo:
        next_step_key = "fascicolo"
        next_step_label = "Il fascicolo può essere aperto automaticamente con checklist e scadenze iniziali."
    else:
        next_step_key = "operativita"
        next_step_label = "La pratica è già operativa: puoi lavorare da fascicolo, agenda e atti."

    # Arricchimento dal PracticeProfile centralizzato
    pp = get_practice_profile(pratica_id) if pratica_id else None

    return {
        "channel": channel,
        "channel_label": workflow_channel_label(channel),
        "practice_label": getattr(pratica, "label", "") or econ_summary.get("pratica_label") or "",
        "area_pratica": getattr(pratica, "area", "") or econ_summary.get("area_pratica") or "",
        "source_label": _source_label(preventivo, conferimento),
        "summary": onboarding.get("summary") or getattr(pratica, "summary", "") or "",
        "when_to_use": onboarding.get("when_to_use") or getattr(pratica, "when_to_use", "") or "",
        "checklist": list(onboarding.get("checklist", []) or []),
        "checklist_preview": list(onboarding.get("checklist", []) or [])[:3],
        "riferimenti_normativi": _normative_refs(pratica)[:4],
        "calc_summary": econ_summary,
        "missing_cliente_fields": cliente_missing,
        "cliente_completo": not cliente_missing,
        "accepted": accepted,
        "firma_eseguita": firma_ok,
        "fascicolo_operativo": bool(fascicolo),
        "fascicolo_pronto": bool(fascicolo),
        "next_step_key": next_step_key,
        "next_step_label": next_step_label,
        "steps": steps,
        "bozza_fascicolo": {
            "titolo": onboarding.get("titolo", ""),
            "tipo": onboarding.get("tipo", ""),
            "oggetto": onboarding.get("oggetto", ""),
            "valore_causa": onboarding.get("valore_causa", 0.0),
        },
        "procedura_operativa": onboarding.get("procedura_operativa", {}),
        "procedura_operativa_nome": onboarding.get("procedura_operativa_nome", ""),
        "procedura_operativa_codice": onboarding.get("procedura_operativa_codice", ""),
        "copertura_operativa": onboarding.get("copertura_operativa", ""),
        "canale_operativo": onboarding.get("canale_operativo", ""),
        "registro_operativo": onboarding.get("registro_operativo", ""),
        # Dati operativi dal PracticeProfile
        "practice_profile": {
            "practice_id": pp.practice_id if pp else pratica_id,
            "channel": pp.channel if pp else "",
            "registry": pp.registry if pp else "",
            "grade": pp.grade if pp else "",
            "office_scope": pp.office_scope if pp else "",
            "rito": pp.rito if pp else "",
            "taxonomy_path": pp.taxonomy_path if pp else [],
            "requires_deposit": pp.requires_deposit if pp else False,
            "requires_notification": pp.requires_notification if pp else False,
            "checklist_template_id": pp.checklist_template_id if pp else "",
            "workflow_profile_id": pp.workflow.workflow_profile_id if pp else "",
            "next_step_hint": pp.workflow.next_step_hint if pp else "",
        },
    }


def _titolo_attivita_checklist(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return "Checklist iniziale"
    clean = raw.rstrip(".")
    return clean if len(clean) <= 90 else clean[:87].rstrip() + "..."


def _tipo_attivita_from_key(value: str) -> TipoAttivita:
    return _ATTIVITA_BY_KEY.get(str(value or "").strip().upper(), TipoAttivita.ALTRO)


def _tipo_scadenza_from_key(value: str) -> TipoTermine:
    return _SCADENZA_BY_KEY.get(str(value or "").strip().upper(), TipoTermine.ADEMPIMENTO)


def _seed_attivita_iniziali(
    gf: GestioneFascicoli,
    id_fascicolo: str,
    *,
    activity_plan: Optional[list[dict[str, Any]]] = None,
    checklist: list[str],
    avvocato: str = "",
) -> int:
    oggi = date.today().isoformat()
    created = 0
    # I controlli iniziali del workflow restano onboarding e scadenze:
    # non devono popolare automaticamente la timeline delle attività processuali.
    for item in activity_plan or []:
        if not _bool(item.get("materialize_in_fascicolo")):
            continue
        titolo = str(item.get("title") or "").strip()
        descrizione = str(item.get("description") or "").strip() or titolo
        gf.aggiungi_attivita(
            id_fascicolo,
            _tipo_attivita_from_key(item.get("activity_type", "")),
            oggi,
            _titolo_attivita_checklist(titolo or descrizione),
            descrizione=descrizione,
            note=str(item.get("note") or "Attivita iniziale generata automaticamente dal workflow commerciale intelligente."),
            avvocato=avvocato,
        )
        created += 1
    return created


def _seed_scadenze_iniziali(
    gs: GestioneScadenziario,
    id_fascicolo: str,
    *,
    deadline_plan: Optional[list[dict[str, Any]]] = None,
    checklist: list[str],
    practice_label: str = "",
) -> int:
    if deadline_plan:
        created = 0
        for item in deadline_plan[:3]:
            giorni = int(item.get("due_in_days") or 3)
            gs.nuova(
                titolo=str(item.get("title") or "Scadenza iniziale").strip(),
                tipo=_tipo_scadenza_from_key(item.get("deadline_type", "")),
                data_scadenza=(date.today() + timedelta(days=giorni)).isoformat(),
                id_fascicolo=id_fascicolo,
                descrizione=str(item.get("description") or f"Controllo iniziale della pratica {practice_label or 'appena aperta'}.").strip(),
                data_decorrenza=date.today().isoformat(),
                note=str(item.get("note") or "Scadenza iniziale generata automaticamente dal workflow commerciale intelligente."),
                perentorio=_bool(item.get("perentorio")),
            )
            created += 1
        return created
    base_rows = [
        (
            "Verifica documentazione iniziale",
            2,
            checklist[0] if checklist else f"Controllare i documenti iniziali della pratica {practice_label or 'appena aperta'}.",
        ),
        (
            "Definisci il primo passo operativo",
            7,
            checklist[1] if len(checklist) > 1 else "Impostare strategia, rito e primo adempimento utile.",
        ),
        (
            "Aggiorna cliente e agenda interna",
            14,
            checklist[2] if len(checklist) > 2 else "Confermare prossime attività, documenti mancanti e calendario di lavoro.",
        ),
    ]
    created = 0
    for titolo, giorni, descrizione in base_rows:
        gs.nuova(
            titolo=titolo,
            tipo=TipoTermine.ADEMPIMENTO,
            data_scadenza=(date.today() + timedelta(days=giorni)).isoformat(),
            id_fascicolo=id_fascicolo,
            descrizione=descrizione,
            data_decorrenza=date.today().isoformat(),
            note="Scadenza iniziale generata automaticamente dal workflow commerciale.",
        )
        created += 1
    return created


def apri_fascicolo_automatico(
    *,
    gp: GestionePreventivi,
    gf: GestioneFascicoli,
    gs: GestioneScadenziario,
    cliente: Any,
    preventivo: Optional[Any] = None,
    conferimento: Optional[Any] = None,
    avvocato: str = "",
) -> Dict[str, Any]:
    existing_id = (
        getattr(conferimento, "id_fascicolo", "")
        or getattr(preventivo, "id_fascicolo", "")
        or ""
    )
    if existing_id:
        existing = gf.get(existing_id)
        if existing:
            return {
                "fascicolo": existing,
                "created": False,
                "attivita_create": 0,
                "scadenze_create": 0,
                "workflow_summary": build_workflow_summary(
                    cliente=cliente,
                    preventivo=preventivo,
                    conferimento=conferimento,
                    fascicolo=existing,
                ),
            }

    if cliente and not getattr(cliente, "profilo_completo_per_conferimento", True):
        raise ValueError(
            "L'anagrafica cliente deve essere completata prima dell'apertura automatica del fascicolo."
        )

    prefill = build_fascicolo_onboarding(
        cliente=cliente,
        preventivo=preventivo,
        conferimento=conferimento,
    )
    fasc = gf.nuovo(
        titolo=prefill.get("titolo") or prefill.get("oggetto") or "Nuova pratica",
        tipo=TipoFascicolo(prefill.get("tipo") or "CIVILE"),
        id_cliente=getattr(cliente, "id", ""),
        nome_cliente=getattr(cliente, "nome_completo", ""),
        oggetto=prefill.get("oggetto", ""),
        tipo_procedimento=prefill.get("tipo_procedimento", ""),
        id_pratica=prefill.get("id_pratica", ""),
        area_pratica=prefill.get("area_pratica", ""),
        procedura_operativa_codice=prefill.get("procedura_operativa_codice", ""),
        procedura_operativa_nome=prefill.get("procedura_operativa_nome", ""),
        subbranch_operativa_codice=prefill.get("subbranch_operativa_codice", ""),
        workflow_operativo_codice=prefill.get("workflow_operativo_codice", ""),
        copertura_operativa=prefill.get("copertura_operativa", ""),
        canale_operativo=prefill.get("canale_operativo", ""),
        registro_operativo=prefill.get("registro_operativo", ""),
        codice_oggetto_pst=prefill.get("codice_oggetto_pst", ""),
        fonte_codice_oggetto=prefill.get("fonte_codice_oggetto", ""),
        file_fonte_codice_oggetto=prefill.get("file_fonte_codice_oggetto", ""),
        profilo_deposito=prefill.get("profilo_deposito", {}),
        valore_preventivato=float(prefill.get("valore_preventivato", 0.0) or 0.0),
        compenso_pattuito=float(prefill.get("compenso_pattuito", 0.0) or 0.0),
        valore_causa=float(prefill.get("valore_causa", 0.0) or 0.0),
        avvocato_referente=prefill.get("avvocato_referente", ""),
        note=prefill.get("note", ""),
    )

    gp.collega_fascicolo(
        fasc.id,
        id_preventivo=getattr(preventivo, "id", "") or None,
        id_conferimento=getattr(conferimento, "id", "") or None,
        converti_preventivo=True,
    )
    gf.registra_onboarding(
        fasc.id,
        "Apertura automatica del fascicolo",
        note=f"Origine workflow: {_source_label(preventivo, conferimento)}",
        avvocato=avvocato or prefill.get("avvocato_referente", ""),
    )
    checklist = list(prefill.get("checklist", []) or [])
    attivita_create = _seed_attivita_iniziali(
        gf,
        fasc.id,
        activity_plan=list(prefill.get("attivita_iniziali", []) or []),
        checklist=checklist,
        avvocato=avvocato or prefill.get("avvocato_referente", ""),
    )
    scadenze_create = _seed_scadenze_iniziali(
        gs,
        fasc.id,
        deadline_plan=list(prefill.get("scadenze_iniziali", []) or []),
        checklist=checklist,
        practice_label=prefill.get("oggetto") or prefill.get("titolo") or "",
    )
    pe_repo = PracticeEngineRepository.from_fascicoli_db(
        str(gf.db_path),
        studio_db=getattr(gf, "_studio_db", None),
    )
    practice_engine_profile, _resolver = ensure_profile_for_fascicolo(
        pe_repo,
        fascicolo=gf.get(fasc.id) or fasc,
        preventivo=gp.get_preventivo(getattr(preventivo, "id", "")) if preventivo else None,
        conferimento=gp.get_conferimento(getattr(conferimento, "id", "")) if conferimento else None,
        actor=avvocato or prefill.get("avvocato_referente", ""),
    )
    pe_repo.audit(
        fasc.id,
        "FASCICOLO_OPENED_FROM_COMMERCIAL_WORKFLOW",
        actor=avvocato or prefill.get("avvocato_referente", ""),
        message="Fascicolo aperto con Regia Operativa applicata.",
        payload={"profile_code": getattr(practice_engine_profile, "code", "")},
    )
    return {
        "fascicolo": gf.get(fasc.id) or fasc,
        "created": True,
        "attivita_create": attivita_create,
        "scadenze_create": scadenze_create,
        "practice_engine_profile": getattr(practice_engine_profile, "code", ""),
        "workflow_summary": build_workflow_summary(
            cliente=cliente,
            preventivo=gp.get_preventivo(getattr(preventivo, "id", "")) if preventivo else None,
            conferimento=gp.get_conferimento(getattr(conferimento, "id", "")) if conferimento else None,
            fascicolo=gf.get(fasc.id) or fasc,
        ),
    }
