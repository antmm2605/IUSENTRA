"""Legacy deposito preparation route registration."""
from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from flask import Flask, flash, redirect, render_template, request, url_for

from web.blueprints.react_shell import render_react_shell_response
from web.services.deposito_route_helpers import ufficio_deposito_destinatario as _ufficio_deposito_destinatario


def register_deposito_prepara_route(
    app: Flask,
    *,
    get_fascicoli: Callable[[], object],
    get_config_studio: Callable[[], object],
    deposito_correction_context: Callable[[object], dict[str, Any]],
    luogo_timbro_firma_visibile: Callable[[], str],
) -> None:
    """Register React-first deposito preparation page and legacy fallback."""

    @app.route("/fascicoli/<id_fasc>/deposito/prepara", methods=["GET"])
    def deposito_prepara(id_fasc):
        """Mostra il riepilogo documenti e la guida al deposito telematico."""
        if (request.args.get("_legacy") or "").strip().lower() not in {"1", "true", "si", "yes", "on"}:
            return render_react_shell_response(f"fascicoli/{id_fasc}/deposito/prepara")
        gestore_fascicoli = get_fascicoli()
        fascicolo = gestore_fascicoli.get(id_fasc)
        if not fascicolo:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("lista_fascicoli"))
        ufficio_deposito = _ufficio_deposito_destinatario(fascicolo)
        pec_tribunale = str(ufficio_deposito.get("pec_dest") or "")
        pdfa_stato: dict[str, Any] = {}
        try:
            from pct.validazione import verifica_dimensione, verifica_pdfa

            for documento in fascicolo.documenti:
                try:
                    percorso = str(gestore_fascicoli.percorso_documento(id_fasc, documento.id))
                    pdfa = verifica_pdfa(percorso)
                    dimensione = verifica_dimensione(percorso)
                    pdfa_stato[documento.id] = {**pdfa, "dimensione": dimensione}
                except Exception:
                    continue
        except Exception:
            pass
        pec_configurata = False
        try:
            cfg = get_config_studio().config
            pec_configurata = bool(cfg and cfg.pec and cfg.pec.indirizzo and cfg.pec.password)
        except Exception:
            cfg = None
            pass
        firma_cfg = getattr(cfg, "firma", None) if cfg else None
        return render_template(
            "fascicoli/deposito_prepara.html",
            fascicolo=fascicolo,
            pec_tribunale=pec_tribunale,
            pec_configurata=pec_configurata,
            pdfa_stato=pdfa_stato,
            correction_context=deposito_correction_context(fascicolo),
            firma_visibile_place=luogo_timbro_firma_visibile(),
            firma_visibile_mode=getattr(firma_cfg, "visible_signature_mode", "laterale"),
            oggi=date.today(),
        )
