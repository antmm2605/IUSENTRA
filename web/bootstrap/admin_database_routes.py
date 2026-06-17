"""Admin database routes extracted from web.app."""

from __future__ import annotations

import os
import json
import sqlite3
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

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

    def _storage_runtime_profile():
        try:
            from web.services.storage_runtime import get_request_storage_runtime

            return get_request_storage_runtime(cfg_data_path("CLIENTI_DB"))
        except Exception:
            return None

    def _studio_db_path() -> str:
        try:
            value = cfg_data_path("STUDIO_DB")
            if value:
                return value
        except Exception:
            pass
        try:
            from pct.storage import StudioDB

            return str(StudioDB.from_data_path(cfg_data_path("CLIENTI_DB")).db_path)
        except Exception:
            return ""

    def _sql_operativo() -> bool:
        profile = _storage_runtime_profile()
        effective = str(getattr(profile, "effective_mode", "") or "").upper()
        return effective in {"SQLITE", "POSTGRESQL"}

    def _json_mirror_payload(payload: dict, percorso_db: str) -> dict:
        payload = dict(payload or {})
        payload["ok"] = True
        payload["stato"] = "SQL operativo"
        payload["messaggio"] = (
            "Archivio SQL operativo: il database è la fonte dati dello studio. "
            "I JSON elencati sono mirror di compatibilità e non vanno usati per sovrascrivere i dati."
        )
        payload["percorso_db"] = percorso_db
        payload["record_migrati"] = 0
        payload.setdefault("per_modulo", {})
        payload.setdefault("errori", [])
        payload.setdefault("avvisi", [])
        payload.setdefault("durata_secondi", 0)
        payload.setdefault("audit_migrazione", {})
        if isinstance(payload["audit_migrazione"], dict):
            payload["audit_migrazione"]["sql_source_of_truth"] = True
        payload["json_mirror_only"] = True
        payload["istruzione"] = (
            "Studio già SQL: i JSON sono solo mirror di compatibilità. "
            "Ogni riparazione deve partire da studio.db o PostgreSQL."
        )
        payload["azione_consigliata"] = (
            "Usa l'audit struttura e l'ottimizzazione SQL. Non eseguire migrazioni dai JSON mirror "
            "quando il database contiene più dati della sorgente."
        )
        return payload

    def _fmt_bytes(n: int) -> str:
        if n < 1024:
            return f"{n} B"
        if n < 1024 ** 2:
            return f"{n / 1024:.1f} KB"
        if n < 1024 ** 3:
            return f"{n / 1024 ** 2:.1f} MB"
        return f"{n / 1024 ** 3:.1f} GB"

    def _ottimizza_sqlite_file(percorso_db: str, modulo: str) -> dict:
        target = Path(percorso_db)
        before = target.stat().st_size if target.exists() and target.is_file() else 0
        if not target.exists() or not target.is_file():
            return {
                "modulo": modulo,
                "operazione": "Ottimizzazione SQL",
                "ok": False,
                "riuscita": False,
                "messaggio": "Archivio SQL non trovato.",
                "dettagli": "Archivio SQL non trovato.",
                "ms": 0,
                "bytes_prima": before,
                "bytes_dopo": before,
                "risparmio_bytes": 0,
                "risparmio_pct": 0,
            }
        started = datetime.now()
        try:
            conn = sqlite3.connect(str(target), isolation_level=None)
            try:
                conn.execute("PRAGMA optimize")
                conn.execute("ANALYZE")
                conn.execute("VACUUM")
            finally:
                conn.close()
            after = target.stat().st_size
            saved = max(before - after, 0)
            return {
                "modulo": modulo,
                "operazione": "VACUUM + ANALYZE + PRAGMA optimize",
                "ok": True,
                "riuscita": True,
                "messaggio": "Archivio SQL ottimizzato.",
                "dettagli": f"{_fmt_bytes(before)} -> {_fmt_bytes(after)}",
                "ms": int((datetime.now() - started).total_seconds() * 1000),
                "bytes_prima": before,
                "bytes_dopo": after,
                "risparmio_bytes": saved,
                "risparmio_pct": round((saved / before) * 100, 1) if before else 0,
            }
        except Exception as exc:
            after = target.stat().st_size if target.exists() else before
            return {
                "modulo": modulo,
                "operazione": "Ottimizzazione SQL",
                "ok": False,
                "riuscita": False,
                "messaggio": "Ottimizzazione SQL non completata.",
                "dettagli": str(exc),
                "ms": int((datetime.now() - started).total_seconds() * 1000),
                "bytes_prima": before,
                "bytes_dopo": after,
                "risparmio_bytes": 0,
                "risparmio_pct": 0,
            }

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

    def _json_has_records(path: str | Path) -> int:
        try:
            p = Path(path)
            if not p.exists() or not p.is_file():
                return 0
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return len(raw)
            if isinstance(raw, list):
                return len(raw)
        except Exception:
            return 0
        return 0

    def _sqlite_table_has_records(db_path: str | Path, table: str) -> int:
        try:
            p = Path(db_path)
            if not p.exists() or not p.is_file():
                return 0
            conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            try:
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if not row:
                    return 0
                count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
                return int((count or [0])[0] or 0)
            finally:
                conn.close()
        except Exception:
            return 0

    def _studio_db_from_clienti_path(path: str | Path) -> Path:
        try:
            from pct.storage import StudioDB

            return StudioDB.from_data_path(path).db_path
        except Exception:
            p = Path(path)
            return p.parents[1] / "studio.db" if len(p.parents) > 1 else p.with_name("studio.db")

    def _primary_counts(paths: dict[str, str]) -> dict[str, int]:
        clienti_path = str(paths.get("CLIENTI_DB", "") or "")
        fascicoli_path = str(paths.get("FASCICOLI_DB", "") or "")
        db_path = _studio_db_from_clienti_path(clienti_path) if clienti_path else Path("")
        return {
            "clienti_json": _json_has_records(clienti_path) if clienti_path else 0,
            "fascicoli_json": _json_has_records(fascicoli_path) if fascicoli_path else 0,
            "clienti_sqlite": _sqlite_table_has_records(db_path, "clienti") if str(db_path) else 0,
            "fascicoli_sqlite": _sqlite_table_has_records(db_path, "fascicoli") if str(db_path) else 0,
        }

    def _tenant_slug_corrente() -> str:
        return str(
            getattr(g, "tenant_slug", "")
            or getattr(g, "auth_tenant_slug", "")
            or getattr(g, "tenant", "")
            or ""
        ).strip().lower()

    def _directory_claims_current_tenant(slug: str) -> tuple[bool, str]:
        if not slug:
            return False, "tenant non determinato"
        directory_path = Path(str(app.config.get("TENANTS_REGISTRY", "tenants.json"))).parent / "tenant_user_directory.json"
        if not directory_path.exists():
            return False, "directory utenti-tenant non trovata"
        try:
            directory = json.loads(directory_path.read_text(encoding="utf-8"))
        except Exception:
            return False, "directory utenti-tenant non leggibile"
        users = directory.get("users") if isinstance(directory, dict) else {}
        emails = directory.get("emails") if isinstance(directory, dict) else {}
        utente = getattr(g, "utente_corrente", None)
        identifiers = {
            str(getattr(utente, "username", "") or "").strip().lower(),
            str(getattr(utente, "email", "") or "").strip().lower(),
        }
        identifiers.discard("")
        for identifier in identifiers:
            entry = (users or {}).get(identifier) or (emails or {}).get(identifier)
            if isinstance(entry, dict) and str(entry.get("tenant_slug") or "").strip().lower() == slug:
                return True, "utente corrente associato allo studio"
        slugs = {
            str(entry.get("tenant_slug") or "").strip().lower()
            for section in (users, emails)
            for entry in (section or {}).values()
            if isinstance(entry, dict) and str(entry.get("tenant_slug") or "").strip()
        }
        if slugs == {slug}:
            return True, "directory associata a un solo studio"
        return False, "directory utenti-tenant non attribuisce con certezza i dati root allo studio corrente"

    def _recover_legacy_root_before_sqlite(operazione: str) -> dict:
        if not app.config.get("MULTI_TENANT"):
            return {"ok": True, "executed": False, "reason": "single-tenant", "operation": operazione}
        slug = _tenant_slug_corrente()
        if not slug:
            return {"ok": True, "executed": False, "reason": "tenant non disponibile", "operation": operazione}
        try:
            from pct.tenant import GestioneTenant
            from web.services.tenant_legacy_bootstrap import legacy_root_data_paths

            tenants = GestioneTenant(app.config["TENANTS_REGISTRY"])
            tenant_paths = tenants.percorsi_dati(slug)
            root_paths = legacy_root_data_paths(app.config)
            if not root_paths:
                return {"ok": True, "executed": False, "reason": "nessun dato root legacy", "operation": operazione}
            if Path(str(root_paths.get("CLIENTI_DB", ""))).resolve() == Path(tenant_paths["CLIENTI_DB"]).resolve():
                return {"ok": True, "executed": False, "reason": "sorgente gia' tenant-aware", "operation": operazione}
            root_counts = _primary_counts(root_paths)
            tenant_counts = _primary_counts(tenant_paths)
            root_has_primary = any(root_counts[key] > 0 for key in ("clienti_json", "fascicoli_json", "clienti_sqlite", "fascicoli_sqlite"))
            tenant_has_primary = any(tenant_counts[key] > 0 for key in ("clienti_json", "fascicoli_json", "clienti_sqlite", "fascicoli_sqlite"))
            if not root_has_primary:
                return {
                    "ok": True,
                    "executed": False,
                    "reason": "nessun cliente o fascicolo nella root legacy",
                    "operation": operazione,
                    "root_counts": root_counts,
                    "tenant_counts": tenant_counts,
                }
            if tenant_has_primary:
                return {
                    "ok": True,
                    "executed": False,
                    "reason": "lo studio corrente contiene gia' clienti o fascicoli",
                    "operation": operazione,
                    "root_counts": root_counts,
                    "tenant_counts": tenant_counts,
                }
            claimed, reason = _directory_claims_current_tenant(slug)
            if not claimed:
                return {
                    "ok": False,
                    "executed": False,
                    "reason": reason,
                    "operation": operazione,
                    "root_counts": root_counts,
                    "tenant_counts": tenant_counts,
                }
            result = tenants.bootstrap_legacy_runtime_data(slug, root_paths)
            return {
                "ok": bool(result.get("ok", True)),
                "executed": bool(result.get("copied") or result.get("sqlite_migrated")),
                "reason": "recupero root legacy eseguito",
                "operation": operazione,
                "target_slug": slug,
                "root_counts": root_counts,
                "tenant_counts_before": tenant_counts,
                "tenant_counts_after": _primary_counts(tenant_paths),
                "bootstrap": result,
            }
        except Exception as exc:
            app.logger.exception("Recupero dati legacy root non riuscito prima di %s: %s", operazione, exc)
            return {"ok": False, "executed": False, "reason": "recupero dati legacy non riuscito", "operation": operazione}

    def _legacy_recovery_block_payload(report: dict) -> dict:
        return {
            "ok": False,
            "stato": "Bloccata per protezione dati",
            "messaggio": "Operazione SQLite bloccata: esistono dati legacy fuori dallo studio corrente non attribuibili con certezza.",
            "percorso_db": "",
            "record_migrati": 0,
            "per_modulo": {},
            "errori": [str(report.get("reason") or "Recupero dati legacy non sicuro.")],
            "avvisi": [],
            "audit_migrazione": {"legacy_recovery": report},
            "durata_secondi": 0,
            "azione_consigliata": "Verifica associazione utenti-studio e ripeti solo quando i dati root sono attribuiti allo studio corretto.",
            "istruzione": _sqlite_instruction(),
            "recupero_legacy": report,
        }

    def _mark_tenant_sqlite_ready(percorso_db: str, report: dict | None = None) -> None:
        slug = _tenant_slug_corrente()
        if not slug:
            return
        if _sqlite_table_has_records(percorso_db, "clienti") < 0:
            return
        try:
            from pct.tenant import GestioneTenant

            tenants = GestioneTenant(app.config["TENANTS_REGISTRY"])
            studio = tenants.get(slug)
            if not studio or not studio.database.is_sqlite:
                return
            studio.database.connessione_ok = True
            studio.database.core_runtime_enabled = True
            studio.database.ultimo_test = datetime.now().isoformat()
            studio.database.errore_connessione = ""
            studio.database.last_migration_at = datetime.now().isoformat()
            if report and report.get("percorso_db"):
                studio.database.last_migration_report = str(report.get("percorso_db"))
            studi = tenants._carica()  # noqa: SLF001 - aggiornamento atomico registry tenant interno
            key = tenants._resolve_registry_key(slug)  # noqa: SLF001
            studi[key] = studio
            tenants._salva(studi)  # noqa: SLF001
            tenants._scrivi_storage_manifest(slug, studio)  # noqa: SLF001
        except Exception as exc:
            app.logger.exception("Marcatura SQLite tenant non riuscita: %s", exc)

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
        percorso_db = _studio_db_path()
        sqlite_info = database.statistiche_sqlite(percorso_db) if percorso_db else None
        if not sqlite_info:
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
        if _sql_operativo():
            percorso_db = _studio_db_path()
            risultati_sql = [_ottimizza_sqlite_file(percorso_db, "studio.db")]
            search_index = cfg_data_path("SEARCH_INDEX")
            if search_index and Path(search_index).exists():
                risultati_sql.append(_ottimizza_sqlite_file(search_index, "search_index"))
            audit("database.ottimizza_sql", risorsa_tipo="db", risorsa_id=percorso_db)
            return jsonify(
                {
                    "ok": all(item.get("ok") for item in risultati_sql),
                    "json_mirror_only": True,
                    "messaggio": "Ottimizzazione SQL completata: i JSON mirror non sono stati compattati.",
                    "risultati": risultati_sql,
                }
            )
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
        if _sql_operativo():
            percorso_db = _studio_db_path()
            payload = _json_mirror_payload({}, percorso_db)
            audit("database.migra_sqlite_noop_sql_operativo", risorsa_tipo="db", risorsa_id=percorso_db)
            return jsonify(payload)
        recupero_legacy = _recover_legacy_root_before_sqlite("migra")
        if not recupero_legacy.get("ok", True):
            return jsonify(_legacy_recovery_block_payload(recupero_legacy)), 200
        percorso_db = os.path.join(
            cfg_data_path("BACKUP_DIR"),
            f"studio_legale_{date.today().isoformat()}.db",
        )
        database = get_database()
        risultato = database.migra_verso_sqlite(percorso_db)
        audit("database.migra_sqlite", risorsa_tipo="db", risorsa_id=percorso_db)
        payload = _sqlite_status_payload(risultato, fallback_db=percorso_db)
        payload["recupero_legacy"] = recupero_legacy
        return jsonify(payload)

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
            if _sql_operativo():
                payload = _json_mirror_payload(payload, percorso_db)
            else:
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
            if _sql_operativo():
                payload = _json_mirror_payload({}, percorso_db)
                audit("database.riconcilia_sqlite_noop_sql_operativo", risorsa_tipo="db", risorsa_id=percorso_db)
                return jsonify(payload)
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

            recupero_legacy = _recover_legacy_root_before_sqlite("attiva-sqlite")
            if not recupero_legacy.get("ok", True):
                return jsonify(_legacy_recovery_block_payload(recupero_legacy)), 200
            studio_db = StudioDB.from_data_path(cfg_data_path("CLIENTI_DB"))
            percorso_db = str(studio_db.db_path)
            if _sql_operativo():
                payload = _json_mirror_payload({}, percorso_db)
                payload["recupero_legacy"] = recupero_legacy
                audit("database.attiva_sqlite_noop_sql_operativo", risorsa_tipo="db", risorsa_id=percorso_db)
                return jsonify(payload)
            if recupero_legacy.get("executed"):
                risultato = get_database().riconcilia_verso_sqlite(percorso_db)
            else:
                risultato = get_database().migra_verso_sqlite(percorso_db)
            pct_cache.invalidate(percorso_db)

            audit("database.attiva_sqlite", risorsa_tipo="db", risorsa_id=percorso_db)
            payload = _sqlite_status_payload(risultato, fallback_db=percorso_db)
            payload["recupero_legacy"] = recupero_legacy
            if risultato.riuscita:
                _mark_tenant_sqlite_ready(percorso_db, payload)
            return jsonify(payload)
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
