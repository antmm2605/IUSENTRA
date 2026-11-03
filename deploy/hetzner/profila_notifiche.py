"""Profilazione della pagina /notifiche-legali, eseguita DENTRO il container app. Sola lettura.

Misura la stessa funzione dell'endpoint `/api/v1/ui/notifiche-legali/presidi` (`build_presidia_list_payload`)
per le code della pagina, con il repository aperto in sola lettura, e stampa SOLO tempi per fase, chiamate e
conteggi. Conta inoltre, per ogni fascicolo, le ricevute RAC/RdAC che il pannello «Comunicazioni e notifica»
prende dall'archivio delle letture, distinguendo quelle con oggetto di notifica L. 53/1994 nel nome o nel
contesto letto da quelle senza (registro NOT-07). Nessun nome, testo, PEC o identificativo di cliente esce.

Uso sul server:
    docker exec -i iusentra-app python - < deploy/hetzner/profila_notifiche.py
"""

from __future__ import annotations

import cProfile
import functools
import json
import os
import pstats
import sys
import time
from collections import Counter, defaultdict
from typing import Any

MARCATORE = "PROFILA_NOTIFICHE_JSON:"
TEMPI: dict[str, dict[str, float]] = defaultdict(lambda: {"chiamate": 0, "secondi": 0.0})
CODE = {
    "tutte": "",
    "da_esaminare": "DETECTED,NEEDS_REVIEW,NOTIFICATION_CONFIRMED,RECIPIENTS_TO_VERIFY",
    "chiuse": "PROOF_DEPOSITED",
}
_L53 = ("notificazione ai sensi", "legge n. 53", "l. 53", "legge 53", "notifica_id")


def _misura(modulo: Any, nome: str) -> None:
    originale = getattr(modulo, nome)

    @functools.wraps(originale)
    def avvolta(*args: Any, **kwargs: Any) -> Any:
        inizio = time.perf_counter()
        try:
            return originale(*args, **kwargs)
        finally:
            voce = TEMPI[f"{modulo.__name__.rsplit('.', 1)[-1]}.{nome}"]
            voce["chiamate"] += 1
            voce["secondi"] += time.perf_counter() - inizio

    setattr(modulo, nome, avvolta)


def _strumenta() -> None:
    import web.services.notification_legal_terms as termini
    import web.services.notification_presidia_payloads as payloads
    from web import helpers

    for nome in ("_practice_payload", "_presidio_rows", "_query_many", "_user_options", "_status_facets", "_summary", "_document_summary"):
        if hasattr(payloads, nome):
            _misura(payloads, nome)
    for nome in ("termine_lungo_del_fascicolo", "termine_di_notifica_lavoro"):
        _misura(termini, nome)
    for nome in ("get_fascicoli", "get_scadenziario"):
        _misura(helpers, nome)


def _profila_coda(nome: str, stati: str) -> dict[str, Any]:
    from web.services.notification_presidia_payloads import build_presidia_list_payload
    from web.services.notification_presidia_runtime import build_notification_presidio_repository

    TEMPI.clear()
    profilo = cProfile.Profile()
    inizio = time.perf_counter()
    esito: dict[str, Any] = {"coda": nome}
    profilo.enable()
    try:
        repo = build_notification_presidio_repository(read_only=True)
        payload = build_presidia_list_payload(repo, {"status": stati, "limit": "50"})
        items = payload.get("items") or []
        esito["righe"] = len(items)
        esito["fascicoli_distinti"] = len({(i.get("practice") or {}).get("id") for i in items})
    except Exception as exc:
        esito["errore"] = type(exc).__name__
    finally:
        profilo.disable()
    esito["totale_s"] = round(time.perf_counter() - inizio, 3)
    esito["fasi"] = {k: {"chiamate": int(v["chiamate"]), "secondi": round(v["secondi"], 3)}
                     for k, v in sorted(TEMPI.items(), key=lambda kv: kv[1]["secondi"], reverse=True)}
    righe = []
    for (file, riga, funzione), (_cc, chiamate, tt, ct, _c) in pstats.Stats(profilo).stats.items():  # type: ignore[attr-defined]
        if ct >= 0.1:
            righe.append({"funzione": f"{file.replace('/app/', '')}:{riga}:{funzione}", "chiamate": chiamate,
                          "proprio_s": round(tt, 3), "cumulato_s": round(ct, 3)})
    esito["cprofile"] = sorted(righe, key=lambda r: r["cumulato_s"], reverse=True)[:30]
    return esito


def _ricevute_archivio() -> dict[str, Any]:
    """NOT-07: ricevute che il pannello prende solo dall'archivio, con e senza oggetto L. 53 (solo conteggi)."""
    from pct.archivio_letture.presidi import prove_notifica_per_oggetto
    from web.helpers import get_fascicoli
    from web.services.react_fascicoli_bridge import (
        _fatti_archivio,
        _notification_document_haystack,
        _notification_proof_kind_for_document,
    )

    conteggi: Counter = Counter()
    fascicoli_con_sole_senza_l53 = 0
    for fascicolo in list(get_fascicoli().tutti()):
        try:
            fatti = _fatti_archivio(fascicolo, categoria="prova_notifica")
        except Exception:
            conteggi["fascicoli_errore_archivio"] += 1
            continue
        conteggi["fascicoli"] += 1
        prove = prove_notifica_per_oggetto(fatti)
        contesti: dict[str, str] = defaultdict(str)
        for fatto in fatti:
            contesti[fatto.oggetto_id] += " " + str(fatto.contesto or "").lower()
        documenti = {str(getattr(d, "id", "")): d for d in getattr(fascicolo, "documenti", []) or []}
        rac, rdac = {"si": 0, "no": 0}, {"si": 0, "no": 0}
        for oid, voce in prove.items():
            kind = str(voce.get("kind") or "")
            if kind not in {"rac", "rdac"} or voce.get("tipo") not in {"documento", "allegato_pec"}:
                continue
            doc = documenti.get(oid)
            if doc is not None and _notification_proof_kind_for_document(doc):
                conteggi[f"{kind}_dal_nome"] += 1
                continue
            nome = _notification_document_haystack(doc) if doc is not None else ""
            l53_nome = any(t in nome for t in _L53)
            l53_contesto = any(t in contesti[oid] for t in _L53)
            chiave = "si" if (l53_nome or l53_contesto) else "no"
            (rac if kind == "rac" else rdac)[chiave] += 1
            conteggi[f"{kind}_archivio_l53_nome"] += int(l53_nome)
            conteggi[f"{kind}_archivio_l53_solo_contesto"] += int(l53_contesto and not l53_nome)
            conteggi[f"{kind}_archivio_senza_l53"] += int(not (l53_nome or l53_contesto))
        if (rac["no"] or rdac["no"]) and not (rac["si"] or rdac["si"]):
            fascicoli_con_sole_senza_l53 += 1
    conteggi["fascicoli_con_sole_ricevute_senza_l53"] = fascicoli_con_sole_senza_l53
    return dict(conteggi)


def main() -> int:
    sys.path.insert(0, "/app")
    avvio = time.perf_counter()
    from pct.scheduler_worker import create_scheduler_app
    from pct.tenant import GestioneTenant
    from web.services.fascicoli_presidi_runtime import _active_tenants, _attach_tenant_context

    app = create_scheduler_app()
    esito: dict[str, Any] = {"avvio_app_s": round(time.perf_counter() - avvio, 1), "code": []}
    studi = _active_tenants(app)
    _strumenta()
    for nome, stati in CODE.items():
        with app.test_request_context("/api/v1/ui/notifiche-legali/presidi"):
            if studi:
                _attach_tenant_context(GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"]), studi[0])
            esito["code"].append(_profila_coda(nome, stati))
    if os.getenv("PROFILA_RICEVUTE", "1") == "1":
        with app.test_request_context("/api/v1/ui/notifiche-legali"):
            if studi:
                _attach_tenant_context(GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"]), studi[0])
            try:
                esito["ricevute_archivio"] = _ricevute_archivio()
            except Exception as exc:
                esito["ricevute_archivio"] = {"errore": type(exc).__name__}
    print(MARCATORE + json.dumps(esito, ensure_ascii=False, default=str), flush=True)
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
