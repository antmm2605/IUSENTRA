from pct.pst_catalog import (
    PST_DM44_SPECIFICHE_URL,
    PST_REGINDE_INTERROGAZIONI_EXT_NAMESPACE,
    PST_USER_VADEMECUM_URL,
    PST_WEB_SERVICES_DOC_URL,
    PST_WEB_SERVICES_DOC_VERSION,
    get_catalog_snapshot,
    get_catalog_sources,
    get_official_methods,
)


def test_catalog_snapshot_usa_documentazione_pst_v165():
    snapshot = get_catalog_snapshot()
    assert snapshot["pst_webservices_doc_version"] == "1.65"
    assert snapshot["pst_webservices_doc_url"] == PST_WEB_SERVICES_DOC_URL
    assert snapshot["reginde_namespace"] == PST_REGINDE_INTERROGAZIONI_EXT_NAMESPACE
    assert snapshot["pst_user_vademecum_url"] == PST_USER_VADEMECUM_URL
    assert snapshot["pst_dm44_specifiche_url"] == PST_DM44_SPECIFICHE_URL
    assert snapshot["busta_max_mb"] == 60


def test_catalog_sources_include_specifiche_e_vademecum():
    urls = {item["url"] for item in get_catalog_sources()}
    assert PST_WEB_SERVICES_DOC_URL in urls
    assert PST_DM44_SPECIFICHE_URL in urls
    assert PST_USER_VADEMECUM_URL in urls


def test_catalog_methods_include_servizi_chiave_v165():
    methods = {item.name: item for item in get_official_methods()}
    assert "getListaUfficiGiudiziari" in methods
    assert "getListaUfficiPenali" in methods
    assert "getRegistriFromUfficio" in methods
    assert "getTipiUfficio" in methods
    assert "getRito" in methods
    assert "getNormativa" in methods
    assert "interrogazioniExt" in methods
    assert methods["getTipiUfficio"].page == 46
    assert methods["getNormativa"].page == 45
