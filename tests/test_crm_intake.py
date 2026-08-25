"""CRM intake lead: pipeline, verifica conflitti art. 24 CDF, conversione.

Fail-closed: niente incarico (VINTO) ne' conversione in cliente senza la
verifica conflitti; match su CF = certo, match solo su nome = da valutare;
lead perso richiede il motivo.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pct.crm_intake import (
    GestioneCrmIntake,
    STATI_LEAD,
    verifica_conflitto_interessi,
)
from pct.storage import StudioDB


class _Repo:
    def __init__(self, rows):
        self._rows = rows

    def tutti(self, stato=None):
        return list(self._rows)


def _cliente(nome="Rossi Mario", cf="RSSMRA80A01F205X"):
    return SimpleNamespace(id="C1", denominazione=nome, nome="", cognome="", codice_fiscale=cf, partita_iva="")


def _controparte(nome="Alfa S.r.l.", piva="01234567890", tipo="CONTROPARTE"):
    return SimpleNamespace(
        id="S1", ragione_sociale=nome, nome="", cognome="",
        codice_fiscale="", partita_iva=piva, tipo=tipo,
    )


# --- Verifica conflitti -----------------------------------------------------------


def test_controparte_con_piva_uguale_e_potenziale_conflitto():
    esito = verifica_conflitto_interessi(
        denominazione="Alfa S.r.l.",
        partita_iva="01234567890",
        get_soggetti=lambda: _Repo([_controparte()]),
    )
    assert esito["livello"] == "potenziale_conflitto"
    assert esito["riscontri"][0]["tipo"] == "controparte"
    assert esito["riscontri"][0]["certo"] is True
    assert "art" in esito["fonte"].lower() or "CDF" in esito["fonte"]


def test_omonimia_senza_codici_e_da_valutare():
    esito = verifica_conflitto_interessi(
        denominazione="alfa s.r.l.",  # case-insensitive
        get_soggetti=lambda: _Repo([_controparte()]),
    )
    assert esito["livello"] == "da_valutare"
    assert esito["riscontri"][0]["certo"] is False


def test_cliente_esistente_segnalato_ma_non_conflitto_certo():
    esito = verifica_conflitto_interessi(
        denominazione="Rossi Mario",
        codice_fiscale="RSSMRA80A01F205X",
        get_clienti=lambda: _Repo([_cliente()]),
    )
    assert esito["livello"] == "da_valutare"
    assert esito["riscontri"][0]["tipo"] == "cliente_esistente"
    assert esito["riscontri"][0]["certo"] is True


def test_nessun_riscontro():
    esito = verifica_conflitto_interessi(
        denominazione="Verdi Anna",
        get_clienti=lambda: _Repo([_cliente()]),
        get_soggetti=lambda: _Repo([_controparte()]),
    )
    assert esito["livello"] == "nessuno"
    assert esito["riscontri"] == []


# --- Pipeline ---------------------------------------------------------------------


@pytest.fixture
def crm(tmp_path):
    return GestioneCrmIntake(db_path=str(tmp_path / "leads.json"))


def test_pipeline_completa(crm):
    lead = crm.nuovo(denominazione="Bianchi Luca", fonte="sito_studio", materia="lavoro")
    assert lead.stato == "NUOVO"
    crm.cambia_stato(lead.id, "CONTATTATO")
    crm.cambia_stato(lead.id, "APPUNTAMENTO")
    crm.cambia_stato(lead.id, "PREVENTIVO")
    colonne = crm.pipeline()
    assert [l.id for l in colonne["PREVENTIVO"]] == [lead.id]
    assert set(colonne) >= set(STATI_LEAD)


def test_vinto_richiede_verifica_conflitti(crm):
    lead = crm.nuovo(denominazione="Bianchi Luca")
    with pytest.raises(ValueError, match="art. 24"):
        crm.cambia_stato(lead.id, "VINTO")
    crm.verifica_conflitti(lead.id)
    assert crm.cambia_stato(lead.id, "VINTO").stato == "VINTO"


def test_perso_richiede_motivo(crm):
    lead = crm.nuovo(denominazione="Bianchi Luca")
    with pytest.raises(ValueError, match="motivo"):
        crm.cambia_stato(lead.id, "PERSO")
    esito = crm.cambia_stato(lead.id, "PERSO", motivo_perso="Ha scelto altro studio")
    assert esito.motivo_perso == "Ha scelto altro studio"


def test_conversione_solo_dopo_verifica_e_idempotente(crm):
    lead = crm.nuovo(denominazione="Bianchi Luca", email="l.bianchi@example.com")
    creati = []

    def crea_cliente(dati):
        creati.append(dati)
        return {"id": "CL-9"}

    with pytest.raises(ValueError, match="verifica conflitti"):
        crm.converti_in_cliente(lead.id, crea_cliente=crea_cliente)
    crm.verifica_conflitti(lead.id)
    esito = crm.converti_in_cliente(lead.id, crea_cliente=crea_cliente)
    assert esito.cliente_id == "CL-9"
    assert esito.stato == "VINTO"
    # seconda conversione: nessun duplicato
    di_nuovo = crm.converti_in_cliente(lead.id, crea_cliente=crea_cliente)
    assert di_nuovo.cliente_id == "CL-9"
    assert len(creati) == 1
    assert "intake CRM" in creati[0]["note"]


def test_verifica_conflitti_salvata_sul_lead(crm):
    lead = crm.nuovo(denominazione="Alfa S.r.l.", partita_iva="01234567890")
    esito = crm.verifica_conflitti(lead.id, get_soggetti=lambda: _Repo([_controparte()]))
    riletto = crm.get(lead.id)
    assert riletto.conflitto_verificato is True
    assert riletto.conflitto_esito["livello"] == esito["livello"] == "potenziale_conflitto"


def test_riscontro_conflitto_richiede_clearance_motivata_prima_della_conversione(crm):
    lead = crm.nuovo(denominazione="Alfa S.r.l.", partita_iva="01234567890")
    crm.verifica_conflitti(lead.id, get_soggetti=lambda: _Repo([_controparte()]))

    with pytest.raises(ValueError, match="decisione professionale"):
        crm.converti_in_cliente(lead.id, crea_cliente=lambda dati: {"id": "CL-9"})
    with pytest.raises(ValueError, match="motivazione"):
        crm.registra_decisione_conflitto(
            lead.id, decisione="CLEARANCE_CONCESSA", motivazione="", operatore="avv.rossi"
        )

    clearance = crm.registra_decisione_conflitto(
        lead.id,
        decisione="CLEARANCE_CONCESSA",
        motivazione="Verificata l'assenza di posizioni contrapposte nel nuovo incarico.",
        operatore="avv.rossi",
    )
    assert clearance["convertibile"] is True
    assert crm.converti_in_cliente(lead.id, crea_cliente=lambda dati: {"id": "CL-9"}).cliente_id == "CL-9"


def test_statistiche_e_tasso_conversione(crm):
    a = crm.nuovo(denominazione="A", fonte="passaparola")
    b = crm.nuovo(denominazione="B", fonte="sito_studio")
    crm.nuovo(denominazione="C", fonte="sito_studio")
    crm.verifica_conflitti(a.id)
    crm.cambia_stato(a.id, "VINTO")
    crm.cambia_stato(b.id, "PERSO", motivo_perso="tariffa")
    stats = crm.statistiche()
    assert stats["totale"] == 3
    assert stats["per_fonte"]["sito_studio"] == 2
    assert stats["tasso_conversione"] == 0.5


def test_persistenza_round_trip(tmp_path):
    percorso = str(tmp_path / "leads.json")
    primo = GestioneCrmIntake(db_path=percorso)
    lead = primo.nuovo(denominazione="Bianchi Luca", materia="famiglia")
    secondo = GestioneCrmIntake(db_path=percorso)
    assert secondo.get(lead.id).materia == "famiglia"


def test_correzione_lead_azzera_verifica_e_registra_audit(crm):
    lead = crm.nuovo(denominazione="Bianchi Luca", codice_fiscale="NON_VALIDO")
    crm.verifica_conflitti(lead.id)

    corretto = crm.aggiorna(
        lead.id,
        denominazione="Bianchi Luca Corretto",
        codice_fiscale="RSSMRA80A01F205X",
        materia="recupero crediti",
    )

    assert corretto.denominazione == "Bianchi Luca Corretto"
    assert corretto.conflitto_verificato is False
    assert corretto.conflitto_esito == {}
    audit = crm.studio_db.conn.execute(
        "SELECT event_type, payload_json FROM intake_compliance_audit WHERE lead_id = ? ORDER BY creato_il DESC",
        (lead.id,),
    ).fetchall()
    assert any(row[0] == "LEAD_DATA_UPDATED" and "verifica_conflitti_da_ripetere" in row[1] for row in audit)


def test_correzione_non_modifica_cliente_gia_convertito(crm):
    lead = crm.nuovo(denominazione="Bianchi Luca")
    crm.verifica_conflitti(lead.id)
    crm.converti_in_cliente(lead.id, crea_cliente=lambda dati: {"id": "CL-9"})

    with pytest.raises(ValueError, match="anagrafica cliente"):
        crm.aggiorna(lead.id, denominazione="Dato non allineato")


def test_sql_e_entity_graph_sono_fonte_operativa_e_json_solo_mirror(tmp_path):
    mirror = tmp_path / "crm" / "leads.json"
    studio_db = StudioDB.get(str(tmp_path / "studio.db"))
    crm = GestioneCrmIntake(
        db_path=str(mirror),
        studio_db=studio_db,
        tenant_id="tenant-test",
    )
    lead = crm.nuovo(denominazione="Alfa S.r.l.", partita_iva="01234567890")
    crm.verifica_conflitti(lead.id, get_soggetti=lambda: _Repo([_controparte()]))
    crm.registra_decisione_conflitto(
        lead.id,
        decisione="CLEARANCE_CONCESSA",
        motivazione="Caso controllato: nessuna posizione contrapposta nel nuovo incarico.",
        operatore="avv.qa",
    )
    crm.converti_in_cliente(lead.id, crea_cliente=lambda dati: {"id": "CL-9"})

    assert crm.source_of_truth == "sqlite"
    assert studio_db.conn.execute("SELECT COUNT(*) FROM crm_leads").fetchone()[0] == 1
    assert studio_db.conn.execute("SELECT COUNT(*) FROM entity_nodes").fetchone()[0] == 2
    assert studio_db.conn.execute("SELECT COUNT(*) FROM entity_relationships").fetchone()[0] == 1
    assessment = studio_db.conn.execute(
        "SELECT status FROM intake_compliance_assessments WHERE lead_id = ?", (lead.id,)
    ).fetchone()
    assert assessment[0] == "POTENZIALE_CONFLITTO"
    assert studio_db.conn.execute(
        "SELECT COUNT(*) FROM transactional_outbox WHERE aggregate_id = ?", (lead.id,)
    ).fetchone()[0] == 3
    assert mirror.exists()


def test_recupera_archivio_crm_scoped_precedente_nel_db_canonico(tmp_path):
    mirror = tmp_path / "crm" / "leads.json"
    legacy_db = StudioDB.get(str(tmp_path / "crm" / "studio.db"))
    legacy = GestioneCrmIntake(db_path=str(mirror), studio_db=legacy_db)
    lead = legacy.nuovo(denominazione="Recupero CRM", partita_iva="12345678903")
    legacy.verifica_conflitti(lead.id)

    canonical_db = StudioDB.get(str(tmp_path / "studio.db"))
    restored = GestioneCrmIntake(db_path=str(mirror), studio_db=canonical_db)

    assert restored.get(lead.id) is not None
    assert canonical_db.conn.execute("SELECT COUNT(*) FROM crm_leads").fetchone()[0] == 1
    assert canonical_db.conn.execute(
        "SELECT COUNT(*) FROM intake_compliance_audit WHERE lead_id = ?", (lead.id,)
    ).fetchone()[0] == 1
    assert canonical_db.conn.execute(
        "SELECT COUNT(*) FROM transactional_outbox WHERE aggregate_id = ?", (lead.id,)
    ).fetchone()[0] == 2


def test_archivio_crm_scoped_migrato_non_reimporta_record_rimossi(tmp_path):
    mirror = tmp_path / "crm" / "leads.json"
    legacy_db = StudioDB.get(str(tmp_path / "crm" / "studio.db"))
    legacy = GestioneCrmIntake(db_path=str(mirror), studio_db=legacy_db)
    lead = legacy.nuovo(denominazione="Dato di collaudo da rimuovere")

    canonical_db = StudioDB.get(str(tmp_path / "studio.db"))
    GestioneCrmIntake(db_path=str(mirror), studio_db=canonical_db)
    assert canonical_db.conn.execute("SELECT COUNT(*) FROM crm_leads").fetchone()[0] == 1

    canonical_db.conn.execute("DELETE FROM crm_leads WHERE id = ?", (lead.id,))
    canonical_db.conn.commit()
    mirror.write_text("{}", encoding="utf-8")

    reloaded = GestioneCrmIntake(db_path=str(mirror), studio_db=canonical_db)
    assert reloaded.get(lead.id) is None
    assert canonical_db.conn.execute("SELECT COUNT(*) FROM crm_leads").fetchone()[0] == 0
    assert canonical_db.conn.execute(
        "SELECT COUNT(*) FROM crm_runtime_migrations WHERE migration_key = ?",
        ("crm_scoped_sqlite_to_root_v1",),
    ).fetchone()[0] == 1


def test_barriera_informativa_segrega_accessi_e_registra_audit_outbox(crm):
    lead = crm.nuovo(denominazione="Trattativa riservata")

    stato = crm.crea_barriera_riservatezza(
        lead.id,
        motivazione="Trattativa riservata con potenziale conflitto interno.",
        utenti_autorizzati=["avv.collaboratore"],
        operatore="avv.responsabile",
    )

    assert stato["attiva"] is True
    assert stato["accesso_consentito"] is True
    assert set(stato["utenti_autorizzati"]) == {"avv.responsabile", "avv.collaboratore"}
    assert crm.accesso_lead_consentito(lead.id, operatore="avv.collaboratore") is True
    assert crm.accesso_lead_consentito(lead.id, operatore="avv.estraneo") is False
    with pytest.raises(PermissionError, match="responsabile"):
        crm.aggiorna_barriera_riservatezza(
            lead.id,
            motivazione="Tentativo non autorizzato.",
            utenti_autorizzati=["avv.estraneo"],
            operatore="avv.collaboratore",
        )

    audit = crm.studio_db.conn.execute(
        "SELECT event_type, payload_json FROM ethical_wall_audit WHERE lead_id = ?",
        (lead.id,),
    ).fetchall()
    assert audit[0][0] == "CRM_ETHICAL_WALL_CREATED"
    assert "potenziale conflitto" in audit[0][1]
    assert crm.studio_db.conn.execute(
        "SELECT COUNT(*) FROM transactional_outbox WHERE aggregate_type = 'ethical_wall'"
    ).fetchone()[0] == 1

    revoked = crm.revoca_barriera_riservatezza(
        lead.id,
        motivazione="Conclusa la trattativa riservata.",
        operatore="avv.responsabile",
    )
    assert revoked["attiva"] is False
    assert crm.accesso_lead_consentito(lead.id, operatore="avv.estraneo") is True
