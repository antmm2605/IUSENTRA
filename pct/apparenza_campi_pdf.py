"""L'apparenza disegnata di un campo compilato.

Scrivere il valore in un campo di modulo non basta: il PDF tiene il valore
(``/V``) e, separatamente, il disegno di come quel valore appare sul foglio
(``/AP``). Un campo con il valore e senza disegno si stampa **vuoto** in molti
lettori — e per un modulo che lo studio deposita a un organismo e' un difetto
che si scopre dall'altra parte.

PyMuPDF genera il disegno da solo. Le librerie con licenza permissiva no:
vanno scritti a mano. Non e' complicato — un'apparenza di campo di testo e' un
flusso di contenuto breve e di forma fissa — ma va fatto, e va verificato
guardando i pixel, non il modello.

Qui si costruisce quel flusso. L'aggancio all'annotazione sta in chi compila.
"""

from __future__ import annotations

#: Margine interno fra il bordo della casella e il testo, in punti.
MARGINE = 2.0

#: Quota dell'altezza della casella occupata dal carattere quando il modulo
#: non dichiara un corpo (``0 Tf`` significa "decidi tu").
QUOTA_AUTOMATICA = 0.72

#: Corpo minimo e massimo quando si decide da soli.
CORPO_MINIMO = 4.0
CORPO_MASSIMO = 24.0


def _stringa_pdf(testo: str) -> bytes:
    """Il testo come stringa letterale PDF, con le parentesi protette.

    Una parentesi non protetta chiude la stringa in anticipo e il flusso
    diventa illeggibile: il campo si stampa vuoto o il lettore rifiuta la
    pagina. Fuori da WinAnsi il carattere si sostituisce invece di far
    saltare tutto il modulo.
    """
    grezzo = str(testo or "")
    fuori = bytearray(b"(")
    for carattere in grezzo:
        try:
            byte = carattere.encode("cp1252")
        except UnicodeEncodeError:
            byte = b"?"
        if byte in (b"(", b")", b"\\"):
            fuori += b"\\"
        fuori += byte
    fuori += b")"
    return bytes(fuori)


def corpo_carattere(altezza: float, *, dichiarato: float = 0.0) -> float:
    """Il corpo da usare: quello dichiarato dal modulo, o uno che ci sta."""
    if dichiarato and dichiarato > 0:
        return float(dichiarato)
    corpo = max(1.0, float(altezza)) * QUOTA_AUTOMATICA
    return max(CORPO_MINIMO, min(corpo, CORPO_MASSIMO))


def apparenza_testo(
    testo: str,
    *,
    larghezza: float,
    altezza: float,
    carattere: str = "Helv",
    corpo: float = 0.0,
    colore: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bytes:
    """Il flusso di contenuto che disegna il valore dentro la casella.

    La casella e' l'origine: le coordinate sono relative al suo riquadro, non
    alla pagina. Il testo viene ritagliato al bordo, cosi' un valore piu' lungo
    della casella non invade il resto del foglio.
    """
    larghezza = max(1.0, float(larghezza))
    altezza = max(1.0, float(altezza))
    punti = corpo_carattere(altezza, dichiarato=corpo)
    # Linea di base: il testo appoggia poco sopra il fondo della casella,
    # centrato in verticale su quello che resta.
    base = max(MARGINE, (altezza - punti) / 2.0 + punti * 0.22)
    rosso, verde, blu = (max(0.0, min(1.0, float(c))) for c in colore)
    nome_carattere = str(carattere or "Helv").lstrip("/") or "Helv"
    return b"".join(
        [
            b"/Tx BMC\n q\n",
            f"0 0 {larghezza:.4f} {altezza:.4f} re\nW\nn\n".encode("ascii"),
            b"BT\n",
            f"{rosso:.4f} {verde:.4f} {blu:.4f} rg\n".encode("ascii"),
            f"/{nome_carattere} {punti:.4f} Tf\n".encode("ascii"),
            f"{MARGINE:.4f} {base:.4f} Td\n".encode("ascii"),
            _stringa_pdf(testo),
            b" Tj\nET\nQ\nEMC\n",
        ]
    )


def _riquadro(annotazione) -> tuple[float, float]:
    """Larghezza e altezza della casella, dalle sue coordinate sulla pagina."""
    rettangolo = [float(v) for v in annotazione.get("/Rect", [0, 0, 0, 0])]
    if len(rettangolo) != 4:
        return (0.0, 0.0)
    x0, y0, x1, y1 = rettangolo
    return (abs(x1 - x0), abs(y1 - y0))


def _corpo_dichiarato(annotazione, modulo) -> tuple[float, str]:
    """Corpo e nome del carattere che il modulo dichiara in ``/DA``.

    Il modulo puo' dichiararlo sulla singola casella o una volta per tutte
    nell'AcroForm. `0 Tf` significa "decidi tu".
    """
    testo = str(annotazione.get("/DA") or "")
    if not testo and modulo is not None:
        testo = str(modulo.get("/DA") or "")
    pezzi = testo.split()
    for indice, pezzo in enumerate(pezzi):
        if pezzo == "Tf" and indice >= 2:
            nome = pezzi[indice - 2].lstrip("/")
            try:
                return (float(pezzi[indice - 1]), nome or "Helv")
            except ValueError:
                return (0.0, nome or "Helv")
    return (0.0, "Helv")


def _riferimento_carattere(writer, nome: str):
    """Il carattere da usare nell'apparenza, riusando quello del modulo se c'e'."""
    from pypdf.generic import DictionaryObject, NameObject

    try:
        modulo = writer._root_object.get("/AcroForm")
        risorse = (modulo or {}).get("/DR") or {}
        caratteri = risorse.get("/Font") or {}
        if f"/{nome}" in caratteri:
            return caratteri.raw_get(f"/{nome}")
    except Exception:
        pass
    # Nessun carattere dichiarato dal modulo: se ne aggiunge uno standard,
    # che ogni lettore di PDF conosce senza doverlo incorporare.
    carattere = DictionaryObject()
    carattere[NameObject("/Type")] = NameObject("/Font")
    carattere[NameObject("/Subtype")] = NameObject("/Type1")
    carattere[NameObject("/BaseFont")] = NameObject("/Helvetica")
    carattere[NameObject("/Encoding")] = NameObject("/WinAnsiEncoding")
    return writer._add_object(carattere)


def applica_apparenza_testo(writer, annotazione, testo: str) -> bool:
    """Disegna il valore dentro la casella e lo aggancia all'annotazione.

    Restituisce ``False`` se la casella non ha misure utilizzabili: in quel
    caso il valore resta scritto nel modulo senza disegno, e chi chiama deve
    saperlo invece di crederlo fatto.
    """
    from pypdf.generic import (
        ArrayObject,
        DecodedStreamObject,
        DictionaryObject,
        FloatObject,
        NameObject,
    )

    larghezza, altezza = _riquadro(annotazione)
    if larghezza <= 0 or altezza <= 0:
        return False
    modulo = None
    try:
        modulo = writer._root_object.get("/AcroForm")
    except Exception:
        modulo = None
    corpo, nome_carattere = _corpo_dichiarato(annotazione, modulo)
    flusso = apparenza_testo(
        testo,
        larghezza=larghezza,
        altezza=altezza,
        carattere=nome_carattere,
        corpo=corpo,
    )

    disegno = DecodedStreamObject()
    disegno.set_data(flusso)
    disegno[NameObject("/Type")] = NameObject("/XObject")
    disegno[NameObject("/Subtype")] = NameObject("/Form")
    disegno[NameObject("/FormType")] = FloatObject(1)
    disegno[NameObject("/BBox")] = ArrayObject(
        [FloatObject(0), FloatObject(0), FloatObject(larghezza), FloatObject(altezza)]
    )
    caratteri = DictionaryObject()
    caratteri[NameObject(f"/{nome_carattere}")] = _riferimento_carattere(writer, nome_carattere)
    risorse = DictionaryObject()
    risorse[NameObject("/Font")] = caratteri
    disegno[NameObject("/Resources")] = risorse

    apparenza = DictionaryObject()
    apparenza[NameObject("/N")] = writer._add_object(disegno)
    annotazione[NameObject("/AP")] = apparenza
    return True


__all__ = [
    "CORPO_MASSIMO",
    "CORPO_MINIMO",
    "MARGINE",
    "QUOTA_AUTOMATICA",
    "apparenza_testo",
    "applica_apparenza_testo",
    "corpo_carattere",
]
