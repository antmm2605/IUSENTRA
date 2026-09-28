"""Attestazione di conformità del difensore su una copia informatica.

Base normativa: D.Lgs. 82/2005 (CAD) art. 22, comma 2 (copia informatica di documento analogico) e
art. 23-bis, comma 2 (copia informatica di documento informatico); potere di attestazione del
difensore: art. 196-octies disp. att. c.p.c. e, nel processo amministrativo, art. 136, comma 2-ter,
c.p.a. L'attestazione si sottoscrive con firma digitale: IUSENTRA prepara la copia con il testo, il
luogo e la data; la firma la appone l'avvocato (pulsante «Firma» del documento).

La copia attestata è un documento nuovo: le pagine dell'originale restano identiche e l'attestazione
si aggiunge in una pagina finale o in fondo all'ultima pagina, con carattere e dimensioni scelti
dall'avvocato.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

TIPI = {
    "analogico": "all'originale analogico",
    "informatico": "al documento informatico",
}
FORMULA = ("Il sottoscritto Avv. {avvocato} attesta, vera ed autentica ai sensi di legge, che la presente copia "
           "informatica è conforme {origine} dal quale è estratta.")

# Caratteri proposti: equivalenti metrici aperti dei caratteri d'ufficio (registrati da pct.caratteri_reali,
# incorporati nel PDF) con il ripiego sui caratteri base del PDF quando non sono installati.
CARATTERI: dict[str, tuple[str, str, dict[str, str]]] = {
    "times": ("Times New Roman", "liberation serif",
              {"normale": "Times-Roman", "grassetto": "Times-Bold", "corsivo": "Times-Italic", "grassetto_corsivo": "Times-BoldItalic"}),
    "arial": ("Arial", "liberation sans",
              {"normale": "Helvetica", "grassetto": "Helvetica-Bold", "corsivo": "Helvetica-Oblique", "grassetto_corsivo": "Helvetica-BoldOblique"}),
    "calibri": ("Calibri", "carlito",
                {"normale": "Helvetica", "grassetto": "Helvetica-Bold", "corsivo": "Helvetica-Oblique", "grassetto_corsivo": "Helvetica-BoldOblique"}),
    "cambria": ("Cambria", "caladea",
                {"normale": "Times-Roman", "grassetto": "Times-Bold", "corsivo": "Times-Italic", "grassetto_corsivo": "Times-BoldItalic"}),
    "courier": ("Courier New", "liberation mono",
                {"normale": "Courier", "grassetto": "Courier-Bold", "corsivo": "Courier-Oblique", "grassetto_corsivo": "Courier-BoldOblique"}),
}
STILI = ("normale", "grassetto", "corsivo", "grassetto_corsivo")
_TAGLI = {"normale": "normal", "grassetto": "bold", "corsivo": "italic", "grassetto_corsivo": "bold_italic"}
POSIZIONI = {"pagina": "In una pagina finale", "fondo": "In fondo all'ultima pagina"}


@dataclass(frozen=True)
class Attestazione:
    avvocato: str
    firma: str
    luogo: str
    data: date
    tipo: str = "analogico"
    testo: str = ""
    carattere_testo: str = "times"
    dimensione_testo: float = 11
    carattere_firma: str = "times"
    stile_firma: str = "corsivo"
    dimensione_firma: float = 13
    posizione: str = "pagina"

    def testo_attestazione(self) -> str:
        """La formula (o il testo scritto dall'avvocato) con nome e tipo di originale."""
        origine = TIPI.get(self.tipo, TIPI["analogico"])
        return (self.testo or FORMULA).replace("{avvocato}", self.avvocato).replace("{origine}", origine)

    def luogo_data(self) -> str:
        return f"{self.luogo}, {self.data.strftime('%d.%m.%Y')}"


def da_dati(dati: dict[str, Any], *, avvocato: str = "", luogo: str = "") -> Attestazione:
    """Valida le scelte dell'avvocato (valori ammessi, dimensioni ragionevoli, data reale)."""
    def testo(chiave: str, predefinito: str = "", massimo: int = 200) -> str:
        valore = re.sub(r"\s+", " ", str(dati.get(chiave) or predefinito)).strip()
        if len(valore) > massimo:
            raise ValueError(f"Il campo «{chiave}» è troppo lungo.")
        return valore

    def numero(chiave: str, predefinito: float, minimo: float, massimo: float) -> float:
        try:
            valore = float(str(dati.get(chiave) or predefinito).replace(",", "."))
        except ValueError as exc:
            raise ValueError(f"Dimensione non valida: {chiave}.") from exc
        if not minimo <= valore <= massimo:
            raise ValueError(f"La dimensione deve essere tra {minimo:g} e {massimo:g} punti.")
        return valore

    nome = testo("avvocato", avvocato, 120)
    if not nome:
        raise ValueError("Indica il nome dell'avvocato che attesta.")
    sede = testo("luogo", luogo, 80)
    if not sede:
        raise ValueError("Indica il luogo dell'attestazione.")
    grezza = testo("data", date.today().isoformat(), 10)
    try:
        giorno = date.fromisoformat(grezza)
    except ValueError as exc:
        raise ValueError("Data dell'attestazione non valida.") from exc
    tipo = testo("tipo", "analogico", 20)
    carattere_testo, carattere_firma = testo("carattereTesto", "times", 20), testo("carattereFirma", "times", 20)
    stile_firma, posizione = testo("stileFirma", "corsivo", 20), testo("posizione", "pagina", 20)
    if tipo not in TIPI or carattere_testo not in CARATTERI or carattere_firma not in CARATTERI:
        raise ValueError("Scelta non prevista per tipo o carattere.")
    if stile_firma not in STILI or posizione not in POSIZIONI:
        raise ValueError("Scelta non prevista per stile della firma o posizione.")
    return Attestazione(
        avvocato=nome, firma=testo("firma", nome, 120) or nome, luogo=sede, data=giorno, tipo=tipo,
        testo=testo("testo", "", 1200), carattere_testo=carattere_testo,
        dimensione_testo=numero("dimensioneTesto", 11, 8, 16), carattere_firma=carattere_firma,
        stile_firma=stile_firma, dimensione_firma=numero("dimensioneFirma", 13, 8, 28), posizione=posizione,
    )


def _font(carattere: str, stile: str) -> str:
    """Il carattere registrato (incorporato nel PDF) oppure il carattere base equivalente."""
    _etichetta, famiglia, base = CARATTERI[carattere]
    try:
        from pct.caratteri_reali import registro

        tagli = registro().get(famiglia)
        if tagli and tagli.get(_TAGLI[stile]):
            return str(tagli[_TAGLI[stile]])
    except Exception:
        pass
    return base[stile]


def _righe(testo: str, font: str, dimensione: float, larghezza: float) -> list[str]:
    from reportlab.pdfbase.pdfmetrics import stringWidth

    righe: list[str] = []
    for paragrafo in testo.split("\n"):
        corrente = ""
        for parola in paragrafo.split():
            prova = f"{corrente} {parola}".strip()
            if corrente and stringWidth(prova, font, dimensione) > larghezza:
                righe.append(corrente)
                corrente = parola
            else:
                corrente = prova
        righe.append(corrente)
    return righe


def _riquadro(att: Attestazione, larghezza: float) -> tuple[float, Any]:
    """Altezza del blocco e funzione che lo disegna a partire dall'alto (x, y_alto)."""
    corpo = _font(att.carattere_testo, "normale")
    titolo = _font(att.carattere_testo, "grassetto")
    firma = _font(att.carattere_firma, att.stile_firma)
    nota = _font(att.carattere_testo, "corsivo")
    d = att.dimensione_testo
    righe = _righe(att.testo_attestazione(), corpo, d, larghezza)
    interlinea = d * 1.35
    altezza = d * 1.6 + len(righe) * interlinea + interlinea * 2.2 + att.dimensione_firma * 1.4 + d * 1.3

    def disegna(tela: Any, x: float, y: float) -> None:
        from reportlab.pdfbase.pdfmetrics import stringWidth

        tela.setFont(titolo, d + 1)
        tela.drawString(x, y - d, "ATTESTAZIONE DI CONFORMITÀ")
        y -= d * 1.6 + interlinea * 0.4
        tela.setFont(corpo, d)
        for riga in righe:
            tela.drawString(x, y - d, riga)
            y -= interlinea
        y -= interlinea * 0.6
        tela.drawString(x, y - d, att.luogo_data())
        y -= interlinea * 1.6
        destra = x + larghezza
        testo_firma = f"Avv. {att.firma}"
        tela.setFont(firma, att.dimensione_firma)
        tela.drawString(destra - stringWidth(testo_firma, firma, att.dimensione_firma), y - att.dimensione_firma, testo_firma)
        y -= att.dimensione_firma * 1.4
        didascalia = "(sottoscrizione tramite firma digitale)"
        tela.setFont(nota, d * 0.85)
        tela.drawString(destra - stringWidth(didascalia, nota, d * 0.85), y - d * 0.85, didascalia)

    return altezza, disegna


def applica(pdf: bytes, att: Attestazione) -> bytes:
    """La copia con l'attestazione: pagine originali identiche, attestazione in coda o in fondo all'ultima."""
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas

    lettore = PdfReader(io.BytesIO(pdf))
    if lettore.is_encrypted:
        raise ValueError("Il PDF è protetto da password: sbloccalo prima di attestarne la conformità.")
    scrittore = PdfWriter(clone_from=lettore)
    ultima = scrittore.pages[-1]
    larghezza_pagina, altezza_pagina = float(ultima.mediabox.width), float(ultima.mediabox.height)
    margine = 56.7  # 2 cm
    larghezza = larghezza_pagina - 2 * margine
    altezza, disegna = _riquadro(att, larghezza)
    buffer = io.BytesIO()
    tela = canvas.Canvas(buffer, pagesize=(larghezza_pagina, altezza_pagina))
    if att.posizione == "fondo":
        from reportlab.lib.colors import white

        alto = margine * 0.6 + altezza + 10
        tela.setFillColor(white)
        tela.rect(margine - 8, margine * 0.6 - 4, larghezza + 16, altezza + 14, stroke=0, fill=1)
        tela.setFillColorRGB(0, 0, 0)
        disegna(tela, margine, alto)
    else:
        disegna(tela, margine, altezza_pagina - margine)
    tela.showPage()
    tela.save()
    sovrapposta = PdfReader(io.BytesIO(buffer.getvalue())).pages[0]
    if att.posizione == "fondo":
        ultima.merge_page(sovrapposta)
    else:
        scrittore.add_page(sovrapposta)
    uscita = io.BytesIO()
    scrittore.write(uscita)
    return uscita.getvalue()


def opzioni() -> dict[str, Any]:
    return {
        "tipi": [{"id": k, "etichetta": f"Copia informatica conforme {v}"} for k, v in TIPI.items()],
        "caratteri": [{"id": k, "etichetta": v[0]} for k, v in CARATTERI.items()],
        "stiliFirma": [{"id": s, "etichetta": s.replace("_", " ").capitalize()} for s in STILI],
        "posizioni": [{"id": k, "etichetta": v} for k, v in POSIZIONI.items()],
        "formula": FORMULA,
    }


__all__ = ["Attestazione", "CARATTERI", "FORMULA", "applica", "da_dati", "opzioni"]
