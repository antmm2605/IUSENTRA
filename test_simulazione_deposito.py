"""Test per l'indice di ricerca full-text (SQLite FTS5)."""

import pytest
from pct.search_index import IndiceRicerca, RisultatoRicerca


@pytest.fixture
def indice(tmp_path):
    return IndiceRicerca(index_path=str(tmp_path / "search.db"))


# ------------------------------------------------------------------ Indicizzazione

def test_indicizza_e_cerca(indice):
    indice.indicizza("cliente", "C001", "Mario Rossi", "avvocato penalista Roma")
    risultati = indice.cerca("Mario")
    assert len(risultati) == 1
    assert risultati[0].tipo == "cliente"
    assert risultati[0].id == "C001"
    assert risultati[0].titolo == "Mario Rossi"


def test_rimuovi_documento(indice):
    indice.indicizza("fascicolo", "F001", "Causa Rossi", "tribunale Milano")
    indice.rimuovi("fascicolo", "F001")
    assert indice.cerca("Rossi") == []


def test_upsert_sovrascrive(indice):
    indice.indicizza("cliente", "C002", "Vecchio Titolo", "testo originale")
    indice.indicizza("cliente", "C002", "Nuovo Titolo", "testo aggiornato")
    risultati = indice.cerca("Nuovo")
    assert len(risultati) == 1
    assert risultati[0].titolo == "Nuovo Titolo"
    # Il vecchio titolo non deve comparire
    assert indice.cerca("Vecchio") == []


def test_cerca_prefix_match(indice):
    """Prefix match: 'Ros*' deve trovare 'Rossi'."""
    indice.indicizza("cliente", "C003", "Rossi Paolo", "avvocato")
    risultati = indice.cerca("Ros")
    assert any(r.id == "C003" for r in risultati)


def test_cerca_corpo(indice):
    """Ricerca nel corpo, non solo nel titolo."""
    indice.indicizza("fascicolo", "F002", "Causa civile", "tribunale di Napoli sezione lavoro")
    risultati = indice.cerca("Napoli")
    assert any(r.id == "F002" for r in risultati)


def test_filtra_per_tipo(indice):
    indice.indicizza("cliente", "C004", "Anna Bianchi", "commercialista")
    indice.indicizza("fascicolo", "F003", "Anna eredità", "successione")
    solo_clienti = indice.cerca("Anna", tipi=["cliente"])
    assert all(r.tipo == "cliente" for r in solo_clienti)


def test_cerca_query_vuota(indice):
    assert indice.cerca("") == []
    assert indice.cerca("   ") == []


def test_cerca_query_invalida_non_crasha(indice):
    """Una query FTS5 malformata non deve sollevare eccezioni."""
    indice.indicizza("cliente", "C005", "Test", "corpo")
    # Caratteri speciali FTS5 che possono causare errori di parsing
    risultati = indice.cerca('"unclosed')
    assert isinstance(risultati, list)


def test_limite_risultati(indice):
    for i in range(20):
        indice.indicizza("scadenza", f"S{i:03d}", f"Scadenza test {i}", "deposito atti")
    risultati = indice.cerca("test", limit=5)
    assert len(risultati) <= 5


# ------------------------------------------------------------------ Ricostruzione

def test_ricostruisci_da_dict(indice):
    clienti = [
        {"id": "C010", "cognome": "Verdi", "nome": "Luigi", "codice_fiscale": "VRDLGI80A01H501Z"},
        {"id": "C011", "ragione_sociale": "Studio Rossi SRL"},
    ]
    indice.ricostruisci(clienti=clienti)
    assert len(indice.cerca("Verdi")) == 1
    assert len(indice.cerca("Rossi")) == 1


def test_ricostruisci_svuota_precedenti(indice):
    indice.indicizza("cliente", "OLD", "Vecchio", "corpo")
    indice.ricostruisci(clienti=[{"id": "NEW", "cognome": "Nuovo", "nome": ""}])
    assert indice.cerca("Vecchio") == []
    assert len(indice.cerca("Nuovo")) == 1


def test_ricostruisci_fascicoli(indice):
    fascicoli = [
        {"id": "F010", "numero": "2024/001", "titolo": "Causa di lavoro", "tribunale": "Roma"},
    ]
    indice.ricostruisci(fascicoli=fascicoli)
    assert len(indice.cerca("lavoro")) == 1


# ------------------------------------------------------------------ Cerca globale

def test_cerca_globale_raggruppa(indice):
    indice.indicizza("cliente", "C020", "Marco Ferrari", "commercialista")
    indice.indicizza("fascicolo", "F020", "Marco vs Ferrari", "causa civile")
    gruppi = indice.cerca_globale("Ferrari", limit=10)
    assert isinstance(gruppi, dict)
    tipi = set(gruppi.keys())
    assert len(tipi) >= 1


# ------------------------------------------------------------------ Statistiche

def test_statistiche(indice):
    indice.indicizza("cliente", "C030", "Test", "corpo")
    indice.indicizza("fascicolo", "F030", "Test", "corpo")
    stats = indice.statistiche()
    assert stats["totale"] == 2
    assert stats["per_tipo"]["cliente"] == 1
    assert stats["per_tipo"]["fascicolo"] == 1


def test_statistiche_vuote(indice):
    stats = indice.statistiche()
    assert stats["totale"] == 0


# ------------------------------------------------------------------ Metadati helper

def test_url_fascicolo(indice):
    indice.indicizza("fascicolo", "F040", "Titolo", "corpo")
    r = indice.cerca("Titolo")[0]
    assert r.url == "/fascicoli/F040"


def test_icona_cliente(indice):
    indice.indicizza("cliente", "C040", "Test", "corpo")
    r = indice.cerca("Test")[0]
    assert r.icona == "bi-person"


def test_snippet_presente(indice):
    indice.indicizza("cliente", "C050", "Snippet Test", "questo è un testo molto lungo da cercare")
    risultati = indice.cerca("testo")
    assert len(risultati) == 1
    # Il snippet può contenere il termine cercato (con o senza mark)
    assert risultati[0].snippet is not None


# ------------------------------------------------------------------ Ottimizzazione

def test_ottimizza_non_crasha(indice):
    indice.indicizza("cliente", "C060", "Test", "corpo")
    indice.ottimizza()  # non deve sollevare eccezioni
