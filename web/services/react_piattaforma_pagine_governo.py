"""Pagine di governo del pannello di piattaforma: panoramica e governance.

Traducono in sezioni i dati della panoramica storica `/admin/` (studi, piani,
scadenze) e della governance del prodotto (`build_product_governance_surface`).
"""

from __future__ import annotations

from typing import Any

from web.services.react_piattaforma_sezioni import (
    _elenco,
    _t,
    data_ora,
    facts,
    link,
    metrics,
    notes,
    shortcuts,
    status,
    table,
)


def costruisci_cruscotto() -> dict[str, Any]:
    from web.blueprints.admin import PIANI, _tenant_manager

    tm = _tenant_manager()
    tm.verifica_scadenze()
    studi = tm.lista()
    in_scadenza = [s for s in studi if s.giorni_alla_scadenza is not None and 0 < s.giorni_alla_scadenza <= 14]
    return {"studi": studi, "stats": tm.statistiche(), "in_scadenza": in_scadenza, "piani": PIANI}


def costruisci_governance(slug: str) -> dict[str, Any]:
    from web.services.product_governance_surface import build_product_governance_surface

    return build_product_governance_surface(selected_slug=slug)


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
    titolo_riga = lambda testo, nota: f"{_t(testo)} — {_t(nota)}" if _t(nota) else _t(testo)
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
