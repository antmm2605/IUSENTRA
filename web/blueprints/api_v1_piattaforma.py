"""API React del pannello di piattaforma (superamministratore).

Montato sotto `/api/v1/ui/piattaforma`; le pagine e le loro sezioni stanno in
`web/services/react_piattaforma_bridge.py`. Solo il superamministratore della
piattaforma, come le viste storiche `/admin/*`.
"""

from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify

from web.blueprints.api_v1_react import _richiedi_auth
from web.services import react_piattaforma_bridge as bridge
from web.services.security_redaction import redacted_json_response

api_v1_piattaforma = Blueprint("api_v1_piattaforma", __name__)


def _superadmin() -> bool:
    return bool(getattr(g.get("utente_corrente"), "is_superadmin", False))


@api_v1_piattaforma.get("/<pagina>")
@_richiedi_auth
def pagina(pagina: str):
    if not _superadmin():
        return jsonify(ok=False, message="Pannello riservato al superamministratore della piattaforma."), 403
    try:
        risultato, stato = bridge.pagina(pagina)
        risultato["user"] = str(getattr(g.get("utente_corrente"), "username", "") or "")
        risposta = redacted_json_response(risultato)
        risposta.status_code = stato
        return risposta
    except Exception:
        current_app.logger.exception("Errore pagina del pannello di piattaforma %s", pagina)
        return jsonify(ok=False, message="Pagina non disponibile: riprova fra poco."), 500
