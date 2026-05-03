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
            latest_sqlite_snapshot_path(app.config.get("BACKUP_DIR", "./backup"))
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
            app.config.get("BACKUP_DIR", "./backup"),
            f"studio_legale_{date.today().isoformat()}.db",
        )
        database = get_database()
        risultato = database.migra_verso_sqlite(percorso_db)
        audit("database.migra_sqlite", risorsa_tipo="db", risorsa_id=percorso_db)
        totale = sum(risultato.record_migrati.values()) if risultato.record_migrati else 0
        if risultato.riuscita and risultato.avvisi:
            messaggio = (
                "Migrazione completata con avvisi: alcuni riferimenti orfani sono stati "
                "scollegati per preservare i record."
            )
        elif risultato.riuscita:
            messaggio = "Migrazione completata con successo."
        else:
            messaggio = "Migrazione non completata: verifica gli errori riportati."
        return jsonify(
            {
                "ok": risultato.riuscita,
                "messaggio": messaggio,
                "percorso_db": risultato.percorso_db,
                "record_migrati": totale,
                "per_modulo": risultato.record_migrati,
                "errori": risultato.errori,
                "avvisi": risultato.avvisi,
                "durata_secondi": round(risultato.ms / 1000, 3),
            }
        )

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
            totale = sum(risultato.record_migrati.values()) if risultato.record_migrati else 0
            return jsonify(
                {
                    "ok": risultato.riuscita,
                    "percorso_db": percorso_db,
                    "record_migrati": totale,
                    "per_modulo": risultato.record_migrati,
                    "errori": risultato.errori,
                    "avvisi": risultato.avvisi,
                    "istruzione": (
                        "Per ambienti multi-tenant imposta SQLite dal pannello SUPERADMIN dello studio. "
                        "Per installazioni single-tenant legacy puoi usare PCT_STORAGE_MODE=SQLITE; "
                        "PCT_SQLITE_MODE=1 resta supportato come compatibilita'."
                    ),
                }
            )
        except Exception as exc:
            app.logger.exception("Errore attivazione SQLite: %s", exc)
            return jsonify({"ok": False, "errore": str(exc)}), 200

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
