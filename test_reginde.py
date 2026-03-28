"""Test per la gestione profili e permessi personalizzati."""

import pytest
from pct.auth import (
    GestioneUtenti,
    Utente,
    RuoloUtente,
    PERMESSI,
    TUTTI_PERMESSI,
    DESCRIZIONI_RUOLI,
)


@pytest.fixture
def gu(tmp_path):
    return GestioneUtenti(
        db_path=str(tmp_path / "utenti.json"),
        audit_path=str(tmp_path / "audit.json"),
        secret_key="test-secret",
    )


# ------------------------------------------------------------------ Nuovi ruoli

def test_tutti_ruoli_presenti():
    ruoli = {r.value for r in RuoloUtente}
    assert "AMMINISTRATORE" in ruoli
    assert "AVVOCATO" in ruoli
    assert "COLLABORATORE" in ruoli
    assert "PRATICANTE" in ruoli
    assert "SEGRETERIA" in ruoli
    assert "CONTABILE" in ruoli


def test_ogni_ruolo_ha_permessi():
    for ruolo in RuoloUtente:
        assert ruolo in PERMESSI, f"Ruolo {ruolo} manca da PERMESSI"
        assert len(PERMESSI[ruolo]) > 0, f"Ruolo {ruolo} ha lista vuota"


def test_ogni_ruolo_ha_descrizione():
    for ruolo in RuoloUtente:
        assert ruolo in DESCRIZIONI_RUOLI
        desc = DESCRIZIONI_RUOLI[ruolo]
        assert "descrizione" in desc
        assert "colore" in desc
        assert "icona" in desc


def test_amministratore_ha_tutti_permessi():
    """L'amministratore deve avere tutti i permessi del sistema."""
    tutti = {p for _, p, _ in TUTTI_PERMESSI}
    admin_perms = set(PERMESSI[RuoloUtente.AMMINISTRATORE])
    assert tutti == admin_perms


def test_collaboratore_non_elimina_fascicoli():
    u = Utente(ruolo=RuoloUtente.COLLABORATORE)
    assert u.ha_permesso("fascicoli.leggi")
    assert u.ha_permesso("fascicoli.scrivi")
    assert not u.ha_permesso("fascicoli.elimina")


def test_praticante_solo_lettura_piu_agenda():
    u = Utente(ruolo=RuoloUtente.PRATICANTE)
    assert u.ha_permesso("fascicoli.leggi")
    assert not u.ha_permesso("fascicoli.scrivi")
    assert u.ha_permesso("agenda.leggi")
    assert u.ha_permesso("agenda.scrivi")
    assert not u.ha_permesso("clienti.scrivi")


def test_contabile_solo_lettura():
    u = Utente(ruolo=RuoloUtente.CONTABILE)
    assert u.ha_permesso("fascicoli.leggi")
    assert not u.ha_permesso("fascicoli.scrivi")
    assert not u.ha_permesso("messaggi.scrivi")
    assert not u.ha_permesso("utenti.leggi")


# ------------------------------------------------------------------ Permessi extra

def test_permesso_extra_aggiunge_permesso(gu):
    u = gu.crea("av1", "password123", RuoloUtente.COLLABORATORE)
    assert not u.ha_permesso("fascicoli.elimina")
    gu.aggiorna_permessi(u.id, permessi_extra=["fascicoli.elimina"], permessi_negati=[])
    u_agg = gu.get(u.id)
    assert u_agg.ha_permesso("fascicoli.elimina")


def test_permesso_negato_rimuove_permesso(gu):
    u = gu.crea("av2", "password123", RuoloUtente.AVVOCATO)
    assert u.ha_permesso("fascicoli.scrivi")
    gu.aggiorna_permessi(u.id, permessi_extra=[], permessi_negati=["fascicoli.scrivi"])
    u_agg = gu.get(u.id)
    assert not u_agg.ha_permesso("fascicoli.scrivi")


def test_permessi_effettivi(gu):
    u = gu.crea("av3", "password123", RuoloUtente.COLLABORATORE)
    gu.aggiorna_permessi(u.id,
                         permessi_extra=["fascicoli.elimina"],
                         permessi_negati=["fascicoli.scrivi"])
    u_agg = gu.get(u.id)
    effettivi = u_agg.permessi_effettivi
    assert "fascicoli.elimina" in effettivi
    assert "fascicoli.scrivi" not in effettivi
    assert "fascicoli.leggi" in effettivi  # ancora dal ruolo


def test_ha_override_true(gu):
    u = gu.crea("av4", "password123", RuoloUtente.SEGRETERIA)
    assert not u.ha_override
    gu.aggiorna_permessi(u.id, permessi_extra=["fascicoli.scrivi"], permessi_negati=[])
    u_agg = gu.get(u.id)
    assert u_agg.ha_override


def test_ha_override_false_default(gu):
    u = gu.crea("av5", "password123", RuoloUtente.AVVOCATO)
    assert not u.ha_override


def test_conflitto_extra_negato_errore(gu):
    u = gu.crea("av6", "password123", RuoloUtente.SEGRETERIA)
    with pytest.raises(ValueError, match="conflitto"):
        gu.aggiorna_permessi(u.id,
                             permessi_extra=["fascicoli.scrivi"],
                             permessi_negati=["fascicoli.scrivi"])


def test_permesso_non_esistente_errore(gu):
    u = gu.crea("av7", "password123", RuoloUtente.SEGRETERIA)
    with pytest.raises(ValueError, match="non riconosciuto"):
        gu.aggiorna_permessi(u.id, permessi_extra=["permesso.inesistente"], permessi_negati=[])


def test_reset_override(gu):
    u = gu.crea("av8", "password123", RuoloUtente.COLLABORATORE)
    gu.aggiorna_permessi(u.id, permessi_extra=["fascicoli.elimina"], permessi_negati=[])
    gu.aggiorna_permessi(u.id, permessi_extra=[], permessi_negati=[])
    u_agg = gu.get(u.id)
    assert not u_agg.ha_override


# ------------------------------------------------------------------ Priorità override

def test_negato_ha_priorita_su_extra(gu):
    """Un permesso negato vince anche se è anche in extra (errore di chiamata)."""
    u = gu.crea("av9", "password123", RuoloUtente.AVVOCATO)
    # Imposta manualmente entrambi (bypassa la validazione)
    u.permessi_extra = ["fascicoli.elimina"]
    u.permessi_negati = ["fascicoli.elimina"]
    # Il negato deve vincere
    assert not u.ha_permesso("fascicoli.elimina")


# ------------------------------------------------------------------ Persistenza override

def test_persistenza_permessi_extra(tmp_path):
    db = str(tmp_path / "u.json")
    audit = str(tmp_path / "a.json")
    gu1 = GestioneUtenti(db_path=db, audit_path=audit, secret_key="s")
    u = gu1.crea("px", "password123", RuoloUtente.SEGRETERIA)
    gu1.aggiorna_permessi(u.id,
                          permessi_extra=["fascicoli.scrivi"],
                          permessi_negati=["agenda.scrivi"])
    gu2 = GestioneUtenti(db_path=db, audit_path=audit, secret_key="s")
    u2 = gu2.get(u.id)
    assert u2.ha_permesso("fascicoli.scrivi")
    assert not u2.ha_permesso("agenda.scrivi")


# ------------------------------------------------------------------ per_ruolo query

def test_per_ruolo(gu):
    gu.crea("c1", "password123", RuoloUtente.COLLABORATORE)
    gu.crea("c2", "password123", RuoloUtente.COLLABORATORE)
    gu.crea("s1", "password123", RuoloUtente.SEGRETERIA)
    result = gu.per_ruolo(RuoloUtente.COLLABORATORE)
    assert len(result) == 2
    assert all(u.ruolo == RuoloUtente.COLLABORATORE for u in result)


# ------------------------------------------------------------------ Statistiche

def test_statistiche_con_override(gu):
    u = gu.crea("ov1", "password123", RuoloUtente.COLLABORATORE)
    gu.aggiorna_permessi(u.id, permessi_extra=["fascicoli.elimina"], permessi_negati=[])
    stats = gu.statistiche()
    assert stats["con_override"] == 1


def test_statistiche_nuovi_ruoli(gu):
    gu.crea("col1", "password123", RuoloUtente.COLLABORATORE)
    gu.crea("pra1", "password123", RuoloUtente.PRATICANTE)
    gu.crea("cnt1", "password123", RuoloUtente.CONTABILE)
    stats = gu.statistiche()
    assert stats["per_ruolo"]["COLLABORATORE"] == 1
    assert stats["per_ruolo"]["PRATICANTE"] == 1
    assert stats["per_ruolo"]["CONTABILE"] == 1


# ------------------------------------------------------------------ Proprietà UI

def test_colore_ruolo():
    u = Utente(ruolo=RuoloUtente.AMMINISTRATORE)
    assert u.colore_ruolo == "danger"


def test_icona_ruolo():
    u = Utente(ruolo=RuoloUtente.AVVOCATO)
    assert "bi-" in u.icona_ruolo


def test_descrizione_ruolo():
    u = Utente(ruolo=RuoloUtente.PRATICANTE)
    assert len(u.descrizione_ruolo) > 0


# ------------------------------------------------------------------ TUTTI_PERMESSI struttura

def test_tutti_permessi_struttura():
    assert len(TUTTI_PERMESSI) > 0
    for item in TUTTI_PERMESSI:
        assert len(item) == 3
        categoria, chiave, etichetta = item
        assert "." in chiave, f"Chiave senza categoria: {chiave}"


def test_nessun_permesso_duplicato():
    chiavi = [p for _, p, _ in TUTTI_PERMESSI]
    assert len(chiavi) == len(set(chiavi)), "Ci sono permessi duplicati in TUTTI_PERMESSI"
