"""Adeguata verifica dalla scheda del cliente (oltre all'intake CRM).

Stesso motore di ``pct.antiriciclaggio`` (D.Lgs. 231/2007 artt. 17-25, 31-32, 35, 42; Regole tecniche
CNF 20/09/2019): qui la scheda si apre, si aggiorna e si conferma dal cliente, con la griglia dei
punteggi modificabile, il documento d'identità (art. 19 c. 1 lett. a), la valutazione della
segnalazione di operazione sospetta (art. 35, portale Infostat-UIF: IUSENTRA non invia nulla) e
l'obbligo di astensione (art. 42). Il fascicolo antiriciclaggio si esporta in PDF.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pct.antiriciclaggio import (
    ETICHETTE_PUNTEGGIO,
    PRESTAZIONE_DIFENSIVA,
    PRESTAZIONI_IN_AMBITO,
    LivelloVerifica,
    MacroArea,
)

ETICHETTE_STATO = {"BOZZA": "In compilazione", "COMPLETATA": "Completata", "DA_RINNOVARE": "Da rinnovare",
                   "FUORI_AMBITO": "Fuori ambito (difesa in giudizio)"}
SOS = {"": "Non valutata", "non_ricorre": "Non ricorrono sospetti", "in_valutazione": "In valutazione",
       "segnalata": "Segnalata alla UIF"}
TIPI_DOCUMENTO = ("carta_identita", "passaporto", "patente", "permesso_soggiorno", "altro")


def _testo(valore: Any, massimo: int = 500) -> str:
    return " ".join(str(valore or "").split())[:massimo]


def _data(valore: Any) -> str:
    try:
        return date.fromisoformat(str(valore or "").strip()[:10]).isoformat()
    except ValueError:
        return ""


def _flag(valore: Any) -> bool:
    return str(valore or "").strip().lower() in {"1", "true", "si", "sì", "on"}


def scheda(verifica: Any, oggi: date | None = None) -> dict[str, Any]:
    dati = verifica.to_dict()
    giorno = oggi or date.today()
    scadenza_doc = _data(dati.get("documento_scadenza"))
    dati.update({
        "stato_etichetta": ETICHETTE_STATO.get(verifica.stato, verifica.stato),
        "prestazione_etichetta": PRESTAZIONI_IN_AMBITO.get(verifica.prestazione, "Difesa in giudizio (art. 17 c. 7)"
                                                           if verifica.prestazione == PRESTAZIONE_DIFENSIVA else verifica.prestazione),
        "documento_scaduto": bool(scadenza_doc and scadenza_doc < giorno.isoformat()),
        "sos_etichetta": SOS.get(str(dati.get("sos_valutazione") or ""), "Non valutata"),
        "promemoria": promemoria(verifica, giorno),
    })
    return dati


def promemoria(verifica: Any, oggi: date) -> list[str]:
    """Obblighi da ricordare all'avvocato: non decide nulla al suo posto."""
    messaggi: list[str] = []
    if not verifica.in_ambito:
        return ["Difesa o consulenza collegata a un procedimento giudiziario: fuori dagli obblighi di adeguata verifica "
                "(art. 17 c. 7 D.Lgs. 231/2007)."]
    scadenza_doc = _data(getattr(verifica, "documento_scadenza", ""))
    if not getattr(verifica, "documento_numero", ""):
        messaggi.append("Identifica il cliente con un documento d'identità valido e conservane copia (art. 19 c. 1 lett. a).")
    elif scadenza_doc and scadenza_doc < oggi.isoformat():
        messaggi.append("Il documento d'identità registrato è scaduto: acquisiscine uno valido.")
    livello = verifica.livello_scelto or verifica.livello_suggerito().value
    if livello == LivelloVerifica.RAFFORZATA.value or verifica.cliente_pep or verifica.paese_alto_rischio:
        messaggi.append("Rischio elevato: verifica rafforzata (artt. 24-25) e valutazione della segnalazione di operazione "
                        "sospetta alla UIF tramite il portale Infostat-UIF (art. 35), senza avvisare il cliente (art. 39).")
    if not getattr(verifica, "sos_valutazione", ""):
        messaggi.append("Registra l'esito della valutazione sulla segnalazione di operazione sospetta (art. 35).")
    if getattr(verifica, "impossibile_completare", False):
        messaggi.append("Se non puoi completare l'adeguata verifica devi astenerti dall'incarico e valutare la "
                        "segnalazione (art. 42 D.Lgs. 231/2007).")
    if verifica.stato == "DA_RINNOVARE":
        messaggi.append("Controllo costante scaduto: riesamina la scheda (art. 18 c. 1 lett. d).")
    return messaggi


def campi_da_richiesta(dati: dict[str, Any], attuale: Any = None) -> dict[str, Any]:
    """Campi modificabili della scheda, validati. Gli indici restano nella griglia CNF (1-5)."""
    campi: dict[str, Any] = {}
    prestazione = _testo(dati.get("prestazione") or getattr(attuale, "prestazione", ""), 60)
    if prestazione not in (*PRESTAZIONI_IN_AMBITO, PRESTAZIONE_DIFENSIVA):
        raise ValueError("Prestazione antiriciclaggio non riconosciuta.")
    campi["prestazione"] = prestazione
    for chiave, sorgente, massimo in (("scopo_natura", "scopoNatura", 500), ("descrizione_prestazione", "descrizionePrestazione", 500),
                                      ("note", "note", 2000), ("documento_numero", "documentoNumero", 40),
                                      ("documento_rilasciato_da", "documentoRilasciatoDa", 120), ("sos_note", "sosNote", 2000)):
        valore = dati.get(sorgente, dati.get(chiave))
        campi[chiave] = _testo(valore, massimo) if valore is not None else _testo(getattr(attuale, chiave, ""), massimo)
    if not campi["scopo_natura"]:
        raise ValueError("Indica scopo e natura del rapporto (art. 18 c. 1 lett. c).")
    tipo_doc = _testo(dati.get("documentoTipo", getattr(attuale, "documento_tipo", "")), 30)
    if tipo_doc and tipo_doc not in TIPI_DOCUMENTO:
        raise ValueError("Tipo di documento non riconosciuto.")
    campi["documento_tipo"] = tipo_doc
    for chiave, sorgente in (("documento_data_rilascio", "documentoDataRilascio"), ("documento_scadenza", "documentoScadenza"),
                             ("sos_data", "sosData")):
        campi[chiave] = _data(dati.get(sorgente, getattr(attuale, chiave, "")))
    sos = _testo(dati.get("sosValutazione", getattr(attuale, "sos_valutazione", "")), 30)
    if sos not in SOS:
        raise ValueError("Esito della valutazione non riconosciuto.")
    campi["sos_valutazione"] = sos
    for chiave, sorgente in (("cliente_pep", "clientePep"), ("paese_alto_rischio", "paeseAltoRischio"),
                             ("impossibile_completare", "impossibileCompletare")):
        campi[chiave] = _flag(dati[sorgente]) if sorgente in dati else bool(getattr(attuale, chiave, False))
    titolare = dati.get("titolareEffettivo")
    if isinstance(titolare, dict):
        campi["titolare_effettivo"] = {k: _testo(titolare.get(k), 200) for k in ("nome", "codice_fiscale", "criterio", "note")}
    indici = dati.get("indici")
    if isinstance(indici, list):
        validi = []
        aree = {m.value for m in MacroArea}
        for riga in indici[:30]:
            if not isinstance(riga, dict) or str(riga.get("macro_area")) not in aree:
                raise ValueError("Indice di rischio non valido.")
            try:
                punteggio = int(riga.get("punteggio"))
            except (TypeError, ValueError):
                raise ValueError("Il punteggio di ogni indice va da 1 a 5.") from None
            if punteggio not in ETICHETTE_PUNTEGGIO:
                raise ValueError("Il punteggio di ogni indice va da 1 a 5.")
            validi.append({"macro_area": riga["macro_area"], "descrizione": _testo(riga.get("descrizione"), 300),
                           "punteggio": punteggio, "note": _testo(riga.get("note"), 500)})
        campi["indici"] = validi
    return campi


__all__ = ["SOS", "TIPI_DOCUMENTO", "campi_da_richiesta", "promemoria", "scheda"]
