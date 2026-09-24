"""Routes for the PST encryption certificate used by electronic filing."""

from __future__ import annotations

from base64 import b64decode
from binascii import Error as Base64Error
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from flask import Flask, g, jsonify, request

from pct.pst_cifratura import (
    PSTCifraturaError,
    certificato_cifratura_in_cache,
    salva_certificato_cifratura_ufficio,
)


def register_deposito_certificate_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], object],
    audit: Callable[..., Any],
) -> None:
    """Register the read/write endpoint for the cached PST certificate."""

    @app.route("/api/v1/ui/fascicoli/<id_fasc>/deposito/certificato-cifratura", methods=["GET", "POST"])
    def api_deposito_certificato_cifratura(id_fasc):
        """Controlla o salva il .cer PST usato per cifrare Atto.msg in Atto.enc."""

        try:
            fascicolo = get_fascicoli().get(id_fasc)
            if not fascicolo:
                return jsonify({"ok": False, "errore": "Fascicolo non trovato."}), 404
            if request.method == "GET":
                codice = str(request.args.get("codice_ufficio") or "").strip()
                if not codice:
                    return jsonify({"ok": False, "errore": "Codice ufficio mancante."}), 400
                info = certificato_cifratura_in_cache(codice)
                return jsonify(
                    {
                        "ok": True,
                        "codice_ufficio": codice,
                        "cached": bool(info),
                        "certificato": asdict(info) if info else None,
                    }
                )
            payload_json = request.get_json(silent=True) or {}
            codice = str(payload_json.get("codice_ufficio") or "").strip()
            certificato_b64 = str(payload_json.get("certificato_b64") or "").strip()
            source_url = str(payload_json.get("source_url") or "").strip()
            if not codice:
                return jsonify({"ok": False, "errore": "Codice ufficio mancante."}), 400
            if not certificato_b64:
                return jsonify({"ok": False, "errore": "Certificato PST mancante."}), 400
            try:
                payload = b64decode(certificato_b64, validate=True)
            except (Base64Error, ValueError) as exc:
                raise PSTCifraturaError("Certificato PST non codificato correttamente.") from exc
            info = salva_certificato_cifratura_ufficio(codice, payload, source_url=source_url)
            utente = getattr(g, "utente_corrente", None)
            audit(
                "fascicoli.deposito.certificato_cifratura",
                "fascicolo",
                id_fasc,
                utente=getattr(utente, "username", None),
                dettagli=f"Certificato PST {codice} salvato ({info.sha256[:12]})",
            )
            return jsonify(
                {
                    "ok": True,
                    "codice_ufficio": codice,
                    "cached": True,
                    "certificato": asdict(info),
                }
            )
        except PSTCifraturaError as exc:
            app.logger.warning("Certificato PST deposito non accettato %s: %s", id_fasc, exc)
            return jsonify(
                {
                    "ok": False,
                    "errore": "Certificato PST non valido o non compatibile con l'ufficio indicato.",
                }
            ), 400
        except Exception as exc:
            app.logger.exception("Certificato PST deposito non salvato %s: %s", id_fasc, exc)
            return jsonify(
                {
                    "ok": False,
                    "errore": "Certificato PST non salvato. Verifica Local Signer e riprova.",
                }
            ), 500
