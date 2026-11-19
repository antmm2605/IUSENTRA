"""Le parti di un pannello pronto che dipendono dall'utente e dal momento dell'apertura.

Il pannello «Letture» dice che cosa è nuovo dall'ultima apertura dell'utente e registra la vista: è una
proiezione personale che cambia a ogni apertura. Il resto del pannello si serve dal salvato; le novità si
ricompongono con la stessa funzione del motore (``novita_letture``) e la vista si registra come prima, salvo
``visto=0``.
"""

from __future__ import annotations

import json

from flask import request


def novita_letture(corpo: bytes, fascicolo_id: str) -> bytes:
    from pct.registro_letture.sintesi import sintesi_lettori_operativi
    from web.services.registro_letture_runtime import novita_letture as calcola

    dati = json.loads(corpo.decode("utf-8"))
    letture = dati.get("letture") if isinstance(dati, dict) else None
    if not isinstance(letture, dict):
        return corpo
    if isinstance(letture.get("sintesi"), dict) and isinstance(letture.get("lettori"), list):
        letture["sintesi"] = sintesi_lettori_operativi(letture["sintesi"], letture["lettori"])
    segna = str(request.args.get("visto") or "1").strip().lower() not in {"0", "false", "no"}
    try:
        from web.blueprints.api_v1_react import _public_json_payload  # stessa sanificazione della risposta del motore

        letture["novita"] = _public_json_payload(calcola(fascicolo_id, segna_visto=segna), "novita")
    except Exception:
        # Come nel motore: le novità che non si leggono non fanno sparire il pannello, si dichiarano.
        letture.setdefault("degradato", []).append({"passo": "novità dall'ultima apertura",
                                                     "motivo": "Novità non disponibili in questo momento."})
    return json.dumps(dati, ensure_ascii=False).encode("utf-8")


def obblighi_da_lettura(corpo: bytes, fascicolo_id: str) -> bytes:
    from web.blueprints.api_v1_react import _con_riscontri_processuali, _public_json_payload

    dati = json.loads(corpo)
    risultato = _con_riscontri_processuali(dati, fascicolo_id, "notifiche")
    return json.dumps(_public_json_payload(risultato), ensure_ascii=False).encode("utf-8")


def allinea_attivita_udienze(dati: dict, lettura: dict | None) -> None:
    """Presenta le attività automatiche con il provvedimento già riscontrato nella Lettura."""
    if not lettura or lettura.get("aggiornamento_pendente") or not dati.get("activities"):
        return
    udienze = (lettura.get("ragionamento") or {}).get("udienze") or []
    fonti = {(u["data"], u["documento_id"]): u for u in udienze if u.get("data") and u.get("documento_id")}
    date_con_provvedimento = {giorno for giorno, _ in fonti}
    documenti = {d["id"]: d for d in (lettura.get("documenti") or {}).get("tutti", [])}
    attivita = []
    for voce in dati["activities"]:
        giorno, oid = voce.get("date"), voce.get("sourceDocumentId")
        automatica = voce.get("readOnly") and (voce.get("sourceIsDerived") or voce.get("sourceConfirmedInAgenda"))
        if voce.get("type") != "UDIENZA" or not automatica or voce.get("result") == "ANNULLATO":
            attivita.append(voce)
            continue
        udienza = fonti.get((giorno, oid))
        if udienza:
            modalita = udienza.get("modalita") or ""
            ora = udienza.get("ora") or ""
            descrizione = f"Udienza fissata con provvedimento del giudice · {modalita}" if modalita else "Udienza fissata con provvedimento del giudice"
            if ora:
                descrizione += f" · ore {ora}"
            voce = {**voce, "description": descrizione, "hearingTime": ora, "result": "REGISTRATO",
                    "sourceDocumentLabel": udienza.get("documento") or voce.get("sourceDocumentLabel"),
                    "sourceExcerpt": udienza.get("brano") or voce.get("sourceExcerpt")}
        elif _fonte_secondaria_udienza(documenti.get(oid, {})) and (
            giorno in date_con_provvedimento or (voce.get("sourceIsDerived") and not voce.get("sourceConfirmedInAgenda"))
        ):
            continue
        attivita.append(voce)
    dati["activities"] = attivita


def _fonte_secondaria_udienza(documento: dict, nome_fonte: str = "") -> bool:
    from pct.pec_oggetti_ufficiali import classifica_ricevuta_pec

    etichetta = str(documento.get("etichetta") or "").casefold()
    return (
        documento.get("natura") in {"precedente_giurisprudenziale", "attestazione", "atto_difensivo"}
        or etichetta.startswith(("ricevuta pec", "copia non crittografata del deposito", "note scritte"))
        or bool(classifica_ricevuta_pec(documento.get("nome") or nome_fonte, usa_corpo=False)[0])
    )


def allinea_presidio_udienze(dati: dict, lettura: dict | None, fascicolo_id: str) -> None:
    """Ricollega le proposte storiche al provvedimento letto nel fascicolo."""
    from web.services.contributo_stato_runtime import href_documento

    presidio = dati.get("documentPresidio") or {}
    if not lettura or lettura.get("aggiornamento_pendente") or not presidio.get("actions"):
        return
    ragionamento = lettura.get("ragionamento") or {}
    per_giorno = {}
    for udienza in ragionamento.get("udienze") or ():
        if udienza.get("data") and udienza.get("documento_id"):
            per_giorno.setdefault(udienza["data"], []).append(udienza)
    termini = {}
    costituzioni = {}
    for conclusione in ragionamento.get("conclusioni") or ():
        fonte = conclusione.get("letto") or {}
        termine = conclusione.get("termine") or {}
        if conclusione.get("codice") == "costituzione_convenuto" and fonte.get("documento_id") and termine.get("data_grezza"):
            for riferimento in {fonte["documento_id"], *(termine.get("fonti_trasmissione") or ())}:
                for data in {termine["data_grezza"], termine.get("scadenza_iso")} - {None, ""}:
                    costituzioni.setdefault((data, riferimento), []).append(conclusione)
        if conclusione.get("codice") != "notifica_ordinata" or conclusione.get("stato") != "fatto":
            continue
        busta = (conclusione.get("prova_notifica") or {}).get("deposito_inviato") or {}
        scadenza = termine.get("scadenza_iso")
        if busta.get("copia_in_chiaro_id") and scadenza and fonte.get("documento_id"):
            termini.setdefault((scadenza, busta["copia_in_chiaro_id"]), []).append(conclusione)
    documenti = {d["id"]: d for d in (lettura.get("documenti") or {}).get("tutti", [])}
    azioni = []
    note = {(a.get("date"), a.get("documentId")) for a in presidio["actions"] if a.get("type") == "note_127_ter"}
    udienze_viste = {}
    for azione in presidio["actions"]:
        registrata = bool(azione.get("registeredHref"))
        if not azione.get("historical"):
            azioni.append(azione)
            continue
        oid, tipo = azione.get("documentId"), azione.get("type")
        if tipo in {"udienza_documento", "udienza_127_bis"}:
            candidati = per_giorno.get(azione.get("date"), ())
            diretti = [u for u in candidati if u["documento_id"] == oid]
            secondaria = _fonte_secondaria_udienza(documenti.get(oid, {}), azione.get("source") or "")
            compatibili = [u for u in candidati if (
                (not azione.get("time") or azione["time"] == u.get("ora"))
                and (tipo != "udienza_127_bis" or str(u.get("modalita") or "").startswith("da remoto"))
            )]
            corrispondenza = diretti or (compatibili if secondaria else ())
            if len(corrispondenza) == 1:
                udienza = corrispondenza[0]
                chiave = (udienza["data"], udienza["documento_id"])
                modalita = udienza.get("modalita") or ""
                if not registrata and (chiave in udienze_viste or (
                    modalita.startswith("sostituita da note scritte") and chiave in note
                )):
                    continue
                azione = {**azione, "documentId": udienza["documento_id"], "source": udienza.get("documento"),
                          "sourceHref": href_documento(fascicolo_id, udienza["documento_id"]),
                          "description": " · ".join(filter(None, [modalita, udienza.get("ora")])) or azione.get("description", "")}
                precedente = udienze_viste.get(chiave)
                if registrata and precedente is not None and not azioni[precedente].get("registeredHref"):
                    azioni[precedente] = azione
                    continue
                udienze_viste[chiave] = len(azioni)
            elif secondaria and not compatibili and not registrata:
                continue
        if not registrata and tipo in {"costituzione_convenuto", "costituzione_resistente"}:
            candidati = costituzioni.get((azione.get("dateIso"), oid), ())
            if len(candidati) == 1:
                conclusione = candidati[0]
                fonte, termine = conclusione["letto"], conclusione["termine"]
                descrizione = termine["computo"]
                if conclusione.get("onerato_codice") == "controparte":
                    descrizione += " Termine della controparte."
                if any(n.get("norma") == "art. 416 c.p.c." for n in conclusione.get("norme") or ()):
                    descrizione += " Costituzione disciplinata dall’art. 416 c.p.c."
                azione = {**azione, "documentId": fonte["documento_id"], "source": fonte.get("documento"),
                          "sourceHref": href_documento(fascicolo_id, fonte["documento_id"]),
                          "dateIso": termine["scadenza_iso"], "date": termine["scadenza"],
                          "title": "Costituzione del convenuto secondo il decreto originario",
                          "description": descrizione}
        elif not registrata and tipo == "termine_documento":
            candidati = termini.get((azione.get("dateIso"), oid), ())
            if len(candidati) == 1:
                conclusione = candidati[0]
                fonte = conclusione["letto"]
                azione = {**azione, "documentId": fonte["documento_id"], "source": fonte.get("documento"),
                          "sourceHref": href_documento(fascicolo_id, fonte["documento_id"]),
                          "title": "Rinnovazione della notifica eseguita", "description": conclusione["prova_o_motivo"]}
        azioni.append(azione)
    if presidio.get("nextAction"):
        presidio["nextAction"] = next(
            (a for a in azioni if a.get("id") == presidio["nextAction"].get("id")),
            azioni[0] if azioni else None,
        )
    presidio["actions"] = azioni


def attivita_da_lettura(corpo: bytes, fascicolo_id: str) -> bytes:
    from web.services.riscontri_processuali_runtime import lettura_consultiva

    dati = json.loads(corpo)
    allinea_attivita_udienze(dati, lettura_consultiva(fascicolo_id))
    return json.dumps(dati, ensure_ascii=False).encode("utf-8")


def allinea_relata_al_riscontro(dati: dict, lettura: dict | None, fascicolo_id: str) -> None:
    from urllib.parse import quote

    from pct.formatting import format_date_it

    monitor = dati.get("notificationRelata")
    if not monitor or monitor.get("releaseDetected") or not lettura or lettura.get("aggiornamento_pendente"):
        return
    riscontri = [
        voce for voce in (lettura.get("ragionamento") or {}).get("conclusioni") or ()
        if voce.get("codice") == "notifica_ordinata" and voce.get("stato") == "fatto" and voce.get("prova_notifica")
    ]
    if not riscontri:
        _mostra_relata_storica(monitor, lettura, fascicolo_id)
        return
    if monitor.get("status") in {"nessuna_notifica", "prova_raccolta", "ricevute_da_completare", "storico_gestito"}:
        ultimo = max(riscontri, key=lambda v: (v.get("termine") or {}).get("scadenza_iso", ""))
        prova = ultimo["prova_notifica"]
        invio = prova["invio_id"]
        monitor.update(status="prova_raccolta", statusLabel="Rinnovazione della notifica documentata", tone="success",
                       notificationAlreadySent=True, proofComplete=True, systemNotification=ultimo["prova_o_motivo"],
                       primaryHref=f"/fascicoli/{quote(fascicolo_id, safe='')}/documenti/{quote(invio, safe='')}/visualizza",
                       primaryLabel="Apri PEC della rinnovazione")
        deposito = prova.get("deposito_inviato")
        dettaglio_prova = "RAC e RdAC collegate all’invio. L’esito del deposito della prova è un riscontro distinto."
        if deposito and not monitor.get("proofDeposited"):
            copia = quote(deposito["copia_in_chiaro_id"], safe="")
            monitor.update(depositHref=f"/fascicoli/{quote(fascicolo_id, safe='')}/documenti/{copia}/visualizza",
                           depositLabel="Apri busta già inviata")
            dettaglio_prova = (
                f"RAC e RdAC già incluse nella busta inviata il {format_date_it(deposito['data'])}. "
                "Consulta l’esito della cancelleria nel registro PCT."
            )
        completati = {
            "acquisizione": "Ricorso e provvedimenti collegati all’invio.",
            "relata": "Relata presente nella PEC di rinnovazione.",
            "firma": "Invio già eseguito.",
        }
        for passo in monitor.get("steps") or ():
            if passo["id"] in completati:
                passo.update(status="superato", detail=completati[passo["id"]])
            elif passo["id"] == "prova":
                passo.update(status="monitorato", detail=dettaglio_prova)


def _mostra_relata_storica(monitor: dict, lettura: dict, fascicolo_id: str) -> None:
    if (lettura.get("fase") or {}).get("codice") != "chiusa" or monitor.get("status") not in {
        "prova_raccolta", "ricevute_da_completare",
    }:
        return

    from urllib.parse import quote

    from web.services.obblighi_notifica_sintesi import leggi
    from web.services.riscontri_processuali_runtime import proietta_riscontri, stati_obblighi_da_lettura

    riscontri = proietta_riscontri(lettura, "notifiche").get("conclusioni") or []
    if not riscontri or any(voce.get("stato") not in {"fatto", "non_dovuto"} for voce in riscontri):
        return
    sintesi = leggi(fascicolo_id) or {}
    obblighi = stati_obblighi_da_lettura(sintesi.get("obblighi") or [], lettura)
    stati = {voce.get("stato") for voce in obblighi}
    if "riscontro_storico" not in stati or stati - {"notificato", "riscontro_storico"}:
        return

    monitor.update(
        status="riscontri_storici", statusLabel="Riscontri storici delle notifiche", tone="info",
        systemNotification="Gli atti e le ricevute restano consultabili. Per la notifica ai fini del termine breve "
                           "vale il riscontro storico esposto nella Lettura.",
        primaryHref=f"/fascicoli/{quote(fascicolo_id, safe='')}#lettura-fascicolo",
        primaryLabel="Apri la Lettura", depositHref="", depositLabel="",
    )
    for passo in monitor.get("steps") or ():
        if passo.get("id") == "firma":
            passo.update(status="monitorato", detail="Consulta la relata e le eventuali firme già archiviate.")
        elif passo.get("id") == "prova":
            passo.update(status="monitorato", detail="Ricevute e relate consultabili tra i documenti monitorati.")


def relata_da_lettura(corpo: bytes, fascicolo_id: str) -> bytes:
    from web.services.riscontri_processuali_runtime import lettura_consultiva

    dati = json.loads(corpo)
    allinea_relata_al_riscontro(dati, lettura_consultiva(fascicolo_id), fascicolo_id)
    return json.dumps(dati, ensure_ascii=False).encode("utf-8")

def redazione_dal_conto(corpo: bytes, fascicolo_id: str) -> bytes:
    """Completa la redazione salvata da fatti già disponibili nelle fonti comuni."""
    from web.services.react_redazione_guidata_bridge import applica_valore_in_redazione, contributo_per_redazione
    from web.services.riscontri_processuali_runtime import contesto_operativo_da_lettura, lettura_materializzata

    dati = json.loads(corpo)
    contesto = dati.get("contesto") or {}
    economia = contesto.get("economia")
    fascicolo = contesto.get("fascicolo")
    if not isinstance(economia, dict):
        return corpo
    valore_senza_fonte = (isinstance(fascicolo, dict) and "valoreCausa" in fascicolo
                          and not (fascicolo.get("valoreCausa") or {}).get("fonte"))
    contributo_mancante = not (economia.get("contributoUnificato") or {}).get("disponibile")
    if not valore_senza_fonte and not contributo_mancante:
        return corpo
    comune = contesto_operativo_da_lettura(lettura_materializzata(fascicolo_id), fascicolo_id)
    cambiato = False
    if contributo_mancante and comune.get("contributo"):
        economia["contributoUnificato"] = contributo_per_redazione(comune["contributo"])
        cambiato = True
    if valore_senza_fonte and comune.get("valore_causa"):
        applica_valore_in_redazione(contesto, comune["valore_causa"])
        cambiato = True
    return json.dumps(dati, ensure_ascii=False).encode("utf-8") if cambiato else corpo
