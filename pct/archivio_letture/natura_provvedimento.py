"""Il documento è un provvedimento del giudice? Tipo salvato, catalogo o testo.

Il tipo del documento nasce spesso dal nome del file (un PDF scaricato dal
portale diventa «Allegato», un provvedimento comunicato via PEC «Atto
giudiziario»): fermarsi al tipo lasciava fuori sentenze vere. Qui il tipo è
una delle tre prove; le altre sono l'etichetta del catalogo dal contenuto e il
testo stesso della sentenza (art. 132 c.p.c.; art. 88 c.p.a.). L'appartenenza
della sentenza al fascicolo resta una verifica separata e obbligatoria
(R.G., parte e ufficio nell'intestazione).
"""
from __future__ import annotations

from typing import Any

TIPI_PROVVEDIMENTO = frozenset({"SENTENZA", "ORDINANZA", "DECRETO", "VERBALE"})
# Tipi assegnati dal nome del file o dal canale, che non dicono che cosa contiene il documento.
TIPI_GENERICI = frozenset({"", "ALLEGATO", "ALTRO", "ATTO_GIUDIZIARIO", "COMUNICAZIONE", "DEPOSITO_PCT"})


def tipo_normalizzato(tipo: Any) -> str:
    valore = getattr(tipo, "value", tipo)
    return str(valore or "").strip().upper().split(".")[-1]


def etichetta_di_sentenza(etichetta: Any = "", natura: Any = "") -> bool:
    """Catalogo dal contenuto: «Sentenza», «Provvedimento - sentenza», natura «provvedimento»."""
    testo = f"{etichetta or ''} {natura or ''}".casefold()
    return "sentenza" in testo or "provvedimento" in testo


def testo_di_sentenza(testo: str) -> bool:
    """La sentenza si riconosce dal testo: intestazione, data e dispositivo."""
    if not str(testo or "").strip():
        return False
    from pct.fascicolo_sentenza_economica import analyze_sentenza_tribunale_text

    try:
        return bool(analyze_sentenza_tribunale_text(str(testo)).found)
    except Exception:
        return False


def e_provvedimento(tipo: Any = "", *, testo: str = "", etichetta_catalogo: Any = "", natura_catalogo: Any = "") -> bool:
    if tipo_normalizzato(tipo) in TIPI_PROVVEDIMENTO or etichetta_di_sentenza(etichetta_catalogo, natura_catalogo):
        return True
    return tipo_normalizzato(tipo) in TIPI_GENERICI and testo_di_sentenza(testo)


__all__ = ["TIPI_GENERICI", "TIPI_PROVVEDIMENTO", "e_provvedimento", "etichetta_di_sentenza", "testo_di_sentenza", "tipo_normalizzato"]
