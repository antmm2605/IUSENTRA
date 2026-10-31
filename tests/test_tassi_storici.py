"""Serie storiche dei saggi legale (art. 1284 c.c.) e moratorio (D.Lgs. 231/2002).

I valori attesi sono letti dai testi ufficiali consultati il 31/10/2026
(decreti e comunicati in Gazzetta Ufficiale, art. 1284 c.c. e leggi su
Normattiva) e citati in ``pct/data/tassi_storici.json``.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from pct.normative_tables import FONTI_OPERATIVE, GestioneTabelleNormative, canonical_table_definitions

_DOMINI_UFFICIALI = ("https://www.gazzettaufficiale.it/", "https://www.normattiva.it/")


@pytest.fixture()
def norme(tmp_path):
    return GestioneTabelleNormative(str(tmp_path / "tabelle_normative.json"))


def _riga(norme, table_id: str, giorno: str) -> dict:
    target = date.fromisoformat(giorno)
    trovate = [
        r for r in norme.rows(table_id)
        if date.fromisoformat(r["start"]) <= target <= date.fromisoformat(r["end"])
    ]
    assert len(trovate) == 1, f"{table_id} {giorno}: {trovate}"
    return trovate[0]


@pytest.mark.parametrize("mode, inizio", [("legali", date(1942, 4, 19)), ("mora", date(2002, 8, 8))])
def test_serie_continua_senza_buchi_ne_sovrapposizioni(norme, mode, inizio):
    periodi = norme.interest_periods(mode)
    assert periodi[0].start == inizio
    assert periodi[-1].end >= date(2026, 12, 31)
    for precedente, successivo in zip(periodi, periodi[1:]):
        assert precedente.start <= precedente.end
        assert precedente.end + timedelta(days=1) == successivo.start, (precedente.label, successivo.label)


@pytest.mark.parametrize("mode", ["legali", "mora"])
def test_ogni_riga_ha_fonte_ufficiale_con_url(norme, mode):
    for periodo in norme.interest_periods(mode):
        assert periodo.source.url.startswith(_DOMINI_UFFICIALI), periodo.label
        if periodo.start.year < 2025:  # serie storica: data di consultazione dichiarata
            assert "2026-10-31" in periodo.source.note, periodo.label


def test_righe_annuali_per_il_divisore_365_366(norme):
    """Ogni riga del saggio legale sta in un solo anno solare (divisore 365/366)."""
    for riga in norme.rows("interesse_legale"):
        assert riga["start"][:4] == riga["end"][:4], riga
        assert riga.get("decreto") and riga.get("gazzetta"), riga


@pytest.mark.parametrize(
    "giorno, saggio, decreto, codice",
    [
        ("1990-12-15", 5.0, "Art. 1284 c.c.", "interesse_legale_cc_1942"),
        ("1990-12-16", 10.0, "L. 26 novembre 1990, n. 353", "interesse_legale_l353_1990"),
        ("1997-06-30", 5.0, "L. 23 dicembre 1996, n. 662", "interesse_legale_l662_1996"),
        ("2000-03-01", 2.5, "D.M. Tesoro 10 dicembre 1998", "interesse_legale_1999"),
        ("2001-07-01", 3.5, "D.M. Tesoro 11 dicembre 2000", "interesse_legale_2001"),
        ("2007-12-31", 2.5, "D.M. MEF 1 dicembre 2003", "interesse_legale_2004"),
        ("2013-05-10", 2.5, "D.M. MEF 12 dicembre 2011", "interesse_legale_2012"),
        ("2021-02-01", 0.01, "D.M. MEF 11 dicembre 2020", "interesse_legale_2021"),
        ("2023-01-01", 5.0, "D.M. MEF 13 dicembre 2022", "interesse_legale_2023"),
        ("2024-12-31", 2.5, "D.M. MEF 29 novembre 2023", "interesse_legale_2024"),
    ],
)
def test_saggio_legale_valori_chiave(norme, giorno, saggio, decreto, codice):
    riga = _riga(norme, "interesse_legale", giorno)
    assert riga["rate"] == saggio
    assert riga["decreto"].startswith(decreto)
    assert riga["source_code"] == codice


@pytest.mark.parametrize(
    "giorno, riferimento, tasso, codice",
    [
        ("2002-08-08", 3.35, 10.35, "mora_231_2003_h1"),
        ("2003-03-31", 2.85, 9.85, "mora_231_2003_h1"),
        ("2008-01-01", 4.20, 11.20, "mora_231_2008_h1"),
        ("2012-12-31", 1.00, 8.00, "mora_231_2012_h2"),
        ("2013-01-01", 0.75, 8.75, "mora_231_2013_h1"),
        ("2016-07-01", 0.0, 8.00, "mora_231_2016_h2"),
        ("2023-07-01", 4.00, 12.00, "mora_231_2023_h2"),
        ("2024-12-31", 4.25, 12.25, "mora_231_2024_h2"),
    ],
)
def test_mora_commerciale_valori_chiave(norme, giorno, riferimento, tasso, codice):
    riga = _riga(norme, "mora_commerciale", giorno)
    assert riga["reference_rate"] == riferimento
    assert riga["rate"] == tasso
    assert riga["source_code"] == codice
    assert riga["comunicato"].startswith("Comunicato MEF, G.U. Serie generale")


def test_maggiorazione_sette_punti_fino_al_2012_otto_dal_2013(norme):
    for riga in norme.rows("mora_commerciale"):
        attesa = 7.0 if riga["start"] < "2013-01-01" else 8.0
        assert riga["maggiorazione"] == attesa, riga
        assert riga["rate"] == pytest.approx(riga["reference_rate"] + attesa), riga


def test_source_codes_coprono_tutte_le_righe():
    definizioni = canonical_table_definitions()
    for table_id in ("interesse_legale", "mora_commerciale"):
        tabella = definizioni[table_id]
        codici = set(tabella["source_codes"])
        assert {r["source_code"] for r in tabella["rows"]} <= codici
        assert all(code in FONTI_OPERATIVE for code in codici)


def test_fonti_2024_2025_puntano_ai_decreti_giusti():
    assert "23A06669" in FONTI_OPERATIVE["interesse_legale_2024"].url
    assert "24A06721" in FONTI_OPERATIVE["interesse_legale_2025"].url


def test_calcolo_storico_senza_avviso_di_copertura_parziale(tmp_path):
    from pct.strumenti_legali import GestioneStrumentiLegali

    gestore = GestioneStrumentiLegali(str(tmp_path / "tabelle_normative.json"))
    esito = gestore.calcola_interessi(
        {"int_tipo": "legali", "int_capitale": "10000", "int_data_inizio": "2020-01-01", "int_data_fine": "2023-12-31"}
    )
    # 10.000 x (0,05% + 0,01% + 1,25% + 5%) per anni interi: 5 + 1 + 125 + 500.
    assert esito["total_interest"] == 631.0
    assert esito["covered_days"] == esito["days"] == 1461
    assert not any("parzialmente" in w for w in esito["warnings"])
