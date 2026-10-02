"""Preparazione udienza: elenco delle prossime udienze con lo stato della preparazione e avvio.

Le udienze vengono dall'agenda (appuntamenti di tipo udienza) e dai fascicoli con la data della
prossima udienza; ogni udienza è collegata al fascicolo per numero di ruolo. Una udienza ha al più
una preparazione: «Prepara» la crea o riapre quella esistente.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote

from pct.controllo_studio.fonti import rif_fascicolo
from pct.udienze.preparazione import ESITI, quando, stato_etichetta
from web.services.preparazione_udienza_associazione import fascicolo_udienza

ORIZZONTE = 60


def _href(sessione: Any) -> str:
    passo = 5 if getattr(sessione, "stato", "") == "completato" else max(1, min(int(getattr(sessione, "step_corrente", 1) or 1), 5))
    return f"/wizard-pro/{quote(str(sessione.id))}/step/{passo}"


def elenco(*, agenda: Any, fascicoli: Any, preparazioni: Any, oggi: date) -> dict[str, Any]:
    tutti_fascicoli = list(fascicoli.tutti())
    sessioni = [s for s in preparazioni.lista() if getattr(s, "stato", "") != "archiviato"]
    per_appuntamento = {str(s.id_appuntamento): s for s in sessioni if s.id_appuntamento}
    limite = (oggi + timedelta(days=ORIZZONTE)).isoformat()
    udienze, visti = [], set()
    for app in agenda.tutti():
        stato = str(getattr(getattr(app, "stato", ""), "value", ""))
        if str(getattr(getattr(app, "tipo", ""), "value", "")) != "UDIENZA" or stato in {"ANNULLATO", "RINVIATO"}:
            continue
        giorno = str(app.data_ora or "")[:10]
        if not giorno or giorno < oggi.isoformat() or giorno > limite:
            continue
        fascicolo = fascicolo_udienza(app, tutti_fascicoli, sessioni)
        sessione = per_appuntamento.get(str(app.id))
        if fascicolo is not None:
            visti.add((str(fascicolo.id), giorno))
        udienze.append(_riga(app.data_ora, app.titolo, app.luogo or app.tribunale, fascicolo, sessione, oggi, id_appuntamento=str(app.id),
                             cliente=str(app.cliente or getattr(fascicolo, "nome_cliente", "") or "")))
    for fascicolo in tutti_fascicoli:
        giorno = str(getattr(fascicolo, "data_prossima_udienza", "") or "")[:10]
        if not giorno or giorno < oggi.isoformat() or giorno > limite or (str(fascicolo.id), giorno) in visti:
            continue
        sessione = next((s for s in sessioni if s.id_fascicolo == fascicolo.id and not s.id_appuntamento and s.stato != "completato"), None)
        udienze.append(_riga(str(fascicolo.data_prossima_udienza), f"Udienza {fascicolo.titolo}", fascicolo.tribunale, fascicolo, sessione,
                             oggi, cliente=str(fascicolo.nome_cliente or "")))
    udienze.sort(key=lambda u: u["dataOra"])
    concluse = sorted((s for s in sessioni if s.stato == "completato"), key=lambda s: s.completato_il or "", reverse=True)[:8]
    settimana = (oggi + timedelta(days=7)).isoformat()
    return {
        "ok": True, "udienze": udienze,
        "concluse": [{"id": s.id, "titolo": s.titolo, "esito": ESITI.get(s.esito, s.esito or "—"), "data": (s.completato_il or "")[:10],
                      "rinvio": s.esito_rinvio_data, "href": _href(s)} for s in concluse],
        "riepilogo": {"settimana": sum(1 for u in udienze if u["dataOra"][:10] <= settimana),
                      "daPreparare": sum(1 for u in udienze if u["stato"] == "Da preparare"),
                      "preparate": sum(1 for u in udienze if u["stato"] in {"Preparata", "Esito registrato"})},
        "fascicoli": [{"value": f.id, "label": " — ".join(p for p in (f.numero_rg and f"R.G. {f.numero_rg}", f.titolo) if p)}
                      for f in tutti_fascicoli[:500]],
    }


def _riga(data_ora: str, titolo: str, luogo: str, fascicolo: Any, sessione: Any, oggi: date, *, id_appuntamento: str = "", cliente: str = "") -> dict[str, Any]:
    ora = str(data_ora or "")
    return {
        "idAppuntamento": id_appuntamento, "idFascicolo": str(getattr(fascicolo, "id", "") or ""), "titolo": str(titolo or "Udienza"),
        "dataOra": ora if len(ora) > 10 else f"{ora[:10]}T00:00", "quando": quando(ora if len(ora) > 10 else f"{ora[:10]}T09:00", oggi),
        "luogo": str(luogo or ""), "cliente": cliente, "giudice": str(getattr(fascicolo, "giudice", "") or ""),
        "fascicolo": rif_fascicolo(fascicolo), "stato": stato_etichetta(sessione),
        "passiFatti": sum(1 for n in range(1, 6) if getattr(sessione, f"step{n}_confermato", False)) if sessione else 0,
        "href": _href(sessione) if sessione else "",
    }


def avvia(*, agenda: Any, fascicoli: Any, preparazioni: Any, id_appuntamento: str, id_fascicolo: str, avvocato: str) -> Any:
    """Riapre la preparazione dell'udienza se c'è già, altrimenti la crea con la lista dei documenti del fascicolo."""

    from pct.wizard_pro import DocumentoChecklist, SessioneWizardPro
    from web.services.preparazione_udienza_documenti import nomi_documenti

    appuntamento = agenda.get(id_appuntamento) if id_appuntamento else None
    if id_appuntamento and appuntamento is None:
        raise ValueError("Udienza non trovata in agenda.")
    for sessione in preparazioni.lista():
        if appuntamento is not None and sessione.id_appuntamento == appuntamento.id and sessione.stato != "archiviato":
            return sessione
    fascicolo = fascicoli.get(id_fascicolo) if id_fascicolo else None
    if fascicolo is None and appuntamento is not None:
        fascicolo = fascicolo_udienza(appuntamento, list(fascicoli.tutti()), preparazioni.lista())
    if fascicolo is None:
        raise ValueError("Scegli il fascicolo dell'udienza.")
    if appuntamento is None:
        for sessione in preparazioni.lista_per_fascicolo(fascicolo.id):
            if sessione.stato == "in_corso" and not sessione.id_appuntamento:
                return sessione
    rg = str(getattr(fascicolo, "numero_rg", "") or "")
    sessione = SessioneWizardPro.nuova(id_fascicolo=fascicolo.id, titolo=f"Udienza {'R.G. ' + rg + ' — ' if rg else ''}{fascicolo.titolo}",
                                       id_appuntamento=str(getattr(appuntamento, "id", "") or ""), avvocato=avvocato)
    nomi = nomi_documenti(fascicolo)
    sessione.checklist_documenti = [DocumentoChecklist(id_documento=d.id, label=nomi[str(d.id)],
                                                       tipo=str(getattr(d.tipo, "value", d.tipo)), obbligatorio=False, stato="da_portare",
                                                       nome_file=d.nome, firmato=bool(d.firmato_digitalmente)).to_dict()
                                    for d in fascicolo.documenti if not getattr(d, "eliminato_il", "")]
    sessione.modificato_il = datetime.now().isoformat()
    preparazioni.salva(sessione)
    return sessione


__all__ = ["avvia", "elenco"]
