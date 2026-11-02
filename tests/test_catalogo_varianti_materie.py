"""Dieci documenti diversi per ogni tipologia delle materie estese (richiesta dell'avvocato del 02/11/2026).

Ogni regola d'identità delle aree `estesa_*` ha, oltre al documento di prova, dieci varianti inventate e
diverse tra loro (forma del titolo, ufficio, caso concreto, lunghezza): tutte devono finire sulla stessa
voce e sezione del documento di prova, con confidenza alta.
"""

from __future__ import annotations

import importlib

import pytest

from tests.test_document_catalog_titoli import _cataloga

MODULI = (
    "penale", "pubblico", "tributi_lavoro", "persone", "impresa", "settori", "fonti_superiori",
)
MINIMO_VARIANTI = 10


def _dati():
    righe = []
    for nome in MODULI:
        modulo = importlib.import_module(f"tests.dati_catalogo_titoli_estesa_{nome}")
        campioni = modulo.CAMPIONI
        varianti = getattr(modulo, "VARIANTI", {})
        for regola in sorted(campioni):
            righe.append((nome, regola, campioni[regola], tuple(varianti.get(regola, ()))))
    return righe


DATI = _dati()


@pytest.mark.parametrize(("area", "regola", "campione", "varianti"), DATI, ids=[r[1] for r in DATI])
def test_dieci_varianti_diverse_per_tipologia(area, regola, campione, varianti):
    assert len(varianti) >= MINIMO_VARIANTI, f"{area}/{regola}: {len(varianti)} varianti"
    normalizzate = {" ".join(v.lower().split()) for v in varianti}
    assert len(normalizzate) == len(varianti), f"{regola}: varianti ripetute"
    _, label, sezione = campione
    for indice, testo in enumerate(varianti):
        esito = _cataloga(testo, f"{regola}_{indice}.pdf")
        assert esito.status == "proposed", f"{regola} variante {indice}: {esito.reason}"
        assert (esito.document_label, esito.document_section) == (label, sezione), f"{regola} variante {indice}"
        assert esito.confidence >= 90
