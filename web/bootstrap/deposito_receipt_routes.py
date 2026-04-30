"""Receipt polling routes for deposit workflows."""

from __future__ import annotations

from collections.abc import Callable

from flask import Flask, jsonify


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

        try:
            cfg_studio = get_config_studio().config
            pec_cfg = cfg_studio.pec if cfg_studio and hasattr(cfg_studio, "pec") else None
            if not pec_cfg or not pec_cfg.imap_host:
                return jsonify(
                    {
                        "stato": deposito.stato,
                        "ricevuta_accettazione": bool(deposito.ricevuta_accettazione),
                        "ricevuta_consegna": bool(deposito.ricevuta_consegna),
                        "info": "IMAP non configurato - verifica manuale necessaria.",
                    }
                )

            from pct.pec import ClientPEC, ConfigPEC

            config_pec = ConfigPEC(
                indirizzo=pec_cfg.indirizzo,
                password=pec_cfg.password,
                smtp_host=getattr(pec_cfg, "smtp_host", ""),
                imap_host=pec_cfg.imap_host,
                imap_port=getattr(pec_cfg, "imap_port", 993),
            )
            client_pec = ClientPEC(config_pec)
            ricevute = client_pec.attendi_ricevute(timeout=15)
            aggiornato = False

            if ricevute.get("accettazione") and not deposito.ricevuta_accettazione:
                deposito.ricevuta_accettazione = ricevute["accettazione"]
                if deposito.stato in ("INVIATO",):
                    deposito.stato = "ACCETTATO_PEC"
                aggiornato = True

            if ricevute.get("consegna") and not deposito.ricevuta_consegna:
                deposito.ricevuta_consegna = ricevute["consegna"]
                if deposito.stato not in (
                    "WARN_CONTROLLI",
                    "ERRORE_CONTROLLI",
                    "ACCETTATO_CANCELLERIA",
                    "RIFIUTATO_CANCELLERIA",
                ):
                    deposito.stato = "CONSEGNATO"
                aggiornato = True

            if ricevute.get("controlli") and not deposito.ricevuta_controlli_automatici:
                deposito.ricevuta_controlli_automatici = ricevute["controlli"]
                esito_controlli = str(ricevute.get("esito_controlli", "OK")).upper()
                deposito.esito_controlli = esito_controlli
                if esito_controlli == "ERROR":
                    deposito.stato = "ERRORE_CONTROLLI"
                elif esito_controlli == "WARN":
                    deposito.stato = "WARN_CONTROLLI"
                aggiornato = True

            if ricevute.get("cancelleria") and not deposito.ricevuta_cancelleria:
                deposito.ricevuta_cancelleria = ricevute["cancelleria"]
                deposito.stato = (
                    "ACCETTATO_CANCELLERIA"
                    if ricevute.get("cancelleria_accettato", True)
                    else "RIFIUTATO_CANCELLERIA"
                )
                aggiornato = True

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
                }
            )
        except Exception as exc:
            app.logger.exception("deposito_controlla_ricevute %s/%s: %s", id_fasc, id_dep, exc)
            return jsonify({"errore": str(exc), "stato": deposito.stato})
