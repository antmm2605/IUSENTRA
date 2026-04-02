from pct.pst_catalog import (
    PST_DM44_SPECIFICHE_URL,
    PST_REGINDE_INTERROGAZIONI_EXT_NAMESPACE,
    PST_USER_VADEMECUM_URL,
    PST_WEB_SERVICES_DOC_DETAIL_URL,
    PST_WEB_SERVICES_DOC_PAGE_URL,
    PST_WEB_SERVICES_DOC_URL,
    PST_WEB_SERVICES_DOC_VERSION,
    PST_WEB_SERVICES_UPDATE_PAGE_URL,
    PST_WEB_SERVICES_WSDL_CATALOG_PACKAGE_NAME,
    PST_WEB_SERVICES_WSDL_CATALOG_PACKAGE_VERSION,
    PST_WEB_SERVICES_WSDL_CATALOG_URL,
    PST_WEB_SERVICES_WSDL_CATALOG_VERSION,
    get_catalog_snapshot,
    get_catalog_sources,
    get_official_methods,
    get_wsdl_catalog_modules,
    get_xsd_channel,
    get_xsd_channels,
)


def test_catalog_snapshot_usa_documentazione_pst_v169():
    snapshot = get_catalog_snapshot()
    assert snapshot["pst_webservices_doc_version"] == "1.69"
    assert snapshot["pst_webservices_doc_url"] == PST_WEB_SERVICES_DOC_URL
    assert snapshot["pst_webservices_doc_page_url"] == PST_WEB_SERVICES_DOC_PAGE_URL
    assert snapshot["pst_webservices_doc_detail_url"] == PST_WEB_SERVICES_DOC_DETAIL_URL
    assert snapshot["pst_webservices_update_page_url"] == PST_WEB_SERVICES_UPDATE_PAGE_URL
    assert snapshot["pst_webservices_wsdl_catalog_version"] == PST_WEB_SERVICES_WSDL_CATALOG_VERSION
    assert snapshot["pst_webservices_wsdl_catalog_package_version"] == PST_WEB_SERVICES_WSDL_CATALOG_PACKAGE_VERSION
    assert snapshot["pst_webservices_wsdl_catalog_package_name"] == PST_WEB_SERVICES_WSDL_CATALOG_PACKAGE_NAME
    assert snapshot["pst_webservices_wsdl_catalog_url"] == PST_WEB_SERVICES_WSDL_CATALOG_URL
    assert snapshot["reginde_namespace"] == PST_REGINDE_INTERROGAZIONI_EXT_NAMESPACE
    assert snapshot["pst_user_vademecum_url"] == PST_USER_VADEMECUM_URL
    assert snapshot["pst_dm44_specifiche_url"] == PST_DM44_SPECIFICHE_URL
    assert snapshot["busta_max_mb"] == 60


def test_catalog_sources_include_specifiche_e_vademecum():
    urls = {item["url"] for item in get_catalog_sources()}
    assert PST_WEB_SERVICES_DOC_URL in urls
    assert PST_WEB_SERVICES_DOC_DETAIL_URL in urls
    assert PST_WEB_SERVICES_WSDL_CATALOG_URL in urls
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


def test_catalog_snapshot_include_moduli_wsdl_e_canali_xsd():
    snapshot = get_catalog_snapshot()

    wsdl_keys = {row["key"] for row in snapshot["wsdl_modules"]}
    xsd_keys = {row["key"] for row in snapshot["xsd_channels"]}

    assert "catalogo_ug" in wsdl_keys
    assert "reginde" in wsdl_keys
    assert "SICI" in xsd_keys
    assert "SIGP" in xsd_keys
    assert "UNEP" in xsd_keys
    assert "CASSAZIONE" in xsd_keys
    assert snapshot["xsd_summary"]["production_ready"] >= 3


def test_xsd_channels_have_status_and_package():
    sici = get_xsd_channel("SICI")
    cassazione = get_xsd_channel("CASSAZIONE")

    assert sici.package_name == "XSD_SICI_20260116.zip"
    assert sici.production_ready is True
    assert cassazione.status_source_news_date == "2026-03-04"
    assert cassazione.production_ready is True


def test_wsdl_catalog_modules_include_consultazione_and_accessori():
    modules = {item.key: item for item in get_wsdl_catalog_modules()}

    assert "sicid_consultazione" in modules
    assert "fascicolo_informatico" in modules
    assert "pagamenti_telematici" in modules
    assert "verifica_pdf" in modules
