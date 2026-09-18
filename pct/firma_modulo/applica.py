"""La firma applicata nel campo giusto, e il modulo appiattito.

Appiattire e' necessario: un modulo che resta compilabile puo' essere
modificato dopo la firma, e un documento del genere non prova nulla
(art. 20 CAD, integrita' del documento informatico)."""

from __future__ import annotations

from typing import Optional

try:  # PyMuPDF e' dichiarato in requirements.txt
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    try:
        import fitz
    except ImportError:
        fitz = None  # type: ignore[assignment]

from .taratura import QUOTA_LARGHEZZA_MAX, SCALA_FIRMA, STACCO_DAL_RIGO
from .campi import _nascosto, zona_firma
from .tratto import _da_base64, rifila_firma


# ---------------------------------------------------------------------------
# Applicazione
# ---------------------------------------------------------------------------

def _riquadro_proporzionato(zona: fitz.Rect, proporzione: float) -> fitz.Rect:
    """
    Riquadro interno a `zona` che conserva le proporzioni della firma, la
    tiene un po' piu' piccola dello spazio disponibile e la centra sul campo.
    """
    larghezza, altezza = zona.width, zona.height
    if proporzione <= 0:
        return zona

    if larghezza / altezza > proporzione:      # sovrabbonda in larghezza
        nuova_larghezza = altezza * proporzione
        nuova_altezza = altezza
    else:
        nuova_larghezza = larghezza
        nuova_altezza = larghezza / proporzione

    nuova_larghezza *= SCALA_FIRMA
    nuova_altezza *= SCALA_FIRMA

    massimo = larghezza * QUOTA_LARGHEZZA_MAX
    if nuova_larghezza > massimo:
        nuova_altezza *= massimo / nuova_larghezza
        nuova_larghezza = massimo

    centro_x = (zona.x0 + zona.x1) / 2
    x0 = centro_x - nuova_larghezza / 2
    y1 = zona.y1 - STACCO_DAL_RIGO
    return fitz.Rect(x0, y1 - nuova_altezza, x0 + nuova_larghezza, y1)


def applica_firme(
    percorso_in: str,
    firme: dict[str, str | bytes],
    percorso_out: Optional[str] = None,
    *,
    testi: Optional[dict[str, str]] = None,
    appiattisci: bool = True,
) -> bytes:
    """
    Scrive i testi nei campi, incolla le firme nei rispettivi riquadri e
    (se richiesto) appiattisce il modulo: il PDF che riceve lo studio non e'
    piu' modificabile e non porta con se' i campi vuoti delle altre varianti.
    """
    doc = fitz.open(percorso_in)
    try:
        # 1. testi
        if testi:
            for pagina in doc:
                for w in pagina.widgets():
                    if w.field_name in testi and not _nascosto(doc, w):
                        w.field_value = str(testi[w.field_name])
                        w.update()

        # 2. firme
        preparate = {
            nome: rifila_firma(_da_base64(dato)) for nome, dato in firme.items()
        }
        applicate: set[str] = set()

        for pagina in doc:
            for w in list(pagina.widgets()):
                nome = w.field_name or ""
                if nome not in preparate or nome in applicate:
                    continue
                if _nascosto(doc, w):
                    continue
                png, proporzione = preparate[nome]
                riquadro = _riquadro_proporzionato(
                    zona_firma(fitz.Rect(w.rect), pagina), proporzione
                )
                pagina.insert_image(riquadro, stream=png, keep_proportion=True, overlay=True)
                applicate.add(nome)

        mancanti = set(preparate) - applicate
        if mancanti:
            raise ValueError(
                "campi firma non trovati o non visibili: " + ", ".join(sorted(mancanti))
            )

        # 3. appiattimento
        if appiattisci:
            _appiattisci(doc, da_rimuovere=set(preparate))

        dati = doc.tobytes(deflate=True, garbage=3)
        if percorso_out:
            with open(percorso_out, "wb") as f:
                f.write(dati)
        return dati
    finally:
        doc.close()


def _appiattisci(doc: fitz.Document, da_rimuovere: Optional[set[str]] = None) -> None:
    """
    Fissa i campi dentro il contenuto della pagina e toglie i widget.

    ATTENZIONE: in moduli come l'autocertificazione CU la grafica (tabella,
    diciture "FIRMA" e "IL DICHIARANTE", righini) e' disegnata dall'aspetto
    di widget-pulsante a tutta pagina, uno per variante di impaginazione.
    Cancellare i widget vuoti farebbe sparire meta' del modulo: si rimuovono
    solo quelli dei campi firma appena timbrati, che non disegnano nulla e
    lascerebbero una toppa bianca sopra la firma.
    """
    nomi = da_rimuovere or set()
    if nomi:
        for pagina in doc:
            for w in list(pagina.widgets()):
                if (w.field_name or "") in nomi:
                    try:
                        pagina.delete_widget(w)
                    except Exception:
                        pass

    try:
        doc.bake(widgets=True)     # PyMuPDF >= 1.24: i campi diventano contenuto
        return
    except AttributeError:
        pass

    for pagina in doc:                      # ripiego per versioni precedenti
        for w in list(pagina.widgets()):
            try:
                pagina.delete_widget(w)
            except Exception:
                pass
    try:
        doc.xref_set_key(doc.pdf_catalog(), "AcroForm", "null")
    except Exception:
        pass
