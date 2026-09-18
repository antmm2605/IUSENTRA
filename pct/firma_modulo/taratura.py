"""Le misure con cui una firma si appoggia sul rigo di un modulo.

Una firma a penna non sta schiacciata dentro la casella: sale sopra il rigo
con le maiuscole e scende sotto con i tratti discendenti, e non tocca mai i
bordi. Le quote sono dichiarate qui perche' si possano leggere e correggere."""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Parametri
# ---------------------------------------------------------------------------

#: altezza massima della firma, in punti (1 pt = 1/72"). 40 pt ~ 14 mm:
#: e' l'altezza di una firma a penna su un rigo di modulo.
ALTEZZA_MAX_PT = 40.0

#: quanto la firma puo' debordare in alto rispetto al riquadro del campo:
#: una firma reale sale sopra il rigo, non resta schiacciata dentro la casella
SFORAMENTO_SUPERIORE = 3.2

#: quota dell'altezza totale che resta sopra il rigo (il resto scende sotto,
#: come i tratti discendenti di una firma a penna)
QUOTA_SOPRA_IL_RIGO = 0.78

#: aria lasciata fra la firma e il testo prestampato sopra il campo
ARIA_DALL_ETICHETTA = 2.0

#: margini interni orizzontali, in punti
MARGINE_X = 4.0

#: la firma non riempie tutto lo spazio disponibile: resta un po' piu' piccola,
#: come una firma a penna che non tocca mai i bordi del rigo
SCALA_FIRMA = 0.80

#: larghezza massima della firma in quota della larghezza del campo
QUOTA_LARGHEZZA_MAX = 0.78

#: distacco fra il fondo della firma e il rigo, in punti
STACCO_DAL_RIGO = 0.8

#: la firma appoggia qui sopra il fondo del campo
APPOGGIO_Y = 1.5

#: bit Hidden nel flag /F di un'annotazione
BIT_NASCOSTO = 2

#: nomi di campo riconosciuti come firma, con l'etichetta da mostrare al cliente
ETICHETTE = {
    "firma_dichiarazione": "Firma",
    "firma_privacy": "Il dichiarante",
    "ricorrente": "Ricorrente",
    "firma": "Firma",
    "firma_richiedente": "Firma del richiedente",
}

RE_FIRMA = re.compile(r"firma|ricorrent|sottoscri|signature", re.I)
