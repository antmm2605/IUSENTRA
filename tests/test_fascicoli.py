"""Test per la gestione fascicoli e archivio."""

import pytest
from datetime import date, timedelta
from pathlib import Path

from pct.fascicoli import (
    GestioneFascicoli,
    Fascicolo,
    TipoFascicolo,
    StatoFascicolo,
    TipoDocumento,
    TipoAttivita,
    EsitoAttivita,
    AttivitaProcessuale,
    Documento,
)


@pytest.fixture
def gf(tmp_path):
    return GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "documenti"),
        archive_dir=str(tmp_path / "archivio"),
    )


@pytest.fixture
def fascicolo_base(gf):
    return gf.nuovo(
        titolo="Rossi c/ Bianchi",
        tipo=TipoFascicolo.CIVILE,
        id_cliente="ABC123",
        nome_cliente="Mario Rossi",
        controparte="Luigi Bianchi",
        tribunale="Tribunale di Milano",
        numero_rg="1234",
        anno_rg=2024,
        avvocato_referente="Avv. Verdi",
    )


# ------------------------------------------------------------------ CRUD

def test_crea_fascicolo(fascicolo_base):
    f = fascicolo_base
    assert f.id is not None
    assert f.numero.startswith(str(date.today().year))
    assert f.titolo == "Rossi c/ Bianchi"
    assert f.stato == StatoFascicolo.APERTO
    assert f.rg_completo == "RG 1234/2024"


def test_numerazione_progressiva(gf):
    f1 = gf.nuovo(titolo="F1", tipo=TipoFascicolo.CIVILE)
    f2 = gf.nuovo(titolo="F2", tipo=TipoFascicolo.PENALE)
    anno = date.today().year
    assert f1.numero == f"{anno}/001"
    assert f2.numero == f"{anno}/002"


def test_titolo_vuoto_errore(gf):
    with pytest.raises(ValueError, match="obbligatorio"):
        gf.nuovo(titolo="  ", tipo=TipoFascicolo.CIVILE)


def test_aggiorna_fascicolo(gf, fascicolo_base):
    f = gf.aggiorna(fascicolo_base.id, giudice="Dott. Neri", sezione="I")
    assert f.giudice == "Dott. Neri"
    assert f.sezione == "I"


def test_elimina_fascicolo(gf, fascicolo_base):
    gf.elimina(fascicolo_base.id)
    assert gf.get(fascicolo_base.id) is None


# ------------------------------------------------------------------ Stato

def test_cambia_stato(gf, fascicolo_base):
    f = gf.cambia_stato(fascicolo_base.id, StatoFascicolo.IN_CORSO, note="Prima udienza")
    assert f.stato == StatoFascicolo.IN_CORSO
    assert len(f.avanzamento) >= 1


def test_avanzamento_registrato(gf, fascicolo_base):
    gf.cambia_stato(fascicolo_base.id, StatoFascicolo.SOSPESO, note="Rinvio d'ufficio")
    f = gf.get(fascicolo_base.id)
    assert any("SOSPESO" in av.stato_nuovo for av in f.avanzamento)


def test_definisci(gf, fascicolo_base):
    f = gf.definisci(fascicolo_base.id, esito_finale="FAVOREVOLE",
                     motivo="Sentenza di primo grado")
    assert f.stato == StatoFascicolo.DEFINITO
    assert f.data_chiusura != ""
    assert f.archivio is not None
    assert f.archivio.esito_finale == "FAVOREVOLE"


def test_archivia_crea_zip(gf, fascicolo_base):
    gf.definisci(fascicolo_base.id, esito_finale="FAVOREVOLE")
    f = gf.archivia(fascicolo_base.id, crea_zip=True)
    assert f.stato == StatoFascicolo.ARCHIVIATO
    assert f.archivio.percorso_zip != ""
    assert Path(f.archivio.percorso_zip).exists()
    assert f.archivio.hash_zip != ""


def test_archivia_senza_zip(gf, fascicolo_base):
    f = gf.archivia(fascicolo_base.id, crea_zip=False)
    assert f.stato == StatoFascicolo.ARCHIVIATO
    assert f.archivio.percorso_zip == ""


def test_ripristina_da_archivio(gf, fascicolo_base):
    gf.archivia(fascicolo_base.id, crea_zip=False)
    f = gf.ripristina_da_archivio(fascicolo_base.id)
    assert f.stato == StatoFascicolo.APERTO
    assert f.data_chiusura == ""


def test_archivia_due_volte_errore(gf, fascicolo_base):
    gf.archivia(fascicolo_base.id, crea_zip=False)
    with pytest.raises(ValueError):
        gf.archivia(fascicolo_base.id, crea_zip=False)


# ------------------------------------------------------------------ Documenti

def test_aggiungi_documento(gf, fascicolo_base):
    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="atto.pdf",
        tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        contenuto=b"%PDF-1.4 test content",
        note="Atto principale",
    )
    assert doc.id is not None
    assert doc.nome == "atto.pdf"
    assert doc.dimensione_bytes > 0
    assert doc.hash_sha256 != ""
    f = gf.get(fascicolo_base.id)
    assert len(f.documenti) == 1


def test_documento_salvato_su_disco(gf, fascicolo_base):
    gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="memoria.pdf",
        tipo=TipoDocumento.MEMORIA,
        contenuto=b"contenuto memoria",
    )
    f = gf.get(fascicolo_base.id)
    percorso = gf.percorso_documento(fascicolo_base.id, f.documenti[0].id)
    assert percorso.exists()
    assert percorso.read_bytes() == b"contenuto memoria"


def test_rimuovi_documento(gf, fascicolo_base):
    doc = gf.aggiungi_documento(
        fascicolo_base.id, "da_eliminare.pdf",
        TipoDocumento.ALTRO, b"contenuto"
    )
    percorso = gf.percorso_documento(fascicolo_base.id, doc.id)
    gf.rimuovi_documento(fascicolo_base.id, doc.id)
    assert not percorso.exists()
    f = gf.get(fascicolo_base.id)
    assert len(f.documenti) == 0


def test_documento_nomi_collisione(gf, fascicolo_base):
    """Nomi duplicati devono essere rinominati automaticamente."""
    gf.aggiungi_documento(fascicolo_base.id, "doc.pdf", TipoDocumento.ALTRO, b"v1")
    gf.aggiungi_documento(fascicolo_base.id, "doc.pdf", TipoDocumento.ALTRO, b"v2")
    f = gf.get(fascicolo_base.id)
    assert len(f.documenti) == 2
    nomi = [d.percorso.split("/")[-1] for d in f.documenti]
    assert len(set(nomi)) == 2  # nomi diversi


def test_zip_include_documenti(gf, fascicolo_base):
    gf.aggiungi_documento(
        fascicolo_base.id, "sentenza.pdf",
        TipoDocumento.SENTENZA, b"testo sentenza"
    )
    gf.definisci(fascicolo_base.id)
    f = gf.archivia(fascicolo_base.id, crea_zip=True)
    import zipfile
    with zipfile.ZipFile(f.archivio.percorso_zip, "r") as zf:
        nomi = zf.namelist()
    assert "fascicolo.json" in nomi
    assert "indice_documenti.json" in nomi
    assert any("sentenza.pdf" in n for n in nomi)


# ------------------------------------------------------------------ Attività

def test_aggiungi_attivita(gf, fascicolo_base):
    att = gf.aggiungi_attivita(
        fascicolo_base.id,
        tipo=TipoAttivita.UDIENZA,
        data=(date.today() + timedelta(days=10)).isoformat(),
        titolo="Prima udienza di comparizione",
        luogo="Aula 3",
    )
    assert att.id is not None
    assert att.tipo == TipoAttivita.UDIENZA
    assert att.esito == EsitoAttivita.IN_ATTESA


def test_attivita_passa_in_corso(gf, fascicolo_base):
    """Aggiungere la prima attività porta il fascicolo IN_CORSO."""
    assert fascicolo_base.stato == StatoFascicolo.APERTO
    gf.aggiungi_attivita(
        fascicolo_base.id,
        TipoAttivita.CONSULTAZIONE,
        date.today().isoformat(),
        "Prima consultazione",
    )
    f = gf.get(fascicolo_base.id)
    assert f.stato == StatoFascicolo.IN_CORSO


def test_aggiorna_esito_attivita(gf, fascicolo_base):
    att = gf.aggiungi_attivita(
        fascicolo_base.id,
        TipoAttivita.UDIENZA,
        date.today().isoformat(),
        "Udienza",
    )
    aggiornata = gf.aggiorna_attivita(
        fascicolo_base.id, att.id,
        esito=EsitoAttivita.FAVOREVOLE,
        note="Sentenza a nostro favore",
    )
    assert aggiornata.esito == EsitoAttivita.FAVOREVOLE


def test_prossima_scadenza(gf, fascicolo_base):
    domani = (date.today() + timedelta(days=1)).isoformat()
    tra_dieci = (date.today() + timedelta(days=10)).isoformat()
    gf.aggiungi_attivita(fascicolo_base.id, TipoAttivita.UDIENZA,
                         tra_dieci, "Udienza lontana")
    gf.aggiungi_attivita(fascicolo_base.id, TipoAttivita.TERMINE_SCADENZA,
                         domani, "Scadenza imminente")
    f = gf.get(fascicolo_base.id)
    sc = f.prossima_scadenza
    assert sc is not None
    assert sc.data == domani


def test_ultima_attivita(gf, fascicolo_base):
    gf.aggiungi_attivita(fascicolo_base.id, TipoAttivita.UDIENZA,
                         "2024-01-10", "Prima")
    gf.aggiungi_attivita(fascicolo_base.id, TipoAttivita.UDIENZA,
                         "2024-03-15", "Ultima")
    f = gf.get(fascicolo_base.id)
    assert f.ultima_attivita.titolo == "Ultima"


# ------------------------------------------------------------------ Query

def test_filtra_per_stato(gf, fascicolo_base):
    f2 = gf.nuovo(titolo="Altro", tipo=TipoFascicolo.PENALE)
    gf.cambia_stato(f2.id, StatoFascicolo.SOSPESO)
    aperti = gf.tutti(stato=StatoFascicolo.APERTO)
    assert all(f.stato == StatoFascicolo.APERTO for f in aperti)


def test_filtra_per_cliente(gf, fascicolo_base):
    gf.nuovo(titolo="Altro cliente", tipo=TipoFascicolo.CIVILE,
             id_cliente="ZZZ999", nome_cliente="Altro")
    f_cliente = gf.tutti(id_cliente="ABC123")
    assert all(f.id_cliente == "ABC123" for f in f_cliente)


def test_cerca_testo(gf, fascicolo_base):
    gf.nuovo(titolo="Verdi c/ Neri", tipo=TipoFascicolo.PENALE,
             controparte="Carlo Neri")
    risultati = gf.cerca(testo="bianchi")
    assert len(risultati) == 1
    assert "Bianchi" in risultati[0].controparte


def test_archivio_separato(gf, fascicolo_base):
    gf.archivia(fascicolo_base.id, crea_zip=False)
    attivi = gf.tutti()
    archiviati = gf.archivio()
    assert fascicolo_base.id not in [f.id for f in attivi]
    assert fascicolo_base.id in [f.id for f in archiviati]


def test_scadenze_imminenti(gf, fascicolo_base):
    domani = (date.today() + timedelta(days=1)).isoformat()
    tra_30 = (date.today() + timedelta(days=30)).isoformat()
    gf.aggiungi_attivita(fascicolo_base.id, TipoAttivita.TERMINE_SCADENZA,
                         domani, "Scadenza vicina")
    gf.aggiungi_attivita(fascicolo_base.id, TipoAttivita.UDIENZA,
                         tra_30, "Udienza lontana")
    sc = gf.fascicoli_con_scadenze_imminenti(entro_giorni=7)
    assert len(sc) == 1


# ------------------------------------------------------------------ Persistenza

def test_persistenza(tmp_path):
    db = str(tmp_path / "f.json")
    docs = str(tmp_path / "docs")
    arch = str(tmp_path / "arch")
    gf1 = GestioneFascicoli(db_path=db, documents_dir=docs, archive_dir=arch)
    f = gf1.nuovo(titolo="Test persistenza", tipo=TipoFascicolo.CONSULENZA)
    gf1.aggiungi_documento(f.id, "test.txt", TipoDocumento.ALTRO, b"testo")
    gf2 = GestioneFascicoli(db_path=db, documents_dir=docs, archive_dir=arch)
    caricato = gf2.get(f.id)
    assert caricato is not None
    assert caricato.titolo == "Test persistenza"
    assert len(caricato.documenti) == 1


def test_statistiche(gf, fascicolo_base):
    f2 = gf.nuovo(titolo="F2", tipo=TipoFascicolo.PENALE)
    gf.archivia(f2.id, crea_zip=False)
    stats = gf.statistiche()
    assert stats["totale"] == 2
    assert stats["archiviati"] == 1
    assert stats["attivi"] >= 1
