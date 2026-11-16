"""V31: la scheda del fascicolo non mostra appuntamenti di altri procedimenti (RG 538/2026, 31/10/2026)."""

from __future__ import annotations

from types import SimpleNamespace

from web.services.react_fascicoli_bridge import _agenda_for_fascicolo


def _app(id_, **campi):
    base = dict(id=id_, titolo="", note="", procedimento="", cliente="", tribunale="", external_source_url="",
                external_profile_id="", external_uid="", id_fascicolo="", data_ora="2026-10-01T09:00:00", stato="PROGRAMMATO")
    base.update(campi)
    return SimpleNamespace(**base)


def test_solo_il_ruolo_completo_del_fascicolo_e_le_voci_collegate():
    fascicolo = SimpleNamespace(id="1F244953", numero_rg="538", anno_rg="2026", rg="538/2026",
                                source_external_id="", source_snapshot=None)
    voci = [
        _app("altro-anno", titolo="Udienza del 20/04/2023", procedimento="RG 538/2024"),
        _app("hash-pec", titolo="PEC ricevuta: annotazione - RG 1814/2024", procedimento="RG 1814/2024",
             external_uid="PEC_RICEZIONE:pec_7597a50ec12804242eb3d2c41ae66649575d25fc6f2892ded642ab0ae0538bf5"),
        _app("numero-nel-testo", titolo="Termine note - RG 901/2026", note="protocollo 538 del registro"),
        _app("giusta", titolo="Deposito note scritte - 15/09/2026 - RG 538/2026", procedimento="RG 538/2026"),
        _app("collegata", titolo="Udienza", id_fascicolo="1F244953", procedimento="RG 538/2024"),
        _app("altro-fascicolo", titolo="Udienza RG 538/2026", id_fascicolo="ZZZ"),
    ]
    agenda = SimpleNamespace(tutti=lambda: voci)
    assert {a.id for a in _agenda_for_fascicolo(lambda: agenda, fascicolo)} == {"giusta", "collegata"}


def test_agenda_del_fascicolo_prima_i_prossimi_poi_i_passati_in_tono_neutro(monkeypatch):
    """V34: promemoria PEC del 2024 e udienze del 2023 non restano in testa né «da attenzionare»."""
    from datetime import date
    from types import SimpleNamespace

    from web.services import react_fascicoli_bridge as bridge

    monkeypatch.setattr(bridge, "oggi_rome", lambda: date(2026, 10, 31))
    voci = bridge._appointments([
        SimpleNamespace(id="A", titolo="Udienza del 20/04/2023", data_ora="2023-04-20T09:00:00", tipo="UDIENZA"),
        SimpleNamespace(id="B", titolo="Classifica PEC e conferma adempimenti", data_ora="2024-06-04T09:00:00+02:00", tipo="SCADENZA"),
        SimpleNamespace(id="C", titolo="Udienza di discussione", data_ora="2026-11-24T09:30:00", tipo="UDIENZA"),
        SimpleNamespace(id="D", titolo="Termine note", data_ora="2026-11-01T09:00:00", tipo="SCADENZA"),
    ])
    assert [voce["id"] for voce in voci] == ["D", "C", "B", "A"]
    assert [voce["tone"] for voce in voci] == ["warning", "primary", "neutral", "neutral"]
    assert [voce["past"] for voce in voci] == [False, False, True, True]



def test_agenda_sql_consulta_il_fascicolo_senza_materializzare_le_voci_degli_altri():
    import json
    import sqlite3

    from pct.calendar_sql_records import appointment_candidates_for_case, appointment_from_row

    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE appuntamenti (id TEXT PRIMARY KEY, dati_json TEXT)")
        elementi = [
            ("diretto", "F1", "Udienza", ""),
            ("storico", "", "Termine note per RG 538/2026", ""),
            ("altro-anno", "", "Udienza per RG 538/2025", ""),
            ("altro-fascicolo", "F2", "Udienza per RG 538/2026", ""),
        ]
        for id_, fascicolo_id, titolo, procedimento in elementi:
            dati = {"id": id_, "id_fascicolo": fascicolo_id, "titolo": titolo, "procedimento": procedimento,
                    "tipo": "UDIENZA", "stato": "PROGRAMMATO", "durata_minuti": 30, "luogo": "", "data_ora": "2026-10-01T09:00:00"}
            conn.execute("INSERT INTO appuntamenti VALUES (?,?)", (id_, json.dumps(dati)))
        database = SimpleNamespace(fetchall_readonly=lambda sql, params=(): conn.execute(sql, params).fetchall())
        tutti = [appointment_from_row(row) for row in conn.execute("SELECT * FROM appuntamenti")]
        caso = SimpleNamespace(id="F1", numero_rg="538", anno_rg="2026", rg="538/2026", source_snapshot=None)

        def candidati(fid):
            letti = appointment_candidates_for_case(database, fid)
            assert {app.id for app in letti} == {"diretto", "storico", "altro-anno"}
            return letti

        def caricamento_completo():
            raise AssertionError("Il dettaglio SQL non deve caricare l'Agenda completa")

        vecchi = _agenda_for_fascicolo(lambda: SimpleNamespace(tutti=lambda: tutti), caso)
        nuovi = _agenda_for_fascicolo(caricamento_completo, caso, candidati=candidati)
        assert [app.id for app in nuovi] == [app.id for app in vecchi] == ["diretto", "storico"]


def test_scadenziario_sql_consulta_solo_le_scadenze_collegate():
    import json
    import sqlite3

    from pct.calendar_sql_records import deadlines_for_case

    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE scadenze (id TEXT PRIMARY KEY, id_fascicolo TEXT, data_scadenza TEXT, dati_json TEXT)")
        for id_, giorno, stato in (("seconda", "2026-12-16", "BOZZA"), ("prima", "2026-12-01", "APERTO")):
            dati = {"id": id_, "titolo": id_, "data_scadenza": giorno, "id_fascicolo": "F1", "stato": stato}
            conn.execute("INSERT INTO scadenze VALUES (?,?,?,?)", (id_, "F1", giorno, json.dumps(dati)))
        conn.execute("INSERT INTO scadenze VALUES ('altra', 'F2', '2026-12-01', 'non decodificare')")
        database = SimpleNamespace(fetchall_readonly=lambda sql, params: conn.execute(sql, params).fetchall())
        scadenze = deadlines_for_case(database, "F1")
        assert [(s.id, s.stato.value) for s in scadenze] == [("prima", "APERTO"), ("seconda", "BOZZA")]
