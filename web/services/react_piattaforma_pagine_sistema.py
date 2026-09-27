"""Pagine di sola lettura del pannello di piattaforma: sistema e prodotto.

Stato installazione, salute del sistema, siti degli studi, valutazione di Lex e
osservabilità: gli adattatori traducono i dati dei servizi delle viste storiche
`/admin/*` in sezioni (`react_piattaforma_sezioni`), senza calcolare nulla.
"""

from __future__ import annotations

from typing import Any

from web.services.react_piattaforma_sezioni import _t, data_ora, facts, link, metrics, notes, status, table


def costruisci_installazione() -> dict[str, Any]:
    from web.services.studio_installation_status import build_studio_installation_status

    return build_studio_installation_status()


def costruisci_salute() -> dict[str, Any]:
    from web.services.system_health_surface import build_system_health_surface

    return build_system_health_surface()


def costruisci_siti(query: str) -> dict[str, Any]:
    from web.services.studio_site_runtime import build_platform_sites_payload

    return build_platform_sites_payload(query=query)


def costruisci_scorecard() -> dict[str, Any]:
    from web.services.lex_eval_scorecard import build_lex_eval_scorecard

    return build_lex_eval_scorecard()


def costruisci_osservabilita() -> dict[str, Any]:
    from flask import current_app

    from web.services.observability_runtime import build_observability_payload

    return build_observability_payload(current_app._get_current_object())


def stato_installazione(payload: dict[str, Any]) -> dict[str, Any]:
    contatori = payload.get("counters") or {}
    return {
        "title": "Stato installazione dello studio",
        "subtitle": "Esiti, avvisi, blocchi e prove essenziali in una schermata.",
        "sections": [
            metrics([{"label": etichetta, "value": contatori.get(chiave, 0)} for chiave, etichetta in (("utenti", "Utenti"), ("clienti", "Clienti"), ("fascicoli", "Fascicoli"), ("documenti", "Documenti"), ("agenda", "Agenda"), ("scadenze", "Scadenze"))]),
            status("Avvio dello studio in sei passi", [{"title": s.get("title"), "summary": s.get("summary"), "detail": s.get("detail"), "status": s.get("status")} for s in payload.get("steps") or []]),
            status("Prove di collegamento e configurazione", [{"title": c.get("label"), "summary": c.get("value"), "status": c.get("status")} for c in payload.get("checks") or []]),
            notes("Cosa manca ancora", list(payload.get("warnings") or [])),
        ],
    }


def salute_sistema(payload: dict[str, Any]) -> dict[str, Any]:
    storage = payload.get("storage") or {}
    disco = storage.get("disk") or {}
    lento = payload.get("slow_endpoint_action") or {}
    ai = ((payload.get("local_ai") or {}).get("runtime") or {})
    ocr = payload.get("ocr") or {}
    scheduler = payload.get("scheduler_health") or {}
    lex = payload.get("lex_first_token") or {}
    return {
        "title": "Salute del sistema",
        "subtitle": _t(payload.get("metrics_scope")) or "Latenze, scheduler, OCR, AI locale, backup e spazio disco.",
        "links": [
            link("Dati in formato JSON", "/admin/system-health", external=True),
            link("Server e manutenzione", "/admin/server-manutenzione"),
            link("Osservabilità", "/admin/osservabilita"),
        ],
        "sections": [
            metrics([{"label": c.get("label"), "value": c.get("value"), "note": c.get("detail")} for c in payload.get("cards") or []]),
            table(
                "Spazio disco reale",
                [("label", "Area"), ("value", "Spazio"), ("detail", "Significato")],
                list(storage.get("rows") or []),
                subtitle=f"{disco.get('used_percent') or 0}% usato · misurato il {data_ora(storage.get('sampled_at')) or 'n.d.'} · aggiornamento ogni 5 minuti",
            ),
            table(
                "Endpoint più lenti",
                [("bucket", "Gruppo"), ("avg_ms", "Media (ms)"), ("p95_ms", "P95 (ms)"), ("max_ms", "Massimo (ms)"), ("count", "Campioni")],
                list(payload.get("http_buckets") or []),
                empty="Nessun campione HTTP ancora raccolto.",
            ),
            notes(_t(lento.get("title")) or "Endpoint lenti", [lento.get("detail"), lento.get("action")], tone="info"),
            facts(
                "AI locale, OCR e scheduler",
                [
                    ("Primo token di Lex", f"{lex.get('avg_ms') or 0} ms su {lex.get('count') or 0} campioni"),
                    ("Coda OCR", f"in coda {ocr.get('queue_depth') or ocr.get('in_coda') or 0} · completati {ocr.get('completed') or ocr.get('completati') or 0}"),
                    ("AI locale", _t(ai.get("status_text")) or _t(ai.get("status")) or "non configurata"),
                    ("Scheduler", "attivo" if scheduler.get("ok") else "da verificare"),
                ],
            ),
        ],
    }


def siti_studio(payload: dict[str, Any]) -> dict[str, Any]:
    stats = payload.get("stats") or {}
    righe = []
    for sito in payload.get("sites") or []:
        vetrine = [nome for nome, chiave in (("strumenti", "show_legal_tools"), ("applicazioni", "show_applications"), ("news", "show_legal_news")) if sito.get(chiave)]
        righe.append(
            {
                "site": f"{_t(sito.get('site_name'))} · {_t(sito.get('studio_nome'))}",
                "tenant": sito.get("tenant_slug"),
                "address": f"/web/{_t(sito.get('public_slug'))}/",
                "state": "Pubblicato" if sito.get("is_published") else "Bozza",
                "extras": ", ".join(vetrine) or "nessuna",
                "_href": _t(sito.get("public_url")),
                "_external": True,
                "_tone": "success" if sito.get("is_published") else "",
            }
        )
    return {
        "title": "Siti degli studi",
        "subtitle": "Siti pubblici degli studi della piattaforma, con stato di pubblicazione e sezioni attive.",
        "filter": {"name": "q", "label": "Cerca sito o studio", "value": _t(payload.get("query"))},
        "sections": [
            metrics([
                {"label": "Siti", "value": stats.get("sites", 0)},
                {"label": "Pubblicati", "value": stats.get("published", 0), "tone": "success"},
                {"label": "Contatti ricevuti", "value": stats.get("contacts", 0)},
                {"label": "Prenotazioni da gestire", "value": stats.get("pending_bookings", 0), "tone": "warning" if stats.get("pending_bookings") else "neutral"},
            ]),
            table("Siti", [("site", "Sito e studio"), ("tenant", "Studio"), ("address", "Indirizzo pubblico"), ("state", "Stato"), ("extras", "Sezioni extra")], righe, empty="Nessun sito con questi filtri."),
        ],
    }


def lex_scorecard(payload: dict[str, Any]) -> dict[str, Any]:
    riepilogo = payload.get("summary") or {}
    casi = []
    for caso in payload.get("cases") or []:
        esito = ("passato" if caso.get("passed") else "fallito") if caso.get("measured") else "non misurato"
        fonti = caso.get("sources_useful")
        casi.append(
            {
                "title": f"{_t(caso.get('title'))} ({_t(caso.get('id'))})",
                "area": _t(caso.get("area")).replace("_", " "),
                "result": esito,
                "duration": f"{caso.get('duration_ms')} ms" if caso.get("duration_ms") else "n.d.",
                "sources": "sì" if fonti is True else "no" if fonti is False else "n.d.",
                "warnings": " · ".join(_t(w) for w in caso.get("warnings") or []) or "nessuna",
                "_tone": "success" if esito == "passato" else "danger" if esito == "fallito" else "",
            }
        )
    return {
        "title": "Valutazione di Lex",
        "subtitle": "Casi di prova misurati sulle risposte di Lex: esito, tempi e utilità delle fonti.",
        "sections": [
            metrics([
                {"label": "Casi", "value": riepilogo.get("cases_total", 0)},
                {"label": "Misurati", "value": riepilogo.get("measured_cases", 0)},
                {"label": "Passati", "value": riepilogo.get("passed_cases", 0), "tone": "success"},
                {"label": "Falliti", "value": riepilogo.get("failed_cases", 0), "tone": "danger" if riepilogo.get("failed_cases") else "neutral"},
            ]),
            facts("Misurazione", [("Stato", riepilogo.get("measurement_status_label")), ("Risultati aggiornati", data_ora(riepilogo.get("results_updated_at"))), ("File dei risultati", riepilogo.get("results_path"))]),
            table("Indicatori", [("label", "Indicatore"), ("value", "Valore"), ("target", "Obiettivo"), ("status", "Esito")], [{**k, "_tone": "success" if k.get("status") == "ok" else ""} for k in payload.get("kpi") or []]),
            table(
                "Aree",
                [("area", "Area"), ("titles", "Casi"), ("counts", "Misurati / totale · passati · falliti")],
                [{"area": _t(a.get("area")).replace("_", " "), "titles": " · ".join(_t(x) for x in a.get("titles") or []), "counts": f"{a.get('measured', 0)}/{a.get('count', 0)} · {a.get('passed', 0)} · {a.get('failed', 0)}"} for a in payload.get("areas") or []],
            ),
            table("Criteri di valutazione", [("name", "Criterio"), ("count", "Casi")], [{"name": _t(r.get("name")).replace("_", " "), "count": r.get("count")} for r in payload.get("rubric") or []]),
            table("Casi", [("title", "Caso"), ("area", "Area"), ("result", "Esito"), ("duration", "Durata"), ("sources", "Fonti utili"), ("warnings", "Avvisi")], casi),
            notes("Prossime azioni", [f"{_t(a.get('label'))}: {_t(a.get('detail'))}" for a in payload.get("actions") or []], tone="info"),
        ],
    }


def _voci_json(valore: Any) -> list[tuple[str, Any]]:
    """Coppie leggibili da un dizionario di stato (senza strutture annidate)."""
    if not isinstance(valore, dict):
        return []
    return [(str(k).replace("_", " "), v) for k, v in valore.items() if not isinstance(v, (dict, list))]


def osservabilita(payload: dict[str, Any]) -> dict[str, Any]:
    riepilogo = payload.get("summary") or {}
    storage = payload.get("storage") or {}
    runtime = payload.get("runtime") or {}
    primo_token = ((runtime.get("lex") or {}).get("first_token") or {})
    prodotto = payload.get("product") or {}
    avvisi = []
    for avviso in payload.get("alerts") or []:
        codice = _t(avviso.get("normalized_code") or avviso.get("code"))
        dettagli = [f"Soglia: {_t(avviso.get('threshold'))}" if avviso.get("threshold") else "", _t(avviso.get("operator_message")), f"Come intervenire: {_t(avviso.get('remediation'))}"]
        dettagli += [f"{n}. {_t(passo)}" for n, passo in enumerate(avviso.get("remediation_steps") or [], start=1)]
        avvisi.append(
            {
                "title": " / ".join(x for x in (_t(avviso.get("family")), _t(avviso.get("component")), codice) if x),
                "summary": _t(avviso.get("operator_message")),
                "detail": " · ".join(x for x in dettagli if x),
                "status": "danger" if avviso.get("severity") == "danger" else "warning",
                "statusLabel": "errore" if avviso.get("severity") == "danger" else "attenzione",
            }
        )
    return {
        "title": "Osservabilità",
        "subtitle": "Metriche del processo web, pipeline OCR, AI locale e segnali di degrado con i rimedi.",
        "links": [link("Salute del sistema", "/admin/salute-sistema"), link("Server e manutenzione", "/admin/server-manutenzione")],
        "sections": [
            metrics([
                {"label": "Stato", "value": riepilogo.get("status_label"), "tone": "danger" if riepilogo.get("degraded") else "success", "note": f"errori {riepilogo.get('errors', 0)} · avvisi {riepilogo.get('warnings', 0)}"},
                {"label": "Processo attivo da", "value": f"{runtime.get('uptime_seconds', 0)} s"},
                {"label": "Archivio", "value": storage.get("default_mode"), "note": f"indice: {_t(storage.get('search_index')) or 'non configurato'}"},
                {"label": "Disco", "value": f"{storage.get('disk_used_percent') or 0}% usato", "note": f"liberi {_t(storage.get('disk_free_label')) or 'n.d.'}"},
                {"label": "Primo token di Lex", "value": f"{primo_token.get('avg_ms') or 0} ms", "note": f"P95 {primo_token.get('p95_ms') or 0} ms"},
            ]),
            status("Segnali di degrado", avvisi) if avvisi else notes("Segnali di degrado", ["Processo, OCR, funzioni del prodotto e AI locale coerenti con l'ultima lettura."], tone="success"),
            table(
                "Latenza degli endpoint",
                [("bucket", "Gruppo"), ("count", "Campioni"), ("avg_ms", "Media (ms)"), ("p95_ms", "P95 (ms)"), ("max_ms", "Massimo (ms)")],
                list(((runtime.get("http") or {}).get("buckets") or [])[:12]),
                empty="Nessun campione HTTP ancora raccolto.",
            ),
            facts("AI locale", _voci_json((payload.get("providers") or {}).get("local_ai"))),
            facts("Pipeline OCR", _voci_json(payload.get("ocr"))),
            table(
                "Funzioni del prodotto",
                [("label", "Funzione"), ("surface", "Superficie"), ("audit_depth", "Tracciamento"), ("status", "Stato")],
                list(prodotto.get("capabilities") or []),
                subtitle=f"Eventi di audit: {_t(prodotto.get('audit_events')) or '0'}",
            ),
        ],
    }
