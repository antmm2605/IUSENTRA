from pct.legal_platform_catalog import (
    build_operational_fields,
    catalogo_piattaforma_legale,
    infer_legal_operational_procedure,
)


def test_catalogo_piattaforma_legale_copre_le_procedure_wave1_e_wave2():
    catalogo = catalogo_piattaforma_legale()

    assert catalogo["stats"]["procedure_totali"] == 22
    assert catalogo["stats"]["procedure_telematiche"] >= 5
    assert catalogo["by_area"]["Tributario"] >= 2
    assert catalogo["by_channel"]["PTT_TRIBUTARIO"] >= 1


def test_build_operational_fields_associa_la_procedura_tributaria_ai_moduli_core():
    fields = build_operational_fields(
        practice_id="ricorso_tributario",
        area_pratica="Tributario",
        tipo_procedimento="Ricorso tributario di primo grado",
        oggetto="Impugnazione avviso di accertamento",
    )

    assert fields["procedura_operativa_codice"] == "PROC_TRIB_RIC_002"
    assert fields["procedura_operativa_nome"] == "Ricorso tributario di primo grado"
    assert fields["canale_operativo"] == "PTT_TRIBUTARIO"
    assert fields["registro_operativo"] == "PTT_TRIBUTARIO"
    assert fields["procedura_operativa"]["module_bindings"]["preventivo"]["practice_id"] == "ricorso_tributario"
    assert "fattura" in fields["procedura_operativa"]["module_bindings"]


def test_infer_legal_operational_procedure_supporta_keyword_professionali():
    proc = infer_legal_operational_procedure(oggetto="Gestione data breach con notifiche e remediation")

    assert proc is not None
    assert proc.code == "PROC_PRIV_DB_001"
