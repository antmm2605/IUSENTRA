"""Route legacy di importazione per PDP, PAT e PTT."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qsl, urlparse

from flask import Flask, flash, g, redirect, request, session, url_for

from web.blueprints.react_shell import render_react_shell_response

_PAGOPA_SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9._~!$&'()*+,;=:@%/-]{1,512}$")
_PAGOPA_ALLOWED_PATH_PREFIXES = ("it/pagopa_", "resources/", "dwr/")

def register_telematico_portali_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    portale_demo_mode: Callable[[str], bool],
    portale_browser_channel_required: Callable[[str], bool],
    portale_local_channel_enabled: Callable[[str], bool],
    portale_browser_guided_message: Callable[[str], str],
    is_portale_dns_error: Callable[[Exception], bool],
    codice_fiscale_avvocato_portale: Callable[[], str],
    serialize_portale_search_item: Callable[[str, Any], dict[str, Any]],
    build_portale_preview: Callable[[str, dict[str, Any], list[dict[str, Any]]], dict[str, Any]],
    find_exact_fascicolo_locale_portale: Callable[[str, dict[str, Any]], Any],
    sync_existing_fascicolo_from_portale: Callable[..., Any],
    register_direct_portale_import_sync: Callable[..., None],
) -> None:
    """Register remaining PDP, PAT and SIGIT UI routes."""

    def _pagopa_fascicolo_from_referrer() -> str:
        referrer = str(request.referrer or "").strip()
        if not referrer:
            return ""
        parsed = urlparse(referrer)
        if parsed.netloc and parsed.netloc != request.host:
            return ""
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            if key == "iusentra_fascicolo":
                return value
        return ""

    def _pagopa_safe_query_pairs() -> list[tuple[str, str]]:
        fascicolo_id = (
            str(request.args.get("iusentra_fascicolo") or "").strip()
            or str(session.get("pst_pagopa_fascicolo_id") or "").strip()
            or _pagopa_fascicolo_from_referrer().strip()
        )
        return [("iusentra_fascicolo", fascicolo_id)] if fascicolo_id else []

    def _pagopa_safe_pst_path(raw_path: str) -> str:
        cleaned = str(raw_path or "it/pagopa_altripag.wp").strip().replace("\\", "/")
        if cleaned.startswith("PST/"):
            cleaned = cleaned[4:]
        cleaned = cleaned.lstrip("/")
        parts = [part for part in cleaned.split("/") if part]
        if (
            "://" in cleaned
            or cleaned.startswith("//")
            or not _PAGOPA_SAFE_PATH_RE.fullmatch(cleaned)
            or any(part == ".." for part in parts)
            or not cleaned.startswith(_PAGOPA_ALLOWED_PATH_PREFIXES)
        ):
            return "it/pagopa_altripag.wp"
        return "/".join(parts)

    @app.route("/PST/", defaults={"pst_path": ""}, methods=["GET", "POST"])
    @app.route("/PST/<path:pst_path>", methods=["GET", "POST"])
    def pst_pagopa_absolute_escape(pst_path: str):
        cleaned = _pagopa_safe_pst_path(pst_path)

        query_pairs = _pagopa_safe_query_pairs()
        query_args = {key: value for key, value in query_pairs if key == "iusentra_fascicolo" and value}
        return redirect(
            url_for("api_v1_react.pst_pagopa_proxy", pst_path=cleaned, **query_args),
            code=307 if request.method == "POST" else 302,
        )

    @app.route("/pdp", methods=["GET"])
    def pdp_home():
        # Pagina React (TelematicoSurfacePage/TelematicoPage): la vista Jinja è stata tolta.
        return render_react_shell_response("pdp")

    @app.route("/pdp/ricerca", methods=["POST"])
    def pdp_ricerca():
        id_fasc = str(request.form.get("id_fasc") or "").strip()
        flash(
            "Per PDP Penale la ricerca diretta e' stata sostituita dall'acquisizione guidata, "
            "cosi evitiamo richieste inutili e agganciamo subito il workflow PDP.",
            "info",
        )
        if id_fasc:
            return redirect(url_for("portale_acquisizione_wizard", portale="pdp", id_fasc=id_fasc))
        return redirect(url_for("portale_acquisizione_wizard", portale="pdp"))

    @app.route("/pdp/documenti")
    def pdp_documenti():
        # Consultazione dai portali: acquisizione guidata React, con ufficio, numero e anno del ruolo.
        from web.bootstrap.react_route_gate import _redirect_portale

        return _redirect_portale(request.path)

    @app.route("/pdp/importa", methods=["POST"])
    def pdp_importa():
        form_data = request.form
        demo_mode = form_data.get("demo_mode") == "1" or portale_demo_mode("pdp")
        try:
            from pct.pdp import ClientPDP, FascicoloPDP, crea_client_pdp

            fascicolo = FascicoloPDP(
                numero_rg=form_data.get("numero_rg", ""),
                anno_rg=int(form_data.get("anno_rg", 0) or 0),
                tipo_registro=form_data.get("tipo_registro", ""),
                fase=form_data.get("fase", ""),
                stato=form_data.get("stato", ""),
                reato=form_data.get("reato", ""),
                sezione=form_data.get("sezione", ""),
                giudice=form_data.get("giudice", ""),
                data_iscrizione=form_data.get("data_iscrizione", ""),
                data_udienza=form_data.get("data_udienza", ""),
                imputati=json.loads(form_data.get("imputati_json", "[]")),
                parti_offese=json.loads(form_data.get("parti_offese_json", "[]")),
                codice_ufficio=form_data.get("codice_ufficio", ""),
                nome_ufficio=form_data.get("nome_ufficio", ""),
            )
            selection = serialize_portale_search_item("pdp", fascicolo)
            preview = build_portale_preview("pdp", selection, [])
            user_name = getattr(getattr(g, "utente_corrente", None), "username", "") or ""
            target = find_exact_fascicolo_locale_portale("pdp", selection)
            if target:
                target = sync_existing_fascicolo_from_portale(
                    "pdp",
                    target,
                    selection,
                    preview,
                    preserve_blank=True,
                    append_import_note=True,
                    user_name=user_name,
                )
                register_direct_portale_import_sync(
                    "pdp",
                    selection,
                    preview,
                    id_fasc=target.id,
                    created=False,
                    user_name=user_name,
                )
                flash(
                    "Pratica penale gia presente: fascicolo locale integrato senza creare duplicati.",
                    "success",
                )
                return redirect(url_for("dettaglio_fascicolo", id_fasc=target.id))
            if portale_local_channel_enabled("pdp"):
                client = ClientPDP(codice_fiscale_avvocato=codice_fiscale_avvocato_portale())
            else:
                client = crea_client_pdp(demo=demo_mode)
            risultato = client.importa_fascicolo(fascicolo, get_fascicoli(), get_clienti(), user_name)
            for avviso in risultato.avvisi:
                flash(avviso, "warning")
            if risultato.successo and risultato.id_fascicolo_locale:
                register_direct_portale_import_sync(
                    "pdp",
                    selection,
                    preview,
                    id_fasc=risultato.id_fascicolo_locale,
                    created=True,
                    user_name=user_name,
                )
                flash(risultato.messaggio, "success")
                return redirect(url_for("dettaglio_fascicolo", id_fasc=risultato.id_fascicolo_locale))
            flash(risultato.messaggio, "danger")
        except Exception:
            flash("Importazione PDP non completata.", "danger")
        return redirect(url_for("pdp_home"))

    @app.route("/pat", methods=["GET"])
    def pat_home():
        # Pagina React (TelematicoSurfacePage/TelematicoPage): la vista Jinja è stata tolta.
        return render_react_shell_response("pat")

    @app.route("/pat/ricerca", methods=["POST"])
    def pat_ricerca():
        id_fasc = request.form.get("id_fasc", "").strip()
        flash(
            "Nel PAT la consultazione del fascicolo passa dal Portale dell'Avvocato ufficiale: "
            "usa Acquisizione guidata e importa nel fascicolo interno file, ricevute ed esiti.",
            "info",
        )
        return redirect(url_for("portale_acquisizione_wizard", portale="pat", id_fasc=id_fasc or None))

    @app.route("/pat/documenti")
    def pat_documenti():
        id_fasc = str(request.args.get("id_fasc") or "").strip()
        flash(
            "Nel PAT la consultazione dei documenti si completa sul Portale dell'Avvocato ufficiale. "
            "In IUSENTRA trovi il fascicolo PAT interno e importi i file gia scaricati dal portale.",
            "info",
        )
        return redirect(url_for("portale_acquisizione_wizard", portale="pat", id_fasc=id_fasc or None))

    @app.route("/pat/importa", methods=["POST"])
    def pat_importa():
        form_data = request.form
        demo_mode = form_data.get("demo_mode") == "1" or portale_demo_mode("pat")
        try:
            from pct.pat import ClientPAT, FascicoloPAT, crea_client_pat

            fascicolo = FascicoloPAT(
                numero_ricorso=form_data.get("numero_ricorso", ""),
                anno=int(form_data.get("anno", 0) or 0),
                tipo=form_data.get("tipo", ""),
                stato=form_data.get("stato", ""),
                materia=form_data.get("materia", ""),
                sezione=form_data.get("sezione", ""),
                giudice_relatore=form_data.get("giudice_relatore", ""),
                data_deposito=form_data.get("data_deposito", ""),
                data_udienza=form_data.get("data_udienza", ""),
                oggetto=form_data.get("oggetto", ""),
                ricorrenti=json.loads(form_data.get("ricorrenti_json", "[]")),
                resistenti=json.loads(form_data.get("resistenti_json", "[]")),
                codice_ufficio=form_data.get("codice_ufficio", ""),
                nome_ufficio=form_data.get("nome_ufficio", ""),
            )
            selection = serialize_portale_search_item("pat", fascicolo)
            preview = build_portale_preview("pat", selection, [])
            user_name = getattr(getattr(g, "utente_corrente", None), "username", "") or ""
            target = find_exact_fascicolo_locale_portale("pat", selection)
            if target:
                target = sync_existing_fascicolo_from_portale(
                    "pat",
                    target,
                    selection,
                    preview,
                    preserve_blank=True,
                    append_import_note=True,
                    user_name=user_name,
                )
                register_direct_portale_import_sync(
                    "pat",
                    selection,
                    preview,
                    id_fasc=target.id,
                    created=False,
                    user_name=user_name,
                )
                flash(
                    "Pratica amministrativa gia presente: fascicolo locale integrato senza creare duplicati.",
                    "success",
                )
                return redirect(url_for("dettaglio_fascicolo", id_fasc=target.id))
            if portale_local_channel_enabled("pat"):
                client = ClientPAT(codice_fiscale_avvocato=codice_fiscale_avvocato_portale())
            else:
                client = crea_client_pat(demo=demo_mode)
            risultato = client.importa_fascicolo(fascicolo, get_fascicoli(), get_clienti(), user_name)
            for avviso in risultato.avvisi:
                flash(avviso, "warning")
            if risultato.successo and risultato.id_fascicolo_locale:
                register_direct_portale_import_sync(
                    "pat",
                    selection,
                    preview,
                    id_fasc=risultato.id_fascicolo_locale,
                    created=True,
                    user_name=user_name,
                )
                flash(risultato.messaggio, "success")
                return redirect(url_for("dettaglio_fascicolo", id_fasc=risultato.id_fascicolo_locale))
            flash(risultato.messaggio, "danger")
        except Exception:
            flash("Importazione PAT non completata.", "danger")
        return redirect(url_for("pat_home"))

    @app.route("/sigit", methods=["GET"])
    def sigit_home():
        # Pagina React (TelematicoSurfacePage/TelematicoPage): la vista Jinja è stata tolta.
        return render_react_shell_response("sigit")

    @app.route("/sigit/ricerca", methods=["POST"])
    def sigit_ricerca():
        id_fasc = request.form.get("id_fasc", "").strip()
        flash(portale_browser_guided_message("ptt"), "info")
        kwargs: dict[str, Any] = {"portale": "ptt"}
        if id_fasc:
            kwargs["id_fasc"] = id_fasc
        return redirect(url_for("portale_acquisizione_wizard", **kwargs))

    @app.route("/sigit/documenti")
    def sigit_documenti():
        id_fasc = request.args.get("id_fasc", "").strip()
        flash(portale_browser_guided_message("ptt"), "info")
        kwargs: dict[str, Any] = {"portale": "ptt"}
        if id_fasc:
            kwargs["id_fasc"] = id_fasc
        return redirect(url_for("portale_acquisizione_wizard", **kwargs))

    @app.route("/sigit/importa", methods=["POST"])
    def sigit_importa():
        form_data = request.form
        demo_mode = form_data.get("demo_mode") == "1" or portale_demo_mode("ptt")
        try:
            from pct.sigit import ClientSIGIT, FascicoloSIGIT, crea_client_sigit

            fascicolo = FascicoloSIGIT(
                numero_rgt=form_data.get("numero_rgt", ""),
                anno_rgt=int(form_data.get("anno_rgt", 0) or 0),
                tipo=form_data.get("tipo", ""),
                stato=form_data.get("stato", ""),
                materia=form_data.get("materia", ""),
                sezione=form_data.get("sezione", ""),
                giudice_relatore=form_data.get("giudice_relatore", ""),
                data_deposito=form_data.get("data_deposito", ""),
                data_udienza=form_data.get("data_udienza", ""),
                oggetto_controversia=form_data.get("oggetto_controversia", ""),
                valore_controversia=float(form_data.get("valore_controversia") or 0),
                ricorrenti=json.loads(form_data.get("ricorrenti_json", "[]")),
                resistenti=json.loads(form_data.get("resistenti_json", "[]")),
                codice_commissione=form_data.get("codice_commissione", ""),
                nome_commissione=form_data.get("nome_commissione", ""),
            )
            selection = serialize_portale_search_item("ptt", fascicolo)
            preview = build_portale_preview("ptt", selection, [])
            user_name = getattr(getattr(g, "utente_corrente", None), "username", "") or ""
            target = find_exact_fascicolo_locale_portale("ptt", selection)
            if target:
                target = sync_existing_fascicolo_from_portale(
                    "ptt",
                    target,
                    selection,
                    preview,
                    preserve_blank=True,
                    append_import_note=True,
                    user_name=user_name,
                )
                register_direct_portale_import_sync(
                    "ptt",
                    selection,
                    preview,
                    id_fasc=target.id,
                    created=False,
                    user_name=user_name,
                )
                flash(
                    "Pratica tributaria gia presente: fascicolo locale integrato senza creare duplicati.",
                    "success",
                )
                return redirect(url_for("dettaglio_fascicolo", id_fasc=target.id))
            if portale_local_channel_enabled("ptt"):
                client = ClientSIGIT(codice_fiscale_avvocato=codice_fiscale_avvocato_portale())
            else:
                client = crea_client_sigit(demo=demo_mode)
            risultato = client.importa_fascicolo(fascicolo, get_fascicoli(), get_clienti(), user_name)
            for avviso in risultato.avvisi:
                flash(avviso, "warning")
            if risultato.successo and risultato.id_fascicolo_locale:
                register_direct_portale_import_sync(
                    "ptt",
                    selection,
                    preview,
                    id_fasc=risultato.id_fascicolo_locale,
                    created=True,
                    user_name=user_name,
                )
                flash(risultato.messaggio, "success")
                return redirect(url_for("dettaglio_fascicolo", id_fasc=risultato.id_fascicolo_locale))
            flash(risultato.messaggio, "danger")
        except Exception:
            flash("Importazione SIGIT non completata.", "danger")
        return redirect(url_for("sigit_home"))
