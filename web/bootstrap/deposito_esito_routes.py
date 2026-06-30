"""Manual deposito outcome route registration."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Flask, flash, g, redirect, request, url_for

from web.services.deposito_route_helpers import manual_deposito_payload as _manual_deposito_payload


def register_deposito_esito_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], object],
    audit: Callable[..., None],
    sync_pubblica: Callable[..., None],
) -> None:
    """Register manual deposito outcome insert/update routes."""

    @app.route("/fascicoli/<id_fasc>/depositi/aggiungi", methods=["POST"])
    def aggiungi_esito_deposito(id_fasc):
        """Registra manualmente un esito di deposito telematico nel fascicolo."""
        gestore_fascicoli = get_fascicoli()
        utente = g.utente_corrente
        form = request.form
        try:
            actor = utente.username if utente else ""
            gestore_fascicoli.aggiungi_esito_deposito(
                id_fasc=id_fasc,
                **_manual_deposito_payload(form, actor, actor_key="registrato_da"),
            )
            flash("Esito deposito registrato nel fascicolo.", "success")
            audit("fascicoli.deposito.aggiungi", "fascicolo", id_fasc)
            sync_pubblica("modifica", "fascicoli", id_fasc, utente=actor)
        except (ValueError, KeyError) as exc:
            app.logger.warning("Deposito manuale non valido %s: %s", id_fasc, exc)
            flash("Esito deposito non registrato. Verifica i dati e riprova.", "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/depositi/<id_dep>/modifica", methods=["POST"])
    def modifica_esito_deposito(id_fasc, id_dep):
        """Modifica manualmente un esito di deposito telematico nel fascicolo."""
        gestore_fascicoli = get_fascicoli()
        utente = g.utente_corrente
        form = request.form
        try:
            actor = utente.username if utente else ""
            gestore_fascicoli.modifica_esito_deposito(
                id_fasc=id_fasc,
                id_dep=id_dep,
                **_manual_deposito_payload(form, actor, actor_key="modificato_da"),
            )
            flash("Deposito aggiornato.", "success")
            audit("fascicoli.deposito.modifica", "fascicolo", id_fasc)
            sync_pubblica("modifica", "fascicoli", id_fasc, utente=actor)
        except (ValueError, KeyError) as exc:
            app.logger.warning("Modifica deposito non valida %s/%s: %s", id_fasc, id_dep, exc)
            flash("Deposito non aggiornato. Verifica i dati e riprova.", "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
