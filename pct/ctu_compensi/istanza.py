"""Bozza dell'istanza di liquidazione del CTU con la nota specifica (art. 71 D.P.R. 115/2002).

Produce l'HTML per l'editor del fascicolo: l'ausiliario la rilegge, la firma e la deposita con
l'atto «Deposito istanza di liquidazione CTU» del catalogo PCT. Nessun invio automatico.
"""

from __future__ import annotations

from html import escape
from typing import Any

from pct.ctu_compensi.onorari import euro


def _it(data_iso: str) -> str:
    valore = str(data_iso or "")[:10]
    return f"{valore[8:10]}/{valore[5:7]}/{valore[:4]}" if len(valore) == 10 else "____"


def _riga(etichetta: str, importo: float) -> str:
    return f"<tr><td>{escape(etichetta)}</td><td style=\"text-align:right\">{escape(euro(importo))}</td></tr>"


def html_istanza(*, incarico: Any, fascicolo: Any, calcolo: dict[str, Any], operazioni: list[dict[str, Any]]) -> str:
    ufficio = escape(str(getattr(fascicolo, "tribunale", "") or getattr(fascicolo, "ufficio", "") or "Tribunale di ____"))
    rg = escape(str(getattr(fascicolo, "numero_rg", "") or getattr(fascicolo, "rg", "") or "____"))
    giudice = escape(str(getattr(fascicolo, "giudice", "") or "____"))
    titolo_causa = escape(str(getattr(fascicolo, "titolo", "") or ""))
    nome = escape(incarico.nome_ctu or "____")
    parti = [f"<p><strong>{ufficio}</strong><br>R.G. n. {rg} — G.I. {giudice}<br>{titolo_causa}</p>",
             "<h2 style=\"text-align:center\">Istanza di liquidazione del compenso del consulente tecnico d'ufficio</h2>",
             f"<p>Il sottoscritto {nome}, nominato consulente tecnico d'ufficio con provvedimento del {_it(incarico.data_nomina)}"
             + (f" e che ha prestato l'impegno il {_it(incarico.data_giuramento)}" if incarico.data_giuramento else "")
             + (f", ha depositato la relazione il {_it(incarico.data_deposito_relazione)}" if getattr(incarico, "data_deposito_relazione", "") else "")
             + ".</p>",
             "<p>Chiede la liquidazione del compenso ai sensi degli artt. 49 ss. e 71 D.P.R. 115/2002, secondo la nota che segue.</p>",
             "<h3>Nota specifica</h3><table style=\"width:100%;border-collapse:collapse\">"]
    for riga in calcolo.get("righe") or []:
        dettaglio = f" (valore {euro(riga['valore'])})" if riga.get("valore") else ""
        forbice = (f": da {euro(riga['minimo'])} a {euro(riga['massimo'])}" if riga["minimo"] != riga["massimo"] else "")
        parti.append(f"<tr><td colspan=\"2\">{escape(riga['titolo'] + dettaglio + forbice)}</td></tr>")
    parti.append(_riga("Onorario richiesto", calcolo["onorario_base"]))
    for passaggio in calcolo.get("passaggi") or []:
        parti.append(_riga(passaggio["voce"], passaggio["onorario"]))
    if calcolo.get("contributo"):
        parti.append(_riga(f"Contributo previdenziale {calcolo['contributo_perc']:g}%", calcolo["contributo"]))
    if calcolo.get("iva"):
        parti.append(_riga(f"IVA {calcolo['iva_perc']:g}%", calcolo["iva"]))
    if calcolo.get("spese_viaggio"):
        parti.append(_riga("Indennità e spese di viaggio (art. 55)", calcolo["spese_viaggio"]))
    if calcolo.get("spese_documentate"):
        parti.append(_riga("Spese documentate (art. 56), come da allegati", calcolo["spese_documentate"]))
    parti.append(f"<tr><td><strong>Totale</strong></td><td style=\"text-align:right\"><strong>{escape(euro(calcolo['totale']))}"
                 "</strong></td></tr></table>")
    if operazioni:
        parti.append("<h3>Operazioni svolte</h3><ul>")
        for op in operazioni:
            durata = f", {int(op.get('minuti') or 0) // 60} h {int(op.get('minuti') or 0) % 60:02d} min" if op.get("minuti") else ""
            parti.append(f"<li>{_it(op.get('data', ''))} — {escape(str(op.get('descrizione') or op.get('tipo') or 'Operazione'))}"
                         f"{escape(durata)}{escape(', ' + str(op.get('luogo'))) if op.get('luogo') else ''}</li>")
        parti.append("</ul>")
    for nota in calcolo.get("note") or []:
        parti.append(f"<p><em>{escape(nota)}</em></p>")
    parti.append("<p>Chiede che il compenso sia posto a carico della parte che il Giudice riterrà, con provvisoria esecutività "
                 "del decreto (art. 168 D.P.R. 115/2002).</p><p>Con osservanza.</p><p>Luogo e data ____</p>"
                 f"<p style=\"text-align:right\">{nome}</p>")
    return "".join(parti)


__all__ = ["html_istanza"]
