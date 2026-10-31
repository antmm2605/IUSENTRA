"""Collaudo sulla norma del calcolatore «Contributi Cassa Forense».

Fonti consultate il 31/10/2026 su cassaforense.it: Regolamento unico della previdenza
forense (G.U. S.G. n. 238 del 10/10/2024), tabella ufficiale dei contributi minimi,
note illustrative Mod. 5/2026 e Vademecum gennaio 2025.
"""
from __future__ import annotations

import pytest

from pct.calcolatori.collaudo import CASI, esito_caso
from pct.normative_tables import FONTI_OPERATIVE, GestioneTabelleNormative
from pct.strumenti_legali import GestioneStrumentiLegali


@pytest.fixture()
def gestore(tmp_path):
    return GestioneStrumentiLegali(normative_db_path=str(tmp_path / "tabelle_normative.json"))


def _calcola(gestore, anno, reddito, volume, posizione="ordinaria"):
    return gestore.calcola_contributi_cassa_forense(
        {"cf_anno": str(anno), "cf_reddito": str(reddito), "cf_compensi": str(volume), "cf_posizione": posizione}
    )


def test_casi_di_collaudo_presenti_e_superati(gestore):
    casi = CASI["contributi_cassa_forense"]
    assert len(casi) >= 4
    assert all(caso.verificato_il == "2026-10-31" for caso in casi)
    falliti = [motivo for caso in casi if (motivo := esito_caso(gestore, "contributi_cassa_forense", caso))]
    assert falliti == []


def test_tabella_2025_e_2026_coincide_con_la_tabella_ufficiale(tmp_path):
    righe = GestioneTabelleNormative(str(tmp_path / "t.json")).rows("contributi_cassa_forense")
    per_anno = {(int(r["year"]), r["tipo"]): r for r in righe}
    s25, i25, m25 = per_anno[(2025, "soggettivo")], per_anno[(2025, "integrativo")], per_anno[(2025, "maternita_assistenza")]
    assert (s25["aliquota"], s25["minimo_eur"], s25["minimo_ridotto_eur"], s25["copertura_eur"], s25["tetto_eur"]) == (
        16.0, 2750.0, 1375.0, 17188.0, 130000.0)
    assert (i25["aliquota"], i25["minimo_eur"], i25["minimo_ridotto_eur"]) == (4.0, 350.0, 175.0)
    assert m25["minimo_eur"] == 57.65
    s26, i26, m26 = per_anno[(2026, "soggettivo")], per_anno[(2026, "integrativo")], per_anno[(2026, "maternita_assistenza")]
    assert (s26["aliquota"], s26["minimo_eur"], s26["minimo_ridotto_eur"], s26["copertura_eur"], s26["tetto_eur"]) == (
        17.0, 2790.0, 1395.0, 16412.0, 131800.0)
    assert (i26["minimo_eur"], i26["minimo_ridotto_eur"]) == (355.0, 177.5)
    assert m26["status"] == "da_definire"
    # Oltre il tetto 3%, pensionati 12% (art. 30, cc. 1 e 3)
    assert {r["aliquota_oltre_tetto"] for r in (s25, s26)} == {3.0}
    assert {r["aliquota_pensionati"] for r in (s25, s26)} == {12.0}


def test_esempio_ufficiale_vademecum_minimo_ridotto(gestore):
    """Vademecum gennaio 2025, tavola 14, caso 1: reddito 30.000 con minimo ridotto → 3.425."""
    risultato = _calcola(gestore, 2025, 30000, 0, "agevolata")
    assert risultato["soggettivo_minimo"] == 1375.0
    assert risultato["soggettivo_eccedenza"] == 2050.0
    assert risultato["soggettivo_totale"] == 3425.0


def test_2026_senza_maternita_ufficiale_avvisa_e_non_inventa(gestore):
    risultato = _calcola(gestore, 2026, 10000, 10000)
    maternita = {r["tipo"]: r for r in risultato["contributi"]}["maternita_assistenza"]
    assert maternita["status"] == "da_definire" and maternita["calcolato"] == 0.0
    assert risultato["totale_provvisorio"] is True
    assert any("da definire" in avviso for avviso in risultato["warnings"])
    assert risultato["totale"] == 3190.0


@pytest.mark.parametrize("anno", [2024, 2020])
def test_anni_del_regolamento_previgente_rifiutati(gestore, anno):
    with pytest.raises(ValueError, match="previgente"):
        _calcola(gestore, anno, 50000, 50000)


def test_anno_non_pubblicato_rifiutato_senza_ripiego(gestore):
    with pytest.raises(ValueError, match="non risultano pubblicati"):
        _calcola(gestore, 2027, 50000, 50000)


def test_posizione_sconosciuta_rifiutata(gestore):
    with pytest.raises(ValueError):
        _calcola(gestore, 2025, 50000, 50000, "inventata")


def test_arrotondamento_all_euro_e_soglia_dieci_euro(gestore):
    sopra = _calcola(gestore, 2025, 17300, 0)  # 16% x 112 = 17,92 → 18 euro > 10
    assert sopra["soggettivo_eccedenza"] == 18.0
    sotto = _calcola(gestore, 2025, 17250, 0)  # 16% x 62 = 9,92 → 10 euro, non dovuto
    assert sotto["soggettivo_eccedenza"] == 0.0


def test_fonti_citano_regolamento_note_e_tabella(gestore):
    risultato = _calcola(gestore, 2025, 50000, 60000)
    codici = {fonte["code"] for fonte in risultato["sources"]}
    assert {"cassa_forense_regolamento_unico", "cassa_forense_note_mod5_2026", "cassa_forense_contributi_2026"} <= codici
    assert FONTI_OPERATIVE["cassa_forense_regolamento_unico"].url.endswith("regolamento-unico-previdenza-forense.pdf")
    assert "2026-10-31" in FONTI_OPERATIVE["cassa_forense_contributi_2026"].note


def test_minimo_integrativo_senza_ripiego_inventato(tmp_path):
    norme = GestioneTabelleNormative(str(tmp_path / "t.json"))
    assert norme.cassa_forense_minimo_integrativo(2025) == 350.0
    assert norme.cassa_forense_minimo_integrativo(2026) == 355.0
    assert norme.cassa_forense_minimo_integrativo(2030) == 0.0
    assert norme.cassa_forense_aliquota_integrativa(2026) == 4.0


def test_risultato_applicazioni_elenca_le_voci(gestore):
    from pct.applicazioni_runtime import build_tool_result

    risultato = _calcola(gestore, 2025, 50000, 60000)
    resa = build_tool_result("contributi_cassa_forense", risultato)
    testo = repr(resa)
    assert "Contributo soggettivo 2025" in testo and "Contributo di maternità 2025" in testo
