"""Modelli personali dell'editor nel repository SQL nativo dei template."""
from __future__ import annotations

from uuid import UUID
from flask import g, jsonify, request
from pct.editor_linked_fields import template_linked_html


def register_editor_personal_template_routes(app, *, audit, get_repository=None, resolve_context=None):
    def authorized(write=False):
        user = g.get('utente_corrente')
        return user and user.ha_permesso('fascicoli.scrivi' if write else 'fascicoli.leggi')

    def repository():
        if getattr(g, 'tenant_context_missing', False):
            raise RuntimeError('Contesto studio mancante')
        if get_repository:
            return get_repository()
        from pct.template_atti_repository import GestioneTemplateRepository, derive_template_repository_db_path
        from pct.postgres_runtime_support import database_config_to_dsn, resolve_runtime_postgres_dsn
        anchor = (getattr(g, 'data_paths', {}) or {}).get('TEMPLATE_ATTI_DB')
        if not anchor:
            raise RuntimeError('Percorso dei modelli dello studio mancante')
        tenant = getattr(g, 'tenant', None)
        dsn = database_config_to_dsn(getattr(tenant, 'database', None)) if tenant is not None else resolve_runtime_postgres_dsn()
        return GestioneTemplateRepository(derive_template_repository_db_path(str(anchor)), postgres_dsn=dsn)

    @app.get('/api/editor/modelli-personali')
    def editor_personal_templates():
        if not authorized():
            return jsonify(ok=False, errore='Non sei autorizzato a consultare i modelli.'), 403
        try:
            items = repository().list_templates()
            return jsonify(ok=True, modelli=[{'id': item['template_id'], 'titolo': item['titolo']} for item in items if item['collezione'] == 'Editor personale'])
        except Exception:
            app.logger.exception('Catalogo modelli editor non disponibile')
            return jsonify(ok=False, errore='Modelli non caricati. Riprova.'), 503

    @app.get('/api/editor/modelli-personali/<id_template>')
    def editor_personal_template(id_template):
        if not authorized():
            return jsonify(ok=False, errore='Non sei autorizzato a consultare i modelli.'), 403
        try:
            item = repository().get_template(id_template)
            if not item or item['collezione'] != 'Editor personale':
                return jsonify(ok=False, errore='Modello personale non trovato.'), 404
            return jsonify(ok=True, id=id_template, titolo=item['titolo'], html=item['corpo'])
        except Exception:
            app.logger.exception('Modello editor non disponibile')
            return jsonify(ok=False, errore='Modello non caricato. Il documento è preservato.'), 503

    @app.post('/api/editor/modelli-personali')
    def editor_save_personal_template():
        if not authorized(write=True):
            return jsonify(ok=False, errore='Non sei autorizzato a creare modelli.'), 403
        payload = request.get_json(silent=True) or {}
        try:
            if not isinstance(payload, dict):
                raise ValueError('Richiesta del modello non valida.')
            title = str(payload.get('titolo') or '').strip()
            html = str(payload.get('html') or '')
            command = str(UUID(str(payload.get('command_id') or '')))
            if not title or len(title) > 100 or any(ord(char) < 32 for char in title) or not html.strip() or len(html.encode('utf-8')) > 2_000_000:
                raise ValueError('Indica il titolo e un documento entro i limiti consentiti.')
            template, _ = template_linked_html(html)
        except ValueError as error:
            return jsonify(ok=False, errore=str(error)), 400
        try:
            identifier = repository().create_editor_template({'id': command, 'titolo': title, 'categoria': 'Altro', 'corpo': template, 'collezione': 'Editor personale', 'builtin': False})
            audit('editor.modello_personale.crea', 'template_atti', identifier, dettagli='Modello editor con campi riutilizzabili; valori collegati precedenti rimossi.')
            return jsonify(ok=True, id=identifier, titolo=title), 201
        except ValueError as error:
            return jsonify(ok=False, errore=str(error)), 409
        except Exception:
            app.logger.exception('Salvataggio modello editor non confermato')
            return jsonify(ok=False, errore='Salvataggio non confermato: riprova la stessa richiesta.'), 503

    @app.get('/api/editor/<id_fasc>/modelli-personali/<id_template>/compila')
    def editor_fill_personal_template(id_fasc, id_template):
        if not resolve_context:
            return jsonify(ok=False, errore='Collegamento al fascicolo non disponibile.'), 503
        response = app.make_response(resolve_context(id_fasc))
        if response.status_code != 200:
            return response
        context = response.get_json()
        try:
            item = repository().get_template(id_template)
            if not item or item['collezione'] != 'Editor personale':
                return jsonify(ok=False, errore='Modello personale non trovato.'), 404
            html, missing = template_linked_html(item['corpo'], context=context['fields'], matter_id=context['matterId'], client_id=context['clientId'])
            return jsonify(ok=True, html=html, mancanti=missing, titolo=item['titolo'], matterId=id_fasc)
        except Exception:
            app.logger.exception('Compilazione modello editor non riuscita')
            return jsonify(ok=False, errore='Compilazione non riuscita. Il documento è preservato.'), 503
