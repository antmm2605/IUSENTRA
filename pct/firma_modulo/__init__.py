"""La firma del cliente appoggiata nel campo giusto di un modulo PDF.

Oggi il portale clienti timbra la firma in un riquadro a coordinate fisse, in
fondo alla pagina. Su un modulo con i campi firma — un'autocertificazione, una
procura alle liti, un ricorso — la firma finisce cosi' lontano dal rigo
«Firma», e il modulo sembra non firmato.

Questo modulo trova i campi firma veri (i widget AcroForm), sceglie quello
**visibile** fra le impaginazioni sovrapposte che i moduli ministeriali
portano, e ci appoggia sopra il tratto del cliente alla misura di una firma a
penna. Poi appiattisce il modulo: un modulo che resta compilabile puo' essere
cambiato dopo la firma, e un documento del genere non prova nulla (art. 20
D.Lgs. 82/2005, integrita' del documento informatico).

Base normativa: art. 20 CAD per l'integrita'; art. 21 CAD per il valore della
sottoscrizione elettronica semplice, che il portale gia' governa con inviti,
verifica dell'identita' e registro delle prove.
"""

from __future__ import annotations

from .anteprima import anteprima_pagine
from .applica import applica_firme
from .campi import campi_firmabili, campi_testo, zona_firma
from .modello import CampoFirma
from .portale import campi_firma_del_documento, firma_nei_campi, tratto_trasparente
from .taratura import ETICHETTE, RE_FIRMA
from .tratto import rifila_firma

VERSIONE_FIRMA_MODULO = "2026.09.18.firma-modulo.v1"

__all__ = [
    "ETICHETTE",
    "RE_FIRMA",
    "VERSIONE_FIRMA_MODULO",
    "CampoFirma",
    "anteprima_pagine",
    "applica_firme",
    "campi_firma_del_documento",
    "campi_firmabili",
    "campi_testo",
    "firma_nei_campi",
    "rifila_firma",
    "tratto_trasparente",
    "zona_firma",
]
