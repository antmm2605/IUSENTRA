"""Lettura del fascicolo a più riprese: progresso salvato, riavvii non contati, documento guasto chiuso.

Verifica del 02/11/2026: in produzione (2.476.0) più fascicoli da ~40 documenti
restavano fermi con «Tempo disponibile per la lettura esaurito dopo tre
tentativi»: tre riavvii dello scheduler (memoria esaurita, deploy) facevano
scadere la prenotazione e ogni scadenza contava come tentativo fallito.
"""

from __future__ import annotations

import threading

import pytest

from pct.fascicoli import TipoDocumento
from tests.test_archivio_letture_runtime import _app, _fascicolo, _pdf, _seed


@pytest.fixture
def lettura(tmp_path, monkeypatch):
    """App con tre documenti, letture contate per documento e indicizzazione esterna neutralizzata."""
    from web.services import archivio_letture_runtime as runtime

    app = _app(tmp_path)
    fid, decreto, relata = _seed(app)
    with app.app_context():
        terzo = app.extensions["core_runtime"]["get_fascicoli"]().aggiungi_documento(
            fid, nome_file="ordinanza.pdf", tipo=TipoDocumento.ALTRO,
            contenuto=_pdf([
                "TRIBUNALE DI TORINO - Sezione Prima Civile - R.G. n. 777/2026",
                "Il Giudice, sentite le parti, rinvia la causa all'udienza del 20/01/2027 alle ore 10.00",
                "per la precisazione delle conclusioni e assegna alle parti i termini di legge.",
                "Si comunichi alle parti costituite a cura della cancelleria.",
            ]),
        )
    letti: list[str] = []
    originale = runtime._leggi_un_documento

    def conta(fascicolo, registro, tenant, fascicolo_id, contesto, oggetto, **kwargs):
        letti.append(oggetto.oggetto_id)
        return originale(fascicolo, registro, tenant, fascicolo_id, contesto, oggetto, **kwargs)

    monkeypatch.setattr(runtime, "_leggi_un_documento", conta)
    monkeypatch.setattr(runtime, "_indicizza_fonti_pendenti", lambda *a, **k: {})
    monkeypatch.setattr(runtime, "OGGETTI_PER_GIRO", 1)
    # Le verifiche finali del fascicolo hanno i loro test: qui conta la coda.
    monkeypatch.setattr("web.services.discordanze_letture_runtime.verifica_discordanze_fascicolo", lambda *a, **k: {})
    return app, fid, [decreto, relata, terzo.id], letti


def _turno(app, fid):
    """Un turno della coda, come lo avvia il tick dello scheduler, atteso fino alla fine."""
    from web.services import archivio_letture_runtime as runtime

    with app.app_context():
        assert runtime.avvia_lettura_in_background(app, fid, _accoda_evento=False)
    for thread in threading.enumerate():
        if thread.name == f"archivio-letture-{fid}":
            thread.join(timeout=120)


def _registro(app):
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

    with app.app_context():
        return registro_corrente(), tenant_corrente()


def test_fascicolo_grande_si_completa_in_piu_turni_senza_rileggere(lettura, monkeypatch):
    from web.services import archivio_letture_runtime as runtime

    app, fid, documenti, letti = lettura
    monkeypatch.setattr(runtime, "SECONDI_PER_TURNO", 0)  # ogni turno chiude dopo un giro
    registro, tenant = _registro(app)
    registro.accoda_evento(tenant, fid)

    _turno(app, fid)
    stato = registro.esito_evento(tenant, fid)
    assert stato["stato"] == "pending" and stato["attempts"] == 0 and not stato["last_error"]
    assert len(letti) == 1

    _turno(app, fid)
    assert len(letti) == 2 and registro.esito_evento(tenant, fid)["stato"] == "pending"

    _turno(app, fid)
    stato = registro.esito_evento(tenant, fid)
    assert stato["stato"] == "idle" and not stato["last_error"]
    assert sorted(letti) == sorted(documenti), "ogni documento letto una sola volta in tutti i turni"
    assert not registro.da_leggere(tenant, fid, runtime.LETTORE_DOCUMENTI, tipi=("documento",))
    with registro.connection() as conn:
        esiti = [r[0] for r in conn.execute(
            "SELECT stato FROM letture_eventi_esiti WHERE fascicolo_id=? ORDER BY attempt", (fid,)).fetchall()]
    assert esiti == ["partial", "partial", "succeeded"]


def test_prenotazione_scaduta_per_riavvio_non_conta_e_riprende_dal_salvato(lettura):
    from web.services import archivio_letture_runtime as runtime

    app, fid, documenti, letti = lettura
    registro, tenant = _registro(app)
    with app.app_context():
        runtime.leggi_fascicolo(_fascicolo(app, fid), limite=1)  # un documento letto prima del riavvio
    assert len(letti) == 1
    registro.accoda_evento(tenant, fid)
    for morto in range(3):  # tre riavvii dello scheduler a metà lavoro
        assert registro.reclama_evento(tenant, fid, f"worker-morto-{morto}")
        with registro.connection() as conn:
            conn.execute("UPDATE letture_eventi SET lease_until='2000-01-01T00:00:00Z' WHERE fascicolo_id=?", (fid,))

    _turno(app, fid)
    stato = registro.esito_evento(tenant, fid)
    assert stato["stato"] == "idle" and not stato["last_error"], stato
    assert sorted(letti) == sorted(documenti), "il turno dopo il riavvio legge solo i documenti mancanti"


def test_documento_sempre_in_errore_si_chiude_e_non_blocca_il_fascicolo(lettura, monkeypatch):
    from web.services import archivio_letture_runtime as runtime

    app, fid, documenti, letti = lettura
    guasto = documenti[0]
    originale = runtime.leggi_testo

    def rotto(testo, **kwargs):
        if (kwargs.get("metadata") or {}).get("documento_id") == guasto:
            raise ValueError("struttura del testo non interpretabile")
        return originale(testo, **kwargs)

    monkeypatch.setattr(runtime, "leggi_testo", rotto)
    registro, tenant = _registro(app)
    registro.accoda_evento(tenant, fid)
    _turno(app, fid)

    stato = registro.esito_evento(tenant, fid)
    assert stato["stato"] == "idle" and not stato["last_error"], stato
    letture = {lt.oggetto_id: lt for lt in registro.letture(tenant, fid, lettore=runtime.LETTORE_DOCUMENTI)}
    assert letture[guasto].stato == "non_leggibile"
    assert "3 volte" in letture[guasto].esito["motivo"] and "struttura del testo" in letture[guasto].esito["motivo"]
    assert all(letture[d].stato == "letto" for d in documenti[1:])
    assert not registro.da_leggere(tenant, fid, runtime.LETTORE_DOCUMENTI, tipi=("documento",))


def test_guasto_del_registro_non_si_attribuisce_al_documento(lettura, monkeypatch):
    import sqlite3

    from web.services import archivio_letture_runtime as runtime

    app, fid, documenti, _letti = lettura
    monkeypatch.setattr(runtime, "leggi_testo", lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")))
    registro, tenant = _registro(app)
    with app.app_context(), pytest.raises(sqlite3.OperationalError):
        runtime.leggi_fascicolo(_fascicolo(app, fid))
    assert {lt.stato for lt in registro.letture(tenant, fid, lettore=runtime.LETTORE_DOCUMENTI)} <= {"letto"}


def test_riconvalida_riprende_i_fermi_storici_senza_rileggere_il_gia_letto(lettura):
    from pct.registro_letture.event_retry import ERRORE_TEMPO_STORICO
    from web.services import archivio_letture_runtime as runtime

    app, fid, documenti, letti = lettura
    registro, tenant = _registro(app)
    with app.app_context():
        runtime.leggi_fascicolo(_fascicolo(app, fid), limite=2)
    gia_letti = list(letti)
    registro.accoda_evento(tenant, fid)
    registro.accoda_evento(tenant, "ALTRO-FERMO")
    with registro.connection() as conn:
        conn.execute("UPDATE letture_eventi SET stato='idle',attempts=3,last_error=?,last_error_code='LeaseExpired'",
                     (ERRORE_TEMPO_STORICO,))
    assert registro.esito_evento(tenant, fid)["stato"] == "failed"

    # Di giorno: si riprendono subito i soli fermi del vecchio conteggio, a lotti.
    assert runtime.riprendi_letture_ferme(registro, tenant, ora=11, limite=1) == 1
    assert runtime.riprendi_letture_ferme(registro, tenant, ora=11, limite=1) == 1
    assert runtime.riprendi_letture_ferme(registro, tenant, ora=11, limite=1) == 0  # idempotente
    assert registro.esito_evento(tenant, fid)["stato"] == "pending"

    _turno(app, fid)
    assert registro.esito_evento(tenant, fid)["stato"] == "idle"
    assert letti[:len(gia_letti)] == gia_letti and len(letti) == len(documenti)
    assert sorted(letti) == sorted(documenti), "i documenti già letti non si rileggono"


def test_il_tick_riprende_i_fermi_e_rispetta_le_letture_contemporanee(tmp_path, monkeypatch):
    from pct.registro_letture.event_retry import ERRORE_TEMPO_STORICO
    from web.services import archivio_letture_runtime as runtime

    app = _app(tmp_path)
    avviati: list[str] = []

    def avvia(_app, fascicolo_id, **kwargs):
        avviati.append(fascicolo_id)
        runtime._ATTIVE.add(fascicolo_id)
        return True

    monkeypatch.setattr(runtime, "avvia_lettura_in_background", avvia)
    monkeypatch.setattr(runtime, "_ATTIVE", set())
    registro, tenant = _registro(app)
    for indice in range(5):
        registro.accoda_evento(tenant, f"FERMO-{indice}")
    with registro.connection() as conn:
        conn.execute("UPDATE letture_eventi SET stato='idle',attempts=3,last_error=?,last_error_code='LeaseExpired'",
                     (ERRORE_TEMPO_STORICO,))
    with app.app_context():
        report = runtime.riprendi_eventi_lettura(app, limite_per_tenant=20)
        assert report["ferme_riprese"] == 5
        assert report["avviati"] == runtime.LETTURE_CONCORRENTI
        assert runtime.riprendi_eventi_lettura(app, limite_per_tenant=20)["ferme_riprese"] == 0
