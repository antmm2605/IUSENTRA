"""Sequenza notturna: un lavoro pesante alla volta dalle 21:30, in ordine, con ripresa la notte dopo."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from pct.scheduler_notturno import catena, finestra, guardia
from pct.scheduler_notturno.registro import RegistroNotte
from pct.scheduler_notturno.sequenza import FASI, lavori_della_sequenza, passi_in_ordine

ROMA = ZoneInfo("Europe/Rome")


def _ambiente(chiamati, *, ocr=0, memoria=8000, fallisce=(), spenti=()):
    def lavoro(nome):
        if nome in spenti:
            return SimpleNamespace(func=lambda: None, args=(), kwargs={}, next_run_time=None)

        def esegui():
            chiamati.append(nome)
            if nome in fallisce:
                raise RuntimeError("errore di prova")
            return {"ok": True, "lavorati": 0}

        return SimpleNamespace(func=esegui, args=(), kwargs={}, next_run_time=datetime.now(ROMA))

    scaricati = []
    amb = catena.Ambiente(lavoro, lambda: memoria, lambda: ocr, lambda: scaricati.append(1) or ["m"])
    return amb, scaricati


def _giro(registro, amb, momento):
    return catena.esegui_passo(registro, amb, momento, adesso=lambda: momento)


def test_ordine_per_dipendenza():
    numeri = [f.numero for f in FASI]
    assert numeri == sorted(numeri)
    ordine = [p.lavoro for _f, p in passi_in_ordine()]
    assert ordine.index("mailbox_sync_runtime") < ordine.index("pec_fascicolo_documenti_recupero")
    assert ordine.index("pec_fascicolo_documenti_recupero") < ordine.index("__fase_3")
    assert ordine.index("__fase_3") < ordine.index("archivio_letture_automatico")
    assert ordine.index("archivio_letture_automatico") < ordine.index("fascicoli_document_economic_presidio")
    assert ordine.index("fascicoli_document_economic_presidio") < ordine.index("catalogo_seconda_lettura_lex")
    assert ordine.index("rag_rispezzatura_notturna") < ordine.index("legal_updates_batch")
    assert len(ordine) == len(set(ordine))


def test_finestra_e_sera():
    assert finestra.in_finestra(datetime(2026, 11, 3, 21, 30, tzinfo=ROMA))
    assert finestra.in_finestra(datetime(2026, 11, 4, 7, 29, tzinfo=ROMA))
    assert not finestra.in_finestra(datetime(2026, 11, 4, 7, 30, tzinfo=ROMA))
    assert not finestra.in_finestra(datetime(2026, 11, 3, 21, 29))  # naive = ora di Roma
    assert finestra.sera_della_notte(datetime(2026, 11, 4, 2, 0, tzinfo=ROMA)).isoformat() == "2026-11-03"


def test_un_passo_per_giro_e_fallimento_non_blocca(tmp_path):
    registro = RegistroNotte(tmp_path / "r.sqlite")
    chiamati = []
    amb, _ = _ambiente(chiamati, fallisce={"mailbox_sync_runtime"})
    momento = datetime(2026, 11, 3, 21, 31, tzinfo=ROMA)
    primo = _giro(registro, amb, momento)
    assert primo["esito"] == "fallito" and chiamati == ["mailbox_sync_runtime"]
    secondo = _giro(registro, amb, momento)
    assert secondo["esito"] == "completato" and chiamati[-1] == "pec_audit_pipeline_workers"
    assert secondo["risultato"]["totals"]["lavorati"] == 0
    assert secondo["avvio"] == momento.isoformat(timespec="seconds")
    assert registro.passi("2026-11-03")[0]["esito"] == "fallito"


def test_attesa_ocr_e_ai_scaricata(tmp_path):
    registro = RegistroNotte(tmp_path / "r.sqlite")
    amb, scaricati = _ambiente([], ocr=5)
    momento = datetime(2026, 11, 3, 22, 0, tzinfo=ROMA)
    while True:
        esito = _giro(registro, amb, momento)
        if esito.get("skipped"):
            break
    assert "coda OCR" in esito["message"] and scaricati
    amb.ocr_in_coda = lambda: 0
    assert _giro(registro, amb, momento)["esito"] == "completato"


def test_ripresa_la_notte_dopo(tmp_path):
    registro = RegistroNotte(tmp_path / "r.sqlite")
    chiamati = []
    amb, _ = _ambiente(chiamati)
    _giro(registro, amb, datetime(2026, 11, 3, 23, 0, tzinfo=ROMA))
    _giro(registro, amb, datetime(2026, 11, 3, 23, 1, tzinfo=ROMA))
    assert _giro(registro, amb, datetime(2026, 11, 4, 7, 45, tzinfo=ROMA))["skipped"]
    _giro(registro, amb, datetime(2026, 11, 4, 21, 30, tzinfo=ROMA))
    # Ogni notte riparte dalla fase 1; resta annotato dove si era fermata la notte prima.
    assert chiamati[-1] == "mailbox_sync_runtime"
    assert "fermata al passo 3" in registro.avanzamento("2026-11-04")["ripresa_da"]


def test_lavori_spenti_e_settimanali(tmp_path):
    registro = RegistroNotte(tmp_path / "r.sqlite")
    amb, _ = _ambiente([], spenti={"mailbox_sync_runtime"})
    assert _giro(registro, amb, datetime(2026, 11, 3, 22, 0, tzinfo=ROMA))["esito"] == "spento"


def test_attesa_memoria(tmp_path):
    registro = RegistroNotte(tmp_path / "r.sqlite")
    chiamati = []
    amb, _ = _ambiente(chiamati, memoria=300)
    esito = _giro(registro, amb, datetime(2026, 11, 3, 22, 0, tzinfo=ROMA))
    assert esito["skipped"] and "memoria" in esito["message"] and not chiamati


def test_guardia_notte_giorno(monkeypatch):
    monkeypatch.setattr(guardia, "catena_in_servizio", lambda: True)
    lavoro = "legal_updates_batch"
    assert lavoro in lavori_della_sequenza()
    assert guardia.motivo_per_saltare(lavoro, datetime(2026, 11, 3, 23, 15, tzinfo=ROMA))
    assert not guardia.motivo_per_saltare(lavoro, datetime(2026, 11, 3, 12, 0, tzinfo=ROMA))
    assert guardia.motivo_per_saltare("archivio_letture_automatico", datetime(2026, 11, 3, 23, 0, tzinfo=ROMA))
    assert not guardia.motivo_per_saltare("archivio_letture_automatico", datetime(2026, 11, 3, 10, 0, tzinfo=ROMA))
    assert not guardia.motivo_per_saltare("mailbox_sync_runtime", datetime(2026, 11, 3, 23, 0, tzinfo=ROMA))
    assert guardia.motivo_per_saltare("catalogo_seconda_lettura_lex", datetime(2026, 11, 3, 10, 0, tzinfo=ROMA))
    chiamate = []
    custodito = guardia.custodisci("aggiorna_scadute", lambda: chiamate.append(1) or {"ok": True})
    assert guardia.esegui_in_catena(custodito)["ok"] and chiamate == [1]
    monkeypatch.setattr(guardia, "catena_in_servizio", lambda: False)
    assert not guardia.motivo_per_saltare(lavoro, datetime(2026, 11, 3, 23, 15, tzinfo=ROMA))


def test_registrato_nel_registro_pianificazioni():
    from pct.scheduler_registry import default_scheduler_templates

    tpl = {t.key: t for t in default_scheduler_templates({})}["sequenza_notturna"]
    assert tpl.built_in and tpl.hour == "21-23,0-7"


def test_semaforo_occupato_non_avanza_e_non_blocca(tmp_path):
    registro = RegistroNotte(tmp_path / "r.sqlite")
    occupato = {"ok": True, "skipped": True, "reason": guardia.SEMAFORO_OCCUPATO, "message": "occupato"}
    risposte = [occupato, {"ok": True, "lavorati": 1}]
    amb = catena.Ambiente(lambda nome: SimpleNamespace(func=lambda: risposte.pop(0), args=(), kwargs={},
                                                       next_run_time=datetime.now(ROMA)),
                          lambda: 8000, lambda: 0, lambda: [])
    momento = datetime(2026, 11, 3, 21, 31, tzinfo=ROMA)
    primo = _giro(registro, amb, momento)
    assert primo["skipped"] and registro.avanzamento("2026-11-03")["indice"] == 0
    secondo = _giro(registro, amb, momento)
    assert secondo["esito"] == "completato" and registro.avanzamento("2026-11-03")["indice"] == 1


def test_attesa_del_semaforo_limitata(monkeypatch):
    attese = []

    class _Finto:
        def __init__(self, *a, attesa_massima=None, **k):
            attese.append(attesa_massima)

        def __enter__(self):
            return True

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(guardia, "motore_pesante", _Finto)
    monkeypatch.setattr(guardia, "catena_in_servizio", lambda: False)
    guardia.esegui_in_catena(guardia.custodisci("legal_updates_batch", lambda: {"ok": True}))
    assert attese == [guardia.ATTESA_CATENA_SECONDI]
    # I lavori leggeri a orario fisso (PEC, avvisi) non aspettano il semaforo.
    assert guardia.custodisci("mailbox_sync_runtime", lambda: {"ok": True})()["ok"] and len(attese) == 1
    # Il coordinatore delle letture non trattiene il semaforo necessario ai propri thread.
    lavoro = guardia.custodisci("archivio_letture_automatico", lambda: {"ok": True})
    assert guardia.esegui_in_catena(lavoro)["ok"] and len(attese) == 1
    monkeypatch.setattr(guardia, "catena_in_servizio", lambda: True)
    monkeypatch.setattr(guardia.finestra, "in_finestra", lambda *_: True)
    manuale = guardia.custodisci("legal_updates_batch", lambda: {"ok": True})
    assert manuale()["skipped"] and len(attese) == 1
    assert guardia.esegui_manualmente(manuale)["ok"] and attese[-1] == guardia.ATTESA_DIURNA_SECONDI
    assert not guardia.motivo_per_saltare("daily_plan_incremental_refresh")



def test_semaforo_occupato_troppo_a_lungo_rinvia_il_passo(tmp_path):
    """Notte del 04/11/2026: un passo in attesa del semaforo ha fermato la catena dalle 05:08 alle 07:30."""
    registro = RegistroNotte(tmp_path / "r.sqlite")
    occupato = {"ok": True, "skipped": True, "reason": guardia.SEMAFORO_OCCUPATO, "message": "occupato"}
    amb = catena.Ambiente(lambda nome: SimpleNamespace(func=lambda: dict(occupato), args=(), kwargs={},
                                                       next_run_time=datetime.now(ROMA)),
                          lambda: 8000, lambda: 0, lambda: [])
    inizio = datetime(2026, 11, 3, 21, 31, tzinfo=ROMA)
    assert _giro(registro, amb, inizio)["skipped"]
    assert _giro(registro, amb, inizio + timedelta(minutes=10))["skipped"]
    rinviato = _giro(registro, amb, inizio + timedelta(minutes=21))
    assert rinviato["esito"] == "rinviato" and registro.avanzamento("2026-11-03")["indice"] == 1


def test_la_catena_aspetta_un_lavoro_gia_avviato_da_un_altro_giro(tmp_path):
    registro = RegistroNotte(tmp_path / "scheduler.sqlite")
    momento = datetime(2026, 11, 3, 21, 31, tzinfo=ROMA)
    occupato = SimpleNamespace(
        func=lambda: {"ok": True, "skipped": True, "reason": guardia.LAVORO_IN_CORSO},
        args=(), kwargs={}, next_run_time=momento,
    )
    amb = catena.Ambiente(lambda _nome: occupato, lambda: 8000, lambda: 0, lambda: [])
    assert _giro(registro, amb, momento)["skipped"]
    assert registro.avanzamento("2026-11-03")["indice"] == 0
    assert not registro.passi("2026-11-03")


def test_il_registro_aggiunge_i_risultati_e_preserva_le_prove_storiche(tmp_path):
    import sqlite3

    from pct.scheduler_notturno.registro import SCHEMA

    db = tmp_path / "scheduler.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript(SCHEMA.replace("    risultato_json TEXT NOT NULL DEFAULT '{}',\n", ""))
        conn.execute(
            "INSERT INTO notte_passi(sera,indice,fase,lavoro,esito) VALUES (?,?,?,?,?)",
            ("2026-11-10", 0, 1, "mailbox_sync_runtime", "completato"),
        )
    registro = RegistroNotte(db)
    esito = registro.passo("2026-11-10", 0)
    assert esito["esito"] == "completato" and esito["risultato"] == {}


def test_esito_senza_riscontro_o_parziale_non_e_completato(tmp_path):
    registro = RegistroNotte(tmp_path / "r.sqlite")
    momento = datetime(2026, 11, 3, 21, 31, tzinfo=ROMA)
    risultati = iter((None, {"ok": True, "status": "parziale", "fonti_riuscite": 2},
                      {"ok": False, "summary": "Registro degli organismi non disponibile."}))
    job = SimpleNamespace(func=lambda: next(risultati), args=(), kwargs={}, next_run_time=momento)
    amb, _ = _ambiente([])
    amb.trova_lavoro = lambda _nome: job

    assert _giro(registro, amb, momento)["esito"] == "fallito"
    secondo = _giro(registro, amb, momento)
    assert secondo["esito"] == "rinviato"
    assert secondo["risultato"]["totals"]["fonti_riuscite"] == 2
    terzo = _giro(registro, amb, momento)
    assert terzo["esito"] == "fallito"
    assert terzo["message"] == "Registro degli organismi non disponibile."


def test_controllo_patrocinio_rispetta_mattina_bimestrale(tmp_path):
    registro = RegistroNotte(tmp_path / "r.sqlite")
    posizione = next(i for i, (_, p) in enumerate(passi_in_ordine()) if p.lavoro == "patrocinio_adeguamento_bimestrale")
    chiamati = []
    amb, _ = _ambiente(chiamati)
    for momento, atteso in (
        (datetime(2026, 11, 1, 2, tzinfo=ROMA), "completato"),
        (datetime(2026, 11, 12, 2, tzinfo=ROMA), "saltato"),
    ):
        sera = finestra.sera_della_notte(momento).isoformat()
        registro.apri_notte(sera, posizione, "", momento.isoformat())
        assert _giro(registro, amb, momento)["esito"] == atteso
    assert chiamati == ["patrocinio_adeguamento_bimestrale"]


def test_riusa_il_giro_periodico_solo_dopo_l_avvio_del_passo(tmp_path):
    registro = RegistroNotte(tmp_path / "r.sqlite")
    chiamati = []
    ambiente, _ = _ambiente(chiamati)
    ora = datetime(2026, 11, 13, 22, 0, tzinfo=ROMA)
    sera = "2026-11-13"
    registro.apri_notte(sera, 0, "", ora.isoformat())
    registro.aggiorna(sera, ora.isoformat(), passo_avviato_alle=ora.isoformat())
    giro = {"origin": "scheduler", "scheduled_at": (ora - timedelta(minutes=1)).isoformat(),
            "finished_at": (ora + timedelta(minutes=2)).isoformat(),
            "result": {"job": "mailbox_sync_runtime", "ok": True, "totals": {"warnings": 0, "channels": 2}}}
    ambiente.ultimo_giro = lambda _nome: giro
    adesso = ora + timedelta(minutes=3)
    passo = passi_in_ordine()[0][1]
    assert not catena._giro_periodico_valido(ambiente, passo, ora, adesso)
    giro["scheduled_at"] = "2026-11-13 22:00:00"
    giro["finished_at"] = "2026-11-13T21:02:00Z"
    giro["result"]["totals"]["warnings"] = 1
    assert not catena._giro_periodico_valido(ambiente, passo, ora, adesso)
    giro["result"]["totals"]["warnings"] = 0
    giro["result"]["scan_mode"] = "mixed:incremental,not_started"
    assert not catena._giro_periodico_valido(ambiente, passo, ora, adesso)
    giro["result"]["scan_mode"] = "incremental"
    giro["run_id"] = "Run-1"
    esito = _giro(registro, ambiente, adesso)
    assert esito["esito"] == "completato" and chiamati == []
    assert esito["risultato"]["mode"] == "riuso_giro_periodico"
    assert esito["risultato"]["run_id"] == "Run-1"


def test_coda_ocr_illeggibile_non_risulta_vuota(tmp_path, monkeypatch):
    from pct.scheduler_notturno import risorse

    queue = tmp_path / "ocr.db"
    queue.write_bytes(b"archivio illeggibile")
    monkeypatch.setenv("PCT_OCR_QUEUE_DB", str(queue))
    registro = RegistroNotte(tmp_path / "r.sqlite")
    momento = datetime(2026, 11, 3, 22, 0, tzinfo=ROMA)
    posizione = next(i for i, (_, p) in enumerate(passi_in_ordine()) if p.lavoro == "__fase_3")
    registro.apri_notte("2026-11-03", posizione, "", momento.isoformat())
    amb, _ = _ambiente([])
    amb.ocr_in_coda = lambda: risorse.ocr_in_coda({})

    prima = _giro(registro, amb, momento)
    assert prima.get("skipped")
    assert "non verificabile" in prima["message"]
    dopo = _giro(registro, amb, momento + catena.ATTESA_OCR_MAX)
    assert dopo["esito"] == "rinviato"
    assert "non verificabile" in dopo["message"]


def test_richiesta_semaforo_resta_in_coda_fino_al_limite_del_passo(tmp_path, monkeypatch):
    from contextlib import contextmanager

    registro = RegistroNotte(tmp_path / "scheduler.sqlite")
    inizio = datetime(2026, 11, 3, 21, 45, tzinfo=ROMA)
    ora = [inizio]
    attese = []

    @contextmanager
    def semaforo(_nome, *, priorita, attesa_massima):
        attese.append(attesa_massima)
        ora[0] += timedelta(seconds=attesa_massima)
        raise guardia.SemaforoOccupato()
        yield

    monkeypatch.setattr(guardia, "motore_pesante", semaforo)
    job = SimpleNamespace(func=guardia.custodisci("mailbox_sync_runtime", lambda: {"ok": True}),
                          args=(), kwargs={}, next_run_time=inizio)
    amb, _ = _ambiente([])
    amb.trova_lavoro = lambda _nome: job
    risultato = catena.esegui_passo(registro, amb, inizio, adesso=lambda: ora[0])
    assert attese == [1200]
    assert risultato["esito"] == "rinviato"
    assert registro.avanzamento("2026-11-03")["indice"] == 1


def test_lotto_esaurito_non_ripete_i_controlli_gia_fatti():
    assert catena._niente_da_fare({"ok": True, "totals": {"esaminati": 25, "restano": 0}})
    assert not catena._niente_da_fare({"ok": True, "totals": {"esaminati": 0, "restano": 2}})
    assert catena._niente_da_fare({"ok": True, "status": "parziale", "restano": 2})
