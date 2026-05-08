"""Route PolisWeb estratte dal blocco legacy telematico."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from flask import Flask, flash, g, redirect, render_template, request, url_for

from web.bootstrap.telematico_portali_common import (
    group_documenti_per_deposito,
    resolve_nome_ufficio,
)


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
) -> None:
    """Register PolisWeb consultation and import routes."""

    @app.route("/polisWeb", methods=["GET"])
    def polisWeb_home():
        import traceback as _tb

        try:
            auth_mode = polis_auth_mode()
            demo_mode = auth_mode == "demo"
            server_demo_mode = auth_mode != "reale"
            pkcs11_mode = auth_mode == "pkcs11"
            id_fasc = request.args.get("id_fasc", "")
            fascicolo_ctx = get_fascicoli().get(id_fasc) if id_fasc else None
            return render_template(
                "polisWeb.html",
                demo_mode=demo_mode,
                server_demo_mode=server_demo_mode,
                pkcs11_mode=pkcs11_mode,
                fascicolo=fascicolo_ctx,
                id_fasc=id_fasc,
                cert_preferences=polis_cert_preferences(),
            )
        except Exception as exc:
            tb = "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))
            app.logger.error("ERRORE polisWeb_home:\n%s", tb)
            return f"<pre style='color:red;padding:2em'><b>Errore PolisWeb:</b>\n{tb}</pre>", 500

    @app.route("/polisWeb/ricerca", methods=["POST"])
    def polisWeb_ricerca():
        form_data = request.form
        tribunale = form_data.get("tribunale", "").strip()
        auth_mode = polis_auth_mode()
        server_demo_mode = form_data.get("server_demo_mode") == "1" or auth_mode != "reale"
        demo_mode = form_data.get("demo_mode") == "1" or auth_mode == "demo"
        pkcs11_mode = auth_mode == "pkcs11"

        if not tribunale:
            flash("Seleziona un tribunale.", "danger")
            return redirect(url_for("polisWeb_home"))

        id_fasc = form_data.get("id_fasc", "").strip()
        fascicolo_ctx = get_fascicoli().get(id_fasc) if id_fasc else None
        try:
            numero_rg = form_data.get("numero_rg", "").strip() or None
            anno_rg = int(form_data.get("anno_rg") or 0) or None
            nome_parte = form_data.get("nome_parte", "").strip() or None
            cf_parte = form_data.get("cf_parte", "").strip() or None
        except (ValueError, TypeError) as exc:
            flash(f"Parametri non validi: {exc}", "danger")
            return redirect(url_for("polisWeb_home"))

        try:
            from pct.polisWeb import crea_client

            client = crea_client(demo=demo_mode)
            fascicoli = client.ricerca_fascicoli(
                tribunale=tribunale,
                numero_rg=numero_rg,
                anno_rg=anno_rg,
                nome_parte=nome_parte,
                codice_fiscale_parte=cf_parte,
            )
        except Exception as exc:
            app.logger.exception("Errore polisWeb_ricerca: %s", exc)
            flash(f"Errore ricerca PST: {exc}", "danger")
            return redirect(url_for("polisWeb_home"))

        tribunale_sel_nome = resolve_nome_ufficio(tribunale)
        return render_template(
            "polisWeb.html",
            fascicoli=fascicoli,
            tribunale_sel=tribunale,
            tribunale_sel_nome=tribunale_sel_nome,
            numero_rg=numero_rg or "",
            anno_rg=anno_rg or "",
            nome_parte=nome_parte or "",
            cf_parte=cf_parte or "",
            demo_mode=demo_mode,
            server_demo_mode=server_demo_mode,
            pkcs11_mode=pkcs11_mode,
            fascicolo=fascicolo_ctx,
            id_fasc=id_fasc,
            cert_preferences=polis_cert_preferences(),
        )

    @app.route("/polisWeb/documenti", methods=["GET"])
    def polisWeb_documenti():
        codice_ufficio = request.args.get("codice_ufficio", "")
        numero_rg = request.args.get("numero_rg", "")
        auth_mode = polis_auth_mode()
        demo_mode = auth_mode != "reale"
        try:
            anno_rg = int(request.args.get("anno_rg", 0) or 0)
        except (ValueError, TypeError):
            anno_rg = 0
        try:
            from pct.polisWeb import crea_client

            client = crea_client(demo=demo_mode)
            documenti = client.consulta_documenti(codice_ufficio, numero_rg, anno_rg)
        except Exception as exc:
            app.logger.exception("Errore polisWeb_documenti: %s", exc)
            flash(str(exc), "danger")
            return redirect(url_for("polisWeb_home"))

        return render_template(
            "polisWeb_documenti.html",
            documenti=documenti,
            depositi=group_documenti_per_deposito(documenti),
            numero_rg=numero_rg,
            anno_rg=anno_rg,
            codice_ufficio=codice_ufficio,
            nome_ufficio=resolve_nome_ufficio(codice_ufficio),
            demo_mode=demo_mode,
        )

    @app.route("/polisWeb/fascicolo-wizard", methods=["GET"])
    def polisWeb_fascicolo_wizard():
        codice_ufficio = request.args.get("codice_ufficio", "")
        numero_rg = request.args.get("numero_rg", "")
        auth_mode = polis_auth_mode()
        demo_mode = auth_mode != "reale"
        id_fasc = request.args.get("id_fasc", "")
        sezione_attiva = request.args.get("sezione", "attivita_processuali")

        try:
            anno_rg = int(request.args.get("anno_rg", 0) or 0)
        except (ValueError, TypeError):
            anno_rg = 0

        fascicolo_ctx = get_fascicoli().get(id_fasc) if id_fasc else None
        try:
            from pct.polisWeb import PST_SEZIONI_WIZARD, crea_client, raggruppa_per_sezioni_wizard

            client = crea_client(demo=demo_mode)
            documenti = client.consulta_documenti(codice_ufficio, numero_rg, anno_rg)
        except Exception as exc:
            app.logger.exception("Errore polisWeb_fascicolo_wizard: %s", exc)
            flash(str(exc), "danger")
            return redirect(url_for("polisWeb_home"))

        sezioni_dati = raggruppa_per_sezioni_wizard(documenti)
        sezioni_conteggi = {
            section_id: sum(len(deposito["documenti"]) for deposito in depositi)
            for section_id, depositi in sezioni_dati.items()
        }
        sezione_ids = [section["id"] for section in PST_SEZIONI_WIZARD]
        if sezione_attiva not in sezione_ids:
            sezione_attiva = sezione_ids[0]

        return render_template(
            "pst_wizard.html",
            documenti=documenti,
            sezioni_wizard=PST_SEZIONI_WIZARD,
            sezioni_dati=sezioni_dati,
            sezioni_conteggi=sezioni_conteggi,
            sezione_attiva=sezione_attiva,
            numero_rg=numero_rg,
            anno_rg=anno_rg,
            codice_ufficio=codice_ufficio,
            nome_ufficio=resolve_nome_ufficio(codice_ufficio),
            demo_mode=demo_mode,
            fascicolo=fascicolo_ctx,
            id_fasc=id_fasc,
            n_tot=len(documenti),
            oggi=date.today(),
        )

    @app.route("/polisWeb/importa", methods=["POST"])
    def polisWeb_importa():
        import json as _json

        from pct.polisWeb import (
            ClientPolisWebImportOnly,
            DocumentoPolisWeb,
            FascicoloPolisWeb,
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

            if id_fasc_target:
                fascicolo_target = gestione_fascicoli.get(id_fasc_target)
                if (
                    fascicolo_target
                    and (not (fascicolo_target.numero_rg or "").strip() or fascicolo_target.numero_rg == numero_rg_imp)
                    and (
                        not int(getattr(fascicolo_target, "anno_rg", 0) or 0)
                        or fascicolo_target.anno_rg == anno_rg_imp
                    )
                    and (not fascicolo_target.tribunale or fascicolo_target.tribunale == nome_ufficio_imp)
                ):
                    fascicolo_esistente = fascicolo_target

            if fascicolo_esistente is None:
                for item in gestione_fascicoli.tutti():
                    if (
                        item.numero_rg == numero_rg_imp
                        and item.anno_rg == anno_rg_imp
                        and item.tribunale == nome_ufficio_imp
                    ):
                        fascicolo_esistente = item
                        break

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
