"""Document-scoped local language checks and editor downloads.

Registered by the fascicolo editor bootstrap with the same repositories and
permission context; the document update and PDF conversion routes remain there.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from typing import Any

from flask import Flask, jsonify, request, send_file
from web.services.document_word_fonts import SourceFontCoverageError


def register_editor_language_export_routes(
    app: Flask, *, get_fascicoli: Callable[[], Any], audit: Callable[..., None]
) -> None:
    """Register the existing language and download endpoints without changing contracts."""

    @app.route("/api/editor/<id_fasc>/<id_doc>/lingua", methods=["POST"])
    def api_editor_lingua(id_fasc, id_doc):
        from pct.editor_language import controlla_ortografia, suggerisci_frase
        from pct.editor_ai.validators import assert_user_can_write, EditorAIPermissionDenied, user_id_from_context
        from web.services.editor_ai_runtime import editor_ai_user_context

        try:
            utente = editor_ai_user_context()
            assert_user_can_write(utente)
            fascicolo = get_fascicoli().get(id_fasc)
            documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None) if fascicolo else None
            if documento is None:
                return jsonify({"ok": False, "errore": "Documento non trovato."}), 404
            body = request.get_json(silent=True) or {}
            testo = body.get("testo", "")
            azione = body.get("azione", "ortografia")
            if azione == "ortografia":
                return jsonify({"ok": True, "rilievi": controlla_ortografia(testo), "locale": True})
            if azione == "documento":
                from pct.editor_grammar import controlla_documento
                from pct.editor_linked_fields import linked_fields_catalog
                from web.helpers import get_clienti
                from web.blueprints.template_atti import _get_studio_timbro, _studio_config_for_prefill
                import re

                cliente = get_clienti().get(fascicolo.id_cliente) if fascicolo.id_cliente else None
                campi = linked_fields_catalog(
                    cliente=cliente, fascicolo=fascicolo,
                    config=_studio_config_for_prefill(), studio_timbro=_get_studio_timbro(),
                )
                nomi = {'cliente.nome', 'cliente.cognome', 'cliente.nome_completo',
                        'cliente.luogo_nascita', 'fascicolo.giudice', 'fascicolo.tribunale',
                        'fascicolo.avvocato_controparte', 'studio.citta',
                        'studio_timbro.nome_professionista', 'studio_timbro.professionista_nome'}
                termini = {parola for campo in campi if campo['available'] and (
                    campo['id'] in nomi or campo['id'].startswith('cliente.indirizzo_')
                    and campo['id'].endswith(('.comune', '.via'))
                ) for parola in re.findall(r"[^\W\d_]+", campo['value'])}
                rilievi = controlla_documento(testo, termini_contesto=termini)
                audit("fascicoli.documento.controllo_linguistico", "fascicolo", id_fasc, dettagli=f"doc {id_doc}; solo locale; {len(rilievi)} rilievi; testo invariato")
                return jsonify({"ok": True, "rilievi": rilievi, "locale": True})
            if azione != "frase":
                raise ValueError("Operazione linguistica non consentita.")
            proposta = suggerisci_frase(testo, user_id_from_context(utente))
            audit("fascicoli.documento.suggerimento_linguistico", "fascicolo", id_fasc, dettagli=f"doc {id_doc}; solo locale; proposta non applicata")
            return jsonify({"ok": True, "proposta": proposta, "locale": True})
        except EditorAIPermissionDenied:
            return jsonify({"ok": False, "errore": "Operazione non autorizzata."}), 403
        except ValueError as exc:
            return jsonify({"ok": False, "errore": str(exc)}), 400
        except Exception:
            return jsonify({"ok": False, "errore": "Supporto linguistico locale non disponibile. Riprova tra poco."}), 503

    @app.route("/api/editor/<id_fasc>/<id_doc>/rtf", methods=["POST"])
    def api_editor_rtf(id_fasc, id_doc):
        from pct.editor_export import esporta_documento_editor
        from pct.editor_ai.validators import assert_user_can_read, EditorAIPermissionDenied
        from web.services.editor_ai_runtime import editor_ai_user_context

        try:
            assert_user_can_read(editor_ai_user_context())
            repository = get_fascicoli()
            fascicolo = repository.get(id_fasc)
            documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None) if fascicolo else None
            if documento is None:
                return jsonify({"errore": "Documento non trovato."}), 404
            body = request.get_json(silent=True) or {}
            titolo = documento.nome.rsplit(".", 1)[0]
            from pct.document_crypto import decrypt_doc
            from web.services.editor_word_source import editor_word_source
            contenuto = esporta_documento_editor(body.get("html", "<p></p>"), formato="rtf", titolo=titolo,
                fonte_word=editor_word_source(repository, id_fasc, documento, decrypt_doc))
            audit("fascicoli.documento.editor_rtf", "fascicolo", id_fasc, dettagli=f"doc {id_doc}")
            return send_file(io.BytesIO(contenuto), mimetype="application/rtf", as_attachment=True, download_name=titolo + ".rtf")
        except EditorAIPermissionDenied:
            return jsonify({"errore": "Operazione non autorizzata."}), 403
        except SourceFontCoverageError as error:
            return jsonify({"errore": str(error)}), 422
        except Exception:
            return jsonify({"errore": "Generazione RTF non completata."}), 503

    @app.route("/api/editor/<id_fasc>/<id_doc>/docx", methods=["POST"])
    def api_editor_docx(id_fasc, id_doc):
        from pct.editor_export import esporta_documento_editor

        try:
            body = request.get_json(force=True) or {}
            html = body.get("html", "<p></p>")
            repository = get_fascicoli()
            fascicolo = repository.get(id_fasc)
            documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None)
            titolo = documento.nome.rsplit(".", 1)[0] if documento else "documento"
            from pct.document_crypto import decrypt_doc
            from web.services.editor_word_source import editor_word_source
            docx_bytes = esporta_documento_editor(html, formato='docx', titolo=titolo,
                fonte_word=editor_word_source(repository, id_fasc, documento, decrypt_doc))
            audit("fascicoli.documento.editor_docx", "fascicolo", id_fasc, dettagli=f"doc {id_doc}")
            return send_file(
                io.BytesIO(docx_bytes),
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                as_attachment=True,
                download_name=titolo + ".docx",
            )
        except ImportError:
            return jsonify({"errore": "Generazione DOCX non disponibile."}), 503
        except SourceFontCoverageError as error:
            return jsonify({"errore": str(error)}), 422
        except Exception as exc:
            app.logger.exception("Errore api_editor_docx: %s", exc)
            return "Generazione DOCX non completata.", 500
