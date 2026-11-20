"""Numeri d'articolo con suffissi lunghi e numerazione a punto (artt. 281-undecies, 281-terdecies, 473-bis.11 c.p.c.)."""
from __future__ import annotations

import pytest

from web.services.ricerca_legale_norma_citata import _numero_articolo, estremi


@pytest.mark.parametrize("etichetta,numero", [
    ("Art. 281-undecies.", "281undecies"),
    ("Art. 281-terdecies.", "281terdecies"),
    ("Art. 281-ter.", "281ter"),
    ("Art. 473-bis.11.", "473bis.11"),
    ("Art. 473-bis.", "473bis"),
    ("Art. 1385.", "1385"),
])
def test_numero_articolo(etichetta, numero):
    assert _numero_articolo(etichetta)[0] == numero


def test_estremi_con_numerazione_a_punto():
    e = estremi("art. 473-bis.11 r.d. 1443/1940")
    assert e and e["articolo"] == "473bis.11"
