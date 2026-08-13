from pct.deposito_destination_tables import (
    audit_deposit_destination,
    load_destination_catalog,
    load_object_catalog,
)


def test_tabella_studio_telematico_conferma_vicenza_lavoro():
    audit = audit_deposit_destination(
        office_code="0241160092",
        office_name="Tribunale di Vicenza",
        office_pec="tribunale.vicenza@civile.ptel.giustiziacert.it",
        ministerial_role="Lavoro",
        deposit_key="Introduttivi_SICID::Ricorso",
    )

    assert audit["ok"] is True
    assert {item["code"] for item in audit["checks"]} == {
        "ufficio_tabella",
        "pec_ufficio",
        "servizio_deposito",
        "registro_sezione",
        "rito_materia",
    }
    assert all(item["passed"] is True for item in audit["checks"])


def test_tabella_studio_telematico_blocca_pec_diversa_dalla_destinazione_reale():
    audit = audit_deposit_destination(
        office_code="0241160092",
        office_name="Tribunale di Vicenza",
        office_pec="ufficio.errato@pec.invalid",
        ministerial_role="Lavoro",
        deposit_key="Introduttivi_SICID::Ricorso",
    )

    assert audit["ok"] is False
    assert "pec_ufficio" in audit["errors"]


def test_tabella_studio_telematico_blocca_lavoro_sul_giudice_di_pace():
    audit = audit_deposit_destination(
        office_code="0241160150",
        office_name="Giudice di Pace - Vicenza",
        office_pec="gdp.vicenza@civile.ptel.giustiziacert.it",
        ministerial_role="Lavoro",
        deposit_key="Introduttivi_SICID::Ricorso",
    )

    assert audit["ok"] is False
    assert {"servizio_deposito", "registro_sezione"}.intersection(audit["errors"])


def test_catalogo_destinazioni_conserva_impronta_e_tabelle_sorgente():
    catalog = load_destination_catalog()

    assert len(str(catalog["source"]["sha256"])) == 64
    assert catalog["counts"]["offices_with_services"] == 1442
    assert catalog["counts"]["registry_rows"] == 2888
    assert catalog["counts"]["rite_rows"] == 1192


def test_tabella_oggetti_distingue_retribuzione_privata_e_pubblico_impiego():
    records = {
        item["codice"]: item for item in load_object_catalog()["records"] if item.get("codice") in {"220050", "222050"}
    }

    assert records["220050"]["codicePadre"] == "220"
    assert records["220050"]["descrizionePadre"] == "Lavoro dipendente da privato"
    assert records["222050"]["codicePadre"] == "222"
    assert records["222050"]["descrizionePadre"] == "Pubblico impiego"


def test_destinazione_vicenza_lavoro_controlla_anche_oggetto_pubblico_impiego():
    audit = audit_deposit_destination(
        office_code="0241160092",
        office_name="Tribunale di Vicenza",
        office_pec="tribunale.vicenza@civile.ptel.giustiziacert.it",
        ministerial_role="Lavoro",
        deposit_key="Introduttivi_SICID::Ricorso",
        object_code="222050",
    )

    object_check = next(item for item in audit["checks"] if item["code"] == "codice_oggetto_tabella")
    assert audit["ok"] is True
    assert object_check["passed"] is True
    assert object_check["actual"]["codice_padre"] == "222"
    assert object_check["actual"]["descrizione_padre"] == "Pubblico impiego"


def test_destinazione_blocca_codice_oggetto_non_presente_nella_tabella_ministeriale():
    audit = audit_deposit_destination(
        office_code="0241160092",
        office_name="Tribunale di Vicenza",
        office_pec="tribunale.vicenza@civile.ptel.giustiziacert.it",
        ministerial_role="Lavoro",
        deposit_key="Introduttivi_SICID::Ricorso",
        object_code="999999",
    )

    assert audit["ok"] is False
    assert "codice_oggetto_tabella" in audit["errors"]
