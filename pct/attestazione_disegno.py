"""Caratteri e disegno dei due testi dell'attestazione: il blocco dell'attestazione e la firma testo.

Il blocco dell'attestazione va a capo dentro la larghezza del suo riquadro; se nell'altezza non ci
sta, il carattere si riduce fino a un minimo leggibile. La firma testo (nome e cognome dell'avvocato
sotto «Vera ed autentica») si scrive centrata nel suo riquadro, ridotta solo se non ci entra.
I caratteri si incorporano nel PDF: equivalenti metrici aperti dei caratteri d'ufficio
(pct.caratteri_reali) e due corsivi calligrafici con licenza SIL OFL 1.1 (pct/data/fonts/firma).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

CARATTERI: dict[str, tuple[str, str, dict[str, str]]] = {
    "arial": ("Arial", "liberation sans",
              {"normale": "Helvetica", "grassetto": "Helvetica-Bold", "corsivo": "Helvetica-Oblique", "grassetto_corsivo": "Helvetica-BoldOblique"}),
    "times": ("Times New Roman", "liberation serif",
              {"normale": "Times-Roman", "grassetto": "Times-Bold", "corsivo": "Times-Italic", "grassetto_corsivo": "Times-BoldItalic"}),
    "calibri": ("Calibri", "carlito",
                {"normale": "Helvetica", "grassetto": "Helvetica-Bold", "corsivo": "Helvetica-Oblique", "grassetto_corsivo": "Helvetica-BoldOblique"}),
    "cambria": ("Cambria", "caladea",
                {"normale": "Times-Roman", "grassetto": "Times-Bold", "corsivo": "Times-Italic", "grassetto_corsivo": "Times-BoldItalic"}),
    "courier": ("Courier New", "liberation mono",
                {"normale": "Courier", "grassetto": "Courier-Bold", "corsivo": "Courier-Oblique", "grassetto_corsivo": "Courier-BoldOblique"}),
}
#: Corsivi calligrafici per la firma testo: un solo taglio, lo stile non si applica.
CALLIGRAFICI: dict[str, tuple[str, str]] = {
    "great_vibes": ("Great Vibes (calligrafico)", "GreatVibes-Regular.ttf"),
    "allura": ("Allura (calligrafico)", "Allura-Regular.ttf"),
}
STILI = ("normale", "grassetto", "corsivo", "grassetto_corsivo")
_TAGLI = {"normale": "normal", "grassetto": "bold", "corsivo": "italic", "grassetto_corsivo": "bold_italic"}
_CARTELLA_CALLIGRAFICI = Path(__file__).resolve().parent / "data" / "fonts" / "firma"
DIMENSIONE_MINIMA = 7.0
INTERLINEA = 1.08


def font(carattere: str, stile: str = "normale") -> str:
    """Il nome del carattere registrato in ReportLab (incorporato) o il carattere base equivalente."""
    if carattere in CALLIGRAFICI:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        nome = f"IuFirma-{carattere}"
        if nome not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(nome, str(_CARTELLA_CALLIGRAFICI / CALLIGRAFICI[carattere][1])))
        return nome
    _etichetta, famiglia, base = CARATTERI[carattere]
    try:
        from pct.caratteri_reali import registro

        tagli = registro().get(famiglia)
        if tagli and tagli.get(_TAGLI[stile]):
            return str(tagli[_TAGLI[stile]])
    except Exception:
        pass
    return base[stile]


def a_capo(testo: str, nome_font: str, dimensione: float, larghezza: float) -> list[str]:
    from reportlab.pdfbase.pdfmetrics import stringWidth

    righe: list[str] = []
    for paragrafo in testo.split("\n"):
        corrente = ""
        for parola in paragrafo.split():
            prova = f"{corrente} {parola}".strip()
            if corrente and stringWidth(prova, nome_font, dimensione) > larghezza:
                righe.append(corrente)
                corrente = parola
            else:
                corrente = prova
        righe.append(corrente)
    return righe


@dataclass(frozen=True)
class Blocco:
    larghezza: float
    altezza: float
    dimensione: float
    disegna: Callable[[Any, float, float], None]


def blocco_testo(paragrafi: list[str], nome_font: str, dimensione: float, larghezza: float) -> Blocco:
    """Paragrafi allineati a sinistra, a capo dentro `larghezza`; si disegna dall'angolo in alto a sinistra."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    righe = [riga for paragrafo in paragrafi for riga in a_capo(paragrafo, nome_font, dimensione, larghezza)]
    passo = dimensione * INTERLINEA

    def disegna(tela: Any, x: float, y: float) -> None:
        tela.setFont(nome_font, dimensione)
        for riga in righe:
            y -= passo
            tela.drawString(x, y + dimensione * 0.2, riga)

    occupata = max((stringWidth(riga, nome_font, dimensione) for riga in righe), default=0.0)
    return Blocco(larghezza=occupata, altezza=passo * len(righe), dimensione=dimensione, disegna=disegna)


def blocco_nel_riquadro(paragrafi: list[str], nome_font: str, dimensione: float, larghezza: float, altezza: float) -> Blocco:
    """Il blocco alla dimensione scelta o, se non entra nell'altezza, alla più grande che ci sta."""
    corrente = dimensione
    while True:
        blocco = blocco_testo(paragrafi, nome_font, corrente, larghezza)
        if blocco.altezza <= altezza or corrente <= DIMENSIONE_MINIMA:
            break
        corrente = max(DIMENSIONE_MINIMA, corrente - 0.5)
    if blocco.altezza > altezza + 0.5:
        raise ValueError("Il riquadro dell'attestazione è troppo piccolo per il testo: disegnalo più grande.")
    return blocco


def firma_nel_riquadro(testo: str, nome_font: str, dimensione: float, larghezza: float, altezza: float) -> Blocco:
    """Una riga centrata nel riquadro, ridotta solo se è più larga o più alta del riquadro."""
    from reportlab.pdfbase.pdfmetrics import getAscentDescent, stringWidth

    corrente = min(dimensione, altezza / 1.1)
    while corrente > DIMENSIONE_MINIMA and stringWidth(testo, nome_font, corrente) > larghezza:
        corrente -= 0.5
    corrente = max(corrente, DIMENSIONE_MINIMA)
    occupata = stringWidth(testo, nome_font, corrente)
    sale, scende = getAscentDescent(nome_font, corrente)

    def disegna(tela: Any, x: float, y: float) -> None:
        tela.setFont(nome_font, corrente)
        base = y - altezza / 2 - (sale + scende) / 2
        tela.drawString(x + max(0.0, (larghezza - occupata) / 2), base, testo)

    return Blocco(larghezza=occupata, altezza=altezza, dimensione=corrente, disegna=disegna)


__all__ = ["CALLIGRAFICI", "CARATTERI", "STILI", "Blocco", "blocco_nel_riquadro", "blocco_testo", "firma_nel_riquadro", "font"]
