from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path

from pct.agenda import Agenda, TipoAppuntamento
from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_react_shell import _app


def _seed_wizard_case(app):
    clienti = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = clienti.nuovo(TipoCliente.PERSONA_FISICA, nome="Marco", cognome="Neri")
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Responsabilita contrattuale",
        TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="Tribunale di Torino",
    )
    agenda = Agenda(db_path=app.config["AGENDA_DB"])
    appuntamento = agenda.aggiungi(
        "Udienza istruttoria",
        TipoAppuntamento.UDIENZA,
        (datetime.now() + timedelta(days=3)).replace(microsecond=0).isoformat(),
        durata_minuti=45,
        luogo="Aula 3",
        id_cliente=cliente.id,
        cliente=cliente.nome_completo,
        procedimento="RG 123/2026",
        tribunale="Tribunale di Torino",
    )
    return cliente, fascicolo, appuntamento


def _session_id_from(location: str) -> str:
    match = re.search(r"/wizard-pro/([^/]+)/step/1", location)
    assert match, location
    return match.group(1)


def test_wizard_pro_react_get_api_e_post_flusso_completo(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    _cliente, fascicolo, appuntamento = _seed_wizard_case(app)

    with app.test_client() as client:
        _login(client)
        dashboard = client.get("/wizard-pro/")
        dashboard_classic = client.get("/wizard-pro/?_legacy=1")
        dashboard_api = client.get("/api/v1/ui/wizard-pro")
        start = client.post(
            "/wizard-pro/nuovo",
            data={"id_fascicolo": fascicolo.id, "id_appuntamento": appuntamento.id, "titolo": ""},
        )
        session_id = _session_id_from(start.headers["Location"])
        redirect_case = client.get(f"/wizard-pro/fascicolo/{fascicolo.id}")
        step1 = client.get(f"/wizard-pro/{session_id}/step/1")
        step1_classic = client.get(f"/wizard-pro/{session_id}/step/1?_legacy=1")
        step1_api = client.get(f"/api/v1/ui/wizard-pro/session/{session_id}/step/1")
        save1 = client.post(
            f"/wizard-pro/{session_id}/step/1",
            data={"step1_note": "Verificare costituzione e produzioni."},
        )
        step2 = client.get(f"/wizard-pro/{session_id}/step/2")
        save2 = client.post(
            f"/wizard-pro/{session_id}/step/2",
            data={"doc_extra_label": "Memoria istruttoria", "doc_stato_0": "pronto", "doc_note_0": "Presente"},
        )
        save3 = client.post(
            f"/wizard-pro/{session_id}/step/3",
            data={
                "note_preparazione": "Linea difensiva pronta.",
                "argomenti_principali": "Inadempimento e prova documentale.",
                "richieste_giudice": "Ammissione mezzi istruttori.",
                "eccezioni_da_sollevare": "Prescrizione avversaria.",
            },
        )
        save4 = client.post(
            f"/wizard-pro/{session_id}/step/4",
            data={
                "precheck_firma_ok": "1",
                "precheck_docs_pronti": "1",
                "precheck_cliente_notificato": "1",
                "precheck_trasporto_ok": "1",
                "precheck_note": "Partenza confermata.",
            },
        )
        save5 = client.post(
            f"/wizard-pro/{session_id}/step/5",
            data={
                "esito": "rinvio",
                "esito_rinvio_data": (date.today() + timedelta(days=45)).isoformat(),
                "esito_note_verbale": "Rinvio per escussione testimoni.",
                "esito_azioni": "Preparare capitoli e notificare cliente.",
                "esito_aggiorna_fascicolo": "1",
            },
        )
        complete = client.get(f"/wizard-pro/{session_id}/completo")
        complete_classic = client.get(f"/wizard-pro/{session_id}/completo?_legacy=1")
        complete_api = client.get(f"/api/v1/ui/wizard-pro/session/{session_id}/completo")
        archive = client.post(f"/wizard-pro/{session_id}/archivia")
        delete = client.post(f"/wizard-pro/{session_id}/elimina")

    assert dashboard.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in dashboard.get_data(as_text=True)
    assert dashboard_classic.status_code == 200
    assert 'id="root"' not in dashboard_classic.get_data(as_text=True)
    assert dashboard_api.status_code == 200
    assert dashboard_api.get_json()["contracts"]["mock_fallback"] is False
    assert start.status_code in {302, 303}
    assert start.headers["Location"].endswith(f"/wizard-pro/{session_id}/step/1")
    assert redirect_case.status_code in {302, 303}
    assert redirect_case.headers["Location"].endswith(f"/wizard-pro/{session_id}/step/1")
    assert step1.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in step1.get_data(as_text=True)
    assert step1_classic.status_code == 200
    assert 'id="root"' not in step1_classic.get_data(as_text=True)
    assert step1_api.status_code == 200
    step_payload = step1_api.get_json()
    assert step_payload["contracts"]["mock_fallback"] is False
    assert step_payload["session"]["id"] == session_id
    assert step_payload["currentStep"] == 1
    assert save1.status_code in {302, 303}
    assert save1.headers["Location"].endswith(f"/wizard-pro/{session_id}/step/2")
    assert step2.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in step2.get_data(as_text=True)
    assert save2.status_code in {302, 303}
    assert save2.headers["Location"].endswith(f"/wizard-pro/{session_id}/step/3")
    assert save3.status_code in {302, 303}
    assert save3.headers["Location"].endswith(f"/wizard-pro/{session_id}/step/4")
    assert save4.status_code in {302, 303}
    assert save4.headers["Location"].endswith(f"/wizard-pro/{session_id}/step/5")
    assert save5.status_code in {302, 303}
    assert save5.headers["Location"].endswith(f"/wizard-pro/{session_id}/completo")
    assert complete.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in complete.get_data(as_text=True)
    assert complete_classic.status_code == 200
    assert 'id="root"' not in complete_classic.get_data(as_text=True)
    assert complete_api.status_code == 200
    complete_payload = complete_api.get_json()
    assert complete_payload["contracts"]["writes"] == "operational_routes"
    assert complete_payload["session"]["id"] == session_id
    assert complete_payload["outcome"]["value"] == "rinvio"
    assert archive.status_code in {302, 303}
    assert delete.status_code in {302, 303}
