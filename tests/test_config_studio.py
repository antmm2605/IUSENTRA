from __future__ import annotations

from pct.config_studio import ConfigFirma, ConfigStudio, GestioneConfigStudio


def test_config_firma_visible_signature_mode_default_retrocompatibile():
    cfg = ConfigStudio.from_dict({"firma": {"backend_preferito": "p12"}})

    assert cfg.firma.visible_signature_mode == "laterale"


def test_config_firma_visible_signature_mode_normalizza_valori_invalidi():
    cfg = ConfigFirma(visible_signature_mode="valore-non-valido")

    assert cfg.visible_signature_mode == "laterale"


def test_config_studio_salva_e_ricarica_firma_visibile_basso_sinistra(tmp_path):
    path = tmp_path / "studio.json"
    gestore = GestioneConfigStudio(str(path))
    cfg = gestore.config
    cfg.firma.visible_signature_mode = "basso_sinistra"
    gestore.aggiorna(cfg)

    ricaricato = GestioneConfigStudio(str(path)).config

    assert ricaricato.firma.visible_signature_mode == "basso_sinistra"
