"""Esiti delle azioni di «Server e manutenzione» come sezioni React.

Ogni funzione riceve l'oggetto che il blueprint storico
`web/blueprints/server_maintenance_admin.py` passava al template
`admin/server_manutenzione.html` (`compaction`, `backup_retention`,
`docker_prune`, `max_optimization`, `inactive_cleanup`,
`professional_maintenance`, `log_cleanup`, `normativa_cleanup`,
`copia_doppia_fascicoli`, `collegamenti_pec`, `chunk_rag`, `spazio_database`)
e restituisce le stesse informazioni del riquadro di esito, in sezioni tipizzate.
"""

from __future__ import annotations

from typing import Any

from web.services import react_piattaforma_pagina_server_manutenzione_lessico as lessico
from web.services.react_piattaforma_sezioni import _t, facts, notes, status, table

it = lessico.it
percorso = lessico.percorso


def _presenza(valore: Any) -> str:
    return "presente" if valore else "non rilevato"


def _errori(risultato: dict[str, Any], chiave: str = "errors") -> list[dict[str, Any]]:
    errori = [it(e) for e in risultato.get(chiave) or [] if _t(e)]
    return [notes("Errori da verificare", errori, tone="danger")] if errori else []


def _per_studio(voci: list[str | None]) -> str:
    """Parti di una riga di riepilogo, separate da virgola (le parti vuote si saltano)."""
    return ", ".join(v for v in voci if v)


# ------------------------------------------------------------------ server e spazio


def manutenzione_professionale(m: dict[str, Any]) -> list[dict[str, Any]]:
    applicata = bool(m.get("applied"))
    backup = m.get("backup_retention") or {}
    escluse = m.get("inactive_tenants") or {}
    istantanea = m.get("temporary_snapshot") or {}
    registri = m.get("system_logs") or {}
    servizi = m.get("docker_prune") or {}
    normativa = m.get("normativa_global") or {}
    return [
        facts("Manutenzione professionale applicata" if applicata else "Analisi della manutenzione professionale", [
            ("Backup eliminabili", f"{_t(backup.get('archives_to_delete')) or '0'} archivi"),
            ("Cartelle escluse", escluse.get("candidates_count") or "0"),
            ("Istantanea temporanea", istantanea.get("bytes_reclaimable_label")),
            ("Registri di sistema", registri.get("after") or registri.get("before")),
            ("Memoria temporanea dei servizi", servizi.get("bytes_reclaimable_label") or servizi.get("bytes_reclaimed_label")),
            ("Normativa globale: backup duplicati", normativa.get("bytes_reclaimable_label")),
            ("Archivio Normattiva attivo", _presenza(normativa.get("live_db_exists"))),
            ("Indice della normativa", _presenza(normativa.get("index_exists"))),
            ("Recuperato" if applicata else "Recuperabile", m.get("bytes_reclaimed_label") if applicata else m.get("bytes_reclaimable_label")),
        ]),
        *_errori(m),
    ]


def normativa_globale(r: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        facts("Pulizia della normativa globale applicata" if r.get("applied") else "Analisi della normativa globale", [
            ("Backup duplicati recuperabili", r.get("bytes_reclaimable_label")),
            ("Percorsi rimossi", r.get("directories_deleted") or "0"),
            ("Spazio recuperato", r.get("bytes_reclaimed_label")),
            ("Archivio Normattiva", _presenza(r.get("live_db_exists"))),
            ("Indice di ricerca", _presenza(r.get("index_exists"))),
            ("Cartella della normativa", percorso(r.get("normativa_root"))),
        ]),
        *_errori(r),
    ]


def pulizia_registri(r: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        facts("Pulizia dei registri di sistema", [
            ("Prima", r.get("before") or "dato non disponibile"),
            ("Dopo", r.get("after") or "dato non disponibile"),
        ]),
        *_errori(r),
    ]


def pulizia_servizi(r: dict[str, Any]) -> list[dict[str, Any]]:
    errore = _t(r.get("error"))
    sezioni = [
        facts(
            "Errore nella pulizia della memoria temporanea dei servizi" if errore else "Pulizia della memoria temporanea dei servizi completata",
            [("Errore", errore), ("Spazio recuperato", r.get("bytes_reclaimed_label"))],
        )
    ]
    uscita = _t(r.get("stdout"))
    if uscita:
        sezioni.append(notes("Dettaglio tecnico del comando", [uscita[-4000:]], tone="info"))
    return sezioni


def avvio_backup(r: dict[str, Any]) -> list[dict[str, Any]]:
    return [facts("Backup avviato in secondo piano", [("Processo", r.get("pid")), ("File di registro dell'avvio", percorso(r.get("log")))])]


def conservazione_backup(r: dict[str, Any]) -> list[dict[str, Any]]:
    regole = r.get("retention") or {}
    interni = r.get("tenant") or {}
    voci: list[tuple[str, Any]] = [
        ("Cartella", percorso(r.get("backup_dir"))),
        ("Archivi analizzati", r.get("backup_archives_scanned") or "0"),
        ("Archivi eliminabili", r.get("archives_to_delete") or "0"),
        ("Archivi rimossi", r.get("archives_deleted") or "0"),
        ("Spazio prima", r.get("bytes_total_before_label")),
        ("Spazio dopo", r.get("bytes_total_after_label")),
        ("Recuperabile", r.get("bytes_reclaimable_label")),
        ("Recuperato", r.get("bytes_reclaimed_label")),
        ("Politica di conservazione", _per_studio([
            f"conserva almeno {_t(regole.get('min_count'))} copie",
            f"massimo {_t(regole.get('count'))} copie",
            f"{_t(regole.get('days'))} giorni",
            f"tetto {_t(regole.get('max_gib'))} GiB",
        ])),
    ]
    if interni:
        voci.append(("Backup interni degli studi", _per_studio([
            f"{_t(interni.get('tenant_backup_roots')) or '0'} cartelle",
            f"{_t(interni.get('archives_to_delete')) or '0'} archivi eliminabili",
            f"copie speculari eliminabili {_t(interni.get('mirror_dirs_to_delete')) or '0'}",
        ])))
    titolo = "Conservazione dei backup applicata" if r.get("applied") else "Analisi della conservazione dei backup"
    return [facts(titolo, voci), *_errori(r)]


def cartelle_escluse(r: dict[str, Any]) -> list[dict[str, Any]]:
    sezioni = [
        facts("Cartelle escluse eliminate" if r.get("applied") else "Analisi delle cartelle escluse", [
            ("Cartelle candidate", r.get("candidates_count") or "0"),
            ("Eliminazioni eseguite", r.get("directories_deleted") or "0"),
            ("Recuperabile", r.get("bytes_reclaimable_label")),
            ("Recuperato", r.get("bytes_reclaimed_label")),
        ])
    ]
    candidate = list(r.get("candidates") or [])[:8]
    if candidate:
        sezioni.append(table(
            "Prime cartelle candidate",
            [("slug", "Cartella"), ("state", "Stato"), ("size", "Spazio")],
            [{"slug": c.get("slug"), "state": it(c.get("status_label")), "size": c.get("size_label"), "_tone": "warning"} for c in candidate],
        ))
    return sezioni + _errori(r)


# ------------------------------------------------------------------ archivi degli studi


def compattazione(c: dict[str, Any]) -> list[dict[str, Any]]:
    studio = _t(c.get("tenant_slug"))
    titolo = ("Compattazione applicata" if c.get("applied") else "Analisi della compattazione") + (f" per {studio}" if studio else "")
    sezioni = [
        facts(titolo, [
            ("Percorsi", c.get("roots_scanned") or "0"),
            ("File analizzati", c.get("files_scanned") or "0"),
            ("Duplicati identici", c.get("duplicate_files") or "0"),
            ("Da compattare", c.get("physical_duplicate_files") or "0"),
            ("Già compattati", c.get("already_hardlinked_files") or "0"),
            ("Compattati ora", c.get("hardlinked_files") or "0"),
            ("Recuperabile", c.get("bytes_reclaimable_label")),
            ("Recuperato", c.get("bytes_reclaimed_label")),
        ])
    ]
    if c.get("duplicate_files") and not c.get("physical_duplicate_files") and not c.get("bytes_reclaimable"):
        sezioni.append(notes("Duplicati già compattati", [
            "I duplicati identici indicati sono già compattati: restano più percorsi applicativi, ma non occupano spazio disco aggiuntivo."
        ], tone="info"))
    return sezioni


def ottimizzazione_massima(o: dict[str, Any]) -> list[dict[str, Any]]:
    from web.services.server_maintenance_surface import human_bytes

    allegati = o.get("compaction") or {}
    posta = o.get("mail_archives") or {}
    archivi = o.get("databases") or {}
    studio = _t(o.get("tenant_slug"))
    titolo = ("Ottimizzazione degli archivi applicata" if o.get("applied") else "Analisi dell'ottimizzazione degli archivi") + (f" per {studio}" if studio else "")
    sezioni = [
        facts(titolo, [
            ("Allegati e copie speculari", _per_studio([
                f"{_t(allegati.get('files_scanned')) or '0'} file analizzati",
                f"{_t(allegati.get('physical_duplicate_files')) or '0'} duplicati da compattare",
                f"recuperabile {_t(allegati.get('bytes_reclaimable_label'))}",
                f"recuperato {_t(allegati.get('bytes_reclaimed_label'))}",
            ])),
            ("Archivi della posta", _per_studio([
                f"{_t(posta.get('mailboxes_scanned')) or '0'} caselle analizzate",
                f"recuperabile {_t(posta.get('bytes_reclaimable_label'))}",
                f"recuperato {_t(posta.get('bytes_reclaimed_label'))}",
            ]) if posta else ""),
            ("Archivi degli studi", _per_studio([
                f"{_t(archivi.get('files_scanned')) or '0'} file analizzati",
                f"{_t(archivi.get('optimized_files')) or '0'} ottimizzabili",
                f"recuperabile {_t(archivi.get('bytes_reclaimable_label'))}",
                f"recuperato {_t(archivi.get('bytes_reclaimed_label'))}",
            ])),
            ("Totale", f"recuperabile {_t(o.get('bytes_reclaimable_label'))} · recuperato {_t(o.get('bytes_reclaimed_label'))}"),
        ])
    ]
    risultati = list(archivi.get("results") or [])[:5]
    if risultati:
        sezioni.append(table(
            "Archivi con più spazio recuperabile",
            [("path", "Archivio"), ("size", "Recuperabile"), ("error", "Errore")],
            [
                {"path": v.get("display_path"), "size": human_bytes(int(v.get("bytes_reclaimable") or 0)), "error": it(v.get("error")), "_tone": "danger" if v.get("error") else ""}
                for v in risultati
            ],
        ))
    return sezioni


def _voce_studio(studio: dict[str, Any], sintesi: str) -> dict[str, Any]:
    errore = _t(studio.get("errore"))
    return {"title": studio.get("studio"), "summary": sintesi, "detail": errore, "status": "danger" if errore else "info", "statusLabel": "Errore" if errore else "Esaminato"}


def spazio_database(r: dict[str, Any]) -> list[dict[str, Any]]:
    voci = []
    for s in r.get("studi") or []:
        sintesi = f"{_t(s.get('su_disco'))} su disco, {_t(s.get('liberabili'))} in pagine libere ({_t(s.get('percento_libero'))}%)"
        if s.get("compattato"):
            sintesi += f" → {_t(s.get('dopo'))}, recuperati {_t(s.get('recuperati'))}"
        voce = _voce_studio(s, sintesi)
        if s.get("saltato") and not voce["detail"]:
            voce.update(detail=f"Saltato: {it(s.get('saltato'))}", status="warning", statusLabel="Saltato")
        elif s.get("compattato"):
            voce.update(status="success", statusLabel="Compattato")
        voci.append(voce)
    eseguita = bool(r.get("compattazione_eseguita"))
    avvisi = [it(r.get("messaggio"))]
    if not eseguita and r.get("gb_liberabili"):
        avvisi.append("Nessuna modifica eseguita. La compattazione blocca il database in scrittura per tutta la durata: lanciarla fuori orario.")
    return [
        notes("Database compattati" if eseguita else "Analisi dello spazio dei database", avvisi, tone="warning" if r.get("errori") else ("success" if eseguita else "info")),
        status("Archivi degli studi", voci),
    ]


# ------------------------------------------------------------------ fascicoli, PEC, archivio di ricerca


def copia_doppia(r: dict[str, Any]) -> list[dict[str, Any]]:
    eseguita = bool(r.get("riscrittura_eseguita"))
    voci = [
        _voce_studio(s, _per_studio([
            f"{_t(s.get('fascicoli'))} fascicoli",
            f"{_t(s.get('da_sgrassare'))} con la copia doppia",
            f"{_t(s.get('mb_in_eccesso'))} MB in eccesso",
            f"{_t(s.get('riscritte'))} righe riscritte" if s.get("riscritte") else None,
        ]))
        for s in r.get("studi") or []
    ]
    avvisi = [it(r.get("messaggio"))]
    if not eseguita and r.get("mb_in_eccesso"):
        avvisi.append("Nessuna modifica eseguita. La riscrittura tocca solo il campo dati_json: le colonne con i documenti restano invariate.")
    return [
        notes("Copia doppia rimossa dai fascicoli" if eseguita else "Analisi della copia doppia dei fascicoli", avvisi, tone="warning" if r.get("errori") else ("success" if eseguita else "info")),
        status("Studi esaminati", voci),
    ]


def collegamenti_pec(r: dict[str, Any]) -> list[dict[str, Any]]:
    eseguito = bool(r.get("ricollegamento_eseguito"))
    voci = [
        _voce_studio(s, _per_studio([
            f"{_t(s.get('esaminati'))} senza fascicolo",
            f"{_t(s.get('collegabili'))} collegabili",
            f"{_t(s.get('ricollegati'))} collegate" if s.get("ricollegati") else None,
            f"{_t(s.get('solo_rg'))} con il solo numero di ruolo",
            f"{_t(s.get('senza_candidato'))} senza candidato",
        ]))
        for s in r.get("studi") or []
    ]
    avvisi = [it(r.get("messaggio"))]
    if not eseguito and r.get("collegabili"):
        avvisi.append("Nessuna modifica eseguita. Il collegamento decide da quale PEC decorre un termine: leggere prima, applicare poi.")
    return [
        notes("PEC ricollegate ai fascicoli" if eseguito else "Analisi dei collegamenti PEC", avvisi, tone="warning" if r.get("errori") else ("success" if eseguito else "info")),
        status("Studi esaminati", voci),
    ]


def frammenti_ricerca(r: dict[str, Any]) -> list[dict[str, Any]]:
    eseguita = bool(r.get("rispezzatura_eseguita"))
    voci = [
        _voce_studio(s, _per_studio([
            f"{_t(s.get('chunk_da_scartare'))} frammenti da scartare su {_t(s.get('chunk_in_attesa'))} in attesa",
            f"{_t(s.get('documenti_coinvolti'))} documenti",
            f"{_t(s.get('documenti_rifatti'))} rifatti" if s.get("documenti_rifatti") else None,
            f"{_t(s.get('documenti_verso_ocr'))} passati all'OCR" if s.get("documenti_verso_ocr") else None,
            f"{_t(s.get('documenti_senza_file'))} senza file di partenza" if s.get("documenti_senza_file") else None,
        ]))
        for s in r.get("studi") or []
    ]
    avvisi = [it(r.get("messaggio"))]
    if eseguita and r.get("documenti_restanti"):
        avvisi.append("La passata si ferma da sola per non farsi interrompere dal server: ripetere l'operazione finché i documenti restanti non arrivano a zero.")
    if not eseguita and r.get("chunk_da_scartare"):
        avvisi.append("Nessuna modifica eseguita. Senza rifarli, quei documenti restano senza niente di ricercabile.")
    titolo = "Frammenti dell'archivio di ricerca rifatti" if eseguita else "Analisi dei frammenti dell'archivio di ricerca"
    return [
        notes(titolo, avvisi, tone="warning" if r.get("errori") else ("success" if eseguita else "info")),
        status("Studi esaminati", voci),
    ]


__all__ = [
    "avvio_backup",
    "cartelle_escluse",
    "collegamenti_pec",
    "compattazione",
    "conservazione_backup",
    "copia_doppia",
    "frammenti_ricerca",
    "manutenzione_professionale",
    "normativa_globale",
    "ottimizzazione_massima",
    "pulizia_registri",
    "pulizia_servizi",
    "spazio_database",
]
