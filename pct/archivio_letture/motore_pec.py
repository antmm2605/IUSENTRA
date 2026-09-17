"""Il motore PEC: dai messaggi del presidio PEC ai fatti collaudati.

Il presidio PEC (pct/pec_pipeline) ha già letto ogni messaggio: intestazioni
certificate dal gestore, daticert.xml, corpo, allegati con OCR, eventi, termini
e udienze estratti. Questo motore non rilegge la PEC: traduce ciò che il
presidio sa in fatti dell'archivio, con l'origine giusta e il collaudo.
Le ricevute di accettazione e di avvenuta consegna (D.P.R. 68/2005; L.
53/1994 art. 3-bis) si riconoscono dall'oggetto certificato dal gestore.
"""

from __future__ import annotations

import re
from typing import Any

from pct.registro_letture.fatti_repository import Fatto

from .collaudo import Contesto, collauda_tutti
from .motore_documenti import leggi_testo

VERSIONE_MOTORE_PEC = "2026.09.16.motore-pec.v8"
_RICEVUTE = (
    ("rac", "accettazione", re.compile(r"^\s*(?:accettazione|posta certificata:\s*accettazione)\b", re.IGNORECASE)),
    ("rdac", "consegna", re.compile(r"^\s*(?:consegna|avvenuta consegna|posta certificata:\s*(?:avvenuta )?consegna)\b", re.IGNORECASE)),
    ("errore_consegna", "errore_consegna", re.compile(r"^\s*(?:avviso di mancata consegna|mancata consegna|errore di consegna)\b", re.IGNORECASE)),
)
_BASE_NORMATIVA_PEC = (
    "D.P.R. 68/2005 art. 6 e L. 53/1994 art. 3-bis: data certificata e "
    "ricevute PEC nella notifica telematica"
)


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _giorno(valore: Any) -> str:
    return _testo(valore)[:10]


def _ora(valore: Any) -> str:
    testo = _testo(valore)
    return testo[11:16] if len(testo) >= 16 and testo[10] in "T " else ""


def fatti_da_messaggio(messaggio: dict[str, Any], contesto: Contesto) -> list[Fatto]:
    """I fatti di un messaggio del presidio: udienze, termini, eventi, ricevute PEC."""
    ricevuta_il = _giorno(messaggio.get("received_at"))
    oggetto = _testo(messaggio.get("subject"))
    mittente = _testo(messaggio.get("from"))
    fatti: list[Fatto] = []
    for campo, campo_data, espressione in _RICEVUTE:
        if not espressione.search(oggetto):
            continue
        fatti.append(Fatto(
            categoria="prova_notifica", campo=campo, valore=campo, valore_letto=oggetto[:120], etichetta={"rac": "Ricevuta di accettazione", "rdac": "Ricevuta di avvenuta consegna", "errore_consegna": "Avviso di mancata consegna"}[campo],
            contesto=f"{oggetto} — da {mittente}"[:300], origine="pec_intestazioni", confidenza=1.0,
            prove=[
                {"codice": "segnali", "esito": "ok", "dettaglio": "oggetto certificato dal gestore PEC"},
                {"codice": "base_normativa", "esito": "ok", "dettaglio": _BASE_NORMATIVA_PEC},
            ],
        ))
        if ricevuta_il and campo != "errore_consegna":
            ora = _ora(messaggio.get("received_at"))
            fatti.append(Fatto(
                categoria="data", campo=campo_data, valore=ricevuta_il + (f"T{ora}" if ora else ""), valore_letto=_testo(messaggio.get("received_at"))[:25],
                etichetta=f"{'Accettazione' if campo == 'rac' else 'Avvenuta consegna'} del {ricevuta_il[8:10]}/{ricevuta_il[5:7]}/{ricevuta_il[:4]}" + (f" ore {ora}" if ora else ""),
                contesto=oggetto[:300], origine="pec_intestazioni", confidenza=1.0,
                prove=[
                    {"codice": "calendario", "esito": "ok", "dettaglio": "data di ricezione certificata"},
                    {"codice": "ancoraggio", "esito": "ok", "dettaglio": "oggetto della ricevuta"},
                    {"codice": "base_normativa", "esito": "ok", "dettaglio": _BASE_NORMATIVA_PEC},
                ],
            ))
    udienze = list(messaggio.get("udienze") or [])
    profile = messaggio.get("procedural_profile") or {}
    descrizione_evento = _testo(profile.get("descrizione_evento"))
    proposta = messaggio.get("deadline_proposal") or {}
    data_proposta = proposta.get("detected_procedural_date") or {}
    note_xml = bool(re.search(r"(?:FISSATO|RIASSEGNATO) TERMINE PER NOTE IN SOSTITUZIONE UDIENZA", descrizione_evento, re.I)) and "Comunicazione.xml" in str(data_proposta.get("source") or "") and bool(messaggio.get("collegata"))
    if note_xml and not udienze and data_proposta.get("date"):
        udienze = [{"hearing_date": data_proposta["date"], "hearing_time":"", "mode":"note_scritte", "human_review_required":False}]
    for udienza in udienze:
        giorno = _giorno(udienza.get("hearing_date"))
        if not giorno:
            continue
        scritta = _testo(udienza.get("mode")) in {"note_scritte", "trattazione scritta"}
        ora = "" if scritta else _testo(udienza.get("hearing_time"))[:5]
        rivedere = bool(udienza.get("human_review_required"))
        fatti.append(Fatto(
            categoria="data", campo="termine" if scritta else "udienza", valore=giorno + (f"T{ora}" if ora else ""), valore_letto=giorno, etichetta=("Deposito note in sostituzione udienza del " if scritta else "Udienza del ") + f"{giorno[8:10]}/{giorno[5:7]}/{giorno[:4]}" + (f" ore {ora}" if ora else "") + (f" ({_testo(udienza.get('mode'))})" if _testo(udienza.get("mode")) else ""),
            contesto=(descrizione_evento if note_xml else f"{'Termine per note scritte' if scritta else 'Udienza'} comunicato con la PEC «{oggetto}» del {ricevuta_il}")[:300], origine="presidio_pec", confidenza=0.7 if rivedere else 0.95,
            prove=[{"codice": "ancoraggio", "esito": "ok", "dettaglio": "udienza estratta dal presidio PEC"}, {"codice": "forma", "esito": "attenzione" if rivedere else "ok", "dettaglio": "da rivedere per il presidio" if rivedere else "nessuna correzione"}],
        ))
    for termine in list(messaggio.get("termini") or []):
        giorno = _giorno(termine.get("dies_a_quo_date"))
        if not giorno:
            continue
        tipo = _testo(termine.get("deadline_type")).replace("_", " ")
        norma = _testo(termine.get("norm_ref"))
        rivedere = bool(termine.get("human_review_required"))
        prove = [
            {"codice": "ancoraggio", "esito": "ok", "dettaglio": "termine estratto dal presidio PEC"},
            {"codice": "forma", "esito": "attenzione" if rivedere else "ok", "dettaglio": "da rivedere per il presidio" if rivedere else "nessuna correzione"},
        ]
        if norma:
            prove.append({"codice": "base_normativa", "esito": "ok", "dettaglio": f"riferimento indicato dal presidio: {norma}"})
        fatti.append(Fatto(
            categoria="data", campo="decorrenza", valore=giorno, valore_letto=giorno, etichetta=f"Decorrenza del termine {tipo} dal {giorno[8:10]}/{giorno[5:7]}/{giorno[:4]}" + (f" ({_testo(termine.get('norm_ref'))})" if _testo(termine.get("norm_ref")) else ""),
            contesto=f"termine {tipo} dalla PEC «{oggetto}» del {ricevuta_il}"[:300], origine="presidio_pec", confidenza=0.7 if rivedere else 0.95,
            prove=prove,
        ))
    for evento in list(messaggio.get("eventi") or []):
        evento = dict(evento)
        if note_xml:
            evento.update(primary_event="riassegnazione_note" if "RIASSEGNATO" in descrizione_evento.upper() else "fissazione_note", human_review_required=False)
        primario = _testo(evento.get("primary_event"))
        if not primario:
            continue
        # L'evento porta con sé il giorno della PEC che lo comunica: senza data
        # resterebbe un dato senza posto nel tempo, e la cronologia non potrebbe
        # mostrarlo. La data certa è quella di ricezione (D.P.R. 68/2005 art. 6).
        fatti.append(Fatto(
            categoria="evento", campo=primario, valore=_testo(evento.get("family")) or primario, valore_letto=primario, etichetta=primario.replace("_", " "),
            contesto=f"evento della PEC «{oggetto}» del {ricevuta_il}"[:300], origine="presidio_pec", confidenza=0.7 if evento.get("human_review_required") else 0.95,
            verifica="plausibile" if evento.get("human_review_required") else "verificata",
            prove=[
                {"codice": "classificazione", "esito": "ok", "dettaglio": f"priorità {_testo(evento.get('priority')) or 'n.d.'}"},
                {"codice": "data", "esito": "ok" if ricevuta_il else "attenzione", "dettaglio": ricevuta_il or "PEC senza data di ricezione"},
                {"codice": "base_normativa", "esito": "ok", "dettaglio": _BASE_NORMATIVA_PEC},
            ],
        ))
    contesto_pec = Contesto(oggi=contesto.oggi, anno_riferimento=contesto.anno_riferimento, data_minima=contesto.data_minima, numero_rg=contesto.numero_rg, anno_rg=contesto.anno_rg, date_note=contesto.date_note)
    ricevuta = None
    try:
        from pct.registro_letture.verifica_date import interpreta_data

        ricevuta = interpreta_data(ricevuta_il)
    except Exception:
        ricevuta = None
    if ricevuta is not None:
        # Un'udienza o una decorrenza comunicate con una PEC non possono precederla.
        contesto_pec.data_minima = max(filter(None, [contesto.data_minima, ricevuta]))
    collaudati = collauda_tutti(fatti, contesto_pec)
    from .termini_pec import scadenza_proposta
    if messaggio.get("event_type") != "pct_deposito":
        for termine in messaggio.get("termini") or []:
            proposta_termine = scadenza_proposta(termine)
            if proposta_termine is not None:
                collaudati.append(proposta_termine)
    lifecycle = messaggio.get("deposit_lifecycle") or {}
    stage = lifecycle.get("current_stage") or {}
    correlation = lifecycle.get("correlation") or {}
    receipt = lifecycle.get("receipt") or {}
    deposito_id = messaggio.get("archive_deposito_id")
    final = stage.get("id") in {"accettazione_deposito", "rifiuto_deposito"}
    if deposito_id and stage.get("id") and (not final or receipt.get("outcome_code") is not None):
        collaudati.append(Fatto(
            categoria="evento", campo="esito_deposito", valore=str(deposito_id),
            etichetta=str(stage.get("label") or "Ricevuta deposito"),
            contesto="Ricevuta collegata all'invio mediante gli identificativi originali.",
            origine="pec_identificativi", confidenza=1.0, verifica="verificata",
            prove=[{"codice":"correlazione_ricevuta", "esito":"ok", "deposito_id":deposito_id,
                    "message_id":messaggio.get("id"), "mime_sha256":messaggio.get("mime_sha256"),
                    "receipt_message_id":messaggio.get("header_message_id"),
                    "stage":stage.get("id"), "label":stage.get("label"),
                    "idbusta":correlation.get("idbusta"), "source_message_id":correlation.get("source_message_id"),
                    "occurred_at":receipt.get("occurred_at") or messaggio.get("received_at"),
                    "outcome_code":receipt.get("outcome_code"), "reference":messaggio.get("archive_receipt_reference") or {}}]))
    return collaudati


def fatti_da_allegato(testo: str, *, nome: str, contesto: Contesto) -> list[Fatto]:
    """Gli allegati PEC letti dal presidio (OCR) passano dal motore documenti con origine «pec_allegato»."""
    return leggi_testo(testo, origine="pec_allegato", contesto=contesto, nome=nome)


__all__ = ["VERSIONE_MOTORE_PEC", "fatti_da_allegato", "fatti_da_messaggio"]
