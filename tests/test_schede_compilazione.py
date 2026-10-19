"""Schede di compilazione dei 5 atti pilota."""
import json
from pathlib import Path

from pct.schede_compilazione import FONTI, campi_da_chiedere, carica_schede, scheda_per_template

CATALOGO = {t["id"] for t in json.loads(Path("pct/template_atti_catalogo_data/catalogo_master.json").read_text(encoding="utf-8"))["template"]}


def test_cinque_schede_coerenti_col_catalogo():
    schede = carica_schede()
    assert sorted(schede) == ["CIV_ORD_001", "CIV_ORD_009", "ESE_001", "LAV_001", "MON_001"]
    for s in schede.values():
        assert set(s["template"]) <= CATALOGO
        assert s["base_normativa"] and s["scrive_lex"] and s["astensione"]
        for campo in s["campi"]:
            assert campo["fonte"]["tipo"] in FONTI
            for norma in campo.get("norma", []) + s["base_normativa"]:
                assert norma["atto"] and norma["articolo"]


def test_domande_solo_per_i_dati_mancanti():
    s = scheda_per_template("MON_002")
    assert s["id"] == "MON_001"
    valori = {"difensore": "Avv. Rossi", "procura": "procura.pdf", "data_luogo": "Bari", "ricorrente": "Alfa srl",
              "debitore": "Beta srl", "fonte_credito": "contratto", "capitale": "1000", "prova_scritta": "fatture.pdf"}
    assert [m["campo"] for m in campi_da_chiedere(s, valori)] == ["interessi"]
