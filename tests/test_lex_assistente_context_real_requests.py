from __future__ import annotations

from pathlib import Path

from tests.test_web_bootstrap import _cfg_web, _seed_tenant_admin, _write_studio_config


def _seed_studio_con_moscato(tmp_path: Path):
    from pct.agenda import Agenda, TipoAppuntamento
    from pct.clienti import GestioneClienti, Indirizzo, Recapiti, TipoCliente
    from pct.tenant import GestioneTenant
    from web.app import create_app

    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, admin = _seed_tenant_admin(
        app,
        studio_nome="Studio Lex Client Test",
        studio_slug="studio-lex-client-test",
    )
    manager = GestioneTenant(app.config["TENANTS_REGISTRY"])
    paths = manager.percorsi_dati(studio.slug, reconcile_aliases=False)
    _write_studio_config(Path(paths["CONFIG_STUDIO_DB"]))

    clienti = GestioneClienti(db_path=paths["CLIENTI_DB"])
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Marco",
        cognome="Moscato",
        codice_fiscale="MSCMRC80A01H501Z",
    )
    clienti.aggiorna(
        cliente.id,
        indirizzo_residenza=Indirizzo(via="Via Roma", civico="12", cap="89029", comune="Taurianova", provincia="RC"),
        recapiti=Recapiti(
            telefono="0966123456",
            email="marco.moscato@example.test",
            pec="marco.moscato@pec.example.test",
        ),
    )

    agenda = Agenda(db_path=paths["AGENDA_DB"])
    agenda.aggiungi(
        "Udienza istruttoria Moscato",
        TipoAppuntamento.UDIENZA,
        "2026-04-10T09:30:00",
        durata_minuti=45,
        luogo="Aula 2",
        cliente="Marco Moscato",
        id_cliente=cliente.id,
        procedimento="RG 23/2026",
        tribunale="Tribunale di Palmi",
    )
    return app, studio, admin


def _login(client, studio, admin) -> None:
    response = client.post(
        "/login",
        data={
            "username": admin.username,
            "password": "PasswordSicura!123",
            "studio_slug": studio.slug,
        },
        follow_redirects=False,
    )
    assert response.status_code == 302


def test_assistente_context_risponde_con_dati_cliente_reali(tmp_path: Path):
    app, studio, admin = _seed_studio_con_moscato(tmp_path)

    with app.test_client() as client:
        _login(client, studio, admin)
        response = client.post(
            "/api/assistente/context",
            json={"question": "mi dati i dati del cliente marco moscato", "context_label": "Contesto clienti"},
        )

    payload = response.get_json()
    answer = payload.get("answer", "")
    assert response.status_code == 200
    assert payload["ok"] is True
    assert "Moscato Marco" in answer
    assert "marco.moscato@example.test" in answer
    assert "marco.moscato@pec.example.test" in answer
    assert "0966123456" in answer
    assert "base documentale disponibile non e' ancora sufficiente" not in answer
    assert "Non ho trovato dati reali sufficienti" not in answer


def test_assistente_chat_stream_risponde_con_dati_cliente_reali(tmp_path: Path):
    app, studio, admin = _seed_studio_con_moscato(tmp_path)

    with app.test_client() as client:
        _login(client, studio, admin)
        response = client.post(
            "/api/assistente/chat",
            json={"message": "mi dati i dati del cliente marco moscato", "context_label": "Contesto clienti"},
        )

    stream = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Moscato Marco" in stream
    assert "marco.moscato@example.test" in stream
    assert "base documentale disponibile non e' ancora sufficiente" not in stream


def test_assistente_context_ultime_udienze_legge_agenda_reale(tmp_path: Path):
    app, studio, admin = _seed_studio_con_moscato(tmp_path)

    with app.test_client() as client:
        _login(client, studio, admin)
        response = client.post("/api/assistente/context", json={"question": "ultime udienze"})

    payload = response.get_json()
    answer = payload.get("answer", "")
    assert response.status_code == 200
    assert payload["ok"] is True
    assert "Udienza istruttoria Moscato" in answer
    assert "Non ho trovato dati reali sufficienti" not in answer


def test_assistente_context_diffida_compila_studio_e_cliente_senza_fonti_irreali(tmp_path: Path):
    app, studio, admin = _seed_studio_con_moscato(tmp_path)

    with app.test_client() as client:
        _login(client, studio, admin)
        response = client.post(
            "/api/assistente/context",
            json={
                "question": "scrivi diffida per il cliente marco moscato",
                "context_label": "Contesto clienti",
            },
        )

    payload = response.get_json()
    answer = payload.get("answer", "")
    assert response.status_code == 200
    assert payload["ok"] is True
    assert "Studio Refactor" in answer
    assert "Avv. Refactor" in answer
    assert "Moscato Marco" in answer
    assert "\n\n---\n\n" in answer
    assert "\n**Fatto**\n\n" in answer
    assert "\n1. " in answer
    assert "\n2. " in answer
    assert "[Studio Legale / Avv. Nome Cognome]" not in answer
    assert "Fonti consultate" not in answer
    assert "Contesto fonte" not in answer
    assert "\ufffd" not in answer
