"""API React del pannello di piattaforma (superamministratore).

Montato sotto `/api/v1/ui/piattaforma`; le pagine, le loro sezioni e le loro
azioni stanno in `web/services/react_piattaforma_bridge.py`. Solo il superamministratore della
piattaforma, come le viste storiche `/admin/*`.
"""

from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request

from web.blueprints.api_v1_react import _richiedi_auth
from web.services import react_piattaforma_bridge as bridge
from web.services.security_redaction import redacted_json_response

api_v1_piattaforma = Blueprint("api_v1_piattaforma", __name__)


def _superadmin() -> bool:
    return bool(getattr(g.get("utente_corrente"), "is_superadmin", False))


# Pagine che, come la console storica (`support_operator_identity_or_403`), restano
# aperte al superamministratore anche mentre è entrato in uno studio.
PAGINE_OPERATORE_ASSISTENZA = {"supporto-remoto"}


def _autorizzato(pagina: str) -> bool:
    if _superadmin():
        return True
    if pagina not in PAGINE_OPERATORE_ASSISTENZA:
        return False
    from werkzeug.exceptions import HTTPException

    from web.services.support_runtime import support_operator_identity_or_403

    try:
        support_operator_identity_or_403()
    except HTTPException:
        return False
    return True


@api_v1_piattaforma.get("/<pagina>")
@_richiedi_auth
def pagina(pagina: str):
    if not _autorizzato(pagina):
        return jsonify(ok=False, message="Pannello riservato al superamministratore della piattaforma."), 403
    try:
        risultato, stato = bridge.pagina(pagina)
        risultato["user"] = str(getattr(g.get("utente_corrente"), "username", "") or "")
        risposta = redacted_json_response(risultato, consenti_percorsi=True)
        risposta.status_code = stato
        return risposta
    except Exception:
        current_app.logger.exception("Errore pagina del pannello di piattaforma %s", pagina)
        return jsonify(ok=False, message="Pagina non disponibile: riprova fra poco."), 500


@api_v1_piattaforma.post("/<pagina>/azioni/<azione>")
@_richiedi_auth
def azione(pagina: str, azione: str):
    """Esegue un'azione della pagina con gli stessi servizi della vista storica."""
    if not _autorizzato(pagina):
        return jsonify(ok=False, message="Pannello riservato al superamministratore della piattaforma."), 403
    corpo = request.get_json(silent=True) or {}
    try:
        risultato, stato = bridge.esegui(pagina, azione, corpo.get("params"), corpo.get("values"))
        risposta = redacted_json_response(risultato, consenti_percorsi=True)
        risposta.status_code = stato
        return risposta
    except Exception:
        current_app.logger.exception("Errore azione %s del pannello di piattaforma %s", azione, pagina)
        return jsonify(ok=False, message="Operazione non completata: il dettaglio tecnico è nei log del server."), 500
