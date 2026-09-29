"""Preparazione udienza: scheda della singola udienza, salvataggi dei passi ed esito.

L'esito non resta una nota: il rinvio diventa un'udienza in agenda (e la data della prossima
udienza del fascicolo), i termini assegnati dal giudice diventano scadenze del fascicolo e
l'udienza tenuta diventa un'attività del fascicolo. Nulla si crea due volte.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from urllib.parse import quote

from pct.controllo_studio.fonti import rif_fascicolo
from pct.udienze.preparazione import ESITI, STATI_DOCUMENTO, passi, quando, stato_etichetta
from pct.udienze.tipi import AVVISO_ASSENZA, TIPI, catalogo, fonte, verifiche

CAMPI_PASSO = {
    1: ("step1_note",),
    3: ("note_preparazione", "argomenti_principali", "richieste_giudice", "eccezioni_da_sollevare"),
    4: ("precheck_firma_ok", "precheck_docs_pronti", "precheck_cliente_notificato", "precheck_trasporto_ok", "precheck_note"),
}
_ESITO_ATTIVITA = {"favorevole": "FAVOREVOLE", "parziale": "PARZIALE", "sfavorevole": "SFAVOREVOLE", "rinvio": "RINVIATO"}


def dettaglio(sessione: Any, *, agenda: Any, fascicoli: Any, scadenziario: Any, oggi: date) -> dict[str, Any]:
    fascicolo = fascicoli.get(sessione.id_fascicolo)
    app = agenda.get(sessione.id_appuntamento) if sessione.id_appuntamento else None
    data_ora = str(getattr(app, "data_ora", "") or getattr(fascicolo, "data_prossima_udienza", "") or "")
    termini = sorted((s for s in scadenziario.tutte(solo_aperte=True) if s.id_fascicolo == sessione.id_fascicolo),
                     key=lambda s: s.data_scadenza or "")[:8]
    attivita = sorted(getattr(fascicolo, "attivita", []) or [], key=lambda a: a.data or "", reverse=True)[:4]
    documenti = {str(d.id): d for d in (getattr(fascicolo, "documenti", []) or [])}
    remoto = str(getattr(app, "remote_hearing_url", "") or "")
    return {
        "ok": True, "id": sessione.id, "titolo": sessione.titolo, "stato": stato_etichetta(sessione), "completata": sessione.stato == "completato",
        "passoCorrente": max(1, min(int(sessione.step_corrente or 1), 5)), "passi": passi(sessione),
        "udienza": {
            "dataOra": data_ora, "quando": quando(data_ora, oggi) if data_ora else "Data da indicare",
            "luogo": str(getattr(app, "luogo", "") or getattr(fascicolo, "tribunale", "") or ""),
            "ufficio": str(getattr(fascicolo, "tribunale", "") or getattr(app, "tribunale", "") or ""),
            "giudice": str(getattr(fascicolo, "giudice", "") or ""), "sezione": str(getattr(fascicolo, "sezione", "") or ""),
            "rg": str(getattr(fascicolo, "numero_rg", "") or ""), "collegamento": remoto,
            "agendaHref": f"/agenda/{quote(str(app.id))}/modifica" if app is not None else "/agenda",
        },
        "causa": {
            "cliente": str(getattr(fascicolo, "nome_cliente", "") or ""), "controparte": str(getattr(fascicolo, "controparte", "") or ""),
            "avvocatoControparte": str(getattr(fascicolo, "avvocato_controparte", "") or ""),
            "oggetto": str(getattr(fascicolo, "oggetto", "") or ""), "fascicolo": rif_fascicolo(fascicolo),
            "idCliente": str(getattr(fascicolo, "id_cliente", "") or ""),
        },
        "termini": [{"titolo": s.titolo, "data": s.data_scadenza, "perentorio": bool(s.perentorio),
                     "href": f"/scadenziario/{quote(str(s.id))}/modifica"} for s in termini],
        "attivita": [{"data": a.data, "titolo": a.titolo, "descrizione": (a.descrizione or "")[:240]} for a in attivita],
        "tipoUdienza": sessione.tipo_udienza, "tipi": catalogo(), "verifiche": verifiche(sessione.tipo_udienza, sessione.verifiche_tipo),
        "avvisoAssenza": {"testo": AVVISO_ASSENZA[1], "fonte": fonte(AVVISO_ASSENZA[0])},
        "documenti": [{
            "indice": i, "etichetta": d.get("label", ""), "stato": d.get("stato", "da_portare"),
            "statoEtichetta": STATI_DOCUMENTO.get(d.get("stato", ""), "Da preparare"), "firmato": bool(d.get("firmato")),
            "href": f"/fascicoli/{quote(sessione.id_fascicolo)}/documenti/{quote(d['id_documento'])}/visualizza"
            if d.get("id_documento") in documenti else "",
        } for i, d in enumerate(sessione.checklist_documenti)],
        "campi": {campo: getattr(sessione, campo) for campi in CAMPI_PASSO.values() for campo in campi},
        "esito": {"valore": sessione.esito, "rinvioData": sessione.esito_rinvio_data, "rinvioOra": sessione.esito_rinvio_ora,
                  "noteVerbale": sessione.esito_note_verbale, "azioni": sessione.esito_azioni, "termini": sessione.termini_assegnati,
                  "rinvioAgendaHref": f"/agenda/{quote(sessione.id_appuntamento_rinvio)}/modifica" if sessione.id_appuntamento_rinvio else ""},
        "esiti": [{"value": k, "label": v} for k, v in ESITI.items()],
        "messaggioClienteHref": f"/messaggi/nuovo?id_cliente={quote(str(getattr(fascicolo, 'id_cliente', '') or ''))}&id_fascicolo={quote(sessione.id_fascicolo)}",
    }


def salva_passo(sessione: Any, passo: int, dati: dict[str, Any], *, conferma: bool) -> None:
    for campo in CAMPI_PASSO.get(passo, ()):
        if campo in dati:
            valore = dati[campo]
            setattr(sessione, campo, bool(valore) if campo.startswith("precheck_") and campo != "precheck_note" else str(valore or "")[:4000])
    if passo == 1 and "tipo_udienza" in dati:
        tipo = str(dati.get("tipo_udienza") or "")
        if tipo and tipo not in TIPI:
            raise ValueError("Tipo di udienza non riconosciuto.")
        sessione.tipo_udienza = tipo
    if conferma and 1 <= passo <= 4:
        setattr(sessione, f"step{passo}_confermato", True)
        sessione.step_corrente = max(int(sessione.step_corrente or 1), passo + 1)


def imposta_documento(sessione: Any, indice: int, stato: str) -> None:
    if stato not in STATI_DOCUMENTO:
        raise ValueError("Stato del documento non valido.")
    if not 0 <= indice < len(sessione.checklist_documenti):
        raise ValueError("Documento non trovato.")
    sessione.checklist_documenti[indice]["stato"] = stato


def aggiungi_documento(sessione: Any, etichetta: str) -> None:
    testo = " ".join(str(etichetta or "").split())[:200]
    if not testo:
        raise ValueError("Scrivi cosa portare.")
    sessione.checklist_documenti.append({"id_documento": "", "label": testo, "tipo": "ALTRO", "obbligatorio": False,
                                         "stato": "da_portare", "note": "", "nome_file": "", "firmato": False})


def imposta_verifica(sessione: Any, chiave: str, fatta: bool) -> None:
    if chiave not in {v[0] for v in TIPI.get(sessione.tipo_udienza, {}).get("verifiche", [])}:
        raise ValueError("Verifica non prevista per questo tipo di udienza.")
    sessione.verifiche_tipo = {**(sessione.verifiche_tipo or {}), chiave: bool(fatta)}


def registra_esito(sessione: Any, dati: dict[str, Any], *, agenda: Any, fascicoli: Any, scadenziario: Any, utente: str, oggi: date) -> list[str]:
    """Salva l'esito e ne crea i seguiti (una volta sola). Restituisce cosa è stato creato."""

    from pct.agenda import StatoAppuntamento, TipoAppuntamento
    from pct.fascicoli import EsitoAttivita, TipoAttivita
    from pct.scadenziario import TipoTermine

    esito = str(dati.get("esito") or "")
    if esito not in ESITI:
        raise ValueError("Scegli l'esito dell'udienza.")
    rinvio = str(dati.get("rinvioData") or "")[:10]
    ora = str(dati.get("rinvioOra") or "")[:5] or "09:00"
    if esito == "rinvio":
        try:
            if date.fromisoformat(rinvio) <= oggi:
                raise ValueError("La data del rinvio deve essere futura.")
        except ValueError as exc:
            raise ValueError(str(exc) if "futura" in str(exc) else "Indica la data del rinvio.") from exc
    termini = []
    for riga in (dati.get("termini") or [])[:10]:
        descrizione, giorno = str(riga.get("descrizione") or "").strip()[:200], str(riga.get("data") or "")[:10]
        if descrizione and giorno:
            date.fromisoformat(giorno)
            termini.append({"descrizione": descrizione, "data": giorno, "perentorio": bool(riga.get("perentorio")),
                            "id_scadenza": str(riga.get("id_scadenza") or "")})
    sessione.esito, sessione.esito_rinvio_data, sessione.esito_rinvio_ora = esito, rinvio if esito == "rinvio" else "", ora
    sessione.esito_note_verbale = str(dati.get("noteVerbale") or "")[:4000]
    sessione.esito_azioni = str(dati.get("azioni") or "")[:4000]
    fascicolo = fascicoli.get(sessione.id_fascicolo)
    app = agenda.get(sessione.id_appuntamento) if sessione.id_appuntamento else None
    creati = []
    if esito == "rinvio" and not sessione.id_appuntamento_rinvio:
        nuovo = agenda.aggiungi(f"Udienza di rinvio — {getattr(fascicolo, 'titolo', sessione.titolo)}", TipoAppuntamento.UDIENZA,
                                f"{rinvio}T{ora}:00", int(getattr(app, "durata_minuti", 60) or 60),
                                str(getattr(app, "luogo", "") or getattr(fascicolo, "tribunale", "") or ""), allow_overlap=True,
                                cliente=str(getattr(fascicolo, "nome_cliente", "") or ""), id_cliente=str(getattr(fascicolo, "id_cliente", "") or ""),
                                procedimento=f"RG {fascicolo.numero_rg}" if getattr(fascicolo, "numero_rg", "") else "",
                                tribunale=str(getattr(fascicolo, "tribunale", "") or ""), note=f"Rinvio disposto all'udienza del {oggi.strftime('%d/%m/%Y')}")
        sessione.id_appuntamento_rinvio = nuovo.id
        creati.append(f"udienza di rinvio del {rinvio[8:10]}/{rinvio[5:7]}/{rinvio[:4]} in agenda")
    for termine in termini:
        if termine["id_scadenza"]:
            continue
        scadenza = scadenziario.nuova(termine["descrizione"], TipoTermine.ADEMPIMENTO, termine["data"], id_fascicolo=sessione.id_fascicolo,
                                      descrizione="Termine assegnato dal giudice all'udienza", perentorio=termine["perentorio"],
                                      data_decorrenza=oggi.isoformat(), id_utente_responsabile=utente)
        termine["id_scadenza"] = scadenza.id
        creati.append(f"termine «{termine['descrizione']}»")
    sessione.termini_assegnati = termini
    if fascicolo is not None and not sessione.id_attivita_fascicolo:
        attivita = fascicoli.aggiungi_attivita(
            fascicolo.id, TipoAttivita.UDIENZA, str(getattr(app, "data_ora", "") or oggi.isoformat())[:10], sessione.titolo,
            descrizione="\n".join(p for p in (f"Esito: {ESITI[esito]}.", sessione.esito_note_verbale, sessione.esito_azioni) if p),
            esito=EsitoAttivita(_ESITO_ATTIVITA.get(esito, "IN_ATTESA")), id_appuntamento=sessione.id_appuntamento, avvocato=utente,
            note=f"[Preparazione udienza {sessione.id}]")
        sessione.id_attivita_fascicolo = attivita.id
        creati.append("nota dell'udienza nel fascicolo")
    if fascicolo is not None:
        # La nota dell'udienza tenuta non deve diventare la «prossima udienza»: vale il rinvio, se c'è.
        tenuta = str(getattr(app, "data_ora", "") or "")[:10]
        prossima = rinvio if esito == "rinvio" else ("" if str(fascicoli.get(fascicolo.id).data_prossima_udienza or "")[:10] in {tenuta, oggi.isoformat()} else None)
        if prossima is not None:
            fascicoli.aggiorna(fascicolo.id, data_prossima_udienza=prossima)
    if app is not None and str(getattr(app.stato, "value", app.stato)) not in {"COMPLETATO", "ANNULLATO"}:
        agenda.cambia_stato(app.id, StatoAppuntamento.COMPLETATO)
    sessione.step5_confermato, sessione.stato = True, "completato"
    sessione.completato_il = datetime.now().isoformat(timespec="seconds")
    return creati


__all__ = ["aggiungi_documento", "dettaglio", "imposta_documento", "imposta_verifica", "registra_esito", "salva_passo"]
