from __future__ import annotations

import json
from pathlib import Path


REGISTRY = Path("docs/specs/ministero/fonti_ufficiali/registro_fonti_ufficiali_2026-06-02.json")


def test_registro_fonti_ufficiali_ha_file_locali_e_regole_applicate():
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    source_files = {item["id"]: item for item in payload["source_files"]}

    assert len(source_files) >= 30
    for source in source_files.values():
        local_path = Path(source["local_path"])
        assert local_path.exists(), f"Fonte ufficiale non salvata localmente: {source['id']}"
        assert local_path.stat().st_size > 0, f"Fonte ufficiale vuota: {source['id']}"
        assert source.get("official_url", "").startswith("https://")
        assert source.get("sha256_short")

    for rule in payload["rules"]:
        assert rule["source_ids"], f"Regola senza fonte: {rule['id']}"
        for source_id in rule["source_ids"]:
            assert source_id in source_files, f"Regola {rule['id']} cita fonte non registrata: {source_id}"
        assert rule["software_modules"], f"Regola senza modulo software: {rule['id']}"
        assert rule["tests"], f"Regola senza test collegato: {rule['id']}"
        assert rule["rule"], f"Regola senza contenuto: {rule['id']}"


def test_registro_fonti_ufficiali_copre_cu_pagamenti_deontologia_e_portali():
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rule_ids = {rule["id"] for rule in payload["rules"]}

    required = {
        "cu_art13_calcolo_base",
        "cu_art13_riduzioni_50",
        "cu_art13_maggiorazioni",
        "cu_art13_importi_speciali",
        "pst_uffici_codici_deposito",
        "pst_schemi_canali",
        "pst_pagamenti_rt_xml",
        "pat_siga_profilo_pagamenti",
        "ptt_sigit_profilo_cut",
        "giustizia_map_competenza",
        "cdf_art25bis_equo_compenso",
        "cdf_art27_informativa_cliente",
        "gdpr_art30_registro_trattamenti",
        "gdpr_studio_legale_registro_avvocato",
        "fatturapa_sdi_xml_obbligatorio",
        "fatturapa_sdi_esiti_monitoraggio",
        "impostazioni_sdi_canale_configurabile",
    }
    assert required.issubset(rule_ids)
