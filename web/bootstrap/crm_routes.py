"""Route della pipeline CRM di intake (lead → conflitti → cliente).

Base deontologica: artt. 23-24 CDF (incarico e conflitto di interessi),
L. 247/2012 art. 13 (preventivo scritto). La pagina e' la shell React /crm;
le scritture passano da queste route operative con audit.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Flask, g, jsonify, request

from pct.antiriciclaggio import PRESTAZIONE_DIFENSIVA, PRESTAZIONI_IN_AMBITO
from pct.aml_screening import (
    EU_FINANCIAL_SANCTIONS_URL,
    ScreeningSourceUnavailable,
    screen_eu_financial_sanctions,
)
from web.blueprints.react_shell import render_react_shell_response


def register_crm_routes(app: Flask, core: dict[str, Any]) -> None:
    """Registra la superficie CRM leggendo gli accessor dal bundle core."""

    get_crm: Callable[[], Any] = core["get_crm"]
    get_antiriciclaggio: Callable[[], Any] = core["get_antiriciclaggio"]
    get_clienti: Callable[[], Any] = core["get_clienti"]
    get_soggetti: Callable[[], Any] = core["get_soggetti"]
    get_utenti: Callable[[], Any] = core["get_utenti"]
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

    def _flag(value: Any) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "si", "sì", "yes", "on"}

    def _operatore() -> str:
        return str(getattr(g.get("utente_corrente"), "username", "") or "avvocato").strip() or "avvocato"

    def _utenti_autorizzabili() -> list[dict[str, str]]:
        """Espone solo gli utenti attivi necessari al selettore della barriera."""

        corrente = g.get("utente_corrente")
        can_read_users = False
        try:
            can_read_users = bool(corrente and corrente.ha_permesso("utenti.leggi"))
        except Exception:
            can_read_users = False
        if not can_read_users:
            username = _operatore()
            return [{"username": username, "label": username}]
        try:
            utenti = list(get_utenti().tutti(solo_attivi=True))
        except Exception:
            utenti = []
        return [
            {
                "username": str(getattr(utente, "username", "") or "").strip(),
                "label": str(getattr(utente, "nome_completo", "") or getattr(utente, "username", "")).strip(),
            }
            for utente in utenti
            if str(getattr(utente, "username", "") or "").strip()
        ]

    def _normalizza_utenti_autorizzati(dati: Any) -> list[str]:
        values = dati.get("utentiAutorizzati") or dati.get("utenti_autorizzati") or []
        if not isinstance(values, (list, tuple, set)):
            raise ValueError("Gli utenti autorizzati devono essere indicati come elenco.")
        allowed = {item["username"].strip().lower() for item in _utenti_autorizzabili() if item.get("username")}
        normalized = {str(value or "").strip().lower() for value in values if str(value or "").strip()}
        unknown = sorted(normalized - allowed)
        if unknown:
            raise ValueError("Uno o più utenti autorizzati non risultano attivi nello studio.")
        return sorted(normalized)

    def _accesso_lead(lead_id: str, *, azione: str):
        crm = get_crm()
        if crm.get(lead_id) is None:
            return None
        if crm.accesso_lead_consentito(lead_id, operatore=_operatore()):
            return None
        crm.registra_accesso_barriera_negato(lead_id, operatore=_operatore(), azione=azione)
        return jsonify({"ok": False, "message": "Azione non consentita: il contatto è protetto da una barriera informativa."}), 403

    @app.route("/crm")
    def crm_pipeline_page():
        return render_react_shell_response("crm")

    @app.route("/api/v1/ui/crm")
    def crm_pipeline_payload():
        from web.services.react_crm_bridge import build_react_crm_payload

        if not _permesso():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        try:
            return jsonify(
                build_react_crm_payload(
                    get_crm=get_crm,
                    get_antiriciclaggio=get_antiriciclaggio,
                    operatore=_operatore(),
                    utenti_autorizzabili=_utenti_autorizzabili(),
                )
            )
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
        denied = _accesso_lead(lead_id, azione="aggiornamento_stato")
        if denied:
            return denied
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
        denied = _accesso_lead(lead_id, azione="verifica_conflitti")
        if denied:
            return denied
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

    @app.route("/crm/lead/<lead_id>/conflitti/decisione", methods=["POST"])
    def crm_lead_decisione_conflitto(lead_id: str):
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        denied = _accesso_lead(lead_id, azione="decisione_conflitto")
        if denied:
            return denied
        dati = request.get_json(silent=True) or request.form
        try:
            esito = get_crm().registra_decisione_conflitto(
                lead_id,
                decisione=str(dati.get("decisione") or ""),
                motivazione=str(dati.get("motivazione") or ""),
                operatore=_operatore(),
            )
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Errore decisione conflitto lead %s: %s", lead_id, exc)
            return jsonify({"ok": False, "message": f"Decisione non registrata: {exc}"}), 200
        audit("crm.conflitto_deciso", "crm_lead", lead_id, dettagli=esito.get("decisione") or "")
        message = "Clearance registrata." if esito.get("decisione") == "CLEARANCE_CONCESSA" else "Astensione registrata."
        return jsonify({"ok": True, "message": message, "messaggio": message, "esito": esito})

    @app.route("/crm/lead/<lead_id>/aggiorna", methods=["POST"])
    def crm_lead_aggiorna(lead_id: str):
        """Correzione contestuale prima della conversione in anagrafica."""

        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        denied = _accesso_lead(lead_id, azione="correzione_dati")
        if denied:
            return denied
        dati = request.get_json(silent=True) or request.form
        campi = {
            "denominazione": str(dati.get("denominazione") or ""),
            "codice_fiscale": str(dati.get("codiceFiscale") or dati.get("codice_fiscale") or ""),
            "partita_iva": str(dati.get("partitaIva") or dati.get("partita_iva") or ""),
            "email": str(dati.get("email") or ""),
            "telefono": str(dati.get("telefono") or ""),
            "fonte": str(dati.get("fonte") or "altro"),
            "materia": str(dati.get("materia") or ""),
            "esigenza": str(dati.get("esigenza") or ""),
            "note": str(dati.get("note") or ""),
        }
        try:
            lead = get_crm().aggiorna(lead_id, **campi)
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Errore correzione lead %s: %s", lead_id, exc)
            return jsonify({"ok": False, "message": f"Correzione non riuscita: {exc}"}), 200
        audit("crm.lead_corretto", "crm_lead", lead_id, dettagli="correzione dati intake")
        message = "Dati del contatto aggiornati. Riesegui la verifica conflitti prima della conversione."
        return jsonify({"ok": True, "message": message, "messaggio": message, "leadId": lead.id})

    @app.route("/crm/lead/<lead_id>/converti", methods=["POST"])
    def crm_lead_converti(lead_id: str):
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        denied = _accesso_lead(lead_id, azione="conversione_cliente")
        if denied:
            return denied

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

    @app.route("/crm/lead/<lead_id>/barriera-riservatezza", methods=["POST"])
    def crm_lead_barriera_riservatezza_crea(lead_id: str):
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        denied = _accesso_lead(lead_id, azione="istituzione_barriera_informativa")
        if denied:
            return denied
        dati = request.get_json(silent=True) or request.form
        try:
            stato = get_crm().crea_barriera_riservatezza(
                lead_id,
                motivazione=str(dati.get("motivazione") or ""),
                utenti_autorizzati=_normalizza_utenti_autorizzati(dati),
                operatore=_operatore(),
                titolo=str(dati.get("titolo") or "Barriera informativa del fascicolo"),
            )
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 403
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Errore istituzione barriera lead %s: %s", lead_id, exc)
            return jsonify({"ok": False, "message": f"Barriera informativa non istituita: {exc}"}), 200
        audit("crm.barriera_informativa_istituita", "crm_lead", lead_id, dettagli=f"barriera={stato.get('id')}")
        message = "Barriera informativa istituita: il contatto è visibile solo ai professionisti autorizzati."
        return jsonify({"ok": True, "message": message, "messaggio": message, "stato": stato})

    @app.route("/crm/lead/<lead_id>/barriera-riservatezza/aggiorna", methods=["POST"])
    def crm_lead_barriera_riservatezza_aggiorna(lead_id: str):
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        denied = _accesso_lead(lead_id, azione="aggiornamento_barriera_informativa")
        if denied:
            return denied
        dati = request.get_json(silent=True) or request.form
        try:
            stato = get_crm().aggiorna_barriera_riservatezza(
                lead_id,
                motivazione=str(dati.get("motivazione") or ""),
                utenti_autorizzati=_normalizza_utenti_autorizzati(dati),
                operatore=_operatore(),
            )
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 403
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Errore aggiornamento barriera lead %s: %s", lead_id, exc)
            return jsonify({"ok": False, "message": f"Barriera informativa non aggiornata: {exc}"}), 200
        audit("crm.barriera_informativa_aggiornata", "crm_lead", lead_id, dettagli=f"barriera={stato.get('id')}")
        return jsonify({"ok": True, "message": "Autorizzazioni della barriera aggiornate.", "messaggio": "Autorizzazioni della barriera aggiornate.", "stato": stato})

    @app.route("/crm/lead/<lead_id>/barriera-riservatezza/revoca", methods=["POST"])
    def crm_lead_barriera_riservatezza_revoca(lead_id: str):
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        denied = _accesso_lead(lead_id, azione="revoca_barriera_informativa")
        if denied:
            return denied
        dati = request.get_json(silent=True) or request.form
        try:
            stato = get_crm().revoca_barriera_riservatezza(
                lead_id,
                motivazione=str(dati.get("motivazione") or ""),
                operatore=_operatore(),
            )
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 403
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Errore revoca barriera lead %s: %s", lead_id, exc)
            return jsonify({"ok": False, "message": f"Barriera informativa non revocata: {exc}"}), 200
        audit("crm.barriera_informativa_revocata", "crm_lead", lead_id, dettagli=f"barriera={stato.get('id')}")
        return jsonify({"ok": True, "message": "Barriera informativa revocata con motivazione.", "messaggio": "Barriera informativa revocata con motivazione.", "stato": stato})

    @app.route("/crm/lead/<lead_id>/antiriciclaggio/avvia", methods=["POST"])
    def crm_lead_antiriciclaggio_avvia(lead_id: str):
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        denied = _accesso_lead(lead_id, azione="avvio_adeguata_verifica")
        if denied:
            return denied
        dati = request.get_json(silent=True) or request.form
        lead = get_crm().get(lead_id)
        if lead is None:
            return jsonify({"ok": False, "message": "Lead non trovato."}), 404
        if not lead.cliente_id:
            return jsonify({"ok": False, "message": "Prima crea e collega il cliente dall'intake."}), 400
        prestazione = str(dati.get("prestazione") or "").strip()
        scopo_natura = str(dati.get("scopoNatura") or dati.get("scopo_natura") or "").strip()
        if not prestazione or not scopo_natura:
            return jsonify({"ok": False, "message": "Indica prestazione e scopo/natura del rapporto."}), 400
        if prestazione not in (*PRESTAZIONI_IN_AMBITO, PRESTAZIONE_DIFENSIVA):
            return jsonify({"ok": False, "message": "Prestazione AML non riconosciuta."}), 400
        aml = get_antiriciclaggio()
        esistenti = aml.per_lead(lead.id)
        if esistenti:
            verifica = esistenti[0]
            message = "Esiste già una scheda di adeguata verifica collegata a questo intake."
            return jsonify({"ok": True, "message": message, "messaggio": message, "verificaId": verifica.id, "esistente": True})
        titolare = dati.get("titolareEffettivo") or dati.get("titolare_effettivo") or {}
        if not isinstance(titolare, dict):
            titolare = {}
        try:
            verifica = aml.nuova(
                cliente_id=lead.cliente_id,
                lead_id=lead.id,
                prestazione=prestazione,
                descrizione_prestazione=str(dati.get("descrizionePrestazione") or dati.get("descrizione_prestazione") or ""),
                scopo_natura=scopo_natura,
                cliente_pep=_flag(dati.get("clientePep") or dati.get("cliente_pep")),
                paese_alto_rischio=_flag(dati.get("paeseAltoRischio") or dati.get("paese_alto_rischio")),
                titolare_effettivo=titolare,
                operatore=_operatore(),
                note=str(dati.get("note") or ""),
            )
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Errore avvio AML lead %s: %s", lead_id, exc)
            return jsonify({"ok": False, "message": f"Adeguata verifica non avviata: {exc}"}), 200
        audit("crm.antiriciclaggio_avviato", "aml_verification", verifica.id, dettagli=f"lead={lead.id}")
        return jsonify({"ok": True, "message": "Scheda di adeguata verifica avviata e collegata al cliente.", "messaggio": "Scheda di adeguata verifica avviata e collegata al cliente.", "verificaId": verifica.id})

    @app.route("/crm/lead/<lead_id>/antiriciclaggio/<verifica_id>/aggiorna", methods=["POST"])
    def crm_lead_antiriciclaggio_aggiorna(lead_id: str, verifica_id: str):
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        denied = _accesso_lead(lead_id, azione="aggiornamento_adeguata_verifica")
        if denied:
            return denied
        dati = request.get_json(silent=True) or request.form
        aml = get_antiriciclaggio()
        verifica = aml.get(verifica_id)
        if verifica is None or verifica.lead_id != lead_id:
            return jsonify({"ok": False, "message": "Scheda AML non trovata per questo intake."}), 404
        titolare = dati.get("titolareEffettivo") or dati.get("titolare_effettivo") or {}
        if not isinstance(titolare, dict):
            titolare = {}
        prestazione = str(dati.get("prestazione") or verifica.prestazione)
        if prestazione not in (*PRESTAZIONI_IN_AMBITO, PRESTAZIONE_DIFENSIVA):
            return jsonify({"ok": False, "message": "Prestazione AML non riconosciuta."}), 400
        aggiornata = aml.aggiorna(
            verifica_id,
            prestazione=prestazione,
            descrizione_prestazione=str(dati.get("descrizionePrestazione") or dati.get("descrizione_prestazione") or verifica.descrizione_prestazione),
            scopo_natura=str(dati.get("scopoNatura") or dati.get("scopo_natura") or verifica.scopo_natura),
            cliente_pep=_flag(dati.get("clientePep") or dati.get("cliente_pep")),
            paese_alto_rischio=_flag(dati.get("paeseAltoRischio") or dati.get("paese_alto_rischio")),
            titolare_effettivo=titolare,
            note=str(dati.get("note") or verifica.note),
            operatore=_operatore(),
        )
        if aggiornata is None:
            return jsonify({"ok": False, "message": "Scheda AML non trovata."}), 404
        audit("crm.antiriciclaggio_aggiornato", "aml_verification", verifica_id, dettagli=f"lead={lead_id}")
        return jsonify({"ok": True, "message": "Scheda di adeguata verifica aggiornata.", "messaggio": "Scheda di adeguata verifica aggiornata."})

    @app.route("/crm/lead/<lead_id>/antiriciclaggio/<verifica_id>/conferma", methods=["POST"])
    def crm_lead_antiriciclaggio_conferma(lead_id: str, verifica_id: str):
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        denied = _accesso_lead(lead_id, azione="conferma_adeguata_verifica")
        if denied:
            return denied
        dati = request.get_json(silent=True) or request.form
        aml = get_antiriciclaggio()
        verifica = aml.get(verifica_id)
        if verifica is None or verifica.lead_id != lead_id:
            return jsonify({"ok": False, "message": "Scheda AML non trovata per questo intake."}), 404
        try:
            esito = aml.completa(
                verifica_id,
                livello_scelto=str(dati.get("livello") or ""),
                motivazione_scostamento=str(dati.get("motivazioneScostamento") or dati.get("motivazione_scostamento") or ""),
                operatore=_operatore(),
            )
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        audit("crm.antiriciclaggio_confermato", "aml_verification", verifica_id, dettagli=f"livello={esito.livello_scelto}")
        return jsonify({"ok": True, "message": "Adeguata verifica confermata e rinnovo programmato.", "messaggio": "Adeguata verifica confermata e rinnovo programmato."})

    @app.route("/crm/lead/<lead_id>/antiriciclaggio/<verifica_id>/screening-ue", methods=["POST"])
    def crm_lead_antiriciclaggio_screening_ue(lead_id: str, verifica_id: str):
        """Screening locale sullo snapshot UE, senza inviare dati a terzi."""

        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        denied = _accesso_lead(lead_id, azione="screening_lista_ue")
        if denied:
            return denied
        lead = get_crm().get(lead_id)
        aml = get_antiriciclaggio()
        verifica = aml.get(verifica_id)
        if lead is None or verifica is None or verifica.lead_id != lead_id:
            return jsonify({"ok": False, "message": "Scheda AML non trovata per questo intake."}), 404
        titolare = getattr(verifica, "titolare_effettivo", None)
        subject = str(getattr(titolare, "nome", "") or lead.denominazione or "").strip()
        try:
            result = screen_eu_financial_sanctions(
                subject,
                cache_dir=aml.db_path.parent / "screening",
            )
            evidence = aml.registra_evidenza_screening(
                verifica.id,
                provider_key=result["provider_key"],
                source_url=result["source_url"],
                source_version=result["source_version"],
                snapshot_hash=result["snapshot_hash"],
                subject_label=result["subject_label"],
                outcome=result["outcome"],
                matches=result["matches"],
                checked_by=_operatore(),
                note=result["note"],
            )
        except ScreeningSourceUnavailable as exc:
            evidence = aml.registra_evidenza_screening(
                verifica.id,
                provider_key="eu-consolidated-financial-sanctions",
                source_url=EU_FINANCIAL_SANCTIONS_URL,
                subject_label=subject,
                outcome="NON_DISPONIBILE",
                checked_by=_operatore(),
                note=f"Fonte UE non disponibile: {exc}",
            )
            audit("crm.antiriciclaggio_screening_non_disponibile", "aml_verification", verifica.id, dettagli=str(exc))
            return jsonify({"ok": False, "message": "Fonte UE non disponibile: screening non conclusivo, rieseguire più tardi.", "messaggio": "Fonte UE non disponibile: screening non conclusivo, rieseguire più tardi.", "evidenza": evidence}), 200
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Errore screening UE lead %s: %s", lead_id, exc)
            return jsonify({"ok": False, "message": f"Screening non conclusivo: {exc}"}), 200
        audit("crm.antiriciclaggio_screening_ue", "aml_verification", verifica.id, dettagli=evidence["outcome"])
        message = (
            "Possibile riscontro nella lista UE: apri la prova e valuta manualmente."
            if evidence["outcome"] == "POTENZIALE_RISCONTRO"
            else "Nessun riscontro nella lista UE verificata; prova e fonte sono registrate."
        )
        return jsonify({"ok": True, "message": message, "messaggio": message, "evidenza": evidence})
