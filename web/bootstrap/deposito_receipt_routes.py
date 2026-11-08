"""Receipt polling routes for deposit workflows."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from flask import Flask, jsonify, request

from pct.deposito_simulazione import (
    apply_simulated_receipt,
    is_simulated_deposit,
    next_receipt_phase,
    receipt_flags,
)


def register_deposito_receipt_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], object],
    get_config_studio: Callable[[], object],
    audit: Callable[..., None],
) -> None:
    """Register IMAP receipt polling endpoints."""

    @app.route("/api/fascicoli/<id_fasc>/depositi/<id_dep>/controlla", methods=["POST"])
    def deposito_controlla_ricevute(id_fasc, id_dep):
        """Controlla via IMAP se sono arrivate nuove ricevute PEC per un deposito."""

        gestore_fascicoli = get_fascicoli()
        fascicolo = gestore_fascicoli.get(id_fasc)
        if not fascicolo:
            return jsonify({"errore": "Fascicolo non trovato"}), 200

        deposito = next((item for item in fascicolo.depositi_pct if item.id == id_dep), None)
        if not deposito:
            return jsonify({"errore": "Deposito non trovato"}), 200

        if is_simulated_deposit(deposito):
            return jsonify(
                {
                    "stato": deposito.stato,
                    "ricevuta_accettazione": bool(deposito.ricevuta_accettazione),
                    "ricevuta_consegna": bool(deposito.ricevuta_consegna),
                    "ricevuta_controlli": bool(deposito.ricevuta_controlli_automatici),
                    "ricevuta_cancelleria": bool(deposito.ricevuta_cancelleria),
                    "simulazione": True,
                    "prossima_fase": next_receipt_phase(deposito),
                    "aggiornato": False,
                    "messaggio": "Deposito di prova: nessun controllo esterno eseguito.",
                }
            )

        try:
            cfg_studio = get_config_studio().config
            pec_cfg = cfg_studio.pec if cfg_studio and hasattr(cfg_studio, "pec") else None
            if not pec_cfg or not pec_cfg.imap_host:
                return jsonify(
                    {
                        "stato": deposito.stato,
                        "ricevuta_accettazione": bool(deposito.ricevuta_accettazione),
                        "ricevuta_consegna": bool(deposito.ricevuta_consegna),
                        "info": "Casella PEC non configurata per il controllo automatico.",
                        "messaggio": "Casella PEC non configurata: verifica manuale necessaria.",
                    }
                )

            # Le quattro PEC di ritorno (accettazione, consegna, esito dei controlli automatici,
            # esito della cancelleria: D.M. 44/2011 artt. 13-14; Specifiche DGSIA 7/8/2024 art. 17)
            # entrano nel deposito solo se ne portano un identificativo (Message-ID, IdBusta,
            # RefID): pct/ricevute_deposito_pct.py. Mai PEC del giorno scelte per parola.
            from pct.polling_depositi import _cerca_ricevute_imap
            from pct.ricevute_deposito_pct import applica_ricevute

            ricevute = _cerca_ricevute_imap(
                imap_host=pec_cfg.imap_host,
                imap_port=getattr(pec_cfg, "imap_port", 993),
                indirizzo=pec_cfg.indirizzo,
                password=pec_cfg.password,
                giorni_indietro=30,
            )
            esito_ricevute = applica_ricevute(deposito, ricevute)
            aggiornato = bool(esito_ricevute["aggiornato"])

            if aggiornato:
                gestore_fascicoli._salva()
                audit(
                    "fascicoli.deposito.ricevute",
                    "fascicolo",
                    id_fasc,
                    dettagli=f"Deposito {id_dep} aggiornato a {deposito.stato}",
                )

            return jsonify(
                {
                    "stato": deposito.stato,
                    "ricevuta_accettazione": bool(deposito.ricevuta_accettazione),
                    "ricevuta_consegna": bool(deposito.ricevuta_consegna),
                    "ricevuta_controlli": bool(deposito.ricevuta_controlli_automatici),
                    "esito_controlli": deposito.esito_controlli,
                    "ricevuta_cancelleria": bool(deposito.ricevuta_cancelleria),
                    "aggiornato": aggiornato,
                    "eventi": esito_ricevute["eventi"],
                    "messaggio": (
                        "Ricevute aggiornate: " + "; ".join(esito_ricevute["eventi"]) + "."
                        if aggiornato and esito_ricevute["eventi"]
                        else "Nessuna nuova ricevuta PEC collegata a questo deposito."
                    ),
                }
            )
        except Exception as exc:
            app.logger.exception("deposito_controlla_ricevute %s/%s: %s", id_fasc, id_dep, exc)
            return jsonify({"errore": "Controllo ricevute non completato. Verifica la PEC e riprova.", "stato": deposito.stato})

    @app.route("/api/fascicoli/<id_fasc>/depositi/<id_dep>/simula-ricevuta", methods=["POST"])
    def deposito_simula_ricevuta(id_fasc, id_dep):
        """Genera una ricevuta sintetica solo per depositi creati senza invio reale."""

        gestore_fascicoli = get_fascicoli()
        fascicolo = gestore_fascicoli.get(id_fasc)
        if not fascicolo:
            return jsonify({"ok": False, "errore": "Fascicolo non trovato"}), 404

        deposito = next((item for item in fascicolo.depositi_pct if item.id == id_dep), None)
        if not deposito:
            return jsonify({"ok": False, "errore": "Deposito non trovato"}), 404
        if not is_simulated_deposit(deposito):
            return jsonify(
                {
                    "ok": False,
                    "errore": "La ricevuta di prova può essere generata solo per depositi senza invio reale.",
                }
            ), 400

        body = request.get_json(silent=True) or {}
        fase = str(request.form.get("fase") or body.get("fase") or request.args.get("fase") or "prossima")
        ref = str(getattr(fascicolo, "rg_completo", "") or getattr(fascicolo, "numero", "") or id_fasc)
        generated_at = datetime.now().isoformat(timespec="seconds")
        try:
            phase, updated, message = apply_simulated_receipt(
                deposito,
                fase=fase,
                fascicolo_ref=ref,
                generated_at=generated_at,
            )
        except ValueError as exc:
            app.logger.warning("Simulazione ricevuta non valida %s/%s: %s", id_fasc, id_dep, exc)
            return jsonify({"ok": False, "errore": "Ricevuta di prova non generata. Verifica fase e deposito."}), 400

        if updated:
            try:
                fascicolo.modificato_il = generated_at
            except Exception:
                pass
            gestore_fascicoli._salva()
            audit(
                "fascicoli.deposito.ricevuta_prova",
                "fascicolo",
                id_fasc,
                dettagli=f"Deposito {id_dep} - fase {phase} - stato {deposito.stato}",
            )

        flags = receipt_flags(deposito)
        return jsonify(
            {
                "ok": True,
                "stato": deposito.stato,
                "fase": phase,
                "aggiornato": updated,
                "simulazione": True,
                "ricevuta_accettazione": flags["accettazione"],
                "ricevuta_consegna": flags["consegna"],
                "ricevuta_controlli": flags["controlli"],
                "ricevuta_cancelleria": flags["cancelleria"],
                "prossima_fase": next_receipt_phase(deposito),
                "messaggio": message,
                "message": message,
            }
        )
