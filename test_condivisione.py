"""Test per la gestione anagrafica clienti."""

import pytest
from datetime import date, timedelta

from pct.clienti import (
    GestioneClienti,
    Cliente,
    TipoCliente,
    StatoCliente,
    TipoDocumento,
    Indirizzo,
    Recapiti,
    DocumentoIdentita,
    RiferimentoProcedimento,
)


@pytest.fixture
def gc(tmp_path):
    return GestioneClienti(db_path=str(tmp_path / "clienti.json"))


@pytest.fixture
def persona_fisica(gc):
    return gc.nuovo(
        tipo=TipoCliente.PERSONA_FISICA,
        nome="Mario",
        cognome="Rossi",
        codice_fiscale="RSSMRA80A01H501Z",
        data_nascita="1980-01-01",
        luogo_nascita="Roma",
    )


@pytest.fixture
def persona_giuridica(gc):
    return gc.nuovo(
        tipo=TipoCliente.PERSONA_GIURIDICA,
        ragione_sociale="Acme S.r.l.",
        partita_iva="12345678901",
        forma_giuridica="Srl",
    )


# ------------------------------------------------------------------ CRUD

def test_crea_persona_fisica(persona_fisica):
    c = persona_fisica
    assert c.id is not None
    assert c.nome == "Mario"
    assert c.cognome == "Rossi"
    assert c.tipo == TipoCliente.PERSONA_FISICA
    assert c.stato == StatoCliente.ATTIVO


def test_crea_persona_giuridica(persona_giuridica):
    c = persona_giuridica
    assert c.ragione_sociale == "Acme S.r.l."
    assert c.tipo == TipoCliente.PERSONA_GIURIDICA


def test_nome_completo_pf(persona_fisica):
    assert persona_fisica.nome_completo == "Rossi Mario"


def test_nome_completo_pg(persona_giuridica):
    assert persona_giuridica.nome_completo == "Acme S.r.l."


def test_cf_obbligatorio_univoco(gc, persona_fisica):
    with pytest.raises(ValueError, match="già presente"):
        gc.nuovo(
            tipo=TipoCliente.PERSONA_FISICA,
            nome="Luigi",
            cognome="Bianchi",
            codice_fiscale="RSSMRA80A01H501Z",  # stesso CF
        )


def test_cf_case_insensitive(gc, persona_fisica):
    with pytest.raises(ValueError, match="già presente"):
        gc.nuovo(
            tipo=TipoCliente.PERSONA_FISICA,
            nome="Test",
            cognome="Test",
            codice_fiscale="rssmra80a01h501z",  # lowercase
        )


def test_pf_senza_nome_errore(gc):
    with pytest.raises(ValueError, match="Nome o cognome"):
        gc.nuovo(tipo=TipoCliente.PERSONA_FISICA)


def test_pg_senza_ragione_sociale_errore(gc):
    with pytest.raises(ValueError, match="Ragione sociale"):
        gc.nuovo(tipo=TipoCliente.PERSONA_GIURIDICA)


def test_aggiorna_campi(gc, persona_fisica):
    c = gc.aggiorna(persona_fisica.id, note="Cliente importante", avvocato_referente="Avv. Bianchi")
    assert c.note == "Cliente importante"
    assert c.avvocato_referente == "Avv. Bianchi"


def test_aggiorna_recapiti(gc, persona_fisica):
    c = gc.aggiorna_recapiti(
        persona_fisica.id,
        email="mario.rossi@email.it",
        cellulare="+39 333 1234567",
        pec="mario.rossi@pec.it",
    )
    assert c.recapiti.email == "mario.rossi@email.it"
    assert c.recapiti.cellulare == "+39 333 1234567"
    assert c.recapiti.pec == "mario.rossi@pec.it"


def test_aggiorna_indirizzo(gc, persona_fisica):
    c = gc.aggiorna_indirizzo(
        persona_fisica.id,
        "residenza",
        via="Via Roma", civico="10", cap="00100",
        comune="Roma", provincia="RM",
    )
    assert c.indirizzo_residenza.via == "Via Roma"
    assert c.indirizzo_residenza.comune == "Roma"


def test_aggiorna_documento(gc, persona_fisica):
    scadenza = (date.today() + timedelta(days=365)).isoformat()
    c = gc.aggiorna_documento(
        persona_fisica.id,
        tipo=TipoDocumento.CARTA_IDENTITA,
        numero="CA12345AB",
        rilasciato_da="Comune di Roma",
        data_scadenza=scadenza,
    )
    assert c.documento.numero == "CA12345AB"
    assert not c.documento.scaduto


def test_documento_scaduto(gc, persona_fisica):
    scadenza_passata = "2020-01-01"
    c = gc.aggiorna_documento(
        persona_fisica.id,
        data_scadenza=scadenza_passata,
    )
    assert c.documento.scaduto


def test_elimina(gc, persona_fisica):
    gc.elimina(persona_fisica.id)
    assert gc.get(persona_fisica.id) is None


def test_elimina_inesistente(gc):
    with pytest.raises(KeyError):
        gc.elimina("XXXXXXXX")


def test_archivia(gc, persona_fisica):
    c = gc.archivia(persona_fisica.id)
    assert c.stato == StatoCliente.ARCHIVIATO


# ------------------------------------------------------------------ Procedimenti

def test_aggiungi_procedimento(gc, persona_fisica):
    proc = RiferimentoProcedimento(
        numero_rg="1234", anno=2024,
        tribunale="Tribunale di Roma",
        descrizione="Controversia contrattuale",
    )
    c = gc.aggiungi_procedimento(persona_fisica.id, proc)
    assert len(c.procedimenti) == 1
    assert c.procedimenti[0].numero_rg == "1234"


def test_procedimenti_attivi(gc, persona_fisica):
    gc.aggiungi_procedimento(persona_fisica.id,
        RiferimentoProcedimento(numero_rg="1234", anno=2024, tribunale="Roma", attivo=True))
    gc.aggiungi_procedimento(persona_fisica.id,
        RiferimentoProcedimento(numero_rg="5678", anno=2023, tribunale="Milano", attivo=False))
    c = gc.get(persona_fisica.id)
    assert len(c.procedimenti_attivi) == 1


# ------------------------------------------------------------------ Query

def test_tutti_ordinati(gc):
    gc.nuovo(tipo=TipoCliente.PERSONA_FISICA, nome="Zara", cognome="Zeta")
    gc.nuovo(tipo=TipoCliente.PERSONA_FISICA, nome="Aldo", cognome="Alfa")
    tutti = gc.tutti()
    nomi = [c.nome_completo for c in tutti]
    assert nomi == sorted(nomi)


def test_filtra_per_stato(gc, persona_fisica):
    c2 = gc.nuovo(tipo=TipoCliente.PERSONA_FISICA, nome="Luigi", cognome="Bianchi")
    gc.aggiorna(c2.id, stato=StatoCliente.INATTIVO)
    attivi = gc.tutti(stato=StatoCliente.ATTIVO)
    assert all(c.stato == StatoCliente.ATTIVO for c in attivi)


def test_cerca_per_nome(gc, persona_fisica):
    gc.nuovo(tipo=TipoCliente.PERSONA_FISICA, nome="Luigi", cognome="Bianchi")
    risultati = gc.cerca(testo="rossi")
    assert len(risultati) == 1
    assert risultati[0].cognome == "Rossi"


def test_cerca_per_cf(gc, persona_fisica):
    risultati = gc.cerca(testo="RSSMRA80A01H501Z")
    assert len(risultati) == 1


def test_cerca_vuoto(gc, persona_fisica):
    risultati = gc.cerca(testo="XYZ_NON_ESISTE")
    assert len(risultati) == 0


def test_statistiche(gc, persona_fisica, persona_giuridica):
    stats = gc.statistiche()
    assert stats["totale"] == 2
    assert stats["per_tipo"]["PERSONA_FISICA"] == 1
    assert stats["per_tipo"]["PERSONA_GIURIDICA"] == 1


# ------------------------------------------------------------------ Persistenza

def test_persistenza(tmp_path, persona_fisica):
    db = str(tmp_path / "clienti2.json")
    gc1 = GestioneClienti(db_path=db)
    gc1.nuovo(tipo=TipoCliente.PERSONA_FISICA, nome="Test", cognome="Pers")
    gc2 = GestioneClienti(db_path=db)
    assert len(gc2.tutti(stato=None)) == 1


# ------------------------------------------------------------------ Validazione

def test_valida_cf_valido():
    assert GestioneClienti.valida_cf("RSSMRA80A01H501Z") is True


def test_valida_cf_non_valido():
    assert GestioneClienti.valida_cf("123") is False


def test_valida_piva_valida():
    assert GestioneClienti.valida_piva("12345678901") is True


def test_valida_piva_non_valida():
    assert GestioneClienti.valida_piva("123") is False


# ------------------------------------------------------------------ Serde

def test_serializzazione_roundtrip(gc, persona_fisica):
    gc.aggiorna_recapiti(persona_fisica.id, email="test@test.it", pec="test@pec.it")
    gc.aggiorna_indirizzo(persona_fisica.id, "residenza", via="Via Test", comune="Roma")
    gc.aggiungi_procedimento(persona_fisica.id,
        RiferimentoProcedimento(numero_rg="999", anno=2024, tribunale="Roma"))

    c = gc.get(persona_fisica.id)
    d = c.to_dict()
    ricostruito = Cliente.from_dict(d)

    assert ricostruito.nome == c.nome
    assert ricostruito.tipo == c.tipo
    assert ricostruito.recapiti.email == c.recapiti.email
    assert ricostruito.indirizzo_residenza.via == c.indirizzo_residenza.via
    assert len(ricostruito.procedimenti) == len(c.procedimenti)


# ------------------------------------------------------------------ Eta

def test_eta_calcolata(gc):
    c = gc.nuovo(
        tipo=TipoCliente.PERSONA_FISICA,
        nome="Giovane",
        cognome="Test",
        data_nascita="1990-06-15",
    )
    assert c.eta is not None
    assert c.eta >= 34  # almeno 34 anni al 2025


def test_eta_senza_nascita(persona_fisica):
    persona_fisica.data_nascita = ""
    assert persona_fisica.eta is None
