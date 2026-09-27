"""Pannello di piattaforma (superamministratore) per la shell React.

Le pagine storiche `/admin/*` rendono ciascuna un template costruito su un
«payload» già calcolato dai servizi (`build_system_health_surface`,
`build_studio_installation_status`, …). Qui ogni pagina si traduce in sezioni
tipizzate che un solo componente React sa mostrare:

- `metrics`: indicatori (etichetta, valore, nota, tono);
- `status`: elenco di voci con esito (ok, attenzione, blocco, informazione);
- `table`: tabella con colonne dichiarate e righe (con collegamento facoltativo);
- `facts`: coppie etichetta/valore;
- `notes`: avvisi in testo.

I dati restano quelli dei servizi esistenti: l'adattatore non calcola nulla,
cambia solo la forma. Una pagina nuova si aggiunge con il suo adattatore in
`PAGINE`.
"""

from __future__ import annotations

from typing import Any, Callable

TONI = {"ok": "success", "success": "success", "block": "danger", "danger": "danger", "errore": "danger", "error": "danger", "warning": "warning", "warn": "warning", "info": "info"}


def _t(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "sì" if value else "no"
    return str(value).strip()


def data_ora(value: Any) -> str:
    """Data e ora in formato italiano (gg/mm/aaaa hh:mm) da un valore ISO."""
    from datetime import datetime

    testo = _t(value)
    if not testo:
        return ""
    try:
        momento = datetime.fromisoformat(testo.replace("Z", "+00:00"))
    except ValueError:
        return testo
    if momento.tzinfo is not None:
        from zoneinfo import ZoneInfo

        momento = momento.astimezone(ZoneInfo("Europe/Rome"))
    return momento.strftime("%d/%m/%Y %H:%M")


def _tono(stato: Any) -> str:
    return TONI.get(_t(stato).lower(), "neutral")


def metrics(items: list[dict[str, Any]], title: str = "") -> dict[str, Any]:
    return {"kind": "metrics", "title": title, "items": [{"label": _t(i.get("label")), "value": _t(i.get("value")), "note": _t(i.get("note")), "tone": i.get("tone") or "neutral"} for i in items]}


def status(title: str, items: list[dict[str, Any]], subtitle: str = "") -> dict[str, Any]:
    return {
        "kind": "status",
        "title": title,
        "subtitle": subtitle,
        "items": [
            {"title": _t(i.get("title")), "summary": _t(i.get("summary")), "detail": _t(i.get("detail")), "tone": _tono(i.get("status")), "statusLabel": _t(i.get("statusLabel") or i.get("status")).upper()}
            for i in items
        ],
    }


def table(title: str, columns: list[tuple[str, str]], rows: list[dict[str, Any]], *, subtitle: str = "", empty: str = "Nessun dato.") -> dict[str, Any]:
    return {
        "kind": "table",
        "title": title,
        "subtitle": subtitle,
        "empty": empty,
        "columns": [{"key": k, "label": label} for k, label in columns],
        "rows": [{"cells": {k: _t(r.get(k)) for k, _ in columns}, "href": _t(r.get("_href")), "external": bool(r.get("_external")), "tone": r.get("_tone") or ""} for r in rows],
    }


def facts(title: str, items: list[tuple[str, Any]]) -> dict[str, Any]:
    return {"kind": "facts", "title": title, "items": [{"label": label, "value": _t(value)} for label, value in items if _t(value)]}


def notes(title: str, items: list[Any], tone: str = "warning") -> dict[str, Any]:
    testi = [_t(i) for i in items if _t(i)]
    return {"kind": "notes", "title": title, "tone": tone, "items": testi}


def shortcuts(title: str, items: list[tuple[str, str, str]]) -> dict[str, Any]:
    """Collegamenti alle sezioni del pannello (etichetta, descrizione, indirizzo)."""
    return {"kind": "shortcuts", "title": title, "items": [{"label": label, "detail": detail, "href": href} for label, detail, href in items]}


def link(label: str, href: str, *, tone: str = "neutral", external: bool = False) -> dict[str, Any]:
    return {"label": label, "href": href, "tone": tone, "external": external}


# ------------------------------------------------------------------ adattatori


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


def _elenco(valori: Any, separatore: str = ", ") -> str:
    return separatore.join(_t(v) for v in valori or [] if _t(v))


def cruscotto(payload: dict[str, Any]) -> dict[str, Any]:
    stats = payload.get("stats") or {}
    piani = payload.get("piani") or {}
    totale = int(stats.get("totale") or 0)
    per_piano = stats.get("per_piano") or {}

    def riga_studio(studio: Any, **extra: Any) -> dict[str, Any]:
        return {"name": _t(getattr(studio, "nome", "")), "slug": f"/{_t(getattr(studio, 'slug', ''))}", "state": _t(getattr(studio, "stato", "")), "plan": _t(getattr(studio, "piano", "")), "_href": f"/admin/studi/{_t(getattr(studio, 'slug', ''))}", **extra}

    in_scadenza = [
        riga_studio(s, days=f"{s.giorni_alla_scadenza} giorn{'o' if s.giorni_alla_scadenza == 1 else 'i'}", _tone="warning")
        for s in payload.get("in_scadenza") or []
    ]
    return {
        "title": "Panoramica della piattaforma",
        "subtitle": "Studi legali della piattaforma, piani, scadenze e accesso rapido alle sezioni di governo.",
        "links": [link("Nuovo studio", "/admin/studi/nuovo", tone="primary"), link("Tutti gli studi", "/admin/studi")],
        "sections": [
            metrics([
                {"label": "Studi totali", "value": totale},
                {"label": "Attivi", "value": stats.get("attivi", 0), "tone": "success"},
                {"label": "In prova", "value": stats.get("trial", 0), "tone": "warning" if stats.get("trial") else "neutral"},
                {"label": "Sospesi o scaduti", "value": int(stats.get("sospesi") or 0) + int(stats.get("scaduti") or 0), "tone": "danger" if (stats.get("sospesi") or stats.get("scaduti")) else "neutral"},
            ]),
            table("Scadenze nei prossimi 14 giorni", [("name", "Studio"), ("days", "Scade tra"), ("plan", "Piano")], in_scadenza, empty="Nessuno studio in scadenza nei prossimi 14 giorni."),
            table(
                "Distribuzione dei piani",
                [("plan", "Piano"), ("count", "Studi"), ("share", "Quota")],
                [
                    {"plan": _t((info or {}).get("nome") if isinstance(info, dict) else getattr(info, "nome", chiave)) or chiave, "count": per_piano.get(chiave, 0), "share": f"{int(per_piano.get(chiave, 0) / totale * 100) if totale else 0}%"}
                    for chiave, info in piani.items()
                ],
            ),
            table("Studi recenti", [("name", "Studio"), ("slug", "Indirizzo"), ("state", "Stato"), ("plan", "Piano")], [riga_studio(s) for s in (payload.get("studi") or [])[:8]], empty="Nessuno studio registrato."),
            shortcuts("Sezioni del pannello", [
                ("Utente di piattaforma", "Account unico di superamministratore, separato dagli utenti degli studi.", "/admin/utenti-piattaforma"),
                ("Stato installazione", "Avvio dello studio, avvisi e blocchi in una schermata.", "/admin/stato-installazione"),
                ("Assistente migrazione", "Clienti, fascicoli, agenda, scadenze e documenti da importare.", "/admin/assistente-migrazione"),
                ("Salute del sistema", "Latenze, OCR, AI locale, scheduler e backup.", "/admin/salute-sistema"),
                ("Server e manutenzione", "Consumi per studio, compattazione sicura e spazio di produzione.", "/admin/server-manutenzione"),
                ("Assistenza remota", "Schermo, audio, chat tecnica e controllo avanzato dal superamministratore.", "/admin/supporto-remoto"),
                ("Valutazione di Lex", "Casi di prova, criteri e indicatori di qualità.", "/admin/lex-scorecard"),
                ("Copertura AI", "Verifica automatica, lacune, bozze, revisione e pubblicazione.", "/admin/copertura-ai/"),
            ]),
        ],
    }


def governance(payload: dict[str, Any]) -> dict[str, Any]:
    titolo_riga = lambda testo, nota: f"{_t(testo)} — {_t(nota)}" if _t(nota) else _t(testo)  # noqa: E731
    headline = payload.get("headline") or {}
    runtime = payload.get("runtime") or {}
    backend = payload.get("backend_policy") or {}
    studio = backend.get("selected_studio") or {}
    storage = payload.get("storage") or {}
    autorizzazioni = payload.get("authorization") or {}
    migrazione = payload.get("migration") or {}
    golden = payload.get("golden_paths") or {}
    golden_sommario = golden.get("summary") or {}
    osservabilita_prodotto = payload.get("observability") or {}
    catalogo = (autorizzazioni.get("permission_catalog") or {})
    studi = payload.get("studios") or []
    return {
        "title": "Governance del prodotto",
        "subtitle": "Archivi della piattaforma, archivio effettivo dello studio, modello delle autorizzazioni, migrazione, percorsi certificati, audit e osservabilità.",
        "filter": {
            "name": "slug",
            "label": "Studio",
            "value": next((_t(x.get("slug")) for x in studi if x.get("selected")), ""),
            "options": [{"value": _t(x.get("slug")), "label": f"{_t(x.get('nome'))} · {_t(x.get('slug'))} · {_t(x.get('selected_mode'))}"} for x in studi],
        } if studi else None,
        "sections": [
            metrics([
                {"label": "Domini di archivio censiti", "value": headline.get("storage_domains", 0), "note": "Matrice tecnica modulo per modulo."},
                {"label": "Domini pronti per PostgreSQL", "value": headline.get("postgres_rw_ready", 0), "note": "Lettura e scrittura disponibili."},
                {"label": "Superfici autorizzative", "value": headline.get("authorization_surfaces", 0), "note": "Ruoli, studi, pannello, telematico e AI."},
                {"label": "Eventi di audit", "value": headline.get("audit_events", 0), "note": f"Archivio della piattaforma: {_t(runtime.get('storage_default_label')) or 'n.d.'}"},
            ]),
            status("Archivio effettivo dello studio", [{
                "title": backend.get("alignment_label"),
                "summary": backend.get("policy_title"),
                "detail": backend.get("alignment_detail"),
                "status": backend.get("alignment_status") or "info",
                "statusLabel": backend.get("effective_backend_label"),
            }]) if backend else notes("Archivio effettivo dello studio", ["Nessuno studio con archivio dedicato disponibile."], tone="info"),
            facts("Studio selezionato", [
                ("Studio", _t(studio.get("nome")) or "Nessuno studio selezionato"),
                ("Indirizzo", studio.get("slug")),
                ("Modalità configurata", backend.get("selected_mode_label")),
                ("Archivio effettivo", backend.get("effective_backend_label")),
                ("Domini allineati", f"{backend.get('aligned_domains', 0)}/{backend.get('structured_domains_total', 0)}" if backend else ""),
                ("Regola di lettura", backend.get("policy_detail")),
            ]),
            table("Eccezioni architetturali dichiarate", [("label", "Eccezione"), ("detail", "Motivo")], list(backend.get("explicit_exceptions") or []), empty="Nessuna eccezione dichiarata."),
            table(
                "Matrice degli archivi della piattaforma",
                [("module", "Dominio e modulo"), ("json_mode", "JSON"), ("sqlite_mode", "SQLite"), ("postgres_mode", "PostgreSQL"), ("postgres_parity", "Parità PostgreSQL"), ("migration_wave", "Fase"), ("fallback_mode", "Ripiego"), ("checks", "Controlli di coerenza")],
                [
                    {**r, "module": f"{_t(r.get('domain'))} · {_t(r.get('label'))} ({_t(r.get('source_of_truth'))})", "checks": f"{_t(r.get('parity_note'))} {_elenco(r.get('consistency_checks'), ' | ')}".strip(), "_tone": "success" if r.get("postgres_parity") == "parita' completa" else "warning" if r.get("postgres_parity") == "parita' parziale" else ""}
                    for r in storage.get("rows") or []
                ],
                subtitle=f"SQLite pronti in lettura e scrittura: {_t((storage.get('summary') or {}).get('sqlite_rw_ready')) or '0'}. Capacità tecnica per modulo: non sostituisce l'archivio effettivo dello studio.",
            ),
            table(
                "Superfici autorizzative",
                [("surface", "Superficie"), ("scope", "Ambito"), ("risk", "Rischio"), ("roles", "Ruoli ammessi")],
                [{"surface": titolo_riga(x.get("label"), x.get("note")), "scope": x.get("scope"), "risk": x.get("risk"), "roles": _elenco(x.get("allowed_roles")), "_tone": "danger" if x.get("risk") == "critico" else "warning" if x.get("risk") == "alto" else ""} for x in autorizzazioni.get("surfaces") or []],
            ),
            facts(
                f"Catalogo dei permessi ({_t((autorizzazioni.get('summary') or {}).get('permission_families')) or '0'} famiglie)",
                [(_t(categoria), _elenco(_t(i.get("key")) for i in voci or [])) for categoria, voci in (catalogo.items() if isinstance(catalogo, dict) else [])],
            ),
            status(
                f"Migrazione JSON / SQLite verso PostgreSQL ({_t((migrazione.get('summary') or {}).get('phases_total')) or '0'} fasi)",
                [
                    {"title": f"{_t(f.get('phase_id'))} · {_t(f.get('title'))}", "summary": f.get("objective"), "detail": f"Condizioni di ingresso: {_elenco(f.get('entry_criteria'), ' | ')} · Controlli: {_elenco(f.get('consistency_checks'), ' | ')} · Ripiego: {_elenco(f.get('fallback_rules'), ' | ')}", "status": "info", "statusLabel": _t(f.get("phase_id"))}
                    for f in migrazione.get("phases") or []
                ],
            ),
            table(
                "Percorsi certificati (golden path)",
                [("label", "Flusso"), ("criticality", "Criticità"), ("surfaces", "Superfici"), ("tests", "Test"), ("state", "Stato")],
                [
                    {"label": titolo_riga(r.get("label"), r.get("business_outcome")), "criticality": r.get("criticality"), "surfaces": _elenco(r.get("surfaces")), "tests": _elenco(r.get("pytest_selectors")), "state": " · ".join(x for x in (_t(r.get("status_label")), data_ora(r.get("completed_at")), f"{r.get('duration_seconds')} s" if r.get("duration_seconds") else "") if x), "_tone": "success" if r.get("status") == "passed" else "danger" if r.get("status") == "failed" else ""}
                    for r in golden.get("rows") or []
                ],
                subtitle=(
                    f"Superati {golden_sommario.get('passed', 0)} su {golden_sommario.get('paths_total', 0)} · ultima esecuzione {data_ora(golden_sommario.get('last_generated_at'))}"
                    if golden_sommario.get("last_generated_at")
                    else "Nessuna esecuzione registrata: il comando «iusentra golden-path» produce il rapporto."
                ),
            ),
            table(
                "Flussi presidiati da capo a fondo",
                [("label", "Flusso"), ("coverage", "Copertura"), ("systems", "Sistemi"), ("tests", "Test")],
                [{"label": r.get("label"), "coverage": r.get("coverage"), "systems": _elenco(r.get("systems")), "tests": _elenco(r.get("test_refs")), "_tone": "success" if r.get("coverage") == "integrato" else ""} for r in (payload.get("e2e") or {}).get("rows") or []],
            ),
            table(
                "Ultimi eventi di audit",
                [("action", "Azione"), ("outcome", "Esito"), ("when", "Quando"), ("who", "Chi e cosa")],
                [{"action": e.get("azione"), "outcome": e.get("esito"), "when": data_ora(e.get("timestamp")) or "n.d.", "who": " · ".join(x for x in (_t(e.get("username")) or "sistema", _t(e.get("risorsa_tipo")), _t(e.get("risorsa_id"))) if x)} for e in payload.get("recent_audit") or []],
                empty="Nessun evento di audit disponibile.",
            ),
            table(
                "Osservabilità e audit come funzioni del prodotto",
                [("label", "Funzione"), ("surface", "Superficie"), ("sources", "Sorgenti"), ("outcome", "Risultato"), ("audit_depth", "Tracciamento"), ("status", "Stato")],
                [{**r, "sources": _elenco(r.get("sources"))} for r in osservabilita_prodotto.get("rows") or []],
                subtitle=f"Funzioni: {_t((osservabilita_prodotto.get('summary') or {}).get('capabilities_total')) or '0'}",
            ),
        ],
    }


def _costruttori() -> dict[str, Callable[[], dict[str, Any]]]:
    """I servizi che calcolano i dati delle pagine (importati solo quando servono)."""

    def installazione() -> dict[str, Any]:
        from web.services.studio_installation_status import build_studio_installation_status

        return build_studio_installation_status()

    def salute() -> dict[str, Any]:
        from web.services.system_health_surface import build_system_health_surface

        return build_system_health_surface()

    def siti() -> dict[str, Any]:
        from flask import request

        from web.services.studio_site_runtime import build_platform_sites_payload

        return build_platform_sites_payload(query=str(request.args.get("q") or "").strip())

    def scorecard() -> dict[str, Any]:
        from web.services.lex_eval_scorecard import build_lex_eval_scorecard

        return build_lex_eval_scorecard()

    def osservabilita_dati() -> dict[str, Any]:
        from web.services.observability_runtime import build_observability_payload

        from flask import current_app

        return build_observability_payload(current_app._get_current_object())

    def cruscotto_dati() -> dict[str, Any]:
        from web.blueprints.admin import PIANI, _tenant_manager

        tm = _tenant_manager()
        tm.verifica_scadenze()
        studi = tm.lista()
        in_scadenza = [s for s in studi if s.giorni_alla_scadenza is not None and 0 < s.giorni_alla_scadenza <= 14]
        return {"studi": studi, "stats": tm.statistiche(), "in_scadenza": in_scadenza, "piani": PIANI}

    def governance_dati() -> dict[str, Any]:
        from flask import request

        from web.services.product_governance_surface import build_product_governance_surface

        return build_product_governance_surface(selected_slug=str(request.args.get("slug") or ""))

    return {"cruscotto": cruscotto_dati, "governance": governance_dati, "stato-installazione": installazione, "salute-sistema": salute, "siti-studio": siti, "lex-scorecard": scorecard, "osservabilita": osservabilita_dati}


# Indirizzo di ogni pagina: le rotte storiche restano quelle del pannello.
INDIRIZZI = {"cruscotto": "/admin/", "siti-studio": "/admin/siti-studio/"}

PAGINE: dict[str, tuple[str, Callable[[dict[str, Any]], dict[str, Any]]]] = {
    "cruscotto": ("Panoramica", cruscotto),
    "governance": ("Governance del prodotto", governance),
    "stato-installazione": ("Stato installazione", stato_installazione),
    "salute-sistema": ("Salute del sistema", salute_sistema),
    "siti-studio": ("Siti degli studi", siti_studio),
    "lex-scorecard": ("Valutazione di Lex", lex_scorecard),
    "osservabilita": ("Osservabilità", osservabilita),
}


def menu() -> list[dict[str, str]]:
    return [{"key": chiave, "label": etichetta, "href": INDIRIZZI.get(chiave, f"/admin/{chiave}")} for chiave, (etichetta, _) in PAGINE.items()]


def titolo(chiave: str) -> str:
    voce = PAGINE.get(chiave)
    return voce[0] if voce else "Pannello di piattaforma"


def pagina(chiave: str) -> tuple[dict[str, Any], int]:
    voce = PAGINE.get(chiave)
    costruttore = _costruttori().get(chiave)
    if voce is None or costruttore is None:
        return {"ok": False, "message": "Pagina del pannello non trovata."}, 404
    _, adattatore = voce
    corpo = adattatore(costruttore() or {})
    corpo["sections"] = [s for s in corpo.get("sections") or [] if s.get("items") or s.get("rows") or s.get("kind") == "table"]
    visti: set[str] = set()
    corpo["links"] = [c for c in corpo.get("links") or [] if not (c["href"] in visti or visti.add(c["href"]))]
    return {"ok": True, "page": chiave, "menu": menu(), **corpo}, 200


__all__ = ["PAGINE", "data_ora", "menu", "pagina", "titolo"]
