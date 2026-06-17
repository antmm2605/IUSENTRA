from pct.pratiche_collegate_catalog import (
    codice_oggetto_pst_entry,
    codice_oggetto_pst_payload,
    list_codici_oggetto_pst,
    load_codici_oggetto_pst_catalog,
    looks_like_codice_oggetto_pst,
    normalize_codice_oggetto_pst,
)


def test_catalogo_codici_oggetto_pst_importato_da_xsd_ufficiali():
    catalog = load_codici_oggetto_pst_catalog()
    rows = list_codici_oggetto_pst()
    codes = {row["codice"] for row in rows}

    assert catalog["versione"] == "2026-05-11.pst-xsd-official"
    assert catalog["fonte"]["tipo"] == "PST_XSD"
    assert catalog["fonte"]["betaAmmessiProduzione"] is False
    assert len(rows) == 1018
    assert "014001" in codes
    assert "111604" in codes


def test_catalogo_codici_oggetto_pst_esclude_codici_non_presenti_negli_xsd():
    assert codice_oggetto_pst_entry("014001") is not None
    assert codice_oggetto_pst_entry("111604") is not None
    assert codice_oggetto_pst_entry("B02001") is not None
    assert codice_oggetto_pst_entry("014700") is None
    assert codice_oggetto_pst_entry("IUSENTRA-BOZZA") is None


def test_payload_codice_oggetto_pst_restituisce_fonte_xsd_specifica():
    payload = codice_oggetto_pst_payload("014001")

    assert payload["codice_oggetto_pst"] == "014001"
    assert payload["fonte_codice_oggetto"] == "PST_XSD"
    assert payload["file_fonte_codice_oggetto"].endswith("tipi-base.xsd")
    assert codice_oggetto_pst_payload("222050 - Retribuzione")["codice_oggetto_pst"] == "222050"


def test_normalizza_codice_oggetto_pst_da_descrizione_ufficiale_univoca():
    descrizione = "Azioni di competenza del Giudice di Pace in materia di risarcimento danno"

    assert normalize_codice_oggetto_pst(descrizione) == "145009"
    assert codice_oggetto_pst_payload(descrizione)["codice_oggetto_pst"] == "145009"


def test_heuristic_codes_accepts_official_alphanumeric_and_rejects_internal_aliases():
    assert looks_like_codice_oggetto_pst("014001") is True
    assert looks_like_codice_oggetto_pst("B02001") is True
    assert looks_like_codice_oggetto_pst("ESEC_MOB_001") is False
    assert looks_like_codice_oggetto_pst("IUSENTRA-BOZZA") is False


def test_normalizza_codice_oggetto_pst_da_valore_descrittivo_importato():
    for codice in ("014001", "111604", "222050", "B02001"):
        entry = codice_oggetto_pst_entry(codice)
        assert entry is not None
        assert normalize_codice_oggetto_pst(f"{codice} - {entry['descrizione']}") == codice
        assert codice_oggetto_pst_payload(f"{codice} - {entry['descrizione']}")["codice_oggetto_pst"] == codice
    assert normalize_codice_oggetto_pst("IUSENTRA-BOZZA") == ""


def test_tutti_i_codici_oggetto_pst_ufficiali_arrivano_al_deposito():
    rows = list_codici_oggetto_pst()

    assert len(rows) == 1018
    for row in rows:
        codice = row["codice"]
        descrizione = row["descrizione"]

        assert normalize_codice_oggetto_pst(codice) == codice
        assert normalize_codice_oggetto_pst(f"{codice} - {descrizione}") == codice
        assert codice_oggetto_pst_payload(codice)["codice_oggetto_pst"] == codice
        assert codice_oggetto_pst_payload(f"{codice} - {descrizione}")["codice_oggetto_pst"] == codice
