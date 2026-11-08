"""Il precedente richiamato dalle altre pronunce della rosa sale nella classifica (es. Cass. lav. 29961/2023)."""

import sqlite3

from pct.giurisprudenza_richiami import conta_richiami, precedenti_richiamati_prima


def _righe():
    return [{"id": i, "numero_sentenza": n, "anno_sentenza": a} for i, (n, a) in enumerate(
        [("24319", 2026), ("24317", 2026), ("01567", 2026), ("09396", 2022), ("07254", 2024), ("29961", 2023)], start=1)]


def _db(testi):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE sentenze (id INTEGER PRIMARY KEY, testo_integrale TEXT)")
    conn.executemany("INSERT INTO sentenze VALUES (?, ?)", testi.items())
    return conn


def test_forme_di_citazione_riconosciute_senza_confondere_numeri_e_date():
    testi = {1: "come statuito con la sentenza n. 29961 del 27 ottobre 2023.", 2: "quantostatuito con la sentenza n. 29961 del 27ottobre 2023",
             3: "hanno preso le mosse dalla sentenza n. 29961 del 2023", 4: "v. Cass. n. 129961/2023 e n. 2996/2023", 5: "n. 29961/2022"}
    assert conta_richiami(_righe(), testi)[6] == 3


def test_precedente_citato_da_piu_pronunce_sale_in_cima():
    conn = _db({1: "sentenza n. 29961 del 27 ottobre 2023", 2: "sentenza n. 29961 del 27ottobre 2023", 3: "sentenza n. 29961 del 2023",
                4: "altro", 5: "altro", 6: "testo lungo del precedente"})
    ordine = [r["numero_sentenza"] for r in precedenti_richiamati_prima(conn, _righe())]
    assert ordine[0] == "29961" and ordine[1:] == ["24319", "24317", "01567", "09396", "07254"]


def test_un_solo_richiamo_non_cambia_l_ordine():
    conn = _db({1: "sentenza n. 29961/2023", 2: "altro", 3: "altro", 4: "altro", 5: "altro", 6: "altro"})
    assert precedenti_richiamati_prima(conn, _righe()) == _righe()
