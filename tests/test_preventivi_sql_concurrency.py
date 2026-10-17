"""Concorrenza, proiezione consultiva e persistenza dei preventivi SQL."""

import json
import os
from types import MethodType, SimpleNamespace

import pytest

from pct.preventivi import GestionePreventivi, StatoPreventivo, StatoConferimento
from pct.preventivi_sql_writer import PreventiviConflict, PREVENTIVI_COLUMNS, CONFERIMENTI_COLUMNS
from pct.storage import StudioDB


@pytest.fixture
def bank(tmp_path):
    factory = None
    if os.environ.get("PREVENTIVI_TEST_POSTGRES") == "1":
        from tests.test_condivisioni_sql_repository import SQLFactory
        from pct.storage_postgres import PostgresStudioDB

        factory = SQLFactory("postgresql")
        db = factory.new()
        for table, names in (
            ("preventivi_records", PREVENTIVI_COLUMNS),
            ("conferimenti_records", CONFERIMENTI_COLUMNS),
        ):
            integer = {"minuti_stimati", "firma_cliente_eseguita"}
            numeric = {
                "totale",
                "ore_fatturabili_calcolate",
                "compenso_orario_base",
                "massimale_ore",
                "soglia_preapprovazione_ore",
                "compenso_pattuito",
            }
            columns = [
                name
                + (" INTEGER" if name in integer else " DOUBLE PRECISION" if name in numeric else " TEXT")
                + (" PRIMARY KEY" if index == 0 else "")
                for index, name in enumerate(names)
            ]
            db.conn.execute(f"CREATE TABLE {table} ({','.join(columns)})")
        db.conn.execute("CREATE TABLE _meta (chiave TEXT PRIMARY KEY, valore TEXT)")
        from pct.operational_live import ensure_live_schema

        ensure_live_schema(db.conn, postgres=True)
        factory.commit(db)

        def configure(conn):
            conn.chiudi = conn.raw_conn.close
            conn.salva_tabella = MethodType(PostgresStudioDB.salva_tabella, conn)
            conn.fetchall_readonly = lambda sql, parameters=(): conn.conn.execute(sql, parameters).fetchall()
            return conn

        configure(db)
        peer = lambda: configure(factory.new())
    else:
        db = StudioDB(str(tmp_path / "studio.db"))
        peer = lambda: StudioDB(str(tmp_path / "studio.db"))

    def manager(database=None):
        return GestionePreventivi(str(tmp_path / "preventivi.json"), studio_db=database or db)

    first = manager().crea_preventivo(id_cliente="cliente-controllato", oggetto="Primo", voci=[])
    second = manager().crea_preventivo(id_cliente="cliente-controllato", oggetto="Secondo", voci=[])
    try:
        yield db, manager, first.id, second.id, peer, tmp_path
    finally:
        factory.close() if factory else db.chiudi()


def test_sessioni_distinte_conservano_entrambe_le_modifiche(bank):
    db, manager, one, two, peer, _ = bank
    other = peer()
    try:
        a, b = manager(), manager(other)
        a.aggiorna_preventivo(one, oggetto="Prima modifica")
        b.aggiorna_preventivo(two, oggetto="Seconda modifica")
        assert manager().get_preventivo(one).oggetto == "Prima modifica"
        assert manager().get_preventivo(two).oggetto == "Seconda modifica"
    finally:
        other.chiudi()


def test_stessa_voce_concorrente_non_sovrascrive_e_ripristina_snapshot(bank):
    _, manager, one, _, _, _ = bank
    a, b = manager(), manager()
    a.aggiorna_preventivo(one, note="Confermata")
    with pytest.raises(PreventiviConflict):
        b.aggiorna_preventivo(one, note="Obsoleta")
    assert manager().get_preventivo(one).note == "Confermata"
    assert b.get_preventivo(one).note == ""


def test_nuove_righe_e_numerazione_da_snapshot_vecchio(bank):
    _, manager, one, _, _, _ = bank
    a, b = manager(), manager()
    p = a.crea_preventivo(id_cliente="cliente-controllato", oggetto="Nuovo A", voci=[])
    q = b.crea_preventivo(id_cliente="cliente-controllato", oggetto="Nuovo B", voci=[])
    assert p.numero != q.numero
    b.aggiorna_preventivo(one, note="Solo questa")
    assert len(manager().tutti_preventivi()) == 4


def test_cancellazione_puntuale_non_elimina_nuove_righe(bank):
    _, manager, one, two, _, _ = bank
    a, b = manager(), manager()
    p = a.crea_preventivo(id_cliente="cliente-controllato", oggetto="Da conservare", voci=[])
    b.elimina_preventivo(one)
    assert manager().get_preventivo(one) is None
    assert manager().get_preventivo(two) is not None
    assert manager().get_preventivo(p.id) is not None


def test_delete_obsoleto_non_cancella_modifica_confermata(bank):
    _, manager, one, _, _, _ = bank
    a, b = manager(), manager()
    a.aggiorna_preventivo(one, note="Nuova nota")
    with pytest.raises(PreventiviConflict):
        b.elimina_preventivo(one)
    assert manager().get_preventivo(one).note == "Nuova nota"


def test_metadati_non_modellati_preservati(bank):
    db, manager, one, _, _, _ = bank
    row = db.conn.execute("SELECT dati_json FROM preventivi_records WHERE preventivo_id=?", (one,)).fetchone()
    payload = json.loads(row[0])
    payload["provenienza_aggiuntiva"] = {"documento": "prova", "versione": 7}
    db.salva_tabella(
        "preventivi_records",
        [one],
        lambda conn, key: conn.execute(
            "UPDATE preventivi_records SET dati_json=? WHERE preventivo_id=?", (json.dumps(payload), key)
        ),
        delete_all=False,
    )
    manager().aggiorna_preventivo(one, note="Modificata")
    saved = json.loads(
        db.conn.execute("SELECT dati_json FROM preventivi_records WHERE preventivo_id=?", (one,)).fetchone()[0]
    )
    assert saved["provenienza_aggiuntiva"] == payload["provenienza_aggiuntiva"]


def test_identita_immutabile_e_rollback(bank):
    _, manager, one, _, _, _ = bank
    with pytest.raises(ValueError, match="Identificativo"):
        manager().aggiorna_preventivo(one, id="altro")
    assert manager().get_preventivo(one).id == one


def test_proiezione_dal_canonico_senza_file_mirror(bank):
    _, manager, one, _, _, root = bank
    stale = manager()
    manager().aggiorna_preventivo(one, oggetto="Fonte SQL aggiornata")
    payload = stale.repository_payload()
    assert (
        next(row for row in payload["preventivi"] if row["preventivo_id"] == one)["oggetto"] == "Fonte SQL aggiornata"
    )
    assert payload["counts"]["preventivi"] == 2
    assert not list(root.glob("*.json"))
    assert not (root / "preventivi_repository.db").exists()


def test_conferimenti_concorrenti_e_collegamenti(bank):
    _, manager, one, two, _, _ = bank
    c = manager().crea_conferimento(
        avvocato_referente="Avvocato controllato",
        id_cliente="cliente-controllato",
        oggetto="Primo incarico",
        id_preventivo=one,
    )
    d = manager().crea_conferimento(
        avvocato_referente="Avvocato controllato",
        id_cliente="cliente-controllato",
        oggetto="Secondo incarico",
        id_preventivo=two,
    )
    a, b = manager(), manager()
    a.cambia_stato_conferimento(c.id, StatoConferimento.DEFINITO)
    b.cambia_stato_conferimento(d.id, StatoConferimento.REVOCATO)
    assert manager().get_conferimento(c.id).stato == StatoConferimento.DEFINITO
    assert manager().get_conferimento(d.id).id_preventivo == two


def test_revisione_e_conversione_preservano_preventivo(bank):
    _, manager, one, _, _, _ = bank
    gp = manager()
    new = gp.crea_revisione(one)
    assert new.id_preventivo_precedente == one
    p, c = gp.registra_accettazione_preventivo(new.id, via="studio")
    assert c.id_preventivo == p.id
    reopened = manager()
    assert reopened.get_preventivo(new.id).stato == StatoPreventivo.ACCETTATO
    assert reopened.get_conferimento(c.id).id_cliente == "cliente-controllato"


@pytest.mark.parametrize("kind", ["preventivo", "conferimento"])
def test_stato_http_rifiuta_revisione_obsoleta_senza_audit(bank, monkeypatch, kind):
    _, manager, one, _, _, _ = bank
    from web.services import react_preventivi_bridge as bridge

    item = (
        manager().get_preventivo(one)
        if kind == "preventivo"
        else manager().crea_conferimento(
            avvocato_referente="Avvocato controllato", id_cliente="cliente-controllato", oggetto="Incarico"
        )
    )
    calls = []
    monkeypatch.setattr(bridge, "_audit", lambda *args: calls.append(args))
    function = getattr(bridge, f"update_react_{kind}_status")
    kwargs = {f"id_{kind}": item.id}
    result, status = function(
        get_preventivi=manager,
        get_utenti=lambda: None,
        current_user=SimpleNamespace(ha_permesso=lambda value: True),
        payload={"stato": "BOZZA" if kind == "preventivo" else "ATTIVO", "revision": "obsoleta"},
        **kwargs,
    )
    assert status == 409
    assert not result["ok"] and not calls


def test_proiezione_ha_parita_con_regole_del_repository_esistente(bank):
    _, manager, _, _, _, root = bank
    from pct.preventivi import Preventivo, ConferimentoIncarico
    from pct.preventivi_repository import GestionePreventiviRepository

    gp = manager()
    classic = GestionePreventiviRepository(str(root / "parita.db"))
    classic.synchronize_runtime(
        preventivi=gp.tutti_preventivi(),
        conferimenti=gp.tutti_conferimenti(),
        preventivo_model=Preventivo,
        conferimento_model=ConferimentoIncarico,
        export_json=False,
    )
    actual = gp.repository_payload()
    expected = classic.load_repository_payload()
    assert actual["counts"] == expected["counts"]
    for key in ("preventivi", "conferimenti", "workflow_states", "rules", "wizard_steps", "practice_catalog"):
        a = sorted(actual[key], key=lambda row: json.dumps(row, sort_keys=True))
        b = sorted(expected[key], key=lambda row: json.dumps(row, sort_keys=True))
        assert a == b, key
    assert actual["field_map"] == expected["field_map"]


def test_collegamento_storico_non_diventa_associazione_durante_modifica_note(bank):
    db, manager, one, _, _, _ = bank
    payload = json.loads(
        db.conn.execute("SELECT dati_json FROM preventivi_records WHERE preventivo_id=?", (one,)).fetchone()[0]
    )
    payload["id_fascicolo"] = "fascicolo-non-presente"
    db.salva_tabella(
        "preventivi_records",
        [one],
        lambda conn, key: conn.execute(
            "UPDATE preventivi_records SET dati_json=? WHERE preventivo_id=?", (json.dumps(payload), key)
        ),
        delete_all=False,
    )
    gp = manager()
    from web.services.react_preventivi_bridge import _preventivo_record

    item = gp.get_preventivo(one)
    record = _preventivo_record(
        item, {"cliente-controllato": SimpleNamespace(nome="Cliente", cognome="Controllato")}, {}
    )
    assert "non presente" in record["associationNotice"]
    gp.aggiorna_preventivo(one, note="Nota indipendente")
    row = db.conn.execute(
        "SELECT id_fascicolo,dati_json FROM preventivi_records WHERE preventivo_id=?", (one,)
    ).fetchone()
    assert row[0] is None
    assert json.loads(row[1])["id_fascicolo"] == "fascicolo-non-presente"


def test_riga_json_non_valida_non_viene_silenziosamente_eliminata(bank):
    db, manager, one, _, _, _ = bank
    db.salva_tabella(
        "preventivi_records",
        [one],
        lambda conn, key: conn.execute("UPDATE preventivi_records SET dati_json='[]' WHERE preventivo_id=?", (key,)),
        delete_all=False,
    )
    with pytest.raises(ValueError, match="Identità"):
        manager()
    assert db.conn.execute("SELECT COUNT(*) FROM preventivi_records").fetchone()[0] == 2


@pytest.mark.parametrize("kind", ["preventivo", "conferimento"])
def test_stato_con_revisione_corrente_salva_e_audita_una_volta(bank, monkeypatch, kind):
    _, manager, one, _, _, _ = bank
    from web.services import react_preventivi_bridge as bridge

    item = (
        manager().get_preventivo(one)
        if kind == "preventivo"
        else manager().crea_conferimento(
            avvocato_referente="Avvocato controllato", id_cliente="cliente-controllato", oggetto="Incarico"
        )
    )
    calls = []
    monkeypatch.setattr(bridge, "_audit", lambda *args: calls.append(args))
    state = "INVIATO" if kind == "preventivo" else "REVOCATO"
    response, status = getattr(bridge, f"update_react_{kind}_status")(
        get_preventivi=manager,
        get_utenti=lambda: None,
        current_user=SimpleNamespace(ha_permesso=lambda value: True),
        payload={"stato": state, "revision": item.revisione},
        **{f"id_{kind}": item.id},
    )
    assert status == 200 and response["ok"] and len(calls) == 1
    assert getattr(manager(), f"get_{kind}")(item.id).stato.value == state


def test_aggiornamento_sql_non_riscrive_tabella_ne_catalogo(bank):
    db, manager, one, _, _, _ = bank
    if not hasattr(db.conn, "set_trace_callback"):
        pytest.skip("Probe delle query SQLite; regole provate anche PostgreSQL")
    trace = []
    db.conn.set_trace_callback(trace.append)
    try:
        gp = manager()
        assert not any(query.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE")) for query in trace)
        trace.clear()
        gp.aggiorna_preventivo(one, note="Comando puntuale")
    finally:
        db.conn.set_trace_callback(None)
    updates = [query for query in trace if query.lstrip().upper().startswith("UPDATE PREVENTIVI_RECORDS")]
    # SQLite ripete lo statement nel trace quando esegue i trigger live.
    assert len(set(updates)) == 1 and "WHERE" in updates[0]
    assert f"preventivo_id='{one}'" in updates[0]
    assert not any(query.lstrip().upper().startswith("DELETE") for query in trace)


def test_cache_di_vista_invalidata_solo_dalla_revisione_confermata(bank, monkeypatch):
    _, manager, one, _, _, _ = bank
    from pct import preventivi_sql_writer as writer

    original = writer.read_rows
    scans = []

    def observe(db, table):
        scans.append(table)
        return original(db, table)

    gp = manager()
    monkeypatch.setattr(writer, "read_rows", observe)
    initial = gp.repository_payload()
    gp.repository_payload()
    assert len(scans) == 2
    manager().aggiorna_preventivo(one, note="Nuova revisione")
    scans.clear()
    updated = gp.repository_payload()
    assert len(scans) == 2
    assert initial["counts"] == updated["counts"]


def test_conflitto_nel_lotto_annulla_anche_la_prima_modifica(bank):
    _, manager, one, two, _, _ = bank
    first, last = sorted((one, two))
    stale = manager()
    manager().aggiorna_preventivo(last, note="Confermata da altra sessione")
    stale.get_preventivo(first).note = "Da annullare"
    stale.get_preventivo(last).note = "Obsoleta"
    with pytest.raises(PreventiviConflict):
        stale._salva_preventivi()
    fresh = manager()
    assert fresh.get_preventivo(first).note == ""
    assert fresh.get_preventivo(last).note == "Confermata da altra sessione"


def test_errore_sorgente_non_mostra_un_archivio_vuoto_valido(bank):
    db, manager, one, _, _, _ = bank
    from web.services.react_preventivi_bridge import build_react_preventivi_payload

    db.salva_tabella(
        "preventivi_records",
        [one],
        lambda conn, key: conn.execute("UPDATE preventivi_records SET dati_json='[]' WHERE preventivo_id=?", (key,)),
        delete_all=False,
    )
    result = build_react_preventivi_payload(
        get_preventivi=manager, get_clienti=lambda: None, get_fascicoli=lambda: None
    )
    assert not result["ok"]
    assert any("non leggibile" in warning["message"] for warning in result["warnings"])
