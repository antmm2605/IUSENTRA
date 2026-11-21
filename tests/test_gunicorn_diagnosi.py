"""Diagnosi dei worker: un blocco o una morte del worker lascia il motivo nel log."""
import runpy
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from core import gunicorn_diagnosi as diagnosi

RADICE = Path(__file__).resolve().parents[1]


class _Log:
    def __init__(self):
        self.righe = []

    def warning(self, msg, *args):
        self.righe.append(("warning", msg % args))

    def error(self, msg, *args):
        self.righe.append(("error", msg % args))

    def info(self, msg, *args):
        self.righe.append(("info", msg % args))


def test_configurazione_dichiara_gli_hook():
    conf = runpy.run_path(str(RADICE / "gunicorn.conf.py"))
    for hook in ("child_exit", "post_worker_init", "pre_request", "post_request", "worker_abort", "worker_exit"):
        assert callable(conf[hook]), hook
    assert conf["worker_class"] == "gthread" or conf["worker_class"]


def test_richiesta_lenta_e_thread_occupati_finiscono_nel_log(monkeypatch):
    monkeypatch.setattr(diagnosi, "SOGLIA_LENTA", 0.0)
    log = _Log()
    worker = SimpleNamespace(log=log, pid=123, cfg=SimpleNamespace(threads=1))
    diagnosi.inizio_richiesta(SimpleNamespace(method="GET", path="/api/v1/ui/ricerca-legale"))
    try:
        time.sleep(0.01)
        diagnosi._controlla(worker)
        diagnosi._controlla(worker)  # la pila della stessa richiesta si registra una volta sola
    finally:
        diagnosi.fine_richiesta()
    lente = [r for r in log.righe if "richiesta lenta" in r[1]]
    assert len(lente) == 1 and "/api/v1/ui/ricerca-legale" in lente[0][1]
    assert "test_gunicorn_diagnosi" in lente[0][1]  # c'è la pila del thread
    assert any("tutti i 1 thread" in r[1] for r in log.righe)
    assert diagnosi.richieste_in_corso() == []


def test_interruzione_registra_le_pile_di_tutti_i_thread():
    log = _Log()
    fermo = threading.Event()
    t = threading.Thread(target=fermo.wait, name="ricerca-ferma")
    t.start()
    try:
        diagnosi.registra_pile(log, "prova")
    finally:
        fermo.set(); t.join()
    assert sum("pila del thread" in r[1] for r in log.righe) >= 2


def test_healthcheck_in_forma_exec_con_attesa_piu_breve_del_timeout():
    dockerfile = (RADICE / "Dockerfile").read_text(encoding="utf-8")
    blocco = dockerfile.split("HEALTHCHECK", 1)[1].split("\n\n", 1)[0]
    assert 'CMD ["python"' in blocco and "timeout=4" in blocco and "--timeout=5s" in blocco
    for compose in ("docker-compose.yml", "deploy/hetzner/docker-compose.hetzner.yml"):
        testo = (RADICE / compose).read_text(encoding="utf-8")
        app = testo.split("\n  app:\n", 1)[1].split("\n  # ──", 1)[0] if "deploy" in compose else testo.split("\n  app:\n", 1)[1][:900]
        assert "init: true" in app, compose
