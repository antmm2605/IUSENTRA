"""Dalle voci degli archivi dello studio alle voci del Controllo Studio.

Ogni funzione riceve gli oggetti già letti dal proprio archivio e restituisce voci con le azioni
che servono davvero: completare il termine, preparare l'udienza, leggere la PEC, registrare
l'incasso. Le soglie di tempo sono quelle della coda (scaduto, oggi, domani, 7 e 30 giorni).
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any
from urllib.parse import quote, urlencode

from pct.controllo_studio.voce import Azione, Voce, quando_etichetta
from pct.formatting import format_datetime_it, parse_datetime_rome

ORIZZONTE_GIORNI = 30
_RG = re.compile(r"(?<![\d/])(\d{1,7})\s*/\s*(\d{4})(?!\d)")


def _valore(oggetto: Any, campo: str, predefinito: Any = "") -> Any:
    valore = getattr(oggetto, campo, predefinito)
    return getattr(valore, "value", valore)


def _euro(importo: float) -> str:
    intero, decimali = f"{float(importo):,.2f}".split(".")
    return f"€ {intero.replace(',', '.')},{decimali}"


def rif_fascicolo(fascicolo: Any) -> dict[str, str]:
    if fascicolo is None:
        return {}
    rg = str(_valore(fascicolo, "numero_rg") or "")
    anno = str(_valore(fascicolo, "anno_rg") or "")
    if rg and anno and "/" not in rg:
        rg = f"{rg}/{anno}"
    numero = str(_valore(fascicolo, "numero") or "")
    nome = str(_valore(fascicolo, "nome_cliente") or "")
    etichetta = " · ".join(p for p in (nome, f"Fascicolo {numero}" if numero else "",
        f"R.G. {rg}" if rg else "", str(_valore(fascicolo, "titolo") or "") if not nome else "") if p)
    return {"id": str(fascicolo.id), "etichetta": etichetta, "href": f"/fascicoli/{quote(str(fascicolo.id))}"}


def indice_rg(fascicoli: list[Any]) -> dict[str, Any]:
    """Fascicoli per numero di ruolo normalizzato («1234/2026»), per collegare le udienze in agenda."""

    indice = {}
    for fascicolo in fascicoli:
        numero = str(_valore(fascicolo, "numero_rg") or "").strip()
        anno = str(_valore(fascicolo, "anno_rg") or "").strip()
        if numero and anno and "/" not in numero:
            numero = f"{numero}/{anno}"
        trovato = _RG.search(numero)
        if trovato:
            chiave = f"{int(trovato.group(1))}/{trovato.group(2)}"
            if chiave not in indice:
                indice[chiave] = fascicolo
            elif indice[chiave] is not None and str(indice[chiave].id) != str(fascicolo.id):
                indice[chiave] = None  # stesso RG in uffici/registri diversi: mai scegliere l'ultimo
    return indice


def fascicolo_da_testo(testo: str, per_rg: dict[str, Any]) -> Any:
    chiavi = {f"{int(m.group(1))}/{m.group(2)}" for m in _RG.finditer(str(testo or ""))}
    return per_rg.get(next(iter(chiavi))) if len(chiavi) == 1 else None


def voci_scadenze(scadenze: list[Any], fascicoli: dict[str, Any], oggi: date) -> list[Voce]:
    limite = (oggi + timedelta(days=ORIZZONTE_GIORNI)).isoformat()
    voci = []
    for scadenza in scadenze:
        if str(_valore(scadenza, "stato")) not in {"APERTO", "SCADUTO"}:
            continue
        giorno = str(_valore(scadenza, "data_scadenza") or "")[:10]
        if not giorno or giorno > limite:
            continue
        perentorio = bool(_valore(scadenza, "perentorio", False))
        scaduta = giorno < oggi.isoformat()
        vicina = giorno <= (oggi + timedelta(days=2)).isoformat()
        fascicolo = fascicoli.get(str(_valore(scadenza, "id_fascicolo") or ""))
        tipo = str(_valore(scadenza, "tipo") or "").replace("_", " ").capitalize()
        voci.append(Voce(
            id=f"scadenza-{scadenza.id}", area="scadenze", titolo=str(_valore(scadenza, "titolo") or "Termine"),
            dettaglio=" · ".join(p for p in (tipo, "termine perentorio" if perentorio else "") if p),
            data=giorno, gravita="critica" if (scaduta or (vicina and perentorio)) else "alta" if vicina else "normale",
            etichetta=f"Scaduto {quando_etichetta(giorno, oggi).lower()}" if scaduta else quando_etichetta(giorno, oggi),
            fascicolo=rif_fascicolo(fascicolo),
            azioni=[Azione("Apri il termine", href=f"/scadenziario/{quote(str(scadenza.id))}/modifica", principale=True),
                    Azione("Segna fatto", endpoint=f"/api/v1/ui/controllo-studio/scadenze/{quote(str(scadenza.id))}/completa",
                           conferma="Segnare il termine come adempiuto?")],
        ))
    return voci


def voci_agenda(appuntamenti: list[Any], per_rg: dict[str, Any], sessioni_udienza: dict[str, Any], oggi: date) -> list[Voce]:
    limite = (oggi + timedelta(days=14)).isoformat()
    voci = []
    for app in appuntamenti:
        if str(_valore(app, "stato")) in {"COMPLETATO", "ANNULLATO", "RINVIATO"}:
            continue
        inizio = str(_valore(app, "data_ora") or "")
        giorno = inizio[:10]
        if not giorno or giorno < oggi.isoformat() or giorno > limite:
            continue
        udienza = str(_valore(app, "tipo")) == "UDIENZA"
        fascicolo = fascicolo_da_testo(" ".join(str(_valore(app, campo) or "") for campo in ("procedimento", "titolo")), per_rg)
        luogo = str(_valore(app, "luogo") or "")
        azioni = [Azione("Apri in agenda", href=f"/agenda/{quote(str(app.id))}/modifica")]
        gravita = "normale"
        if udienza:
            sessione = sessioni_udienza.get(str(app.id))
            if sessione is not None and str(_valore(sessione, "stato")) == "completato":
                etichetta_prep = "Preparata"
            elif sessione is not None:
                etichetta_prep = f"Preparazione al passo {_valore(sessione, 'step_corrente', 1)} di 5"
            else:
                etichetta_prep = "Da preparare"
            href = (f"/wizard-pro/{quote(str(sessione.id))}/step/{int(_valore(sessione, 'step_corrente', 1) or 1)}" if sessione is not None
                    else f"/wizard-pro/?{urlencode({'id_fascicolo': fascicolo.id, 'id_appuntamento': app.id})}" if fascicolo is not None
                    else f"/wizard-pro/?{urlencode({'id_appuntamento': app.id})}")
            azioni.insert(0, Azione("Prepara l'udienza" if sessione is None else "Continua la preparazione", href=href, principale=True))
            gravita = "alta" if giorno <= (oggi + timedelta(days=1)).isoformat() and etichetta_prep == "Da preparare" else "normale"
            dettaglio = luogo
        else:
            azioni[0].principale = True
            dettaglio = " · ".join(p for p in (str(_valore(app, "cliente") or ""), luogo) if p)
        voci.append(Voce(id=f"agenda-{app.id}", area="agenda", titolo=str(_valore(app, "titolo") or "Appuntamento"),
                         dettaglio=dettaglio, data=giorno, ora=inizio[11:16], gravita=gravita,
                         etichetta=f"Udienza · {etichetta_prep.lower()}" if udienza else str(_valore(app, "tipo") or "").capitalize(),
                         fascicolo=rif_fascicolo(fascicolo), azioni=azioni))
    return voci


def voci_incassi(parcelle: list[Any], clienti: dict[str, Any], oggi: date, fascicoli: dict[str, Any] | None = None) -> list[Voce]:
    voci = []
    for parcella in parcelle:
        if str(_valore(parcella, "stato")) not in {"EMESSA", "SCADUTA"}:
            continue
        importo = float(getattr(parcella, "netto_a_pagare", 0) or getattr(parcella, "totale", 0) or 0)
        scadenza = str(_valore(parcella, "data_scadenza") or "")[:10]
        scaduta = str(_valore(parcella, "stato")) == "SCADUTA" or (bool(scadenza) and scadenza < oggi.isoformat())
        if not scaduta and scadenza and scadenza > (oggi + timedelta(days=ORIZZONTE_GIORNI)).isoformat():
            continue
        cliente = clienti.get(str(_valore(parcella, "id_cliente") or ""))
        nome = str(getattr(cliente, "nome_completo", "") or "Cliente non indicato")
        numero = str(_valore(parcella, "numero") or "")
        giorni = (oggi - date.fromisoformat(scadenza)).days if scaduta and scadenza else 0
        voci.append(Voce(
            id=f"incasso-{parcella.id}", area="incassi", titolo=f"Parcella {numero} — {nome}" if numero else f"Parcella — {nome}",
            dettaglio=f"{_euro(importo)} da incassare" + (f", scaduta da {giorni} giorni" if giorni > 0 else ""),
            data=scadenza or oggi.isoformat(), gravita="critica" if giorni > 30 else "alta" if scaduta else "normale",
            etichetta="Scaduta" if scaduta else "In scadenza", importo=round(importo, 2),
            fascicolo=rif_fascicolo((fascicoli or {}).get(str(_valore(parcella, "id_fascicolo") or ""))),
            azioni=[Azione("Registra incasso", href=f"/incassi-pagamenti?{urlencode({'id_parcella': parcella.id})}#registra-incasso", principale=True),
                    Azione("Apri la parcella", href=f"/fatturazione/{quote(str(parcella.id))}")],
        ))
    return voci


def _ricevuta(quando: str, oggi: date) -> str:
    ricevuta = parse_datetime_rome(quando)
    if ricevuta is None:
        return ""
    if ricevuta.date() == oggi:
        return f"ricevuta oggi alle {ricevuta:%H:%M}"
    return f"ricevuta il {format_datetime_it(ricevuta)}"


def voci_comunicazioni(pec_non_lette: list[Any], messaggi_falliti: list[Any], oggi: date,
                       fascicoli: dict[str, Any] | None = None, collegamenti: dict[str, str] | None = None) -> list[Voce]:
    voci = []
    for pec in pec_non_lette:
        ricevuta = str(_valore(pec, "data") or _valore(pec, "ricevuta_il") or "")
        pst = bool(_valore(pec, "id_deposito_pct")) or "DEPOSITO" in str(_valore(pec, "oggetto") or "").upper()
        voci.append(Voce(
            id=f"pec-{pec.id}", area="comunicazioni", titolo=str(_valore(pec, "oggetto") or "PEC senza oggetto"),
            dettaglio=" · ".join(p for p in (str(_valore(pec, "mittente_nome") or _valore(pec, "mittente") or ""), _ricevuta(ricevuta, oggi)) if p),
            data=parse_datetime_rome(ricevuta).date().isoformat() if parse_datetime_rome(ricevuta) else "",
            gravita="alta" if pst else "normale", fascia="da_leggere",
            etichetta="Esito deposito" if pst else "PEC da leggere",
            fascicolo=rif_fascicolo((fascicoli or {}).get((collegamenti or {}).get(str(pec.id), ""))),
            azioni=[Azione("Leggi la PEC", href=f"/email/messaggio/{quote(str(pec.id))}", principale=True),
                    Azione("Segna letta", endpoint=f"/api/v1/ui/controllo-studio/pec/{quote(str(pec.id))}/letta")],
        ))
    for messaggio in messaggi_falliti:
        voci.append(Voce(
            id=f"messaggio-{messaggio.id}", area="comunicazioni",
            titolo=f"Messaggio non consegnato a {str(_valore(messaggio, 'nome_destinatario') or 'cliente')}",
            dettaglio=" · ".join(p for p in (str(_valore(messaggio, "canale") or "").capitalize(),
                                             str(_valore(messaggio, "errore") or "")[:120]) if p),
            data=oggi.isoformat(), gravita="alta", etichetta="Da rifare",
            azioni=[Azione("Apri il messaggio", href=f"/messaggi/{quote(str(messaggio.id))}", principale=True)],
        ))
    return voci


def voci_notifiche(presidi: list[dict[str, Any]], oggi: date, fascicoli: dict[str, Any] | None = None) -> list[Voce]:
    """Presidi notifiche aperti (già letti dal registro): notifiche fallite o parziali in cima."""

    voci = []
    for riga in presidi:
        tono = str(riga.get("tone") or "")
        data_it = str(riga.get("time") or "")
        termine = parse_datetime_rome(str(riga.get("due_at") or ""))
        giorno = termine.date().isoformat() if termine else ""
        if not giorno and re.fullmatch(r"\d{2}/\d{2}/\d{4}", data_it):
            giorno = f"{data_it[6:10]}-{data_it[3:5]}-{data_it[0:2]}"
        voci.append(Voce(id=str(riga.get("id") or ""), area="notifiche", titolo=str(riga.get("title") or "Notifica da verificare"),
                         dettaglio=str(riga.get("subtitle") or ""), data=giorno,
                         data_riferimento=str(riga.get("reference_at") or ""), tipo_data_riferimento=str(riga.get("reference_label") or ""),
                         gravita="critica" if tono == "danger" else "alta" if tono == "warning" else "normale",
                         etichetta=str(riga.get("badge") or ""),
                         fascicolo=rif_fascicolo((fascicoli or {}).get(str(riga.get("fascicolo_id") or ""))),
                         azioni=[Azione("Apri il presidio", href=str(riga.get("href") or "/notifiche-legali"), principale=True)]))
    return voci


def riepilogo_incassi(parcelle: list[Any], oggi: date) -> dict[str, float]:
    aperte = [p for p in parcelle if str(_valore(p, "stato")) in {"EMESSA", "SCADUTA"}]

    def importo(p: Any) -> float:
        return float(getattr(p, "netto_a_pagare", 0) or getattr(p, "totale", 0) or 0)

    scadute = [p for p in aperte if str(_valore(p, "stato")) == "SCADUTA"
               or (str(_valore(p, "data_scadenza") or "")[:10] and str(_valore(p, "data_scadenza"))[:10] < oggi.isoformat())]
    mese = oggi.strftime("%Y-%m")
    incassato = sum(importo(p) for p in parcelle if str(_valore(p, "stato")) == "PAGATA"
                    and str(_valore(p, "data_pagamento") or "")[:7] == mese)
    return {"da_incassare": round(sum(importo(p) for p in aperte), 2), "scaduto": round(sum(importo(p) for p in scadute), 2),
            "parcelle_scadute": len(scadute), "incassato_mese": round(incassato, 2)}


__all__ = ["ORIZZONTE_GIORNI", "fascicolo_da_testo", "indice_rg", "riepilogo_incassi", "rif_fascicolo", "voci_agenda",
           "voci_comunicazioni", "voci_incassi", "voci_notifiche", "voci_scadenze"]
