"""Template filters and context processors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime
from typing import Any

from flask import Flask, g, session


def register_template_runtime(
    app: Flask,
    *,
    template_symbols: Mapping[str, Any],
    app_version: str,
    connected_operators: Callable[[], int],
) -> None:
    """Register shared Jinja filters and context globals."""

    @app.template_filter("fmt_data")
    def fmt_data(val: str) -> str:
        if not val:
            return "—"
        try:
            testo = str(val).strip()
            for sep in ("T", " "):
                if sep in testo:
                    testo = testo.split(sep)[0]
                    break
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                try:
                    parsed = datetime.strptime(testo[:10], fmt).date()
                    return parsed.strftime("%d/%m/%Y")
                except ValueError:
                    continue
            return val
        except Exception:
            return val

    @app.template_filter("fmt_dataora")
    def fmt_dataora(val: str) -> str:
        if not val:
            return "—"
        try:
            testo = str(val).strip().replace("Z", "")
            if len(testo) == 10:
                return datetime.fromisoformat(testo + "T00:00:00").strftime("%d/%m/%Y")
            return datetime.fromisoformat(testo).strftime("%d/%m/%Y %H:%M")
        except Exception:
            return fmt_data(val)

    @app.context_processor
    def inject_globals():
        return {
            "oggi": date.today(),
            "ora_adesso": datetime.now().strftime("%H:%M"),
            **template_symbols,
            "utente_corrente": g.get("utente_corrente"),
            "n_operatori_connessi": connected_operators(),
            "recenti": session.get("recenti", []),
            "app_version": app_version,
        }
