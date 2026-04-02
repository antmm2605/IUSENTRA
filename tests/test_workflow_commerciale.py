from types import SimpleNamespace

from pct.fascicoli import GestioneFascicoli
from pct.preventivi import GestionePreventivi, StatoPreventivo, TipoVoce, VocePreventivo
from pct.scadenziario import GestioneScadenziario
from pct.workflow_commerciale import apri_fascicolo_automatico, build_workflow_summary


def _cliente_stub():
    return SimpleNamespace(
        id="cli-1",
        nome_completo="Mario Rossi",
        avvocato_referente="Avv. Lucia Verdi",
        profilo_completo_per_conferimento=True,
        campi_mancanti_per_conferimento=[],
    )


def test_registra_accettazione_preventivo_crea_conferimento_online(tmp_path):
    gp = GestionePreventivi(str(tmp_path / "preventivi.json"))
    preventivo = gp.crea_preventivo(
        id_cliente="cli-1",
        oggetto="Recupero credito commerciale",
        voci=[VocePreventivo(descrizione="Studio", importo=1200.0, tipo=TipoVoce.ONORARIO)],
        creato_da="avv.rossi",
        id_pratica="atto_citazione",
        area_pratica="Civile",
        tipo_compenso="Per fasi processuali (D.M. 55/2014)",
    )

    p, conferimento = gp.registra_accettazione_preventivo(
        preventivo.id,
        workflow_channel="ONLINE",
        via="PORTALE_CLIENTE",
        ip="127.0.0.1",
        user_agent="pytest",
        avvocato_referente="Avv. Rossi",
        auto_crea_conferimento=True,
    )

    assert p.stato == StatoPreventivo.ACCETTATO
    assert p.workflow_channel == "ONLINE"
    assert p.accettato_via == "PORTALE_CLIENTE"
    assert conferimento is not None
    assert conferimento.id_preventivo == preventivo.id
    assert conferimento.workflow_channel == "ONLINE"
    assert conferimento.firma_cliente_richiesta is True


def test_build_workflow_summary_identifica_step_firma(tmp_path):
    gp = GestionePreventivi(str(tmp_path / "preventivi.json"))
    cliente = _cliente_stub()
    preventivo = gp.crea_preventivo(
        id_cliente=cliente.id,
        oggetto="Appello civile",
        voci=[VocePreventivo(descrizione="Compenso", importo=1800.0, tipo=TipoVoce.ONORARIO)],
        creato_da="avv.rossi",
        id_pratica="appello_civile",
        area_pratica="Civile",
        tipo_compenso="Per fasi processuali (D.M. 55/2014)",
    )
    _, conferimento = gp.registra_accettazione_preventivo(
        preventivo.id,
        workflow_channel="STUDIO",
        via="STUDIO",
        auto_crea_conferimento=True,
        avvocato_referente="Avv. Rossi",
    )

    summary = build_workflow_summary(
        cliente=cliente,
        preventivo=gp.get_preventivo(preventivo.id),
        conferimento=conferimento,
        fascicolo=None,
    )

    assert summary["next_step_key"] == "firma"
    assert "firma" in summary["next_step_label"].lower()
    assert summary["channel_label"] == "Studio"
    assert summary["checklist_preview"]


def test_apri_fascicolo_automatico_crea_checklist_e_scadenze(tmp_path):
    gp = GestionePreventivi(str(tmp_path / "preventivi.json"))
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "documenti"),
        archive_dir=str(tmp_path / "archivio"),
    )
    gs = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    cliente = _cliente_stub()

    preventivo = gp.crea_preventivo(
        id_cliente=cliente.id,
        oggetto="Amministrazione di sostegno",
        voci=[VocePreventivo(descrizione="Compenso", importo=950.0, tipo=TipoVoce.ONORARIO)],
        creato_da="avv.verdi",
        id_pratica="amministrazione_sostegno",
        area_pratica="Civile",
        tipo_compenso="Per fasi processuali (D.M. 55/2014)",
    )
    _, conferimento = gp.registra_accettazione_preventivo(
        preventivo.id,
        workflow_channel="ONLINE",
        via="PORTALE_CLIENTE",
        auto_crea_conferimento=True,
        avvocato_referente="Avv. Lucia Verdi",
    )
    gp.registra_firma_conferimento(conferimento.id, via="PORTALE_CLIENTE", workflow_channel="ONLINE")

    result = apri_fascicolo_automatico(
        gp=gp,
        gf=gf,
        gs=gs,
        cliente=cliente,
        preventivo=gp.get_preventivo(preventivo.id),
        conferimento=gp.get_conferimento(conferimento.id),
        avvocato="Avv. Lucia Verdi",
    )

    fascicolo = result["fascicolo"]
    assert result["created"] is True
    assert fascicolo.id_cliente == cliente.id
    assert gp.get_preventivo(preventivo.id).id_fascicolo == fascicolo.id
    assert gp.get_conferimento(conferimento.id).id_fascicolo == fascicolo.id
    assert len(fascicolo.attivita) >= 3
    assert len(gs.tutte(id_fascicolo=fascicolo.id)) == 3


def test_apri_fascicolo_automatico_comparsa_risposta_genera_attivita_specifiche(tmp_path):
    gp = GestionePreventivi(str(tmp_path / "preventivi.json"))
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "documenti"),
        archive_dir=str(tmp_path / "archivio"),
    )
    gs = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    cliente = _cliente_stub()

    preventivo = gp.crea_preventivo(
        id_cliente=cliente.id,
        oggetto="Preventivo professionale per comparsa di costituzione e risposta",
        voci=[VocePreventivo(descrizione="Compenso", importo=1100.0, tipo=TipoVoce.ONORARIO)],
        creato_da="avv.verdi",
        id_pratica="comparsa_risposta",
        area_pratica="Civile",
        tipo_compenso="Per fasi processuali (D.M. 55/2014)",
    )
    _, conferimento = gp.registra_accettazione_preventivo(
        preventivo.id,
        workflow_channel="STUDIO",
        via="STUDIO",
        auto_crea_conferimento=True,
        avvocato_referente="Avv. Lucia Verdi",
    )
    gp.registra_firma_conferimento(conferimento.id, via="STUDIO", workflow_channel="STUDIO")

    result = apri_fascicolo_automatico(
        gp=gp,
        gf=gf,
        gs=gs,
        cliente=cliente,
        preventivo=gp.get_preventivo(preventivo.id),
        conferimento=gp.get_conferimento(conferimento.id),
        avvocato="Avv. Lucia Verdi",
    )

    fascicolo = result["fascicolo"]
    titles = [att.titolo.lower() for att in fascicolo.attivita]
    descriptions = [att.descrizione.lower() for att in fascicolo.attivita]

    assert any("166-167" in title or "termine di costituzione" in title for title in titles)
    assert any("citazione" in desc and "procura" in desc for desc in descriptions)
    assert any(att.tipo.value == "DEPOSITO_ATTI" for att in fascicolo.attivita)
    assert any("166-167" in (sc.titolo + " " + sc.descrizione) for sc in gs.tutte(id_fascicolo=fascicolo.id))
