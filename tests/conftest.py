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

    _make_pct_stub("storage_postgres", build_postgres_dsn=_build_postgres_dsn_stub, PostgresStudioDB=None)
    _make_pct_stub("postgres_runtime_support", resolve_runtime_postgres_dsn=lambda *a, **kw: None)

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
    _make_pct_stub(
        "local_ai",
        OllamaHttpClient=type("OllamaHttpClient", (), {}),
        LocalAIService=type("LocalAIService", (), {"get_client": staticmethod(lambda: None)}),
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
