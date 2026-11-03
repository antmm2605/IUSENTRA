"""Calcolo Tariffario (/compensi-forensi): procedimento, area e fase arrivano davvero al motore.

Base normativa: D.M. 10 marzo 2014, n. 55 (testo vigente dal 23/10/2022, D.M. 147/2022),
art. 2 (spese generali 15%), art. 4 c. 1 (valori medi delle tabelle), art. 5 c. 6
(cause di valore indeterminabile); Tabella 2 (giudizi ordinari davanti al Tribunale).
"""

from __future__ import annotations

from collections import Counter

from pct.tariffario import ComplessitaStimata, Fase, Grado, Materia, calcola_compenso
from pct.tariffario_catalogo import tariffario_profile_rows, tariffario_rule_rows
from web.services.react_compensi_forensi_bridge import (
    build_react_compensi_forensi_payload,
    calculate_react_compensi_forensi,
)


class _Tabelle:
    def tariffario_profili(self):
        return tariffario_profile_rows()

    def tariffario_regole(self):
        return tariffario_rule_rows()

    def tariffario_audit(self):
        return []

    def tariffario_riferimenti(self):
        return []


def _calcola(**payload):
    result, status = calculate_react_compensi_forensi(
        get_normative_tables=_Tabelle,
        get_utenti=None,
        current_user=None,
        payload=payload,
        ip_address="",
    )
    meta = {row["label"]: row["value"] for row in (result.get("result") or {}).get("metadata", [])}
    return result, status, meta


def test_procedimenti_unici_tutte_le_regole_senza_etichette_doppie():
    payload = build_react_compensi_forensi_payload(get_normative_tables=_Tabelle)
    proceedings = payload["parameters"]["proceedings"]
    values = [row["value"] for row in proceedings]
    assert len(values) == len(set(values)) == len({row["rule_code"] for row in tariffario_rule_rows()})
    doppie = [key for key, n in Counter((row["area"], row["label"]) for row in proceedings).items() if n > 1]
    assert doppie == []
    assert "minima" not in {row["value"] for row in payload["parameters"]["complexities"]}


def test_procedimento_tribunale_usa_tabella_2_con_importi_dm_147_2022():
    result, status, meta = _calcola(
        area="Civile di cognizione",
        procedimento="civile_cognizione_primo_grado",
        valore_controversia=30000,
        complessita="media",
    )
    assert status == 200, result
    assert meta["Tabella"].startswith("A2 ")
    assert meta["Scaglione"] == "Da € 26.000 a € 52.000"
    # 1.701 + 1.204 + 1.806 + 2.905 = 7.616; + 15% spese generali = 8.758,40
    rows = {row["id"]: row["value"] for row in result["result"]["economic"]["rows"]}
    assert rows["imponibile"] == "€ 8.758,40"


def test_procedimento_di_altra_area_rifiutato():
    result, status, _ = _calcola(
        area="Amministrativo / TAR-CdS",
        procedimento="civile_gdp",
        valore_controversia=30000,
        complessita="media",
    )
    assert status == 400
    assert "procedimento" in result["errors"]


def test_fase_scritta_a_testo_riconosciuta_o_rifiutata():
    result, status, meta = _calcola(
        area="Civile di cognizione",
        procedimento="civile_cognizione_primo_grado",
        fase="Fase di studio",
        valore_controversia=30000,
        complessita="media",
    )
    assert status == 200, result
    assert meta["Fasi"] == "Studio"
    result, status, _ = _calcola(
        area="Civile di cognizione",
        procedimento="civile_cognizione_primo_grado",
        fase="fase inesistente",
        valore_controversia=30000,
    )
    assert status == 400
    assert "Fasi ammesse" in result["message"]


def test_indeterminabile_di_particolare_importanza_entro_520000():
    risultato = calcola_compenso(
        Materia.CIVILE_COGN,
        Grado.TRIBUNALE,
        0,
        [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA, Fase.DECISIONALE],
        complessita=ComplessitaStimata.MOLTO_ALTA,
    )
    assert risultato.scaglione == "Da € 260.000 a € 520.000"
    assert "art. 5, comma 6" in risultato.note


def test_primo_scaglione_non_si_chiama_indeterminabile():
    risultato = calcola_compenso(
        Materia.CIVILE_COGN,
        Grado.TRIBUNALE,
        0,
        [Fase.STUDIO],
        complessita=ComplessitaStimata.MEDIA,
    )
    assert "indeterminabile" not in risultato.scaglione
    assert "art. 5, comma 6" in risultato.note


def test_profili_con_la_stessa_tabella_si_distinguono_nel_catalogo():
    from web.services.react_compensi_forensi_bridge import _safe_record

    primo = _safe_record({"profile_code": "civile_tribunale", "table_label": "Tabella 2 - Giudizi civili ordinari", "grado_input_value": "Tribunale", "summary": "Giudizi civili ordinari di primo grado."}, 1)
    appello = _safe_record({"profile_code": "civile_appello_tribunale", "table_label": "Tabella 2 - Giudizi civili ordinari", "grado_input_value": "Tribunale", "summary": "Appello civile contro sentenza del Giudice di Pace."}, 2)
    assert primo["title"] == appello["title"]
    assert primo["subtitle"] != appello["subtitle"]
    assert appello["subtitle"].startswith("Tribunale · ")
