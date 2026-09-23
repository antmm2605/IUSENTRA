from pct.deposito_profile_backfill import (
    build_deposit_profile_for_record,
    deposit_profile_needs_update,
    merge_profile_into_payload,
)


def test_backfill_sostituisce_provenienza_xsd_storica_con_catalogo_corrente():
    row = {
        "id": "F-1",
        "oggetto": "Procedura CCI",
        "codice_oggetto_pst": "471404",
        "fonte_codice_oggetto": "PST_XSD_STORICO",
        "file_fonte_codice_oggetto": "XSD_SICI_20260126/Atti/sici/tipi-base.xsd",
    }

    profile, payload = build_deposit_profile_for_record("fascicoli", row)
    codice = profile["codice_deposito"]

    assert codice["codice_oggetto_pst"] == "471404"
    assert codice["fonte"] == "PST_XSD"
    assert codice["file"] == "XSD_SICI_20260508/XSD_SICI_20260508/Atti/sici/tipi-base.xsd"
    assert deposit_profile_needs_update(
        {
            **profile,
            "codice_deposito": {
                **codice,
                "fonte": "PST_XSD_STORICO",
                "file": "XSD_SICI_20260126/Atti/sici/tipi-base.xsd",
            },
        },
        profile,
    )

    merged = merge_profile_into_payload(
        {
            **payload,
            "codice_oggetto_pst": "471404",
            "fonte_codice_oggetto": "PST_XSD_STORICO",
            "file_fonte_codice_oggetto": "XSD_SICI_20260126/Atti/sici/tipi-base.xsd",
        },
        profile,
    )
    assert merged["fonte_codice_oggetto"] == "PST_XSD"
    assert merged["file_fonte_codice_oggetto"] == codice["file"]

def test_backfill_da_precedenza_alla_colonna_sql_rispetto_al_mirror_json():
    row = {
        "id": "F-2",
        "codice_oggetto_pst": "010001",
        "dati_json": '{"codice_oggetto_pst":"010002","fonte_codice_oggetto":"MIRROR_STORICO"}',
    }

    profile, payload = build_deposit_profile_for_record("fascicoli", row)
    codice = profile["codice_deposito"]

    assert payload["codice_oggetto_pst"] == "010002"
    assert codice["codice_oggetto_pst"] == "010001"
    assert codice["fonte"] == "PST_XSD"
    merged = merge_profile_into_payload(payload, profile)
    assert merged["codice_oggetto_pst"] == "010001"
    assert merged["fonte_codice_oggetto"] == "PST_XSD"
