"""Sequenza notturna: un lavoro pesante alla volta dalle 21:30, in ordine, con ripresa la notte dopo."""

from __future__ import annotations

from datetime import datetime
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
    assert chiamati[-1] == "poll_pec_cancelleria"
    assert "Ripresa dal passo 3" in registro.avanzamento("2026-11-04")["ripresa_da"]


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
