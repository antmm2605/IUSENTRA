"""Configurazione pytest condivisa.

Su Windows alcune combinazioni Python/pytest lasciano `pytest-current` come
directory reparse point non eliminabile con `Path.unlink()`. Il problema emerge
solo in cleanup atexit e sporca l'output pur con test verdi. Questa patch usa
la rimozione corretta per link a directory e degrada silenziosamente solo se il
link e' gia' gestito/lockato dal sistema operativo.
"""

from __future__ import annotations

import os
import sys
import types
import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def _iusentra_test_pst_cert(tmp_path_factory):
    from pct.pst_cifratura import crea_certificato_cifratura_test

    return crea_certificato_cifratura_test(
        tmp_path_factory.mktemp("pst_cifratura") / "ufficio-test.cer"
    )


@pytest.fixture(autouse=True)
def _iusentra_no_network_pst_cert(monkeypatch, _iusentra_test_pst_cert):
    """I test unitari generano Atto.enc senza dipendere dal PST esterno."""

    def fake_resolver(codice_ufficio, *, cache_dir=None, force_refresh=False):
        return _iusentra_test_pst_cert

    monkeypatch.setattr(
        "pct.pst_cifratura.risolvi_certificato_cifratura_ufficio",
        fake_resolver,
        raising=False,
    )
    monkeypatch.setattr(
        "pct.busta.risolvi_certificato_cifratura_ufficio",
        fake_resolver,
        raising=False,
    )
    monkeypatch.setattr(
        "pct.profilo_deposito.risolvi_certificato_cifratura_ufficio",
        fake_resolver,
        raising=False,
    )


# ---------------------------------------------------------------------------
# Stub moduli pesanti non necessari per i test unitari di Lex.
# La catena di import  lex.retrieval → web.helpers → pct → psycopg2 ecc.
# richiede un'installazione completa non disponibile nell'ambiente di test
# isolato. Questi stub registrano moduli fittizi in sys.modules PRIMA che i
# test vengano raccolti, in modo che le importazioni non falliscano.
# ---------------------------------------------------------------------------

def _stub(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


def _ensure_lex_unit_stubs() -> None:
    """Stub minimi per eseguire test unitari Lex senza stack applicativo completo.

    Viene chiamata solo se il modulo lex.retrieval non è ancora importato
    (cioè in test che non dipendono dall'app Flask completa).
    """
    # Non fare nulla se web è già importato come package reale
    # (significa che l'app Flask è disponibile e i test applicativi funzionano)
    if "web" in sys.modules and hasattr(sys.modules["web"], "app"):
        return

    # Stub per psycopg2 e altre dipendenze C/DB non installate nell'env test isolato
    for name in ("psycopg2", "psycopg2.extras", "psycopg2.pool"):
        if name not in sys.modules:
            _stub(name)

    # Stub per pct sotto-moduli che importano psycopg2 prima che pct.__init__ carichi
    def _make_pct_stub(subname: str, **attrs):
        full = f"pct.{subname}"
        if full not in sys.modules:
            mod = types.ModuleType(full)
            for k, v in attrs.items():
                setattr(mod, k, v)
            # Usa __getattr__ per gestire import non previsti
            mod.__getattr__ = lambda n: None  # type: ignore[attr-defined]
            sys.modules[full] = mod

    def _build_postgres_dsn_stub(*args, **kwargs) -> str:
        host = str(kwargs.get("host") or "").strip()
        db_name = str(kwargs.get("db_name") or "").strip()
        user = str(kwargs.get("user") or "").strip()
        if host and db_name and user:
            return f"postgresql://{user}@{host}/{db_name}"
        return ""

    def _database_config_to_dsn_stub(database) -> str:
        if database is None:
            return ""
        mode = str(
            getattr(database, "normalized_mode", None)
            or getattr(database, "mode", "")
            or ""
        ).strip().upper()
        if mode != "POSTGRESQL":
            return ""
        host = str(getattr(database, "host", "") or "").strip()
        db_name = str(getattr(database, "db_name", "") or "").strip()
        user = str(getattr(database, "utente", "") or "").strip()
        password = str(getattr(database, "password", "") or "")
        port = int(getattr(database, "porta_effettiva", 0) or getattr(database, "porta", 0) or 5432)
        if not all((host, db_name, user)):
            return ""
        auth = f"{user}:{password}" if password else user
        return f"postgresql://{auth}@{host}:{port}/{db_name}"

    def _resolve_runtime_postgres_dsn_stub(explicit_dsn: str = "", **kwargs) -> str:
        if str(explicit_dsn or "").strip():
            return str(explicit_dsn).strip()
        config = dict(kwargs.get("config") or {})
        for key in kwargs.get("env_url_keys") or ():
            value = str(config.get(key) or "").strip()
            if value:
                return value
        dsn = _database_config_to_dsn_stub(kwargs.get("database"))
        if dsn:
            return dsn
        return _database_config_to_dsn_stub(config.get("TENANT_DATABASE_CONFIG"))

    _make_pct_stub("storage_postgres", build_postgres_dsn=_build_postgres_dsn_stub, PostgresStudioDB=None)
    _make_pct_stub(
        "postgres_runtime_support",
        database_config_to_dsn=_database_config_to_dsn_stub,
        resolve_runtime_postgres_dsn=_resolve_runtime_postgres_dsn_stub,
    )

    try:
        importlib.import_module("pct.legal_intelligence")
    except Exception:
        class _GestioneLegalIntelligenceStub:
            def __init__(self, db_path: str = "", *args, **kwargs):
                self.db_path = db_path or kwargs.get("db_path", "")

            def _save(self) -> None:
                if not self.db_path:
                    return
                target = Path(self.db_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    target.write_text(json.dumps({"monitor_runs": []}, ensure_ascii=False), encoding="utf-8")

        _make_pct_stub(
            "legal_intelligence",
            FONTI_UFFICIALI={},
            USER_AGENT="lex-test/1.0",
            fonti_per_query=lambda *a, **kw: [],
            GestioneLegalIntelligence=_GestioneLegalIntelligenceStub,
        )
    try:
        importlib.import_module("pct.local_ai")
    except Exception:
        class _LocalAIServiceStub:
            def __init__(self, **kwargs):
                self.enabled = bool(kwargs.get("enabled", False))
                for key, value in kwargs.items():
                    if key in {"db_path", "policy_path", "config_path", "app_root", "models_path"}:
                        setattr(self, key, Path(value))
                    else:
                        setattr(self, key, value)

            @staticmethod
            def get_client():
                return None

            def bootstrap_runtime(self, *, force: bool = False):
                return {"status": "disabled", "force": bool(force)}

            def health_snapshot(self):
                return {"runtime": {"status": "disabled"}}

        _make_pct_stub(
            "local_ai",
            OllamaHttpClient=type("OllamaHttpClient", (), {}),
            LocalAIService=_LocalAIServiceStub,
            strip_api_suffix=lambda x: x,
        )

    # Stub per web.helpers solo se web non è già un package reale caricato
    if "web.helpers" not in sys.modules and "web" not in sys.modules:
        try:
            importlib.import_module("web.helpers")
        except Exception:
            helpers = _stub("web.helpers")
            helpers.__getattr__ = lambda name: (lambda *a, **kw: None)  # type: ignore[attr-defined]


_ensure_lex_unit_stubs()


if os.name == "nt":
    import _pytest.pathlib as _pytest_pathlib

    def _cleanup_dead_symlinks_windows(root: Path) -> None:
        for leftover in root.iterdir():
            try:
                if not leftover.is_symlink() or leftover.resolve().exists():
                    continue
            except OSError:
                continue
            try:
                leftover.unlink()
            except PermissionError:
                try:
                    os.rmdir(leftover)
                except OSError:
                    pass
            except FileNotFoundError:
                pass

    _pytest_pathlib.cleanup_dead_symlinks = _cleanup_dead_symlinks_windows
