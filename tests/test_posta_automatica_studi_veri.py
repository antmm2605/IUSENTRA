"""Posta automatica: solo gli studi veri, e una casella in errore non blocca nulla.

Decisione dell'avvocato del 19/11/2026: «il 18/11 sera sono rimasti fermi 90 minuti dietro le caselle dello studio di
prova: non devono essere inclusi». Per gli studi veri una casella che non si collega ha un tempo massimo, si riprova
con attesa crescente e lo stesso errore si segnala una volta sola.
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest

from pct.tenant import MOTIVO_ESCLUSO_POSTA, StudioLegale, escluso_dalla_posta_automatica
from web.services import mailbox_sync_runtime as runtime


def test_studio_di_prova_escluso_per_regola_generale():
    assert escluso_dalla_posta_automatica(StudioLegale(slug="studio-prova"))
    assert escluso_dalla_posta_automatica(StudioLegale(slug="studio-demo-rossi", studio_di_prova=True))
    assert not escluso_dalla_posta_automatica(StudioLegale(slug="studio-legale-giuseppe-montagnese"))
    # Il flag si legge anche dal registro degli studi.
    assert StudioLegale.from_dict({"slug": "altro", "studio_di_prova": True}).studio_di_prova is True
    assert MOTIVO_ESCLUSO_POSTA == "studio di prova: escluso dalla posta automatica"


@pytest.fixture()
def contesto(tmp_path):
    runtime.clear_mailbox_sync_runtime_state()
    yield runtime.MailboxRuntimeContext(
        tenant_label="studio-vero",
        data_paths={"EMAIL_CASELLA_DB": str(tmp_path / "casella.json"), "STUDIO_CONFIG": str(tmp_path / "studio.json")},
        config={"IUSENTRA_MAILBOX_SYNC_TIMEOUT_S": "5"},
    )
    runtime.clear_mailbox_sync_runtime_state()


def test_casella_che_non_risponde_non_trattiene_il_giro(contesto, monkeypatch):
    sblocca = threading.Event()

    def casella_ferma(ctx, **kwargs):
        sblocca.wait(10)
        return {"ok": True}

    monkeypatch.setattr(runtime, "_tempo_massimo_casella", lambda ctx: 0.3)
    inizio = time.monotonic()
    esito = runtime._sync_with_runtime_guard("pec", casella_ferma, ctx=contesto, cooldown_seconds=0)
    assert time.monotonic() - inizio < 3, "il giro deve tornare entro il tempo massimo della casella"
    assert esito["ok"] is False and "entro" in esito["result"]["errore"]
    # La sincronizzazione rimasta in sfondo tiene il blocco: il giro dopo non ne apre una seconda.
    assert runtime._sync_with_runtime_guard("pec", casella_ferma, ctx=contesto, cooldown_seconds=0, force=True)["reason"] == "already_running"
    sblocca.set()


def test_errore_ripetuto_con_attesa_crescente_e_segnalato_una_volta(contesto, monkeypatch):
    chiamate = []

    def casella_rotta(ctx, **kwargs):
        chiamate.append(1)
        return {"ok": False, "errore": "Connessione IMAP non completata."}

    orologio = {"t": 1000.0}
    monkeypatch.setattr(runtime, "monotonic", lambda: orologio["t"])
    primo = runtime._sync_with_runtime_guard("pec", casella_rotta, ctx=contesto, cooldown_seconds=0)
    assert primo["result"]["tentativi"] == 1 and not primo["result"].get("gia_segnalato")
    assert primo["result"]["riprova_tra_secondi"] == 300
    # Durante l'attesa la casella non si riprova e non si ripete l'errore.
    orologio["t"] += 60
    attesa = runtime._sync_with_runtime_guard("pec", casella_rotta, ctx=contesto, cooldown_seconds=0)
    assert attesa["skipped"] and attesa["reason"] == "attesa_dopo_errore" and attesa["result"] == {}
    assert len(chiamate) == 1
    orologio["t"] += 300
    secondo = runtime._sync_with_runtime_guard("pec", casella_rotta, ctx=contesto, cooldown_seconds=0)
    assert secondo["result"]["tentativi"] == 2 and secondo["result"]["riprova_tra_secondi"] == 600
    assert secondo["result"]["gia_segnalato"] is True
    # Casella tornata: il conto riparte e un errore nuovo si segnala di nuovo.
    orologio["t"] += 700
    runtime._sync_with_runtime_guard("pec", lambda ctx, **k: {"ok": True}, ctx=contesto, cooldown_seconds=0)
    assert runtime._FALLIMENTI == {}


def test_polling_esiti_deposito_salta_lo_studio_di_prova(monkeypatch):
    from web.services import polling_depositi_runtime as polling

    visti = []
    prova = StudioLegale(slug="studio-prova", nome="Studio Prova")
    vero = StudioLegale(slug="studio-vero", nome="Studio Vero")
    monkeypatch.setattr("web.services.fascicoli_presidi_runtime._active_tenants", lambda app: [prova, vero])
    monkeypatch.setattr(polling, "_credenziali_pdp", lambda app: None)
    monkeypatch.setattr(polling, "_studio", lambda app, manager, studio, **k: visti.append(studio.slug) or {"tenant": studio.slug})
    monkeypatch.setattr("pct.tenant.GestioneTenant", lambda registry_path: SimpleNamespace())
    app = SimpleNamespace(config={"MULTI_TENANT": True, "TENANTS_REGISTRY": "/dev/null"})
    esito = polling.run_polling_esiti_deposito(app, giorni=3)
    assert visti == ["studio-vero"]
    assert esito["studi_esclusi_posta"] == ["studio-prova"]
    assert MOTIVO_ESCLUSO_POSTA in esito["message"]


def test_casella_lenta_in_sfondo_non_rende_fallito_il_giro(contesto, monkeypatch):
    """8080, 23/11/2026: la PEC letta, la posta ordinaria oltre i 240 s finita in sfondo; il giro era registrato
    «failed» e lo scheduler «unhealthy». Ora il giro è completato; dal terzo giro lento di fila diventa un avviso."""
    from pct.scheduler import _esito_canale_nel_log, _esito_canale_posta
    from pct.scheduler_registry import esito_job_result

    sblocca = threading.Event()

    def casella_lenta(ctx, **kwargs):
        sblocca.wait(10)
        return {"ok": True}

    monkeypatch.setattr(runtime, "_tempo_massimo_casella", lambda ctx: 0.2)
    lenta = runtime._sync_with_runtime_guard("ordinary", casella_lenta, ctx=contesto, cooldown_seconds=0)
    sblocca.set()
    canale = _esito_canale_posta(lenta)
    assert lenta["result"]["in_sfondo"] and canale["in_sfondo"]
    assert not canale["warning"] and not canale["errore_del_giro"]
    assert _esito_canale_nel_log(lenta) == "in_sfondo"
    pec = _esito_canale_posta({"ok": True, "result": {"ok": True, "nuove": 6}})
    giro = {"ok": not (canale["errore_del_giro"] or pec["errore_del_giro"]),
            "status": "parziale" if (canale["warning"] or pec["warning"]) else "ok"}
    assert esito_job_result(giro) == ("completed", "")
    # Terzo giro lento di fila: la casella va guardata, il giro torna «parziale».
    terzo = {"ok": False, "skipped": False, "reason": "",
             "result": {"ok": False, "in_sfondo": True, "tentativi": 3, "errore": "Casella non sincronizzata entro 240 secondi."}}
    assert _esito_canale_posta(terzo)["warning"] is True
    # Un errore vero della casella resta un errore del giro e nel log non si legge più «ok».
    rotta = {"ok": False, "skipped": False, "reason": "", "result": {"ok": False, "errore": "Connessione IMAP non completata."}}
    assert _esito_canale_posta(rotta)["errore_del_giro"] and _esito_canale_nel_log(rotta) == "errore"
    assert _esito_canale_nel_log({"ok": True, "skipped": True, "reason": "attesa_dopo_errore"}) == "attesa_dopo_errore"
