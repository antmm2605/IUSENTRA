from types import SimpleNamespace

from pct.preventivi import GestionePreventivi, StatoPreventivo, TipoVoce, VocePreventivo
from pct.workflow_onboarding import build_fascicolo_onboarding


def test_build_fascicolo_onboarding_precompila_fascicolo_da_workflow():
    cliente = SimpleNamespace(
        nome_completo="Mario Rossi",
        avvocato_referente="Avv. Lucia Verdi",
    )
    preventivo = SimpleNamespace(
        numero="2026/001",
        id_pratica="atto_citazione",
        area_pratica="Tributario",
        tipo_procedimento="Ricorso Tributario",
        valore_controversia=18500.0,
        oggetto="Impugnazione avviso di accertamento",
        creato_da="",
    )
    conferimento = SimpleNamespace(
        numero="2026/010",
        id_pratica="atto_citazione",
        area_pratica="Tributario",
        tipo_procedimento="Ricorso Tributario",
        oggetto="Difesa nel giudizio tributario",
        avvocato_referente="Avv. Lucia Verdi",
    )

    onboarding = build_fascicolo_onboarding(
        cliente=cliente,
        preventivo=preventivo,
        conferimento=conferimento,
    )

    assert onboarding["source_label"] == "Conferimento incarico"
    assert onboarding["source_number"] == "2026/010"
    assert onboarding["tipo"] == "TRIBUTARIO"
    assert onboarding["oggetto"] == "Difesa nel giudizio tributario"
    assert onboarding["avvocato_referente"] == "Avv. Lucia Verdi"
    assert onboarding["valore_causa"] == 18500.0
    assert "Checklist iniziale" in onboarding["note"]


def test_build_fascicolo_onboarding_comparsa_risposta_usa_controlli_normativi_specifici():
    cliente = SimpleNamespace(
        nome_completo="Moscato Marco",
        avvocato_referente="Avv. Lucia Verdi",
    )
    conferimento = SimpleNamespace(
        numero="2026/050",
        id_pratica="comparsa_risposta",
        area_pratica="Civile",
        tipo_procedimento="Comparsa di costituzione e risposta",
        oggetto="Conferimento incarico - Preventivo professionale per comparsa di costituzione e risposta",
        avvocato_referente="Avv. Lucia Verdi",
    )
    preventivo = SimpleNamespace(
        numero="2026/011",
        id_pratica="comparsa_risposta",
        area_pratica="Civile",
        tipo_procedimento="Comparsa di costituzione e risposta",
        valore_controversia=5201.0,
        oggetto="Preventivo professionale per comparsa di costituzione e risposta",
        creato_da="",
    )

    onboarding = build_fascicolo_onboarding(
        cliente=cliente,
        preventivo=preventivo,
        conferimento=conferimento,
    )

    assert onboarding["titolo"] == "Moscato Marco - Comparsa di costituzione e risposta"
    assert any("art. 166" in item.lower() for item in onboarding["checklist"])
    assert any("art. 167" in item.lower() for item in onboarding["checklist"])
    assert onboarding["attivita_iniziali"][0]["activity_type"] == "TERMINE_SCADENZA"
    assert "166-167" in onboarding["attivita_iniziali"][0]["title"]


def test_collega_fascicolo_aggiorna_preventivo_e_conferimento(tmp_path):
    db_path = tmp_path / "preventivi.json"
    gp = GestionePreventivi(str(db_path))

    preventivo = gp.crea_preventivo(
        id_cliente="cli-1",
        oggetto="Recupero credito commerciale",
        voci=[VocePreventivo(descrizione="Studio e redazione", importo=1200.0, tipo=TipoVoce.ONORARIO)],
        creato_da="avv.rossi",
        id_pratica="atto_citazione",
        area_pratica="Civile",
        tipo_compenso="Per fasi processuali (D.M. 55/2014)",
        tipo_procedimento="Civile - fase di cognizione",
    )

    conferimento = gp.crea_conferimento(
        id_cliente="cli-1",
        oggetto="Incarico giudiziale per recupero credito",
        avvocato_referente="Avv. Rossi",
        creato_da="avv.rossi",
        id_preventivo=preventivo.id,
    )

    assert conferimento.id_pratica == "atto_citazione"
    assert conferimento.area_pratica == "Civile"

    gp.collega_fascicolo(
        "fasc-001",
        id_preventivo=preventivo.id,
        id_conferimento=conferimento.id,
        converti_preventivo=True,
    )

    gp_reload = GestionePreventivi(str(db_path))
    preventivo_reload = gp_reload.get_preventivo(preventivo.id)
    conferimento_reload = gp_reload.get_conferimento(conferimento.id)

    assert preventivo_reload is not None
    assert conferimento_reload is not None
    assert preventivo_reload.id_fascicolo == "fasc-001"
    assert preventivo_reload.stato == StatoPreventivo.CONVERTITO
    assert conferimento_reload.id_fascicolo == "fasc-001"
