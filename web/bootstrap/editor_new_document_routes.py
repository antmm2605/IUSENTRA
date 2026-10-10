"""Create a studio DOCX through the existing fascicolo document repository."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from uuid import UUID

from pct.prima_nota_transition import prima_nota_source_lock
from flask import g, jsonify, request


def register_editor_new_document_routes(app, *, get_fascicoli, audit, encrypt_doc):
    def allowed(permission):
        user = g.get("utente_corrente")
        return bool(user and user.ha_permesso(permission))

    @app.get("/api/editor/nuovo/fascicoli")
    def editor_new_document_matters():
        if not allowed("fascicoli.leggi"):
            return jsonify(ok=False, errore="Operazione non autorizzata."), 403
        try:
            database = get_fascicoli()._studio_db
            if database is None or getattr(g, "tenant_context_missing", False):
                raise RuntimeError("Archivio SQL dello studio non disponibile")
            rows = database.fetchall_readonly("SELECT id, numero, titolo, nome_cliente, numero_rg, anno_rg FROM fascicoli WHERE stato <> 'ARCHIVIATO' ORDER BY numero DESC")
            return jsonify(ok=True, fascicoli=[{
                "value": row["id"], "client": row["nome_cliente"] or "", "label": " · ".join(part for part in [row["numero"], row["nome_cliente"], row["titolo"], ("R.G. " + str(row["numero_rg"]) + ("/" + str(row["anno_rg"]) if row["anno_rg"] and "/" not in str(row["numero_rg"]) else "")) if row["numero_rg"] else ""] if part),
            } for row in rows])
        except Exception:
            app.logger.exception("Catalogo fascicoli nuovo documento non disponibile")
            return jsonify(ok=False, errore="Fascicoli non caricati. Riprova."), 503

    @app.post("/api/editor/<id_fasc>/nuovo")
    def editor_new_document_create(id_fasc):
        if not allowed("fascicoli.scrivi") or not allowed("fascicoli.leggi"):
            return jsonify(ok=False, errore="Operazione non autorizzata."), 403
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) != {"titolo", "command_id", "html"}:
            return jsonify(ok=False, errore="Richiesta non valida."), 400
        title = body.get("titolo")
        try:
            command = str(UUID(body.get("command_id")))
        except (ValueError, TypeError, AttributeError):
            return jsonify(ok=False, errore="Identificativo della richiesta non valido."), 400
        if not isinstance(title, str) or not title.strip() or len(title) > 100 or re.search(r'[\\/\x00-\x1f]', title):
            return jsonify(ok=False, errore="Inserisci un titolo valido, fino a 100 caratteri."), 400
        html = body.get("html")
        if not isinstance(html, str) or len(html) > 2_000_000:
            return jsonify(ok=False, errore="Contenuto del documento non valido."), 400
        title = title.strip()
        try:
            if getattr(g, "tenant_context_missing", False):
                raise RuntimeError("Contesto studio mancante")
            anchor = Path((getattr(g, "data_paths", {}) or {}).get("FASCICOLI_DB") or app.config["FASCICOLI_DB"])
            marker = "editor-nuovo:" + command
            fingerprint = "editor-richiesta:" + hashlib.sha256((id_fasc + "\0" + title + "\0" + html + "\0" + g.utente_corrente.username).encode()).hexdigest()
            with prima_nota_source_lock(str(anchor) + ".editor-new"):
                repository = get_fascicoli()
                if repository._studio_db is None:
                    raise RuntimeError("Archivio SQL dello studio non disponibile")
                matter = repository.get(id_fasc)
                if matter is None:
                    return jsonify(ok=False, errore="Fascicolo non trovato."), 404
                previous = [doc for doc in matter.documenti if marker in (doc.tags or [])]
                if previous:
                    if len(previous) != 1 or fingerprint not in previous[0].tags:
                        return jsonify(ok=False, errore="Richiesta già utilizzata per un documento diverso."), 409
                    document = previous[0]
                else:
                    from pct.editor import html_to_docx
                    from pct.fascicoli import TipoDocumento
                    raw = html_to_docx(html, titolo=title)
                    filename = title.removesuffix(".docx") + " - " + command[:8] + ".docx"
                    document = repository.aggiungi_documento(
                        id_fasc, filename, TipoDocumento.ALLEGATO, encrypt_doc(raw),
                        caricato_da=g.utente_corrente.username, fonte_documento="REDAZIONE_STUDIO",
                        note="Documento creato nell’editor professionale dello studio.",
                        tags=["bozza-editor", marker, fingerprint], nome_originale=filename,
                        hash_contenuto_sha256=hashlib.sha256(raw).hexdigest(), salvataggio_mirato=True,
                    )
                audit("fascicoli.documento.editor_nuovo", "fascicolo", id_fasc, dettagli=f"doc {document.id}; comando {command}; ripetizione {bool(previous)}")
            return jsonify(ok=True, document_id=document.id, url=f"/fascicoli/{id_fasc}/documenti/{document.id}/editor"), 201
        except Exception:
            app.logger.exception("Creazione documento editor non confermata")
            return jsonify(ok=False, errore="Creazione non confermata. Riprova la stessa richiesta."), 503
