from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.fascicolo_document_catalog import classify_fascicolo_document
from pct.fascicolo_registry_document import (
    REGISTRY_DOCUMENT_PARSER_VERSION,
    apply_fascicolo_registry_automation,
    extract_fascicolo_registry_data,
)
from pct.fascicolo_sentenza_economica import extract_contributo_unificato_document_evidence


REGISTRY_TEXT = """TRIBUNALE ORDINARIO DI PALMI
771/2025
Ruolo Generale N. Iscritto il : 07/03/2025
Ruolo Sezionale N. 00000772
Sezione : Giudice :
Ruolo :
Materia :
OGGETTO
CONTROVERSIE IN MATERIA DI LAVORO, PREV., ASSIST. OBBLIG.
Pubblico impiego
retribuzione
Num. R.G. : del Sezione : Giudice :771/202507/03/2025 01 GABUTTI CARLO
Attori/Ricorrenti/Appellanti :
MANDAGLIO DANIELA
Avv.MONTAGNESE GIUSEPPE
via San Marco 2 - 89029 Taurianova
Resistenti/Ingiunti/Appellati :
AVVOCATURA DISTRETTUALE DI STATO DI REGGIO CALABRIA
Avv.
MINISTERO DELL'ISTRUZIONE E DEL MERITO
Avv.
01 GABUTTI CARLO
Contributo Unificato:Esente
0800570094000007712025
Udienze : Prima discussione : ALLEGATI14/07/2026
Opposizione al Decreto Ingiuntivo: Num. RG ricorso Num. DI Data DI
Ist. n. 1 dep. 07/03/2025
"""


def test_scheda_iscrizione_ruolo_reale_estesa_campo_per_campo():
    result = extract_fascicolo_registry_data(REGISTRY_TEXT)

    assert result.found is True
    assert result.rg_number == "771"
    assert result.rg_year == 2025
    assert result.registration_date == "2025-03-07"
    assert result.court == "Tribunale di Palmi"
    assert result.section == "01"
    assert result.judge == "Gabutti Carlo"
    assert result.role == "Controversie in Materia di Lavoro, Prev., Assist. Obblig."
    assert result.matter == "Pubblico impiego"
    assert result.object == "retribuzione"
    assert result.claimants == ("Mandaglio Daniela",)
    assert result.lawyers == ("Montagnese Giuseppe",)
    assert result.opponents == (
        "Avvocatura Distrettuale dello Stato di Reggio Calabria",
        "Ministero dell'Istruzione e del Merito",
    )
    assert result.contribution_status == "esente"
    assert result.first_hearing_date == "2026-07-14"


def test_scheda_ruolo_non_e_documento_da_inviare_e_riconosce_esenzione():
    classification = classify_fascicolo_document(
        filename="Documento_30446614.pdf",
        extracted_text=REGISTRY_TEXT,
    )
    evidence = extract_contributo_unificato_document_evidence(
        REGISTRY_TEXT,
        {"filename": "Documento_30446614.pdf"},
    )

    assert classification.role == "scheda_iscrizione_ruolo"
    assert classification.label == "Iscrizione a ruolo / dati fascicolo"
    assert classification.deposit_role == "fuori_busta"
    assert classification.deposit_candidate is False
    assert evidence["esente"] is True
    assert evidence["natura"] == "esenzione_contributo_unificato"


def test_automazione_aggiorna_fascicolo_ed_e_idempotente(tmp_path):
    manager = GestioneFascicoli(
        str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "documenti"),
    )
    fascicolo = manager.nuovo("Mandaglio c. MIM", TipoFascicolo.LAVORO)
    metadata = {
        "documento_id": "C71208E1",
        "filename": "Documento_30446614.pdf",
        "sha256": "a" * 64,
    }

    first = apply_fascicolo_registry_automation(
        fascicoli_repository=manager,
        fascicolo_id=fascicolo.id,
        text=REGISTRY_TEXT,
        document_metadata=metadata,
        actor="test",
    )
    saved = manager.get(fascicolo.id)
    second = apply_fascicolo_registry_automation(
        fascicoli_repository=manager,
        fascicolo_id=fascicolo.id,
        text=REGISTRY_TEXT,
        document_metadata=metadata,
        actor="test",
    )

    assert first.applied is True
    assert first.already_processed is False
    assert saved.numero_rg == "771"
    assert saved.anno_rg == 2025
    assert saved.tribunale == "Tribunale di Palmi"
    assert saved.giudice == "Gabutti Carlo"
    assert saved.nome_cliente == "Mandaglio Daniela"
    assert saved.attore_principale == "Mandaglio Daniela"
    assert "Ministero" in saved.controparte
    assert saved.data_prima_udienza == "2026-07-14"
    assert saved.pagamenti["contributo_unificato"]["status"] == "non_previsto"
    assert saved.pagamenti["contributo_unificato"]["natura"] == "esenzione_contributo_unificato"
    state = saved.source_snapshot["post_deposito_cancelleria"]
    assert state["parser_version"] == REGISTRY_DOCUMENT_PARSER_VERSION
    assert len(state["documents"]) == 1
    assert second.already_processed is True
    assert second.applied is False
    assert len(manager.get(fascicolo.id).source_snapshot["post_deposito_cancelleria"]["documents"]) == 1


def test_automazione_non_sovrascrive_un_rg_diverso(tmp_path):
    manager = GestioneFascicoli(str(tmp_path / "fascicoli.json"))
    fascicolo = manager.nuovo(
        "Pratica diversa",
        TipoFascicolo.LAVORO,
        numero_rg="999",
        anno_rg=2025,
        nome_cliente="Cliente già confermato",
    )

    outcome = apply_fascicolo_registry_automation(
        fascicoli_repository=manager,
        fascicolo_id=fascicolo.id,
        text=REGISTRY_TEXT,
        document_metadata={"sha256": "b" * 64},
        actor="test",
    )

    saved = manager.get(fascicolo.id)
    assert "numero_rg_diverso" in outcome.conflicts
    assert saved.numero_rg == "999"
    assert saved.nome_cliente == "Cliente già confermato"
