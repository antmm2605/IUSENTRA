"""Bridge React per la pipeline CRM di intake (lead con verifica conflitti).

Espone il payload di /api/v1/ui/crm: colonne kanban per stato, statistiche di
conversione per fonte, esito della verifica conflitti ex art. 24 CDF per ogni
scheda. Le scritture passano dalle route operative (web/bootstrap/crm_routes).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from pct.antiriciclaggio import PRESTAZIONE_DIFENSIVA, PRESTAZIONI_IN_AMBITO
from pct.crm_intake import FONTI_LEAD, STATI_LEAD

_STATO_LABEL = {
    "NUOVO": "Primo contatto",
    "CONTATTATO": "Istruttoria iniziale",
    "APPUNTAMENTO": "Conferimento da valutare",
    "PREVENTIVO": "Preventivo e incarico",
    "VINTO": "Incarico conferito",
    "PERSO": "Non conferiti",
}

_STATO_TONE = {
    "NUOVO": "info",
    "CONTATTATO": "neutral",
    "APPUNTAMENTO": "warning",
    "PREVENTIVO": "warning",
    "VINTO": "success",
    "PERSO": "danger",
}

_FONTE_LABEL = {
    "passaparola": "Passaparola",
    "sito_studio": "Sito dello studio",
    "referral_professionista": "Referral professionista",
    "directory_ordine": "Directory Ordine",
    "social": "Social",
    "altro": "Altro",
}

_CONFLITTO_LABEL = {
    "nessuno": "Nessun riscontro",
    "da_valutare": "Da valutare",
    "potenziale_conflitto": "Potenziale conflitto",
}

_CONFLITTO_TONE = {
    "nessuno": "success",
    "da_valutare": "warning",
    "potenziale_conflitto": "danger",
}

_PRESTAZIONE_AML_LABEL = {
    **PRESTAZIONI_IN_AMBITO,
    PRESTAZIONE_DIFENSIVA: "Prestazione difensiva o giudiziale (fuori ambito art. 17, comma 7)",
}


def _text(value: Any, fallback: str = "") -> str:
    cleaned = " ".join(str(value or "").split()).strip()
    return cleaned or fallback


def _is_internal_quality_fixture(lead: Any) -> bool:
    """Esclude dalla UI di studio i soli record tecnici di collaudo.

    I record QA creati per verifiche di persistenza non sono contatti dello
    studio: non devono comparire nella pipeline, né alterarne i contatori.
    Il riconoscimento è volutamente stretto (prefisso ``QA``, riferimento a
    una fase e dominio RFC riservato ``example.test``), così un normale
    nominativo o una pratica contenente la parola "qualità" resta visibile.
    Il record rimane invece tracciabile nell'archivio tecnico per chi effettua
    manutenzione autorizzata.
    """

    denominazione = _text(getattr(lead, "denominazione", "")).casefold()
    email = _text(getattr(lead, "email", "")).casefold()
    return (
        denominazione.startswith("qa ")
        and "fase" in denominazione
        and email.endswith("@example.test")
    )


def _aml_payload(lead: Any, get_antiriciclaggio: Callable[[], Any] | None) -> dict[str, Any]:
    lead_id = _text(getattr(lead, "id", ""))
    base = {
        "available": bool(getattr(lead, "cliente_id", "")),
        "id": "",
        "status": "NON_AVVIATA",
        "label": "Da avviare dopo il collegamento del cliente",
        "inScope": True,
        "suggestedLevel": "",
        "selectedLevel": "",
        "renewalAt": "",
        "sourceOfTruth": "",
        "actions": {
            "avvia": f"/crm/lead/{lead_id}/antiriciclaggio/avvia",
            "aggiorna": "",
            "conferma": "",
        },
    }
    if not base["available"] or get_antiriciclaggio is None:
        return base
    try:
        verifiche = list(get_antiriciclaggio().per_lead(lead_id))
    except Exception:
        return base
    if not verifiche:
        base["label"] = "Da avviare: identifica prestazione e scopo del rapporto"
        return base
    verifica = verifiche[0]
    try:
        evidenze = list(get_antiriciclaggio().evidenze_screening(getattr(verifica, "id", "")))
    except Exception:
        evidenze = []
    ultima_evidenza = evidenze[0] if evidenze else {}
    status = _text(getattr(verifica, "stato", ""), "BOZZA")
    base.update({
        "id": _text(getattr(verifica, "id", "")),
        "status": status,
        "label": {
            "BOZZA": "Scheda da completare",
            "COMPLETATA": "Adeguata verifica confermata",
            "DA_RINNOVARE": "Rinnovo del controllo richiesto",
            "FUORI_AMBITO": "Prestazione difensiva fuori ambito",
        }.get(status, status.replace("_", " ").title()),
        "inScope": bool(getattr(verifica, "in_ambito", True)),
        "suggestedLevel": _text(getattr(getattr(verifica, "livello_suggerito", lambda: "")(), "value", "")),
        "selectedLevel": _text(getattr(verifica, "livello_scelto", "")),
        "renewalAt": _text(getattr(verifica, "scadenza_controllo", "")),
        "sourceOfTruth": _text(getattr(get_antiriciclaggio(), "source_of_truth", "")),
        "clientePep": bool(getattr(verifica, "cliente_pep", False)),
        "paeseAltoRischio": bool(getattr(verifica, "paese_alto_rischio", False)),
        "prestazione": _text(getattr(verifica, "prestazione", "")),
        "descrizionePrestazione": _text(getattr(verifica, "descrizione_prestazione", "")),
        "scopoNatura": _text(getattr(verifica, "scopo_natura", "")),
        "titolareEffettivo": getattr(getattr(verifica, "titolare_effettivo", None), "__dict__", {}) or {},
        "note": _text(getattr(verifica, "note", "")),
        "screening": {
            "outcome": _text(ultima_evidenza.get("outcome")),
            "checkedAt": _text(ultima_evidenza.get("checked_at")),
            "sourceUrl": _text(ultima_evidenza.get("source_url")),
            "sourceVersion": _text(ultima_evidenza.get("source_version")),
            "snapshotHash": _text(ultima_evidenza.get("snapshot_hash")),
            "matches": len(list(ultima_evidenza.get("matches") or [])),
        },
        "actions": {
            "avvia": base["actions"]["avvia"],
            "aggiorna": f"/crm/lead/{lead_id}/antiriciclaggio/{_text(getattr(verifica, 'id', ''))}/aggiorna",
            "conferma": f"/crm/lead/{lead_id}/antiriciclaggio/{_text(getattr(verifica, 'id', ''))}/conferma",
            "screening": f"/crm/lead/{lead_id}/antiriciclaggio/{_text(getattr(verifica, 'id', ''))}/screening-ue",
        },
    })
    return base


def _lead_payload(
    lead: Any,
    get_crm: Callable[[], Any],
    get_antiriciclaggio: Callable[[], Any] | None,
    *,
    operatore: str,
) -> dict[str, Any]:
    esito = dict(getattr(lead, "conflitto_esito", {}) or {})
    livello = _text(esito.get("livello"))
    verificato = bool(getattr(lead, "conflitto_verificato", False))
    lead_id = _text(getattr(lead, "id", ""))
    try:
        clearance = dict(get_crm().stato_clearance_conflitto(lead_id))
    except Exception:
        clearance = {"richiesta": False, "decisione": "", "convertibile": False, "label": "Stato clearance non disponibile"}
    try:
        barriera = dict(get_crm().stato_barriera_riservatezza(lead_id, operatore=operatore))
    except Exception:
        barriera = {"attiva": False, "gestibile": False, "label": "Stato barriera non disponibile", "utenti_autorizzati": []}
    return {
        "id": lead_id,
        "denominazione": _text(getattr(lead, "denominazione", ""), "Contatto"),
        "codiceFiscale": _text(getattr(lead, "codice_fiscale", "")),
        "partitaIva": _text(getattr(lead, "partita_iva", "")),
        "email": _text(getattr(lead, "email", "")),
        "telefono": _text(getattr(lead, "telefono", "")),
        "fonte": _text(getattr(lead, "fonte", ""), "altro"),
        "fonteLabel": _FONTE_LABEL.get(_text(getattr(lead, "fonte", ""), "altro"), "Altro"),
        "materia": _text(getattr(lead, "materia", "")),
        "esigenza": _text(getattr(lead, "esigenza", "")),
        "stato": _text(getattr(lead, "stato", ""), "NUOVO"),
        "referente": _text(getattr(lead, "referente", "")),
        "note": _text(getattr(lead, "note", "")),
        "clienteId": _text(getattr(lead, "cliente_id", "")),
        "motivoPerso": _text(getattr(lead, "motivo_perso", "")),
        "creatoIl": _text(getattr(lead, "creato_il", ""))[:10],
        "conflitto": {
            "verificato": verificato,
            "livello": livello,
            "label": _CONFLITTO_LABEL.get(livello, "Verifica da eseguire") if verificato else "Verifica da eseguire",
            "tone": _CONFLITTO_TONE.get(livello, "neutral") if verificato else "neutral",
            "riscontri": [
                {
                    "tipo": _text(r.get("tipo")),
                    "etichetta": _text(r.get("etichetta")),
                    "certo": bool(r.get("certo")),
                    "ruolo": _text(r.get("ruolo")),
                }
                for r in list(esito.get("riscontri") or [])
                if isinstance(r, dict)
            ],
            "clearance": {
                "richiesta": bool(clearance.get("richiesta")),
                "decisione": _text(clearance.get("decisione")),
                "convertibile": bool(clearance.get("convertibile")),
                "label": _text(clearance.get("label")),
            },
        },
        "barrieraRiservatezza": {
            "id": _text(barriera.get("id")),
            "attiva": bool(barriera.get("attiva")),
            "gestibile": bool(barriera.get("gestibile")),
            "titolo": _text(barriera.get("titolo")),
            "motivazione": _text(barriera.get("motivazione")),
            "label": _text(barriera.get("label")),
            "utentiAutorizzati": [_text(username) for username in list(barriera.get("utenti_autorizzati") or []) if _text(username)],
        },
        "antiriciclaggio": _aml_payload(lead, get_antiriciclaggio),
        "actions": {
            "stato": f"/crm/lead/{lead_id}/stato",
            "verificaConflitti": f"/crm/lead/{lead_id}/verifica-conflitti",
            "aggiorna": f"/crm/lead/{lead_id}/aggiorna",
            "converti": f"/crm/lead/{lead_id}/converti",
            "decisioneConflitto": f"/crm/lead/{lead_id}/conflitti/decisione",
            "creaBarrieraRiservatezza": f"/crm/lead/{lead_id}/barriera-riservatezza",
            "aggiornaBarrieraRiservatezza": f"/crm/lead/{lead_id}/barriera-riservatezza/aggiorna",
            "revocaBarrieraRiservatezza": f"/crm/lead/{lead_id}/barriera-riservatezza/revoca",
        },
    }


def build_react_crm_payload(
    *,
    get_crm: Callable[[], Any],
    get_antiriciclaggio: Callable[[], Any] | None = None,
    operatore: str = "",
    utenti_autorizzabili: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    crm = get_crm()
    pipeline = crm.pipeline()
    visible_pipeline = {
        stato: [
            lead
            for lead in pipeline.get(stato, [])
            if (
                not _is_internal_quality_fixture(lead)
                and crm.accesso_lead_consentito(_text(getattr(lead, "id", "")), operatore=operatore)
            )
        ]
        for stato in STATI_LEAD
    }
    visible_leads = [lead for stato in STATI_LEAD for lead in visible_pipeline[stato]]
    per_fonte: dict[str, int] = {}
    for lead in visible_leads:
        fonte = _text(getattr(lead, "fonte", ""), "altro")
        per_fonte[fonte] = per_fonte.get(fonte, 0) + 1
    vinti = len(visible_pipeline["VINTO"])
    persi = len(visible_pipeline["PERSO"])
    chiusi = vinti + persi
    columns = [
        {
            "stato": stato,
            "label": _STATO_LABEL.get(stato, stato),
            "tone": _STATO_TONE.get(stato, "neutral"),
            "count": len(visible_pipeline[stato]),
            "leads": [
                _lead_payload(lead, get_crm, get_antiriciclaggio, operatore=operatore)
                for lead in visible_pipeline[stato]
            ],
        }
        for stato in STATI_LEAD
    ]
    return {
        "source": "repository_reali",
        "sourceOfTruth": str(getattr(crm, "source_of_truth", "sqlite") or "sqlite"),
        "generatedAt": date.today().isoformat(),
        "contracts": {
            "mock_fallback": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
        },
        "columns": columns,
        "summary": {
            "totale": len(visible_leads),
            "aperti": sum(len(visible_pipeline[stato]) for stato in ("NUOVO", "CONTATTATO", "APPUNTAMENTO", "PREVENTIVO")),
            "vinti": vinti,
            "persi": persi,
            "tassoConversione": round(vinti / chiusi, 2) if chiusi else 0.0,
            "perFonte": [
                {
                    "fonte": fonte,
                    "label": _FONTE_LABEL.get(fonte, fonte),
                    "count": int(count or 0),
                }
                for fonte, count in sorted(per_fonte.items(), key=lambda kv: -int(kv[1] or 0))
            ],
        },
        "options": {
            "fonti": [{"value": fonte, "label": _FONTE_LABEL.get(fonte, fonte)} for fonte in FONTI_LEAD],
            "stati": [
                {"value": stato, "label": _STATO_LABEL.get(stato, stato), "tone": _STATO_TONE.get(stato, "neutral")}
                for stato in STATI_LEAD
            ],
            "prestazioniAml": [
                {"value": value, "label": _PRESTAZIONE_AML_LABEL.get(value, value)}
                for value in (*PRESTAZIONI_IN_AMBITO, PRESTAZIONE_DIFENSIVA)
            ],
            "livelliAml": [
                {"value": "SEMPLIFICATA", "label": "Semplificata"},
                {"value": "ORDINARIA", "label": "Ordinaria"},
                {"value": "RAFFORZATA", "label": "Rafforzata"},
            ],
            "utentiAutorizzabili": [
                {"username": _text(item.get("username")), "label": _text(item.get("label"), _text(item.get("username")))}
                for item in list(utenti_autorizzabili or [])
                if _text(item.get("username"))
            ],
        },
        "actions": {
            "nuovo": "/crm/lead/nuovo",
            "clienti": "/clienti",
            "preventivi": "/preventivi/nuovo",
        },
        "fonteDeontologica": "Verifica conflitti ex artt. 23-24 Codice Deontologico Forense; le barriere informative segregano gli accessi ma non sostituiscono l'astensione; preventivo scritto ex L. 247/2012 art. 13.",
        "accesso": {"operatore": _text(operatore)},
    }
