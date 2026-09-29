"""Fascicolo antiriciclaggio del cliente in PDF, da conservare per dieci anni (artt. 31-32 D.Lgs. 231/2007).

Raccoglie in un documento i dati dell'adeguata verifica (artt. 18-20), la profilatura del rischio con la
griglia CNF, il livello scelto e la motivazione, le prove dello screening sulle liste delle sanzioni
finanziarie UE e il registro delle modifiche. Documento interno dello studio: la valutazione sulla
segnalazione di operazione sospetta non va comunicata al cliente (art. 39).
"""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape


def _p(testo: Any, stile) -> Paragraph:
    return Paragraph(escape(str(testo or "—")), stile)


def _data_it(valore: str) -> str:
    valore = str(valore or "")[:10]
    return f"{valore[8:10]}/{valore[5:7]}/{valore[0:4]}" if len(valore) == 10 else (valore or "—")


def pdf_fascicolo(scheda: dict[str, Any], *, cliente: str, studio: str, evidenze: list[dict[str, Any]],
                  registro: list[dict[str, Any]]) -> bytes:
    stili = getSampleStyleSheet()
    normale, titolo, sezione = stili["BodyText"], stili["Title"], stili["Heading3"]
    normale.fontSize = 9
    normale.leading = 12
    uscita = io.BytesIO()
    doc = SimpleDocTemplate(uscita, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Fascicolo antiriciclaggio {cliente}")

    def tabella(righe: list[list[Any]], larghezze: list[float]) -> Table:
        t = Table([[_p(c, normale) for c in r] for r in righe], colWidths=larghezze, repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    titolare = scheda.get("titolare_effettivo") or {}
    corpo: list[Any] = [
        Paragraph("Fascicolo antiriciclaggio", titolo),
        _p(f"{studio} — cliente: {cliente} — scheda {scheda.get('id')}", normale),
        _p("D.Lgs. 231/2007 artt. 17-25, 31-32; Regole tecniche CNF 20/09/2019. Documento interno: non comunicare al "
           "cliente l'eventuale segnalazione di operazione sospetta (art. 39).", normale),
        Spacer(1, 4 * mm), Paragraph("Adeguata verifica", sezione),
        tabella([["Voce", "Dato"],
                 ["Prestazione", scheda.get("prestazione_etichetta")],
                 ["Scopo e natura del rapporto", scheda.get("scopo_natura")],
                 ["Descrizione", scheda.get("descrizione_prestazione")],
                 ["Documento d'identità", " ".join(filter(None, [str(scheda.get("documento_tipo") or "").replace("_", " "),
                                                                   scheda.get("documento_numero"), scheda.get("documento_rilasciato_da")]))],
                 ["Rilascio / scadenza", f"{_data_it(scheda.get('documento_data_rilascio'))} / {_data_it(scheda.get('documento_scadenza'))}"],
                 ["Titolare effettivo (art. 20)", " — ".join(filter(None, [titolare.get("nome"), titolare.get("codice_fiscale"), titolare.get("criterio")]))],
                 ["Persona politicamente esposta", "sì" if scheda.get("cliente_pep") else "no"],
                 ["Paese terzo ad alto rischio", "sì" if scheda.get("paese_alto_rischio") else "no"]],
                [55 * mm, 119 * mm]),
        Spacer(1, 4 * mm), Paragraph("Profilatura del rischio (griglia CNF, punteggi 1-5)", sezione),
        tabella([["Area", "Indice", "Punteggio", "Note"]] + [
            [i.get("macro_area", "").replace("_", " ").lower(), i.get("descrizione"), i.get("punteggio"), i.get("note")]
            for i in scheda.get("indici") or []], [26 * mm, 86 * mm, 22 * mm, 40 * mm]),
        _p(f"Totale {scheda.get('punteggio_totale')} — media {scheda.get('punteggio_medio')} — livello suggerito "
           f"{str(scheda.get('livello_suggerito') or '').lower()}; livello scelto {str(scheda.get('livello_scelto') or 'non ancora confermato').lower()}.", normale),
    ]
    if scheda.get("motivazione_scostamento"):
        corpo.append(_p(f"Motivazione dello scostamento: {scheda['motivazione_scostamento']}", normale))
    corpo += [
        _p(f"Verifica del {_data_it(scheda.get('data_verifica'))} ({scheda.get('operatore') or '—'}); controllo costante entro il "
           f"{_data_it(scheda.get('scadenza_controllo'))}; conservazione fino al {_data_it(scheda.get('conservazione_fino_al'))}.", normale),
        _p(f"Segnalazione di operazione sospetta (art. 35): {scheda.get('sos_etichetta')}"
           + (f" il {_data_it(scheda.get('sos_data'))}" if scheda.get("sos_data") else "")
           + (f" — {scheda.get('sos_note')}" if scheda.get("sos_note") else ""), normale),
        Spacer(1, 4 * mm), Paragraph("Screening sulle sanzioni finanziarie UE", sezione),
        tabella([["Data", "Soggetto", "Esito", "Fonte e impronta"]] + [
            [_data_it(e.get("checked_at")), e.get("subject_label"), str(e.get("outcome") or "").replace("_", " ").lower(),
             f"{e.get('source_url') or ''} {str(e.get('snapshot_hash') or '')[:16]}"] for e in evidenze] or [["—", "—", "—", "—"]],
            [22 * mm, 50 * mm, 34 * mm, 68 * mm]),
        Spacer(1, 4 * mm), Paragraph("Registro delle modifiche", sezione),
        tabella([["Quando", "Evento", "Descrizione"]] + [
            [str(r.get("created_at") or r.get("creato_il") or "")[:19].replace("T", " "), r.get("event_type"), r.get("message")]
            for r in registro[:60]], [36 * mm, 50 * mm, 88 * mm]),
    ]
    doc.build(corpo)
    return uscita.getvalue()


__all__ = ["pdf_fascicolo"]
