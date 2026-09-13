"""Dati che si aggiornano da soli nel tempo: valori, formule e avvisi di scadenza.

Le fonti sono i decreti e i comunicati pubblicati in Gazzetta Ufficiale:
- tassi soglia usura, D.M. MEF trimestrale (G.U. n. 149 del 30/06/2026 per il
  terzo trimestre 2026);
- tasso di riferimento per le transazioni commerciali, comunicato MEF
  semestrale ex art. 5 D.Lgs. 231/2002 (G.U. n. 163 del 16/07/2026);
- saggio degli interessi legali, D.M. MEF annuale (G.U. n. 289 del 13/12/2025);
- contributo unificato, art. 13 D.P.R. 115/2002.
"""
from __future__ import annotations

from datetime import date

import pytest

from pct.normative_tables import GestioneTabelleNormative
from pct.strumenti_legali import GestioneStrumentiLegali


@pytest.fixture()
def norme(tmp_path):
    return GestioneTabelleNormative(db_path=str(tmp_path / "tabelle.json"))


@pytest.fixture()
def gestore(tmp_path):
    return GestioneStrumentiLegali(normative_db_path=str(tmp_path / "strumenti.json"))


# ── Soglie antiusura ─────────────────────────────────────────────────────


def soglia_di_legge(tegm: float) -> float:
    """Art. 2, comma 4, L. 108/1996: TEGM aumentato di un quarto piu' quattro
    punti, con lo scarto dal tasso medio che non puo' superare otto punti."""
    return round(min(tegm * 1.25 + 4, tegm + 8), 4)


def test_ogni_soglia_usura_rispetta_la_formula_di_legge(norme):
    """Guardia permanente: una soglia trascritta male non passa questo controllo."""
    righe = norme.rows("tasso_usura")
    assert righe
    sbagliate = [
        (r["quarter"], r["category"], r["soglia"], soglia_di_legge(r["tegm"]))
        for r in righe
        if abs(soglia_di_legge(r["tegm"]) - r["soglia"]) > 0.0001
    ]
    assert not sbagliate, sbagliate


def test_il_tetto_degli_otto_punti_e_applicato_dove_serve(norme):
    """Sul revolving la formula sfonda il tetto: la soglia si ferma a TEGM + 8."""
    riga = next(
        r for r in norme.rows("tasso_usura")
        if r["quarter"] == "2026-Q3" and r["category"] == "credito_revolving"
    )
    assert riga["tegm"] == 16.21
    assert riga["soglia"] == 24.21
    assert riga["soglia"] < riga["tegm"] * 1.25 + 4


@pytest.mark.parametrize(
    "categoria,tegm,soglia",
    [
        ("aperture_credito_cc_fino_5000", 10.57, 17.2125),
        ("scoperti_senza_affidamento_oltre_1500", 15.88, 23.8500),
        ("credito_personale", 11.68, 18.6000),
        ("mutui_ipotecari_fisso", 4.21, 9.2625),
        ("mutui_ipotecari_variabile", 4.07, 9.0875),
        ("cessione_quinto_fino_15000", 13.87, 21.3375),
        ("altri_finanziamenti", 14.48, 22.1000),
    ],
)
def test_tassi_soglia_del_terzo_trimestre_2026(norme, categoria, tegm, soglia):
    riga = next(
        r for r in norme.rows("tasso_usura")
        if r["quarter"] == "2026-Q3" and r["category"] == categoria
    )
    assert (riga["tegm"], riga["soglia"]) == (tegm, soglia)


def test_il_terzo_trimestre_2026_copre_tutte_le_categorie(norme):
    per_trimestre = {}
    for r in norme.rows("tasso_usura"):
        per_trimestre.setdefault(r["quarter"], set()).add(r["category"])
    assert per_trimestre["2026-Q3"] == per_trimestre["2026-Q2"]
    assert len(per_trimestre["2026-Q3"]) == 24


def test_la_soglia_si_sceglie_in_base_alla_data(norme):
    aprile = norme.usura_soglia_per_categoria("credito_personale", date(2026, 4, 15))
    luglio = norme.usura_soglia_per_categoria("credito_personale", date(2026, 7, 15))
    assert aprile["quarter"] == "2026-Q2"
    assert luglio["quarter"] == "2026-Q3"
    assert not aprile.get("fuori_periodo")
    assert not luglio.get("fuori_periodo")


def test_una_data_scoperta_e_marcata_fuori_periodo(norme):
    riga = norme.usura_soglia_per_categoria("credito_personale", date(2027, 5, 1))
    assert riga["fuori_periodo"] is True


def test_lo_strumento_avvisa_quando_il_trimestre_non_copre_la_data(gestore):
    risultato = gestore.verifica_soglia_usura(
        {"usura_categoria": "credito_personale", "usura_tasso": 5, "usura_data": "2027-05-01"}
    )
    assert any("non copre la data" in a for a in risultato["warnings"])
    assert any("trimestre" in a for a in risultato["warnings"])


# ── Mora commerciale ─────────────────────────────────────────────────────


def test_la_mora_commerciale_e_il_riferimento_piu_otto_punti(norme):
    """Art. 5 D.Lgs. 231/2002: maggiorazione di otto punti percentuali."""
    for riga in norme.rows("mora_commerciale"):
        assert riga["rate"] == pytest.approx(riga["reference_rate"] + 8, abs=0.001), riga["label"]


def test_secondo_semestre_2026_della_mora_commerciale(norme):
    riga = next(r for r in norme.rows("mora_commerciale") if r["start"] == "2026-07-01")
    assert (riga["reference_rate"], riga["rate"], riga["end"]) == (2.40, 10.40, "2026-12-31")


def test_i_semestri_della_mora_non_lasciano_buchi(norme):
    righe = sorted(norme.rows("mora_commerciale"), key=lambda r: r["start"])
    for prima, dopo in zip(righe, righe[1:]):
        assert date.fromisoformat(dopo["start"]) == date.fromisoformat(prima["end"]) + __import__("datetime").timedelta(days=1)


# ── Saggio degli interessi legali ────────────────────────────────────────


def test_saggio_legale_2026_e_quello_del_decreto(norme):
    riga = next(r for r in norme.rows("interesse_legale") if r["start"] == "2026-01-01")
    assert riga["rate"] == 1.60
    assert riga["decreto"] == "D.M. MEF 10 dicembre 2025"
    assert "289" in riga["gazzetta"]


def test_gli_anni_del_saggio_legale_non_lasciano_buchi(norme):
    righe = sorted(norme.rows("interesse_legale"), key=lambda r: r["start"])
    for prima, dopo in zip(righe, righe[1:]):
        assert date.fromisoformat(dopo["start"]) == date.fromisoformat(prima["end"]) + __import__("datetime").timedelta(days=1)


# ── Contributo unificato ─────────────────────────────────────────────────


def test_scaglioni_del_contributo_unificato_civile(norme):
    """Importi dell'art. 13, comma 1, D.P.R. 115/2002."""
    attesi = [(1100.0, 43.0), (5200.0, 98.0), (26000.0, 237.0), (52000.0, 518.0),
              (260000.0, 759.0), (520000.0, 1214.0), (None, 1686.0)]
    righe = [(r.get("max_value"), r["amount"]) for r in norme.rows("contributo_unificato_civile")]
    assert righe == attesi


# ── Copertura dei periodi ────────────────────────────────────────────────


@pytest.mark.parametrize("tabella", ["tasso_usura", "mora_commerciale", "interesse_legale"])
def test_le_tabelle_a_periodi_sanno_dire_fin_dove_arrivano(norme, tabella):
    copertura = norme.periodo_coperto(tabella, date(2027, 6, 1))
    assert copertura["coperto"] is False
    assert copertura["ultimo_fine"]
    assert copertura["righe"] > 0


def test_una_tabella_vuota_non_risulta_coperta(norme):
    assert norme.periodo_coperto("istat_nic")["coperto"] is False


# ── Onorari degli ausiliari ──────────────────────────────────────────────


def test_le_vacazioni_dichiarano_il_decreto_e_l_adeguamento_triennale(norme):
    righe = norme.rows("ctu_vacazioni")
    assert {r["kind"]: r["amount"] for r in righe} == {"prima": 14.68, "successiva": 8.15}
    assert all(r["decreto"] == "D.M. 30 maggio 2002" for r in righe)
    assert "art. 54" in next(r for r in righe if r["kind"] == "prima")["note"]
