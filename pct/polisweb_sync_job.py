"""Job periodico di sincronizzazione dei fascicoli dai registri di cancelleria.

Fase 3 del sync Polisweb. Base normativa: consultazione dei registri tramite
i servizi ufficiali del PST (D.M. 44/2011; specifiche DGSIA).

Attivo SOLO sul canale certificato server (P12/PEM configurato nelle
impostazioni dello studio): in quel caso l'autenticazione al PST e' mTLS e
non richiede il PIN dell'avvocato, quindi il giro puo' essere automatico. Con
il solo token PKCS#11 il PIN e' obbligatorio a ogni sessione: il job NON gira
in autonomia (registra un presidio informativo, non un errore) e lo studio usa
"Aggiorna dal registro" quando e' presente.

Fail-closed: le date lette dal registro diventano proposte in BOZZA, mai
termini operativi automatici. Il giro e' idempotente, a lotti piccoli, con
watermark su file di stato per non ripetere lo stesso fascicolo troppo spesso.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

# Non ri-sincronizzare lo stesso fascicolo piu' spesso di questo intervallo,
# anche se il job gira ogni 30 minuti: il registro non cambia cosi' in fretta.
DEFAULT_MIN_RESYNC_MINUTES = 180
# Tetto prudenziale di fascicoli per giro, per rispettare i sistemi ministeriali.
DEFAULT_MAX_PER_RUN = 20

ROME_OFFSET = timezone(timedelta(hours=2))  # riferimento indicativo per il watermark


def studio_auth_mode(config_studio: Any) -> str:
    """Ricava il canale PST dalle impostazioni firma dello studio (standalone).

    Ritorna 'reale' (P12/PEM: automazione possibile), 'pkcs11' (token: manuale),
    'demo'/'' (non configurato).
    """

    try:
        firma = config_studio.config.firma
    except Exception:
        return ""
    try:
        fmt = getattr(firma, "backend_firma_operativo_safe", "nessuno")
    except Exception:
        fmt = "nessuno"
    if fmt == "pkcs11":
        return "pkcs11"
    if fmt in ("p12", "pem"):
        return "reale"
    return "demo"


def _load_state(state_path: str) -> dict[str, Any]:
    try:
        with open(state_path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state(state_path: str, state: dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(os.path.abspath(state_path)), exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False)
    except Exception:
        pass


def _fascicolo_sincronizzabile(fascicolo: Any) -> bool:
    """Civile con RG e ufficio noti, non archiviato, sync eventi non disattivato."""

    numero = str(getattr(fascicolo, "numero_rg", "") or "").strip()
    anno = str(getattr(fascicolo, "anno_rg", "") or "").strip()
    ufficio = str(
        getattr(fascicolo, "codice_ufficio_portale", "")
        or getattr(fascicolo, "tribunale", "")
        or ""
    ).strip()
    if not (numero and anno and ufficio):
        return False
    if getattr(fascicolo, "events_sync_enabled", True) is False:
        return False
    stato = str(getattr(getattr(fascicolo, "stato", ""), "value", getattr(fascicolo, "stato", "")) or "")
    if stato.upper() in {"ARCHIVIATO", "CHIUSO"}:
        return False
    return True


def _da_risincronizzare(
    fascicolo_id: str,
    ultimo_iso: str,
    *,
    now: datetime,
    min_minutes: int,
) -> bool:
    if not ultimo_iso:
        return True
    try:
        ultimo = datetime.fromisoformat(ultimo_iso)
    except ValueError:
        return True
    if ultimo.tzinfo is None:
        ultimo = ultimo.replace(tzinfo=now.tzinfo)
    return (now - ultimo) >= timedelta(minutes=min_minutes)


def esegui_sync_polisweb(
    *,
    config_studio: Any,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_scadenziario: Callable[[], Any],
    get_soggetti: Callable[[], Any] | None = None,
    state_path: str,
    now: datetime | None = None,
    min_resync_minutes: int = DEFAULT_MIN_RESYNC_MINUTES,
    max_per_run: int = DEFAULT_MAX_PER_RUN,
    sync_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Un giro del job. Ritorna un report auditabile (mai solleva)."""

    now = now or datetime.now(ROME_OFFSET)
    auth_mode = studio_auth_mode(config_studio)
    if auth_mode != "reale":
        return {
            "ok": True,
            "skipped": True,
            "reason": "presidio_manuale",
            "auth_mode": auth_mode,
            "message": (
                "Sincronizzazione automatica non attiva: configura un certificato "
                "P12/PEM dello studio per il sync dai registri senza PIN, oppure usa "
                "'Aggiorna dal registro' con la smart card."
            ),
            "sincronizzati": 0,
            "proposte": 0,
        }

    if sync_fn is None:
        from web.services.polisweb_fascicolo_sync import sincronizza_fascicolo_da_registro as sync_fn  # noqa: PLC0415

    gestione_fascicoli = get_fascicoli()
    try:
        fascicoli = list(gestione_fascicoli.tutti())
    except Exception:
        fascicoli = []
    candidati = [f for f in fascicoli if _fascicolo_sincronizzabile(f)]

    state = _load_state(state_path)
    visti: dict[str, str] = dict(state.get("last_sync_by_fascicolo") or {})

    da_fare = [
        f for f in candidati
        if _da_risincronizzare(str(getattr(f, "id", "")), visti.get(str(getattr(f, "id", "")), ""), now=now, min_minutes=min_resync_minutes)
    ]
    # I meno recenti prima, per equita' di copertura.
    da_fare.sort(key=lambda f: visti.get(str(getattr(f, "id", "")), ""))
    lotto = da_fare[:max_per_run]

    sincronizzati = 0
    proposte_totali = 0
    errori: list[str] = []
    for fascicolo in lotto:
        fid = str(getattr(fascicolo, "id", "") or "")
        try:
            esito = sync_fn(
                fid,
                get_fascicoli=get_fascicoli,
                get_clienti=get_clienti,
                get_soggetti=get_soggetti,
                get_scadenziario=get_scadenziario,
                auth_mode="reale",
                avvocato_referente="scheduler",
            )
        except Exception as exc:  # pragma: no cover - difensivo
            errori.append(f"{fid}: {str(exc)[:120]}")
            continue
        visti[fid] = now.isoformat()
        if esito.get("ok"):
            sincronizzati += 1
            proposte_totali += int(esito.get("proposte_scadenze") or 0)
        elif esito.get("message"):
            errori.append(f"{fid}: {esito['message'][:120]}")

    state["last_sync_by_fascicolo"] = visti
    state["last_run_at"] = now.isoformat()
    _save_state(state_path, state)

    return {
        "ok": True,
        "skipped": False,
        "auth_mode": auth_mode,
        "candidati": len(candidati),
        "lotto": len(lotto),
        "sincronizzati": sincronizzati,
        "proposte": proposte_totali,
        "errori": errori,
        "message": (
            f"Registri: {sincronizzati}/{len(lotto)} fascicoli allineati, "
            f"{proposte_totali} nuove proposte di scadenza."
        ),
    }
