"""Test per lo scadenziario legale intelligente."""

import json

import pytest
from datetime import date, timedelta

from pct.scadenziario import (
    GestioneScadenziario,
    ModalitaOperativa,
    ProfiloTermine,
    calcola_scadenza_avanzata,
    profili_termine_builtin,
    regola_patrono_studio,
    regola_patrono_ufficio,
    regole_calendario_nazionali,
    riepilogo_operativo_scadenza,
    Scadenza,
    TipoTermine,
    PrioritaTermine,
    StatoTermine,
    PRESET_TERMINI,
    calcola_termine,
    festività_italiane,
    è_giorno_lavorativo,
    prossimo_giorno_lavorativo,
    _calcola_pasqua,
)
from pct.auth import GestioneUtenti
from pct.config_studio import GestioneConfigStudio
from web.app import create_app


@pytest.fixture
def gs(tmp_path):
    return GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))


# ------------------------------------------------------------------ Festività e giorni lavorativi

def test_pasqua_2024():
    p = _calcola_pasqua(2024)
    assert p == date(2024, 3, 31)


def test_pasqua_2025():
    p = _calcola_pasqua(2025)
    assert p == date(2025, 4, 20)


def test_festività_fisse_2024():
    feste = festività_italiane(2024)
    assert date(2024, 1, 1) in feste   # Capodanno
    assert date(2024, 4, 25) in feste  # Liberazione
    assert date(2024, 6, 2) in feste   # Repubblica
    assert date(2024, 8, 15) in feste  # Ferragosto
    assert date(2024, 12, 25) in feste # Natale


def test_pasquetta_2024():
    feste = festività_italiane(2024)
    assert date(2024, 4, 1) in feste  # Lunedì dell'Angelo


def test_sabato_non_lavorativo():
    sabato = date(2024, 1, 6)  # Sabato (e anche Epifania)
    assert not è_giorno_lavorativo(sabato)


def test_domenica_non_lavorativa():
    domenica = date(2024, 1, 7)
    assert not è_giorno_lavorativo(domenica)


def test_capodanno_non_lavorativo():
    assert not è_giorno_lavorativo(date(2024, 1, 1))


def test_agosto_non_lavorativo_con_feriale():
    """Agosto è non-lavorativo quando sospensione_feriale=True."""
    assert not è_giorno_lavorativo(date(2024, 8, 5))  # Lunedì normale
    assert not è_giorno_lavorativo(date(2024, 8, 20))


def test_agosto_lavorativo_senza_feriale():
    """Agosto è lavorativo quando sospensione_feriale=False."""
    lunedi_agosto = date(2024, 8, 5)
    assert è_giorno_lavorativo(lunedi_agosto, sospensione_feriale=False)


def test_giorno_lavorativo_normale():
    """Un giovedì normale è lavorativo."""
    assert è_giorno_lavorativo(date(2024, 1, 11))


def test_prossimo_giorno_lavorativo_da_domenica():
    domenica = date(2024, 1, 7)
    lun = prossimo_giorno_lavorativo(domenica)
    assert lun == date(2024, 1, 8)


def test_prossimo_giorno_lavorativo_da_sabato():
    sabato = date(2024, 1, 6)
    lun = prossimo_giorno_lavorativo(sabato)
    assert lun == date(2024, 1, 8)


# ------------------------------------------------------------------ Calcolo termini

def test_calcola_termine_liberi():
    """30 giorni processuali di calendario, con esclusione del dies a quo."""
    d = date(2024, 1, 15)  # Lunedì
    scad = calcola_termine(d, 30, tipo="liberi", sospensione_feriale=False)
    assert scad == date(2024, 2, 14)


def test_calcola_termine_continui():
    """L'alias 'continui' resta disponibile per retrocompatibilità."""
    d = date(2024, 1, 15)
    scad = calcola_termine(d, 30, tipo="continui", sospensione_feriale=False)
    assert scad == date(2024, 2, 14)


def test_calcola_termine_lavorativi():
    """Il tipo lavorativi conta solo i giorni utili di studio/cancelleria."""
    d = date(2024, 1, 15)
    scad = calcola_termine(d, 5, tipo="lavorativi", sospensione_feriale=False)
    assert scad == date(2024, 1, 22)


def test_calcola_termine_con_sospensione_feriale():
    """Ad agosto il termine resta sospeso e riprende a settembre."""
    d = date(2024, 7, 25)
    scad = calcola_termine(d, 10, tipo="liberi", sospensione_feriale=True)
    assert scad == date(2024, 9, 4)


def test_termine_proroga_domenica():
    """Se la scadenza cade di domenica, viene prorogata a lunedì."""
    # Trovare una data dove il +30 cade di domenica
    # Data 2024-04-28 + 30 continui = 2024-05-28 (martedì) — troviamo altro
    # 2024-01-01 + 30 = 2024-01-31 (mercoledì) - no
    # 2024-02-04 + 30 continui = 2024-03-05 (martedì)
    # Usiamo 2024-03-10 + 30 = 2024-04-09 (martedì)
    # Usiamo un approccio: cerchiamo una domenica come risultato base
    for days_offset in range(1, 60):
        d_test = date(2024, 3, 1) + timedelta(days=days_offset)
        d_raw = d_test + timedelta(days=30)
        if d_raw.weekday() == 6:  # domenica
            scad = calcola_termine(d_test, 30, tipo="continui", sospensione_feriale=False)
            assert scad.weekday() != 6  # non domenica
            assert scad == d_raw + timedelta(days=1)
            break


def test_impugnazione_30gg():
    preset = PRESET_TERMINI["impugnazione_sentenza_civile"]
    assert preset["giorni"] == 30
    assert preset["tipo"] == "liberi"


def test_appello_lungo_6mesi():
    preset = PRESET_TERMINI["appello_lungo"]
    assert preset["mesi"] == 6
    assert preset["tipo"] == "continui"


def test_opposizione_decreto_ingiuntivo():
    preset = PRESET_TERMINI["opposizione_decreto_ingiuntivo"]
    assert preset["giorni"] == 40


# ------------------------------------------------------------------ CRUD Scadenze

def test_nuova_scadenza(gs):
    domani = (date.today() + timedelta(days=10)).isoformat()
    sc = gs.nuova(
        titolo="Deposito memoria",
        tipo=TipoTermine.DEPOSITO_MEMORIA,
        data_scadenza=domani,
    )
    assert sc.id is not None
    assert sc.titolo == "Deposito memoria"
    assert sc.stato == StatoTermine.APERTO


def test_titolo_vuoto_errore(gs):
    with pytest.raises(ValueError):
        gs.nuova("  ", TipoTermine.ALTRO, date.today().isoformat())


def test_nuova_da_preset(gs):
    sc = gs.nuova_da_preset(
        preset_key="impugnazione_sentenza_civile",
        titolo="Appello avverso sentenza n. 123/2024",
        data_decorrenza=date.today().isoformat(),
    )
    assert sc.id is not None
    assert sc.data_scadenza > date.today().isoformat()
    assert è_giorno_lavorativo(date.fromisoformat(sc.data_scadenza))


def test_nuova_da_preset_mesi(gs):
    sc = gs.nuova_da_preset(
        preset_key="appello_lungo",
        titolo="Appello termine lungo",
        data_decorrenza="2026-01-31",
    )
    assert sc.data_scadenza == "2026-07-31"


def test_preset_inesistente_errore(gs):
    with pytest.raises(ValueError):
        gs.nuova_da_preset("non_esiste", "titolo", date.today().isoformat())


def test_aggiorna_scadenza(gs):
    sc = gs.nuova("Test", TipoTermine.ALTRO, (date.today() + timedelta(days=5)).isoformat())
    gs.aggiorna(sc.id, note="Aggiornamento note", perentorio=True)
    aggiornata = gs.get(sc.id)
    assert aggiornata.note == "Aggiornamento note"
    assert aggiornata.perentorio is True


def test_completa_scadenza(gs):
    sc = gs.nuova("Completare", TipoTermine.ALTRO,
                  (date.today() + timedelta(days=5)).isoformat())
    gs.completa(sc.id, note="Fatto")
    completata = gs.get(sc.id)
    assert completata.stato == StatoTermine.COMPLETATO
    assert completata.completata_il != ""


def test_elimina_scadenza(gs):
    sc = gs.nuova("Elimina", TipoTermine.ALTRO,
                  (date.today() + timedelta(days=5)).isoformat())
    gs.elimina(sc.id)
    assert gs.get(sc.id) is None


# ------------------------------------------------------------------ Priorità

def test_priorita_critica_0gg():
    sc = Scadenza(
        id="test",
        tipo=TipoTermine.ALTRO,
        stato=StatoTermine.APERTO,
        titolo="Test",
        data_scadenza=date.today().isoformat(),
    )
    sc.aggiorna_priorita()
    assert sc.priorita == PrioritaTermine.CRITICA


def test_priorita_alta_5gg():
    sc = Scadenza(
        id="test",
        tipo=TipoTermine.ALTRO,
        stato=StatoTermine.APERTO,
        titolo="Test",
        data_scadenza=(date.today() + timedelta(days=5)).isoformat(),
    )
    sc.aggiorna_priorita()
    assert sc.priorita == PrioritaTermine.ALTA


def test_priorita_bassa_60gg():
    sc = Scadenza(
        id="test",
        tipo=TipoTermine.ALTRO,
        stato=StatoTermine.APERTO,
        titolo="Test",
        data_scadenza=(date.today() + timedelta(days=60)).isoformat(),
    )
    sc.aggiorna_priorita()
    assert sc.priorita == PrioritaTermine.BASSA


# ------------------------------------------------------------------ Query

def test_imminenti(gs):
    domani = (date.today() + timedelta(days=1)).isoformat()
    tra_30 = (date.today() + timedelta(days=30)).isoformat()
    gs.nuova("Vicina", TipoTermine.ALTRO, domani)
    gs.nuova("Lontana", TipoTermine.ALTRO, tra_30)
    imm = gs.imminenti(entro_giorni=7)
    assert len(imm) == 1
    assert imm[0].titolo == "Vicina"


def test_scadute_rilevate(gs):
    ieri = (date.today() - timedelta(days=1)).isoformat()
    gs.nuova("Scaduta", TipoTermine.ALTRO, ieri)
    sc = gs.scadute()
    assert len(sc) == 1
    assert sc[0].stato == StatoTermine.SCADUTO


def test_filtra_per_fascicolo(gs):
    gs.nuova("F1", TipoTermine.ALTRO,
             (date.today() + timedelta(days=10)).isoformat(),
             id_fascicolo="FASC001")
    gs.nuova("F2", TipoTermine.ALTRO,
             (date.today() + timedelta(days=10)).isoformat(),
             id_fascicolo="FASC002")
    risultati = gs.tutte(id_fascicolo="FASC001")
    assert all(s.id_fascicolo == "FASC001" for s in risultati)


def test_avvisi_da_notificare(gs):
    """Una scadenza tra 7 giorni deve generare un avviso."""
    tra_7 = (date.today() + timedelta(days=7)).isoformat()
    gs.nuova("Avviso test", TipoTermine.ALTRO, tra_7,
             giorni_preavviso=[7, 3, 1])
    da_notif = gs.scadenze_da_notificare()
    assert len(da_notif) == 1
    assert da_notif[0][1] == 7


def test_segna_avviso_inviato(gs):
    tra_7 = (date.today() + timedelta(days=7)).isoformat()
    sc = gs.nuova("Avviso test 2", TipoTermine.ALTRO, tra_7,
                  giorni_preavviso=[7, 3, 1])
    gs.segna_avviso_inviato(sc.id, 7)
    da_notif = gs.scadenze_da_notificare()
    ids = [s.id for s, _ in da_notif]
    assert sc.id not in ids


# ------------------------------------------------------------------ Persistenza

def test_persistenza(tmp_path):
    db = str(tmp_path / "sc.json")
    gs1 = GestioneScadenziario(db_path=db)
    gs1.nuova("Persistenza", TipoTermine.ALTRO,
              (date.today() + timedelta(days=10)).isoformat())
    gs2 = GestioneScadenziario(db_path=db)
    assert len(gs2.tutte()) == 1
    assert gs2.tutte()[0].titolo == "Persistenza"


# ------------------------------------------------------------------ Statistiche

def test_statistiche(gs):
    domani = (date.today() + timedelta(days=1)).isoformat()
    tra_30 = (date.today() + timedelta(days=30)).isoformat()
    sc1 = gs.nuova("SC1", TipoTermine.ALTRO, domani)
    gs.nuova("SC2", TipoTermine.ALTRO, tra_30)
    gs.completa(sc1.id)
    stats = gs.statistiche()
    assert stats["totale"] == 2
    assert stats["completate"] == 1
    assert stats["aperte"] == 1


def test_calcolo_avanzato_separa_scadenza_legale_e_operativa():
    profile = ProfiloTermine.from_dict(profili_termine_builtin()["TERM_30_DAYS"])
    national = regole_calendario_nazionali()
    procedural = [r for r in national if r.kind == "procedural_suspension"]
    office_rule = regola_patrono_ufficio("trib-palermo", "Patrono ufficio", 15, 7, operating_mode=ModalitaOperativa.CHIUSO.value)
    studio_rule = regola_patrono_studio("default-studio", "Patrono studio", 15, 7)

    result = calcola_scadenza_avanzata(
        start_at="2026-06-15T10:00:00",
        profile=profile,
        national_rules=national,
        office_rules=[office_rule],
        studio_rules=[studio_rule],
        procedural_rules=procedural,
        operational_lead_business_days=2,
    )

    assert result.raw_due_at.startswith("2026-07-15")
    assert result.legal_due_at.startswith("2026-07-16")
    assert result.operational_due_at.startswith("2026-07-13")
    assert result.office_mode_on_legal_due_date == "open"
    assert any("Proroga" in item for item in result.trace)


def test_regola_4_ottobre_non_bloccante_di_default():
    rules = regole_calendario_nazionali()
    oct_rule = next(rule for rule in rules if rule.code == "OCT_4_OBSERVANCE")
    assert oct_rule.applies_to_legal_deadlines is False
    assert oct_rule.operating_mode == "open"

def test_riepilogo_operativo_scadenza_evidenzia_proroga_e_anticipo():
    note = riepilogo_operativo_scadenza(
        trace=["Proroga dal 2026-07-15 al giorno successivo utile", "Giorno sospeso per periodo feriale -> 2026-08-05"],
        operational_due_at="2026-07-13T10:00:00",
        operational_lead_business_days=2,
        october_observance_blocks=True,
        office_patron_day=15,
        office_patron_month=7,
        office_operating_mode=ModalitaOperativa.SOLO_URGENTI.value,
    )
    assert any("prorogata" in item.lower() for item in note)
    assert any("2 giorni lavorativi" in item for item in note)
    assert any("sospensione feriale" in item.lower() for item in note)
    assert any("4 ottobre" in item for item in note)
    assert any("solo atti urgenti" in item.lower() for item in note)
def test_scadenza_avanzata_persistita_salva_trace_e_date(gs):
    sc = gs.nuova(
        titolo="Termine con trace",
        tipo=TipoTermine.ALTRO,
        data_scadenza="2026-07-16",
        raw_due_at="2026-07-15T10:00:00",
        legal_due_at="2026-07-16T10:00:00",
        operational_due_at="2026-07-13T10:00:00",
        deadline_profile_code="TERM_30_DAYS",
        trace_json=json.dumps(["giorno iniziale escluso", "proroga finale"], ensure_ascii=False),
        judicial_office_name="Tribunale di Palermo",
        office_mode_on_legal_due_date="open",
    )
    assert sc.ha_calcolo_avanzato is True
    assert sc.trace == ["giorno iniziale escluso", "proroga finale"]
    assert sc.operational_due_at_obj is not None
    assert any("prorogata" in item.lower() for item in sc.riepilogo_operativo)


def _cfg_web(tmp_path):
    return {
        "TESTING": True,
        "MULTI_TENANT": False,
        "BOOTSTRAP_ADMIN_PASSWORD": "admin",
        "STORAGE_MODE_DEFAULT": "json",
        "AUTH_DB": str(tmp_path / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "VALIDATION_RUNS_DB": str(tmp_path / "validation_runs.json"),
        "REDACTION_ASSISTANT_DB": str(tmp_path / "assistente_redazionale.json"),
        "PREVENTIVI_DB": str(tmp_path / "preventivi.json"),
        "STUDIO_CONFIG": str(tmp_path / "studio.json"),
        "UFFICI_GIUDIZIARI_DB": str(tmp_path / "uffici.json"),
    }


def test_route_calcola_termine_avanzato_restituisce_trace(tmp_path):
    cfg = _cfg_web(tmp_path)
    GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
        bootstrap_admin_password="admin",
    )
    app = create_app(cfg)
    client = app.test_client()
    login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    assert login.status_code == 200

    response = client.post(
        "/scadenziario/calcola-termine",
        json={
            "deadline_profile_code": "TERM_30_DAYS",
            "source_event_at": "2026-06-15T10:00:00",
            "operational_lead_business_days": 2,
            "office_patron_name": "Patrono ufficio",
            "office_patron_day": 15,
            "office_patron_month": 7,
            "office_operating_mode": "closed",
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["data_scadenza"] == "2026-07-16"
    assert data["operational_due_at"].startswith("2026-07-14")
    assert isinstance(data["trace"], list)
    assert any("prorogata" in item.lower() for item in data["operational_notes"])


def test_route_nuova_scadenza_avanzata_salva_note(tmp_path):
    cfg = _cfg_web(tmp_path)
    GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
        bootstrap_admin_password="admin",
    )
    app = create_app(cfg)
    client = app.test_client()
    login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    assert login.status_code == 200

    response = client.post(
        "/scadenziario/nuova",
        data={
            "titolo": "Deposito memoria istruttoria",
            "tipo": TipoTermine.DEPOSITO_MEMORIA.value,
            "deadline_profile_code": "TERM_30_DAYS",
            "source_event_at": "2026-06-15T10:00",
            "note": "Preparare allegati e firma entro il giorno precedente.",
            "perentorio": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    gs = GestioneScadenziario(db_path=cfg["SCADENZIARIO_DB"])
    scadenze = gs.tutte(solo_aperte=False)
    assert len(scadenze) == 1
    assert scadenze[0].note == "Preparare allegati e firma entro il giorno precedente."
    assert scadenze[0].legal_due_at.startswith("2026-07-15")


def test_route_modifica_manuale_azzera_metadati_calcolo_avanzato(tmp_path):
    cfg = _cfg_web(tmp_path)
    GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
        bootstrap_admin_password="admin",
    )
    gs = GestioneScadenziario(db_path=cfg["SCADENZIARIO_DB"])
    sc = gs.nuova(
        titolo="Termine da ripulire",
        tipo=TipoTermine.ALTRO,
        data_scadenza="2026-07-16",
        deadline_profile_code="TERM_30_DAYS",
        source_event_type="notifica",
        source_event_at="2026-06-15T10:00:00",
        raw_due_at="2026-07-15T10:00:00",
        legal_due_at="2026-07-16T10:00:00",
        operational_due_at="2026-07-14T10:00:00",
        office_mode_on_legal_due_date="closed",
        trace_json=json.dumps(["proroga finale"], ensure_ascii=False),
        judicial_office_id="trib-001",
        judicial_office_name="Tribunale test",
    )
    app = create_app(cfg)
    client = app.test_client()
    login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    assert login.status_code == 200

    response = client.post(
        f"/scadenziario/{sc.id}/modifica",
        data={
            "titolo": "Termine manuale",
            "tipo": TipoTermine.ALTRO.value,
            "data_scadenza": "2026-08-20",
            "data_decorrenza": "",
            "descrizione": "Aggiornato manualmente",
            "note": "Senza motore avanzato",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    aggiornato = GestioneScadenziario(db_path=cfg["SCADENZIARIO_DB"]).get(sc.id)
    assert aggiornato is not None
    assert aggiornato.data_scadenza == "2026-08-20"
    assert aggiornato.deadline_profile_code == ""
    assert aggiornato.source_event_at == ""
    assert aggiornato.raw_due_at == ""
    assert aggiornato.legal_due_at == ""
    assert aggiornato.operational_due_at == ""
    assert aggiornato.trace == []
    assert aggiornato.note == "Senza motore avanzato"


def test_route_scadenziario_filtra_avanzate_e_operative(tmp_path):
    cfg = _cfg_web(tmp_path)
    GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
        bootstrap_admin_password="admin",
    )
    gs = GestioneScadenziario(db_path=cfg["SCADENZIARIO_DB"])
    gs.nuova(
        titolo="Termine avanzato",
        tipo=TipoTermine.ALTRO,
        data_scadenza="2026-07-16",
        deadline_profile_code="TERM_30_DAYS",
        legal_due_at="2026-07-16T10:00:00",
        operational_due_at="2026-07-14T10:00:00",
        trace_json=json.dumps(["Proroga finale"], ensure_ascii=False),
    )
    gs.nuova(
        titolo="Termine manuale",
        tipo=TipoTermine.ALTRO,
        data_scadenza="2026-08-20",
    )
    app = create_app(cfg)
    client = app.test_client()
    login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    assert login.status_code == 200

    response = client.get("/scadenziario?avanzate=1&operative=1")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Termine avanzato" in body
    assert "Termine manuale" not in body
    assert "Solo calcolo avanzato" in body
    assert "Solo con anticipo operativo" in body


def test_dettaglio_scadenza_mostra_studio_e_contesto(tmp_path):
    cfg = _cfg_web(tmp_path)
    GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
        bootstrap_admin_password="admin",
    )
    GestioneConfigStudio(config_path=cfg["STUDIO_CONFIG"]).aggiorna_sezione(
        "studio",
        {
            "nome": "Studio Test Palermo",
            "city": "Palermo",
            "patron_name": "Santa Rosalia",
            "patron_day": 15,
            "patron_month": 7,
        },
    )
    gs = GestioneScadenziario(db_path=cfg["SCADENZIARIO_DB"])
    sc = gs.nuova(
        titolo="Termine con contesto",
        tipo=TipoTermine.ALTRO,
        data_scadenza="2026-07-16",
        source_event_type="notifica",
        source_event_at="2026-06-15T10:00:00",
        deadline_profile_code="TERM_30_DAYS",
        legal_due_at="2026-07-16T10:00:00",
        operational_due_at="2026-07-14T10:00:00",
        trace_json=json.dumps(["Proroga finale"], ensure_ascii=False),
        judicial_office_name="Tribunale di Palermo",
        judicial_office_patron_name="Santa Rosalia",
        judicial_office_patron_day=15,
        judicial_office_patron_month=7,
        judicial_office_operating_mode="urgent_only",
        judicial_office_source_url="https://tribunale.example/patrono",
        judicial_office_verified_at="2026-07-01",
        operational_lead_business_days=2,
        october_observance_blocks=True,
    )
    app = create_app(cfg)
    client = app.test_client()
    login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    assert login.status_code == 200

    response = client.get(f"/scadenziario/{sc.id}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Studio Test Palermo" in body
    assert "Santa Rosalia" in body
    assert "Solo atti urgenti" in body
    assert "Osservanza bloccante" in body
    assert "Notifica" in body
