"""Registro delle letture: che cosa il gestionale ha già letto e che cosa no.

Ogni lettore (OCR, indice documentale, catalogo, indice di ricerca, RAG locale,
presidio PEC, presidio economico, lettura del fascicolo) chiede al registro
quali oggetti del fascicolo — documenti, PEC, allegati PEC — sono cambiati
dall'ultima lettura, legge solo quelli e registra l'esito con l'impronta
SHA-256 del contenuto. Un fascicolo con impronta invariata non produce
letture. Le anomalie sono i dati letti che i controlli deterministici
giudicano dubbi (le date prima di tutto): restano aperte finché l'avvocato le
conferma o le corregge.

Base normativa della cura documentale: art. 3 D.M. 44/2011 (integrità dei
documenti informatici) e art. 20 CAD D.Lgs. 82/2005 (impronta del documento).
"""

from __future__ import annotations

from .lettori import LETTORI, etichetta_lettore, versione_lettore
from .modello import (
    Anomalia,
    Lettura,
    Oggetto,
    StatoFascicolo,
    StatoLettore,
    impronta_inventario,
    impronta_oggetto,
)
from .repository import RegistroLetture, RegistroLettureError

VERSIONE_REGISTRO = "2026.09.15.registro-letture.v1"

__all__ = [
    "VERSIONE_REGISTRO",
    "LETTORI",
    "Anomalia",
    "Lettura",
    "Oggetto",
    "RegistroLetture",
    "RegistroLettureError",
    "StatoFascicolo",
    "StatoLettore",
    "etichetta_lettore",
    "impronta_inventario",
    "impronta_oggetto",
    "versione_lettore",
]
