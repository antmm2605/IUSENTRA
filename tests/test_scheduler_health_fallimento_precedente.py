"""Un fallimento della versione precedente non rende guasto lo scheduler appena installato (01/11/2026)."""

from datetime import datetime, timedelta, timezone

from pct.scheduler_health import presidio_heartbeat


class _Registro:
    def __init__(self, fine):
        self.fine = fine

    def latest_runs_by_job(self):
        return {"lettura": {"status": "failed", "finished_at": self.fine.isoformat(), "error_message": "database is locked"}}

    def list_jobs(self):
        return [{"job_id": "lettura", "enabled": 1}]


def test_fallimento_prima_dell_avvio_non_e_guasto_certo():
    adesso = datetime.now(timezone.utc)
    avvio = adesso - timedelta(minutes=2)
    esito = presidio_heartbeat(_Registro(avvio - timedelta(minutes=5)), now=adesso, jobs=(("lettura", "Lettura", 45),), avvio_worker=avvio)
    assert esito["ok"] is False  # resta segnalato come degrado
    assert esito["hard_failures"] == 0  # ma non annulla l'attesa del primo giro


def test_fallimento_dopo_l_avvio_resta_guasto_certo():
    adesso = datetime.now(timezone.utc)
    avvio = adesso - timedelta(minutes=10)
    esito = presidio_heartbeat(_Registro(adesso - timedelta(minutes=1)), now=adesso, jobs=(("lettura", "Lettura", 45),), avvio_worker=avvio)
    assert esito["hard_failures"] == 1
