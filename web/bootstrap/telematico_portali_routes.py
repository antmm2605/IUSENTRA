"""Route legacy di importazione per PDP, PAT e PTT."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from typing import Any

from flask import Flask, flash, g, redirect, render_template, request, url_for

from web.bootstrap.telematico_portali_common import (
    group_documenti_per_deposito,
    resolve_nome_ufficio,
)


def register_telematico_portali_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    polis_demo_mode: Callable[[], bool],
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

    @app.route("/pdp", methods=["GET"])
    def pdp_home():
        demo_mode = polis_demo_mode()
        id_fasc = request.args.get("id_fasc", "")
        fascicolo_ctx = get_fascicoli().get(id_fasc) if id_fasc else None
        return render_template(
            "pdp.html",
            demo_mode=demo_mode,
            oggi=date.today(),
            fascicolo=fascicolo_ctx,
            id_fasc=id_fasc,
        )

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
        codice_ufficio = request.args.get("codice_ufficio", "")
        numero_rg = request.args.get("numero_rg", "")
        anno_rg_str = request.args.get("anno_rg", "0")
        anno_rg = int(anno_rg_str) if anno_rg_str.isdigit() else 0
        demo_mode = polis_demo_mode()
        if portale_local_channel_enabled("pdp"):
            flash(
                "Per PDP Penale l'anteprima documenti usa il wizard browser-side con Local Signer.",
                "info",
            )
            return redirect(url_for("portale_acquisizione_wizard", portale="pdp"))
        try:
            from pct.pdp import crea_client_pdp

            client = crea_client_pdp(demo=demo_mode)
            documenti = client.consulta_documenti(codice_ufficio, numero_rg, anno_rg)
        except Exception as exc:
            app.logger.exception("Errore pdp_documenti: %s", exc)
            if is_portale_dns_error(exc):
                flash(portale_browser_guided_message("pdp"), "warning")
                return redirect(url_for("portale_acquisizione_wizard", portale="pdp"))
            documenti = []
            flash(str(exc), "danger")

        return render_template(
            "pdp_documenti.html",
            documenti=documenti,
            depositi=group_documenti_per_deposito(documenti),
            numero_rg=numero_rg,
            anno_rg=anno_rg,
            codice_ufficio=codice_ufficio,
            nome_ufficio=resolve_nome_ufficio(codice_ufficio),
            demo_mode=demo_mode,
        )

    @app.route("/pdp/importa", methods=["POST"])
    def pdp_importa():
        form_data = request.form
        demo_mode = form_data.get("demo_mode") == "1" or polis_demo_mode()
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
        except Exception as exc:
            flash(str(exc), "danger")
        return redirect(url_for("pdp_home"))

    @app.route("/pat", methods=["GET"])
    def pat_home():
        demo_mode = polis_demo_mode()
        id_fasc = request.args.get("id_fasc", "")
        fascicolo_ctx = get_fascicoli().get(id_fasc) if id_fasc else None
        return render_template(
            "pat.html",
            demo_mode=demo_mode,
            oggi=date.today(),
            fascicolo=fascicolo_ctx,
            id_fasc=id_fasc,
            official_portal_url="https://www.giustizia-amministrativa.it/portale-avvocato",
        )

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
            "In HACS trovi il fascicolo PAT interno e importi i file gia scaricati dal portale.",
            "info",
        )
        return redirect(url_for("portale_acquisizione_wizard", portale="pat", id_fasc=id_fasc or None))

    @app.route("/pat/importa", methods=["POST"])
    def pat_importa():
        form_data = request.form
        demo_mode = form_data.get("demo_mode") == "1" or polis_demo_mode()
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
        except Exception as exc:
            flash(str(exc), "danger")
        return redirect(url_for("pat_home"))

    @app.route("/sigit", methods=["GET"])
    def sigit_home():
        demo_mode = polis_demo_mode()
        id_fasc = request.args.get("id_fasc", "")
        fascicolo = get_fascicoli().get(id_fasc) if id_fasc else None
        return render_template(
            "sigit.html",
            demo_mode=demo_mode,
            id_fasc=id_fasc,
            fascicolo=fascicolo,
            official_portal_url="https://sigit.giustiziatributaria.gov.it/Sigit/index.do",
            telecontenzioso_url="https://sigit.giustiziatributaria.gov.it/Sigit/index.do",
            temporary_access_url="https://sigit.giustiziatributaria.gov.it/FascicoloProcessuale/login.jsp",
            commissione_sel="",
            commissione_sel_nome="",
            numero_rgt=None,
            anno_rgt=None,
            materia=None,
            nome_ricorrente=None,
            oggi=date.today(),
        )

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
        demo_mode = form_data.get("demo_mode") == "1" or polis_demo_mode()
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
        except Exception as exc:
            flash(str(exc), "danger")
        return redirect(url_for("sigit_home"))
