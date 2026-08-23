from __future__ import annotations

from pct.legal_intelligence import FONTI_UFFICIALI, official_telematic_source_ids
from pct.telematico_truth_registry import build_capability_truth_registry


def test_registro_collega_capacita_a_fonti_ufficiali_e_stato_acquisizione() -> None:
    registry = build_capability_truth_registry(
        [{"capability_id": "pst_consultazione_fascicoli", "label": "Consultazione PST"}],
        [{"source_id": "pst_servizi_web", "status": "ok", "changed": "false", "last_check": "2026-08-23T10:00:00+02:00"}],
        [
            {"source_id": "pst_giustizia", "nome": "PST Giustizia", "official_url": "https://pst.giustizia.it/PST/"},
            {"source_id": "pst_servizi_web", "nome": "Documentazione servizi web", "official_url": "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4571"},
        ],
    )

    references = registry["entries"][0]["references"]
    assert [item["id"] for item in references] == ["pst_giustizia", "pst_servizi_web"]
    assert references[1]["status"] == "presidiata"
    assert references[1]["href"].startswith("https://pst.giustizia.it/")
    assert references[0]["status"] == "acquisizione_programmata"


def test_elenco_fonti_telematiche_segue_il_catalogo_ufficiale() -> None:
    source_ids = official_telematic_source_ids()

    assert source_ids
    assert "pst_giustizia" in source_ids
    assert all(FONTI_UFFICIALI[source_id].motore == "procedurale_telematico" for source_id in source_ids)
