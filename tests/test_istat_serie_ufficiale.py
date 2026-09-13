"""Serie ISTAT FOI: valori pubblicati, cambio di base e riallineamento del seed.

I valori attesi sono quelli dei comunicati ISTAT pubblicati in Gazzetta
Ufficiale ai sensi dell'art. 81 L. 392/1978: G.U. n. 103 del 04/05/2023
(23A02556), n. 122 del 27/05/2024 (24A02620), n. 117 del 22/05/2025 (25A03038)
e n. 201 del 31/08/2026 (26A04494).
"""
from __future__ import annotations

import pytest

from pct.normative_tables import GestioneTabelleNormative


@pytest.fixture()
def norme(tmp_path):
    return GestioneTabelleNormative(db_path=str(tmp_path / "tabelle.json"))


# ── Valori pubblicati ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "anno,mese,atteso",
    [
        (2022, 12, 118.2),
        (2023, 1, 118.3),
        (2023, 12, 118.9),
        (2024, 1, 119.3),
        (2024, 12, 120.2),
        (2025, 1, 120.9),
        (2025, 3, 121.4),
        (2025, 12, 121.5),
    ],
)
def test_indici_foi_base_2015(norme, anno, mese, atteso):
    assert norme.istat_index_pubblicato("foi", anno, mese) == {"index": atteso, "base": 2015}


@pytest.mark.parametrize(
    "mese,atteso",
    [(1, 100.4), (2, 100.9), (3, 101.5), (4, 102.5), (5, 102.8), (6, 102.8)],
)
def test_indici_foi_2026_base_2025(norme, mese, atteso):
    assert norme.istat_index_pubblicato("foi", 2026, mese) == {"index": atteso, "base": 2025}


def test_la_serie_copre_da_marzo_2022_a_giugno_2026(norme):
    assert norme.istat_index("foi", 2022, 3) is not None
    assert norme.istat_index("foi", 2022, 2) is None
    ultimo = norme.istat_last_available("foi")
    assert (ultimo["year"], ultimo["month"]) == (2026, 6)


# ── Cambio di base 2015=100 → 2025=100 ───────────────────────────────────


def test_il_coefficiente_di_raccordo_e_quello_ufficiale(norme):
    assert norme.istat_coefficiente_raccordo("foi") == 1.214


def test_gli_indici_normalizzati_restano_confrontabili_a_cavallo_del_cambio_base(norme):
    """Dicembre 2025 e gennaio 2026 devono distare quanto la variazione reale."""
    dicembre = norme.istat_index("foi", 2025, 12)
    gennaio = norme.istat_index("foi", 2026, 1)
    assert dicembre == 121.5
    assert gennaio == pytest.approx(100.4 * 1.214, abs=0.001)
    # Salto mensile plausibile: senza raccordo sarebbe un crollo del 17 per cento.
    assert 0 < (gennaio / dicembre - 1) < 0.01


@pytest.mark.parametrize("mese,precedente", [(1, 120.9), (2, 121.1), (3, 121.4), (4, 121.3), (5, 121.2), (6, 121.3)])
def test_le_variazioni_annue_2026_tornano_sugli_indici_del_2025(norme, mese, precedente):
    """Controllo incrociato: indice 2026 raccordato = indice 2025 x (1 + variazione).

    La tolleranza tiene conto dei due arrotondamenti pubblicati: l'indice a un
    decimale sulla base 2025 (±0,05, che il raccordo porta a ±0,06) e la
    variazione annua a un decimale (±0,05 per cento, altri ±0,06 circa).
    """
    variazione = norme.istat_variation_yoy("foi", 2026, mese)
    atteso = precedente * (1 + variazione / 100.0)
    assert norme.istat_index("foi", 2026, mese) == pytest.approx(atteso, abs=0.15)


# ── Medie annue pubblicate ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "anno,atteso", [(2020, 102.3), (2021, 104.2), (2022, 112.6), (2023, 118.7), (2024, 119.7), (2025, 121.4)]
)
def test_medie_annue_pubblicate(norme, anno, atteso):
    assert norme.istat_media_annua("foi", anno) == atteso


def test_la_media_pubblicata_coincide_con_quella_dei_dodici_mesi(norme):
    mensili = [norme.istat_index("foi", 2025, m) for m in range(1, 13)]
    assert norme.istat_media_annua("foi", 2025) == pytest.approx(sum(mensili) / 12, abs=0.05)


# ── NIC: astensione invece di dati non verificabili ──────────────────────


def test_la_serie_nic_e_vuota_per_scelta(norme):
    assert norme.rows("istat_nic") == []
    assert "non e' pubblicato in Gazzetta Ufficiale" in norme.get_table("istat_nic")["description"]


# ── Riallineamento del seed sulle installazioni esistenti ────────────────


def test_una_correzione_del_seed_raggiunge_il_file_gia_salvato(tmp_path):
    """Senza riallineamento una correzione dei dati ufficiali non arriverebbe mai."""
    percorso = str(tmp_path / "tabelle.json")
    primo = GestioneTabelleNormative(db_path=percorso)
    tabella = primo._data["tables"]["istat_foi"]
    # Simula un'installazione ferma a dati sbagliati.
    versione = tabella["versions"][-1]
    versione["rows"] = [{"year": 2025, "month": 3, "index": 999.9, "variation_yoy": 0.0, "base": 2015}]
    versione["data_hash"] = "vecchio"
    tabella["rows"] = list(versione["rows"])
    primo._save()

    secondo = GestioneTabelleNormative(db_path=percorso)
    assert secondo.istat_index("foi", 2025, 3) == 121.4
    versioni = secondo._data["tables"]["istat_foi"]["versions"]
    assert versioni[-1]["origin"] == "sync_seed"
    assert versioni[0]["status"] == "superseded"


def test_il_riallineamento_non_tocca_le_tabelle_aggiornate_da_fuori(tmp_path):
    percorso = str(tmp_path / "tabelle.json")
    primo = GestioneTabelleNormative(db_path=percorso)
    primo.update_table_rows(
        "istat_foi",
        [{"year": 2026, "month": 7, "index": 103.0, "variation_yoy": 3.0, "base": 2025}],
        origin="sync",
    )
    secondo = GestioneTabelleNormative(db_path=percorso)
    assert secondo.istat_index("foi", 2026, 7) == pytest.approx(103.0 * 1.214, abs=0.001)
    assert secondo.istat_index("foi", 2025, 3) is None
