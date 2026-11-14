"""Route PolisWeb estratte dal blocco legacy telematico."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Flask, flash, g, redirect, request, url_for

from web.blueprints.react_shell import render_react_shell_response


def register_polisweb_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_soggetti: Callable[[], Any],
    audit: Callable[..., None],
    polis_auth_mode: Callable[[], str],
    polis_demo_mode: Callable[[], bool],
    polis_cert_preferences: Callable[[], dict[str, Any]],
    get_scadenziario: Callable[[], Any] | None = None,
) -> None:
    """Register PolisWeb consultation and import routes."""

    from web.bootstrap.fascicolo_registro_routes import register_fascicolo_registro_routes

    register_fascicolo_registro_routes(
        app,
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        audit=audit,
        polis_auth_mode=polis_auth_mode,
    )

    @app.route("/polisWeb", methods=["GET"])
    def polisWeb_home():
        # Pagina React (TelematicoSurfacePage/TelematicoPage): la vista Jinja è stata tolta.
        return render_react_shell_response("polisWeb")

    @app.route("/fascicoli/<id_fasc>/sincronizza-registro", methods=["POST"])
    def fascicolo_sincronizza_registro(id_fasc):
        from flask import jsonify

        from web.services.polisweb_fascicolo_sync import sincronizza_fascicolo_da_registro

        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("fascicoli.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente.", "errore": "Permesso insufficiente."}), 403
        try:
            esito = sincronizza_fascicolo_da_registro(
                id_fasc,
                get_fascicoli=get_fascicoli,
                get_clienti=get_clienti,
                get_soggetti=get_soggetti,
                get_scadenziario=get_scadenziario,
                auth_mode=polis_auth_mode(),
                avvocato_referente=getattr(utente, "username", "") or "",
            )
        except Exception as exc:
            app.logger.exception("Errore sincronizzazione registro fascicolo %s: %s", id_fasc, exc)
            return jsonify({"ok": False, "message": f"Sincronizzazione non riuscita: {exc}"}), 200
        if esito.get("ok"):
            audit("polisweb.sincronizza_fascicolo", "fascicolo", id_fasc)
        esito.setdefault("messaggio", esito.get("message", ""))
        return jsonify(esito)


    @app.route("/polisWeb/documenti", methods=["GET"])
    def polisWeb_documenti():
        # Consultazione dai portali: acquisizione guidata React, con ufficio, numero e anno del ruolo.
        from web.bootstrap.react_route_gate import _redirect_portale

        return _redirect_portale(request.path)

    @app.route("/polisWeb/fascicolo-wizard", methods=["GET"])
    def polisWeb_fascicolo_wizard():
        # Consultazione dai portali: acquisizione guidata React, con ufficio, numero e anno del ruolo.
        from web.bootstrap.react_route_gate import _redirect_portale

        return _redirect_portale(request.path)

    @app.route("/polisWeb/importa", methods=["POST"])
    def polisWeb_importa():
        import json as _json

        from pct.polisWeb import (
            ClientPolisWebImportOnly,
            DocumentoPolisWeb,
            FascicoloPolisWeb,
            chiave_esterna_fascicolo_polisweb,
            _parse_data,
            crea_client,
        )
        from pct.uffici_giudiziari import risolvi_ufficio

        form_data = request.form
        utente = g.utente_corrente
        try:
            def _as_bool(value: Any) -> bool:
                if isinstance(value, bool):
                    return value
                if isinstance(value, (int, float)):
                    return bool(value)
                text = str(value or "").strip().lower()
                if text in {"1", "true", "yes", "si", "s", "ok"}:
                    return True
                if text in {"0", "false", "no", "n", "", "none", "null"}:
                    return False
                return bool(value)

            documenti_json_raw = form_data.get("documenti_json", "").strip()
            documenti_prefetch_error = form_data.get("documenti_prefetch_error", "").strip()
            canale_accesso_pst = str(form_data.get("canale_accesso_pst") or "").strip().lower()
            import_locale_richiesto = (
                canale_accesso_pst == "local_signer"
                or bool(documenti_json_raw)
                or bool(documenti_prefetch_error)
            )
            demo_mode = form_data.get("demo_mode") == "1"
            if not import_locale_richiesto:
                demo_mode = demo_mode or polis_demo_mode()

            numero_rg_imp = form_data.get("numero_rg", "")
            anno_rg_imp = int(form_data.get("anno_rg", 0) or 0)
            nome_ufficio_imp = form_data.get("nome_ufficio", "")
            codice_ufficio_imp = form_data.get("codice_ufficio", "")
            if not nome_ufficio_imp and codice_ufficio_imp:
                ufficio = risolvi_ufficio(codice_ufficio_imp)
                if isinstance(ufficio, dict):
                    nome_ufficio_imp = str(ufficio.get("nome") or "").strip()

            def _form_first(*names: str) -> str:
                for name in names:
                    value = str(form_data.get(name) or "").strip()
                    if value:
                        return value
                return ""

            sub_procedimento_imp = _form_first("sub_procedimento", "subprocedimento", "subpro")
            tipo_registro_imp = _form_first("tipo_registro", "registro", "schema")
            registro_portale_imp = _form_first("registro_portale", "registro")
            servizio_pst_imp = _form_first("servizio_pst", "servizio_pst_preferito")
            id_dfa_imp = _form_first("id_dfa", "idDfa", "IDDFA")
            id_fascicolo_portale_imp = _form_first(
                "id_fascicolo_portale",
                "id_fascicolo_pst",
                "id_fascicolo",
            )

            fascicolo_pw = FascicoloPolisWeb(
                numero_rg=numero_rg_imp,
                anno_rg=anno_rg_imp,
                ruolo=form_data.get("ruolo", "CIVILE_COGNIZIONE"),
                stato=form_data.get("stato", "PENDENTE"),
                oggetto=form_data.get("oggetto", ""),
                sezione=form_data.get("sezione", ""),
                giudice=form_data.get("giudice", ""),
                data_iscrizione=_parse_data(form_data.get("data_iscrizione", "")),
                data_udienza=_parse_data(form_data.get("data_udienza", "")),
                parti=_json.loads(form_data.get("parti_json", "[]") or "[]"),
                parti_dettaglio=_json.loads(form_data.get("parti_dettaglio_json", "[]") or "[]"),
                codice_ufficio=codice_ufficio_imp,
                nome_ufficio=nome_ufficio_imp,
                sub_procedimento=sub_procedimento_imp,
                tipo_registro=tipo_registro_imp,
                registro_portale=registro_portale_imp,
                servizio_pst=servizio_pst_imp,
                urn=_form_first("urn"),
                target_path=_form_first("target_path"),
                id_dfa=id_dfa_imp,
                id_fascicolo=id_fascicolo_portale_imp,
                ruolo_polisweb=_form_first("ruolo_polisweb"),
            )
            documenti_pw = None
            if documenti_json_raw:
                documenti_pw = []
                for row in _json.loads(documenti_json_raw or "[]"):
                    payload = dict(row or {})
                    documenti_pw.append(
                        DocumentoPolisWeb(
                            id_documento=str(payload.get("id_documento") or "").strip(),
                            nome=str(payload.get("nome") or "").strip(),
                            tipo=str(payload.get("tipo") or "").strip(),
                            data_deposito=_parse_data(str(payload.get("data_deposito") or "").strip()),
                            mittente=str(payload.get("mittente") or "").strip(),
                            dimensione_bytes=int(payload.get("dimensione_bytes") or 0),
                            disponibile=_as_bool(payload.get("disponibile", True)),
                            id_deposito=str(payload.get("id_deposito") or "").strip(),
                            tipo_atto=str(payload.get("tipo_atto") or "").strip(),
                        )
                    )

            usa_import_locale = not demo_mode and import_locale_richiesto
            if demo_mode:
                client = crea_client(demo=True)
            elif usa_import_locale:
                client = ClientPolisWebImportOnly()
            else:
                client = crea_client(demo=False)

            gestione_fascicoli = get_fascicoli()
            gestione_clienti = get_clienti()
            gestione_soggetti = get_soggetti()
            fascicolo_esistente = None
            id_fasc_target = form_data.get("id_fasc", "").strip()
            apri_portale = form_data.get("apri_portale") == "1"
            acquisisci_portale = form_data.get("acquisisci_portale") == "1"
            mantieni_albero_originale = form_data.get("mantieni_albero_originale") == "1"

            # I metadati dei documenti ricevuti esplicitamente dal Local Signer
            # sono gia' un import assistito dall'utente e vanno sempre censiti.
            # mantieni_albero_originale governa solo la navigazione/acquisizione
            # successiva della UI, non la perdita dei metadati ufficiali.
            expected_external_id = chiave_esterna_fascicolo_polisweb(fascicolo_pw)

            def _match_text(value: Any) -> str:
                return " ".join(str(value or "").strip().casefold().split())

            def _match_rg(value: Any) -> str:
                text = str(value or "").strip()
                digits = "".join(ch for ch in text if ch.isdigit())
                return str(int(digits)) if digits else text

            def _fasc_portale_value(fascicolo: Any, field_name: str) -> str:
                value = str(getattr(fascicolo, field_name, "") or "").strip()
                if value:
                    return value
                snapshot = getattr(fascicolo, "source_snapshot", {}) or {}
                if isinstance(snapshot, dict):
                    if field_name == "id_fascicolo_portale":
                        return str(snapshot.get("id_fascicolo") or snapshot.get("id_fascicolo_portale") or "").strip()
                    return str(snapshot.get(field_name) or "").strip()
                return ""

            incoming_discriminators = {
                "id_fascicolo_portale": id_fascicolo_portale_imp,
                "id_dfa": id_dfa_imp,
                "sub_procedimento": sub_procedimento_imp,
                "registro_portale": registro_portale_imp or tipo_registro_imp,
                "servizio_pst": servizio_pst_imp,
            }

            def _has_portale_discriminator(fascicolo: Any) -> bool:
                return any(
                    _fasc_portale_value(fascicolo, key)
                    for key in ("id_fascicolo_portale", "id_dfa", "sub_procedimento", "registro_portale")
                )

            def _matches_portale_discriminators(fascicolo: Any) -> bool:
                for key, expected in incoming_discriminators.items():
                    if not expected:
                        continue
                    current = _fasc_portale_value(fascicolo, key)
                    if current and _match_text(current) != _match_text(expected):
                        return False
                return True

            def _matches_rg_office(fascicolo: Any, *, strict: bool) -> bool:
                fasc_numero = _match_rg(getattr(fascicolo, "numero_rg", ""))
                incoming_numero = _match_rg(numero_rg_imp)
                try:
                    fasc_anno = int(getattr(fascicolo, "anno_rg", 0) or 0)
                except (TypeError, ValueError):
                    fasc_anno = 0
                incoming_anno = int(anno_rg_imp or 0)
                fasc_tribunale = _match_text(getattr(fascicolo, "tribunale", ""))
                incoming_tribunale = _match_text(nome_ufficio_imp)
                if strict:
                    return bool(
                        incoming_numero
                        and incoming_anno
                        and incoming_tribunale
                        and fasc_numero == incoming_numero
                        and fasc_anno == incoming_anno
                        and fasc_tribunale == incoming_tribunale
                    )
                if fasc_numero and incoming_numero and fasc_numero != incoming_numero:
                    return False
                if fasc_anno and incoming_anno and fasc_anno != incoming_anno:
                    return False
                if fasc_tribunale and incoming_tribunale and fasc_tribunale != incoming_tribunale:
                    return False
                return True

            def _find_fascicolo_esistente_pst():
                fascicoli = list(gestione_fascicoli.tutti())
                if expected_external_id:
                    for item in fascicoli:
                        if (
                            str(getattr(item, "source_external_id", "") or "").strip() == expected_external_id
                            and _matches_rg_office(item, strict=False)
                        ):
                            return item
                strict_matches = [item for item in fascicoli if _matches_rg_office(item, strict=True)]
                if not strict_matches:
                    return None
                has_incoming_discriminator = any(incoming_discriminators.values())
                if has_incoming_discriminator:
                    marked_matches = [
                        item
                        for item in strict_matches
                        if _has_portale_discriminator(item) and _matches_portale_discriminators(item)
                    ]
                    if marked_matches:
                        return marked_matches[0]
                    unmarked_matches = [item for item in strict_matches if not _has_portale_discriminator(item)]
                    if len(strict_matches) == 1 and unmarked_matches:
                        return unmarked_matches[0]
                    return None
                return strict_matches[0]

            if id_fasc_target:
                fascicolo_target = gestione_fascicoli.get(id_fasc_target)
                if fascicolo_target and _matches_rg_office(fascicolo_target, strict=False) and _matches_portale_discriminators(fascicolo_target):
                    fascicolo_esistente = fascicolo_target

            if fascicolo_esistente is None:
                fascicolo_esistente = _find_fascicolo_esistente_pst()

            if fascicolo_esistente:
                risultato = client.sincronizza_fascicolo_esistente(
                    fascicolo_pw=fascicolo_pw,
                    fascicolo_locale=fascicolo_esistente,
                    gestione_fascicoli=gestione_fascicoli,
                    gestione_clienti=gestione_clienti,
                    avvocato_referente=utente.username if utente else "",
                    gestione_soggetti=gestione_soggetti,
                    documenti_pw=documenti_pw,
                )
            else:
                risultato = client.importa_fascicolo(
                    fascicolo_pw=fascicolo_pw,
                    gestione_fascicoli=gestione_fascicoli,
                    gestione_clienti=gestione_clienti,
                    avvocato_referente=utente.username if utente else "",
                    gestione_soggetti=gestione_soggetti,
                    documenti_pw=documenti_pw,
                )

            if risultato.successo:
                for avviso in risultato.avvisi:
                    livello = "info" if avviso.startswith(("Nuovo soggetto", "Nuova parte")) else "warning"
                    flash(avviso, livello)
                if documenti_prefetch_error and not (
                    risultato.depositi_importati or risultato.documenti_importati
                ):
                    flash(documenti_prefetch_error, "warning")
                flash(risultato.messaggio, "success")
                audit(
                    "polisWeb.sincronizza" if fascicolo_esistente else "polisWeb.importa",
                    "fascicolo",
                    risultato.id_fascicolo_locale,
                    dettagli=f"RG {fascicolo_pw.numero_rg}/{fascicolo_pw.anno_rg}",
                )
                return redirect(
                    url_for(
                        "dettaglio_fascicolo",
                        id_fasc=risultato.id_fascicolo_locale,
                        open_pst_nav="1" if (apri_portale or acquisisci_portale) else None,
                        auto_pst_acquire="1"
                        if (acquisisci_portale and mantieni_albero_originale)
                        else None,
                        preserve_pst_tree="1" if mantieni_albero_originale else None,
                    )
                )
            flash(risultato.messaggio, "danger")
        except Exception as exc:
            flash(str(exc), "danger")
        return redirect(url_for("polisWeb_home"))
