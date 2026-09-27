"""Revisione 2.419.0: verifica in due passaggi con l'archivio SQL, profilo e
stato della stanza di assistenza visto dal cliente."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente, genera_totp_secret
from pct.storage import StudioDB


def _gestione(tmp_path: Path) -> GestioneUtenti:
    return GestioneUtenti(
        db_path=str(tmp_path / "auth" / "utenti.json"),
        audit_path=str(tmp_path / "auth" / "audit.json"),
        secret_key="s",
        crea_admin_se_vuoto=False,
        studio_db=StudioDB.get(str(tmp_path / "studio.db")),
    )


def test_verifica_in_due_passaggi_resta_attiva_con_archivio_sql(tmp_path: Path):
    gestione = _gestione(tmp_path)
    utente = gestione.crea("avvocato", "Password123!", RuoloUtente.AVVOCATO, must_change_password=False)
    segreto = genera_totp_secret()
    gestione.imposta_verifica_due_passaggi(utente.id, segreto=segreto, attiva=True)

    # Una nuova lettura dall'archivio SQL deve chiedere il codice all'accesso:
    # prima i campi della verifica non venivano letti e il codice non era mai chiesto.
    riletto = _gestione(tmp_path).get_by_username("avvocato")
    assert riletto.totp_attivato is True and riletto.totp_secret == segreto

    gestione.imposta_verifica_due_passaggi(utente.id, segreto="", attiva=False)
    disattivato = _gestione(tmp_path).get_by_username("avvocato")
    assert disattivato.totp_attivato is False and disattivato.totp_secret == ""


def test_stato_della_stanza_al_cliente_senza_note_interne(tmp_path: Path):
    from tests.test_support_remote import _seed_runtime

    app, superadmin, _, _ = _seed_runtime(tmp_path)
    with app.test_client() as client:
        with client.session_transaction() as sessione:
            sessione["user_id"] = superadmin.id
            sessione["auth_scope"] = "global"
            sessione["auth_tenant_slug"] = ""
            sessione["last_activity"] = datetime.now().isoformat()
        creata = client.post(
            "/support/api/session",
            json={"customer_name": "Lucia Bianchi", "customer_email": "lucia@example.it", "notes": "Nota interna riservata allo studio"},
        ).get_json()
        public_id = creata["session"]["public_id"]
        token_cliente = creata["session"]["client_token"]
        stato = client.get(f"/support/api/{public_id}/state?role=client&token={token_cliente}").get_json()
    sessione_cliente = stato["session"]
    assert sessione_cliente["public_id"] == public_id and sessione_cliente["customer_name"] == "Lucia Bianchi"
    testo = str(sessione_cliente)
    assert "Nota interna" not in testo and "lucia@example.it" not in testo
    assert "operator_token" not in testo and "client_token" not in sessione_cliente
