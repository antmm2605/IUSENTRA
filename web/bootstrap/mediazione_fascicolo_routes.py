"""API JSON della mediazione nel fascicolo, con autorizzazioni dello studio."""
from __future__ import annotations

from flask import g, jsonify, request

from pct.fascicoli import TipoDocumento
from pct.mediazione_procedimenti import FONTI, MediazioneProcedimentiRepository, calendario, normalizza, verifica
from web.services.mediazione_fascicolo import acquisisci_modulo, collega_organismo, organismo, organismi


def register_mediazione_fascicolo_routes(app, *, get_fascicoli, cliente_accessibile, salva_documento_fascicolo, decrypt_doc):
    def context(id_fasc, write=False):
        user = getattr(g, "utente_corrente", None)
        can = getattr(user, "ha_permesso", lambda _: False)
        if not can("fascicoli.scrivi" if write else "fascicoli.leggi"):
            raise PermissionError("Modifica non consentita." if write else "Accesso al fascicolo non consentito.")
        gf = get_fascicoli()
        fasc = gf.get(id_fasc)
        if not fasc or (fasc.id_cliente and not cliente_accessibile(fasc.id_cliente)):
            raise PermissionError("Fascicolo non accessibile.")
        return gf, fasc, MediazioneProcedimentiRepository(gf._studio_db), user

    def result(repo, fasc, user):
        rows = repo.lista(fasc.id)
        return {"ok": True, "id_fascicolo": fasc.id, "source_of_truth": repo.source_of_truth,
                "can_write": bool(user.ha_permesso("fascicoli.scrivi")),
                "procedimenti": [dict(row, controlli=verifica(row), calendario=calendario(row)) for row in rows],
                "documenti": [{"id": doc.id, "nome": doc.nome,
                               "preview": f"/fascicoli/{fasc.id}/documenti/{doc.id}/visualizza"} for doc in fasc.documenti],
                "proposta": {"titolo": f"Mediazione — {fasc.titolo}", "oggetto": fasc.oggetto or fasc.titolo,
                             "parti": [{"nome": name, "ruolo": role, "codice_fiscale": cf, "difensore": lawyer}
                                       for name, role, cf, lawyer in (
                                           (fasc.nome_cliente, "istante", "", fasc.avvocato_referente),
                                           (fasc.controparte, "invitata", fasc.cf_controparte, fasc.avvocato_controparte)) if name]},
                "audit": repo.audit(fasc.id), "fonti": FONTI}

    def error(exc):
        if isinstance(exc, PermissionError):
            return jsonify(ok=False, message=str(exc)), 403
        if isinstance(exc, (ValueError, KeyError, TypeError)):
            return jsonify(ok=False, message=str(exc)), 422
        app.logger.exception("Errore nel procedimento di mediazione")
        return jsonify(ok=False, message="Operazione non riuscita. I dati inseriti restano nel modulo; riprova il salvataggio."), 503

    @app.route("/api/fascicoli/<id_fasc>/mediazioni", methods=["GET", "POST"])
    def fascicolo_mediazioni(id_fasc):
        try:
            gf, fasc, repo, user = context(id_fasc, request.method == "POST")
            if request.method == "POST":
                body = request.get_json(silent=True)
                if not isinstance(body, dict):
                    raise ValueError("Dati del procedimento non validi.")
                identifier = str(body.get("id") or "")
                previous = next((p for p in repo.lista(fasc.id) if p["id"] == identifier), None)
                if identifier and not previous:
                    raise PermissionError("Procedimento non accessibile.")
                version = body.get("versione", 0)
                if not isinstance(version, int) or isinstance(version, bool) or version < 0 or (previous and version == 0):
                    raise ValueError("Versione del procedimento non valida.")
                payload = normalizza(body, {d.id for d in fasc.documenti})
                collega_organismo(payload, previous, app.config)
                repo.salva(fasc.id, identifier, version, payload, str(user.id))
            return jsonify(result(repo, fasc, user))
        except Exception as exc:
            return error(exc)

    @app.route("/api/fascicoli/<id_fasc>/mediazioni/organismi")
    def fascicolo_mediazione_organismi(id_fasc):
        try:
            context(id_fasc)
            number = request.args.get("numero", "")
            return jsonify(ok=True, **({"organismo": organismo(app.config, number)} if number else {"organismi": organismi(app.config)}))
        except Exception as exc:
            return error(exc)

    @app.route("/api/fascicoli/<id_fasc>/mediazioni/<identifier>/modulo", methods=["POST"])
    def fascicolo_mediazione_modulo(id_fasc, identifier):
        try:
            gf, fasc, repo, user = context(id_fasc, True)
            previous = next((p for p in repo.lista(fasc.id) if p["id"] == identifier), None)
            body = request.get_json(silent=True) or {}
            if not previous:
                raise PermissionError("Procedimento non accessibile.")
            if previous["versione"] != body.get("versione"):
                raise ValueError("Il procedimento è cambiato: ricarica prima di acquisire il modulo.")
            raw, filename, source = acquisisci_modulo(app.config, previous["organismo_numero"], body.get("url"))
            doc = salva_documento_fascicolo(gf, fasc.id, filename, raw, TipoDocumento.ALLEGATO,
                                            tags=["mediazione", "modulo_organismo"],
                                            note=f"Modulo organismo {previous['organismo_numero']}: {source['url']}",
                                            caricato_da=str(user.id), preserva_contenuto_originale=True)
            payload = normalizza(previous, {d.id for d in fasc.documenti})
            collega_organismo(payload, previous, app.config)
            payload.update(modulo_ufficiale_documento=doc.id, modulo_fonte=source, modulo_verificato=False)
            payload["moduli_organismo"] = [m for m in payload["moduli_organismo"] if m["documento"] != doc.id]
            payload["moduli_organismo"].append({"documento": doc.id, "nome": doc.nome, "fonte": source, "copie_compilate": []})
            repo.salva(fasc.id, identifier, previous["versione"], payload, str(user.id))
            return jsonify(result(repo, fasc, user))
        except Exception as exc:
            return error(exc)

    @app.route("/api/fascicoli/<id_fasc>/mediazioni/<identifier>/bozza", methods=["POST"])
    def fascicolo_mediazione_bozza(id_fasc, identifier):
        try:
            from pct.mediazione_documenti import bozza_istanza

            gf, fasc, repo, user = context(id_fasc, True)
            previous = next((p for p in repo.lista(fasc.id) if p["id"] == identifier), None)
            body = request.get_json(silent=True) or {}
            if not previous:
                raise PermissionError("Procedimento non accessibile.")
            if previous["versione"] != body.get("versione"):
                raise ValueError("Ricarica i dati prima di generare la bozza.")
            raw = bozza_istanza(previous)
            doc = salva_documento_fascicolo(gf, fasc.id, f"Bozza_mediazione_{identifier}_v{previous['versione']}.pdf", raw,
                                            TipoDocumento.ATTO_GIUDIZIARIO, tags=["mediazione", "bozza_istanza"],
                                            caricato_da=str(user.id), preserva_contenuto_originale=True)
            payload = normalizza(previous, {d.id for d in fasc.documenti})
            collega_organismo(payload, previous, app.config)
            payload["bozza_documento"] = doc.id
            repo.salva(fasc.id, identifier, previous["versione"], payload, str(user.id))
            return jsonify(result(repo, fasc, user))
        except Exception as exc:
            return error(exc)

    @app.route("/api/fascicoli/<id_fasc>/mediazioni/<identifier>/modulo/copia", methods=["POST"])
    def fascicolo_mediazione_copia(id_fasc, identifier):
        try:
            gf, fasc, repo, user = context(id_fasc, True)
            previous = next((p for p in repo.lista(fasc.id) if p["id"] == identifier), None)
            body = request.get_json(silent=True) or {}
            if not previous or previous["versione"] != body.get("versione"):
                raise ValueError("Ricarica il procedimento prima di creare la copia.")
            entry = next((m for m in previous.get("moduli_organismo", []) if m["documento"] == previous.get("modulo_ufficiale_documento") and m["fonte"]["organismo_numero"] == previous["organismo_numero"]), None)
            doc = next((d for d in fasc.documenti if entry and d.id == entry["documento"]), None)
            if not doc or not doc.nome.lower().endswith((".doc", ".docx")):
                raise ValueError("Seleziona un modulo Word acquisito dall'organismo.")
            raw = decrypt_doc(gf.percorso_documento(fasc.id, doc.id).read_bytes())
            copied = salva_documento_fascicolo(gf, fasc.id, f"Copia_da_compilare_{doc.nome}", raw, TipoDocumento.ALLEGATO,
                                               tags=["mediazione", "copia_modulo"], caricato_da=str(user.id),
                                               preserva_contenuto_originale=True)
            payload = normalizza(previous, {d.id for d in fasc.documenti})
            collega_organismo(payload, previous, app.config)
            payload["modulo_compilato_documento"] = copied.id
            for item in payload["moduli_organismo"]:
                if item["documento"] == doc.id:
                    item.setdefault("copie_compilate", []).append(copied.id)
            repo.salva(fasc.id, identifier, previous["versione"], payload, str(user.id))
            return jsonify(result(repo, fasc, user))
        except Exception as exc:
            return error(exc)

    @app.route("/api/fascicoli/<id_fasc>/mediazioni/<identifier>/modulo/campi", methods=["GET", "POST"])
    def fascicolo_mediazione_campi(id_fasc, identifier):
        try:
            from pct.mediazione_documenti import campi_pdf, compila_pdf

            gf, fasc, repo, user = context(id_fasc, request.method == "POST")
            previous = next((p for p in repo.lista(fasc.id) if p["id"] == identifier), None)
            if not previous or not previous.get("modulo_ufficiale_documento"):
                raise ValueError("Acquisisci prima il modulo dell'organismo.")
            doc = next((d for d in fasc.documenti if d.id == previous["modulo_ufficiale_documento"]), None)
            if not doc:
                raise ValueError("Modulo non presente nel fascicolo.")
            raw = decrypt_doc(gf.percorso_documento(fasc.id, doc.id).read_bytes())
            if request.method == "GET":
                import fitz
                with fitz.open(stream=raw, filetype="pdf") as pdf:
                    pages = [{"numero": p.number + 1, "larghezza": p.rect.width, "altezza": p.rect.height} for p in pdf]
                return jsonify(ok=True, campi=campi_pdf(raw), pagine=pages, documento=doc.id, versione=previous["versione"])
            body = request.get_json(silent=True) or {}
            if previous["versione"] != body.get("versione"):
                raise ValueError("Il modulo è cambiato: ricarica i campi prima di salvare.")
            filled = compila_pdf(raw, body.get("valori"))
            compiled = salva_documento_fascicolo(gf, fasc.id, f"Modulo_mediazione_compilato_{identifier}_v{previous['versione']}.pdf", filled,
                                                 TipoDocumento.ATTO_GIUDIZIARIO, tags=["mediazione", "modulo_compilato"],
                                                 caricato_da=str(user.id), preserva_contenuto_originale=True)
            payload = normalizza(previous, {d.id for d in fasc.documenti})
            collega_organismo(payload, previous, app.config)
            payload["modulo_compilato_documento"] = compiled.id
            for entry in payload["moduli_organismo"]:
                if entry["documento"] == doc.id:
                    entry.setdefault("copie_compilate", []).append(compiled.id)
            repo.salva(fasc.id, identifier, previous["versione"], payload, str(user.id))
            return jsonify(result(repo, fasc, user))
        except Exception as exc:
            return error(exc)
