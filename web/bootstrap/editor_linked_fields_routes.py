"""Dati collegati dell'editor, letti dai repository SQL del tenant corrente."""
from __future__ import annotations

import hashlib
import json

from flask import g, jsonify, request
from pct.editor_linked_fields import linked_fields_catalog


def register_editor_linked_fields_routes(app, *, get_fascicoli, get_clienti=None, get_studio_context=None, get_process_dates=None):
    @app.post("/api/editor/<id_fasc>/recupera-campi")
    def editor_recover_fields(id_fasc):
        user = g.get("utente_corrente")
        if not user or not user.ha_permesso("fascicoli.leggi") or not user.ha_permesso("clienti.leggi"):
            return jsonify(ok=False, errore="Non sei autorizzato a recuperare i dati del fascicolo."), 403
        try:
            if getattr(g, "tenant_context_missing", False):
                raise RuntimeError("Contesto studio mancante")
            repository = get_fascicoli()
            if repository._studio_db is None:
                raise RuntimeError("Archivio SQL non disponibile")
            if repository.get(id_fasc) is None:
                return jsonify(ok=False, errore="Fascicolo non trovato."), 404
            from web.services.registro_letture_runtime import registro_corrente, tenant_corrente
            registry, tenant = registro_corrente(sola_lettura=True), tenant_corrente()
            payload = request.get_json(silent=True) if request.is_json else {}
            if not isinstance(payload, dict) or set(payload) - {'generation'}:
                return jsonify(ok=False, errore="Richiesta di recupero non valida."), 400
            if 'generation' not in payload:
                state = registry.esito_evento(tenant, id_fasc)
                if state['stato'] == 'failed':
                    return jsonify(ok=False, errore="La lettura si è fermata. Aggiorna la pagina per riprenderla; il documento è conservato."), 409
                return jsonify(ok=True, stato=state['stato'], generation=state['generation']), 200
            generation = payload['generation']
            if type(generation) is not int or generation < 0:
                return jsonify(ok=False, errore="Generazione del recupero non valida."), 400
            if generation > registry.esito_evento(tenant, id_fasc)['generation']:
                return jsonify(ok=False, errore="Ricarica i dati prima di riprendere la lettura; il documento è conservato."), 409
            state = registro_corrente().richiedi_recupero(tenant, id_fasc, generation=generation)
            if state['generation'] < generation:
                return jsonify(ok=False, errore="Ricarica i dati prima di riprendere la lettura; il documento è conservato."), 409
            return jsonify(ok=True, stato=state['stato'], generation=state['generation']), 202
        except Exception:
            app.logger.exception("Recupero campi del modello non avviato")
            return jsonify(ok=False, errore="Recupero non avviato. I dati e il documento sono preservati."), 503

    @app.get("/api/editor/<id_fasc>/campi-collegati")
    def editor_linked_fields(id_fasc):
        user = g.get("utente_corrente")
        if not user or not user.ha_permesso("fascicoli.leggi") or not user.ha_permesso("clienti.leggi"):
            return jsonify(ok=False, errore="Non sei autorizzato a consultare i dati del cliente e del fascicolo."), 403
        try:
            if getattr(g, "tenant_context_missing", False):
                raise RuntimeError("Contesto studio mancante")
            repository = get_fascicoli()
            if repository._studio_db is None:
                raise RuntimeError("Archivio SQL non disponibile")
            matter = repository.get(id_fasc)
            if matter is None:
                return jsonify(ok=False, errore="Fascicolo non trovato."), 404
            if get_clienti is None:
                from web.helpers import get_clienti as client_factory
            else:
                client_factory = get_clienti
            clients = client_factory()
            if clients._studio_db is None:
                raise RuntimeError("Anagrafica SQL non disponibile")
            client = clients.get(matter.id_cliente) if matter.id_cliente else None
            if matter.id_cliente and client is None:
                return jsonify(ok=False, errore="Il cliente collegato non è disponibile nell’anagrafica dello studio."), 409
            if get_studio_context is not None:
                studio_context = get_studio_context()
            else:
                from web.services.editor_studio_context import studio_context_for_editor
                studio_context = studio_context_for_editor()
            if get_process_dates is not None:
                dates = get_process_dates(matter)
                recovery_state = "idle"
                recovery_error = ""
                recovery_generation = 0
            else:
                from pct.editor_linked_fields import date_modello_da_fatti
                from web.services.registro_letture_runtime import registro_corrente, tenant_corrente
                registry = registro_corrente(sola_lettura=True)
                tenant = tenant_corrente()
                recovery = registry.esito_evento(tenant, matter.id)
                recovery_state, recovery_error = recovery["stato"], recovery["last_error"]
                recovery_generation = int(recovery["generation"])
                dates = date_modello_da_fatti(
                    registry.fatti(tenant, matter.id, categoria="metadato_fascicolo"),
                    fascicolo_id=matter.id, oggetti=registry.oggetti(tenant, matter.id),
                )
            fields = linked_fields_catalog(cliente=client, fascicolo=matter, date_processuali=dates, **studio_context)
            revision = hashlib.sha256(json.dumps([matter.id, matter.id_cliente, [(field["id"], field["value"]) for field in fields]], ensure_ascii=False).encode()).hexdigest()
            return jsonify(ok=True, matterId=matter.id, clientId=matter.id_cliente,
                           matterLabel=" · ".join(part for part in [matter.numero, matter.titolo] if part),
                           clientLabel=client.nome_completo if client else "",
                           notice="" if client else "Nessun cliente è collegato al fascicolo: sono disponibili soltanto i dati della pratica.",
                           revision=revision, fields=fields, recoveryState=recovery_state, recoveryError=recovery_error, recoveryGeneration=recovery_generation)
        except Exception:
            app.logger.exception("Dati collegati dell’editor non disponibili")
            return jsonify(ok=False, errore="Dati non caricati. Riprova; il documento è preservato."), 503
    return editor_linked_fields
