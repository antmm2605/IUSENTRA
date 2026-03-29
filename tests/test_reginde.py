"""Test per il client ReGINde."""

import json
import pytest
from pct.reginde import ClientReGINde
from pct.uffici_giudiziari import (
    GestoreUfficiGiudiziari,
    _build_bundle_completo,
    risolvi_codice_ministero,
    risolvi_base_pst,
    risolvi_ufficio,
)


@pytest.fixture
def client():
    return ClientReGINde()


def test_cerca_tribunale_milano(client):
    ufficio = client.cerca_ufficio_giudiziario("MILANO")
    assert ufficio is not None
    assert "Milano" in ufficio.nome
    assert ufficio.pec.endswith("@civile.ptel.giustiziacert.it")


def test_cerca_tribunale_roma(client):
    ufficio = client.cerca_ufficio_giudiziario("ROMA")
    assert ufficio is not None
    assert "Roma" in ufficio.nome


def test_cerca_tribunale_inesistente(client):
    ufficio = client.cerca_ufficio_giudiziario("PAESE_CHE_NON_ESISTE")
    assert ufficio is None


def test_ottieni_pec_per_codice(client):
    pec = client.ottieni_pec_ufficio("0580010")
    assert pec is not None
    assert "@civile.ptel.giustiziacert.it" in pec


def test_ottieni_pec_codice_inesistente(client):
    pec = client.ottieni_pec_ufficio("9999999")
    assert pec is None


def test_elenca_uffici(client):
    uffici = client.elenca_uffici()
    assert len(uffici) > 0


def test_elenca_uffici_per_distretto(client):
    uffici = client.elenca_uffici(distretto="Milano")
    assert all(u.distretto == "Milano" for u in uffici)


def test_cerca_case_insensitive(client):
    ufficio_upper = client.cerca_ufficio_giudiziario("MILANO")
    ufficio_lower = client.cerca_ufficio_giudiziario("milano")
    assert ufficio_upper is not None
    assert ufficio_lower is not None
    assert ufficio_upper.codice == ufficio_lower.codice


def test_palmi_usa_il_distretto_reggio_calabria(client):
    ufficio = client.cerca_ufficio_giudiziario("PALMI")
    assert ufficio is not None
    assert ufficio.codice == "0910011"
    assert ufficio.distretto == "Reggio di Calabria"


def test_riferimenti_ministeriali_ufficio_milano():
    ufficio = risolvi_ufficio("0580010")
    assert ufficio is not None
    assert ufficio["codice_ministero"] == "0151460094"
    assert ufficio["codice_gl"] == "GLMI"
    assert "JPW_SICID" in ufficio["servizi_ministero"]
    assert ufficio["pec"].endswith("@civile.ptel.giustiziacert.it")


def test_risoluzione_pst_palmi_usa_gl_e_servizio():
    assert risolvi_codice_ministero("0910011") == "0800570094"
    assert risolvi_base_pst("0910011", base_url="https://ext.processotelematico.giustizia.it") == (
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID"
    )


def test_cache_bundle_legacy_viene_rigenerata_se_il_bundle_cambia(tmp_path):
    bundle = _build_bundle_completo()
    cache_path = tmp_path / "uffici_giudiziari.json"
    cache_legacy = []
    for ufficio in bundle:
        if ufficio.get("codice") in {"0910010", "0910011"}:
            cache_legacy.append({**ufficio, "distretto": "Catanzaro"})
        else:
            cache_legacy.append(ufficio)
    cache_path.write_text(
        json.dumps(
            {
                "sorgente": "bundle",
                "aggiornato_il": "2026-03-01T09:00:00",
                "n_uffici": len(cache_legacy),
                "uffici": cache_legacy,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    gestore = GestoreUfficiGiudiziari(str(cache_path))
    uffici = gestore.carica()
    palmi = next(u for u in uffici if u.get("codice") == "0910011")
    reggio = next(u for u in uffici if u.get("codice") == "0910010")

    assert palmi["distretto"] == "Reggio di Calabria"
    assert reggio["distretto"] == "Reggio di Calabria"


def test_cache_remota_legacy_viene_rigenerata_se_bundle_hash_diverso(tmp_path):
    bundle = _build_bundle_completo()
    cache_path = tmp_path / "uffici_giudiziari.json"
    cache_legacy = []
    for ufficio in bundle:
        if ufficio.get("codice") == "0910011":
            cache_legacy.append({**ufficio, "distretto": "Catanzaro"})
        else:
            cache_legacy.append(ufficio)
    cache_path.write_text(
        json.dumps(
            {
                "sorgente": "pst_public",
                "aggiornato_il": "2026-03-01T09:00:00",
                "n_uffici": len(cache_legacy),
                "bundle_hash": "legacy-bundle-hash",
                "uffici": cache_legacy,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    gestore = GestoreUfficiGiudiziari(str(cache_path))
    uffici = gestore.carica()
    palmi = next(u for u in uffici if u.get("codice") == "0910011")

    assert palmi["distretto"] == "Reggio di Calabria"
