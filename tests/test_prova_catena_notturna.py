"""Prova della catena notturna «adesso» (deploy/hetzner/prova_catena.py) su un tenant finto.

Stessa prova del collaudo e2e (tests/test_catena_notturna_fascicolo_completo.py): una PEC con la sentenza
attraversa le fasi 1-5 della catena vera, ma sotto la chiave della prova, senza toccare la notte vera.
Base: art. 3 D.M. 44/2011 e art. 20 CAD. Dati sintetici.
"""

from __future__ import annotations

import importlib.util
import threading
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from tests.test_catena_notturna_fascicolo_completo import (  # noqa: F401 - fixture
    _ingesta_e_collega,
    _lavori,
    _LettureInSfondo,
    ambiente,
)

SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "hetzner" / "prova_catena.py"


def _script():
    spec = importlib.util.spec_from_file_location("prova_catena_test", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_fasi_ammesse():
    prova = _script()
    assert prova.fasi_ammesse("1-5") == {1, 2, 3, 4, 5}
    assert prova.fasi_ammesse("2, 4") == {2, 4}
    assert prova.fasi_ammesse("") is None


def test_prova_esegue_le_fasi_1_5_sotto_la_chiave_dedicata(ambiente, monkeypatch):  # noqa: F811
    import web.services.archivio_letture_runtime as archivio
    from pct.scheduler_notturno import catena
    from pct.scheduler_notturno.registro import RegistroNotte

    prova = _script()
    sfondo = _LettureInSfondo()
    monkeypatch.setattr(archivio, "threading", SimpleNamespace(Thread=sfondo.Thread, Lock=threading.Lock, get_ident=threading.get_ident))
    monkeypatch.setattr(catena, "dormi", lambda _s: None)
    _ingesta_e_collega(ambiente.app, ambiente.fascicolo_id)
    db = ambiente.tmp / "scheduler_registry.sqlite"
    registro = prova.registro_di_prova(db, "prova-2026-11-04")
    lavori = _lavori(ambiente.app)
    amb = catena.Ambiente(trova_lavoro=lavori.get, memoria_libera_mb=lambda: 8000, ocr_in_coda=lambda: 0,
                          scarica_ai_locale=list)
    orologio = {"ora": datetime(2026, 11, 4, 15, 0, tzinfo=ZoneInfo("Europe/Rome"))}  # di giorno

    def adesso():
        orologio["ora"] += timedelta(seconds=30)
        sfondo.esegui()
        return orologio["ora"]

    esito = prova.esegui_prova(registro, amb, minuti=50, fasi={1, 2, 3, 4, 5}, adesso=adesso, dormi=lambda _s: sfondo.esegui())
    eseguiti = {p["lavoro"]: p["esito"] for p in esito["passi"]}
    assert esito["motivo_fine"] == "fasi_richieste_concluse", esito
    assert eseguiti["pec_fascicolo_documenti_recupero"] == "completato", esito
    assert eseguiti["archivio_letture_automatico"] == "completato", esito
    assert eseguiti["fascicoli_document_economic_presidio"] == "completato", esito
    assert eseguiti["mailbox_sync_runtime"] == "spento"  # non registrato nel tenant finto
    assert not any(p["fase"] > 5 for p in esito["passi"])
    # Registro: tutto sotto la chiave della prova, nessuna notte vera aperta.
    vero = RegistroNotte(db)
    assert vero.avanzamento("2026-11-04") is None and vero.avanzamento("2026-11-03") is None
    assert vero.passi("prova-2026-11-04") and vero.ultima_notte_prima("2026-11-05") is None
    with ambiente.app.app_context():
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        assert registro_corrente().da_leggere(tenant_corrente(), ambiente.fascicolo_id, "motore_documenti", tipi=("documento",)) == []


def test_prova_si_ferma_al_primo_passo_fallito_e_allo_scadere(tmp_path, monkeypatch):
    from pct.scheduler_notturno import catena

    prova = _script()
    monkeypatch.setattr(catena, "dormi", lambda _s: None)
    rotto = SimpleNamespace(func=lambda: {"ok": False, "error": "guasto"}, args=(), kwargs={}, next_run_time=datetime.now())
    amb = catena.Ambiente(trova_lavoro=lambda nome: rotto if nome == "pec_audit_pipeline_workers" else None,
                          memoria_libera_mb=lambda: 8000, ocr_in_coda=lambda: 0, scarica_ai_locale=list)
    esito = prova.esegui_prova(prova.registro_di_prova(tmp_path / "r.sqlite", "prova-x"), amb, minuti=50)
    assert esito["motivo_fine"] == "passo_fallito" and esito["passi"][-1]["lavoro"] == "pec_audit_pipeline_workers"
    assert esito["passi"][0]["esito"] == "spento"
    # Tempo: un passo che attende sempre (memoria scarsa) non supera la durata massima.
    occupato = SimpleNamespace(func=lambda: None, args=(), kwargs={}, next_run_time=datetime.now())
    amb2 = catena.Ambiente(trova_lavoro=lambda _n: occupato, memoria_libera_mb=lambda: 10, ocr_in_coda=lambda: 0,
                           scarica_ai_locale=list)
    orologio = {"ora": datetime(2026, 11, 4, 15, 0, tzinfo=ZoneInfo("Europe/Rome"))}

    def adesso():
        orologio["ora"] += timedelta(minutes=1)
        return orologio["ora"]

    esito = prova.esegui_prova(prova.registro_di_prova(tmp_path / "r2.sqlite", "prova-y"), amb2, minuti=10,
                               adesso=adesso, dormi=lambda _s: None)
    assert esito["motivo_fine"] == "tempo_scaduto" and esito["attese"]["giri"] > 0


def test_confronto_solo_numeri_cambiati():
    prova = _script()
    prima = {"studi": [{"studio": "studio_1", "sintesi": {"oggetti_da_leggere_dichiarati": 5, "righe": 2}}], "coda_ocr": {"in_coda": 3}}
    dopo = {"studi": [{"studio": "studio_1", "sintesi": {"oggetti_da_leggere_dichiarati": 0, "righe": 2}}], "coda_ocr": {"in_coda": 0}}
    assert prova.confronto(prima, dopo) == {"studio_1": {"sintesi.oggetti_da_leggere_dichiarati": [5, 0]},
                                            "coda_ocr": {"in_coda": [3, 0]}}
