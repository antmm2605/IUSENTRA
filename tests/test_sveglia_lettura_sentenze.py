"""Il giro che riconosce le sentenze parte quando arriva roba nuova, non a orologio.

Girava ogni dieci minuti e, per concludere che non c'era niente da fare,
elencava decine di migliaia di file: 144 ricognizioni al giorno per reagire a
qualcosa che succede qualche volta a settimana. Chi sa davvero che e' arrivato
un documento e' il motore letture, ed e' lui a chiedere l'esecuzione.
"""

from __future__ import annotations

import web.services.archivio_letture_runtime as runtime


class _Registratore:
    def __init__(self, esplode: bool = False):
        self.chiamate: list[dict] = []
        self.esplode = esplode

    def __call__(self, job_id, *, username="", dedupe_open=False):
        if self.esplode:
            raise RuntimeError("registro non raggiungibile")
        self.chiamate.append({"job_id": job_id, "username": username, "dedupe_open": dedupe_open})
        return {"run_id": "x"}


def _installa(monkeypatch, registratore):
    import web.services.scheduler_admin_surface as superficie

    monkeypatch.setattr(superficie, "request_scheduler_run", registratore, raising=False)


def test_un_documento_nuovo_chiede_il_giro(monkeypatch):
    reg = _Registratore()
    _installa(monkeypatch, reg)

    runtime._sveglia_lettura_sentenze({"documenti_letti": 3, "pec_lette": 0})

    assert len(reg.chiamate) == 1
    assert reg.chiamate[0]["job_id"] == "lex_sentenza_economia_auto"


def test_una_pec_nuova_chiede_il_giro(monkeypatch):
    reg = _Registratore()
    _installa(monkeypatch, reg)

    runtime._sveglia_lettura_sentenze({"documenti_letti": 0, "pec_lette": 1})

    assert len(reg.chiamate) == 1


def test_un_giro_a_vuoto_non_chiede_niente(monkeypatch):
    """Il punto di tutta l'operazione: niente di nuovo, nessun lavoro."""

    reg = _Registratore()
    _installa(monkeypatch, reg)

    runtime._sveglia_lettura_sentenze({"documenti_letti": 0, "pec_lette": 0, "esaminati": 309})

    assert reg.chiamate == []


def test_le_richieste_si_accodano_una_sola_volta(monkeypatch):
    """Un fascicolo con trecento allegati non deve accodare trecento richieste."""

    reg = _Registratore()
    _installa(monkeypatch, reg)

    runtime._sveglia_lettura_sentenze({"documenti_letti": 300, "pec_lette": 0})

    assert reg.chiamate[0]["dedupe_open"] is True


def test_se_il_registro_non_risponde_il_motore_letture_non_si_ferma(monkeypatch):
    """La richiesta e' un'accelerazione: la passata notturna resta la rete."""

    _installa(monkeypatch, _Registratore(esplode=True))

    runtime._sveglia_lettura_sentenze({"documenti_letti": 5, "pec_lette": 2})  # non solleva


def test_il_report_senza_conteggi_non_chiede_niente(monkeypatch):
    reg = _Registratore()
    _installa(monkeypatch, reg)

    runtime._sveglia_lettura_sentenze({})

    assert reg.chiamate == []
