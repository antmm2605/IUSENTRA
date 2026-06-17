"""Profilo deposito telematico precompilato per preventivi, incarichi e fascicoli.

Il profilo nasce nel record operativo SQL/SQLite/PostgreSQL e viaggia lungo
preventivo -> conferimento incarico -> fascicolo. I JSON storici restano solo
mirror o rappresentazioni del record, mai fonte autorevole.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from pct.pst_cifratura import (
    PSTCifraturaError,
    canali_telematici_cifratura_policy,
    risolvi_certificato_cifratura_ufficio,
    valida_canale_telematico_per_cifratura,
)
from pct.uffici_giudiziari import risolvi_ufficio

ROME_TZ = ZoneInfo("Europe/Rome")

CHANNEL_POLICY_BY_OPERATIVE = {
    "PCT": "pct_civile_dm44",
    "PST": "pct_civile_dm44",
    "PCT_CIVILE": "pct_civile_dm44",
    "PCT_LAVORO": "pct_civile_dm44",
    "PCT_TELEMATICO": "pct_civile_dm44",
    "SICID": "pct_civile_dm44",
    "SIECIC": "pct_civile_dm44",
    "PDP": "pdp_penale",
    "PDP_PENALE": "pdp_penale",
    "PENALE": "pdp_penale",
    "PAT": "pat_amministrativo",
    "PAT_AMMINISTRATIVO": "pat_amministrativo",
    "AMMINISTRATIVO": "pat_amministrativo",
    "PTT": "ptt_tributario",
    "PTT_TRIBUTARIO": "ptt_tributario",
    "TRIBUTARIO": "ptt_tributario",
    "SIGIT": "ptt_tributario",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return _text(value).upper().replace("-", "_").replace(" ", "_").replace("/", "_")


def _contains_any(value: str, needles: tuple[str, ...]) -> bool:
    return any(needle in value for needle in needles)


def mappa_canale_deposito(
    *,
    canale_operativo: str = "",
    tipo: str = "",
    area_pratica: str = "",
    tipo_procedimento: str = "",
    source: str = "",
) -> str:
    """Riconduce i canali applicativi alla policy deposito verificabile."""

    for candidate in (canale_operativo, source, tipo, area_pratica, tipo_procedimento):
        normalized = _norm(candidate)
        if not normalized:
            continue
        if normalized in CHANNEL_POLICY_BY_OPERATIVE:
            return CHANNEL_POLICY_BY_OPERATIVE[normalized]
        if _contains_any(normalized, ("PDP", "PENALE")):
            return "pdp_penale"
        if _contains_any(normalized, ("PAT", "AMMINISTRAT", "TAR", "CONSIGLIO_DI_STATO")):
            return "pat_amministrativo"
        if _contains_any(normalized, ("PTT", "TRIBUT", "SIGIT", "CGT", "CPT")):
            return "ptt_tributario"
        if _contains_any(normalized, ("PCT", "PST", "CIVILE", "LAVORO", "SICID", "SIECIC")):
            return "pct_civile_dm44"
    return ""


def _ufficio_payload(
    ufficio: str,
    *,
    tipo_ufficio: str = "",
    pec_ufficio: str = "",
) -> dict[str, Any]:
    testo = _text(ufficio)
    if not testo:
        return {
            "nome": "",
            "tipo": "",
            "codice_iusentra": "",
            "codice_ministero": "",
            "codice_pst": "",
            "pec": _text(pec_ufficio).lower(),
            "pec_verificata": bool(_text(pec_ufficio)),
            "fonte": "",
        }
    try:
        resolved = risolvi_ufficio(testo, tipo=tipo_ufficio or None)
    except Exception:
        resolved = None
    if not resolved:
        return {
            "nome": testo,
            "tipo": _text(tipo_ufficio),
            "codice_iusentra": "",
            "codice_ministero": "",
            "codice_pst": "",
            "pec": _text(pec_ufficio).lower(),
            "pec_verificata": bool(_text(pec_ufficio)),
            "fonte": "inserimento_studio",
        }
    pec = _text(pec_ufficio) or _text(resolved.get("pec_ministero")) or _text(resolved.get("pec"))
    codice_ministero = _text(resolved.get("codice_ministero")) or _text(resolved.get("codice"))
    return {
        "nome": _text(resolved.get("nome")) or testo,
        "tipo": _text(resolved.get("tipo")) or _text(tipo_ufficio),
        "codice_iusentra": _text(resolved.get("codice")),
        "codice_ministero": codice_ministero,
        "codice_pst": codice_ministero,
        "pec": pec.lower(),
        "pec_verificata": bool(pec),
        "fonte": _text(resolved.get("fonte_prevalente")) or "registro_uffici_giudiziari",
    }


def _certificato_payload(
    codice_ufficio: str,
    *,
    richiesto: bool,
    verifica_certificato: bool,
    force_refresh: bool,
) -> dict[str, Any]:
    base = {
        "richiesto": bool(richiesto),
        "verificato": False,
        "codice_ufficio": _text(codice_ufficio),
        "path": "",
        "sha256": "",
        "scadenza": "",
        "fonte": "",
        "errore": "",
    }
    if not richiesto:
        base["verificato"] = True
        return base
    if not codice_ufficio:
        base["errore"] = "Codice ufficio PST mancante."
        return base
    if not verifica_certificato:
        base["errore"] = "Certificato da verificare alla creazione del fascicolo o prima del deposito."
        return base
    try:
        info = risolvi_certificato_cifratura_ufficio(
            codice_ufficio,
            force_refresh=force_refresh,
        )
    except PSTCifraturaError as exc:
        base["errore"] = str(exc)
        return base
    except Exception as exc:
        base["errore"] = f"Verifica certificato non completata: {exc}"
        return base
    payload = asdict(info)
    return {
        "richiesto": True,
        "verificato": True,
        "codice_ufficio": _text(payload.get("codice_ufficio")),
        "path": _text(payload.get("path")),
        "sha256": _text(payload.get("sha256")),
        "scadenza": _text(payload.get("not_valid_after")),
        "fonte": _text(payload.get("source_url")),
        "subject": _text(payload.get("subject")),
        "issuer": _text(payload.get("issuer")),
        "errore": "",
    }


def costruisci_profilo_deposito(
    *,
    id_pratica: str = "",
    area_pratica: str = "",
    tipo_procedimento: str = "",
    tipo: str = "",
    source: str = "",
    canale_operativo: str = "",
    registro_operativo: str = "",
    procedura_operativa_codice: str = "",
    codice_oggetto_pst: str = "",
    fonte_codice_oggetto: str = "",
    file_fonte_codice_oggetto: str = "",
    ufficio: str = "",
    tipo_ufficio: str = "",
    pec_ufficio: str = "",
    verifica_certificato: bool = False,
    force_refresh_certificato: bool = False,
    richiedi_ufficio: bool = False,
    profilo_origine: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Crea il profilo deposito coerente con canale, ufficio e regole tecniche."""

    origine = profilo_origine if isinstance(profilo_origine, dict) else {}
    canale = mappa_canale_deposito(
        canale_operativo=canale_operativo,
        tipo=tipo,
        area_pratica=area_pratica,
        tipo_procedimento=tipo_procedimento,
        source=source,
    )
    if not canale and isinstance(origine.get("canale"), dict):
        canale = _text(origine["canale"].get("codice"))
    policy_map = canali_telematici_cifratura_policy()
    policy = policy_map.get(canale, {})
    validazione = valida_canale_telematico_per_cifratura(canale) if canale else {
        "ok": False,
        "errore": "Canale deposito da determinare.",
        "azione": "Impostare materia, procedura o canale operativo prima del deposito.",
    }
    ufficio_data = _ufficio_payload(ufficio, tipo_ufficio=tipo_ufficio, pec_ufficio=pec_ufficio)
    usa_certificato = bool(policy.get("usa_certificati_pst_cer"))
    certificato = _certificato_payload(
        ufficio_data.get("codice_pst", ""),
        richiesto=usa_certificato,
        verifica_certificato=verifica_certificato,
        force_refresh=force_refresh_certificato,
    )
    blocchi: list[str] = []
    avvisi: list[str] = []
    if not validazione.get("ok"):
        blocchi.append(_text(validazione.get("errore")) or "Canale deposito non riconosciuto.")
    if richiedi_ufficio and not ufficio_data.get("nome"):
        blocchi.append("Autorità giudiziaria destinataria da selezionare.")
    if canale == "pct_civile_dm44":
        if not _text(codice_oggetto_pst):
            blocchi.append("Codice oggetto PST mancante.")
        if richiedi_ufficio and not ufficio_data.get("pec"):
            blocchi.append("PEC ministeriale dell'ufficio non verificata.")
        if richiedi_ufficio and not ufficio_data.get("codice_pst"):
            blocchi.append("Codice ufficio PST mancante.")
        if certificato.get("richiesto") and not certificato.get("verificato"):
            if verifica_certificato:
                blocchi.append(certificato.get("errore") or "Certificato pubblico PST non verificato.")
            else:
                avvisi.append("Certificato pubblico PST da verificare prima del deposito.")
    elif canale in {"pdp_penale", "pat_amministrativo", "ptt_tributario"}:
        avvisi.append("Canale con procedura dedicata: applicare le regole specifiche del portale.")
    stato = "pronto" if not blocchi and (not usa_certificato or certificato.get("verificato") or not verifica_certificato) else "da_verificare"
    if blocchi:
        stato = "bloccato"
    return {
        "versione": 1,
        "generato_il": datetime.now(ROME_TZ).isoformat(timespec="seconds"),
        "timezone": "Europe/Rome",
        "stato": stato,
        "source_of_truth": "sqlite_postgresql_record",
        "json_authoritative": False,
        "struttura_dati": {
            "record_operativo": True,
            "tenant_aware": True,
            "json_solo_mirror": True,
            "source_of_truth": "sqlite_postgresql_record",
            "json_authoritative": False,
        },
        "origine": {
            "profilo_ereditato": bool(origine),
            "stato_origine": _text(origine.get("stato")) if origine else "",
        },
        "pratica": {
            "id_pratica": _text(id_pratica),
            "area_pratica": _text(area_pratica),
            "tipo_procedimento": _text(tipo_procedimento),
            "tipo_fascicolo": _text(tipo),
            "source": _text(source),
            "procedura_operativa_codice": _text(procedura_operativa_codice),
            "registro_operativo": _text(registro_operativo),
        },
        "canale": {
            "codice": canale,
            "nome": _text(policy.get("nome")) or _text(validazione.get("nome")),
            "procedura": _text(validazione.get("procedura")),
            "trasporto": _text(policy.get("trasporto")) or _text(validazione.get("trasporto")),
            "fonte": _text(policy.get("fonte")) or _text(validazione.get("fonte")),
            "fonte_url": _text(policy.get("fonte_url")) or _text(validazione.get("fonte_url")),
        },
        "regole": {
            "usa_certificati_pst_cer": usa_certificato,
            "formati": list(policy.get("formati") or []),
            "firma": _text(policy.get("firma")),
            "limite_dimensione_mb": policy.get("limite_dimensione_mb"),
            "controlli_software": list(policy.get("controlli_software") or []),
        },
        "codice_deposito": {
            "codice_oggetto_pst": _text(codice_oggetto_pst),
            "fonte": _text(fonte_codice_oggetto),
            "file": _text(file_fonte_codice_oggetto),
            "verificato": bool(_text(codice_oggetto_pst)),
        },
        "ufficio": ufficio_data,
        "certificato_cifratura": certificato,
        "blocchi": blocchi,
        "avvisi": avvisi,
    }
