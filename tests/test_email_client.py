from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pct.config_studio import ConfigPEC, GestioneConfigStudio
from pct.email_client import (
    EmailRicevuta,
    GestioneEmailRicevute,
    StatoEmail,
    aggiorna_comunicazioni_cancelleria_da_email,
    aggiorna_esiti_da_email,
)
from pct.fascicoli import GestioneFascicoli, TipoAttivita, TipoFascicolo


def _cfg_web(tmp_path: Path) -> dict:
    os.makedirs(str(tmp_path / "backup"), exist_ok=True)
    return {
        "TESTING": True,
        "AUTH_DB": str(tmp_path / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "BACKUP_DIR": str(tmp_path / "backup"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "EMAIL_CASELLA_DB": str(tmp_path / "casella.json"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
    }


def test_email_casella_filtri_avanzati_e_flag_letto(tmp_path):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    ge = GestioneEmailRicevute(cfg["EMAIL_CASELLA_DB"])
    ge.aggiungi(
        EmailRicevuta(
            id="MAIL-1",
            cartella="INBOX",
            stato=StatoEmail.LETTA,
            mittente="cancelleria@giustiziapec.it",
            mittente_nome="Cancelleria",
            destinatari="studio@example.pec.it",
            oggetto="ACCETTAZIONE DEPOSITO TELEMATICO RG 1025/2024",
            data="2026-04-08T09:00:00",
            corpo_testo="Ricevuta PEC di accettazione",
            allegati=[{"nome": "ricevuta.eml", "size": 1024, "mime": "message/rfc822"}],
            stato_pct="ACCETTATO_PEC",
            origine="IMAP",
        )
    )
    ge.aggiungi(
        EmailRicevuta(
            id="MAIL-2",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="operatore@example.com",
            oggetto="Memo interno",
            data="2026-04-08T10:00:00",
            corpo_testo="Promemoria",
            origine="IMAP",
        )
    )

    app = create_app(cfg)
    with app.test_client() as client:
        login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        assert login.status_code == 200

        response = client.get(
            "/email/?cartella=INBOX&stato=LETTA&pst=1&con_allegati=1&stato_pct=ACCETTATO_PEC&data_da=2026-04-01&data_a=2026-04-30"
        )

        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "ACCETTAZIONE DEPOSITO TELEMATICO RG 1025/2024" in body
        assert "Memo interno" not in body

        post = client.post("/email/MAIL-1/segna-non-letta", data={"cartella": "INBOX"}, follow_redirects=True)
        assert post.status_code == 200

    ge_reload = GestioneEmailRicevute(cfg["EMAIL_CASELLA_DB"])
    assert ge_reload.get("MAIL-1").stato == StatoEmail.NON_LETTA


def test_email_dettaglio_visualizza_e_scarica_allegato_salvato(tmp_path):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    ge = GestioneEmailRicevute(cfg["EMAIL_CASELLA_DB"])
    em = EmailRicevuta(
        id="MAIL-ATT-1",
        cartella="INBOX",
        stato=StatoEmail.LETTA,
        mittente="cancelleria@giustiziapec.it",
        oggetto="PEC con allegato RG 1025/2024",
        data="2026-04-09T10:00:00",
        corpo_testo="Contiene una ricevuta allegata.",
        allegati=[{
            "nome": "ricevuta.pdf",
            "mime": "application/pdf",
            "size": 18,
            "percorso_rel": "MAIL-ATT-1/ricevuta.pdf",
            "nome_file": "ricevuta.pdf",
        }],
    )
    ge.aggiungi(em)
    allegato_dir = Path(cfg["EMAIL_CASELLA_DB"]).parent / "allegati" / "MAIL-ATT-1"
    allegato_dir.mkdir(parents=True, exist_ok=True)
    contenuto = b"%PDF-1.4 allegato\n"
    (allegato_dir / "ricevuta.pdf").write_bytes(contenuto)

    app = create_app(cfg)
    with app.test_client() as client:
        login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        assert login.status_code == 200

        dettaglio = client.get("/email/messaggio/MAIL-ATT-1", follow_redirects=True)
        body = dettaglio.get_data(as_text=True)
        assert "Visualizza" in body
        assert "Scarica" in body

        inline = client.get("/email/messaggio/MAIL-ATT-1/allegato/0")
        assert inline.status_code == 200
        assert inline.data == contenuto

        download = client.get("/email/messaggio/MAIL-ATT-1/allegato/0?download=1")
        assert download.status_code == 200
        assert "attachment" in download.headers.get("Content-Disposition", "").lower()


def test_aggiorna_comunicazioni_cancelleria_da_email_associa_per_rg_senza_duplicare(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = gf.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        oggetto="Vendita di cose immobili",
    )

    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    ge.aggiungi(
        EmailRicevuta(
            id="PEC-COMM-1",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="posta-certificata@legalmail.it",
            mittente_nome="Legalmail PEC",
            oggetto="ACCETTAZIONE DEPOSITO TELEMATICO RG 1025/2024",
            data="2026-04-09T10:15:00",
            corpo_testo="Ricevuta di accettazione del deposito telematico.",
            uid_imap="INBOX:100",
            message_id="<msg-100@example>",
            allegati=[{"nome": "ricevuta.eml"}],
            stato_pct="ACCETTATO_PEC",
        )
    )

    report = aggiorna_comunicazioni_cancelleria_da_email(ge, gf)
    assert report["associati"] == 1
    assert report["duplicati"] == 0

    fasc_reload = gf.get(fasc.id)
    comunicazioni = [
        att for att in fasc_reload.attivita
        if att.tipo == TipoAttivita.COMUNICAZIONE_CANCELLERIA
    ]
    assert len(comunicazioni) == 1
    assert comunicazioni[0].email_uid_imap == "INBOX:100"
    assert "ACCETTAZIONE DEPOSITO TELEMATICO RG 1025/2024" in comunicazioni[0].email_oggetto
    assert "ricevuta.eml" in (comunicazioni[0].note or "")

    report_dup = aggiorna_comunicazioni_cancelleria_da_email(ge, gf)
    assert report_dup["duplicati"] == 1


def test_aggiorna_esiti_da_email_popola_fasi_deposito_tramite_rg(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = gf.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        oggetto="Vendita di cose immobili",
    )
    dep = gf.aggiungi_esito_deposito(
        fasc.id,
        tipo_atto="CITAZIONE",
        pec_destinatario="tribunale.palmi@giustiziapec.it",
        stato="INVIATO",
        nome_atto_principale="citazione.pdf.p7m",
    )

    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    ge.aggiungi(
        EmailRicevuta(
            id="E1",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="cancelleria@giustiziapec.it",
            oggetto="ACCETTAZIONE DEPOSITO TELEMATICO RG 1025/2024",
            data="2026-04-08T09:00:00",
            corpo_testo="Accettazione PEC",
            stato_pct="ACCETTATO_PEC",
        )
    )
    ge.aggiungi(
        EmailRicevuta(
            id="E2",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="cancelleria@giustiziapec.it",
            oggetto="CONSEGNA DEPOSITO TELEMATICO RG 1025/2024",
            data="2026-04-08T09:05:00",
            corpo_testo="Consegna PEC",
            stato_pct="CONSEGNATO",
        )
    )
    ge.aggiungi(
        EmailRicevuta(
            id="E3",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="cancelleria@giustiziapec.it",
            oggetto="WARN CONTROLLI DEPOSITO TELEMATICO RG 1025/2024",
            data="2026-04-08T09:10:00",
            corpo_testo="Anomalia controlli automatici",
            stato_pct="WARN_CONTROLLI",
        )
    )
    ge.aggiungi(
        EmailRicevuta(
            id="E4",
            cartella="INBOX",
            stato=StatoEmail.NON_LETTA,
            mittente="cancelleria@giustiziapec.it",
            oggetto="AVVISO CANCELLERIA RG 1025/2024",
            data="2026-04-08T09:20:00",
            corpo_testo="Deposito accettato dalla cancelleria",
            stato_pct="ACCETTATO_CANCELLERIA",
        )
    )

    log = aggiorna_esiti_da_email(ge, gf)
    assert log

    gf_reload = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc_reload = gf_reload.get(fasc.id)
    dep_reload = next(d for d in fasc_reload.depositi_pct if d.id == dep.id)
    assert dep_reload.stato == "ACCETTATO_CANCELLERIA"
    assert dep_reload.ricevuta_accettazione
    assert dep_reload.ricevuta_consegna
    assert dep_reload.ricevuta_controlli_automatici
    assert dep_reload.esito_controlli == "WARN"
    assert dep_reload.ricevuta_cancelleria


def test_api_pec_poll_cancelleria_usa_workflow_condiviso(tmp_path, monkeypatch):
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    studio_cfg = Path(cfg["STUDIO_CONFIG"])
    studio_cfg.parent.mkdir(parents=True, exist_ok=True)

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    gf.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
    )

    gs = GestioneConfigStudio(str(studio_cfg))
    config = gs.config
    config.pec = ConfigPEC(
        indirizzo="studio@example.pec.it",
        password="segreta",
        smtp_host="smtp.pec.aruba.it",
        smtp_port=465,
        imap_host="imaps.pec.aruba.it",
        imap_port=993,
        use_ssl=True,
    )
    gs.aggiorna(config)

    osservato = {}

    def _fake_sync_workflow(gestione_email, gestione_fascicoli, config_pec, **kwargs):
        osservato["indirizzo"] = config_pec.indirizzo
        osservato["state_path"] = kwargs.get("state_path", "")
        return {
            "sync": {"nuove": 2, "pst_trovate": 2, "errore": ""},
            "auto_esiti": ["ok-1", "ok-2"],
            "poll": {"trovati": 2, "associati": 1, "duplicati": 0, "errori": 0},
        }

    monkeypatch.setattr("pct.email_client.sincronizza_pec_e_fascicoli", _fake_sync_workflow)

    app = create_app(cfg)
    with app.test_client() as client:
        login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        assert login.status_code == 200

        response = client.post("/api/pec/poll-cancelleria", json={}, follow_redirects=True)

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["nuove"] == 2
    assert data["esiti_aggiornati"] == 2
    assert data["report"]["associati"] == 1
    assert osservato["indirizzo"] == "studio@example.pec.it"
    assert osservato["state_path"].endswith("pec_cancelleria_state.json")
