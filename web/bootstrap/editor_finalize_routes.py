"""PDF finale nel fascicolo e dati del timbro nativo; originali preservati."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from uuid import UUID
from flask import g, jsonify, request
from pct.prima_nota_transition import prima_nota_source_lock
from pct.editor_stamp import editor_stamp_payload
from web.services.document_edit_policy import motivo_blocco_editor
from web.services.document_word_fonts import SourceFontCoverageError


def register_editor_finalize_routes(app, *, get_fascicoli, audit, encrypt_doc, get_timbro):
    def allowed(write=False):
        user = g.get('utente_corrente')
        return user and user.ha_permesso('fascicoli.leggi') and (not write or user.ha_permesso('fascicoli.scrivi'))

    @app.get('/api/editor/timbro')
    def editor_stamp():
        if not allowed():
            return jsonify(ok=False, errore='Operazione non autorizzata.'), 403
        try:
            if getattr(g, 'tenant_context_missing', False):
                raise RuntimeError('Contesto studio mancante')
            payload = editor_stamp_payload(get_timbro())
            return jsonify(payload), 200 if payload["ok"] else 409
        except SourceFontCoverageError as error:
            return jsonify(ok=False, errore=str(error)), 422
        except Exception:
            app.logger.exception('Timbro editor non caricato')
            return jsonify(ok=False, errore='Timbro non caricato. Riprova.'), 503

    @app.post('/api/editor/<id_fasc>/<id_doc>/pdf-fascicolo')
    def editor_save_final_pdf(id_fasc, id_doc):
        if not allowed(write=True):
            return jsonify(ok=False, errore='Operazione non autorizzata.'), 403
        body = request.get_json(silent=True) or {}
        try:
            if not isinstance(body, dict):
                raise ValueError('Richiesta PDF non valida.')
            command = str(UUID(str(body.get('command_id') or '')))
            html = body.get('html')
            if not isinstance(html, str) or not html.strip() or len(html.encode('utf-8')) > 2_000_000:
                raise ValueError('Contenuto del documento non valido.')
        except ValueError as error:
            return jsonify(ok=False, errore=str(error)), 400
        try:
            if getattr(g, 'tenant_context_missing', False):
                raise RuntimeError('Contesto studio mancante')
            anchor = (getattr(g, 'data_paths', {}) or {}).get('FASCICOLI_DB')
            if not anchor:
                raise RuntimeError('Percorso dello studio mancante')
            marker = 'editor-pdf:' + command
            fingerprint = 'editor-contenuto:' + hashlib.sha256((id_fasc + '\0' + id_doc + '\0' + html + '\0' + g.utente_corrente.username).encode()).hexdigest()
            with prima_nota_source_lock(str(anchor) + '.editor-final'):
                repo = get_fascicoli()
                if repo._studio_db is None:
                    raise RuntimeError('Archivio SQL non disponibile')
                matter = repo.get(id_fasc)
                source = next((doc for doc in matter.documenti if doc.id == id_doc), None) if matter else None
                if source is None:
                    return jsonify(ok=False, errore='Documento del fascicolo non trovato.'), 404
                reason = motivo_blocco_editor(source)
                if reason or Path(source.nome).suffix.lower() not in {'.docx', '.rtf', '.html', '.htm', '.txt', '.md'}:
                    return jsonify(ok=False, errore=reason or 'La fonte non è modificabile nell’editor.'), 409
                previous = [doc for doc in matter.documenti if marker in (doc.tags or [])]
                if previous:
                    if len(previous) != 1 or fingerprint not in previous[0].tags:
                        return jsonify(ok=False, errore='Richiesta già utilizzata per un PDF diverso.'), 409
                    document = previous[0]
                else:
                    from pct.editor_export import esporta_documento_editor
                    from pct.editor_linked_fields import editor_linked_fields_missing
                    from pct.note_127_ter.bozza import campi_note_mancanti
                    from pct.fascicoli import TipoDocumento
                    from lxml.html import fragment_fromstring
                    from web.services.editor_word_source import editor_word_source
                    from pct.document_crypto import decrypt_doc
                    titolo = Path(source.nome).stem
                    contenuto = fragment_fromstring(html, create_parent=True)
                    mancanti = list(dict.fromkeys(
                        editor_linked_fields_missing(contenuto, matter_id=id_fasc)
                        + campi_note_mancanti(contenuto.text_content())
                    ))
                    if mancanti:
                        return jsonify(ok=False, errore='Completa i campi della bozza prima di salvare il PDF per il deposito: '
                                       + ', '.join(mancanti) + '.'), 409
                    if source.fonte_documento == 'BOZZA_NOTE_127_TER':
                        titolo = re.sub(r'(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)', r'\3-\2-\1', titolo)
                    raw = esporta_documento_editor(html, formato='pdf', titolo=titolo,
                        fonte_word=editor_word_source(repo, id_fasc, source, decrypt_doc, html=html))
                    if not raw.startswith(b'%PDF-'):
                        raise RuntimeError('PDF non prodotto')
                    filename = titolo + ' - finale ' + command[:8] + '.pdf'
                    document = repo.aggiungi_documento(id_fasc, filename, TipoDocumento.ALLEGATO, encrypt_doc(raw), caricato_da=g.utente_corrente.username,
                        fonte_documento='REDAZIONE_STUDIO', note='PDF finale dall’editor; fonte modificabile ' + id_doc,
                        tags=['pdf-finale-editor', 'editor-fonte:' + id_doc, marker, fingerprint], nome_originale=filename,
                        hash_contenuto_sha256=hashlib.sha256(raw).hexdigest(), salvataggio_mirato=True)
                audit('fascicoli.documento.editor_pdf_finale', 'fascicolo', id_fasc, dettagli=f'fonte {id_doc}; PDF {document.id}; comando {command}; ripetizione {bool(previous)}')
            return jsonify(ok=True, document_id=document.id, nome=document.nome, url=f'/fascicoli/{id_fasc}/documenti/{document.id}/visualizza'), 201
        except Exception:
            app.logger.exception('Salvataggio PDF finale non confermato')
            return jsonify(ok=False, errore='PDF non confermato: riprova la stessa richiesta. Il documento originale è preservato.'), 503
