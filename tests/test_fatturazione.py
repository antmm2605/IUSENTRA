from pathlib import Path
import pytest

from pct.fatturazione import GestioneFatturazione, VoceParcella
from pct.preventivi import GestionePreventivi, VocePreventivo
from pct.storage import StudioDB


def test_sql_draft_rejects_stale_writer_and_preserves_its_cache(tmp_path: Path):
    from pct.fatturazione import parcella_revision, ParcellaConcurrentUpdate
    db = StudioDB.get(str(tmp_path / 'studio.db'))
    try:
        first = GestioneFatturazione(db_path=str(tmp_path / 'parcelle.json'), studio_db=db)
        document = first.crea(id_cliente='cliente-1', note='Iniziale',
            voci=[VoceParcella(descrizione='Compenso', quantita=1, prezzo_unitario=260)])
        revision = parcella_revision(document)
        other = GestioneFatturazione(db_path=str(tmp_path / 'parcelle.json'), studio_db=db)
        first.aggiorna(document.id, expected_revision=revision, note='Salvataggio primo utente')
        with pytest.raises(ParcellaConcurrentUpdate):
            other.aggiorna(document.id, expected_revision=revision, note='Bozza concorrente')
        assert other.get(document.id).note == 'Iniziale'
        fresh = GestioneFatturazione(db_path=str(tmp_path / 'parcelle.json'), studio_db=db)
        assert fresh.get(document.id).note == 'Salvataggio primo utente'
        token = parcella_revision(fresh.get(document.id))
        fresh.aggiorna(document.id, expected_revision=token, note='Ripresa consapevole')
        assert fresh.get(document.id).note == 'Ripresa consapevole'
    finally:
        db.chiudi()


def test_sql_draft_deleted_after_opening_is_not_recreated(tmp_path: Path):
    from pct.fatturazione import parcella_revision, ParcellaConcurrentUpdate
    db = StudioDB.get(str(tmp_path / 'studio.db'))
    try:
        manager = GestioneFatturazione(db_path=str(tmp_path / 'parcelle.json'), studio_db=db)
        document = manager.crea(id_cliente='cliente-1',
            voci=[VoceParcella(descrizione='Compenso', quantita=1, prezzo_unitario=260)])
        token = parcella_revision(document)
        db.conn.execute('DELETE FROM parcelle WHERE id=?', (document.id,))
        db.conn.commit()
        with pytest.raises(ParcellaConcurrentUpdate):
            manager.aggiorna(document.id, expected_revision=token, note='Salvataggio tardivo')
        assert db.conn.execute('SELECT id FROM parcelle WHERE id=?', (document.id,)).fetchone() is None
    finally:
        db.chiudi()


def test_preventivo_salva_log_calcolo(tmp_path: Path):
    db_path = tmp_path / "preventivi.json"
    gp = GestionePreventivi(db_path=str(db_path))

    preventivo = gp.crea_preventivo(
        id_cliente="cliente-1",
        oggetto="Preventivo prova",
        voci=[VocePreventivo(descrizione="Compenso", importo=1000.0)],
        log_calcolo='{"source":"preventivo_guidato","pratica_label":"Mediazione civile"}',
    )

    gp_reload = GestionePreventivi(db_path=str(db_path))
    loaded = gp_reload.get_preventivo(preventivo.id)

    assert loaded is not None
    assert loaded.log_calcolo
    assert "Mediazione civile" in loaded.log_calcolo


def test_parcella_salva_provenienza_e_log_calcolo(tmp_path: Path):
    db_path = tmp_path / "parcelle.json"
    gf = GestioneFatturazione(db_path=str(db_path))

    parcella = gf.crea(
        id_cliente="cliente-1",
        id_preventivo="prev-123",
        origine="preventivo",
        id_pratica="negoziazione_assistita",
        area_pratica="Stragiudiziale",
        tipo_compenso="Per fasi processuali (D.M. 55/2014)",
        tipo_procedimento="Negoziazione assistita — Procedura ADR",
        valore_controversia=10000.0,
        complessita="media",
        log_calcolo='{"source":"parcella_da_preventivo","adr":{"enabled":true,"accordo":true}}',
        voci=[VoceParcella(descrizione="Compenso", quantita=1, prezzo_unitario=1000.0)],
        note="Compenso professionale",
    )

    gf_reload = GestioneFatturazione(db_path=str(db_path))
    loaded = gf_reload.get(parcella.id)

    assert loaded is not None
    assert loaded.id_preventivo == "prev-123"
    assert loaded.origine == "preventivo"
    assert loaded.id_pratica == "negoziazione_assistita"
    assert loaded.log_calcolo
    assert '"accordo":true' in loaded.log_calcolo


def test_parcella_associa_la_procedura_operativa(tmp_path: Path):
    db_path = tmp_path / "parcelle.json"
    gf = GestioneFatturazione(db_path=str(db_path))

    parcella = gf.crea(
        id_cliente="cliente-1",
        id_preventivo="prev-ric-001",
        origine="preventivo",
        id_pratica="ricorso_tributario",
        area_pratica="Tributario",
        tipo_compenso="Per fasi processuali (D.M. 55/2014)",
        tipo_procedimento="Ricorso tributario di primo grado",
        voci=[VoceParcella(descrizione="Compenso", quantita=1, prezzo_unitario=1200.0)],
    )

    gf_reload = GestioneFatturazione(db_path=str(db_path))
    loaded = gf_reload.get(parcella.id)

    assert loaded is not None
    assert loaded.procedura_operativa_codice == "PROC_TRIB_RIC_002"
    assert loaded.canale_operativo == "PTT_TRIBUTARIO"
    assert loaded.registro_operativo == "PTT_TRIBUTARIO"


def test_parcella_personalizzata_calcola_spese_generali_spese_e_anticipazioni(tmp_path: Path):
    db_path = tmp_path / "parcelle.json"
    gf = GestioneFatturazione(db_path=str(db_path))

    parcella = gf.crea(
        id_cliente="cliente-1",
        data_emissione="2026-05-10",
        data_scadenza="2026-06-09",
        applica_iva=True,
        applica_cassa=True,
        applica_ritenuta=True,
        percentuale_spese_generali=15,
        voci=[
            VoceParcella(descrizione="Compenso professionale", quantita=1, prezzo_unitario=200.0, tipo="ONORARIO"),
            VoceParcella(descrizione="Spese imponibili", quantita=1, prezzo_unitario=20.0, tipo="SPESE"),
            VoceParcella(descrizione="Contributo unificato", quantita=1, prezzo_unitario=43.5, tipo="ANTICIPO"),
        ],
    )

    assert parcella.totale_competenze == 200.0
    assert parcella.totale_spese_imponibili == 20.0
    assert parcella.totale_anticipazioni == 43.5
    assert parcella.spese_generali == 30.0
    assert parcella.imponibile == 250.0
    assert parcella.cassa_forense == 10.0
    assert parcella.base_iva == 260.0
    assert parcella.iva == 57.2
    assert parcella.ritenuta == 46.0
    assert parcella.totale_documento == 360.7
    assert parcella.totale == 314.7


def test_parcella_personalizzata_salva_tipo_voci_e_snapshot_documento(tmp_path: Path):
    db_path = tmp_path / "parcelle.json"
    gf = GestioneFatturazione(db_path=str(db_path))

    parcella = gf.crea(
        id_cliente="cliente-1",
        percentuale_spese_generali=15,
        metodo_pagamento="Bonifico",
        voci=[VoceParcella(descrizione="Visura", quantita=1, prezzo_unitario=18.0, tipo="SPESE")],
        dati_personalizzati={
            "document": {
                "tipo_documento": "TD01",
                "numero_documento": "2026/005",
                "causale_oggetto": "Parcella fascicolo RG 120/2026",
            },
            "payment": {
                "modalita_pagamento_label": "Bonifico",
                "iban": "IT60X0542811101000000123456",
            },
        },
    )

    gf_reload = GestioneFatturazione(db_path=str(db_path))
    loaded = gf_reload.get(parcella.id)

    assert loaded is not None
    assert loaded.percentuale_spese_generali == 15
    assert loaded.metodo_pagamento == "Bonifico"
    assert loaded.voci[0].tipo == "SPESE"
    assert loaded.dati_personalizzati["document"]["numero_documento"] == "2026/005"
    assert loaded.dati_personalizzati["payment"]["iban"] == "IT60X0542811101000000123456"


def test_parcella_salva_tracciamento_sdi_senza_canale_simulato(tmp_path: Path):
    db_path = tmp_path / "parcelle.json"
    gf = GestioneFatturazione(db_path=str(db_path))

    parcella = gf.crea(
        id_cliente="cliente-1",
        voci=[VoceParcella(descrizione="Compenso professionale", quantita=1, prezzo_unitario=300.0)],
        sdi_stato="INVIATA",
        sdi_identificativo="987654321",
        sdi_canale="intermediario esterno",
        sdi_data_invio="2026-06-02T10:30:00+02:00",
        sdi_ricevuta="Attesa ricevuta SdI",
        sdi_note="Invio registrato dall'intermediario",
    )

    gf_reload = GestioneFatturazione(db_path=str(db_path))
    loaded = gf_reload.get(parcella.id)

    assert loaded is not None
    assert loaded.sdi_stato == "INVIATA"
    assert loaded.sdi_identificativo == "987654321"
    assert loaded.sdi_canale == "intermediario esterno"
    assert loaded.sdi_ricevuta == "Attesa ricevuta SdI"
    assert loaded.sdi_note == "Invio registrato dall'intermediario"


def test_parcella_forfettaria_non_calcola_iva_anche_se_opzione_attiva(tmp_path: Path):
    db_path = tmp_path / "parcelle.json"
    gf = GestioneFatturazione(db_path=str(db_path))

    parcella = gf.crea(
        id_cliente="cliente-1",
        data_emissione="2026-05-10",
        data_scadenza="2026-06-09",
        applica_iva=True,
        applica_cassa=True,
        percentuale_spese_generali=15,
        voci=[VoceParcella(descrizione="Compenso professionale", quantita=1, prezzo_unitario=258.0, tipo="ONORARIO")],
        dati_personalizzati={
            "document": {
                "regime_fiscale": "RF19",
            },
        },
    )

    assert parcella.iva_applicabile is False
    assert parcella.base_iva == 308.57
    assert parcella.iva == 0.0
    assert parcella.totale_documento == 308.57
    assert parcella.totale == 308.57


def test_parcella_sqlite_aggiorna_singolo_record_senza_full_replace(tmp_path: Path):
    studio_db_path = tmp_path / "studio.db"
    studio_db = StudioDB.get(str(studio_db_path))
    try:
        gf = GestioneFatturazione(db_path=str(tmp_path / "parcelle.json"), studio_db=studio_db)
        prima = gf.crea(
            id_cliente="cliente-1",
            voci=[VoceParcella(descrizione="Compenso", quantita=1, prezzo_unitario=100.0)],
        )
        seconda = gf.crea(
            id_cliente="cliente-2",
            voci=[VoceParcella(descrizione="Compenso", quantita=1, prezzo_unitario=200.0)],
        )

        calls = []
        original_salva_tabella = studio_db.salva_tabella

        def spy_salva_tabella(table, rows, inserter, delete_all=True):
            calls.append((table, len(rows), delete_all))
            return original_salva_tabella(table, rows, inserter, delete_all)

        studio_db.salva_tabella = spy_salva_tabella  # type: ignore[method-assign]

        gf.aggiorna(prima.id, note="Aggiornata senza sostituire tutta la tabella")

        assert calls == [("parcelle", 1, False)]
        rows = studio_db.conn.execute("SELECT id, dati_json FROM parcelle ORDER BY id").fetchall()
        assert {row["id"] for row in rows} == {prima.id, seconda.id}
        payload = {
            row["id"]: row["dati_json"]
            for row in rows
        }
        assert "Aggiornata senza sostituire tutta la tabella" in payload[prima.id]
    finally:
        StudioDB.invalidate(str(studio_db_path))


@pytest.fixture(params=['sqlite', 'postgresql'])
def invoice_status_db(request, tmp_path):
    if request.param == 'sqlite':
        db = StudioDB.get(str(tmp_path / 'status.db'))
        try:
            yield db
        finally:
            db.chiudi()
        return
    import os
    import re
    if not os.getenv('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato.')
    from psycopg2.extensions import make_dsn
    from pct.storage_postgres import PostgresStudioDB, CORE_POSTGRES_SCHEMA_SQL
    from tests.test_condivisioni_sql_repository import SQLFactory
    factory = SQLFactory('postgresql')
    db = PostgresStudioDB(make_dsn(**factory.pg_parameters, options=f'-c search_path={factory.schema}'), initialize_schema=False)
    try:
        for table in ('clienti', 'fascicoli', 'parcelle', 'payment_links'):
            ddl = re.search(r'CREATE TABLE IF NOT EXISTS ' + table + r' \(.*?\);', CORE_POSTGRES_SCHEMA_SQL, re.S)
            assert ddl is not None
            db.conn.execute(ddl.group(0))
        db.conn.execute("INSERT INTO clienti(id) VALUES ('cliente-1')")
        db.raw_conn.commit()
        yield db
    finally:
        db.chiudi()
        factory.close()


def test_sql_status_api_rejects_stale_manager_without_overwriting_notes(tmp_path, invoice_status_db):
    from types import SimpleNamespace
    from pct.fatturazione import parcella_revision, StatoParcella
    from web.services.react_fatturazione_archive_actions import update_react_fatturazione_status
    db = invoice_status_db
    writer = GestioneFatturazione(str(tmp_path / 'parcelle.json'), studio_db=db)
    item = writer.crea(id_cliente='cliente-1', note='Prima versione',
        voci=[VoceParcella(descrizione='Compenso', quantita=1, prezzo_unitario=260)])
    stale = GestioneFatturazione(str(tmp_path / 'parcelle.json'), studio_db=db)
    writer.aggiorna(item.id, expected_revision=parcella_revision(item), note='Modifica confermata da altro utente')
    events = []
    result, status = update_react_fatturazione_status(
        get_fatturazione=lambda: stale,
        get_utenti=lambda: SimpleNamespace(registra_evento=lambda *a, **kw: events.append((a, kw))),
        current_user=SimpleNamespace(id='op', username='op', ha_permesso=lambda p: True),
        id_documento=item.id, payload={'stato': 'ANNULLATA'})
    assert status == 409, result
    saved = GestioneFatturazione(str(tmp_path / 'parcelle.json'), studio_db=db).get(item.id)
    assert saved.note == 'Modifica confermata da altro utente'
    assert saved.stato == StatoParcella.BOZZA
    assert stale.get(item.id).stato == StatoParcella.BOZZA
    assert not events


def test_sql_status_api_keeps_client_revision_until_confirmation(tmp_path, invoice_status_db):
    from types import SimpleNamespace
    from pct.fatturazione import parcella_revision, StatoParcella
    from web.services.react_fatturazione_archive_actions import update_react_fatturazione_status
    db = invoice_status_db
    manager = GestioneFatturazione(str(tmp_path / 'parcelle.json'), studio_db=db)
    item = manager.crea(id_cliente='cliente-1', note='Prima versione',
        voci=[VoceParcella(descrizione='Compenso', quantita=1, prezzo_unitario=260)])
    read_revision = parcella_revision(item)
    manager.aggiorna(item.id, expected_revision=read_revision, note='Nuova versione')
    user = SimpleNamespace(id='op', username='op', ha_permesso=lambda p: True)
    audit = SimpleNamespace(registra_evento=lambda *a, **kw: None)
    result, status = update_react_fatturazione_status(get_fatturazione=lambda: manager,
        get_utenti=lambda: audit, current_user=user, id_documento=item.id,
        payload={'stato': 'ANNULLATA', 'expected_revision': read_revision})
    assert status == 409, result
    current_revision = parcella_revision(manager.get(item.id))
    result, status = update_react_fatturazione_status(get_fatturazione=lambda: manager,
        get_utenti=lambda: audit, current_user=user, id_documento=item.id,
        payload={'stato': 'ANNULLATA', 'expected_revision': current_revision})
    assert status == 200, result
    saved = GestioneFatturazione(str(tmp_path / 'parcelle.json'), studio_db=db).get(item.id)
    assert saved.note == 'Nuova versione' and saved.stato == StatoParcella.ANNULLATA
    assert result['item']['revision'] == parcella_revision(saved)


def test_legacy_status_with_exported_revision_persists_the_new_state(tmp_path):
    from types import SimpleNamespace
    from pct.fatturazione import parcella_revision, StatoParcella
    from web.services.react_fatturazione_archive_actions import update_react_fatturazione_status
    path = str(tmp_path / 'legacy.json')
    manager = GestioneFatturazione(path)
    item = manager.crea(id_cliente='controlled', voci=[VoceParcella(descrizione='Voce', prezzo_unitario=100)])
    result, status = update_react_fatturazione_status(
        get_fatturazione=lambda: manager,
        get_utenti=lambda: SimpleNamespace(registra_evento=lambda *a, **kw: None),
        current_user=SimpleNamespace(id='op', ha_permesso=lambda p: True),
        id_documento=item.id, payload={'stato': 'ANNULLATA', 'expected_revision': parcella_revision(item)})
    assert status == 200, result
    assert GestioneFatturazione(path).get(item.id).stato == StatoParcella.ANNULLATA


@pytest.mark.parametrize('command', ['incasso', 'pagamento'])
def test_income_commands_preserve_the_displayed_invoice_revision(tmp_path, invoice_status_db, command):
    from types import SimpleNamespace
    from pct.fatturazione import parcella_revision, StatoParcella
    from web.services.react_incassi_pagamenti_bridge import register_react_incasso, update_react_pagamento_status
    manager = GestioneFatturazione(str(tmp_path / 'invoices.json'), studio_db=invoice_status_db)
    invoice = manager.crea(id_cliente='cliente-1', voci=[VoceParcella(descrizione='Compenso', prezzo_unitario=100)])
    original = parcella_revision(invoice)
    manager.aggiorna(invoice.id, expected_revision=original, note='Ultima modifica confermata')
    events = []
    payment = SimpleNamespace(id='payment-controlled', id_parcella=invoice.id, provider_usato='manuale')
    payments = SimpleNamespace(tutti_link=lambda: [payment],
        segna_pagato=lambda *a: pytest.fail('Pagamento modificato dopo conflitto'))
    kwargs = dict(get_fatturazione=lambda: manager, get_pagamenti=lambda: payments,
        get_utenti=lambda: SimpleNamespace(registra_evento=lambda *a, **kw: events.append(a)),
        current_user=SimpleNamespace(id='op', ha_permesso=lambda p: True), ip_address='')
    if command == 'incasso':
        result, status = register_react_incasso(**kwargs, payload={'id_parcella': invoice.id, 'expected_revision': original})
    else:
        result, status = update_react_pagamento_status(**kwargs, payment_id=payment.id,
            payload={'stato': 'PAGATO', 'expected_revision': original})
    assert status == 409, result
    persisted = GestioneFatturazione(str(tmp_path / 'invoices.json'), studio_db=invoice_status_db).get(invoice.id)
    assert persisted.stato == StatoParcella.BOZZA and persisted.note == 'Ultima modifica confermata'
    assert not persisted.data_pagamento and not events
