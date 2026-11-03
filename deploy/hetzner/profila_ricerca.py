"""Profilazione della ricerca legale (/ricerca-legale), eseguita DENTRO il container app. Sola lettura.

Esegue la stessa funzione dell'endpoint `/api/v1/ui/ricerca-legale?q=...`
(`build_react_legal_intelligence_payload`, pagina «ricerca-legale») per una domanda e stampa SOLO:
tempi per fase e per sorgente, conteggi dei risultati, dimensioni dei database coinvolti, piano
EXPLAIN QUERY PLAN delle istruzioni SQL più lente e i punti caldi del codice (campionamento dello stack).
Nessun testo di documenti, nessun parametro SQL, nessun dato dello studio esce dallo script.

Uso sul server (una domanda per processo, così una ricerca bloccata non pesa sulla successiva):
    docker exec -i -e PROFILA_QUERY="Cassazione prescrizione" iusentra-app python - < deploy/hetzner/profila_ricerca.py
PROFILA_QUERY vuota = pagina senza ricerca (riferimento). PROFILA_LIMITE_S = attesa massima (predefinita 240 s):
oltre, lo script stampa i tempi raccolti fino a quel momento e termina.
"""

from __future__ import annotations

import cProfile
import functools
import io
import json
import os
import pstats
import re
import sqlite3
import sys
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

MARCATORE = "PROFILA_RICERCA_JSON:"
TEMPI: dict[str, dict[str, Any]] = defaultdict(lambda: {"chiamate": 0, "secondi": 0.0, "risultati": 0})
SQL: dict[tuple[str, str], dict[str, Any]] = {}
CAMPIONI: Counter = Counter()
CAMPIONI_FOGLIA: Counter = Counter()
_ORIGINALE_CONNECT = sqlite3.connect
_LOCK = threading.Lock()


def _forma_sql(sql: str) -> str:
    testo = re.sub(r"\s+", " ", str(sql or "")).strip()
    return re.sub(r"(\?,\s*)+\?", "?…", testo)[:400]


class _ConnessioneMisurata(sqlite3.Connection):
    """Misura il tempo di `execute` (il primo passo, dove SQLite ordina e calcola bm25)."""

    def execute(self, sql, parameters=(), /):  # type: ignore[override]
        inizio = time.perf_counter()
        try:
            return super().execute(sql, parameters)
        finally:
            durata = time.perf_counter() - inizio
            _registra_sql(self, sql, parameters, durata)


def _registra_sql(conn: Any, sql: str, parametri: Any, durata: float) -> None:
    db = getattr(conn, "_profila_db", "")
    chiave = (db, _forma_sql(sql))
    with _LOCK:
        voce = SQL.setdefault(chiave, {"chiamate": 0, "secondi": 0.0, "massimo": 0.0, "sql": sql, "parametri": None})
        voce["chiamate"] += 1
        voce["secondi"] += durata
        if durata >= voce["massimo"]:
            voce["massimo"] = durata
            voce["parametri"] = parametri  # serve solo all'EXPLAIN, non viene stampato


def _connect_misurato(database, *args, **kwargs):
    if "factory" in kwargs or len(args) >= 4:
        return _ORIGINALE_CONNECT(database, *args, **kwargs)
    conn = _ORIGINALE_CONNECT(database, *args, factory=_ConnessioneMisurata, **kwargs)
    conn._profila_db = str(database)  # type: ignore[attr-defined]
    conn._profila_args = (args, {k: v for k, v in kwargs.items()})  # type: ignore[attr-defined]
    return conn


def _misura(nome: str, funzione):
    if getattr(funzione, "_profila", False):
        return funzione

    @functools.wraps(funzione)
    def avvolta(*args, **kwargs):
        inizio = time.perf_counter()
        risultato = None
        try:
            risultato = funzione(*args, **kwargs)
            return risultato
        finally:
            durata = time.perf_counter() - inizio
            with _LOCK:
                voce = TEMPI[nome]
                voce["chiamate"] += 1
                voce["secondi"] += durata
                voce["massimo_s"] = max(float(voce.get("massimo_s", 0.0)), durata)
                if isinstance(risultato, tuple) and risultato and isinstance(risultato[0], list):
                    voce["risultati"] += len(risultato[0])
                elif isinstance(risultato, (list, tuple)):
                    voce["risultati"] += len(risultato)

    avvolta._profila = True  # type: ignore[attr-defined]
    return avvolta


def _avvolgi(oggetto: Any, nomi: list[str], prefisso: str) -> None:
    for nome in nomi:
        funzione = getattr(oggetto, nome, None)
        if callable(funzione):
            setattr(oggetto, nome, _misura(f"{prefisso}{nome}", funzione))


def _strumenta() -> None:
    import web.services.react_legal_intelligence_bridge as ponte

    _avvolgi(ponte, [
        "_dashboard_snapshot", "_pipeline_snapshot", "_mediazione_snapshot", "_news_rows", "_matters",
        "_template_atti_source_records", "_guida_pratica_source_records", "_practice_research_records",
        "_practice_nominal_reference_records", "_normative_db_records", "_source_delivery_audit",
        "_source_delivery_records", "_autofetch_monitor", "_enrich_autofetch_monitor_for_lawyer",
        "_official_archive_counts", "_search_repository_records", "_official_archive_records",
        "_public_search_records", "_complete_records_context_from_official_sources", "_enrich_record_context",
        "_dedupe_records", "_sort_records_for_query", "_filter_records_for_exact_reference", "_needs_public_fallback",
        "_matches_query", "_filter_resolved_search_warnings", "build_lex_operational_section",
        "build_advanced_ai_section", "build_lex_agent_metric", "template_atti_source_registry_summary",
        "_search_normattiva", "_search_gazzetta", "_run_public_legal_research", "_rewrite_query_for_legal_research",
        "_build_official_context", "_official_archive_snapshot", "_build_legal_source_delivery_audit",
    ], "ponte.")
    try:
        from pct import sentenzeweb_corpus
        from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza

        _avvolgi(sentenzeweb_corpus, ["configured_corpus"], "sentenzeweb.")
        _avvolgi(sentenzeweb_corpus.PublicSentenzeWebCorpus, ["cerca_sentenze", "_guard_text_availability"], "sentenzeweb.")
        _avvolgi(GestioneCorpusGiurisprudenza, ["_righe_per_estremi", "_massime_pertinenti_prima"], "giurisprudenza_corpus.")
    except Exception as exc:  # pragma: no cover - diagnostica
        TEMPI["errore_strumentazione_sentenzeweb"]["errore"] = type(exc).__name__
    try:
        from lex.ricerca_giuridica import ibrida, indice_fts

        _avvolgi(ibrida.MotoreRicercaNormattiva, ["cerca", "cerca_id", "_vettore_domanda"], "normattiva.")
        _avvolgi(ibrida, ["cerca_fts", "candidati_esatti", "cerca_normattiva_indicizzata"], "normattiva.")
        _avvolgi(indice_fts, ["cerca_fts", "candidati_esatti"], "normattiva.")
        from lex.retrieval import normativa_catalog, official_sources_retriever as osr

        _avvolgi(normativa_catalog, ["leggi_testo_articolo", "fondi_cataloghi"], "normattiva.")
        _avvolgi(osr, ["_search_official_db", "_search_jsonl", "_search_normattiva_indexed"], "archivi.")
    except Exception as exc:  # pragma: no cover - diagnostica
        TEMPI["errore_strumentazione_normattiva"]["errore"] = type(exc).__name__
    try:
        from pct.legal_update_repository import LegalUpdateRepository

        _avvolgi(LegalUpdateRepository, ["search_lex_sources", "_lex_sql_candidates", "_lex_evidence_payload",
                                         "dashboard_snapshot", "list_news"], "aggiornamenti.")
    except Exception as exc:  # pragma: no cover - diagnostica
        TEMPI["errore_strumentazione_aggiornamenti"]["errore"] = type(exc).__name__
    sqlite3.connect = _connect_misurato  # type: ignore[assignment]


def _campiona(thread_id: int, stop: threading.Event) -> None:
    """Campionamento dello stack del thread della ricerca: solo file, funzione e riga."""
    while not stop.wait(0.2):
        frame = sys._current_frames().get(thread_id)
        if frame is None:
            continue
        visti = set()
        foglia = True
        while frame is not None:
            codice = frame.f_code
            nome = f"{codice.co_filename.replace('/app/', '')}:{codice.co_name}:{frame.f_lineno}"
            if foglia:
                CAMPIONI_FOGLIA[nome] += 1
                foglia = False
            if "/app/" in codice.co_filename and nome not in visti:
                CAMPIONI[nome] += 1
                visti.add(nome)
            frame = frame.f_back


def _dimensioni(percorsi: dict[str, str]) -> dict[str, Any]:
    esito: dict[str, Any] = {}
    for etichetta, percorso in percorsi.items():
        if not percorso or not Path(percorso).is_file():
            esito[etichetta] = {"presente": False}
            continue
        voce: dict[str, Any] = {"mb": round(Path(percorso).stat().st_size / 1e6, 1)}
        wal = Path(str(percorso) + "-wal")
        if wal.exists():
            voce["wal_mb"] = round(wal.stat().st_size / 1e6, 1)
        try:
            conn = _ORIGINALE_CONNECT(Path(percorso).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
            try:
                oggetti = conn.execute("SELECT type, name, tbl_name, sql FROM sqlite_master WHERE type IN ('table','index')").fetchall()
                tabelle = {}
                for tipo, nome, tabella, sql in oggetti:
                    if tipo != "table" or nome.startswith("sqlite_"):
                        continue
                    virtuale = "VIRTUAL TABLE" in str(sql or "").upper()
                    if virtuale or re.search(r"_(data|idx|content|docsize|config)$", nome):
                        tabelle[nome] = {"virtuale_fts": True} if virtuale else {"ombra_fts": True}
                        continue
                    try:
                        righe = conn.execute(f'SELECT MAX(rowid) FROM "{nome}"').fetchone()[0]
                    except sqlite3.Error:
                        righe = None
                    tabelle[nome] = {"righe_circa": righe}
                indici: dict[str, list[str]] = defaultdict(list)
                for tipo, nome, tabella, _sql in oggetti:
                    if tipo == "index":
                        indici[tabella].append(nome)
                for nome, info in tabelle.items():
                    if indici.get(nome):
                        info["indici"] = sorted(indici[nome])
                voce["tabelle"] = tabelle
            finally:
                conn.close()
        except sqlite3.Error as exc:
            voce["errore"] = type(exc).__name__
        esito[etichetta] = voce
    return esito


def _explain(limite: int = 10) -> list[dict[str, Any]]:
    lente = sorted(SQL.items(), key=lambda kv: kv[1]["secondi"], reverse=True)[:limite]
    esito = []
    for (db, forma), voce in lente:
        riga: dict[str, Any] = {"db": Path(db.split("?")[0].replace("file://", "")).name or db[:40], "sql": forma,
                                "chiamate": voce["chiamate"], "secondi": round(voce["secondi"], 3),
                                "massimo_s": round(voce["massimo"], 3)}
        sql = str(voce["sql"] or "").strip()
        if sql.upper().startswith(("SELECT", "WITH")):
            try:
                uri = db.startswith("file:")
                conn = _ORIGINALE_CONNECT(db if uri else Path(db).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
                try:
                    piano = conn.execute("EXPLAIN QUERY PLAN " + sql, voce["parametri"] or ()).fetchall()
                    riga["piano"] = [str(p[-1]) for p in piano]
                finally:
                    conn.close()
            except Exception as exc:
                riga["piano_errore"] = type(exc).__name__
        esito.append(riga)
    return esito


def _percorsi_db(app: Any) -> dict[str, str]:
    percorsi: dict[str, str] = {}
    try:
        from lex.retrieval.normativa_catalog import library_path, runtime_general_path

        generale = runtime_general_path()
        percorsi["normattiva_generale"] = str(generale)
        percorsi["normattiva_biblioteca"] = str(library_path(generale))
    except Exception:
        pass
    try:
        from lex.retrieval.official_sources_retriever import CONTAINER_OFFICIAL_DB, DEFAULT_OFFICIAL_DB, _resolve_runtime_path

        percorsi["fonti_ufficiali_gazzetta"] = str(_resolve_runtime_path(
            None, env_names=("PCT_LEX_OFFICIAL_DB", "PCT_OFFICIAL_SOURCES_DB", "PCT_LEX_SOURCES_DB"),
            container_path=CONTAINER_OFFICIAL_DB, repo_path=DEFAULT_OFFICIAL_DB))
    except Exception:
        pass
    try:
        from pct.sentenzeweb_corpus import configured_corpus

        corpus = configured_corpus(app.config)
        if corpus is not None:
            percorsi["sentenzeweb_corpus"] = corpus.db_path
    except Exception:
        pass
    try:
        from web.helpers import get_legal_update_pipeline

        percorsi["aggiornamenti_giuridici"] = str(get_legal_update_pipeline().repository.db_path)
    except Exception:
        pass
    return percorsi


def _esegui(query: str, risultato: dict[str, Any]) -> None:
    from flask import current_app

    from web.helpers import (
        get_agenda, get_clienti, get_fascicoli, get_legal_intelligence, get_legal_update_pipeline, get_scadenziario,
    )
    from web.services.react_legal_intelligence_bridge import build_react_legal_intelligence_payload

    profilo = cProfile.Profile()
    inizio = time.perf_counter()
    profilo.enable()
    try:
        payload = build_react_legal_intelligence_payload(
            get_legal_intelligence=get_legal_intelligence, get_legal_update_pipeline=get_legal_update_pipeline,
            get_fascicoli=get_fascicoli, get_clienti=get_clienti, get_agenda=get_agenda,
            get_scadenziario=get_scadenziario, page="ricerca-legale", query={"q": query} if query else {},
            config=dict(current_app.config),
        )
        risultato["record"] = len(payload.get("records") or [])
        risultato["avvisi"] = [str(w.get("code") or "") for w in payload.get("warnings") or []]
        risultato["fonti_per_tipo"] = dict(Counter(
            str(r.get("registryKind") or r.get("sourceLabel") or r.get("sourceKind") or "altro")[:40]
            for r in payload.get("records") or []))
        risultato["dimensione_json_kb"] = round(len(json.dumps(payload, default=str)) / 1024, 1)
    except Exception as exc:
        risultato["errore"] = type(exc).__name__
    finally:
        profilo.disable()
        risultato["totale_s"] = round(time.perf_counter() - inizio, 3)
        uscita = io.StringIO()
        statistiche = pstats.Stats(profilo, stream=uscita)
        righe = []
        for (file, riga, funzione), (_cc, chiamate, tt, ct, _callers) in statistiche.stats.items():  # type: ignore[attr-defined]
            if ct >= 0.05:
                righe.append({"funzione": f"{file.replace('/app/', '')}:{riga}:{funzione}", "chiamate": chiamate,
                              "proprio_s": round(tt, 3), "cumulato_s": round(ct, 3)})
        risultato["cprofile_cumulato"] = sorted(righe, key=lambda r: r["cumulato_s"], reverse=True)[:45]
        risultato["cprofile_proprio"] = sorted(righe, key=lambda r: r["proprio_s"], reverse=True)[:25]


def main() -> int:
    sys.path.insert(0, "/app")
    query = str(os.getenv("PROFILA_QUERY", "") or "").strip()
    limite = float(os.getenv("PROFILA_LIMITE_S", "240") or 240)
    avvio = time.perf_counter()
    from pct.scheduler_worker import create_scheduler_app
    from pct.tenant import GestioneTenant
    from web.services.fascicoli_presidi_runtime import _active_tenants, _attach_tenant_context

    app = create_scheduler_app()
    esito: dict[str, Any] = {"query": query, "avvio_app_s": round(time.perf_counter() - avvio, 1)}
    studi = _active_tenants(app)
    _strumenta()
    risultato: dict[str, Any] = {}
    with app.test_request_context("/api/v1/ui/ricerca-legale"):
        if studi:
            _attach_tenant_context(GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"]), studi[0])
        esito["percorsi_db"] = {k: Path(v).name for k, v in _percorsi_db(app).items()}
        esito["dimensioni_db"] = _dimensioni(_percorsi_db(app))
        sqlite3.connect = _connect_misurato  # type: ignore[assignment]
        def lavoro() -> None:
            with app.test_request_context("/api/v1/ui/ricerca-legale"):
                if studi:
                    _attach_tenant_context(GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"]), studi[0])
                _esegui(query, risultato)

        filo = threading.Thread(target=lavoro, name="ricerca", daemon=True)
        stop = threading.Event()
        filo.start()
        campionatore = threading.Thread(target=_campiona, args=(filo.ident, stop), daemon=True)
        campionatore.start()
        filo.join(limite)
        stop.set()
        esito["completata"] = not filo.is_alive()
        if filo.is_alive():
            esito["interrotta_dopo_s"] = limite
    esito["risultato"] = risultato
    esito["tempi_per_fase"] = {k: {**v, "secondi": round(v["secondi"], 3), "massimo_s": round(float(v.get("massimo_s", 0.0)), 3)}
                               for k, v in sorted(TEMPI.items(), key=lambda kv: kv[1]["secondi"], reverse=True)}
    totale = sum(CAMPIONI_FOGLIA.values()) or 1
    esito["campioni_totali"] = totale
    esito["punti_caldi"] = [{"punto": k, "quota": round(v / totale, 3)} for k, v in CAMPIONI.most_common(40)]
    esito["foglie"] = [{"punto": k, "quota": round(v / totale, 3)} for k, v in CAMPIONI_FOGLIA.most_common(20)]
    esito["sql_piu_lente"] = _explain()
    print(MARCATORE + json.dumps(esito, ensure_ascii=False, default=str), flush=True)
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
