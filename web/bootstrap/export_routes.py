"""Export and reporting routes extracted from web.app."""

from __future__ import annotations

import csv
import io
import os
from collections.abc import Callable
from datetime import date

from flask import Flask, Response, flash, redirect, request, send_file, url_for

from pct.clienti import StatoCliente, TipoCliente
from pct.fascicoli import StatoFascicolo, TipoFascicolo
from pct.reports import fascicolo_pdf, lista_clienti_pdf, lista_fascicoli_pdf, scadenze_pdf
from pct.scadenziario import PrioritaTermine, TipoTermine


def _enum_export(enum_cls, valore: str):
    """Valore di filtro dell'export: sconosciuto o vuoto = nessun filtro (mai un errore 500)."""
    chiave = str(valore or "").strip().upper()
    if not chiave or chiave == "TUTTI":
        return None
    try:
        return enum_cls(chiave)
    except ValueError:
        return None


def _stato_export(valore: str) -> tuple[StatoFascicolo | None, bool]:
    """«DA_ARCHIVIARE» è lo stato derivato dell'elenco: fascicolo DEFINITO pronto per l'archivio."""
    if str(valore or "").strip().upper() == "DA_ARCHIVIARE":
        return StatoFascicolo.DEFINITO, True
    return _enum_export(StatoFascicolo, valore), False


def register_export_routes(
    app: Flask,
    *,
    get_clienti: Callable[[], object],
    get_fascicoli: Callable[[], object],
    get_scadenziario: Callable[[], object],
    audit: Callable[..., None],
) -> None:
    """Register CSV and PDF export routes."""

    def _csv_response(righe: list[dict], nome_file: str) -> Response:
        if not righe:
            output = io.StringIO()
            output.write("# Nessun dato da esportare\n")
            csv_data = output.getvalue()
        else:
            output = io.StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=righe[0].keys(),
                extrasaction="ignore",
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(righe)
            csv_data = output.getvalue()
        return Response(
            csv_data,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{nome_file}"'},
        )

    @app.route("/clienti/export.csv")
    def export_clienti_csv():
        gc = get_clienti()
        testo = request.args.get("q", "").strip()
        tipo_f = request.args.get("tipo")
        stato_f = request.args.get("stato", "")
        tipo = TipoCliente(tipo_f) if tipo_f else None
        stato = StatoCliente(stato_f) if stato_f else None
        clienti = gc.cerca(testo=testo, tipo=tipo, stato=stato) if testo else gc.tutti(stato=stato, tipo=tipo)
        # «Esporta selezione» della pagina React: solo i clienti scelti.
        scelti = {v.strip() for v in request.args.get("ids", "").split(",") if v.strip()}
        if scelti:
            clienti = [c for c in clienti if str(getattr(c, "id", "")) in scelti]
        righe = []
        for c in clienti:
            d = c.to_dict()
            ind = d.get("indirizzo") or {}
            righe.append(
                {
                    "id": d["id"],
                    "cognome": d.get("cognome", ""),
                    "nome": d.get("nome", ""),
                    "ragione_sociale": d.get("ragione_sociale", ""),
                    "tipo": d.get("tipo", ""),
                    "stato": d.get("stato", ""),
                    "codice_fiscale": d.get("codice_fiscale", ""),
                    "partita_iva": d.get("partita_iva", ""),
                    "email": d.get("email", ""),
                    "telefono": d.get("telefono", ""),
                    "citta": ind.get("citta", "") if isinstance(ind, dict) else "",
                }
            )
        audit("clienti.export_csv")
        return _csv_response(righe, f"clienti_{date.today().isoformat()}.csv")

    def _fascicoli_da_esportare() -> list:
        """Fascicoli filtrati come nell'elenco: «da archiviare» è un DEFINITO pronto per l'archivio."""
        gf = get_fascicoli()
        testo = request.args.get("q", "").strip()
        stato, solo_pronti = _stato_export(request.args.get("stato", ""))
        tipo = _enum_export(TipoFascicolo, request.args.get("tipo", ""))
        fascicoli = gf.cerca(testo=testo, stato=stato, tipo=tipo) if testo else gf.tutti(stato=stato, tipo=tipo)
        if solo_pronti:
            fascicoli = [f for f in fascicoli if bool(getattr(f, "archivio_pronto", False))]
        return list(fascicoli)

    @app.route("/fascicoli/export.csv")
    def export_fascicoli_csv():
        fascicoli = _fascicoli_da_esportare()
        righe = []
        for f in fascicoli:
            d = f.to_dict()
            righe.append(
                {
                    "numero": d.get("numero", ""),
                    "titolo": d.get("titolo", ""),
                    "tipo": d.get("tipo", ""),
                    "stato": d.get("stato", ""),
                    "tribunale": d.get("tribunale", ""),
                    "numero_rg": d.get("numero_rg", ""),
                    "anno_rg": d.get("anno_rg", ""),
                    "nome_cliente": d.get("nome_cliente", ""),
                    "controparte": d.get("controparte", ""),
                    "avvocato_referente": d.get("avvocato_referente", ""),
                    "data_apertura": d.get("data_apertura", ""),
                    "data_chiusura": d.get("data_chiusura", ""),
                }
            )
        audit("fascicoli.export_csv")
        return _csv_response(righe, f"fascicoli_{date.today().isoformat()}.csv")

    @app.route("/fascicoli/export.pdf")
    def export_fascicoli_pdf():
        try:
            fascicoli = _fascicoli_da_esportare()
            studio_nome = os.getenv("PCT_STUDIO_NOME", "Studio Legale")
            mesi_it = [
                "Gennaio",
                "Febbraio",
                "Marzo",
                "Aprile",
                "Maggio",
                "Giugno",
                "Luglio",
                "Agosto",
                "Settembre",
                "Ottobre",
                "Novembre",
                "Dicembre",
            ]
            oggi = date.today()
            mese_label = f"{mesi_it[oggi.month - 1]} {oggi.year}"
            titolo = f"Elenco Fascicoli — {mese_label}"
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                out = tmp.name
            lista_fascicoli_pdf([f.to_dict() for f in fascicoli], out, titolo=titolo, studio_nome=studio_nome)
            audit("fascicoli.export_pdf")
            nome_file = f"fascicoli_{date.today().isoformat()}.pdf"
            return send_file(out, as_attachment=True, download_name=nome_file, mimetype="application/pdf")
        except Exception as e:
            app.logger.exception("Errore export_fascicoli_pdf: %s", e)
            flash(f"Impossibile generare il PDF: {e}", "danger")
            return redirect(url_for("lista_fascicoli"))

    @app.route("/clienti/export.pdf")
    def export_clienti_pdf():
        gc = get_clienti()
        testo = request.args.get("q", "").strip()
        tipo_f = request.args.get("tipo")
        stato_f = request.args.get("stato", "ATTIVO")
        try:
            tipo = TipoCliente(tipo_f) if tipo_f else None
            stato = StatoCliente(stato_f) if stato_f else None
            clienti = gc.cerca(testo=testo, tipo=tipo, stato=stato) if testo else gc.tutti(stato=stato, tipo=tipo)
            studio_nome = os.getenv("PCT_STUDIO_NOME", "Studio Legale")
            mesi_it = [
                "Gennaio",
                "Febbraio",
                "Marzo",
                "Aprile",
                "Maggio",
                "Giugno",
                "Luglio",
                "Agosto",
                "Settembre",
                "Ottobre",
                "Novembre",
                "Dicembre",
            ]
            oggi = date.today()
            mese_label = f"{mesi_it[oggi.month - 1]} {oggi.year}"
            titolo = f"Elenco Clienti — {mese_label}"
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                out = tmp.name
            lista_clienti_pdf([c.to_dict() for c in clienti], out, titolo=titolo, studio_nome=studio_nome)
            audit("clienti.export_pdf")
            nome_file = f"clienti_{date.today().isoformat()}.pdf"
            return send_file(out, as_attachment=True, download_name=nome_file, mimetype="application/pdf")
        except Exception as e:
            app.logger.exception("Errore export_clienti_pdf: %s", e)
            flash(f"Impossibile generare il PDF: {e}", "danger")
            return redirect(url_for("lista_clienti"))

    @app.route("/scadenziario/export.csv")
    def export_scadenziario_csv():
        gs = get_scadenziario()
        filtro_tipo = request.args.get("tipo", "")
        filtro_priorita = request.args.get("priorita", "")
        id_fascicolo = request.args.get("id_fascicolo", "")
        solo_aperte = request.args.get("stato", "aperte") != "tutte"
        scadenze = gs.tutte(
            tipo=TipoTermine(filtro_tipo) if filtro_tipo else None,
            priorita=PrioritaTermine(filtro_priorita) if filtro_priorita else None,
            id_fascicolo=id_fascicolo,
            solo_aperte=solo_aperte,
        )
        righe = []
        for s in scadenze:
            d = s.to_dict() if hasattr(s, "to_dict") else vars(s)
            righe.append(
                {
                    "titolo": d.get("titolo", ""),
                    "tipo": d.get("tipo", ""),
                    "data_scadenza": d.get("data_scadenza", ""),
                    "priorita": d.get("priorita", ""),
                    "stato": d.get("stato", ""),
                    "perentorio": d.get("perentorio", ""),
                    "id_fascicolo": d.get("id_fascicolo", ""),
                    "giorni_preavviso": str(d.get("giorni_preavviso", "")),
                    "completata_il": d.get("completata_il", ""),
                    "note": d.get("note", ""),
                }
            )
        audit("scadenziario.export_csv")
        return _csv_response(righe, f"scadenziario_{date.today().isoformat()}.csv")

    @app.route("/fascicoli/<id_fasc>/pdf")
    def fascicolo_pdf_export(id_fasc):
        gf = get_fascicoli()
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))
        studio_nome = os.getenv("PCT_STUDIO_NOME", "Studio Legale")
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            out = tmp.name
        fascicolo_pdf(fasc.to_dict(), out, studio_nome=studio_nome)
        nome_file = f"fascicolo_{fasc.numero or id_fasc}.pdf".replace("/", "-").replace(" ", "_")
        audit("fascicoli.esporta_pdf", risorsa_tipo="fascicolo", risorsa_id=id_fasc)
        return send_file(out, as_attachment=True, download_name=nome_file, mimetype="application/pdf")

    @app.route("/scadenziario/pdf")
    def scadenziario_pdf_export():
        gs = get_scadenziario()
        stato_raw = request.args.get("stato", "")
        solo_aperte = stato_raw != "tutte"
        lista = gs.tutte(solo_aperte=solo_aperte)
        studio_nome = os.getenv("PCT_STUDIO_NOME", "Studio Legale")
        mese_label = date.today().strftime("%B %Y").capitalize()
        titolo_pdf = f"Scadenziario — {mese_label}"
        dati = [
            {
                "scadenza": s.data_scadenza,
                "titolo": s.titolo,
                "tipo": s.tipo.value if hasattr(s.tipo, "value") else str(s.tipo),
                "fascicolo": s.id_fascicolo or "",
                "priorita": s.priorita.value if hasattr(s.priorita, "value") else str(s.priorita),
                "perentorio": s.perentorio,
            }
            for s in lista
        ]
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            out = tmp.name
        scadenze_pdf(dati, out, titolo=titolo_pdf, studio_nome=studio_nome)
        nome_file = f"scadenziario_{date.today().isoformat()}.pdf"
        audit("scadenziario.esporta_pdf")
        return send_file(out, as_attachment=True, download_name=nome_file, mimetype="application/pdf")
