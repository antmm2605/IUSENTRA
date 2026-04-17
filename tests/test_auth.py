"""Test per il sistema di autenticazione e gestione utenti."""

import pytest
from pct.auth import (
    GestioneUtenti,
    Utente,
    RuoloUtente,
)
from pct.storage import StudioDB


@pytest.fixture
def gu(tmp_path):
    return GestioneUtenti(
        db_path=str(tmp_path / "utenti.json"),
        audit_path=str(tmp_path / "audit.json"),
        secret_key="test-secret",
        bootstrap_admin_credentials_path=str(tmp_path / "bootstrap_admin.json"),
    )


# ------------------------------------------------------------------ Admin di default

def test_admin_default_creato(gu):
    """Al primo avvio viene creato l'admin di default."""
    admin = gu.get_by_username("admin")
    assert admin is not None
    assert admin.ruolo == RuoloUtente.AMMINISTRATORE
    assert admin.attivo is True
    assert admin.must_change_password is True


def test_admin_default_password_temporanea_viene_generata_e_salvata(gu):
    """L'admin di default usa una password temporanea non fissa."""
    creds = gu.bootstrap_admin_credentials()

    assert creds is not None
    assert creds["username"] == "admin"
    assert creds["must_change_password"] is True
    assert creds["password"] != "admin"

    u = gu.autentica("admin", creds["password"])
    assert u is not None
    assert u.username == "admin"


def test_admin_default_usa_password_bootstrap_configurata(tmp_path):
    gu = GestioneUtenti(
        db_path=str(tmp_path / "utenti.json"),
        audit_path=str(tmp_path / "audit.json"),
        secret_key="test-secret",
        bootstrap_admin_password="TempPass123!",
        bootstrap_admin_credentials_path=str(tmp_path / "bootstrap_admin.json"),
    )

    u = gu.autentica("admin", "TempPass123!")

    assert u is not None
    assert u.username == "admin"
    assert gu.bootstrap_admin_credentials()["password"] == "TempPass123!"


# ------------------------------------------------------------------ CRUD utenti

def test_crea_utente(gu):
    u = gu.crea("avvocato1", "password123", RuoloUtente.AVVOCATO,
                email="av1@studio.it", nome_completo="Avv. Bianchi")
    assert u.id is not None
    assert u.username == "avvocato1"
    assert u.ruolo == RuoloUtente.AVVOCATO
    assert u.attivo is True
    assert u.must_change_password is True


def test_username_duplicato_errore(gu):
    gu.crea("pippo", "password123", RuoloUtente.SEGRETERIA)
    with pytest.raises(ValueError, match="già in uso"):
        gu.crea("pippo", "password456", RuoloUtente.AVVOCATO)


def test_password_troppo_corta(gu):
    with pytest.raises(ValueError, match="8 caratteri"):
        gu.crea("utente2", "abc", RuoloUtente.SEGRETERIA)


def test_username_normalizzato(gu):
    """Username convertito in lowercase."""
    u = gu.crea("MARIO", "password123", RuoloUtente.AVVOCATO)
    assert u.username == "mario"


def test_aggiorna_utente(gu):
    u = gu.crea("tizio", "password123", RuoloUtente.SEGRETERIA)
    gu.aggiorna(u.id, nome_completo="Tizio Caio", email="tc@studio.it")
    aggiornato = gu.get(u.id)
    assert aggiornato.nome_completo == "Tizio Caio"
    assert aggiornato.email == "tc@studio.it"


def test_elimina_utente(gu):
    u = gu.crea("daelim", "password123", RuoloUtente.SEGRETERIA)
    gu.elimina(u.id)
    assert gu.get(u.id) is None


def test_non_eliminare_ultimo_admin(gu):
    """Impossibile eliminare l'unico amministratore."""
    admin = gu.get_by_username("admin")
    with pytest.raises(ValueError):
        gu.elimina(admin.id)


def test_cambia_password(gu):
    u = gu.crea("user1", "vecchia123", RuoloUtente.AVVOCATO)
    gu.cambia_password(u.id, "nuova12345")
    assert gu.autentica("user1", "nuova12345") is not None
    assert gu.autentica("user1", "vecchia123") is None
    assert gu.get(u.id).must_change_password is False


def test_reimposta_password_temporanea_obbliga_cambio_al_prossimo_accesso(gu):
    u = gu.crea("user_temp", "vecchia123", RuoloUtente.AVVOCATO)
    gu.cambia_password(u.id, "NuovaTemp123", must_change_password=True)

    aggiornato = gu.get(u.id)

    assert aggiornato.must_change_password is True
    assert gu.autentica("user_temp", "NuovaTemp123") is not None


def test_cambio_password_admin_rimuove_file_bootstrap(tmp_path):
    creds_path = tmp_path / "bootstrap_admin.json"
    gu = GestioneUtenti(
        db_path=str(tmp_path / "utenti.json"),
        audit_path=str(tmp_path / "audit.json"),
        secret_key="test-secret",
        bootstrap_admin_password="TempPass123!",
        bootstrap_admin_credentials_path=str(creds_path),
    )
    admin = gu.get_by_username("admin")

    assert creds_path.exists()

    gu.cambia_password(admin.id, "NuovaPassword123!")

    assert not creds_path.exists()


# ------------------------------------------------------------------ Autenticazione

def test_autentica_credenziali_corrette(gu):
    gu.crea("avv", "correttaPass1", RuoloUtente.AVVOCATO)
    u = gu.autentica("avv", "correttaPass1")
    assert u is not None
    assert u.ultimo_accesso != ""


def test_autentica_credenziali_errate(gu):
    gu.crea("utx", "password123", RuoloUtente.SEGRETERIA)
    assert gu.autentica("utx", "sbagliata") is None


def test_autentica_utente_disabilitato(gu):
    u = gu.crea("disab", "password123", RuoloUtente.SEGRETERIA)
    gu.aggiorna(u.id, attivo=False)
    assert gu.autentica("disab", "password123") is None


def test_autentica_case_insensitive(gu):
    gu.crea("mario", "password123", RuoloUtente.AVVOCATO)
    assert gu.autentica("MARIO", "password123") is not None


def test_autentica_tramite_email(gu):
    gu.crea("antonella", "Password123!", RuoloUtente.AMMINISTRATORE, email="antonella@studio.it")

    utente = gu.autentica("antonella@studio.it", "Password123!")

    assert utente is not None
    assert utente.username == "antonella"


def test_utente_from_dict_ignora_campi_legacy_non_previsti():
    utente = Utente.from_dict(
        {
            "id": "u1",
            "username": "antonella",
            "ruolo": "AMMINISTRATORE",
            "password_hash": "hash",
            "tenant_slug": "antonella-mammola",
            "tenant_id": "legacy-tenant-id",
        }
    )

    assert utente.id == "u1"
    assert utente.username == "antonella"
    assert utente.tenant_slug == "antonella-mammola"


# ------------------------------------------------------------------ Permessi

def test_permessi_amministratore():
    u = Utente(ruolo=RuoloUtente.AMMINISTRATORE)
    assert u.ha_permesso("utenti.leggi")
    assert u.ha_permesso("fascicoli.elimina")
    assert u.ha_permesso("audit.leggi")


def test_permessi_avvocato():
    u = Utente(ruolo=RuoloUtente.AVVOCATO)
    assert u.ha_permesso("fascicoli.leggi")
    assert u.ha_permesso("fascicoli.scrivi")
    assert not u.ha_permesso("utenti.elimina")
    assert not u.ha_permesso("audit.leggi")


def test_permessi_segreteria():
    u = Utente(ruolo=RuoloUtente.SEGRETERIA)
    assert u.ha_permesso("fascicoli.leggi")
    assert not u.ha_permesso("fascicoli.scrivi")
    assert not u.ha_permesso("utenti.leggi")


def test_permessi_superfici_admin_e_tenant():
    amministratore = Utente(ruolo=RuoloUtente.AMMINISTRATORE)
    superadmin = Utente(ruolo=RuoloUtente.SUPERADMIN)

    assert amministratore.ha_permesso("admin.leggi")
    assert amministratore.ha_permesso("autorizzazioni.scrivi")
    assert not amministratore.ha_permesso("tenant.impersona")

    assert superadmin.ha_permesso("tenant.impersona")
    assert superadmin.ha_permesso("tenant.configura")


def test_permessi_telematico_e_ai_per_ruoli_operativi():
    avvocato = Utente(ruolo=RuoloUtente.AVVOCATO)
    praticante = Utente(ruolo=RuoloUtente.PRATICANTE)
    contabile = Utente(ruolo=RuoloUtente.CONTABILE)

    assert avvocato.ha_permesso("telematico.deposita")
    assert avvocato.ha_permesso("ai.usa")
    assert praticante.ha_permesso("telematico.leggi")
    assert praticante.ha_permesso("ai.usa")
    assert not praticante.ha_permesso("telematico.deposita")
    assert not contabile.ha_permesso("ai.usa")


def test_ha_ruolo(gu):
    u = gu.crea("av2", "password123", RuoloUtente.AVVOCATO)
    assert u.ha_ruolo(RuoloUtente.AVVOCATO)
    assert not u.ha_ruolo(RuoloUtente.AMMINISTRATORE)
    assert u.ha_ruolo(RuoloUtente.AVVOCATO, RuoloUtente.SEGRETERIA)


# ------------------------------------------------------------------ Audit log

def test_audit_registra_evento(gu):
    u = gu.crea("loguser", "password123", RuoloUtente.AVVOCATO)
    gu.registra_evento("fascicoli.crea", id_utente=u.id,
                       username=u.username, risorsa_tipo="fascicolo",
                       risorsa_id="abc123")
    eventi = gu.audit_log(id_utente=u.id)
    assert len(eventi) >= 1
    assert eventi[0].azione == "fascicoli.crea"


def test_audit_filtra_per_azione(gu):
    gu.registra_evento("auth.login", username="admin")
    gu.registra_evento("fascicoli.crea", username="admin")
    login_events = gu.audit_log(azione="auth.login")
    assert all("auth.login" in e.azione for e in login_events)


def test_audit_limit(gu):
    for i in range(20):
        gu.registra_evento(f"test.azione_{i}")
    eventi = gu.audit_log(limit=5)
    assert len(eventi) <= 5


# ------------------------------------------------------------------ Persistenza

def test_persistenza_utenti(tmp_path):
    db = str(tmp_path / "utenti.json")
    audit = str(tmp_path / "audit.json")
    gu1 = GestioneUtenti(db_path=db, audit_path=audit, secret_key="s")
    gu1.crea("persist_user", "password123", RuoloUtente.AVVOCATO)
    gu2 = GestioneUtenti(db_path=db, audit_path=audit, secret_key="s")
    assert gu2.get_by_username("persist_user") is not None


def test_persistenza_audit(tmp_path):
    db = str(tmp_path / "utenti.json")
    audit = str(tmp_path / "audit.json")
    gu1 = GestioneUtenti(db_path=db, audit_path=audit, secret_key="s")
    gu1.registra_evento("test.evento")
    gu2 = GestioneUtenti(db_path=db, audit_path=audit, secret_key="s")
    assert len(gu2.audit_log()) >= 1


def test_migra_utenti_legacy_json_in_sqlite_quando_backend_auth_e_vuoto(tmp_path):
    db = str(tmp_path / "auth" / "utenti.json")
    audit = str(tmp_path / "auth" / "audit.json")
    legacy = GestioneUtenti(
        db_path=db,
        audit_path=audit,
        secret_key="s",
        crea_admin_se_vuoto=False,
    )
    legacy.crea(
        "migrato",
        "Password123!",
        RuoloUtente.AVVOCATO,
        must_change_password=False,
    )
    legacy.registra_evento("auth.login", username="migrato")

    studio_db = StudioDB.get(str(tmp_path / "studio.db"))
    migrato = GestioneUtenti(
        db_path=db,
        audit_path=audit,
        secret_key="s",
        crea_admin_se_vuoto=False,
        studio_db=studio_db,
    )

    assert migrato.autentica("migrato", "Password123!") is not None
    assert studio_db.conn.execute("SELECT COUNT(*) FROM utenti").fetchone()[0] == 1
    assert studio_db.conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] >= 1


# ------------------------------------------------------------------ Statistiche

def test_statistiche(gu):
    gu.crea("av3", "password123", RuoloUtente.AVVOCATO)
    gu.crea("seg1", "password123", RuoloUtente.SEGRETERIA)
    stats = gu.statistiche()
    assert stats["totale_utenti"] >= 3  # admin + 2
    assert stats["per_ruolo"]["AVVOCATO"] >= 1
    assert stats["per_ruolo"]["AMMINISTRATORE"] >= 1
