import json
from types import SimpleNamespace

from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.preventivi import GestionePreventivi, StatoPreventivo, VocePreventivo
from pct.profilo_deposito import costruisci_profilo_deposito
from pct.storage import StudioDB
from pct.workflow_onboarding import build_fascicolo_onboarding


def test_profilo_pct_risolve_ufficio_pec_certificato():
    profilo = costruisci_profilo_deposito(
        tipo="LAVORO",
        canale_operativo="PCT_LAVORO",
        codice_oggetto_pst="222050",
        fonte_codice_oggetto="PST_XSD",
        file_fonte_codice_oggetto="tipi-base.xsd",
        ufficio="Tribunale di Vicenza",
        verifica_certificato=True,
        richiedi_ufficio=True,
    )

    assert profilo["source_of_truth"] == "sqlite_postgresql_record"
    assert profilo["json_authoritative"] is False
    assert profilo["canale"]["codice"] == "pct_civile_dm44"
    assert profilo["ufficio"]["pec"] == "tribunale.vicenza@civile.ptel.giustiziacert.it"
    assert profilo["codice_deposito"]["codice_oggetto_pst"] == "222050"
    assert profilo["certificato_cifratura"]["richiesto"] is True
    assert profilo["certificato_cifratura"]["verificato"] is True
    assert profilo["blocchi"] == []


def test_canali_dedicati_non_usano_certificato_pst():
    casi = [
        ("PDP_PENALE", "pdp_penale"),
        ("PAT_AMMINISTRATIVO", "pat_amministrativo"),
        ("PTT_TRIBUTARIO", "ptt_tributario"),
    ]
    for canale_operativo, atteso in casi:
        profilo = costruisci_profilo_deposito(
            canale_operativo=canale_operativo,
            verifica_certificato=True,
            richiedi_ufficio=False,
        )
        assert profilo["canale"]["codice"] == atteso
        assert profilo["certificato_cifratura"]["richiesto"] is False
        assert profilo["certificato_cifratura"]["verificato"] is True


def test_preventivo_accettato_conferimento_fascicolo_ereditano_profilo(tmp_path):
    gp = GestionePreventivi(
        str(tmp_path / "preventivi.json"),
        sync_repository_on_init=False,
    )
    preventivo = gp.crea_preventivo(
        id_cliente="CLI-1",
        oggetto="Ricorso lavoro per retribuzioni",
        voci=[VocePreventivo("Compenso professionale", 1000.0)],
        id_pratica="ricorso_lavoro_retribuzioni",
        area_pratica="Lavoro e previdenza",
        tipo_procedimento="Ricorso lavoro",
        codice_oggetto_pst="222050",
    )

    assert preventivo.profilo_deposito["canale"]["codice"] == "pct_civile_dm44"
    assert preventivo.profilo_deposito["codice_deposito"]["codice_oggetto_pst"] == "222050"

    preventivo, conferimento = gp.registra_accettazione_preventivo(
        preventivo.id,
        auto_crea_conferimento=True,
    )
    assert preventivo.stato == StatoPreventivo.ACCETTATO
    assert conferimento is not None
    assert conferimento.profilo_deposito["origine"]["profilo_ereditato"] is True
    assert conferimento.profilo_deposito["codice_deposito"]["codice_oggetto_pst"] == "222050"

    cliente = SimpleNamespace(
        id="CLI-1",
        nome_completo="Marchetti Lucia",
        profilo_completo_per_conferimento=True,
    )
    prefill = build_fascicolo_onboarding(
        cliente=cliente,
        preventivo=preventivo,
        conferimento=conferimento,
    )
    gf = GestioneFascicoli(str(tmp_path / "fascicoli.json"))
    fascicolo = gf.nuovo(
        titolo=prefill["titolo"],
        tipo=TipoFascicolo.LAVORO,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="Tribunale di Vicenza",
        oggetto=prefill["oggetto"],
        tipo_procedimento=prefill["tipo_procedimento"],
        id_pratica=prefill["id_pratica"],
        area_pratica=prefill["area_pratica"],
        canale_operativo=prefill["canale_operativo"],
        registro_operativo=prefill["registro_operativo"],
        codice_oggetto_pst=prefill["codice_oggetto_pst"],
        fonte_codice_oggetto=prefill["fonte_codice_oggetto"],
        file_fonte_codice_oggetto=prefill["file_fonte_codice_oggetto"],
        profilo_deposito=prefill["profilo_deposito"],
    )

    assert fascicolo.profilo_deposito["origine"]["profilo_ereditato"] is True
    assert fascicolo.profilo_deposito["ufficio"]["pec"] == "tribunale.vicenza@civile.ptel.giustiziacert.it"
    assert fascicolo.profilo_deposito["certificato_cifratura"]["verificato"] is True


def test_profilo_deposito_popola_colonne_sqlite_dedicate(tmp_path):
    studio_db = StudioDB(str(tmp_path / "studio.db"))
    gp = GestionePreventivi(
        str(tmp_path / "preventivi.json"),
        studio_db=studio_db,
        sync_repository_on_init=False,
    )
    preventivo = gp.crea_preventivo(
        id_cliente="CLI-SQL",
        oggetto="Ricorso lavoro",
        voci=[VocePreventivo("Compenso", 1000.0)],
        id_pratica="ricorso_lavoro_retribuzioni",
        area_pratica="Lavoro e previdenza",
        tipo_procedimento="Ricorso lavoro",
        codice_oggetto_pst="222050",
    )
    preventivo, conferimento = gp.registra_accettazione_preventivo(
        preventivo.id,
        auto_crea_conferimento=True,
    )
    assert conferimento is not None

    gf = GestioneFascicoli(str(tmp_path / "fascicoli.json"), studio_db=studio_db)
    fascicolo = gf.nuovo(
        titolo="Ricorso lavoro",
        tipo=TipoFascicolo.LAVORO,
        id_cliente="CLI-SQL",
        nome_cliente="Marchetti Lucia",
        tribunale="Tribunale di Vicenza",
        canale_operativo="PCT_LAVORO",
        codice_oggetto_pst="222050",
        profilo_deposito=conferimento.profilo_deposito,
    )

    for table, key, value in (
        ("preventivi_records", "preventivo_id", preventivo.id),
        ("conferimenti_records", "conferimento_id", conferimento.id),
        ("fascicoli", "id", fascicolo.id),
    ):
        columns = {
            row["name"]
            for row in studio_db.conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        assert "profilo_deposito_json" in columns
        row = studio_db.conn.execute(
            f"SELECT profilo_deposito_json FROM {table} WHERE {key} = ?",
            (value,),
        ).fetchone()
        assert row is not None
        profilo = json.loads(row["profilo_deposito_json"])
        assert profilo["source_of_truth"] == "sqlite_postgresql_record"
        assert profilo["json_authoritative"] is False


def test_fascicolo_autonomo_risolve_profilo_deposito_senza_preventivo(tmp_path):
    studio_db = StudioDB(str(tmp_path / "studio.db"))
    gf = GestioneFascicoli(str(tmp_path / "fascicoli.json"), studio_db=studio_db)

    fascicolo = gf.nuovo(
        titolo="Ricorso lavoro autonomo",
        tipo=TipoFascicolo.LAVORO,
        nome_cliente="Marchetti Lucia",
        tribunale="Tribunale di Vicenza",
        canale_operativo="PCT_LAVORO",
        registro_operativo="SICID",
        codice_oggetto_pst="222050",
        fonte_codice_oggetto="PST_XSD",
        file_fonte_codice_oggetto="tipi-base.xsd",
    )

    profilo = fascicolo.profilo_deposito
    assert profilo["origine"]["profilo_ereditato"] is False
    assert profilo["canale"]["codice"] == "pct_civile_dm44"
    assert profilo["codice_deposito"]["codice_oggetto_pst"] == "222050"
    assert profilo["ufficio"]["pec"] == "tribunale.vicenza@civile.ptel.giustiziacert.it"
    assert profilo["certificato_cifratura"]["richiesto"] is True
    assert profilo["certificato_cifratura"]["verificato"] is True
    assert profilo["blocchi"] == []

    row = studio_db.conn.execute(
        "SELECT profilo_deposito_json FROM fascicoli WHERE id = ?",
        (fascicolo.id,),
    ).fetchone()
    assert row is not None
    profilo_sql = json.loads(row["profilo_deposito_json"])
    assert profilo_sql["canale"]["codice"] == "pct_civile_dm44"
    assert profilo_sql["ufficio"]["pec"] == "tribunale.vicenza@civile.ptel.giustiziacert.it"
