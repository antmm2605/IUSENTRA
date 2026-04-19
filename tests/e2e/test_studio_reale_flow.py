from __future__ import annotations

from pct.clienti import GestioneClienti, TipoCliente
from pct.economic_pipeline import genera_parcella_da_timesheet
from pct.fascicoli import GestioneFascicoli
from pct.fatturazione import GestioneFatturazione, StatoParcella
from pct.pagamenti import GestionePagamenti
from pct.preventivi import GestionePreventivi, TipoVoce, VocePreventivo
from pct.scadenziario import GestioneScadenziario
from pct.studio_demo import build_studio_demo_snapshot
from pct.timesheet import GestioneTimesheet, StatoTimesheet
from pct.workflow_commerciale import apri_fascicolo_automatico


def test_studio_reale_flow_cliente_preventivo_fascicolo_parcella_incasso(tmp_path):
    clienti = GestioneClienti(db_path=str(tmp_path / "clienti" / "anagrafica.json"))
    preventivi = GestionePreventivi(db_path=str(tmp_path / "preventivi" / "preventivi.json"))
    fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
    )
    scadenze = GestioneScadenziario(str(tmp_path / "scadenziario" / "scadenze.json"))
    timesheet = GestioneTimesheet(db_path=str(tmp_path / "timesheet" / "entries.json"))
    fatturazione = GestioneFatturazione(db_path=str(tmp_path / "fatturazione" / "parcelle.json"))
    pagamenti = GestionePagamenti(db_dir=str(tmp_path / "pagamenti"))

    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Elena",
        cognome="Giovannella",
        codice_fiscale="GVNLNE80A41H224R",
        avvocato_referente="Avv. Demo",
    )
    clienti.aggiorna_indirizzo(
        cliente.id,
        "residenza",
        via="Via Roma 12",
        comune="Palmi",
        provincia="RC",
        cap="89015",
    )
    clienti.aggiorna_recapiti(
        cliente.id,
        email="elena.giovannella@example.it",
        cellulare="3331234567",
    )
    cliente = clienti.get(cliente.id)
    assert cliente is not None
    assert cliente.profilo_completo_per_conferimento is True

    preventivo = preventivi.crea_preventivo(
        id_cliente=cliente.id,
        oggetto="Vendita immobili e attivita' preparatorie",
        voci=[
            VocePreventivo(
                descrizione="Fase iniziale",
                importo=850.0,
                tipo=TipoVoce.ONORARIO,
            )
        ],
        creato_da="superadmin",
        id_pratica="vendita_immobili",
        area_pratica="Civile",
        tipo_compenso="Per fasi processuali (D.M. 55/2014)",
    )
    preventivo, conferimento = preventivi.registra_accettazione_preventivo(
        preventivo.id,
        workflow_channel="ONLINE",
        via="PORTALE_CLIENTE",
        auto_crea_conferimento=True,
        avvocato_referente="Avv. Demo",
    )
    assert conferimento is not None

    conferimento = preventivi.registra_firma_conferimento(
        conferimento.id,
        via="PORTALE_CLIENTE",
        workflow_channel="ONLINE",
    )
    apertura = apri_fascicolo_automatico(
        gp=preventivi,
        gf=fascicoli,
        gs=scadenze,
        cliente=cliente,
        preventivo=preventivi.get_preventivo(preventivo.id),
        conferimento=preventivi.get_conferimento(conferimento.id),
        avvocato="Avv. Demo",
    )
    fascicolo = apertura["fascicolo"]
    assert apertura["created"] is True
    assert fascicolo.id_cliente == cliente.id

    voce = timesheet.crea(
        descrizione="Analisi atti e preparazione prima udienza",
        minuti=90,
        id_fascicolo=fascicolo.id,
        id_cliente=cliente.id,
        username="avv.demo",
        valore_unitario=180.0,
        fatturabile=True,
        stato=StatoTimesheet.APERTO,
        origine="e2e",
    )
    timesheet.cambia_stato(voce.id, StatoTimesheet.VALIDATO)

    billing = genera_parcella_da_timesheet(
        timesheet=timesheet,
        fatturazione=fatturazione,
        creato_da="avv.demo",
        entry_ids=[voce.id],
        data_scadenza="2026-05-15",
    )
    parcella = billing["parcella"]
    assert parcella.id_fascicolo == fascicolo.id

    link = pagamenti.crea_link(
        id_parcella=parcella.id,
        id_cliente=cliente.id,
        importo=parcella.totale,
        descrizione="Saldo parcella fascicolo vendita immobili",
    )
    pagamenti.segna_pagato(link.id, provider="BONIFICO", tx_id="TRX-E2E-001")
    fatturazione.cambia_stato(
        parcella.id,
        StatoParcella.PAGATA,
        data_pagamento="2026-04-19",
        metodo_pagamento="BONIFICO",
    )

    snapshot = build_studio_demo_snapshot(
        clienti=clienti.tutti(),
        preventivi=preventivi.tutti_preventivi(),
        conferimenti=preventivi.tutti_conferimenti(),
        fascicoli=fascicoli.tutti(stato=None),
        timesheet_entries=timesheet.tutte(),
        parcelle=fatturazione.tutte(),
        payment_links=pagamenti.tutti_link(),
    )

    assert snapshot["ready"] is True
    assert snapshot["ready_steps"] == snapshot["steps_total"]
    assert snapshot["saldo_aperto"] == 0.0
    assert snapshot["link_incasso_attivi"] == 0
    assert snapshot["next_action"].startswith("Il ciclo cliente -> incasso")
