"""Gli obblighi di notifica del fascicolo, dai documenti catalogati e dall'archivio delle letture.

Raccoglie senza leggere nulla: le voci del catalogo documentale (quale atto è
ogni documento), le date e le parti dell'archivio delle letture, le prove di
notifica già lette. Le regole e le norme sono in `pct.obblighi_notifica`.

Un obbligo «da notificare» con una scadenza futura entra nello scadenziario
una volta sola (il riferimento resta nella nota), come proposta da confermare.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from pct.obblighi_notifica import STATO_DA_NOTIFICARE, DocumentoCatalogato, Parte, obblighi_del_fascicolo
from pct.ora_italiana import oggi_roma

logger = logging.getLogger(__name__)

MARCATORE = "OBBLIGO_NOTIFICA:"
_ETICHETTA_RICORSO_DI = "ricorso per decreto ingiuntivo"


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _dettaglio(fatto: Any, codice: str) -> str:
    return next((str(p.get("dettaglio") or "") for p in list(getattr(fatto, "prove", []) or []) if p.get("codice") == codice), "")


def _catalogo(fascicolo: Any) -> dict[str, str]:
    """document_id → voce del catalogo (proposte e conferme; mai le voci respinte)."""
    try:
        from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id

        assegnazioni = build_document_ai_service().repository.list_catalog_assignments(document_ai_tenant_id(), _testo(fascicolo.id))
    except Exception:
        logger.debug("Catalogo non disponibile per gli obblighi di notifica di %s", getattr(fascicolo, "id", ""), exc_info=True)
        return {}
    return {_testo(a.document_id): _testo(a.document_label) for a in assegnazioni if _testo(a.document_id) and _testo(a.document_label)}


_VALIDE = {"verificata", "corretta"}
_SCARTATE = {"respinta", "ignorata"}


def prova_notifica(oid: str, elenco: list[Any], etichette: dict[str, str], *, data: str = "") -> dict[str, Any]:
    """La prova di notifica di un documento, con l'atto a cui si riferisce e i destinatari che nomina.

    L'atto è certo solo quando relata e ricevuta di avvenuta consegna stanno nella stessa copia notificata
    dell'atto catalogato (art. 3-bis, comma 3, e art. 9 L. 53/1994: la notifica si perfeziona per il
    destinatario con la ricevuta di avvenuta consegna). Una relata in un file separato non si collega per
    somiglianza: l'obbligo resta aperto con il motivo.
    """
    prove = [f for f in elenco if f.categoria == "prova_notifica" and f.verifica not in _SCARTATE]
    relate = [f for f in prove if f.campo == "relata"]
    consegne = [f for f in prove if f.campo == "rdac"]
    etichetta = etichette.get(oid, "").casefold()
    nella_copia = bool(etichetta) and etichetta != "relata di notifica"
    return {
        "documento_id": oid,
        "data": data,
        "atto": " ".join(_testo(f.contesto)[:200] for f in prove),
        "atto_documento_id": oid if nella_copia and relate else "",
        # Il catalogo che riconosce il documento come relata basta a dire che c'è una relata, non che è verificata.
        "relata": bool(relate) or etichetta == "relata di notifica",
        "consegna": bool(consegne),
        "verificata": any(f.verifica in _VALIDE for f in relate) and any(f.verifica in _VALIDE for f in consegne),
        "destinatari": sorted({_testo(f.valore) for f in elenco if f.categoria == "parte"
                               and f.campo in {"controparte", "controinteressato"} and f.verifica not in _SCARTATE}),
    }


def _impronte_testo_atti(documenti: dict[str, Any], fatti: list[Any]) -> dict[str, str]:
    identita = {}
    for oid, originale in documenti.items():
        impronte = {_testo(getattr(originale, campo, "")) for campo in ("hash_sha256", "hash_contenuto_sha256")}
        candidati = {f.valore for f in fatti if f.oggetto_id == oid and f.campo == "impronta_testo_atto"
                     and f.verifica in {"verificata", "corretta"} and f.sha256 and f.sha256 in impronte}
        if len(candidati) == 1:
            identita[oid] = next(iter(candidati))
    return identita


def _qualifica_prove_storiche(prove, fatti, documenti) -> None:
    """Un riscontro degli EML prova la consegna, mentre la validità va verificata."""
    impronte = {
        _testo(d.id): _testo(getattr(d, "hash_sha256", "")).lower()
        for d in documenti
    }
    identita = _impronte_testo_atti({_testo(d.id): d for d in documenti}, fatti)
    for fatto in fatti:
        if fatto.campo != "riscontro_notifica_pec_storica" or fatto.verifica not in {"plausibile", "verificata", "corretta"}:
            continue
        for riscontro in fatto.prove:
            eml = riscontro.get("impronte_eml") or {}
            if fatto.oggetto_id not in eml or any(not h or impronte.get(oid) != h for oid, h in eml.items()):
                continue
            allegati = set(riscontro.get("impronte_allegati") or ())
            consegne = riscontro.get("consegne") or ()
            giorno = str(riscontro.get("accettazione_data") or "")[:10]
            giorni = {giorno, *(str(consegna.get("data") or "")[:10] for consegna in consegne)} - {""}
            if not giorno or not consegne:
                continue
            identita_allegate = {identita[oid] for oid, h in impronte.items() if h in allegati and oid in identita}
            for prova in prove:
                atto_id = prova.get("atto_documento_id")
                if ((impronte.get(atto_id) in allegati or identita.get(atto_id) in identita_allegate)
                        and (prova.get("documento_id") in eml or str(prova.get("data") or "")[:10] in giorni)):
                    prova.update(
                        verificata=False,
                        limite_verifica_storica=(
                            f"Invio del {giorno[8:10]}/{giorno[5:7]}/{giorno[:4]} e ricevute PEC correlate all'atto. "
                            "Prima di usare la data per il termine breve, verificare la relata, "
                            "gli indirizzi nei pubblici elenchi alla data dell'invio e lo stato storico dei certificati "
                            "(art. 3-bis L. 53/1994)."
                        ),
                    )


def raccogli(fascicolo: Any, fatti: list[Any], etichette: dict[str, str],
             testi: dict[str, str] | None = None) -> tuple[list[DocumentoCatalogato], list[Parte], dict[str, Any]]:
    """Documenti, parti e contesto per il calcolo, dai soli dati già letti.

    ``testi``: i testi già salvati nell'indice documentale (nessuna lettura di file). Servono a riconoscere:
    il decreto di fissazione del rito del lavoro (art. 415 c.p.c., ``pct.decreto_fissazione_lavoro``), la
    sentenza di un altro procedimento (``pct.atto_della_causa``), l'atto elencato nella relata della notifica
    PEC con le sue ricevute (art. 3-bis L. 53/1994, ``pct.notifica_atto_l53``) e la condanna al pagamento.
    """
    from pct.atto_della_causa import provvedimento_della_causa, ruoli_in_intestazione
    from pct.decreto_fissazione_lavoro import ETICHETTA as ETICHETTA_DECRETO_415
    from pct.decreto_fissazione_lavoro import e_decreto_fissazione_lavoro, udienza_fissata
    from pct.notifica_atto_l53 import notifiche_pec, prove_per_atto
    from pct.notifica_ricorso_lavoro import data_di_pronuncia
    from pct.sentenza_notificata import condanna_al_pagamento

    testi = dict(testi or {})
    from pct.archivio_letture.parti_fascicolo import parti_lette

    oggi = oggi_roma().isoformat()
    per_oggetto: dict[str, list[Any]] = {}
    for fatto in fatti:
        per_oggetto.setdefault(_testo(getattr(fatto, "oggetto_id", "")), []).append(fatto)
    precedenti = {oid for oid, elenco in per_oggetto.items() if any(f.campo == "natura_documentale" and f.valore in {"precedente_giurisprudenziale", "messaggio_pec"} and f.verifica in {"verificata", "corretta"} for f in elenco)}

    def _data(oid: str, *campi: str) -> str:
        for campo in campi:
            date_campo = sorted({_testo(f.valore)[:10] for f in per_oggetto.get(oid, []) if f.categoria == "data" and f.campo == campo and f.verifica in {"verificata", "corretta"}})
            if date_campo:
                return date_campo[0] if len(date_campo) == 1 else ""
        return ""

    def _nostro(oid: str) -> bool | None:
        lati = {_dettaglio(f, "lato") for f in per_oggetto.get(oid, []) if f.categoria == "parte" and f.campo == "assistito" and f.verifica not in {"respinta", "ignorata"}}
        if lati == {"agisce"}:
            return True
        if lati == {"resiste"}:
            return False
        return None

    nomi = {_testo(getattr(d, "id", "")): _testo(getattr(d, "nome", "")) for d in list(getattr(fascicolo, "documenti", []) or [])}
    # Senza la natura documentale (letture di motori precedenti) vale il nome: un provvedimento di un
    # altro ufficio è giurisprudenza prodotta, non un atto della causa da notificare.
    from pct.archivio_letture.pertinenza_documentale import precedenti_del_fascicolo

    precedenti |= precedenti_del_fascicolo(fascicolo)
    etichette = dict(etichette)
    # Il provvedimento di un altro procedimento (allegato come precedente) non genera obblighi: lo dice il ruolo
    # letto nell'intestazione o una data anteriore all'iscrizione a ruolo (pct.atto_della_causa).
    for oid, etichetta in list(etichette.items()):
        if oid in precedenti or oid not in testi or not etichetta.casefold().startswith(("sentenza", "decreto ingiuntivo")):
            continue
        date_firma = {_testo(f.valore)[:10] for f in per_oggetto.get(oid, []) if f.categoria == "data" and f.campo == "data_atto"
                      and f.verifica in {"verificata", "corretta"}}
        esito, _motivo = provvedimento_della_causa(ruoli=ruoli_in_intestazione(testi[oid]), date_atto=date_firma,
                                                   numero_rg=getattr(fascicolo, "numero_rg", ""), anno_rg=getattr(fascicolo, "anno_rg", ""))
        if esito is False:
            precedenti.add(oid)
    # Il decreto di fissazione del rito del lavoro riconosciuto dal contenuto, anche se il catalogo non l'ha
    # classificato: è la fonte dell'obbligo «ricorso e decreto» (art. 415, commi 4 e 5, c.p.c.).
    decreti_415: dict[str, str] = {}
    udienze_415: dict[str, str] = {}
    for oid, testo in testi.items():
        if oid in precedenti or oid not in nomi or etichette.get(oid, "").casefold().startswith(("ricorso", "relata", "notificazione")):
            continue
        if e_decreto_fissazione_lavoro(testo):
            etichette[oid] = ETICHETTA_DECRETO_415
            udienze_415[oid] = udienza_fissata(testo)
            pronuncia = data_di_pronuncia(testo)
            decreti_415[oid] = pronuncia.isoformat() if pronuncia else ""
    lati_studio = {_dettaglio(f, "lato") for oid, elenco in per_oggetto.items() if oid in nomi and oid not in precedenti
                   for f in elenco if f.categoria == "parte" and f.campo == "assistito" and f.verifica not in {"respinta", "ignorata"}}
    documenti: list[DocumentoCatalogato] = []
    for oid, etichetta in etichette.items():
        if oid in precedenti or oid not in nomi:
            continue
        nostro = _nostro(oid)
        if oid in decreti_415 and nostro is None:
            # Il decreto non nomina il lato: vale quello dell'assistito negli atti di parte (ricorrente → è lo studio a notificare).
            nostro = True if lati_studio == {"agisce"} else False if lati_studio == {"resiste"} else None
        udienze = tuple(sorted({_testo(f.valore)[:10] for f in per_oggetto.get(oid, []) if f.categoria == "data" and f.campo == "udienza" and f.verifica in {"verificata", "corretta"}}))
        if oid in udienze_415:
            udienze = (udienze_415[oid],) if udienze_415[oid] else udienze
        data_atto = decreti_415.get(oid) or _data(oid, "provvedimento", "data_atto")
        documenti.append(DocumentoCatalogato(id=oid, nome=nomi[oid], etichetta=etichetta, data=data_atto, nostro=nostro, udienze=udienze))

    parti: list[Parte] = []
    # Contumace se una qualsiasi lettura della parte lo dice (di solito l'epigrafe della sentenza: «convenuto (contumace)»).
    contumaci = {" ".join(sorted(_testo(f.valore).casefold().split())) for f in fatti
                 if f.categoria == "parte" and "contumac" in _testo(getattr(f, "contesto", "")).casefold()
                 and f.verifica not in {"respinta", "ignorata"}}
    for voce in parti_lette(fatti):
        ruolo = "controinteressato" if "controinteressat" in voce.posizione.casefold() else voce.ruolo
        contumace = (" ".join(sorted(voce.nome.casefold().split())) in contumaci
                     or "contumac" in f"{voce.posizione} {getattr(voce, 'citazione', '')}".casefold())
        parti.append(Parte(nome=voce.nome, ruolo=ruolo, difensore=voce.difensore, posizione=voce.posizione,
                           documenti=tuple(getattr(voce, "oggetti", ()) or ()), contumace=contumace))
    if not any(p.ruolo in {"controparte", "controinteressato"} for p in parti) and _testo(getattr(fascicolo, "controparte", "")):
        parti.append(Parte(nome=_testo(fascicolo.controparte), ruolo="controparte", difensore=_testo(getattr(fascicolo, "avvocato_controparte", ""))))

    # Le notificazioni PEC (art. 3-bis L. 53/1994): la prova è dell'atto elencato nella relata, con le ricevute
    # della stessa spedizione. I documenti della spedizione non sono più «prove senza atto» del fascicolo.
    candidati = {oid: testo for oid, testo in testi.items() if oid in nomi}
    spedizioni = notifiche_pec(candidati, nomi)
    date_atti = {d.id: d.data for d in documenti}
    prove = [p for p in prove_per_atto(spedizioni, nomi, date_atti) if p["atto_documento_id"] not in precedenti]
    delle_spedizioni = {oid for spedizione in spedizioni for oid in spedizione.documenti if spedizione.atti}
    for oid, elenco in per_oggetto.items():
        if oid in delle_spedizioni:
            continue
        if any(f.categoria == "prova_notifica" and f.campo in {"relata", "rdac"} for f in elenco) or etichette.get(oid, "").casefold() == "relata di notifica":
            prove.append(prova_notifica(oid, elenco, etichette, data=_data(oid, "notifica", "data_atto")))
    # Termine breve di impugnazione (art. 325 c.p.c.; art. 92 c.p.a.): solo se nel fascicolo c'è una sola
    # copia notificata di sentenza, con relata e consegna, e la data della notificazione è letta e univoca.
    _qualifica_prove_storiche(
        [p for p in prove if etichette.get(str(p.get("atto_documento_id")), "").casefold() == "sentenza"],
        fatti, getattr(fascicolo, "documenti", ()) or (),
    )
    notifiche_sentenza = {str(prova.get("data") or "")[:10] or _data(prova["documento_id"], "notifica") for prova in prove
                          if prova.get("verificata") and prova.get("atto_documento_id")
                          and etichette.get(str(prova["atto_documento_id"]), "").casefold() == "sentenza"
                          and prova["atto_documento_id"] not in precedenti} - {""}
    try:
        anno_ruolo = int(getattr(fascicolo, "anno_rg", 0) or 0)
    except (TypeError, ValueError):
        anno_ruolo = 0
    contesto = {
        "notifica_sentenza": next(iter(notifiche_sentenza)) if len(notifiche_sentenza) == 1 else "",
        "udienze_future": sorted({_testo(f.valore)[:10] for f in fatti if f.categoria == "data" and f.campo == "udienza" and f.verifica in {"verificata", "corretta"} and f.oggetto_id in nomi and f.oggetto_id not in precedenti and _testo(f.valore)[:10] >= oggi}),
        "date_sentenze": [d.data for d in documenti if d.etichetta.casefold() == "sentenza" and d.data],
        "data_provvedimento_impugnato": next((d.data for d in documenti if d.etichetta.casefold() == "provvedimento amministrativo" and d.data), ""),
        "prove_notifica": prove,
        # La fase del procedimento (pct.obblighi_notifica_atto): sentenza nel fascicolo, udienze già
        # tenute, fascicolo definito. Solo dati già letti e verificati, mai dai precedenti prodotti.
        # Una sentenza datata prima dell'anno di iscrizione a ruolo non è la decisione di questo procedimento.
        "sentenze": [d.id for d in documenti if d.etichetta.casefold().startswith("sentenza") and "precedente" not in d.etichetta.casefold()
                     and not (anno_ruolo and d.data and d.data[:4].isdigit() and int(d.data[:4]) < anno_ruolo)],
        "udienze_tenute": sorted({_testo(f.valore)[:10] for f in fatti if f.categoria == "data" and f.campo == "udienza" and f.verifica in {"verificata", "corretta"} and f.oggetto_id in nomi and f.oggetto_id not in precedenti and _testo(f.valore)[:10] < oggi}),
        "fascicolo_definito": _testo(getattr(getattr(fascicolo, "stato", ""), "value", getattr(fascicolo, "stato", ""))).upper() in {"DEFINITO", "ARCHIVIATO"},
        "nomi_documenti": nomi,
        "documenti_atti": [d.id for d in documenti if d.etichetta.casefold() != "relata di notifica"],
        "decreti_collegati": {oid: data for oid, data in decreti_415.items() if data},
        # Rito del lavoro: niente sospensione feriale (art. 3 L. 742/1969), appello con ricorso (art. 434 c.p.c.).
        "rito_lavoro": _rito_lavoro(fascicolo, etichette),
        "condanne_al_pagamento": {d.id: condanna_al_pagamento(testi.get(d.id, "")) for d in documenti
                                  if d.etichetta.casefold() == "sentenza" and d.id in testi},
    }
    return documenti, parti, contesto


def _rito_lavoro(fascicolo: Any, etichette: dict[str, str]) -> bool:
    """Controversia di lavoro, previdenza o pubblico impiego (artt. 409 e 442 c.p.c.): tipo del fascicolo o atti del rito."""
    tipo = _testo(getattr(getattr(fascicolo, "tipo", ""), "value", getattr(fascicolo, "tipo", ""))).upper()
    if tipo in {"LAVORO", "PREVIDENZA"}:
        return True
    return any("art. 414" in e or "art. 415" in e for e in etichette.values())


def _testi_salvati(fascicolo: Any) -> dict[str, str]:
    try:
        from web.services.archivio_letture_runtime import testi_indice_archivio

        return testi_indice_archivio(fascicolo)
    except Exception:
        logger.debug("Testi salvati non disponibili per gli obblighi di notifica di %s", getattr(fascicolo, "id", ""), exc_info=True)
        return {}


def obblighi_fascicolo(fascicolo: Any) -> list[dict[str, Any]]:
    from web.services.archivio_letture_runtime import fatti_fascicolo

    fatti = fatti_fascicolo(fascicolo, canonico=False)
    documenti, parti, contesto = raccogli(fascicolo, fatti, _catalogo(fascicolo), _testi_salvati(fascicolo))
    from web.services.verifica_notifiche_contesto import repository

    verifiche = repository().elenco(str(fascicolo.id))
    verifiche_registrate = verifiche
    from pct.archivio_letture.verifiche_atti import verifiche_per_atto
    documenti_attuali = {str(d.id): d for d in fascicolo.documenti}
    identita = _impronte_testo_atti(documenti_attuali, fatti)
    verifiche, revisioni = verifiche_per_atto(documenti_attuali, identita, verifiche)
    ufficio = _testo(getattr(fascicolo, "tribunale", "")) or _testo(getattr(fascicolo, "ufficio_giudiziario", ""))
    esito = []
    for documento in documenti:
        verificata = verifiche.get(documento.id, {})
        locale = dict(contesto)
        if verificata:
            documento = replace(documento, nostro=verificata["atto_studio"],
                                udienze=(verificata["udienza"],) if verificata.get("udienza") else documento.udienze)
            locale.update(notifica_estero=verificata["notifica_estero"], sospensione_feriale=verificata["sospensione_feriale"])
            locale["decreti_collegati"] = {**dict(contesto.get("decreti_collegati") or {}),
                                           **({documento.id: verificata["pronuncia_decreto"]} if verificata.get("pronuncia_decreto") else {})}
            locale["pubblicazioni_verificate"] = {documento.id: verificata.get("pubblicazione", "")}
            locale["conoscenze_verificate"] = {documento.id: verificata.get("conoscenza", "")}
        for obbligo in obblighi_del_fascicolo([documento], parti, ufficio=ufficio, contesto=locale):
            item = obbligo.to_dict()
            item["contesto_verificato"] = verificata
            if documento.id in revisioni:
                item.update(scadenza="", calcoli=[], stato="da_verificare", motivo=revisioni[documento.id])
                item["dati_mancanti"].append({"campo": "verifica_attuale", "documento_id": documento.id, "descrizione": revisioni[documento.id]})
                # La revisione resta quella SQL anche quando i vecchi valori
                # non sono utilizzabili: la nuova conferma deve poter passare
                # il controllo di concorrenza senza riproporre date obsolete.
                precedente = verifiche_registrate.get(documento.id, {})
                item["contesto_verificato"] = {"revisione": precedente.get("revisione", 0),
                                              "verifica_documento_id": documento.id}
            if verificata and not verificata["regime_corrente"]:
                item.update(scadenza="", calcoli=[], stato="da_verificare", motivo="Regime precedente o speciale: verifica la norma applicabile prima di calcolare.")
            esito.append(item)
    from pct.archivio_letture.copie_atti import riunisci_obblighi
    from pct.obblighi_notifica_atto import una_voce_per_atto
    from web.services.precedenti_notifica_runtime import annota_fascicolo
    return annota_fascicolo(fascicolo, una_voce_per_atto(riunisci_obblighi(esito, identita), contesto))


def allinea_scadenze(fascicolo: Any, obblighi: list[dict[str, Any]] | None = None) -> dict[str, int]:
    """Gli obblighi da notificare con scadenza futura diventano scadenze da confermare, una volta sola."""
    from pct.scadenziario import StatoTermine, TipoTermine
    from web.helpers import get_scadenziario

    obblighi = obblighi if obblighi is not None else obblighi_fascicolo(fascicolo)
    gestore = get_scadenziario()
    fid = _testo(fascicolo.id)
    esistenti = {}
    for scadenza in gestore.tutte(id_fascicolo=fid, solo_aperte=False):
        for riga in str(getattr(scadenza, "note", "") or "").splitlines():
            riga = riga.strip()
            if riga.startswith(MARCATORE):
                esistenti.setdefault(riga, []).append(scadenza)
    conteggi = {"creati": 0, "esistenti": 0, "aggiornati": 0, "da_verificare": 0}
    oggi = oggi_roma().isoformat()
    for obbligo in obblighi:
        if obbligo["stato"] != STATO_DA_NOTIFICARE or obbligo.get("dati_mancanti") or not obbligo["scadenza"] or obbligo["scadenza"] < oggi:
            continue
        marcatore = MARCATORE + obbligo["chiave"]
        marcatori = [marcatore, *(MARCATORE + fonte["chiave"] for fonte in obbligo.get("fonti_documentali", []))]
        destinatari = "; ".join(f"{d['nome']} {d['presso']}" for d in obbligo["destinatari"]) or "controparte da individuare"
        nota = (f"Obbligo di notifica letto dal documento «{obbligo['documento']}». Destinatari: {destinatari}. "
                f"Termine: {obbligo['formula']}. Fonti: {', '.join(obbligo['fonti'])}. Da confermare.\n{marcatore}")
        campi = dict(
            titolo=f"Notificare {obbligo['atti']}"[:120],
            tipo=TipoTermine.TERMINE_PERENTORIO if obbligo["natura"] == "perentorio" else TipoTermine.ADEMPIMENTO,
            data_scadenza=obbligo["scadenza"],
            descrizione=(obbligo["avvertenze"] or obbligo["formula"])[:300],
            perentorio=obbligo["natura"] == "perentorio",
        )
        trovate = {s.id: s for m in marcatori for s in esistenti.get(m, [])}
        if trovate:
            conteggi["esistenti"] += 1
            if len(trovate) != 1:
                conteggi["da_verificare"] += 1
                continue
            corrente = next(iter(trovate.values()))
            if corrente.data_scadenza == campi["data_scadenza"]:
                continue
            if corrente.stato != StatoTermine.BOZZA:
                conteggi["da_verificare"] += 1
                continue
            note_correnti = corrente.note.rstrip()
            rettifica = f"Termine ricalcolato: {corrente.data_scadenza} → {campi['data_scadenza']}. {obbligo['formula']}"
            gestore.aggiorna(corrente.id, **campi, note=f"{note_correnti}\n{rettifica}")
            conteggi["aggiornati"] += 1
            continue
        nuova = gestore.nuova(**campi, id_fascicolo=fid, note=nota, stato=StatoTermine.BOZZA)
        esistenti[marcatore] = [nuova]
        conteggi["creati"] += 1
    return conteggi


__all__ = ["MARCATORE", "allinea_scadenze", "obblighi_fascicolo", "prova_notifica", "raccogli"]
