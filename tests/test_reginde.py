"""Test per il client ReGINde."""

import json
import pytest
from pct.reginde import ClientReGINde
from pct.uffici_giudiziari import (
    GestoreUfficiGiudiziari,
    _build_bundle_completo,
    _uffici_hash,
    fonti_uffici_giudiziari,
    indirizzi_telematici_ufficio,
    risolvi_codice_ministero,
    risolvi_base_pst,
    risolvi_servizio_pst,
    risolvi_ufficio,
    valida_resolver_pst,
)
from pct.polisWeb import _pst_namespace_qbuilder


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


def test_ottieni_ufficio_per_codice(client):
    ufficio = client.ottieni_ufficio("0580010")
    assert ufficio is not None
    assert ufficio.codice == "0580010"
    assert "Milano" in ufficio.nome


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


def test_risoluzione_tribunale_reggio_calabria_accetta_alias_pratica_reale():
    aliases = [
        "TRIBUNALE DI REGGIO DI CALABRIA",
        "TRIBUNALE ORDINARIO DI REGGIO DI CALABRIA",
        "Tribunale Ordinario - Reggio di Calabria",
    ]
    for alias in aliases:
        ufficio = risolvi_ufficio(alias, tipo="TRIBUNALE")
        assert ufficio is not None, alias
        assert ufficio["codice"] == "0910010"
        assert ufficio["codice_ministero"] == "0800630097"
        assert ufficio["pec"] == "tribunale.reggiocalabria@civile.ptel.giustiziacert.it"


def test_risoluzione_gdp_preferisce_ufficio_attivo_con_pec_su_alias_storico():
    ufficio = risolvi_ufficio("GIUDICE DI PACE DI BARRA", tipo="GDP")
    assert ufficio is not None
    assert ufficio["codice_ministero"] == "06304911552"
    assert ufficio["pec"] == "gdp.barra@civile.ptel.giustiziacert.it"
    assert "NON ATTIVO" not in ufficio["nome"].upper()


def test_risoluzione_pst_gdp_palmi_usa_sigp():
    assert risolvi_codice_ministero("0910401") == "0800570152"
    assert risolvi_servizio_pst("0910401") == "JPW_SIGP"
    base = risolvi_base_pst("0910401", base_url="https://ext.processotelematico.giustizia.it")
    assert base == "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIGP"
    assert _pst_namespace_qbuilder(base) == "urn:CONS-SIGP-BE"


def test_snapshot_ministeriale_aggiunge_corti_appello_mancanti_dal_vecchio_bundle():
    for nome, codice_ministero, codice_gl in [
        ("Corte d'Appello di Reggio di Calabria", "0800630064", "GLRC"),
        ("Corte d'Appello di Salerno", "0651160068", "GLSA"),
        ("Corte d'Appello di Caltanissetta", "0850040065", "GLCL"),
    ]:
        ufficio = risolvi_ufficio(nome, tipo="CORTE_APPELLO")
        assert ufficio is not None
        assert ufficio["codice"] == codice_ministero
        assert ufficio["codice_ministero"] == codice_ministero
        assert ufficio["codice_gl"] == codice_gl
        assert ufficio["aggiunto_da_snapshot_ministeriale"] is True
        assert "JPW_SICID" in ufficio["servizi_ministero"]
        assert risolvi_base_pst(codice_ministero, base_url="https://ext.processotelematico.giustizia.it").endswith(
            f"/{codice_gl}/JPW_SICID"
        )


def test_snapshot_ministeriale_aggiunge_tribunali_e_gdp_ufficiali_non_presenti_nel_bundle_storico():
    tribunale = risolvi_ufficio("Tribunale Ordinario - Caltanissetta", tipo="TRIBUNALE")
    gdp = risolvi_ufficio("Giudice di Pace - Gela", tipo="GDP")

    assert tribunale is not None
    assert tribunale["codice_ministero"] == "0850040098"
    assert tribunale["codice_gl"] == "GLCL"
    assert risolvi_servizio_pst("0850040098", tipo="TRIBUNALE") == "JPW_SICID"
    assert gdp is not None
    assert gdp["codice_ministero"] == "0850070152"
    assert gdp["codice_gl"] == "GLCL"
    assert risolvi_servizio_pst("0850070152", tipo="GDP") == "JPW_SIGP"


def test_risoluzione_pst_cassazione_usa_proxy_cassci():
    assert risolvi_codice_ministero("9990000") == "80417740588"
    assert risolvi_base_pst("9990000", base_url="https://ext.processotelematico.giustizia.it") == (
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLCC/JPW_CASSCI"
    )


def test_resolver_pst_tutti_gli_uffici_jpw_hanno_base_namespace():
    bundle = _build_bundle_completo()
    report = valida_resolver_pst(bundle)

    assert report["ok"] is True
    assert report["n_uffici_jpw"] > 300
    for ufficio in bundle:
        if not any(str(s).startswith("JPW_") for s in (ufficio.get("servizi_ministero") or [])):
            continue
        base = risolvi_base_pst(ufficio["codice"], base_url="https://ext.processotelematico.giustizia.it")
        assert _pst_namespace_qbuilder(base), ufficio["codice"]


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


def test_cache_uffici_rigenera_metadati_pst_mancanti_anche_con_hash_corrente(tmp_path):
    bundle = _build_bundle_completo()
    cache_path = tmp_path / "uffici_giudiziari.json"
    cache_legacy = []
    for ufficio in bundle:
        item = dict(ufficio)
        if item.get("codice") == "0910401":
            for key in ("codice_ministero", "codice_gl", "servizi_ministero", "servizio_pst_predefinito"):
                item.pop(key, None)
        cache_legacy.append(item)
    cache_path.write_text(
        json.dumps(
            {
                "sorgente": "remoto:pst_public",
                "aggiornato_il": "2026-04-24T08:00:00",
                "n_uffici": len(cache_legacy),
                "bundle_hash": _uffici_hash(bundle),
                "uffici": cache_legacy,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    gestore = GestoreUfficiGiudiziari(str(cache_path))
    uffici = gestore.carica()
    gdp_palmi = next(u for u in uffici if u.get("codice") == "0910401")
    saved = json.loads(cache_path.read_text(encoding="utf-8"))

    assert gdp_palmi["codice_ministero"] == "0800570152"
    assert gdp_palmi["codice_gl"] == "GLRC"
    assert gdp_palmi["servizio_pst_predefinito"] == "JPW_SIGP"
    assert saved["pst_resolver"]["ok"] is True


def test_gestore_cerca_supporta_filtri_procura_generale_e_limite():
    gestore = GestoreUfficiGiudiziari()

    risultati = gestore.cerca("roma", tipo="PROCURA_GENERALE", limit=1)

    assert len(risultati) == 1
    assert risultati[0]["tipo"] == "PROCURA_GENERALE"
    assert "Roma" in risultati[0]["nome"]


def test_gestore_cerca_usa_anche_metadati_ministeriali():
    gestore = GestoreUfficiGiudiziari()

    risultati = gestore.cerca("tribunale ordinario", tipo="TRIBUNALE", limit=5)

    assert risultati
    assert all(item["tipo"] == "TRIBUNALE" for item in risultati)


def test_gestore_cerca_supporta_corti_tributarie():
    gestore = GestoreUfficiGiudiziari()

    risultati = gestore.cerca("abruzzo", tipo="CGT", limit=3)

    assert risultati
    assert all(item["tipo"] == "CGT" for item in risultati)


def test_gestore_cerca_supporta_cgarsi():
    gestore = GestoreUfficiGiudiziari()

    risultati = gestore.cerca("sicilia", tipo="CGARS", limit=3)

    assert risultati
    assert all(item["tipo"] == "CGARS" for item in risultati)


def test_indirizzi_telematici_distinguono_uso_e_fonte():
    tribunale = risolvi_ufficio("0580010")
    procura = risolvi_ufficio("0580010".replace("0580010", "0581010")) or {
        "tipo": "PROCURA",
        "nome": "Procura della Repubblica di Milano",
        "pec": "procura.milano@giustiziapec.it",
        "codice": "0581010",
    }

    indirizzi_tribunale = indirizzi_telematici_ufficio(tribunale, data_rilevazione="2026-04-30T12:00:00")
    indirizzi_procura = indirizzi_telematici_ufficio(procura, data_rilevazione="2026-04-30T12:00:00")

    assert indirizzi_tribunale[0]["uso"] == "deposito_pct"
    assert indirizzi_tribunale[0]["fonte"] == "PST"
    assert indirizzi_procura[0]["uso"] == "deposito_penale"
    assert "deposito telematico" in indirizzi_tribunale[0]["note"]
    assert {fonte["id"] for fonte in fonti_uffici_giudiziari()} == {"pst", "ipa", "sito_ufficiale"}


def test_verifica_variazioni_degrada_su_registro_interno_senza_errore_remoto(tmp_path, monkeypatch):
    import requests

    def _raise_unreachable(*args, **kwargs):
        raise requests.RequestException("rete non disponibile")

    monkeypatch.setattr(requests, "get", _raise_unreachable)
    cache_path = tmp_path / "uffici" / "uffici_giudiziari.json"

    report = GestoreUfficiGiudiziari(str(cache_path)).verifica_variazioni()

    assert report["ok"] is True
    assert report["modalita"] == "verifica_locale_governata"
    assert report["sorgente"] == "registro_interno_versionato"
    assert report["errore"] is None
    assert "Nessuna sorgente remota disponibile" not in report["messaggio"]
    assert "PST" in report["messaggio"]
    assert "IPA" in report["messaggio"]
    assert report["fonti"]
