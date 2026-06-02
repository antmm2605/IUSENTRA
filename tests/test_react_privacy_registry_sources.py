from __future__ import annotations

from pathlib import Path

from pct.privacy import GestioneTrattamenti
from web.services.react_privacy_bridge import build_react_privacy_registro_payload


def test_registro_gdpr_art30_usa_fonti_garante_e_presidi_extra_ue(tmp_path: Path) -> None:
    manager = GestioneTrattamenti(db_path=str(tmp_path / "registro.json"))
    manager.nuovo(
        nome="Trasferimento cloud fascicoli",
        finalita="",
        categoria_dati="Dati giudiziari e documenti di causa",
        base_giuridica="",
        soggetti_interessati="",
        destinatari="",
        trasferimento_extra_ue=True,
        paese_destinazione="",
        garanzie_trasferimento_extra_ue="",
        responsabile="Provider cloud esterno",
        registro_responsabile="",
    )

    payload = build_react_privacy_registro_payload(lambda: manager)
    sources = {source["id"]: source for source in payload["officialSources"]}
    treatment = next(item for item in payload["treatments"] if item["name"] == "Trasferimento cloud fascicoli")
    flag_codes = {flag["code"] for flag in treatment["riskFlags"]}

    assert "garante_registro_trattamenti" in sources
    assert "garante_gdpr_art30" in sources
    assert Path(sources["garante_registro_trattamenti"]["localPath"]).exists()
    assert payload["governance"]["title"] == "Presidio GDPR per studio legale"
    assert payload["registerChecklist"]
    assert treatment["sourceReference"].startswith("GDPR art. 30")
    assert "finalita_mancante" in flag_codes
    assert "base_giuridica_mancante" in flag_codes
    assert "destinatari_mancanti" in flag_codes
    assert "garanzie_extra_ue_mancanti" in flag_codes
    assert "registro_responsabile_mancante" in flag_codes
    assert payload["summary"]["missingTransferSafeguards"] >= 1
