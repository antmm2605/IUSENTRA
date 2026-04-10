from __future__ import annotations

import pytest

from pct.config_studio import ConfigFirma, ConfigStudio, GestioneConfigStudio
from pct.pat import ClientPAT, crea_client_pat
from pct.pdp import ClientPDP, crea_client_pdp
from pct.sigit import ClientSIGIT, crea_client_sigit


@pytest.mark.parametrize(
    ("factory", "client_type"),
    [
        (crea_client_pdp, ClientPDP),
        (crea_client_pat, ClientPAT),
        (crea_client_sigit, ClientSIGIT),
    ],
)
def test_factory_portali_riusa_p12_da_config_studio(tmp_path, monkeypatch, factory, client_type):
    studio_cfg = tmp_path / "studio.json"
    p12_path = tmp_path / "firma.p12"
    p12_path.write_bytes(b"fake-p12")

    gs = GestioneConfigStudio(str(studio_cfg))
    cfg = gs.config
    cfg.firma = ConfigFirma(
        p12_path=str(p12_path),
        password="segreta",
        cf_avvocato="rssmra80a01h501z",
    )
    gs.aggiorna(cfg)

    for env_name in (
        "PCT_FIRMA_P12",
        "PCT_FIRMA_PASSWORD",
        "PCT_FIRMA_CERT",
        "PCT_FIRMA_KEY",
        "PCT_FIRMA_KEY_PASSWORD",
        "PCT_CF_AVVOCATO",
    ):
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.setenv("PCT_STUDIO_CONFIG", str(studio_cfg))
    monkeypatch.delenv("PCT_CONFIG_STUDIO_DB", raising=False)

    client = factory(demo=False)

    assert isinstance(client, client_type)
    assert client.p12_path == str(p12_path)
    assert client.p12_password == b"segreta"
    assert client.cf_avvocato == "RSSMRA80A01H501Z"


@pytest.mark.parametrize(
    ("factory", "client_type"),
    [
        (crea_client_pdp, ClientPDP),
        (crea_client_pat, ClientPAT),
        (crea_client_sigit, ClientSIGIT),
    ],
)
def test_factory_portali_riusa_pem_da_config_studio(tmp_path, monkeypatch, factory, client_type):
    studio_cfg = tmp_path / "studio.json"
    cert_path = tmp_path / "firma.crt"
    key_path = tmp_path / "firma.key"
    cert_path.write_text("CERT", encoding="utf-8")
    key_path.write_text("KEY", encoding="utf-8")

    gs = GestioneConfigStudio(str(studio_cfg))
    gs.aggiorna(
        ConfigStudio(
            firma=ConfigFirma(
                cert_pem_path=str(cert_path),
                key_pem_path=str(key_path),
                key_pem_password="chiave-segreta",
                cf_avvocato="RSSMRA80A01H501Z",
            )
        )
    )

    for env_name in (
        "PCT_FIRMA_P12",
        "PCT_FIRMA_PASSWORD",
        "PCT_FIRMA_CERT",
        "PCT_FIRMA_KEY",
        "PCT_FIRMA_KEY_PASSWORD",
        "PCT_CF_AVVOCATO",
    ):
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.setenv("PCT_CONFIG_STUDIO_DB", str(studio_cfg))
    monkeypatch.delenv("PCT_STUDIO_CONFIG", raising=False)

    client = factory(demo=False)

    assert isinstance(client, client_type)
    assert client.cert_pem_path == str(cert_path)
    assert client.key_pem_path == str(key_path)
    assert client.key_pem_password == b"chiave-segreta"
    assert client.cf_avvocato == "RSSMRA80A01H501Z"
