"""Admin database routes extracted from web.app."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date

from flask import Flask, flash, g, jsonify, redirect, render_template, request, send_file, url_for


def register_admin_database_routes(
    app: Flask,
    *,
    get_database: Callable[[], object],
    audit: Callable[..., None],
    latest_sqlite_snapshot_path: Callable[[str], str],
    cfg_data_path: Callable[[str], str],
) -> None:
    """Register admin database inspection, optimization, export, and migration routes."""

    def _problem_payload(problema) -> dict:
        return {
            "livello": problema.severita,
            "modulo": problema.modulo,
            "tipo": problema.tipo,
            "descrizione": problema.messaggio,
            "id_risorsa": problema.id_record,
            "campo": problema.campo,
            "suggerimento": problema.suggerimento,
        }

    def _sqlite_instruction() -> str:
        return (
            "Per ambienti multi-tenant imposta SQLite dal pannello SUPERADMIN dello studio. "
            "Per installazioni single-tenant legacy puoi usare PCT_STORAGE_MODE=SQLITE; "
            "PCT_SQLITE_MODE=1 resta supportato come compatibilità."
        )

    def _sqlite_status_payload(risultato, *, fallback_db: str = "") -> dict:
        totale = sum(risultato.record_migrati.values()) if risultato.record_migrati else 0
        audit_migrazione = risultato.audit or {}
        precheck = audit_migrazione.get("precheck") if isinstance(audit_migrazione, dict) else {}
        reconciliation = audit_migrazione.get("reconciliation") if isinstance(audit_migrazione, dict) else {}
        blockers = list((precheck or {}).get("blockers") or []) if isinstance(precheck, dict) else []
        riconciliata = bool(isinstance(reconciliation, dict) and reconciliation.get("executed"))
        if risultato.riuscita and riconciliata:
            stato = "Eseguita riconciliazione"
            messaggio = (
                "Riconciliazione SQLite completata: il database operativo è rimasto la base, "
                "i record mancanti dalla sorgente sono stati aggiunti senza cancellare quelli già presenti."
            )
            azione = "Controlla eventuali conflitti indicati nel report prima di usare i dati riconciliati."
        elif risultato.riuscita and risultato.avvisi:
            stato = "Completata con avvisi non bloccanti"
            messaggio = "Operazione SQLite completata con avvisi da presidiare."
            azione = "Leggi gli avvisi e conserva il report insieme al backup generato."
        elif risultato.riuscita:
            stato = "Completata"
            messaggio = "Operazione SQLite completata con successo."
            azione = "Puoi usare il database SQLite indicato nel report."
        elif blockers:
            stato = "Bloccata per protezione dati"
            messaggio = (
                "Attivazione SQLite bloccata: il database esistente contiene record non presenti "
                "nei dati correnti e non verrà sovrascritto."
            )
            azione = (
                "Esegui la riconciliazione sicura: il database esistente viene usato come base, "
                "i record solo nella sorgente vengono aggiunti e i conflitti restano da revisione."
            )
        else:
            stato = "Non eseguita"
            messaggio = "Operazione SQLite non eseguita: verifica gli errori riportati."
            azione = "Correggi gli errori indicati e ripeti la pre-verifica prima di procedere."
        return {
            "ok": risultato.riuscita,
            "stato": stato,
            "messaggio": messaggio,
            "percorso_db": risultato.percorso_db or fallback_db,
            "record_migrati": totale,
            "per_modulo": risultato.record_migrati,
            "errori": risultato.errori,
            "avvisi": risultato.avvisi,
            "audit_migrazione": audit_migrazione,
            "durata_secondi": round(risultato.ms / 1000, 3),
            "azione_consigliata": azione,
            "istruzione": _sqlite_instruction(),
        }

    @app.route("/admin/database")
    def admin_database():
        """Dashboard gestione database solo amministratori."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            flash("Accesso riservato agli amministratori.", "danger")
            return redirect(url_for("dashboard"))
        database = get_database()
        statistiche = database.statistiche()
        uso = database.analisi_uso()
        sqlite_info = database.statistiche_sqlite(
            latest_sqlite_snapshot_path(cfg_data_path("BACKUP_DIR"))
        )
        return render_template(
            "admin/database.html",
            statistiche=statistiche,
            uso=uso,
            sqlite_info=sqlite_info,
        )

    @app.route("/admin/database/verifica")
    def admin_database_verifica():
        """Verifica integrita referenziale di tutti i moduli."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        database = get_database()
        problemi = database.verifica_integrita()
        audit("database.verifica_integrita")
        return jsonify(
            {
                "ok": True,
                "n_problemi": len(problemi),
                "n_riparazioni": 0,
                "riparazioni": [],
                "problemi": [_problem_payload(problema) for problema in problemi],
            }
        )

    @app.route("/admin/database/verifica-ripara", methods=["POST"])
    def admin_database_verifica_ripara():
        """Verifica e ripara automaticamente i problemi risolvibili."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        database = get_database()
        report = database.ripara_integrita()
        problemi = database.verifica_integrita()
        audit(
            "database.verifica_ripara_integrita",
            dettagli=(
                f"riparazioni={report.get('n_riparazioni', 0)}; "
                f"residui={len(problemi)}"
            ),
        )
        return jsonify(
            {
                "ok": bool(report.get("ok", True)) and not problemi,
                "n_problemi": len(problemi),
                "problemi": [_problem_payload(problema) for problema in problemi],
                "n_riparazioni": int(report.get("n_riparazioni", 0) or 0),
                "riparazioni": report.get("riparazioni", []),
                "backup_files": report.get("backup_files", []),
                "errori": report.get("errori", []),
                "durata_ms": report.get("ms", 0),
            }
        )

    @app.route("/admin/database/ottimizza", methods=["POST"])
    def admin_database_ottimizza():
        """Esegue ottimizzazione su tutti i moduli."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        database = get_database()
        risultati = database.ottimizza()
        audit("database.ottimizza")
        return jsonify(
            {
                "ok": True,
                "risultati": [
                    {
                        "modulo": risultato.modulo,
                        "operazione": risultato.operazione,
                        "ok": risultato.riuscita,
                        "riuscita": risultato.riuscita,
                        "messaggio": risultato.dettagli,
                        "dettagli": risultato.dettagli,
                        "ms": risultato.ms,
                        "bytes_prima": risultato.bytes_prima,
                        "bytes_dopo": risultato.bytes_dopo,
                        "risparmio_bytes": max(risultato.bytes_prima - risultato.bytes_dopo, 0),
                        "risparmio_pct": round(
                            ((risultato.bytes_prima - risultato.bytes_dopo) / risultato.bytes_prima) * 100,
                            1,
                        )
                        if risultato.bytes_prima and risultato.bytes_dopo <= risultato.bytes_prima
                        else 0,
                    }
                    for risultato in risultati
                ],
            }
        )

    @app.route("/admin/database/migra", methods=["POST"])
    def admin_database_migra():
        """Migra tutti i dati JSON verso un singolo database SQLite."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        percorso_db = os.path.join(
            cfg_data_path("BACKUP_DIR"),
            f"studio_legale_{date.today().isoformat()}.db",
        )
        database = get_database()
        risultato = database.migra_verso_sqlite(percorso_db)
        audit("database.migra_sqlite", risorsa_tipo="db", risorsa_id=percorso_db)
        return jsonify(_sqlite_status_payload(risultato, fallback_db=percorso_db))

    @app.route("/admin/database/preverifica-sqlite", methods=["POST"])
    def admin_database_preverifica_sqlite():
        """Esegue la pre-verifica anti-perdita senza modificare il database SQLite."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        try:
            from pct.storage import StudioDB

            studio_db = StudioDB.from_data_path(cfg_data_path("CLIENTI_DB"))
            percorso_db = str(studio_db.db_path)
            payload = get_database().preverifica_attivazione_sqlite(percorso_db)
            payload["istruzione"] = _sqlite_instruction()
            audit("database.preverifica_sqlite", risorsa_tipo="db", risorsa_id=percorso_db)
            return jsonify(payload)
        except Exception as exc:
            app.logger.exception("Errore pre-verifica SQLite: %s", exc)
            return jsonify(
                {
                    "ok": False,
                    "stato": "Non eseguita",
                    "messaggio": "Pre-verifica SQLite non eseguita.",
                    "errore": "Pre-verifica SQLite non eseguita. Il database esistente non è stato modificato.",
                    "errori": ["Pre-verifica SQLite non eseguita."],
                    "avvisi": [],
                    "audit_migrazione": {"precheck": {}, "validation": {}, "staging": False},
                    "azione_consigliata": "Verifica configurazione tenant, permessi su /data e ripeti l'analisi.",
                    "istruzione": _sqlite_instruction(),
                }
            ), 200

    @app.route("/admin/database/riconcilia-sqlite", methods=["POST"])
    def admin_database_riconcilia_sqlite():
        """Riconcilia SQLite preservando il database operativo come base."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        try:
            from pct.storage import StudioDB
            from pct import cache as pct_cache

            studio_db = StudioDB.from_data_path(cfg_data_path("CLIENTI_DB"))
            percorso_db = str(studio_db.db_path)
            risultato = get_database().riconcilia_verso_sqlite(percorso_db)
            pct_cache.invalidate(percorso_db)
            audit("database.riconcilia_sqlite", risorsa_tipo="db", risorsa_id=percorso_db)
            return jsonify(_sqlite_status_payload(risultato, fallback_db=percorso_db))
        except Exception as exc:
            app.logger.exception("Errore riconciliazione SQLite: %s", exc)
            return jsonify(
                {
                    "ok": False,
                    "stato": "Rollback eseguito",
                    "messaggio": "Riconciliazione SQLite non completata.",
                    "errore": "Riconciliazione SQLite non completata. Il database esistente non è stato modificato.",
                    "errori": ["Riconciliazione SQLite non completata."],
                    "avvisi": [],
                    "audit_migrazione": {
                        "precheck": {},
                        "validation": {},
                        "reconciliation": {"executed": False},
                    },
                    "azione_consigliata": "Conserva il report e richiedi intervento SUPERADMIN prima di ripetere.",
                    "istruzione": _sqlite_instruction(),
                }
            ), 200

    @app.route("/admin/database/attiva-sqlite", methods=["POST"])
    def admin_database_attiva_sqlite():
        """
        Crea studio.db nella root dei dati del tenant e importa tutti i dati JSON.

        In modalita' single-tenant legacy l'attivazione puo' ancora passare da
        PCT_STORAGE_MODE=SQLITE (con PCT_SQLITE_MODE=1 come alias legacy). In multi-tenant la scelta corretta e' definire la
        strategia storage dal SUPERADMIN sullo studio interessato.
        """
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        try:
            from pct.storage import StudioDB
            from pct import cache as pct_cache

            studio_db = StudioDB.from_data_path(cfg_data_path("CLIENTI_DB"))
            percorso_db = str(studio_db.db_path)
            risultato = get_database().migra_verso_sqlite(percorso_db)
            pct_cache.invalidate(percorso_db)

            audit("database.attiva_sqlite", risorsa_tipo="db", risorsa_id=percorso_db)
            return jsonify(_sqlite_status_payload(risultato, fallback_db=percorso_db))
        except Exception as exc:
            app.logger.exception("Errore attivazione SQLite: %s", exc)
            return jsonify(
                {
                    "ok": False,
                    "stato": "Rollback eseguito",
                    "messaggio": "Attivazione SQLite non completata.",
                    "errore": "Operazione SQLite non completata. Il database esistente non è stato modificato.",
                    "errori": ["Operazione SQLite non completata."],
                    "avvisi": [],
                    "azione_consigliata": "Esegui la pre-verifica e ripeti solo dopo aver risolto l'errore.",
                    "istruzione": _sqlite_instruction(),
                }
            ), 200

    @app.route("/admin/database/export")
    def admin_database_export():
        """Esporta un archivio ZIP completo di tutti i dati."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            flash("Accesso riservato agli amministratori.", "danger")
            return redirect(url_for("dashboard"))
        import tempfile

        output_dir = tempfile.mkdtemp(prefix="iusentra_export_")
        zip_path = get_database().esporta_tutto(output_dir)
        nome_file = f"export_{date.today().isoformat()}.zip"
        audit("database.esporta_zip")
        return send_file(
            zip_path,
            as_attachment=True,
            download_name=nome_file,
            mimetype="application/zip",
        )
