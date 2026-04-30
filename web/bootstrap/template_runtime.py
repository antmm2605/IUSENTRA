"""Template filters and context processors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime
from typing import Any

from flask import Flask, g, session

from web.services.ui_localization import (
    MONTHS_IT,
    MONTHS_SHORT_IT,
    WEEKDAYS_IT,
    WEEKDAYS_SHORT_IT,
    format_date,
    format_date_long,
    format_datetime,
    format_day_month,
    format_day_month_year,
    format_month_short,
    format_portal_import_note,
    format_short_weekday_date,
    format_time_only,
)
from web.services.local_signer_release import latest_local_signer_release


def register_template_runtime(
    app: Flask,
    *,
    template_symbols: Mapping[str, Any],
    app_version: str,
    connected_operators: Callable[[], int],
) -> None:
    """Register shared Jinja filters and context globals."""

    @app.template_filter("fmt_data")
    def fmt_data(val: Any) -> str:
        return format_date(val)

    @app.template_filter("fmt_dataora")
    def fmt_dataora(val: Any) -> str:
        return format_datetime(val)

    @app.template_filter("fmt_ora")
    def fmt_ora(val: Any) -> str:
        return format_time_only(val)

    @app.template_filter("fmt_data_estesa")
    def fmt_data_estesa(val: Any) -> str:
        return format_date_long(val)

    @app.template_filter("fmt_data_estesa_con_giorno")
    def fmt_data_estesa_con_giorno(val: Any) -> str:
        return format_date_long(val, include_weekday=True)

    @app.template_filter("fmt_data_breve_con_giorno")
    def fmt_data_breve_con_giorno(val: Any) -> str:
        return format_short_weekday_date(val)

    @app.template_filter("fmt_giorno_mese")
    def fmt_giorno_mese(val: Any) -> str:
        return format_day_month(val)

    @app.template_filter("fmt_giorno_mese_anno")
    def fmt_giorno_mese_anno(val: Any) -> str:
        return format_day_month_year(val)

    @app.template_filter("fmt_mese_breve")
    def fmt_mese_breve(val: Any) -> str:
        return format_month_short(val)

    @app.template_filter("fmt_nota_import")
    def fmt_nota_import(val: Any) -> str:
        return format_portal_import_note(val)

    @app.context_processor
    def inject_globals():
        return {
            "oggi": date.today(),
            "ora_adesso": datetime.now().strftime("%H:%M"),
            "mesi_italiani": MONTHS_IT,
            "mesi_italiani_brevi": MONTHS_SHORT_IT,
            "giorni_settimana_italiani": WEEKDAYS_IT,
            "giorni_settimana_brevi_italiani": WEEKDAYS_SHORT_IT,
            **template_symbols,
            "utente_corrente": g.get("utente_corrente"),
            "n_operatori_connessi": connected_operators(),
            "recenti": session.get("recenti", []),
            "app_version": app_version,
            "local_signer_release": latest_local_signer_release(),
        }
