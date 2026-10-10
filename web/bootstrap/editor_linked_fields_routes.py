"""Dati collegati dell'editor, letti dai repository SQL del tenant corrente."""
from __future__ import annotations

import hashlib
import json

from flask import g, jsonify
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
            from web.services.archivio_letture_runtime import lettura_dopo_evento
            if not lettura_dopo_evento(id_fasc):
                raise RuntimeError("Recupero non accodato")
            return jsonify(ok=True, stato="pending"), 202
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
                from web.blueprints.template_atti import _get_studio_timbro, _studio_config_for_prefill
                studio_context = {"config": _studio_config_for_prefill(), "studio_timbro": _get_studio_timbro()}
            if get_process_dates is not None:
                dates = get_process_dates(matter)
                recovery_state = "idle"
            else:
                from pct.editor_linked_fields import date_modello_da_fatti
                from web.services.registro_letture_runtime import registro_corrente, tenant_corrente
                registry = registro_corrente()
                tenant = tenant_corrente()
                recovery_state = registry.stato_evento(tenant, matter.id)
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
                           revision=revision, fields=fields, recoveryState=recovery_state)
        except Exception:
            app.logger.exception("Dati collegati dell’editor non disponibili")
            return jsonify(ok=False, errore="Dati non caricati. Riprova; il documento è preservato."), 503
    return editor_linked_fields
