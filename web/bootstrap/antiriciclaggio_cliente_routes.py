"""Rotte dell'adeguata verifica dalla scheda del cliente (D.Lgs. 231/2007).

Lettura con ``clienti.leggi``, scrittura con ``clienti.scrivi``. Logica in
``web.services.antiriciclaggio_cliente_runtime`` e nel motore ``pct.antiriciclaggio``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Flask, Response, g, jsonify, request


def register_antiriciclaggio_cliente_routes(app: Flask, core: dict[str, Any]) -> None:
    get_antiriciclaggio: Callable[[], Any] = core["get_antiriciclaggio"]
    get_clienti: Callable[[], Any] = core["get_clienti"]
    get_config_studio: Callable[[], Any] = core["get_config_studio"]
    audit: Callable[..., None] = core["audit"]

    def _puo(permesso: str) -> bool:
        utente = g.get("utente_corrente")
        try:
            return bool(utente and utente.ha_permesso(permesso))
        except Exception:
            return False

    def _operatore() -> str:
        utente = g.get("utente_corrente")
        return str(getattr(utente, "username", "") or "")

    def _cliente(cliente_id: str):
        cliente = get_clienti().get(cliente_id)
        if cliente is None:
            raise LookupError("Cliente non trovato.")
        return cliente

    def _verifica(cliente_id: str, verifica_id: str):
        verifica = get_antiriciclaggio().get(verifica_id)
        if verifica is None or verifica.cliente_id != cliente_id:
            raise LookupError("Scheda antiriciclaggio non trovata per questo cliente.")
        return verifica

    def _errore(exc: Exception):
        codice = 404 if isinstance(exc, LookupError) else 400
        return jsonify({"ok": False, "message": str(exc).strip("'")}), codice

    @app.route("/api/v1/ui/clienti/<cliente_id>/antiriciclaggio")
    def cliente_aml_stato(cliente_id: str):
        from pct.antiriciclaggio import PRESTAZIONE_DIFENSIVA, PRESTAZIONI_IN_AMBITO, LivelloVerifica
        from web.services.antiriciclaggio_cliente_runtime import SOS, TIPI_DOCUMENTO, scheda

        if not _puo("clienti.leggi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        try:
            cliente = _cliente(cliente_id)
            aml = get_antiriciclaggio()
            schede = [dict(scheda(v), evidenze=aml.evidenze_screening(v.id)[:5]) for v in aml.per_cliente(cliente_id)]
        except LookupError as exc:
            return _errore(exc)
        return jsonify({
            "ok": True, "cliente": cliente.nome_completo, "puoModificare": _puo("clienti.scrivi"), "schede": schede,
            "opzioni": {
                "prestazioni": [{"value": k, "label": v} for k, v in PRESTAZIONI_IN_AMBITO.items()]
                + [{"value": PRESTAZIONE_DIFENSIVA, "label": "Difesa o consulenza per un procedimento giudiziario (esclusa, art. 17 c. 7)"}],
                "livelli": [{"value": v.value, "label": v.value.capitalize()} for v in LivelloVerifica],
                "sos": [{"value": k, "label": v} for k, v in SOS.items()],
                "documenti": list(TIPI_DOCUMENTO),
            },
        })

    @app.route("/clienti/<cliente_id>/antiriciclaggio/avvia", methods=["POST"])
    def cliente_aml_avvia(cliente_id: str):
        from web.services.antiriciclaggio_cliente_runtime import campi_da_richiesta

        if not _puo("clienti.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        try:
            _cliente(cliente_id)
            campi = campi_da_richiesta(request.get_json(silent=True) or {})
            verifica = get_antiriciclaggio().nuova(cliente_id=cliente_id, operatore=_operatore(), **campi)
        except (LookupError, ValueError) as exc:
            return _errore(exc)
        audit("clienti.antiriciclaggio_avviato", "aml_verification", verifica.id, dettagli=f"cliente={cliente_id}")
        return jsonify({"ok": True, "message": "Scheda di adeguata verifica aperta.", "verificaId": verifica.id})

    @app.route("/clienti/<cliente_id>/antiriciclaggio/<verifica_id>/aggiorna", methods=["POST"])
    def cliente_aml_aggiorna(cliente_id: str, verifica_id: str):
        from web.services.antiriciclaggio_cliente_runtime import campi_da_richiesta

        if not _puo("clienti.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        try:
            attuale = _verifica(cliente_id, verifica_id)
            campi = campi_da_richiesta(request.get_json(silent=True) or {}, attuale)
            get_antiriciclaggio().aggiorna(verifica_id, operatore=_operatore(), **campi)
        except (LookupError, ValueError) as exc:
            return _errore(exc)
        audit("clienti.antiriciclaggio_aggiornato", "aml_verification", verifica_id, dettagli=f"cliente={cliente_id}")
        return jsonify({"ok": True, "message": "Scheda di adeguata verifica aggiornata."})

    @app.route("/clienti/<cliente_id>/antiriciclaggio/<verifica_id>/conferma", methods=["POST"])
    def cliente_aml_conferma(cliente_id: str, verifica_id: str):
        if not _puo("clienti.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or {}
        try:
            _verifica(cliente_id, verifica_id)
            esito = get_antiriciclaggio().completa(verifica_id, livello_scelto=str(dati.get("livello") or ""),
                                                    motivazione_scostamento=str(dati.get("motivazioneScostamento") or ""),
                                                    operatore=_operatore())
        except (LookupError, ValueError, KeyError) as exc:
            return _errore(exc if not isinstance(exc, KeyError) else LookupError(str(exc)))
        audit("clienti.antiriciclaggio_confermato", "aml_verification", verifica_id, dettagli=f"livello={esito.livello_scelto}")
        return jsonify({"ok": True, "message": "Adeguata verifica confermata: rinnovo del controllo costante programmato."})

    @app.route("/clienti/<cliente_id>/antiriciclaggio/<verifica_id>/screening-ue", methods=["POST"])
    def cliente_aml_screening(cliente_id: str, verifica_id: str):
        """Screening locale sulla lista consolidata UE delle sanzioni finanziarie, senza inviare dati a terzi."""
        from pct.aml_screening import EU_FINANCIAL_SANCTIONS_URL, ScreeningSourceUnavailable, screen_eu_financial_sanctions

        if not _puo("clienti.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        try:
            cliente = _cliente(cliente_id)
            verifica = _verifica(cliente_id, verifica_id)
        except LookupError as exc:
            return _errore(exc)
        aml = get_antiriciclaggio()
        titolare = verifica.titolare_effettivo
        titolare = titolare.get("nome", "") if isinstance(titolare, dict) else getattr(titolare, "nome", "")
        soggetti = [s for s in dict.fromkeys([cliente.nome_completo.strip(), str(titolare or "").strip()]) if s]
        esiti = []
        try:
            for soggetto in soggetti:
                r = screen_eu_financial_sanctions(soggetto, cache_dir=aml.db_path.parent / "screening")
                esiti.append(aml.registra_evidenza_screening(
                    verifica.id, provider_key=r["provider_key"], source_url=r["source_url"], source_version=r["source_version"],
                    snapshot_hash=r["snapshot_hash"], subject_label=r["subject_label"], outcome=r["outcome"],
                    matches=r["matches"], checked_by=_operatore(), note=r["note"]))
        except ScreeningSourceUnavailable as exc:
            aml.registra_evidenza_screening(verifica.id, provider_key="eu-consolidated-financial-sanctions",
                                            source_url=EU_FINANCIAL_SANCTIONS_URL, subject_label=", ".join(soggetti),
                                            outcome="NON_DISPONIBILE", checked_by=_operatore(), note=f"Fonte UE non disponibile: {exc}")
            return jsonify({"ok": False, "message": "Fonte UE non disponibile: screening non conclusivo, riprova più tardi."}), 200
        except ValueError as exc:
            return _errore(exc)
        audit("clienti.antiriciclaggio_screening_ue", "aml_verification", verifica.id, dettagli=",".join(e["outcome"] for e in esiti))
        riscontri = [e for e in esiti if e["outcome"] == "POTENZIALE_RISCONTRO"]
        message = ("Possibile riscontro nella lista UE: apri la prova e valuta manualmente." if riscontri
                   else f"Nessun riscontro nella lista UE per {', '.join(soggetti)}; prova e fonte registrate.")
        return jsonify({"ok": True, "message": message, "evidenze": esiti})

    @app.route("/clienti/<cliente_id>/antiriciclaggio/<verifica_id>/fascicolo.pdf")
    def cliente_aml_pdf(cliente_id: str, verifica_id: str):
        from pct.antiriciclaggio_fascicolo import pdf_fascicolo
        from web.services.antiriciclaggio_cliente_runtime import scheda

        if not _puo("clienti.leggi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        try:
            cliente = _cliente(cliente_id)
            verifica = _verifica(cliente_id, verifica_id)
        except LookupError as exc:
            return _errore(exc)
        aml = get_antiriciclaggio()
        try:
            studio = str(get_config_studio().config.studio.nome or "Studio legale")
        except Exception:
            studio = "Studio legale"
        contenuto = pdf_fascicolo(scheda(verifica), cliente=cliente.nome_completo, studio=studio,
                                  evidenze=aml.evidenze_screening(verifica.id), registro=aml.audit(verifica.id))
        audit("clienti.antiriciclaggio_fascicolo_pdf", "aml_verification", verifica.id, dettagli=f"cliente={cliente_id}")
        return Response(contenuto, mimetype="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename=fascicolo-antiriciclaggio-{verifica.id}.pdf"})
