"""Privacy and GDPR routes extracted from web.app."""

from __future__ import annotations

import io
import json
import os
from collections.abc import Callable
from datetime import date, datetime

from flask import Flask, Response, abort, flash, g, jsonify, redirect, render_template, request, send_file, url_for


def _richiede_json() -> bool:
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in (request.headers.get("Accept") or "")
    )


def register_privacy_routes(
    app: Flask,
    *,
    get_trattamenti: Callable[[], object],
    get_clienti: Callable[[], object],
    get_fascicoli: Callable[[], object],
    get_utenti: Callable[[], object],
    audit: Callable[..., None],
) -> None:
    """Register privacy register, GDPR export, and audit export routes."""

    @app.route("/privacy/registro")
    def registro_trattamenti():
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            abort(403)
        return render_template("privacy/registro.html", trattamenti=get_trattamenti().tutti())

    @app.route("/privacy/registro/nuovo", methods=["GET", "POST"])
    def nuovo_trattamento():
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            abort(403)

        if request.method == "POST":
            form = request.form
            get_trattamenti().nuovo(
                nome=form.get("nome", ""),
                finalita=form.get("finalita", ""),
                categoria_dati=form.get("categoria_dati", ""),
                base_giuridica=form.get("base_giuridica", ""),
                soggetti_interessati=form.get("soggetti_interessati", ""),
                destinatari=form.get("destinatari", ""),
                trasferimento_extra_ue=form.get("trasferimento_extra_ue") == "1",
                paese_destinazione=form.get("paese_destinazione", ""),
                termine_conservazione=form.get("termine_conservazione", ""),
                misure_sicurezza=form.get("misure_sicurezza", ""),
                responsabile=form.get("responsabile", ""),
                note=form.get("note", ""),
            )
            audit("privacy.registro.nuovo")
            flash("Trattamento aggiunto al registro.", "success")
            if _richiede_json():
                return jsonify({"ok": True, "message": "Trattamento aggiunto al registro.", "redirect": url_for("registro_trattamenti")})
            return redirect(url_for("registro_trattamenti"))
        return render_template(
            "privacy/registro.html",
            trattamenti=get_trattamenti().tutti(),
            form_nuovo=True,
        )

    @app.route("/privacy/registro/<id_t>/elimina", methods=["POST"])
    def elimina_trattamento(id_t):
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            abort(403)
        try:
            get_trattamenti().elimina(id_t)
            audit("privacy.registro.elimina", risorsa_id=id_t)
            flash("Trattamento eliminato.", "success")
            if _richiede_json():
                return jsonify({"ok": True, "id": id_t, "message": "Trattamento eliminato.", "redirect": url_for("registro_trattamenti")})
        except KeyError as exc:
            if _richiede_json():
                return jsonify({"ok": False, "message": str(exc)}), 400
            flash(str(exc), "danger")
        return redirect(url_for("registro_trattamenti"))

    @app.route("/clienti/<id_cliente>/consenso", methods=["POST"])
    def aggiorna_consenso(id_cliente):
        """Registra o aggiorna il consenso al trattamento dati del cliente."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("clienti.scrivi"):
            abort(403)
        clienti = get_clienti()
        cliente = clienti.get(id_cliente)
        if not cliente:
            abort(404)
        form = request.form
        consenso = form.get("consenso_trattamento") == "1"
        clienti.aggiorna(
            id_cliente,
            consenso_trattamento=consenso,
            data_consenso=form.get("data_consenso", date.today().isoformat()),
            modalita_consenso=form.get("modalita_consenso", ""),
        )
        audit(
            "clienti.consenso",
            "cliente",
            id_cliente,
            dettagli=f"{'concesso' if consenso else 'revocato'} via {form.get('modalita_consenso', '')}",
        )
        flash("Consenso aggiornato.", "success")
        return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))

    @app.route("/clienti/<id_cliente>/informativa.pdf")
    def informativa_privacy_pdf(id_cliente):
        """Genera il PDF dell'informativa privacy per il cliente."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("clienti.leggi"):
            abort(403)
        cliente = get_clienti().get(id_cliente)
        if not cliente:
            abort(404)
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

        buffer = io.BytesIO()
        documento = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=2.5 * cm,
            rightMargin=2.5 * cm,
            topMargin=2.5 * cm,
            bottomMargin=2.5 * cm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("title", parent=styles["Title"], fontSize=14, spaceAfter=6)
        heading_style = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, spaceAfter=4)
        body_style = ParagraphStyle("body", parent=styles["Normal"], fontSize=9, spaceAfter=6, leading=14)
        studio = os.getenv("PCT_STUDIO_NOME", "Studio Legale")
        elements = [
            Paragraph("INFORMATIVA SUL TRATTAMENTO DEI DATI PERSONALI", title_style),
            Paragraph("ai sensi degli artt. 13-14 del Regolamento UE 2016/679 (GDPR)", body_style),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3a5c")),
            Spacer(1, 0.4 * cm),
            Paragraph("1. Titolare del trattamento", heading_style),
            Paragraph(f"{studio} - i recapiti sono disponibili presso lo studio.", body_style),
            Paragraph("2. Finalita e base giuridica del trattamento", heading_style),
            Paragraph(
                "I Suoi dati personali sono trattati per l'erogazione di servizi legali, "
                "la gestione dei fascicoli e procedimenti giudiziari e stragiudiziali, "
                "nonche per adempiere ad obblighi legali e contabili. "
                "La base giuridica e l'esecuzione di un contratto (art. 6.1.b GDPR) "
                "e l'adempimento di obblighi legali (art. 6.1.c GDPR).",
                body_style,
            ),
            Paragraph("3. Categorie di dati trattati", heading_style),
            Paragraph(
                "Dati anagrafici e di contatto, codice fiscale, dati relativi a procedimenti "
                "giudiziari, dati economici e patrimoniali strettamente necessari "
                "all'esercizio dell'attivita professionale.",
                body_style,
            ),
            Paragraph("4. Destinatari dei dati", heading_style),
            Paragraph(
                "I Suoi dati possono essere comunicati ad autorita giudiziarie e "
                "amministrative, alla controparte e ai suoi difensori, nonche "
                "a consulenti tecnici e periti nell'ambito dei procedimenti. "
                "Non vengono trasferiti a Paesi terzi.",
                body_style,
            ),
            Paragraph("5. Periodo di conservazione", heading_style),
            Paragraph(
                "I dati saranno conservati per l'intera durata del rapporto professionale "
                "e per i successivi 10 anni, ai sensi dell'art. 2220 c.c. e delle norme "
                "deontologiche forensi.",
                body_style,
            ),
            Paragraph("6. Diritti dell'interessato", heading_style),
            Paragraph(
                "Ha diritto di accedere ai Suoi dati (art. 15), rettificarli (art. 16), "
                "cancellarli (art. 17), limitarne il trattamento (art. 18), "
                "riceverne copia portabile (art. 20) e opporsi al trattamento (art. 21). "
                "Puo esercitare tali diritti contattando direttamente lo studio.",
                body_style,
            ),
            Paragraph("7. Diritto di reclamo", heading_style),
            Paragraph(
                "Ha il diritto di proporre reclamo al Garante per la protezione dei "
                "dati personali (www.garanteprivacy.it).",
                body_style,
            ),
            Spacer(1, 1 * cm),
            HRFlowable(width="100%", thickness=0.5, color=colors.grey),
            Spacer(1, 0.3 * cm),
            Paragraph(
                f"Informativa generata il {date.today().strftime('%d/%m/%Y')} per: "
                f"<b>{cliente.nome_completo}</b>",
                body_style,
            ),
        ]
        documento.build(elements)
        buffer.seek(0)
        audit("clienti.informativa_pdf", "cliente", id_cliente, dettagli=f"PDF Art.13 - {cliente.nome_completo}")
        nome = f"informativa_{cliente.nome_completo.replace(' ', '_').lower()}.pdf"
        return send_file(
            buffer,
            as_attachment=True,
            download_name=nome,
            mimetype="application/pdf",
        )

    @app.route("/clienti/<id_cliente>/porta-via")
    def gdpr_portabilita(id_cliente):
        """Esporta i dati personali del cliente in JSON strutturato."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("clienti.leggi"):
            abort(403)
        cliente = get_clienti().get(id_cliente)
        if not cliente:
            abort(404)
        fascicoli_cliente = [fascicolo for fascicolo in get_fascicoli().tutti() if fascicolo.id_cliente == id_cliente]
        payload = {
            "metadati": {
                "standard": "GDPR Art. 20 - Portabilita dei dati personali",
                "regolamento": "Reg. UE 2016/679",
                "data_estrazione": datetime.now().isoformat(),
                "estratto_da": utente.username,
                "versione": "1.0",
            },
            "anagrafica": {
                "tipo": cliente.tipo.value,
                "nome": cliente.nome,
                "cognome": cliente.cognome,
                "ragione_sociale": cliente.ragione_sociale,
                "codice_fiscale": cliente.codice_fiscale,
                "partita_iva": cliente.partita_iva,
                "data_nascita": cliente.data_nascita,
                "luogo_nascita": cliente.luogo_nascita,
                "provincia_nascita": cliente.provincia_nascita,
                "nazionalita": cliente.nazionalita,
                "sesso": cliente.sesso,
                "forma_giuridica": cliente.forma_giuridica,
                "rappresentante_legale": cliente.rappresentante_legale,
            },
            "recapiti": {
                "telefono": cliente.recapiti.telefono,
                "cellulare": cliente.recapiti.cellulare,
                "email": cliente.recapiti.email,
                "pec": cliente.recapiti.pec,
                "fax": cliente.recapiti.fax,
            },
            "indirizzi": {
                "residenza": str(cliente.indirizzo_residenza) or None,
                "domicilio": str(cliente.indirizzo_domicilio) or None,
                "sede_legale": str(cliente.indirizzo_sede_legale) or None,
            },
            "dati_studio": {
                "avvocato_referente": cliente.avvocato_referente,
                "data_prima_acquisizione": cliente.data_prima_acquisizione,
                "stato": cliente.stato.value,
                "provenienza": cliente.provenienza,
                "note": cliente.note,
            },
            "procedimenti": [
                {
                    "numero_rg": procedimento.numero_rg,
                    "anno": procedimento.anno,
                    "tribunale": procedimento.tribunale,
                    "descrizione": procedimento.descrizione,
                    "data_apertura": procedimento.data_apertura,
                    "data_chiusura": procedimento.data_chiusura,
                    "attivo": procedimento.attivo,
                }
                for procedimento in cliente.procedimenti
            ],
            "fascicoli": [
                {
                    "numero": fascicolo.numero,
                    "titolo": fascicolo.titolo,
                    "tipo": fascicolo.tipo.value,
                    "stato": fascicolo.stato.value,
                    "data_apertura": fascicolo.data_apertura,
                    "n_documenti": len(fascicolo.documenti),
                }
                for fascicolo in fascicoli_cliente
            ],
        }
        audit("gdpr.portabilita", "cliente", id_cliente, dettagli=f"Export Art.20 - {cliente.nome_completo}")
        nome = f"dati_{cliente.nome_completo.replace(' ', '_').lower()}_{date.today().isoformat()}.json"
        response = Response(
            json.dumps(payload, ensure_ascii=False, indent=2),
            mimetype="application/json",
        )
        response.headers["Content-Disposition"] = f'attachment; filename="{nome}"'
        return response

    @app.route("/audit/esporta.csv")
    def esporta_audit_csv():
        """Esporta l'audit log come CSV."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("audit.leggi"):
            abort(403)
        csv_data = get_utenti().esporta_audit_csv(
            id_utente=request.args.get("id_utente", ""),
            azione=request.args.get("azione", ""),
            da=request.args.get("da") or None,
            a=request.args.get("a") or None,
        )
        audit("audit.esporta_csv")
        response = Response(csv_data, mimetype="text/csv; charset=utf-8")
        response.headers["Content-Disposition"] = f'attachment; filename="audit_{date.today().isoformat()}.csv"'
        return response
