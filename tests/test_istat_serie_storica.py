"""Serie storica ISTAT FOI: continuità, basi e raccordo fra le basi.

La serie decide ogni rivalutazione monetaria del gestionale. Un buco impedisce
il calcolo; un indice attribuito alla base sbagliata lo fa sbagliare di un
fattore intero senza che nulla lo segnali. Questi test guardano la serie come
dato, non il codice che la legge.

I valori sono quelli dei comunicati ISTAT pubblicati in Gazzetta Ufficiale ai
sensi dell'art. 81 L. 392/1978 e dell'art. 54 L. 449/1997.
"""

from __future__ import annotations

import pytest

from pct.normative_tables import GestioneTabelleNormative


@pytest.fixture(scope="module")
def norme(tmp_path_factory):
    return GestioneTabelleNormative(str(tmp_path_factory.mktemp("norme") / "tabelle.json"))


def _mesi(norme) -> list[tuple[int, int]]:
    return [
        (anno, mese)
        for anno in range(2005, 2030)
        for mese in range(1, 13)
        if norme.istat_index_pubblicato("foi", anno, mese)
    ]


def test_la_serie_parte_dal_2011_e_non_ha_buchi(norme):
    mesi = _mesi(norme)
    assert mesi[0] == (2011, 1)
    atteso = []
    anno, mese = mesi[0]
    while (anno, mese) <= mesi[-1]:
        atteso.append((anno, mese))
        mese += 1
        if mese == 13:
            anno, mese = anno + 1, 1
    assert mesi == atteso, "la serie mensile deve essere continua"
    assert len(mesi) >= 186


def test_ogni_mese_dichiara_la_base_a_cui_si_riferisce(norme):
    """Un indice senza base non e' confrontabile con nessun altro."""
    for anno, mese in _mesi(norme):
        pubblicato = norme.istat_index_pubblicato("foi", anno, mese)
        assert pubblicato["base"] in {2010, 2015, 2025}, f"{anno}-{mese}: base {pubblicato['base']}"


@pytest.mark.parametrize(
    ("anno", "mese", "base"),
    [(2011, 1, 2010), (2015, 12, 2010), (2016, 1, 2015), (2025, 12, 2015), (2026, 1, 2025)],
)
def test_le_basi_cambiano_nei_mesi_giusti(norme, anno, mese, base):
    """Base 2010 fino a dicembre 2015, 2015 fino a dicembre 2025, poi 2025."""
    assert norme.istat_index_pubblicato("foi", anno, mese)["base"] == base


def test_i_coefficienti_di_raccordo_sono_quelli_pubblicati(norme):
    """G.U. n. 65 del 18/03/2016 per 2010→2015; il 2025 era gia' in tabella."""
    defaults = norme.get_table("istat_foi").get("defaults") or {}
    assert defaults["coefficienti_raccordo"]["2010_2015"] == 1.071
    assert defaults["coefficienti_raccordo"]["2015_2025"] == 1.214
    assert "18/03/2016" in defaults["fonti_raccordo"]["2010_2015"]


def test_il_raccordo_riporta_ogni_base_alla_base_2015(norme):
    # 107,1 in base 2010 e' il 2015: riportato alla base 2015 deve valere 100.
    assert norme.istat_fattore_verso_2015("foi", 2015) == 1.0
    assert round(107.1 * norme.istat_fattore_verso_2015("foi", 2010), 2) == 100.0
    assert round(100.0 * norme.istat_fattore_verso_2015("foi", 2025), 3) == 121.4


def test_la_serie_normalizzata_non_salta_ai_cambi_di_base(norme):
    """Nessuno scalino artificiale fra un mese e il successivo.

    Senza il raccordo, dicembre 2015 (107,0 in base 2010) e gennaio 2016 (99,7
    in base 2015) mostrerebbero un crollo del 7%: e' il fattore di base, non
    l'inflazione. La soglia del 4% lascia passare il massimo salto realmente
    avvenuto nella serie — ottobre 2022, +3,3% sulla crisi energetica — e
    ferma qualunque scalino di conversione, che sarebbe almeno del 7%.
    """
    mesi = _mesi(norme)
    for precedente, corrente in zip(mesi, mesi[1:]):
        prima = norme.istat_index("foi", *precedente)
        dopo = norme.istat_index("foi", *corrente)
        variazione = abs(dopo / prima - 1)
        assert variazione < 0.04, f"salto anomalo fra {precedente} e {corrente}: {variazione:.1%}"


def test_la_serie_cresce_nel_lungo_periodo(norme):
    """Controllo di senso: dal 2011 al 2026 i prezzi sono saliti."""
    assert norme.istat_index("foi", 2026, 6) > norme.istat_index("foi", 2011, 1)


@pytest.mark.parametrize(
    ("anno", "mese", "indice"),
    [
        (2011, 1, 101.2),
        (2011, 10, 103.6),   # rettificato: la Gazzetta riporta anche 107,6 per refuso
        (2012, 3, 105.2),    # rettificato: la Gazzetta riporta anche 105,7 per refuso
        (2015, 12, 107.0),
        (2016, 1, 99.7),
        (2022, 1, 107.7),
        (2022, 3, 109.9),
    ],
)
def test_valori_puntuali_dai_comunicati_in_gazzetta(norme, anno, mese, indice):
    assert norme.istat_index_pubblicato("foi", anno, mese)["index"] == indice


def test_la_rivalutazione_attraversa_il_cambio_di_base(norme):
    """Rivalutare dal 2012 al 2026 deve dare un risultato plausibile.

    E' il caso che prima non si poteva calcolare: la serie partiva dal 2022.
    """
    from pct.strumenti_legali import GestioneStrumentiLegali

    esito = GestioneStrumentiLegali().calcola_rivalutazione_istat({
        "riv_importo": "10000",
        "riv_tipo": "foi",
        "riv_anno_base": "2012", "riv_mese_base": "1",
        "riv_anno_fine": "2026", "riv_mese_fine": "6",
    })
    # Dal 2012 al 2026 l'indice FOI e' cresciuto di circa un quinto.
    assert 11500 <= esito["importo_rivalutato"] <= 13500
    assert esito["importo_rivalutato"] > esito["importo_originale"]
