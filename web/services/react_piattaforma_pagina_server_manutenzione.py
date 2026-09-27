"""Pagina «Server e manutenzione» del pannello di piattaforma (React).

Sostituisce la vista storica `/admin/server-manutenzione` (blueprint
`web/blueprints/server_maintenance_admin.py`, template
`web/templates/admin/server_manutenzione.html`). I dati restano quelli di
`build_server_maintenance_surface()`; qui cambia la forma (sezioni tipizzate)
e il lessico, in italiano (`..._server_manutenzione_lessico`).

Le azioni stanno in `..._server_manutenzione_azioni` (stessi servizi e stessi
argomenti degli invii storici) e i loro esiti in `..._server_manutenzione_esiti`.
"""

from __future__ import annotations

from typing import Any

from web.services import react_piattaforma_pagina_server_manutenzione_azioni as azioni
from web.services import react_piattaforma_pagina_server_manutenzione_lessico as lessico
from web.services.react_piattaforma_sezioni import _t, actions, azione, link, metrics, notes, table

it = lessico.it
percorso = lessico.percorso

TONI_VOCE = {"success": "success", "warning": "warning", "danger": "danger"}

CONFERME = {
    "applica-manutenzione-professionale": (
        "Eseguire la manutenzione professionale? Vengono rimossi solo i backup eccedenti, le cartelle degli studi non registrate, "
        "le istantanee temporanee e la memoria temporanea ricostruibile dei servizi."
    ),
    "applica-retention-backup": (
        "Applicare la politica di conservazione dei backup? Gli archivi oltre il numero di copie, i giorni e il tetto configurati "
        "vengono eliminati definitivamente; restano sempre le copie minime previste."
    ),
    "pulisci-log-sistema": "Ridurre i registri di sistema mantenendo solo gli ultimi 256 MiB?",
    "docker-prune": (
        "Pulire la memoria temporanea ricostruibile dei servizi? I dati degli studi non vengono toccati; "
        "la prossima ricostruzione dei servizi sarà più lenta."
    ),
    "backup-ora": (
        "Avviare ora il backup completo del server? Il salvataggio prosegue in secondo piano e può richiedere diversi minuti; "
        "l'esito si legge poi in «Ultimo backup»."
    ),
    "compatta": (
        "Compattare in sicurezza allegati e copie interne di tutti gli studi? I file identici vengono sostituiti da collegamenti "
        "allo stesso contenuto: i percorsi applicativi restano invariati."
    ),
    "applica-compattazione-database": (
        "Compattare gli archivi studio.db? Per tutta la durata il database resta bloccato in scrittura e l'applicativo non risponde: "
        "su un archivio grande sono minuti, non secondi. Lanciarlo quando nessuno sta lavorando."
    ),
    "applica-ottimizzazione-massima": "Ottimizzare allegati e archivi degli studi mantenendo invariati i percorsi applicativi?",
    "elimina-cartelle-escluse": (
        "Eliminare definitivamente le cartelle escluse dal registro degli studi attivi? "
        "Gli archivi degli studi registrati non vengono toccati."
    ),
    "applica-copia-doppia-fascicoli": (
        "Togliere la copia doppia dai fascicoli? Viene riscritto solo il campo dati_json: le colonne con i documenti veri "
        "non vengono toccate e le righe già alleggerite vengono saltate."
    ),
    "pulisci-normativa-globale": (
        "Rimuovere solo i backup duplicati della normativa globale? Archivio Normattiva, indice e sorgenti restano disponibili "
        "per Ricerca legale e Lex."
    ),
    "applica-collegamenti-pec": (
        "Ricollegare le PEC rimaste senza fascicolo? Vengono toccati solo i messaggi che la regola di oggi collega: numero di ruolo "
        "del fascicolo, mittente che è quell'ufficio giudiziario, atto del procedimento. Da quale PEC decorre un termine dipende "
        "da questo collegamento: lanciarlo dopo avere letto l'analisi."
    ),
    "applica-chunk-rag": (
        "Rifare i frammenti dei documenti che ne hanno di inservibili? I file vengono riletti dal disco e reindicizzati: è lavoro "
        "vero sulla macchina. I documenti senza file di partenza restano come sono. Lanciarlo dopo avere letto l'analisi, "
        "e quando nessuno sta lavorando."
    ),
}


def costruisci() -> dict[str, Any]:
    """Payload della pagina, come la rotta storica `dashboard()`."""
    from web.services.server_maintenance_surface import build_server_maintenance_surface

    return build_server_maintenance_surface()


def _pulsante(chiave: str, etichetta: str, tono: str = "neutral") -> dict[str, Any]:
    return azione(chiave, etichetta, tone=tono, confirm=CONFERME.get(chiave, ""))


# ------------------------------------------------------------------ disco, backup e console del server


def _sezioni_disco(payload: dict[str, Any]) -> list[dict[str, Any]]:
    disco = payload.get("disk") or {}
    sintesi = payload.get("summary") or {}
    ultimo = payload.get("last_backup") or {}
    sistema = payload.get("system_info") or {}
    if ultimo.get("found"):
        impronta = "impronta SHA-256 presente" if ultimo.get("checksum") else "senza impronta di controllo"
        backup = {"label": "Ultimo backup", "value": ultimo.get("label"), "note": f"{_t(ultimo.get('size_label'))} — {_t(ultimo.get('count'))} archivi — {impronta}", "tone": "success" if ultimo.get("checksum") else "warning"}
    else:
        backup = {"label": "Ultimo backup", "value": "Nessuno", "note": f"Nessun archivio di backup trovato in {percorso(payload.get('backup_dir'))}", "tone": "warning"}
    if sistema.get("available"):
        carico = " ".join(_t(sistema.get(k)) for k in ("load_1", "load_5", "load_15"))
        memoria = {"label": "Memoria di sistema", "value": f"{_t(sistema.get('mem_percent'))}%", "note": f"{_t(sistema.get('mem_used_label'))} / {_t(sistema.get('mem_total_label'))} — carico {carico}"}
    else:
        memoria = {"label": "Memoria di sistema", "value": "N/D", "note": "Metriche di sistema non disponibili"}
    return [
        metrics([
            {"label": "Disco usato", "value": disco.get("used_label"), "note": f"{_t(disco.get('used_percent'))}% di {_t(disco.get('total_label'))}"},
            {"label": "Spazio libero", "value": disco.get("free_label"), "tone": "success"},
            {"label": "Backup esterni", "value": sintesi.get("backup_external_size_label"), "note": percorso(payload.get("backup_dir"))},
            {"label": "Copie speculari interne", "value": sintesi.get("backup_mirror_size_label"), "note": f"Percorsi analizzati: {_t(sintesi.get('backup_roots'))}"},
        ], title="Disco e backup"),
        metrics([backup, memoria], title="Ultimo backup e memoria"),
    ]


def _sezioni_console(console: dict[str, Any]) -> list[dict[str, Any]]:
    servizi = console.get("docker") or {}
    presidio = "presidio attivo" if console.get("connected") else "presidio parziale"
    return [
        metrics([
            {"label": "Sistema e piattaforma", "value": console.get("outside_tenants_label"), "note": it(console.get("outside_tenants_note"))},
            {"label": "Recupero immediato", "value": console.get("immediate_reclaimable_label"), "note": "Memoria ricostruibile, senza toccare i dati degli studi.", "tone": "success"},
            {"label": "Da verificare", "value": console.get("review_reclaimable_label"), "note": "Istantanee residue e archivi sopra soglia.", "tone": "warning"},
            {"label": "Memoria temporanea dei servizi", "value": servizi.get("build_cache_size_label"), "note": f"Recuperabile: {_t(servizi.get('build_cache_reclaimable_label'))}"},
        ], title=f"Console {_t(console.get('provider_name'))} · {presidio}"),
        table(
            "Composizione fuori dagli studi",
            [("label", "Voce"), ("size", "Spazio"), ("note", "Significato"), ("code", "Codice tecnico")],
            [
                {"label": it(v.get("label")), "size": v.get("size_label"), "note": it(v.get("note")), "code": v.get("code"), "_tone": TONI_VOCE.get(_t(v.get("tone")), "")}
                for v in console.get("outside_breakdown") or []
            ],
            subtitle="Composizione del disco, memoria temporanea dei servizi, dati globali e aree pulibili dal superamministratore.",
        ),
        table(
            "Recupero dello spazio",
            [("label", "Recupero"), ("size", "Spazio"), ("action", "Azione consigliata"), ("note", "Nota")],
            [
                {"label": it(v.get("label")), "size": v.get("size_label"), "action": it(v.get("action")), "note": it(v.get("note")), "_tone": TONI_VOCE.get(_t(v.get("tone")), "")}
                for v in console.get("recovery_items") or []
            ],
        ),
        table(
            "Aree del server",
            [("label", "Area"), ("path", "Percorso"), ("size", "Dimensione"), ("note", "Nota")],
            [
                {"label": it(a.get("label")), "path": percorso(a.get("path")), "size": f"{_t(a.get('size_label'))}{' (stima rapida)' if a.get('estimated') else ''}", "note": it(a.get("note"))}
                for a in console.get("areas") or []
            ],
        ),
    ]


# ------------------------------------------------------------------ manutenzione sicura globale


def _sezioni_manutenzione(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        notes("Manutenzione sicura globale · dati reali", [it(v) for v in payload.get("recommendations") or []], tone="info"),
        actions("Spazio sul disco", [
            _pulsante("analizza-manutenzione-professionale", "Analizza manutenzione", "primary"),
            _pulsante("applica-manutenzione-professionale", "Esegui manutenzione", "danger"),
            _pulsante("analizza-retention-backup", "Analizza conservazione dei backup"),
            _pulsante("applica-retention-backup", "Applica conservazione dei backup", "warning"),
            _pulsante("backup-ora", "Esegui backup ora", "primary"),
            _pulsante("pulisci-log-sistema", "Pulisci registri di sistema"),
            _pulsante("docker-prune", "Pulisci memoria temporanea dei servizi", "danger"),
        ], subtitle="L'analisi della manutenzione legge l'ultimo censimento notturno dello spazio: non lo ricalcola."),
        actions("Archivi degli studi", [
            _pulsante("analizza-compattazione", "Analizza compattazione"),
            _pulsante("compatta", "Compatta tutto in sicurezza", "success"),
            _pulsante("analizza-spazio-database", "Analizza spazio database"),
            _pulsante("applica-compattazione-database", "Compatta database degli studi", "warning"),
            _pulsante("analizza-ottimizzazione-massima", "Analizza ottimizzazione massima"),
            _pulsante("applica-ottimizzazione-massima", "Ottimizza archivi degli studi", "success"),
        ]),
        actions("Cartelle e copie doppie", [
            _pulsante("analizza-cartelle-escluse", "Analizza cartelle escluse"),
            _pulsante("elimina-cartelle-escluse", "Elimina cartelle escluse", "danger"),
            _pulsante("analizza-copia-doppia-fascicoli", "Analizza copia doppia fascicoli"),
            _pulsante("applica-copia-doppia-fascicoli", "Togli copia doppia fascicoli", "warning"),
            _pulsante("analizza-normativa-globale", "Analizza normativa globale"),
            _pulsante("pulisci-normativa-globale", "Pulisci backup Normattiva", "danger"),
        ]),
        actions("Archivio di ricerca e PEC", [
            _pulsante("analizza-collegamenti-pec", "Analizza collegamenti PEC"),
            _pulsante("applica-collegamenti-pec", "Ricollega PEC al fascicolo", "warning"),
            _pulsante("analizza-chunk-rag", "Analizza frammenti dell'archivio di ricerca"),
            _pulsante("applica-chunk-rag", "Rifai i frammenti inservibili", "warning"),
        ]),
    ]


# ------------------------------------------------------------------ consumi per studio


def _elenco_percorsi(voci: list[dict[str, Any]] | None) -> str:
    return "; ".join(f"{_t(v.get('display_path') or v.get('path'))} ({_t(v.get('size_label'))})" for v in (voci or [])[:4])


def _cella_studio(studio: dict[str, Any]) -> str:
    slug = _t(studio.get("registry_slug") or studio.get("slug"))
    chiave = _t(studio.get("canonical_storage_key"))
    parti = [
        _t(studio.get("display_name")) or slug,
        slug + (f" - archivio {chiave}" if chiave and chiave != _t(studio.get("slug")) else ""),
        it(studio.get("storage_status_label")),
        f"File: {_t(studio.get('file_count'))} - cartelle: {_t(studio.get('directory_count'))}",
        "Scansione rapida parziale" if studio.get("scan_truncated") else "",
        percorso(studio.get("path")),
    ]
    return " · ".join(p for p in parti if p)


def _riga_studio(studio: dict[str, Any]) -> dict[str, Any]:
    dominante = studio.get("dominant_category") or {}
    categorie = [c for c in studio.get("categories") or [] if c.get("size_bytes")][:5]
    slug = _t(studio.get("slug"))
    collegamenti = studio.get("links") or {}
    indirizzo_registro = _t(studio.get("registry_slug")) or slug
    return {
        "studio": _cella_studio(studio),
        "total": studio.get("total_label"),
        "dominant": f"{it(dominante.get('label'))} · {_t(dominante.get('size_label'))} - {_t(dominante.get('percent'))}%" if dominante else "Nessun dato",
        "categories": "; ".join(f"{it(c.get('label'))}: {_t(c.get('size_label'))} ({_t(c.get('percent'))}%)" for c in categorie) or "Nessuna area con dati.",
        "paths": _elenco_percorsi(studio.get("top_paths")) or "Nessuna cartella significativa.",
        "files": _elenco_percorsi(studio.get("largest_files")) or "Nessun file rilevante.",
        "advice": " ".join(it(v) for v in (studio.get("recommendations") or [])[:3]),
        "_href": collegamenti.get("detail"),
        "_tone": "warning" if studio.get("scan_truncated") else "",
        "_actions": [
            azione("apri-archivio-studio", "Archivio", params={"slug": indirizzo_registro}, detail=_t(collegamenti.get("database"))),
            azione("analizza-compattazione", "Analizza", tone="primary", params={"slug": slug}),
            azione(
                "compatta",
                "Compatta",
                tone="success",
                params={"slug": slug},
                confirm=(
                    f"Compattare in sicurezza allegati e copie interne dello studio {_t(studio.get('display_name')) or slug}? "
                    "I file identici vengono sostituiti da collegamenti allo stesso contenuto: i percorsi applicativi restano invariati."
                ),
            ),
        ],
    }


def _sezioni_studi(payload: dict[str, Any]) -> list[dict[str, Any]]:
    sintesi = payload.get("summary") or {}
    indicatori = [
        {"label": "Studi attivi", "value": sintesi.get("tenant_count") or "0"},
        {"label": "Spazio degli studi", "value": sintesi.get("tenant_total_size_label")},
        {"label": "Posta degli studi", "value": sintesi.get("tenant_email_size_label")},
        {"label": "Backup degli studi", "value": sintesi.get("tenant_backup_size_label")},
    ]
    if sintesi.get("inactive_tenant_dirs"):
        indicatori.append({"label": "Cartelle escluse", "value": sintesi.get("inactive_tenant_dirs"), "tone": "warning"})
    if sintesi.get("scan_truncated"):
        indicatori.append({"label": "Scansione", "value": "Rapida", "note": "Scansione rapida: usare le analisi mirate per il dettaglio.", "tone": "warning"})
    sezioni = [
        metrics(indicatori, title="Consumi per studio"),
        table(
            "Consumi per studio",
            [
                ("studio", "Studio"),
                ("total", "Totale"),
                ("dominant", "Area dominante"),
                ("categories", "Distribuzione"),
                ("paths", "Cartelle più pesanti"),
                ("files", "File principali"),
                ("advice", "Indicazioni"),
            ],
            [_riga_studio(s) for s in payload.get("tenants") or []],
            subtitle="Solo gli archivi iscritti nel registro degli studi: le cartelle storiche sono escluse dal conteggio.",
            empty="Nessuno studio rilevato nello spazio di archiviazione corrente.",
        ),
    ]
    escluse = payload.get("inactive_tenants") or []
    if escluse:
        sezioni.append(table(
            "Cartelle dati escluse dagli studi attivi",
            [("folder", "Cartella"), ("state", "Stato"), ("size", "Spazio"), ("note", "Nota")],
            [
                {
                    "folder": f"{_t(c.get('slug'))} · {percorso(c.get('path'))}",
                    "state": it(c.get("storage_status_label")),
                    "size": c.get("total_label"),
                    "note": it(c.get("storage_warning")) or "Cartella esclusa dal conteggio operativo.",
                    "_tone": "warning",
                }
                for c in escluse
            ],
            subtitle="Non sono conteggiate come studio operativo. Se restano fuori dal registro degli studi, vanno rimosse con la manutenzione controllata.",
        ))
    return sezioni


def _sezione_aree(payload: dict[str, Any]) -> dict[str, Any]:
    return table(
        "Aree di archiviazione principali",
        [("label", "Area"), ("path", "Percorso"), ("size", "Dimensione"), ("note", "Nota")],
        [{"label": it(a.get("label")), "path": percorso(a.get("path")), "size": a.get("size_label"), "note": it(a.get("note"))} for a in payload.get("areas") or []],
    )


def adatta(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": "Server e manutenzione",
        "subtitle": "Consumi per studio, compattazione dei dati e manutenzioni sicure per prestazioni e spazio su disco.",
        "links": [link("Osservabilità operativa", "/admin/osservabilita")],
        "sections": [
            *_sezioni_disco(payload),
            *_sezioni_console(payload.get("host_console") or {}),
            *_sezioni_manutenzione(payload),
            *_sezioni_studi(payload),
            _sezione_aree(payload),
        ],
    }


def esegui(chiave: str, params: dict[str, str], values: dict[str, str]) -> dict[str, Any]:
    return azioni.esegui(chiave, params, values)


__all__ = ["adatta", "costruisci", "esegui"]
