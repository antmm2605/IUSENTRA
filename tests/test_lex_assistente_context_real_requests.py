from __future__ import annotations

import sqlite3
from pathlib import Path

from tests.test_web_bootstrap import _cfg_web, _seed_tenant_admin, _write_studio_config


QSP_ATTACHMENT_OCR_TEXT = (
    "CORTE SUPREMA DI CASSAZIONE QUINTA SEZIONE PENALE. Oggetto: ricorso n. 9966/2026 R.G. "
    "E' pervenuto all'esame preliminare di questo Ufficio il ricorso RG 9966/26, proposto nell'interesse "
    "di Gianfranco Greco avverso la sentenza della Corte d'appello di Caltanissetta del 10 ottobre 2025. "
    "La pena è stata concordata tra le parti ex art. 599-bis cod. proc. pen. "
    "Il ricorrente deduce, con quattro motivi, le seguenti censure: - l'illegalità della pena, per non "
    "essere stato motivato il giudizio di comparazione tra la recidiva e le ulteriori circostanze; - il difetto "
    "di controllo giudiziale sull'accordo; - la motivazione apparente in ordine all'esclusione di cause di "
    "proscioglimento ex art. 129 cod. proc. pen.; - la violazione dei limiti del concordato. "
    "Al netto del riferimento nominalistico alla illegalità della pena, il ricorso pone il tema della deducibilità "
    "dell'erronea determinazione della sanzione, concordata tra le parti ex art. 599-bis cod. proc. pen., "
    "con richiamo all'art. 81, comma secondo, cod. pen."
)


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


def test_assistente_chat_questione_penale_rg_non_finisce_nell_editor(tmp_path: Path, monkeypatch):
    from pct.legal_update_repository import LegalUpdateRepository, derive_legal_updates_db_path

    monkeypatch.setattr(
        "lex.legal_sources.tools.search_legal_sources",
        lambda query, limit=6: {"data": {"passages": []}},
    )
    app, studio, admin = _seed_studio_con_moscato(tmp_path)
    repo = LegalUpdateRepository(
        db_path=derive_legal_updates_db_path(app.config["LEGAL_INTELLIGENCE_DB"]),
        json_path="",
    )
    with sqlite3.connect(repo.db_path) as conn:
        conn.executemany(
            """
            INSERT INTO web_verification_evidence (
                evidence_key, source_code, source_name, query, origin, title,
                source_url, attachment_url, attachment_type, sha256, is_official,
                context_chars, excerpt, content_text, matched_terms_json,
                verification_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "qsp-page",
                    "cassazione_massimario",
                    "Corte Suprema di Cassazione",
                    "Questione Penale Pendente del ricorso R.G. 9926/2026",
                    "pagina_fonte_ufficiale",
                    "Questione Penale Pendente del ricorso R.G. 9926/2026 ud. 09/07/2026",
                    "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",
                    "",
                    "",
                    "a" * 64,
                    1,
                    915,
                    "Questione penale pendente R.G. 9926/2026. Se, avverso la sentenza emessa a seguito di concordato in appello, siano deducibili con il ricorso per cassazione i vizi attinenti alla determinazione della pena non comportanti l'illegalità della stessa.",
                    "Data inserimento: 05 maggio 2026 Questione penale Pendente del ricorso R.G. n. 9926/2026 ud. 09/07/2026 Se, avverso la sentenza emessa a seguito di concordato in appello, siano deducibili con il ricorso per cassazione i vizi attinenti alla determinazione della pena non comportanti l'illegalità della stessa. Ricorrente: Turco G. Relatore: E. Morosini Data udienza: 09 luglio 2026 Riferimenti normativi: Cod. proc. pen. artt. 599-bis e 606 Allegati Ordinanza di rimessione.",
                    '["questione penale", "9926/2026"]',
                    "verified",
                ),
                (
                    "qsp-attachment",
                    "cassazione_massimario",
                    "Corte Suprema di Cassazione",
                    "Questione Penale Pendente del ricorso R.G. 9926/2026",
                    "allegato_fonte_ufficiale",
                    "Ordinanza di rimessione",
                    "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",
                    "https://www.cortedicassazione.it/resources/cms/documents/Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf",
                    "pdf",
                    "b" * 64,
                    1,
                    620,
                    "R.G. 9966/2026. Ordinanza di rimessione.",
                    QSP_ATTACHMENT_OCR_TEXT,
                    '["ordinanza", "rimessione", "9966/2026"]',
                    "verified",
                ),
            ],
        )
        conn.commit()

    question = "Questione Penale Pendente del ricorso R.G. 9926/2026"
    with app.test_client() as client:
        _login(client, studio, admin)
        response = client.post(
            "/api/assistente/chat",
            json={
                "messages": [
                    {"role": "user", "content": "Come mi supporta Lex nell'editor professionale per una bozza?"},
                    {"role": "assistant", "content": "Editor Lex: supporto alla redazione."},
                    {"role": "user", "content": question},
                ],
                "context_label": "Lex",
                "page_context": "editor",
                "page_path": "/redazione-atti",
                "mode": "fascicolo",
            },
        )

    stream = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Allegato: **Ordinanza di rimessione**." in stream
    assert "### Risposta alla domanda" in stream
    assert "sentenza definitiva" in stream
    assert "Motivi del ricorso" in stream
    assert "Punto di diritto" in stream
    assert "concordato in appello" in stream
    assert "Cod. proc. pen. artt. 599-bis e 606" in stream
    assert "Punto da verificare" in stream
    assert "Apri PDF ufficiale" in stream
    assert "Nota%5FUfficio%5FSpoglio%5FV%5FSez.%5Fpenale%5FRG%5F9966%5F2026%5F1.pdf" in stream
    assert "R.G. 9926/2026" in stream
    assert "R.G. 9966/2026" in stream
    assert "Editor Lex" not in stream
    assert "template_atti" not in stream


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
