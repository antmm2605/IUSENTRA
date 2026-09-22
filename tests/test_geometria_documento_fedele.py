"""Il rettangolo che prende il posto di quello di PyMuPDF.

Questi test fissano il comportamento su cui il resto di `documento_fedele`
faceva conto: aree sempre positive, rettangoli che si sfiorano senza
intersecarsi, rettangoli degeneri che non intersecano niente. Sono le
condizioni al contorno, quelle che decidono se una cella di tabella esce
sottolineata o no.
"""

from __future__ import annotations

import dataclasses

import pytest

from pct.documento_fedele.geometria import Riquadro


def test_si_costruisce_dalle_coordinate_da_una_tupla_e_da_un_altro_riquadro():
    dalle_coordinate = Riquadro(1, 2, 3, 4)
    dalla_tupla = Riquadro((1, 2, 3, 4))
    dalla_copia = Riquadro(dalle_coordinate)
    assert dalle_coordinate == dalla_tupla == dalla_copia
    assert tuple(dalle_coordinate) == (1.0, 2.0, 3.0, 4.0)


def test_un_riquadro_vuole_quattro_coordinate():
    with pytest.raises(ValueError, match="quattro coordinate"):
        Riquadro((1, 2, 3))


def test_le_misure_restano_positive_con_gli_angoli_invertiti():
    dritto = Riquadro(10, 20, 40, 60)
    storto = Riquadro(40, 60, 10, 20)
    assert storto.width == dritto.width == 30
    assert storto.height == dritto.height == 40
    assert storto.get_area() == dritto.get_area() == 1200


def test_due_riquadri_sovrapposti_si_intersecano():
    a, b = Riquadro(0, 0, 10, 10), Riquadro(5, 5, 20, 20)
    assert a.intersects(b)
    assert a & b == Riquadro(5, 5, 10, 10)
    assert (a & b).get_area() == 25


def test_due_riquadri_che_si_sfiorano_su_un_bordo_non_si_intersecano():
    sinistra, destra = Riquadro(0, 0, 5, 5), Riquadro(5, 0, 10, 5)
    assert not sinistra.intersects(destra)
    assert (sinistra & destra).get_area() == 0


def test_un_riquadro_degenere_non_interseca_niente():
    pagina = Riquadro(0, 0, 100, 100)
    filo = Riquadro(30, 10, 30, 90)
    assert filo.get_area() == 0
    assert filo.vuoto
    assert not filo.intersects(pagina)
    assert not pagina.intersects(filo)


def test_due_riquadri_lontani_danno_un_intersezione_di_area_zero():
    a, b = Riquadro(0, 0, 10, 10), Riquadro(200, 200, 210, 210)
    assert not a.intersects(b)
    assert (a & b).get_area() == 0


def test_contiene_guarda_i_bordi_inclusi():
    fuori = Riquadro(0, 0, 100, 100)
    assert fuori.contiene(Riquadro(10, 10, 20, 20))
    assert fuori.contiene(fuori)
    assert not fuori.contiene(Riquadro(90, 90, 110, 110))


def test_unito_prende_il_piu_piccolo_che_li_contiene_entrambi():
    a, b = Riquadro(0, 10, 30, 20), Riquadro(25, 5, 40, 12)
    assert a.unito(b) == Riquadro(0, 5, 40, 20)


def test_la_sovrapposizione_e_una_frazione_di_questo_riquadro():
    piccolo = Riquadro(0, 0, 10, 10)
    meta = Riquadro(5, 0, 100, 10)
    assert piccolo.sovrapposizione(meta) == pytest.approx(0.5)
    assert piccolo.sovrapposizione(piccolo) == pytest.approx(1.0)
    assert piccolo.sovrapposizione(Riquadro(500, 500, 510, 510)) == 0.0


def test_la_sovrapposizione_di_un_riquadro_senza_area_e_zero():
    assert Riquadro(3, 3, 3, 9).sovrapposizione(Riquadro(0, 0, 100, 100)) == 0.0


def test_il_riquadro_non_si_puo_modificare():
    uno = Riquadro(1, 2, 3, 4)
    with pytest.raises(dataclasses.FrozenInstanceError):
        uno.x0 = 99  # type: ignore[misc]
