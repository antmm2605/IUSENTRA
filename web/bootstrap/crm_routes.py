"""Route della pipeline CRM di intake (lead → conflitti → cliente).

Base deontologica: artt. 23-24 CDF (incarico e conflitto di interessi),
L. 247/2012 art. 13 (preventivo scritto). La pagina e' la shell React /crm;
le scritture passano da queste route operative con audit.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Flask, g, jsonify, request

from web.blueprints.react_shell import render_react_shell_response


def register_crm_routes(app: Flask, core: dict[str, Any]) -> None:
    """Registra la superficie CRM leggendo gli accessor dal bundle core."""

    get_crm: Callable[[], Any] = core["get_crm"]
    get_clienti: Callable[[], Any] = core["get_clienti"]
    get_soggetti: Callable[[], Any] = core["get_soggetti"]
    audit: Callable[..., None] = core["audit"]
    def _permesso(scrittura: bool = False) -> bool:
        utente = g.get("utente_corrente")
        if not utente:
            return False
        chiave = "clienti.scrivi" if scrittura else "clienti.leggi"
        try:
            return bool(utente.ha_permesso(chiave))
        except Exception:
            return False

    @app.route("/crm")
    def crm_pipeline_page():
        return render_react_shell_response("crm")

    @app.route("/api/v1/ui/crm")
    def crm_pipeline_payload():
        from web.services.react_crm_bridge import build_react_crm_payload

        if not _permesso():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        try:
            return jsonify(build_react_crm_payload(get_crm=get_crm))
        except Exception as exc:
            app.logger.exception("Errore payload CRM: %s", exc)
            return jsonify({"ok": False, "message": "Pipeline CRM non disponibile."}), 200

    @app.route("/crm/lead/nuovo", methods=["POST"])
    def crm_lead_nuovo():
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or request.form
        try:
            lead = get_crm().nuovo(
                denominazione=str(dati.get("denominazione") or ""),
                codice_fiscale=str(dati.get("codiceFiscale") or dati.get("codice_fiscale") or ""),
                partita_iva=str(dati.get("partitaIva") or dati.get("partita_iva") or ""),
                email=str(dati.get("email") or ""),
                telefono=str(dati.get("telefono") or ""),
                fonte=str(dati.get("fonte") or "altro"),
                materia=str(dati.get("materia") or ""),
                esigenza=str(dati.get("esigenza") or ""),
                referente=getattr(g.get("utente_corrente"), "username", "") or "",
            )
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Errore creazione lead: %s", exc)
            return jsonify({"ok": False, "message": f"Creazione non riuscita: {exc}"}), 200
        audit("crm.lead_creato", "crm_lead", lead.id, dettagli=lead.denominazione)
        message = f"Contatto registrato nella pipeline: {lead.denominazione}."
        return jsonify({"ok": True, "message": message, "messaggio": message, "leadId": lead.id})

    @app.route("/crm/lead/<lead_id>/stato", methods=["POST"])
    def crm_lead_stato(lead_id: str):
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or request.form
        try:
            lead = get_crm().cambia_stato(
                lead_id,
                str(dati.get("stato") or ""),
                motivo_perso=str(dati.get("motivoPerso") or dati.get("motivo_perso") or ""),
            )
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        audit("crm.lead_stato", "crm_lead", lead_id, dettagli=lead.stato)
        message = f"Lead aggiornato: {lead.stato}."
        return jsonify({"ok": True, "message": message, "messaggio": message})

    @app.route("/crm/lead/<lead_id>/verifica-conflitti", methods=["POST"])
    def crm_lead_verifica_conflitti(lead_id: str):
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        try:
            esito = get_crm().verifica_conflitti(
                lead_id,
                get_clienti=get_clienti,
                get_soggetti=get_soggetti,
            )
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        except Exception as exc:
            app.logger.exception("Errore verifica conflitti lead %s: %s", lead_id, exc)
            return jsonify({"ok": False, "message": f"Verifica non riuscita: {exc}"}), 200
        audit(
            "crm.verifica_conflitti",
            "crm_lead",
            lead_id,
            dettagli=f"livello={esito.get('livello')} riscontri={len(esito.get('riscontri') or [])}",
        )
        etichette = {
            "nessuno": "Nessun riscontro tra clienti e controparti dello studio.",
            "da_valutare": "Riscontri da valutare (omonimie o cliente esistente): decide l'avvocato.",
            "potenziale_conflitto": "Potenziale conflitto ex art. 24 CDF: valutare l'astensione.",
        }
        message = etichette.get(str(esito.get("livello")), "Verifica completata.")
        return jsonify({"ok": True, "message": message, "messaggio": message, "esito": esito})

    @app.route("/crm/lead/<lead_id>/converti", methods=["POST"])
    def crm_lead_converti(lead_id: str):
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403

        def _crea_cliente(dati: dict[str, Any]):
            from pct.clienti import TipoCliente

            gestione = get_clienti()
            denominazione = str(dati.get("denominazione") or "").strip()
            partita_iva = str(dati.get("partita_iva") or "")
            if partita_iva:
                return gestione.nuovo(
                    TipoCliente.PERSONA_GIURIDICA,
                    ragione_sociale=denominazione,
                    codice_fiscale=str(dati.get("codice_fiscale") or ""),
                    partita_iva=partita_iva,
                    email=str(dati.get("email") or ""),
                    telefono=str(dati.get("telefono") or ""),
                    note=str(dati.get("note") or ""),
                )
            parti = denominazione.split(" ", 1)
            return gestione.nuovo(
                TipoCliente.PERSONA_FISICA,
                nome=parti[0] if len(parti) > 1 else "",
                cognome=parti[1] if len(parti) > 1 else denominazione,
                codice_fiscale=str(dati.get("codice_fiscale") or ""),
                email=str(dati.get("email") or ""),
                telefono=str(dati.get("telefono") or ""),
                note=str(dati.get("note") or ""),
            )

        try:
            lead = get_crm().converti_in_cliente(lead_id, crea_cliente=_crea_cliente)
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Errore conversione lead %s: %s", lead_id, exc)
            return jsonify({"ok": False, "message": f"Conversione non riuscita: {exc}"}), 200
        audit("crm.lead_convertito", "crm_lead", lead_id, dettagli=f"cliente={lead.cliente_id}")
        message = "Cliente creato dall'intake: prosegui con preventivo e adeguata verifica."
        return jsonify({
            "ok": True,
            "message": message,
            "messaggio": message,
            "clienteId": lead.cliente_id,
            "next": {"preventivo": "/preventivi/nuovo", "cliente": f"/clienti?focus={lead.cliente_id}"},
        })
