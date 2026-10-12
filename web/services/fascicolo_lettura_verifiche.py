"""Le verifiche automatiche del fascicolo: i presìdi controllano, l'avvocato decide.

Ogni cosa che un presidio sa fare da solo non deve diventare un compito per
l'avvocato: le ricevute dei depositi le controlla il polling PEC/PDP, le PEC
che citano il numero di ruolo certificato da un ufficio giudiziario si
collegano al fascicolo e passano al presidio PEC (che ne estrae termini e
udienze e li registra), i presidi notifica si riallineano alle prove già nel
fascicolo, i documenti senza testo vengono indicizzati dal presidio
documentale. Questo servizio orchestra quelle verifiche per un fascicolo,
nella coda SQL del lettore (mai nel processo web), non più di una volta ogni
quindici minuti salvo richiesta esplicita, e ne conserva l'esito in un
registro per fascicolo: la lettura lo mostra e propone all'avvocato solo ciò
che resta davvero da decidere.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROME_TZ = ZoneInfo("Europe/Rome")
INTERVALLO_MINUTI = 15
DOMINI_UFFICIALI = ("giustiziacert.it", "giustizia.it", "giustizia-amministrativa.it", "giustiziatributaria.gov.it")
ATTORE = "lettura-fascicolo"

_LOCK = threading.Lock()
logger = logging.getLogger(__name__)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _adesso() -> str:
    return datetime.now(ROME_TZ).isoformat(timespec="seconds")


def _data_it(valore: str) -> str:
    try:
        return datetime.fromisoformat(valore).astimezone(ROME_TZ).strftime("%d/%m/%Y ore %H:%M")
    except (TypeError, ValueError):
        return ""


# ── registro degli esiti ───────────────────────────────────────────────────
def registro_path(paths: dict[str, Any] | None, config: dict[str, Any] | None = None) -> Path:
    base = _clean((paths or {}).get("FASCICOLI_DB")) or _clean((config or {}).get("FASCICOLI_DB")) or "./fascicoli/fascicoli.json"
    return Path(base).parent.parent / "intelligence" / "lettura_verifiche.json"


def _leggi_tutto(percorso: Path) -> dict[str, Any]:
    try:
        return json.loads(percorso.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}


def leggi_registro(fascicolo_id: str, *, paths: dict[str, Any] | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    from pct.discordanze_letture_repository import RegistroDiscordanze
    from web.services.registro_letture_runtime import registro_per_percorsi, tenant_corrente

    registro = registro_per_percorsi(paths)
    tenant = tenant_corrente()
    record, _ = RegistroDiscordanze(registro).esito(tenant,_clean(fascicolo_id))
    if record:
        record["eseguita_il_it"] = _data_it(record.get("eseguita_il", ""))
    record["in_corso"] = bool(record.get("in_corso")) or registro.presidi_in_corso(tenant, _clean(fascicolo_id))
    return record


def scrivi_registro(fascicolo_id: str, record: dict[str, Any], *, paths: dict[str, Any] | None = None, config: dict[str, Any] | None = None) -> None:
    from pct.discordanze_letture_repository import RegistroDiscordanze
    from web.services.registro_letture_runtime import registro_per_percorsi, tenant_corrente

    RegistroDiscordanze(registro_per_percorsi(paths)).pubblica_esito(tenant_corrente(),_clean(fascicolo_id),record)
    percorso = registro_path(paths, config)
    with _LOCK:
        tutto = _leggi_tutto(percorso)
        tutto[_clean(fascicolo_id)] = {chiave: valore for chiave, valore in record.items() if chiave != "in_corso"}
        percorso.parent.mkdir(parents=True, exist_ok=True)
        try:
            percorso.write_text(json.dumps(tutto, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            logger.warning("Mirror JSON degli esiti non aggiornato; esito conservato in SQL per %s", fascicolo_id)


def verifiche_necessarie(record: dict[str, Any], *, forza: bool = False) -> bool:
    if forza:
        return True
    if record.get("in_corso"):
        return False
    try:
        ultima = datetime.fromisoformat(str(record.get("eseguita_il") or ""))
    except (TypeError, ValueError):
        return True
    return datetime.now(ROME_TZ) - ultima > timedelta(minutes=INTERVALLO_MINUTI)


# ── le singole verifiche ───────────────────────────────────────────────────
def _mittente_ufficiale(indirizzo: str) -> bool:
    testo = _clean(indirizzo).lower()
    return any(dominio in testo for dominio in DOMINI_UFFICIALI)


def _profilo_da_ufficio_giudiziario(messaggio: dict[str, Any]) -> bool:
    profilo = dict(messaggio.get("procedural_profile") or {})
    testo = " ".join(
        _clean(profilo.get(chiave)).lower()
        for chiave in (
            "ufficio",
            "codice_ufficio",
            "cancelleria",
            "giudice",
            "numero_rg",
            "oggetto_evento",
            "descrizione_evento",
        )
    )
    if not _clean(profilo.get("numero_rg")):
        return False
    ha_ufficio = bool(
        _clean(profilo.get("codice_ufficio"))
        or "ufficio giudiziario" in testo
        or "tribunale" in testo
        or "corte" in testo
        or "giudice" in testo
        or "cancelleria" in testo
    )
    ha_atto_processuale = bool(
        _clean(profilo.get("giudice"))
        or _clean(profilo.get("cancelleria"))
        or _clean(profilo.get("oggetto_evento"))
        or _clean(profilo.get("descrizione_evento"))
    )
    return ha_ufficio and ha_atto_processuale


def verifica_pec(fascicolo: Any, *, repository: Any = None) -> dict[str, Any]:
    """Collega le PEC che citano il ruolo con mittente ufficiale e fa ripartire il presidio su di esse."""
    from web.services.fascicolo_pec_presidio import messaggi_pec_per_fascicolo

    if repository is None:
        from web.services.pec_pipeline_runtime import repository_for_current_request

        repository = repository_for_current_request()
    messaggi = messaggi_pec_per_fascicolo(fascicolo, repository=repository)
    from web.services.ricevute_collegamento_esito import collega_ricevute_da_esito

    collegate: list[str] = collega_ricevute_da_esito(fascicolo, messaggi, repository)
    da_confermare: list[dict[str, str]] = []
    for messaggio in messaggi:
        if messaggio.get("collegata"):
            continue
        identity = _identita_pec_per_fascicolo(repository, dict(messaggio.get("procedural_profile") or {}), fascicolo)
        ufficio_dimostrato = _mittente_ufficiale(messaggio.get("from", "")) or _profilo_da_ufficio_giudiziario(messaggio)
        if identity["complete_match"] and messaggio.get("corrispondenza") == "rg" and ufficio_dimostrato:
            if _collega_per_ruolo(
                repository,
                messaggio["id"],
                _clean(getattr(fascicolo, "id", "")),
                fascicolo=fascicolo,
                motivo="identità congiunta del procedimento verificata dalla fonte",
            ):
                collegate.append(messaggio["id"])
                continue
        da_confermare.append({"id": messaggio["id"], "oggetto": messaggio.get("subject", ""), "corrispondenza": messaggio.get("corrispondenza", ""),
                             "mime_sha256": messaggio.get("mime_sha256", ""), "identity_evidence": identity,
                             "motivo": "; ".join(identity["conflicts"]) or ("Provenienza dall’ufficio giudiziario non dimostrata." if not ufficio_dimostrato else "Fonte o collegamento cambiati durante la verifica.")})
    eseguiti = 0
    if collegate:
        try:
            esito = repository.run_pending_jobs(limit=max(4, 3 * len(collegate)), actor=ATTORE)
            eseguiti = int(esito.get("processed") or 0)
        except Exception as exc:  # il collegamento resta valido anche se il worker non gira ora
            logger.warning("Presidio PEC: job non eseguiti subito per %s: %s", getattr(fascicolo, "id", ""), exc)
        try:
            from web.services.registro_letture_runtime import pec_collegata

            pec_collegata(_clean(getattr(fascicolo, "id", "")))
        except Exception as exc:
            logger.debug("Registro letture non aggiornato dopo il collegamento PEC: %s", exc)
    return {"esaminate": len(messaggi), "collegate": len(collegate), "job_eseguiti": eseguiti, "da_confermare": da_confermare}


def _identita_pec_per_fascicolo(repository: Any, profile: dict[str, Any], fascicolo: Any) -> dict[str, Any]:
    from pct.pec_case_identity import case_identity_evidence
    from pct.clienti import GestioneClienti
    from pct.codice_fiscale import _checksum

    cf = re.sub(r"\s+", "", str(profile.get("codice_fiscale_cliente") or "")).upper()
    client = {}
    cf_valid = not cf or (GestioneClienti.valida_cf(cf) and _checksum(cf[:15]) == cf[15])
    if re.fullmatch(r"[0-9]{11}", cf):
        from web.services.applicazioni_runtime import _validate_partita_iva

        cf_valid = _validate_partita_iva(cf)
    if cf and cf_valid:
        studio_db = repository._studio_db_for_data_path(repository.fascicoli_db_path)
        if studio_db is not None:
            clients = studio_db.fetchall_readonly("SELECT codice_fiscale FROM clienti WHERE id=?", (_clean(getattr(fascicolo, "id_cliente", "")),))
            client = dict(clients[0]) if clients else {}
    identity = case_identity_evidence(profile, fascicolo, client)
    for key, label in (("rg_match", "R.G. completo di numero e anno"), ("client_name_match", "nome e cognome del cliente"), ("office_match", "ufficio giudiziario")):
        if not identity[key]:
            identity["conflicts"].append(f"Non dimostrato dalla fonte: {label}.")
    if not cf_valid:
        identity["conflicts"].append("Codice fiscale della parte non valido.")
    elif cf and not identity["client_tax_code_match"]:
        identity["conflicts"].append("Codice fiscale della parte senza riscontro concordante in anagrafica.")
    identity["complete_match"] = not identity["conflicts"]
    return identity


def _collega_per_ruolo(repository: Any, message_id: str, fascicolo_id: str, *, fascicolo: Any = None, motivo: str = "identità congiunta del procedimento") -> bool:
    from pct.pec_pipeline import canonical_json, iso_now
    import uuid

    try:
        if fascicolo is None or _clean(getattr(fascicolo, "id", "")) != fascicolo_id:
            return False
        with repository.connect() as conn:
            row = conn.execute(
                "SELECT linked_fascicolo_id,mime_sha256 FROM pec_messages WHERE tenant_id=? AND id=?",
                (repository.tenant_id, message_id),
            ).fetchone()
            if row is None or row["linked_fascicolo_id"] not in ("", None, fascicolo_id):
                return False
            if row["linked_fascicolo_id"] == fascicolo_id:
                return True
            parsed = repository.latest_parsed_row(conn, message_id)
            if parsed is None:
                return False
            profile = dict((json.loads(parsed["parsed_json"] or "{}") or {}).get("procedural_profile") or {})
            identity = _identita_pec_per_fascicolo(repository, profile, fascicolo)
            if not identity["complete_match"]:
                return False
            versione = parsed["id"]
            changed = conn.execute(
                "UPDATE pec_messages SET linked_fascicolo_id=?, linked_fascicolo_score=?, status=? "
                "WHERE tenant_id=? AND id=? AND COALESCE(linked_fascicolo_id,'')='' AND mime_sha256=? "
                "AND ?=(SELECT id FROM pec_parsed_versions WHERE message_id=? ORDER BY version DESC LIMIT 1)",
                (fascicolo_id, 1.0, "linked", repository.tenant_id, message_id, row["mime_sha256"], versione, message_id),
            ).rowcount
            if changed != 1:
                return False
            conn.execute(
                "INSERT INTO pec_fascicolo_links (id, message_id, parsed_version_id, fascicolo_id, score, status, seeds_json, candidates_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, message_id, versione, fascicolo_id, 1.0, "ruolo_certificato_ufficio", canonical_json({"rg": motivo, "identity_evidence": identity}), canonical_json([{"id": fascicolo_id, "score": 1.0, "reasons": [motivo], "identity_evidence": identity}]), iso_now()),
            )
            repository.append_audit(conn, action="pec.fascicolo.collegata_dalla_lettura", resource_type="pec_message", resource_id=message_id, payload={"fascicolo_id": fascicolo_id, "motivo": motivo}, actor=ATTORE)
            if versione:
                repository.enqueue_job(conn, "validate", message_id=message_id, priority=20, actor=ATTORE)
        return True
    except Exception as exc:
        logger.warning("Presidio PEC: collegamento non riuscito per %s: %s", message_id, exc)
        return False


def verifica_notifiche(fascicolo_id: str) -> dict[str, Any]:
    """Riallinea i presidi notifica aperti alle prove già nel fascicolo."""
    from web.services.notification_presidia_fascicolo_reconciliation import reconcile_presidio_with_fascicolo_notification_proof
    from web.services.notification_presidia_payloads import build_presidia_list_payload
    from web.services.notification_presidia_runtime import build_notification_presidio_repository

    repo = build_notification_presidio_repository()
    payload = build_presidia_list_payload(repo, {"fascicolo": fascicolo_id, "limit": 50})
    esaminati = 0
    riallineati = 0
    for voce in list(payload.get("items") or []):
        identificativo = _clean(voce.get("id"))
        if not identificativo:
            continue
        esaminati += 1
        try:
            esito = reconcile_presidio_with_fascicolo_notification_proof(repo, identificativo, actor=ATTORE)
            if esito.get("changed"):
                riallineati += 1
        except Exception as exc:
            logger.warning("Presidio notifiche: riallineamento non riuscito per %s: %s", identificativo, exc)
    return {"esaminati": esaminati, "riallineati": riallineati}


def _contesto_di_sistema(tenant_slug: str = "") -> dict[str, Any]:
    """Il presidio automatico agisce come attore di sistema, come già fanno le API tenant e lo scheduler."""
    return {"user": None, "user_id": ATTORE, "tenant_slug": _clean(tenant_slug), "skip_permission_check": True}


def verifica_documenti(fascicolo_id: str, tenant_slug: str = "") -> dict[str, Any]:
    """Indicizza e cataloga i documenti che il presidio documentale non ha ancora letto."""
    from web.services.document_intelligence_runtime import build_document_catalog_payload, build_lex_indexing_summary_payload

    contesto = _contesto_di_sistema(tenant_slug)
    stato = build_lex_indexing_summary_payload(fascicolo_id, process=False, user_context=contesto, apply_automations=False)
    totale = int(stato.get("total_documents") or 0)
    da_leggere = int(stato.get("not_indexed") or 0) + int(stato.get("queued") or 0) + int(stato.get("stale") or 0)
    if not da_leggere:
        return {"documenti": totale, "letti": int(stato.get("ready") or 0), "indicizzati": 0, "errori": 0, "da_acquisire": 0, "esito": "tutti_letti"}
    riepilogo = build_lex_indexing_summary_payload(fascicolo_id, process=True, retry_errors=False, user_context=contesto, apply_automations=True)
    avvisi = [str(voce or "") for voce in list(riepilogo.get("warnings") or [])]
    non_scaricati = [voce for voce in avvisi if "No such file" in voce or "non trovato" in voce.lower()]
    errori = int(riepilogo.get("errors") or 0)
    try:
        build_document_catalog_payload(fascicolo_id, process=True, user_context=contesto)
    except Exception as exc:
        logger.warning("Catalogo documentale non aggiornato dopo l'indicizzazione di %s: %s", fascicolo_id, exc)
    return {
        "documenti": int(riepilogo.get("total_documents") or totale),
        "letti": int(riepilogo.get("ready") or 0),
        "indicizzati": max(int(riepilogo.get("ready") or 0) - int(stato.get("ready") or 0), 0),
        "errori": max(errori - len(non_scaricati), 0),
        "da_acquisire": len(non_scaricati),
        # I nomi servono alla lettura per dire quali documenti sono censiti ma non scaricati.
        "non_scaricati": [voce.split(":", 1)[0].strip() for voce in non_scaricati][:200],
        "esito": "indicizzazione_eseguita",
    }


def verifica_archivio(fascicolo: Any) -> dict[str, Any]:
    """I due motori dell'archivio leggono ciò che manca (mai ciò che è già letto) e collaudano i fatti."""
    from web.services.archivio_letture_runtime import leggi_fascicolo

    esito = leggi_fascicolo(fascicolo)
    documenti, pec = esito.get("documenti") or {}, esito.get("pec") or {}
    return {
        "documenti_letti": int(documenti.get("letti") or 0), "pec_lette": int(pec.get("letti") or 0),
        "fatti": int(documenti.get("fatti") or 0) + int(pec.get("fatti") or 0),
        "verificati": int(documenti.get("verificati") or 0) + int(pec.get("verificati") or 0),
        "senza_testo": int(documenti.get("senza_testo") or 0), "restano": int(esito.get("restano") or 0),
        "esito": "archivio_aggiornato" if (documenti.get("letti") or pec.get("letti")) else "archivio_invariato",
    }


def verifica_depositi(app: Any, fascicolo: Any, paths: dict[str, Any]) -> dict[str, Any]:
    """Controlla le ricevute dei depositi in corso con il polling PEC/PDP dello studio."""
    pendenti = [
        voce for voce in list(getattr(fascicolo, "depositi_pct", []) or [])
        if _clean(getattr(voce, "stato", "")).upper() in {"INVIATO", "ACCETTATO_PEC", "ACCETTATO", "CONSEGNATO", "CONTROLLI_SUPERATI", "WARN_CONTROLLI"}
    ]
    if not pendenti:
        return {"pendenti": 0, "esito": "nessun_deposito_in_corso"}
    from pct.config_studio import GestioneConfigStudio

    config_pec = None
    try:
        percorso = _clean(paths.get("STUDIO_CONFIG")) or _clean(app.config.get("STUDIO_CONFIG")) or _clean(app.config.get("CONFIG_STUDIO_DB")) or "./config/studio.json"
        config_pec = getattr(GestioneConfigStudio(config_path=percorso).config, "pec", None)
        if config_pec and (not getattr(config_pec, "imap_host", "") or not getattr(config_pec, "indirizzo", "")):
            config_pec = None
    except Exception:
        config_pec = None
    if config_pec is None:
        return {"pendenti": len(pendenti), "esito": "pec_non_configurata"}
    from pct.polling_depositi import esegui_polling
    from web.helpers import get_fascicoli

    try:
        esito = esegui_polling(gf=get_fascicoli(), config_pec=config_pec, credenziali_pdp=None, giorni_indietro=30)
    except Exception as exc:
        return {"pendenti": len(pendenti), "esito": "polling_fallito", "errore": str(exc)[:160]}
    return {"pendenti": len(pendenti), "esito": "controllate", "controllati": int(esito.get("controllati") or 0), "aggiornati": int(esito.get("aggiornati") or 0), "errori": int(esito.get("errori") or 0)}


def lacune_conoscenza_del_fascicolo(fascicolo: Any, scadenze: list[Any]) -> list[dict[str, Any]]:
    from pct.procedura_fasi import lacune_conoscenza

    riferimenti = [_clean(getattr(voce, "titolo", "")) + " " + _clean(getattr(voce, "descrizione", "")) for voce in scadenze]
    return lacune_conoscenza(
        tipo=_clean(getattr(getattr(fascicolo, "tipo", ""), "value", getattr(fascicolo, "tipo", ""))),
        tipo_procedimento=_clean(getattr(fascicolo, "tipo_procedimento", "")),
        canale_operativo=_clean(getattr(fascicolo, "canale_operativo", "")),
        riferimenti=riferimenti,
    )


# ── orchestrazione ─────────────────────────────────────────────────────────
def esegui_verifiche(app: Any, fascicolo_id: str, *, paths: dict[str, Any] | None = None, tenant_slug: str = "") -> dict[str, Any]:
    """Esegue tutte le verifiche nel contesto dell'app (e del tenant) e ne registra l'esito."""
    from flask import g

    fascicolo_id = _clean(fascicolo_id)
    paths = dict(paths or {})
    record: dict[str, Any] = {"eseguita_il": _adesso(), "esiti": {}, "errori": {}}
    with app.test_request_context("/"):
        g.data_paths = paths
        g.tenant = None
        g.tenant_context_slug = tenant_slug
        g.tenant_context_required = False
        g.tenant_context_missing = False
        g.storage_runtime = None
        if tenant_slug and app.config.get("MULTI_TENANT"):
            try:
                from pct.tenant import GestioneTenant

                manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
                g.tenant = manager.get(tenant_slug)
            except Exception:
                g.tenant = None
        from web.helpers import get_fascicoli, get_scadenziario

        fascicolo = get_fascicoli().get(fascicolo_id)
        if fascicolo is None:
            record["errori"]["fascicolo"] = "fascicolo non trovato"
            return record
        passi = (
            ("pec", lambda: verifica_pec(fascicolo)),
            ("notifiche", lambda: verifica_notifiche(fascicolo_id)),
            ("depositi", lambda: verifica_depositi(app, fascicolo, paths)),
            ("documenti", lambda: verifica_documenti(fascicolo_id, tenant_slug)),
            ("archivio", lambda: verifica_archivio(fascicolo)),
        )
        record["in_corso"] = True
        scrivi_registro(fascicolo_id, record, paths=paths, config=app.config)
        for nome, funzione in passi:
            try:
                record["esiti"][nome] = funzione()
            except Exception as exc:
                logger.exception("Verifica automatica %s non completata per %s", nome, fascicolo_id)
                record["errori"][nome] = str(exc)[:200]
        try:
            scadenze = list(get_scadenziario().tutte(id_fascicolo=fascicolo_id, solo_aperte=False))
        except Exception:
            scadenze = []
        try:
            record["lacune_conoscenza"] = lacune_conoscenza_del_fascicolo(fascicolo, scadenze)
        except Exception as exc:
            record["errori"]["conoscenza"] = str(exc)[:200]
        record["completata_il"] = _adesso()
        record["in_corso"] = False
        scrivi_registro(fascicolo_id, record, paths=paths, config=app.config)
    return record


def avvia_verifiche_in_background(app: Any, fascicolo_id: str, *, paths: dict[str, Any] | None = None, tenant_slug: str = "", forza: bool = False) -> bool:
    """Accoda le verifiche nel worker nativo; non forza la rilettura dei documenti."""
    fascicolo_id = _clean(fascicolo_id)
    if not fascicolo_id:
        return False
    record = leggi_registro(fascicolo_id, paths=paths, config=app.config)
    if not verifiche_necessarie(record, forza=forza):
        return False
    from web.services.registro_letture_runtime import registro_per_percorsi, tenant_corrente

    registro = registro_per_percorsi(paths)
    tenant = _clean(tenant_slug) or tenant_corrente()
    return bool(registro.accoda_evento(tenant, fascicolo_id, presidi=True))


__all__ = [
    "INTERVALLO_MINUTI", "avvia_verifiche_in_background", "esegui_verifiche", "lacune_conoscenza_del_fascicolo", "leggi_registro",
    "registro_path", "scrivi_registro", "verifica_archivio", "verifica_depositi", "verifica_documenti", "verifica_notifiche", "verifica_pec", "verifiche_necessarie",
]
