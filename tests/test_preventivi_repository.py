from __future__ import annotations

import json
from pathlib import Path

from flask import Flask

from pct.preventivi import GestionePreventivi, TipoVoce, VocePreventivo
from pct.compensi_a_tempo import COMPENSO_A_TEMPO_CODE
from web.services.assistente_studio_context import _preventivi_lines


def _build_gestore(tmp_path) -> GestionePreventivi:
    return GestionePreventivi(str(tmp_path / "preventivi.json"))


def _create_preventivo(gestore: GestionePreventivi):
    return gestore.crea_preventivo(
        id_cliente="cli-001",
        oggetto="Decreto ingiuntivo per recupero crediti",
        voci=[VocePreventivo(descrizione="Studio pratica", importo=1200.0, tipo=TipoVoce.ONORARIO)],
        creato_da="avv.rossi",
        id_pratica="decreto_ingiuntivo",
        area_pratica="Civile",
        tipo_compenso="Per fasi processuali (D.M. 55/2014)",
        tipo_procedimento="Procedimento monitorio",
        valore_controversia=18000.0,
        workflow_channel="ONLINE",
        anticipazioni_art15=43.5,
    )


def test_preventivi_repository_sync_exports_split_payload_and_clean_json(tmp_path):
    gestore = _build_gestore(tmp_path)
    preventivo = _create_preventivo(gestore)

    stats = gestore.statistiche_repository()
    assert stats["preventivi_workflow_states"] > 0
    assert stats["preventivi_field_map"] > 0
    assert stats["preventivi_rules"] > 0
    assert stats["preventivi_practice_catalog"] > 0
    assert stats["preventivi_records"] == 1
    assert Path(stats["json_path"]).exists()
    assert Path(stats["workflow_states_json_path"]).exists()
    assert Path(stats["field_map_json_path"]).exists()
    assert Path(stats["rules_json_path"]).exists()

    payload = gestore.repository_payload()
    assert payload["counts"]["preventivi"] == 1
    assert any(row["field_name"] == "tipo_compenso" for row in payload["field_map"]["preventivo"])
    assert any(row["rule_code"] == "calcolo_totale" for row in payload["rules"])
    assert any(row["practice_id"] == "decreto_ingiuntivo" for row in payload["practice_catalog"])

    record = payload["preventivi"][0]
    assert record["preventivo_id"] == preventivo.id
    assert "campi_mancanti_json" not in record
    assert "warning_json" not in record
    assert "piano_pagamenti" not in record

    workflow_payload = json.loads(Path(stats["workflow_states_json_path"]).read_text(encoding="utf-8"))
    assert workflow_payload["count"] == len(payload["workflow_states"])

    selection = gestore.select_best_preventivi_runtime("preventivo online decreto ingiuntivo")
    assert selection["best_preventivo"]["preventivo_id"] == preventivo.id

    practice_selection = gestore.select_best_pratiche_preventivo("decreto ingiuntivo monitorio")
    assert practice_selection["best_practice"]["practice_id"] == "decreto_ingiuntivo"


def test_preventivi_repository_tracks_conferimento_and_next_actions(tmp_path):
    gestore = _build_gestore(tmp_path)
    preventivo = _create_preventivo(gestore)

    gestore.registra_accettazione_preventivo(
        preventivo.id,
        workflow_channel="ONLINE",
        via="PORTALE_CLIENTE",
        auto_crea_conferimento=True,
        avvocato_referente="Avv. Rossi",
    )

    payload = gestore.repository_payload()
    record = next(row for row in payload["preventivi"] if row["preventivo_id"] == preventivo.id)
    conferimento = next(row for row in payload["conferimenti"] if row["id_preventivo"] == preventivo.id)

    assert record["stato"] == "ACCETTATO"
    assert record["next_action"] == "Raccogli la firma del conferimento."
    assert conferimento["next_action"] == "Raccogli la firma cliente sul conferimento."
    assert any("Firma cliente ancora da raccogliere." == item for item in conferimento["warning"])


def test_preventivi_repository_salva_campi_compenso_a_tempo_e_conferimento(tmp_path):
    gestore = _build_gestore(tmp_path)
    preventivo = gestore.crea_preventivo(
        id_cliente="cli-tempo",
        oggetto="Consulenza continuativa a tempo",
        voci=[VocePreventivo(descrizione="Compenso art. 22-bis", importo=1500.0, tipo=TipoVoce.ONORARIO)],
        creato_da="avv.rossi",
        tipo_compenso=COMPENSO_A_TEMPO_CODE,
        tariffa_oraria=250.0,
        ore_stimate=5.0,
        minuti_stimati=45,
        criterio_arrotondamento_orario="ora_frazione_oltre_30",
        ore_fatturabili_calcolate=6.0,
        compenso_orario_base=1500.0,
        massimale_ore=12.0,
        soglia_preapprovazione_ore=8.0,
        attivita_orarie_incluse="studio pratica; riunioni",
        attivita_orarie_escluse="trasferte",
        warning_compenso_orario=["Tariffa fuori range solo a scopo test"],
    )

    payload = gestore.repository_payload()
    record = next(row for row in payload["preventivi"] if row["preventivo_id"] == preventivo.id)

    assert record["tipo_compenso"] == COMPENSO_A_TEMPO_CODE
    assert record["criterio_arrotondamento_orario"] == "ora_frazione_oltre_30"
    assert record["minuti_stimati"] == 45
    assert record["ore_fatturabili_calcolate"] == 6.0
    assert record["compenso_orario_base"] == 1500.0
    assert record["massimale_ore"] == 12.0
    assert record["soglia_preapprovazione_ore"] == 8.0
    assert record["warning_compenso_orario"] == ["Tariffa fuori range solo a scopo test"]

    gestore.registra_accettazione_preventivo(
        preventivo.id,
        workflow_channel="STUDIO",
        via="FIRMA_CARTACEA",
        auto_crea_conferimento=True,
        avvocato_referente="Avv. Rossi",
    )
    payload = gestore.repository_payload()
    conferimento = next(row for row in payload["conferimenti"] if row["id_preventivo"] == preventivo.id)

    assert conferimento["tipo_compenso"] == COMPENSO_A_TEMPO_CODE
    assert conferimento["criterio_arrotondamento_orario"] == "ora_frazione_oltre_30"
    assert conferimento["massimale_ore"] == 12.0
    assert conferimento["soglia_preapprovazione_ore"] == 8.0
    assert conferimento["warning_compenso_orario"] == ["Tariffa fuori range solo a scopo test"]


def test_preventivi_lines_expose_repository_context_for_lex(tmp_path):
    gestore = _build_gestore(tmp_path)
    _create_preventivo(gestore)

    app = Flask(__name__)
    app.config["PREVENTIVI_DB"] = gestore.db_path

    with app.app_context():
        lines, sources = _preventivi_lines("mi aiuti con il preventivo online per decreto ingiuntivo")

    assert any("Repository preventivi strutturato" in line for line in lines)
    assert any("Regola di calcolo:" in line for line in lines)
    assert any("Step wizard consigliato:" in line for line in lines)
    assert any("Prossima azione:" in line for line in lines)
    assert any("Pratica del wizard utile:" in line for line in lines)

    preventivo_source = next(row for row in sources if str(row.get("id", "")).startswith("preventivo:"))
    assert preventivo_source["preventivo_state"] == "BOZZA"
    assert preventivo_source["wizard_step"]
    assert preventivo_source["next_action"]
    assert preventivo_source["preventivi_formula_rules"]
    assert "conferimento_collegato" in preventivo_source


def test_preventivi_repository_esporta_procedura_operativa(tmp_path):
    gestore = _build_gestore(tmp_path)
    preventivo = gestore.crea_preventivo(
        id_cliente="cli-002",
        oggetto="Impugnazione avviso di accertamento",
        voci=[VocePreventivo(descrizione="Compenso", importo=1300.0, tipo=TipoVoce.ONORARIO)],
        creato_da="avv.rossi",
        id_pratica="ricorso_tributario",
        area_pratica="Tributario",
        tipo_compenso="Per fasi processuali (D.M. 55/2014)",
        tipo_procedimento="Ricorso tributario di primo grado",
    )

    payload = gestore.repository_payload()
    record = next(row for row in payload["preventivi"] if row["preventivo_id"] == preventivo.id)

    assert record["procedura_operativa_codice"] == "PROC_TRIB_RIC_002"
    assert record["registro_operativo"] == "PTT_TRIBUTARIO"
    assert any(row["field_name"] == "procedura_operativa_nome" for row in payload["field_map"]["preventivo"])


def test_preventivi_repository_esporta_classificazioni_tassonomiche_aggiuntive(tmp_path):
    gestore = _build_gestore(tmp_path)
    preventivo = gestore.crea_preventivo(
        id_cliente="cli-003",
        oggetto="Preventivo con tassonomia multipla",
        voci=[VocePreventivo(descrizione="Compenso", importo=950.0, tipo=TipoVoce.ONORARIO)],
        creato_da="avv.rossi",
        id_pratica="decreto_ingiuntivo",
        area_pratica="Civile",
        tipo_compenso="Per fasi processuali (D.M. 55/2014)",
        tipo_procedimento="Procedimento monitorio",
        classificazioni_tassonomiche=[
            {
                "uid": "row-1",
                "area_tassonomica": "Giudiziale",
                "macro_area_tassonomica": "Diritto civile",
                "sottobranca_tassonomica": "Recupero crediti e monitori",
                "tipologia_pratica_id": "decreto_ingiuntivo",
                "tipologia_pratica_label": "Decreto ingiuntivo",
            }
        ],
    )

    payload = gestore.repository_payload()
    record = next(row for row in payload["preventivi"] if row["preventivo_id"] == preventivo.id)

    assert record["classificazioni_tassonomiche_count"] == 1
    assert record["classificazioni_tassonomiche"][0]["tipologia_pratica_id"] == "decreto_ingiuntivo"
    assert any(row["field_name"] == "classificazioni_tassonomiche" for row in payload["field_map"]["preventivo"])
