"""Legacy deposito send route kept out of the main deposito bootstrap."""

from __future__ import annotations

import os
import tempfile as _tmp
import uuid as _uuid
from collections.abc import Callable
from datetime import datetime as _dt
from typing import Any

from flask import Flask, flash, g, jsonify, redirect, request, url_for

from pct.deposito_simulazione import simulated_deposit_note
from pct.fascicoli import EsitoDepositoPCT
from pct.pst_cifratura import PSTCifraturaError
from web.services.deposito_route_helpers import (
    allegati_busta as _allegati_busta,
    deposito_oggetto as _deposito_oggetto,
    guided_transport_completion_response as _guided_transport_completion_response,
    ufficio_deposito_destinatario as _ufficio_deposito_destinatario,
    validate_busta_document_selection as _validate_busta_document_selection,
    validation_summary as _validation_summary,
    wants_json_response as _wants_json_response,
)
from web.services.local_pec_runtime import (
    deposito_pec_body,
    deposito_pec_subject,
    local_pec_required_response,
    local_pec_confirmation_result,
)


def register_deposito_legacy_send_route(
    app: Flask,
    *,
    get_fascicoli: Callable[[], object],
    get_config_studio: Callable[[], object],
    audit: Callable[..., None],
    sync_pubblica: Callable[..., None],
    run_deposito_validation: Callable[..., object],
    polis_demo_mode: Callable[[], bool],
    documenti_busta_nomi: Callable[[str, list[Any]], list[str]],
) -> None:
    """Register the classic POST deposito send endpoint."""

    @app.route("/fascicoli/<id_fasc>/deposito/invia", methods=["POST"])
    def deposito_invia(id_fasc):
        """Crea la busta telematica e la invia via PEC all'ufficio giudiziario."""
        gestore_fascicoli = get_fascicoli()
        utente = g.utente_corrente
        form = request.form
        fascicolo = gestore_fascicoli.get(id_fasc)
        if not fascicolo:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("lista_fascicoli"))

        demo_mode_raw = form.get("demo_mode")
        demo_mode = (demo_mode_raw == "1") if demo_mode_raw in {"0", "1"} else polis_demo_mode()
        tipo_atto = form.get("tipo_atto", "ATTO").strip()
        codice_registro = form.get("codice_registro", "RG").strip()
        numero_rg = form.get("numero_rg", "").strip()
        anno_rg_str = form.get("anno_rg", "").strip()
        oggetto = _deposito_oggetto(form, fascicolo)
        note = form.get("note", "").strip()
        ufficio_deposito = _ufficio_deposito_destinatario(fascicolo)
        tribunale_nome = (
            form.get("tribunale_nome", "").strip()
            or str(ufficio_deposito.get("nome") or "").strip()
            or fascicolo.tribunale
        )
        tribunale_pec = form.get("tribunale_pec", "").strip() or str(ufficio_deposito.get("pec_dest") or "").strip()
        codice_ufficio = str(ufficio_deposito.get("codice_ufficio") or "").strip() or form.get("codice_ufficio", "").strip()
        atto_id = form.get("atto_principale_id", "").strip()
        allegati_ids = request.form.getlist("allegati_ids")

        validation = run_deposito_validation(
            fasc=fascicolo,
            gf=gestore_fascicoli,
            form_like=request.form,
            operatore=utente.username if utente else "",
        )
        blockers = [issue for issue in validation.issues if issue.get("level") == "BLOCK"]
        if blockers:
            first = blockers[0]
            return jsonify(
                {
                    "ok": False,
                    "errore": f"{first.get('title')}. {first.get('suggested_action', '')}".strip(),
                    "validation": _validation_summary(validation),
                }
            ), 400

        if not tribunale_nome:
            flash("Seleziona un ufficio giudiziario destinatario.", "danger")
            return redirect(url_for("deposito_prepara", id_fasc=id_fasc))
        if not atto_id:
            flash("Seleziona l'atto principale da includere nella busta.", "danger")
            return redirect(url_for("deposito_prepara", id_fasc=id_fasc))

        selection_error = _validate_busta_document_selection(
            fascicolo,
            gestore_fascicoli,
            id_fasc,
            form,
            atto_id,
            allegati_ids,
        )
        if selection_error:
            if _wants_json_response(request.headers):
                return jsonify({"ok": False, "errore": selection_error}), 400
            flash(selection_error, "danger")
            return redirect(url_for("deposito_prepara", id_fasc=id_fasc))

        anno_rg = int(anno_rg_str) if anno_rg_str.isdigit() else (fascicolo.anno_rg or 0)
        id_dep = form.get("local_pec_id_deposito", "").strip() or _uuid.uuid4().hex[:8].upper()
        timestamp = _dt.now().isoformat()

        if demo_mode:
            pec_prova = tribunale_pec or f"{tribunale_nome.lower().replace(' ', '.')}@pec.prova.invalid"
            esito = EsitoDepositoPCT(
                id=id_dep,
                timestamp=timestamp,
                stato="INVIATO",
                tipo_atto=tipo_atto,
                pec_destinatario=pec_prova,
                messaggio=(
                    f"Prova deposito senza invio reale: busta {id_dep} predisposta per {tribunale_nome}. "
                    f"Atto: {tipo_atto} - RG {numero_rg}/{anno_rg}."
                ),
                note=simulated_deposit_note(note),
                registrato_da=utente.username if utente else "prova",
            )
        else:
            try:
                from pct.busta import Allegato as AllegatoBusta
                from pct.busta import BustaTelematica, DatiBusta
                atto_doc = next((doc for doc in fascicolo.documenti if doc.id == atto_id), None)
                if not atto_doc:
                    flash("Documento selezionato come atto principale non trovato.", "danger")
                    return redirect(url_for("deposito_prepara", id_fasc=id_fasc))

                atto_path = str(gestore_fascicoli.percorso_documento(id_fasc, atto_id))
                allegati_busta = _allegati_busta(
                    fascicolo,
                    gestore_fascicoli,
                    id_fasc,
                    [item for item in allegati_ids if item != atto_id],
                    AllegatoBusta,
                )

                dati = DatiBusta(
                    codice_ufficio=codice_ufficio or tribunale_nome,
                    codice_registro=codice_registro,
                    oggetto=oggetto,
                    tipo_atto=tipo_atto,
                    atto_principale=atto_path,
                    allegati=allegati_busta,
                    numero_rg=numero_rg or None,
                    anno_rg=anno_rg or None,
                    operatore=utente.username if utente else "",
                    cf_mittente="",
                )

                cfg_studio = get_config_studio().config
                pec_cfg = cfg_studio.pec if cfg_studio and hasattr(cfg_studio, "pec") else None
                if not pec_cfg or not pec_cfg.indirizzo:
                    raise RuntimeError(
                        "Configurazione PEC non trovata. Configura le credenziali PEC nelle impostazioni."
                    )

                pec_dest = tribunale_pec
                if not pec_dest and codice_ufficio:
                    try:
                        from pct.uffici_giudiziari import get_gestore as _get_uff

                        cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
                        ufficio = next(
                            (
                                row
                                for row in _get_uff(cache_path).carica()
                                if row.get("codice") == codice_ufficio
                            ),
                            None,
                        )
                        pec_dest = str((ufficio or {}).get("pec") or "")
                    except Exception:
                        pass

                if not pec_dest:
                    raise RuntimeError(
                        f"Indirizzo PEC non trovato per l'ufficio '{tribunale_nome}'. "
                        "Verifica la selezione o imposta manualmente la PEC."
                    )

                oggetto_pec = deposito_pec_subject(
                    tipo_atto=tipo_atto,
                    numero_rg=numero_rg or None,
                    anno_rg=anno_rg or None,
                    tribunale=tribunale_nome,
                )
                from pathlib import Path as _Path

                output_dir = os.getenv("PCT_DEPOSITI_DIR", _tmp.gettempdir())
                busta_dir = _Path(output_dir) / id_dep
                busta = BustaTelematica(dati)
                documenti_busta = documenti_busta_nomi(atto_path, allegati_busta)
                corpo_pec = form.get("corpo_pec", "").strip() or deposito_pec_body(documenti_busta)
                try:
                    busta_path = busta.crea_busta(str(busta_dir))
                except PSTCifraturaError as exc:
                    app.logger.exception("Certificato PST/cifratura busta non completata %s: %s", id_fasc, exc)
                    guided_response = _guided_transport_completion_response(
                        busta=busta,
                        id_deposito=id_dep,
                        timestamp=timestamp,
                        pec_dest=pec_dest,
                        tipo_atto=tipo_atto,
                        oggetto_pec=oggetto_pec,
                        corpo_pec=corpo_pec,
                        documenti_busta=documenti_busta,
                        attachment_path=getattr(busta, "_last_atto_msg_path", "") or "",
                        validation=validation,
                    )
                    return jsonify(
                        guided_response
                        or {
                            "ok": False,
                            "requires_guided_completion": True,
                            "package_ready": True,
                            "errore": "Invio diretto sospeso: certificato PST non disponibile.",
                            "message": (
                                "Il software ha preparato il pacchetto di controllo, ma non registra un deposito "
                                "come valido finche' Atto.msg non viene cifrato in Atto.enc con il certificato PST."
                            ),
                            "next_actions": [
                                f"Recupera o collega il certificato pubblico PST .cer dell'ufficio {codice_ufficio}.",
                                "Genera Atto.enc ministeriale prima dell'invio reale.",
                            ],
                            "documenti_busta": documenti_busta,
                            "corpo_pec": corpo_pec,
                        }
                    ), 409
                guided_response = _guided_transport_completion_response(
                    busta=busta,
                    id_deposito=id_dep,
                    timestamp=timestamp,
                    pec_dest=pec_dest,
                    tipo_atto=tipo_atto,
                    oggetto_pec=oggetto_pec,
                    corpo_pec=corpo_pec,
                    documenti_busta=documenti_busta,
                    attachment_path=busta_path,
                    validation=validation,
                )
                if guided_response:
                    return jsonify(guided_response), 409
                if form.get("local_pec_confirmed") != "1":
                    return jsonify(
                        local_pec_required_response(
                            pec_cfg=pec_cfg,
                            pec_dest=pec_dest,
                            tipo_atto=tipo_atto,
                            id_deposito=id_dep,
                            timestamp=timestamp,
                            oggetto_pec=oggetto_pec,
                            attachment_path=busta_path,
                            validation=validation,
                            documenti=documenti_busta,
                            corpo_pec=corpo_pec,
                            busta_audit=busta.audit_conformita_pst(),
                        )
                    )

                ris_locale = local_pec_confirmation_result(form.get("local_pec_message_id", ""))
                esito = EsitoDepositoPCT(
                    id=id_dep,
                    timestamp=timestamp,
                    stato="INVIATO",
                    tipo_atto=tipo_atto,
                    pec_destinatario=pec_dest,
                    messaggio=(
                        f"Busta {id_dep} inviata via PEC dal PC locale tramite Local Signer. "
                        f"Message-ID: {ris_locale.get('message_id', '')}"
                    ),
                    note=note,
                    registrato_da=utente.username if utente else "",
                    busta_path=busta_path,
                )
            except Exception as exc:
                app.logger.exception("Errore deposito_invia %s: %s", id_fasc, exc)
                flash("Deposito non completato. Verifica il canale ufficiale e riprova.", "danger")
                return redirect(url_for("deposito_prepara", id_fasc=id_fasc))

        try:
            from datetime import datetime as _dtnow

            documenti_deposito_ids = [atto_id] + [aid for aid in allegati_ids if aid and aid != atto_id]
            if not getattr(esito, "documenti_ids", None):
                esito.documenti_ids = documenti_deposito_ids
            fascicolo.depositi_pct.append(esito)
            for documento in fascicolo.documenti:
                if documento.id in documenti_deposito_ids:
                    documento.id_deposito_pct = esito.id
            fascicolo.modificato_il = _dtnow.now().isoformat()
            gestore_fascicoli._salva()
            audit(
                "fascicoli.deposito.invia",
                "fascicolo",
                id_fasc,
                dettagli=f"Deposito {esito.id} - {tipo_atto} verso {esito.pec_destinatario}",
            )
            sync_pubblica("modifica", "fascicoli", id_fasc, utente=utente.username if utente else "")
            if demo_mode:
                flash(
                    f"Deposito di prova registrato con ID {esito.id}. Nessun messaggio PEC è stato spedito.",
                    "warning",
                )
            else:
                flash(
                    f"Deposito {esito.id} inviato via PEC a {esito.pec_destinatario}. Ricevute di accettazione e consegna saranno disponibili a breve.",
                    "success",
                )
        except Exception as exc:
            app.logger.exception("Errore salvataggio esito deposito %s: %s", id_fasc, exc)
            flash("Deposito inviato, ma il salvataggio dell'esito non è stato completato.", "warning")

        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
