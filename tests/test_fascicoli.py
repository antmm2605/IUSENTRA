"""Test per la gestione fascicoli e archivio."""

import hashlib
import json
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
    EsitoDepositoPCT,
    normalizza_stato_deposito_pct,
    stato_fascicolo_da_descrizione_portale,
    _normalizza_esito_controlli,
)
from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicolo_document_presidio import duplicate_practice_groups, normalise_practice_duplicate_key
from pct.storage import StudioDB


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


def test_gestione_fascicoli_deriva_documenti_e_archivio_dal_db_path_quando_non_specificati(tmp_path):
    db_path = tmp_path / "tenant-demo" / "fascicoli.json"
    gf = GestioneFascicoli(db_path=str(db_path))

    assert gf.documents_dir == db_path.parent / "documenti"
    assert gf.archive_dir == db_path.parent / "archivio"


def test_doppioni_fascicolo_ignora_controparte_nel_nome_cliente() -> None:
    first = {
        "id": "CB1360DD",
        "numero_rg": "795",
        "anno_rg": "2026",
        "nome_cliente": "Eugenio Grosso c. MIM",
    }
    second = {
        "id": "FE336495",
        "numero_rg": "795",
        "anno_rg": "2026",
        "nome_cliente": "Grosso Eugenio",
    }

    assert normalise_practice_duplicate_key(first) == normalise_practice_duplicate_key(second)
    groups = duplicate_practice_groups([first, second])
    assert len(groups) == 1
    assert groups[0]["count"] == 2


def test_percorso_documento_lettura_normalizza_separatori_windows(gf, fascicolo_base):
    fasc_dir = gf.documents_dir / fascicolo_base.id
    fasc_dir.mkdir(parents=True, exist_ok=True)
    target = fasc_dir / "atto.pdf"
    target.write_bytes(b"%PDF-1.4 test")
    doc = Documento(
        id="DOCWIN01",
        nome="atto.pdf",
        tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        percorso=f"{fascicolo_base.id}\\atto.pdf",
        dimensione_bytes=target.stat().st_size,
        hash_sha256="",
    )
    fascicolo_base.documenti.append(doc)
    gf._salva()

    assert gf.percorso_documento(fascicolo_base.id, doc.id) == target
    assert gf.percorso_documento_lettura(fascicolo_base.id, doc.id) == target


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


def test_nuovo_sql_blocca_cliente_mancante_nel_tenant(tmp_path):
    studio_db = StudioDB(str(tmp_path / "studio.db"))
    gestore = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
        studio_db=studio_db,
    )

    with pytest.raises(ValueError, match="tenant corrente"):
        gestore.nuovo(
            titolo="Martorano Mara c. MIM",
            tipo=TipoFascicolo.LAVORO,
            id_cliente="BA82D89F",
            nome_cliente="",
        )

    assert gestore.tutti() == []


def test_nuovo_sql_riallinea_nome_cliente_da_anagrafica_tenant(tmp_path):
    studio_db = StudioDB(str(tmp_path / "studio.db"))
    clienti = GestioneClienti(
        db_path=str(tmp_path / "clienti" / "anagrafica.json"),
        studio_db=studio_db,
    )
    cliente = clienti.nuovo(
        tipo=TipoCliente.PERSONA_FISICA,
        nome="Mara",
        cognome="Martorano",
    )
    gestore = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
        studio_db=studio_db,
    )

    fascicolo = gestore.nuovo(
        titolo="Martorano Mara c. MIM",
        tipo=TipoFascicolo.LAVORO,
        id_cliente=cliente.id,
        nome_cliente="Nome non allineato",
    )

    assert fascicolo.id_cliente == cliente.id
    assert fascicolo.nome_cliente == "Martorano Mara"


def test_aggiorna_sql_blocca_cambio_su_cliente_mancante(tmp_path):
    studio_db = StudioDB(str(tmp_path / "studio.db"))
    clienti = GestioneClienti(
        db_path=str(tmp_path / "clienti" / "anagrafica.json"),
        studio_db=studio_db,
    )
    cliente = clienti.nuovo(
        tipo=TipoCliente.PERSONA_FISICA,
        nome="Mario",
        cognome="Rossi",
    )
    gestore = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
        studio_db=studio_db,
    )
    fascicolo = gestore.nuovo(
        titolo="Rossi c/ Bianchi",
        tipo=TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
    )

    with pytest.raises(ValueError, match="tenant corrente"):
        gestore.aggiorna(
            fascicolo.id,
            id_cliente="CLIENTE_NO",
            nome_cliente="Cliente inesistente",
        )

    assert gestore.get(fascicolo.id).id_cliente == cliente.id


def test_nuovo_blocca_doppione_cliente_rg(gf):
    primo = gf.nuovo(
        titolo="Spagnolo Sara c. MIM",
        tipo=TipoFascicolo.CIVILE,
        nome_cliente="Spagnolo Sara",
        numero_rg="3950",
        anno_rg=2026,
        tribunale="Tribunale di Vicenza",
    )

    secondo = gf.nuovo(
        titolo="Spagnolo Sara c. Ministero",
        tipo=TipoFascicolo.CIVILE,
        nome_cliente="Sara Spagnolo",
        numero_rg="3950",
        anno_rg=2026,
        tribunale="Tribunale di Vicenza",
    )

    assert secondo.id == primo.id
    assert len(gf.tutti()) == 1
    assert any("Creazione doppione bloccata" in item.descrizione for item in secondo.avanzamento)


def test_riconcilia_doppioni_cliente_rg_unisce_documenti_e_pagamenti(gf):
    principale = gf.nuovo(
        titolo="Punturiero c. MIM",
        tipo=TipoFascicolo.CIVILE,
        nome_cliente="Punturiero Rosa",
        numero_rg="1733",
        anno_rg=2026,
        data_prossima_udienza="",
        pagamenti={
            "liquidazione_giudice": {
                "status": "da_registrare",
                "fonti_documentali": [],
            }
        },
    )
    duplicato = Fascicolo(
        id="DUP1733A",
        numero="2026/999",
        titolo="RG 1733/2026 - retribuzione",
        tipo=TipoFascicolo.CIVILE,
        nome_cliente="Rosa Punturiero",
        numero_rg="1733",
        anno_rg=2026,
        data_prossima_udienza="2026-09-10",
        pagamenti={
            "liquidazione_giudice": {
                "status": "da_registrare",
                "importo": 1100,
                "documento_fonte": "Sentenza.pdf",
                "fonti_documentali": ["Sentenza.pdf"],
            }
        },
    )
    dup_dir = gf.documents_dir / duplicato.id
    dup_dir.mkdir(parents=True, exist_ok=True)
    source_file = dup_dir / "Sentenza.pdf"
    source_file.write_bytes(b"%PDF-1.4 sentenza")
    duplicato.documenti.append(
        Documento(
            id="DOCSENT1",
            nome="Sentenza.pdf",
            tipo=TipoDocumento.SENTENZA,
            percorso=f"{duplicato.id}/Sentenza.pdf",
            dimensione_bytes=source_file.stat().st_size,
            hash_sha256="sentenza-hash",
        )
    )
    gf._fascicoli[duplicato.id] = duplicato
    gf._salva()

    report = gf.riconcilia_doppioni_cliente_rg()
    primary_id = report["groups"][0]["primaryId"]
    aggiornato = gf.get(primary_id)

    assert report["removedDuplicates"] == 1
    assert primary_id in {principale.id, duplicato.id}
    assert len(gf.tutti()) == 1
    assert aggiornato.data_prossima_udienza == "2026-09-10"
    assert any(doc.nome == "Sentenza.pdf" for doc in aggiornato.documenti)
    assert gf.percorso_documento_lettura(aggiornato.id, "DOCSENT1").exists()
    assert aggiornato.pagamenti["liquidazione_giudice"]["importo"] == 1100
    assert aggiornato.pagamenti["liquidazione_giudice"]["fonti_documentali"] == ["Sentenza.pdf"]
    assert aggiornato.pagamenti["_presidio_documentale"]["status"] == "stale"


def test_aggiungi_documento_marca_presidio_da_rianalizzare(gf, fascicolo_base):
    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="Decreto fissazione udienza.pdf",
        tipo=TipoDocumento.DECRETO,
        contenuto=b"%PDF-1.4 decreto",
    )
    aggiornato = gf.get(fascicolo_base.id)

    assert aggiornato.pagamenti["_presidio_documentale"]["status"] == "stale"
    assert aggiornato.pagamenti["_presidio_documentale"]["document_id"] == doc.id


def test_aggiungi_documenti_accumula_tutti_gli_id_da_analizzare(gf, fascicolo_base):
    primo = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="Primo allegato.txt",
        tipo=TipoDocumento.ALLEGATO,
        contenuto=b"primo",
    )
    secondo = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="Secondo allegato.txt",
        tipo=TipoDocumento.ALLEGATO,
        contenuto=b"secondo",
    )

    marker = gf.get(fascicolo_base.id).pagamenti["_presidio_documentale"]

    assert marker["document_id"] == secondo.id
    assert marker["document_ids"] == [primo.id, secondo.id]


def test_aggiungi_documento_non_duplica_stesso_contenuto(gf, fascicolo_base):
    primo = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="Ricorso.pdf",
        tipo=TipoDocumento.RICORSO,
        contenuto=b"%PDF-1.4 stesso contenuto",
    )
    secondo = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="Ricorso.pdf",
        tipo=TipoDocumento.RICORSO,
        contenuto=b"%PDF-1.4 stesso contenuto",
        tags=["Portale Servizi"],
        fonte_documento="PORTALE_TELEMATICO",
        nome_portale="Ricorso.pdf",
    )

    aggiornato = gf.get(fascicolo_base.id)

    assert secondo.id == primo.id
    assert len(aggiornato.documenti) == 1
    assert aggiornato.documenti[0].fonte_documento == "PORTALE_TELEMATICO"
    assert "Portale Servizi" in aggiornato.documenti[0].tags


def test_aggiungi_documento_stesso_contenuto_nome_diverso_restano_distinti(gf, fascicolo_base):
    gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="allegato-01.pdf",
        tipo=TipoDocumento.ALLEGATO,
        contenuto=b"%PDF-1.4\n%%EOF",
    )
    gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="allegato-02.pdf",
        tipo=TipoDocumento.ALLEGATO,
        contenuto=b"%PDF-1.4\n%%EOF",
    )

    aggiornato = gf.get(fascicolo_base.id)

    assert [doc.nome for doc in aggiornato.documenti] == ["allegato-01.pdf", "allegato-02.pdf"]


def test_aggiungi_documento_non_duplica_pdf_stesso_nome_tipo_conserva_versione(gf, fascicolo_base):
    primo = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="Sentenza.pdf",
        tipo=TipoDocumento.SENTENZA,
        contenuto=b"%PDF-1.4 sentenza importata",
        fonte_documento="IMPORT_ESTERNO",
    )
    secondo = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="Sentenza.pdf",
        tipo=TipoDocumento.SENTENZA,
        contenuto=b"%PDF-1.4 sentenza portale",
        fonte_documento="PORTALE_TELEMATICO",
        nome_portale="Sentenza.pdf",
    )

    aggiornato = gf.get(fascicolo_base.id)
    doc = aggiornato.documenti[0]

    assert secondo.id == primo.id
    assert len(aggiornato.documenti) == 1
    assert doc.fonte_documento == "IMPORT_ESTERNO"
    assert len(doc.versioni) == 1
    assert doc.versioni[0].hash_sha256 == hashlib.sha256(b"%PDF-1.4 sentenza portale").hexdigest()
    assert (gf.documents_dir / doc.versioni[0].percorso).exists()


def test_documenti_portale_con_identificativi_distinti_e_stesso_nome_restano_distinti(gf, fascicolo_base):
    primo = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="Decreto.pdf",
        tipo=TipoDocumento.DECRETO,
        contenuto=b"%PDF-1.4 decreto uno",
        fonte_documento="PORTALE_TELEMATICO",
        id_documento_portale="PST-DOC-001",
        id_cat_portale="PST-CAT-001",
    )
    secondo = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="Decreto.pdf",
        tipo=TipoDocumento.DECRETO,
        contenuto=b"%PDF-1.4 decreto due",
        fonte_documento="PORTALE_TELEMATICO",
        id_documento_portale="PST-DOC-002",
        id_cat_portale="PST-CAT-002",
    )

    aggiornato = gf.get(fascicolo_base.id)

    assert primo.id != secondo.id
    assert len(aggiornato.documenti) == 2
    assert {doc.id_documento_portale for doc in aggiornato.documenti} == {"PST-DOC-001", "PST-DOC-002"}


def test_riconcilia_documenti_duplicati_assorbe_record_e_riferimenti(gf, fascicolo_base):
    originale = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="Sentenza.pdf",
        tipo=TipoDocumento.SENTENZA,
        contenuto=b"%PDF-1.4 sentenza identica",
    )
    fascicolo = gf.get(fascicolo_base.id)
    duplicato = Documento(
        id="DUPDOC01",
        nome="Sentenza.pdf",
        tipo=TipoDocumento.SENTENZA,
        percorso=originale.percorso,
        dimensione_bytes=originale.dimensione_bytes,
        hash_sha256=originale.hash_sha256,
        fonte_documento="IMPORT_ESTERNO",
    )
    fascicolo.documenti.append(duplicato)
    fascicolo.depositi_pct.append(
        EsitoDepositoPCT(
            id="DEP1",
            timestamp="2026-07-09T09:00:00",
            stato="IMPORTATO_DA_PORTALE",
            tipo_atto="SENTENZA",
            pec_destinatario="tribunale@example.test",
            documenti_ids=[duplicato.id],
        )
    )
    fascicolo.attivita.append(
        AttivitaProcessuale(
            id="ATT1",
            tipo=TipoAttivita.PROVVEDIMENTO,
            data="2026-07-09",
            titolo="Deposito sentenza",
            id_documento=duplicato.id,
        )
    )
    gf._salva()

    report = gf.riconcilia_documenti_duplicati(fascicolo_base.id)
    aggiornato = gf.get(fascicolo_base.id)
    remaining_id = aggiornato.documenti[0].id

    assert report["documentiDuplicatiAssorbiti"] == 1
    assert len(aggiornato.documenti) == 1
    assert aggiornato.depositi_pct[0].documenti_ids == [remaining_id]
    assert aggiornato.attivita[0].id_documento == remaining_id
    assert any("documenti duplicati" in item.descrizione for item in aggiornato.avanzamento)


def test_riconcilia_documenti_duplicati_pdf_stesso_nome_conserva_versione(gf, fascicolo_base):
    originale = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="Sentenza.pdf",
        tipo=TipoDocumento.SENTENZA,
        contenuto=b"%PDF-1.4 sentenza importata",
    )
    fascicolo = gf.get(fascicolo_base.id)
    duplicato = Documento(
        id="DUPDOC02",
        nome="Sentenza.pdf",
        tipo=TipoDocumento.SENTENZA,
        percorso=f"{fascicolo_base.id}/Sentenza-portale.pdf",
        dimensione_bytes=len(b"%PDF-1.4 sentenza portale"),
        hash_sha256=hashlib.sha256(b"%PDF-1.4 sentenza portale").hexdigest(),
        fonte_documento="PORTALE_TELEMATICO",
    )
    fascicolo.documenti.append(duplicato)

    report = gf.riconcilia_documenti_duplicati(fascicolo_base.id)
    aggiornato = gf.get(fascicolo_base.id)

    assert report["documentiDuplicatiAssorbiti"] == 1
    assert len(aggiornato.documenti) == 1
    assert aggiornato.documenti[0].id == duplicato.id
    assert len(aggiornato.documenti[0].versioni) == 1
    assert aggiornato.documenti[0].versioni[0].percorso == originale.percorso


def test_riconcilia_documenti_duplicati_sql_non_riscrive_tutta_tabella(tmp_path):
    studio_db = StudioDB.get(str(tmp_path / "studio.db"))
    gf_sql = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "documenti"),
        archive_dir=str(tmp_path / "archivio"),
        studio_db=studio_db,
    )
    primo = gf_sql.nuovo(
        titolo="Primo c. MIM",
        tipo=TipoFascicolo.CIVILE,
        nome_cliente="Primo Cliente",
        numero_rg="101",
        anno_rg=2026,
    )
    secondo = gf_sql.nuovo(
        titolo="Secondo c. MIM",
        tipo=TipoFascicolo.CIVILE,
        nome_cliente="Secondo Cliente",
        numero_rg="102",
        anno_rg=2026,
    )
    originale = gf_sql.aggiungi_documento(
        primo.id,
        nome_file="Sentenza.pdf",
        tipo=TipoDocumento.SENTENZA,
        contenuto=b"%PDF-1.4 sentenza",
    )
    fascicolo = gf_sql.get(primo.id)
    fascicolo.documenti.append(
        Documento(
            id="DUPSQL01",
            nome="Sentenza.pdf",
            tipo=TipoDocumento.SENTENZA,
            percorso=originale.percorso,
            dimensione_bytes=originale.dimensione_bytes,
            hash_sha256=originale.hash_sha256,
        )
    )

    report = gf_sql.riconcilia_documenti_duplicati(primo.id)
    mirror = json.loads((tmp_path / "fascicoli.json").read_text(encoding="utf-8"))

    assert report["source_of_truth"] == "sqlite"
    assert report["documentiDuplicatiAssorbiti"] == 1
    assert studio_db.conn.execute("select count(*) from fascicoli").fetchone()[0] == 2
    assert studio_db.conn.execute("select id from fascicoli where id=?", (secondo.id,)).fetchone()[0] == secondo.id
    assert set(mirror) == {primo.id, secondo.id}
    assert len(mirror[primo.id]["documenti"]) == 1


def test_riconcilia_doppioni_cliente_rg_sql_salva_solo_record_coinvolti(tmp_path, monkeypatch):
    studio_db = StudioDB.get(str(tmp_path / "studio.db"))
    gf_sql = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "documenti"),
        archive_dir=str(tmp_path / "archivio"),
        studio_db=studio_db,
    )
    principale = gf_sql.nuovo(
        titolo="Grosso Eugenio c. MIM",
        tipo=TipoFascicolo.CIVILE,
        nome_cliente="Grosso Eugenio",
        numero_rg="795",
        anno_rg=2026,
    )
    duplicato = Fascicolo(
        id="DUP795RG",
        numero="2026/999",
        titolo="Eugenio Grosso c. MIM",
        tipo=TipoFascicolo.CIVILE,
        nome_cliente="Eugenio Grosso c. MIM",
        numero_rg="795",
        anno_rg=2026,
        stato=StatoFascicolo.ARCHIVIATO,
    )
    gf_sql._fascicoli[duplicato.id] = duplicato
    gf_sql._salva()

    def _full_replace_vietato():
        raise AssertionError("La riconciliazione SQL deve usare salvataggio parziale")

    monkeypatch.setattr(gf_sql, "_salva", _full_replace_vietato)
    report = gf_sql.riconcilia_doppioni_cliente_rg()
    mirror = json.loads((tmp_path / "fascicoli.json").read_text(encoding="utf-8"))

    assert report["source_of_truth"] == "sqlite"
    assert report["removedDuplicates"] == 1
    assert studio_db.conn.execute("select count(*) from fascicoli").fetchone()[0] == 1
    assert studio_db.conn.execute("select count(*) from fascicoli where id=?", (principale.id,)).fetchone()[0] == 1
    assert studio_db.conn.execute("select count(*) from fascicoli where id=?", (duplicato.id,)).fetchone()[0] == 0
    assert set(mirror) == {principale.id}


def test_aggiorna_non_lascia_doppioni_cliente_rg(gf):
    primo = gf.nuovo(
        titolo="Cliente c. MIM",
        tipo=TipoFascicolo.CIVILE,
        nome_cliente="Cliente Test",
        numero_rg="701",
        anno_rg=2026,
    )
    secondo = gf.nuovo(
        titolo="Altro fascicolo",
        tipo=TipoFascicolo.CIVILE,
        nome_cliente="Altro Cliente",
        numero_rg="702",
        anno_rg=2026,
    )

    aggiornato = gf.aggiorna(
        secondo.id,
        nome_cliente="Test Cliente",
        numero_rg="701",
        anno_rg=2026,
    )

    assert aggiornato.id in {primo.id, secondo.id}
    assert len(gf.tutti()) == 1


def test_aggiorna_fascicolo(gf, fascicolo_base):
    f = gf.aggiorna(fascicolo_base.id, giudice="Dott. Neri", sezione="I")
    assert f.giudice == "Dott. Neri"
    assert f.sezione == "I"


def test_aggiorna_flag_controlli_conformita(gf, fascicolo_base):
    gf.aggiorna(fascicolo_base.id, compliance_controls_enabled=False)
    ricaricato = gf.get(fascicolo_base.id)
    assert ricaricato.compliance_controls_enabled is False


def test_elimina_fascicolo(gf, fascicolo_base):
    gf.elimina(fascicolo_base.id)
    assert gf.get(fascicolo_base.id) is None


def test_riallinea_integrita_documento_fisico_preserva_hash_precedente(gf, fascicolo_base):
    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        "verbale.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        b"contenuto ricevuto dal portale",
    )
    previous_hash = doc.hash_sha256
    doc.hash_contenuto_sha256 = ""
    gf._salva()
    path = gf.percorso_documento(fascicolo_base.id, doc.id)
    path.write_bytes(b"copia storica gia trasformata")

    report = gf.riallinea_integrita_documento_fisico(fascicolo_base.id, doc.id)
    updated = gf.get(fascicolo_base.id).documenti[0]

    assert report["changed"] is True
    assert updated.hash_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert updated.dimensione_bytes == path.stat().st_size
    assert updated.hash_contenuto_sha256 == previous_hash
    assert gf.riallinea_integrita_documento_fisico(fascicolo_base.id, doc.id)["changed"] is False


def test_sostituisci_documento_preserva_file_precedente_e_hash_contenuto(gf, fascicolo_base):
    original_bytes = b"prima versione"
    updated_bytes = b"seconda versione"
    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        "memoria.pdf",
        TipoDocumento.MEMORIA,
        original_bytes,
    )
    original_path = doc.percorso

    updated = gf.sostituisci_documento(
        fascicolo_base.id,
        doc.id,
        "memoria.pdf",
        updated_bytes,
        hash_contenuto_sha256=hashlib.sha256(updated_bytes).hexdigest(),
    )

    assert updated.percorso != original_path
    assert (gf.documents_dir / original_path).read_bytes() == original_bytes
    assert (gf.documents_dir / updated.percorso).read_bytes() == updated_bytes
    assert updated.versioni[-1].percorso == original_path
    assert updated.hash_contenuto_sha256 == hashlib.sha256(updated_bytes).hexdigest()


# ------------------------------------------------------------------ Stato

def test_cambia_stato(gf, fascicolo_base):
    f = gf.cambia_stato(fascicolo_base.id, StatoFascicolo.IN_CORSO, note="Prima udienza")
    assert f.stato == StatoFascicolo.IN_CORSO
    assert len(f.avanzamento) >= 1


def test_avanzamento_registrato(gf, fascicolo_base):
    gf.cambia_stato(fascicolo_base.id, StatoFascicolo.SOSPESO, note="Rinvio d'ufficio")
    f = gf.get(fascicolo_base.id)
    assert any("SOSPESO" in av.stato_nuovo for av in f.avanzamento)


def test_normalizza_stato_fascicolo_da_descrizione_portale():
    assert stato_fascicolo_da_descrizione_portale("PROCEDIMENTO DEFINITO") == StatoFascicolo.DEFINITO
    assert stato_fascicolo_da_descrizione_portale("pendente") == StatoFascicolo.IN_CORSO
    assert stato_fascicolo_da_descrizione_portale("RINVIATO") == StatoFascicolo.SOSPESO
    assert stato_fascicolo_da_descrizione_portale("ESTINTO") == StatoFascicolo.ARCHIVIATO


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


def test_aggiungi_documento_con_tag(gf, fascicolo_base):
    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="comparsa.pdf",
        tipo=TipoDocumento.COMPARSA,
        contenuto=b"comparsa di risposta",
        tags=["comparsa", "udienza", "comparsa"],
    )

    assert doc.tags == ["comparsa", "udienza", "comparsa"]
    fascicolo = gf.get(fascicolo_base.id)
    assert fascicolo.documenti[0].tags == ["comparsa", "udienza", "comparsa"]


def test_aggiorna_metadati_documento_normalizza_i_tag(gf, fascicolo_base):
    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="istanza.pdf",
        tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        contenuto=b"istanza",
    )

    aggiornato = gf.aggiorna_documento_metadati(
        fascicolo_base.id,
        doc.id,
        note="Istanza aggiornata",
        data_documento="2026-04-18",
        tags=["istanza", "udienza", "Istanza", "", "udienza"],
    )

    assert aggiornato.note == "Istanza aggiornata"
    assert aggiornato.data_documento == "2026-04-18"
    assert aggiornato.tags == ["istanza", "udienza"]


def test_rinomina_documento_aggiorna_nome_e_file(gf, fascicolo_base):
    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="atto_originale.pdf",
        tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        contenuto=b"%PDF-1.4 atto",
    )
    percorso_originale = gf.percorso_documento(fascicolo_base.id, doc.id)

    rinominato = gf.rinomina_documento(fascicolo_base.id, doc.id, "Ricorso introduttivo")

    assert rinominato.nome == "Ricorso introduttivo.pdf"
    assert not percorso_originale.exists()
    assert gf.percorso_documento(fascicolo_base.id, doc.id).exists()
    assert gf.get(fascicolo_base.id).documenti[0].nome == "Ricorso introduttivo.pdf"
    assert "iusentra:nome-personalizzato" in gf.get(fascicolo_base.id).documenti[0].tags


def test_rinomina_documento_non_cambia_estensione(gf, fascicolo_base):
    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="atto.pdf.p7m",
        tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        contenuto=b"firmato",
    )

    with pytest.raises(ValueError, match="estensione"):
        gf.rinomina_documento(fascicolo_base.id, doc.id, "atto.docx")


def test_rinomina_documento_lungo_preserva_estensione(gf, fascicolo_base):
    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="atto.pdf.p7m",
        tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        contenuto=b"firmato",
    )

    rinominato = gf.rinomina_documento(fascicolo_base.id, doc.id, f"{'memoria' * 40}.pdf.p7m")

    assert rinominato.nome.endswith(".pdf.p7m")
    assert len(rinominato.nome) <= 180


def test_rimuovi_documento(gf, fascicolo_base):
    doc = gf.aggiungi_documento(
        fascicolo_base.id, "da_eliminare.pdf",
        TipoDocumento.ALTRO, b"contenuto"
    )
    percorso = gf.percorso_documento(fascicolo_base.id, doc.id)
    gf.rimuovi_documento(fascicolo_base.id, doc.id, eliminato_da="Avv. Prova")
    assert percorso.exists()
    f = gf.get(fascicolo_base.id)
    assert len(f.documenti) == 0
    assert len(f.documenti_cestino) == 1
    assert f.documenti_cestino[0].id == doc.id
    assert f.documenti_cestino[0].eliminato_il
    assert f.documenti_cestino[0].eliminato_da == "Avv. Prova"

    ripristinato = gf.ripristina_documento(fascicolo_base.id, doc.id)
    assert ripristinato.id == doc.id
    assert ripristinato.eliminato_il == ""
    assert ripristinato.eliminato_da == ""
    assert percorso.exists()
    assert [item.id for item in gf.get(fascicolo_base.id).documenti] == [doc.id]
    assert gf.get(fascicolo_base.id).documenti_cestino == []

    gf.rimuovi_documento(fascicolo_base.id, doc.id)
    gf.elimina_documento_definitivamente(fascicolo_base.id, doc.id)
    assert not percorso.exists()
    assert gf.get(fascicolo_base.id).documenti_cestino == []


def test_eliminazione_definitiva_ripristina_il_cestino_se_il_file_non_si_cancella(
    gf, fascicolo_base, monkeypatch
):
    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        "file_bloccato.pdf",
        TipoDocumento.ALTRO,
        b"contenuto",
    )
    percorso = gf.percorso_documento(fascicolo_base.id, doc.id)
    gf.rimuovi_documento(fascicolo_base.id, doc.id)
    original_unlink = Path.unlink

    def unlink_bloccato(path, *args, **kwargs):
        if path == percorso:
            raise OSError("file in uso")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink_bloccato)

    with pytest.raises(OSError, match="file in uso"):
        gf.elimina_documento_definitivamente(fascicolo_base.id, doc.id)

    assert percorso.exists()
    assert [item.id for item in gf.get(fascicolo_base.id).documenti_cestino] == [doc.id]


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


def test_registra_import_documenti_portale_collega_documenti_senza_attivita(gf, fascicolo_base):
    doc1 = gf.aggiungi_documento(
        fascicolo_base.id,
        "sentenza.pdf",
        TipoDocumento.SENTENZA,
        b"sentenza",
    )
    doc2 = gf.aggiungi_documento(
        fascicolo_base.id,
        "verbale.pdf",
        TipoDocumento.VERBALE,
        b"verbale",
    )

    esito = gf.registra_import_documenti_portale(
        id_fasc=fascicolo_base.id,
        fonte="PolisWeb / PST",
        documenti_ids=[doc1.id, doc2.id],
        tipo_atto="Acquisizione documenti PolisWeb",
        note="Fascicolo ufficiale acquisito dal portale",
        registrato_da="admin",
        pec_destinatario="tribunale.milano@giustiziapec.it",
        nome_atto_principale=doc1.nome,
    )

    fascicolo = gf.get(fascicolo_base.id)
    assert esito.stato == "IMPORTATO_DA_PORTALE"
    assert len(fascicolo.depositi_pct) == 1
    assert fascicolo.depositi_pct[0].servizio_portale == "DocumentiFascicolo"
    assert fascicolo.documenti[0].id_deposito_pct == esito.id
    assert fascicolo.documenti[1].id_deposito_pct == esito.id
    assert not any(
        att.tipo == TipoAttivita.CONSULTAZIONE and att.id_deposito_pct == esito.id
        for att in fascicolo.attivita
    )


def test_sincronizza_deposito_portale_riusa_lotto_generico_e_compila_metadati(gf, fascicolo_base):
    doc1 = gf.aggiungi_documento(
        fascicolo_base.id,
        "SentenzaDefinitiva_33581101.pdf",
        TipoDocumento.SENTENZA,
        b"sentenza",
    )
    doc2 = gf.aggiungi_documento(
        fascicolo_base.id,
        "Relata_33581101.pdf",
        TipoDocumento.ALLEGATO,
        b"relata",
    )

    lotto = gf.registra_import_documenti_portale(
        id_fasc=fascicolo_base.id,
        fonte="PolisWeb / PST",
        documenti_ids=[doc1.id, doc2.id],
        tipo_atto="Documenti ufficiali PolisWeb",
        note="Lotto locale da catalogare",
        registrato_da="admin",
    )

    esito = gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PST",
        id_deposito_esterno="DEP-PORTALE-001",
        tipo_atto="Sentenza definitiva",
        data_deposito="2026-01-08",
        mittente="cancelleria@tribunale.palmi.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-001",
                "nome": "SentenzaDefinitiva_33581101.pdf",
                "tipo": "SentenzaDefinitiva",
                "data_deposito": "2026-01-08",
                "mittente": "cancelleria@tribunale.palmi.giustiziapec.it",
                "dimensione_bytes": 12000,
                "disponibile": True,
                "id_deposito": "DEP-PORTALE-001",
                "tipo_atto": "Sentenza definitiva",
            },
            {
                "id_documento": "DOC-002",
                "nome": "Relata_33581101.pdf",
                "tipo": "ALLEGATO",
                "data_deposito": "2026-01-08",
                "mittente": "cancelleria@tribunale.palmi.giustiziapec.it",
                "dimensione_bytes": 8000,
                "disponibile": True,
                "id_deposito": "DEP-PORTALE-001",
                "tipo_atto": "Sentenza definitiva",
            },
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    fascicolo = gf.get(fascicolo_base.id)
    assert fascicolo is not None
    assert len(fascicolo.depositi_pct) == 1
    assert esito.id == lotto.id
    assert fascicolo.depositi_pct[0].id_deposito_esterno == "DEP-PORTALE-001"
    assert len(fascicolo.depositi_pct[0].documenti_portale) == 2

    doc1_reload = next(item for item in fascicolo.documenti if item.id == doc1.id)
    doc2_reload = next(item for item in fascicolo.documenti if item.id == doc2.id)
    assert doc1_reload.id_deposito_pct == lotto.id
    assert doc1_reload.classificazione_portale == "SentenzaDefinitiva"
    assert doc1_reload.tipo_atto_portale == "Sentenza definitiva"
    assert doc1_reload.id_documento_portale == "DOC-001"
    assert doc2_reload.classificazione_portale == "ALLEGATO"
    assert doc2_reload.id_documento_portale == "DOC-002"


def test_sincronizza_deposito_portale_preserva_allegati_e_id_reperto(gf, fascicolo_base):
    esito = gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PST",
        id_deposito_esterno="DEP-CITAZIONE-001",
        tipo_atto="Citazione",
        data_deposito="2024-09-05",
        mittente="MONTAGNESE ROBERTO",
        documenti_portale=[
            {
                "id_documento": "DOC-PRIMARIO",
                "id_cat": "CAT-PRIMARIO",
                "nome": "Citazione Stilitano Montagnese.pdf",
                "tipo": "Citazione",
                "data_deposito": "2024-09-05",
                "mittente": "MONTAGNESE ROBERTO",
                "dimensione_bytes": 42000,
                "disponibile": True,
            },
            {
                "id_documento": "DOC-ALLEGATO-1",
                "id_cat": "CAT-ALLEGATO-1",
                "id_reperto": "REP-ALLEGATO-1",
                "id_documento_padre": "DOC-PRIMARIO",
                "parent_nome": "Citazione Stilitano Montagnese.pdf",
                "is_allegato": True,
                "nome": "PROCURA.PDF",
                "tipo": "Allegato",
                "data_deposito": "2024-09-05",
                "mittente": "MONTAGNESE ROBERTO",
                "dimensione_bytes": 12000,
                "disponibile": True,
            },
            {
                "id_reperto": "REP-ALLEGATO-1",
                "nome": "PROCURA.PDF",
                "tipo": "Allegato",
                "data_deposito": "2024-09-05",
                "is_allegato": True,
            },
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    assert len(esito.documenti_portale) == 2
    allegato = next(item for item in esito.documenti_portale if item["nome"] == "PROCURA.PDF")
    assert allegato["id_reperto"] == "REP-ALLEGATO-1"
    assert allegato["id_documento_padre"] == "DOC-PRIMARIO"
    assert allegato["parent_nome"] == "Citazione Stilitano Montagnese.pdf"
    assert allegato["is_allegato"] is True


def test_riconcilia_documenti_portale_ripara_match_ambiguo_e_normalizza_note(gf, fascicolo_base):
    dep_citazione = gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PST",
        id_deposito_esterno="DEP-CIT-001",
        tipo_atto="Citazione",
        data_deposito="2024-09-05",
        mittente="avv.rossi@example.pec.it",
        documenti_portale=[
            {
                "id_documento": "28139218",
                "id_cat": "28139218",
                "nome": "Citazione_28139218.pdf",
                "tipo": "Citazione",
                "data_deposito": "2024-09-05",
                "mittente": "avv.rossi@example.pec.it",
                "dimensione_bytes": 470000,
                "disponibile": True,
                "id_deposito": "DEP-CIT-001",
                "tipo_atto": "Citazione",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )
    dep_verbale = gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PST",
        id_deposito_esterno="DEP-VERB-001",
        tipo_atto="Verbale udienza",
        data_deposito="2025-11-11",
        mittente="cancelleria@tribunale.palmi.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "32970605",
                "id_cat": "32970605",
                "nome": "VerbaleUdienza_32970605.pdf",
                "tipo": "VerbaleUdienza",
                "data_deposito": "2025-11-11",
                "mittente": "cancelleria@tribunale.palmi.giustiziapec.it",
                "dimensione_bytes": 104000,
                "disponibile": True,
                "id_deposito": "DEP-VERB-001",
                "tipo_atto": "Verbale udienza",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )
    dep_sentenza = gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PST",
        id_deposito_esterno="DEP-SENT-001",
        tipo_atto="Sentenza definitiva",
        data_deposito="2026-01-08",
        mittente="cancelleria@tribunale.palmi.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "33581101",
                "id_cat": "33581101",
                "nome": "SentenzaDefinitiva_33581101.pdf",
                "tipo": "SentenzaDefinitiva",
                "data_deposito": "2026-01-08",
                "mittente": "cancelleria@tribunale.palmi.giustiziapec.it",
                "dimensione_bytes": 293000,
                "disponibile": True,
                "id_deposito": "DEP-SENT-001",
                "tipo_atto": "Sentenza definitiva",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    doc_citazione = gf.aggiungi_documento(
        fascicolo_base.id,
        "Citazione_28139218.pdf",
        TipoDocumento.CITAZIONE,
        b"citazione",
        note="Importato da PolisWeb / PST il 2026-04-24 | Origine: pst:JPW_SICID:28139218 | Tipo atto portale: Citazione",
        data_documento="2026-04-24",
        fonte_documento="PORTALE_TELEMATICO",
        nome_originale="pst:JPW_SICID:28139218",
        nome_portale="Citazione_28139218.pdf",
        classificazione_portale="Citazione",
        tipo_atto_portale="Citazione",
        id_documento_portale="28139218",
        id_cat_portale="28139218",
        id_deposito_pct=dep_citazione.id,
    )
    doc_verbale = gf.aggiungi_documento(
        fascicolo_base.id,
        "VerbaleUdienza_32970605.pdf",
        TipoDocumento.VERBALE,
        b"verbale",
        note="Importato da PolisWeb / PST il 2026-04-24 | Origine: pst:JPW_SICID:32970605 | Tipo atto portale: VerbaleUdienza",
        data_documento="2026-04-24",
        fonte_documento="PORTALE_TELEMATICO",
        nome_originale="pst:JPW_SICID:32970605",
        nome_portale="VerbaleUdienza_32970605.pdf",
        classificazione_portale="VerbaleUdienza",
        tipo_atto_portale="Verbale udienza",
        id_documento_portale="32970605",
        id_cat_portale="32970605",
        id_deposito_pct=dep_verbale.id,
    )
    doc_sentenza = gf.aggiungi_documento(
        fascicolo_base.id,
        "SentenzaDefinitiva_33581101.pdf",
        TipoDocumento.SENTENZA,
        b"sentenza",
        note="Importato da PolisWeb / PST il 2026-04-24 | Origine: SentenzaDefinitiva_33581101.pdf.p7m | Tipo atto portale: SentenzaDefinitiva",
        data_documento="2026-04-24",
        fonte_documento="PORTALE_TELEMATICO",
        nome_originale="SentenzaDefinitiva_33581101.pdf.p7m",
        nome_portale="SentenzaDefinitiva_33581101.pdf",
        classificazione_portale="SentenzaDefinitiva",
        tipo_atto_portale="Sentenza definitiva",
        id_documento_portale="33581101",
        id_cat_portale="33581101",
        id_deposito_pct=dep_sentenza.id,
    )

    # Riproduce due righe storiche corrotte senza passare dalla deduplicazione
    # corrente, che impedisce correttamente di creare nuovi duplicati portale.
    for documento in (doc_verbale, doc_sentenza):
        documento.nome = "Citazione_28139218.pdf"
        documento.nome_portale = "Citazione_28139218.pdf"
        documento.classificazione_portale = "Citazione"
        documento.tipo_atto_portale = "Citazione"
        documento.id_documento_portale = "28139218"
        documento.id_cat_portale = "28139218"
        documento.id_deposito_pct = dep_citazione.id
    gf._salva()

    esito = gf.riconcilia_documenti_portale(fascicolo_base.id)

    assert esito["documenti_allineati"] == 3
    assert esito["depositi_toccati"] == 3

    fascicolo_reload = gf.get(fascicolo_base.id)
    assert fascicolo_reload is not None
    by_id = {doc.id: doc for doc in fascicolo_reload.documenti}

    doc_verbale_reload = by_id[doc_verbale.id]
    assert doc_verbale_reload.id_deposito_pct == dep_verbale.id
    assert doc_verbale_reload.nome == "VerbaleUdienza_32970605.pdf"
    assert doc_verbale_reload.classificazione_portale == "VerbaleUdienza"
    assert doc_verbale_reload.tipo_atto_portale == "Verbale udienza"
    assert doc_verbale_reload.data_documento == "2025-11-11"
    assert "Documenti fascicolo" in doc_verbale_reload.tags
    assert "VerbaleUdienza" in doc_verbale_reload.tags
    assert "Cancelleria" in doc_verbale_reload.tags
    assert "24/04/2026" in doc_verbale_reload.note

    doc_sentenza_reload = by_id[doc_sentenza.id]
    assert doc_sentenza_reload.id_deposito_pct == dep_sentenza.id
    assert doc_sentenza_reload.nome == "SentenzaDefinitiva_33581101.pdf"
    assert doc_sentenza_reload.classificazione_portale == "SentenzaDefinitiva"
    assert doc_sentenza_reload.tipo_atto_portale == "Sentenza definitiva"
    assert doc_sentenza_reload.data_documento == "2026-01-08"

    doc_citazione_reload = by_id[doc_citazione.id]
    assert doc_citazione_reload.id_deposito_pct == dep_citazione.id
    assert "24/04/2026" in doc_citazione_reload.note


def test_normalizza_stato_deposito_pct_migra_legacy():
    assert normalizza_stato_deposito_pct("accettato") == "ACCETTATO_PEC"
    assert normalizza_stato_deposito_pct("RIFIUTATO") == "RIFIUTATO_CANCELLERIA"
    assert normalizza_stato_deposito_pct("importato_da_pst") == "IMPORTATO_DA_PST"


def test_normalizza_stato_deposito_pct_rifiuta_valori_non_validi():
    with pytest.raises(ValueError, match="Stato deposito non valido"):
        normalizza_stato_deposito_pct("CHIUSO")


def test_normalizza_esito_controlli_accetta_solo_valori_canonici():
    assert _normalizza_esito_controlli("warn") == "WARN"
    assert _normalizza_esito_controlli("") == ""
    with pytest.raises(ValueError, match="Esito controlli non valido"):
        _normalizza_esito_controlli("KO")


def test_aggiungi_esito_deposito_normalizza_controlli(gf, fascicolo_base):
    esito = gf.aggiungi_esito_deposito(
        fascicolo_base.id,
        tipo_atto="MEMORIA",
        pec_destinatario="tribunale.milano@giustiziapec.it",
        stato="accettato",
        esito_controlli="warn",
    )

    assert esito.stato == "ACCETTATO_PEC"
    assert esito.esito_controlli == "WARN"


def test_caricamento_fascicoli_migra_stati_legacy_su_disco(tmp_path):
    db_path = tmp_path / "fascicoli.json"
    raw = {
        "FASC1234": {
            "id": "FASC1234",
            "numero": "2026/001",
            "titolo": "Migrazione depositi legacy",
            "tipo": "CIVILE",
            "stato": "APERTO",
            "documenti": [],
            "attivita": [],
            "avanzamento": [],
            "depositi_pct": [
                {
                    "id": "DEP00001",
                    "timestamp": "2026-04-04T10:00:00",
                    "stato": "ACCETTATO",
                    "tipo_atto": "MEMORIA",
                    "pec_destinatario": "tribunale.milano@giustiziapec.it",
                    "esito_controlli": "warn",
                }
            ],
        }
    }
    db_path.write_text(__import__("json").dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    gf = GestioneFascicoli(
        db_path=str(db_path),
        documents_dir=str(tmp_path / "documenti"),
        archive_dir=str(tmp_path / "archivio"),
    )

    fascicolo = gf.get("FASC1234")
    assert fascicolo is not None
    assert fascicolo.depositi_pct[0].stato == "ACCETTATO_PEC"
    assert fascicolo.depositi_pct[0].esito_controlli == "WARN"

    persisted = __import__("json").loads(db_path.read_text(encoding="utf-8"))
    assert persisted["FASC1234"]["depositi_pct"][0]["stato"] == "ACCETTATO_PEC"
    assert persisted["FASC1234"]["depositi_pct"][0]["esito_controlli"] == "WARN"


def test_collega_documenti_a_deposito_portale_aggancia_file_locali_al_deposito_ufficiale(gf, fascicolo_base):
    dep = gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-001",
        tipo_atto="Sentenza",
        data_deposito="2026-03-29",
        mittente="cancelleria@tribunale.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-001",
                "nome": "sentenza definitiva.pdf",
                "tipo": "PROVVEDIMENTO",
                "data_deposito": "2026-03-29",
                "mittente": "cancelleria@tribunale.giustiziapec.it",
                "dimensione_bytes": 20480,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-001",
                "tipo_atto": "Sentenza",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )
    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        "sentenza definitiva.pdf",
        TipoDocumento.SENTENZA,
        b"sentenza",
    )

    gf.collega_documenti_a_deposito_portale(
        fascicolo_base.id,
        dep.id,
        [doc.id],
        note="File ufficiale acquisito dal fascicolo locale",
        registrato_da="admin",
    )

    fascicolo = gf.get(fascicolo_base.id)
    deposito = fascicolo.depositi_pct[0]
    assert deposito.documenti_ids == [doc.id]
    assert deposito.servizio_portale == "DocumentiFascicolo"
    assert "File ufficiale acquisito dal fascicolo locale" in deposito.note
    assert fascicolo.documenti[0].id_deposito_pct == dep.id
    assert fascicolo.documenti[0].classificazione_portale == "PROVVEDIMENTO"
    assert fascicolo.documenti[0].tipo_atto_portale == "Sentenza"
    assert fascicolo.documenti[0].id_documento_portale == "DOC-001"
    assert fascicolo.documenti[0].mittente_portale == "cancelleria@tribunale.giustiziapec.it"
    assert fascicolo.documenti[0].fonte_documento == "PORTALE_TELEMATICO"


def test_collega_documenti_portale_deduplica_ids_e_mantiene_classificazione(gf, fascicolo_base):
    dep = gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="DEP-DECRETO-35052610",
        tipo_atto="Decreto",
        data_deposito="2026-05-07",
        mittente="RUSCIO EMANUELA",
        documenti_portale=[
            {
                "id_documento": "35052610",
                "nome": "Decreto_35052610.pdf",
                "tipo": "Decreto",
                "data_deposito": "2026-05-07",
                "mittente": "RUSCIO EMANUELA",
                "dimensione_bytes": 12000,
                "disponibile": True,
                "id_deposito": "DEP-DECRETO-35052610",
                "tipo_atto": "Decreto",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )
    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        "Decreto_35052610.pdf",
        TipoDocumento.DECRETO,
        b"decreto",
        fonte_documento="PORTALE_TELEMATICO",
        nome_originale="pst:JPW_SICID:35052610",
    )

    gf.collega_documenti_a_deposito_portale(
        fascicolo_base.id,
        dep.id,
        [doc.id, doc.id, doc.id],
        note="File ufficiale acquisito dal fascicolo PST.",
        registrato_da="admin",
    )

    fascicolo = gf.get(fascicolo_base.id)
    deposito = fascicolo.depositi_pct[0]
    documento = fascicolo.documenti[0]
    assert deposito.documenti_ids == [doc.id]
    assert documento.id_deposito_pct == dep.id
    assert documento.classificazione_portale == "Decreto"
    assert documento.tipo_atto_portale == "Decreto"
    assert documento.id_documento_portale == "35052610"
    assert not any(
        att.tipo == TipoAttivita.CONSULTAZIONE and att.id_deposito_pct == dep.id
        for att in fascicolo.attivita
    )


def test_sincronizza_deposito_portale_registra_metadati_senza_attivita_documenti(gf, fascicolo_base):
    esito = gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-001",
        tipo_atto="Memoria conclusionale",
        data_deposito="2026-03-29",
        mittente="avv.rossi@pec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-001",
                "nome": "memoria_conclusionale.pdf.p7m",
                "tipo": "ATTO",
                "data_deposito": "2026-03-29",
                "mittente": "avv.rossi@pec.it",
                "dimensione_bytes": 20480,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-001",
                "tipo_atto": "Memoria conclusionale",
            },
            {
                "id_documento": "DOC-002",
                "nome": "nota_spese.pdf.p7m",
                "tipo": "ALLEGATO",
                "data_deposito": "2026-03-29",
                "mittente": "avv.rossi@pec.it",
                "dimensione_bytes": 8192,
                "disponibile": "true",
                "id_deposito": "BUSTA-PST-001",
                "tipo_atto": "Memoria conclusionale",
            },
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    fascicolo = gf.get(fascicolo_base.id)
    assert esito.stato == "IMPORTATO_DA_PST"
    assert esito.id_deposito_esterno == "BUSTA-PST-001"
    assert esito.fonte_portale == "PolisWeb / PST"
    assert esito.servizio_portale == "DocumentiFascicolo"
    assert len(esito.documenti_portale) == 2
    assert esito.documenti_portale[1]["disponibile"] is True
    assert len(fascicolo.depositi_pct) == 1
    assert not any(
        att.id_deposito_pct == esito.id and att.tipo == TipoAttivita.DEPOSITO_ATTI
        for att in fascicolo.attivita
    )


def test_sincronizza_deposito_portale_aggiorna_senza_duplicare(gf, fascicolo_base):
    gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-001",
        tipo_atto="Sentenza",
        data_deposito="2026-03-29",
        mittente="cancelleria@tribunale.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-001",
                "nome": "sentenza.pdf",
                "tipo": "PROVVEDIMENTO",
                "data_deposito": "2026-03-29",
                "mittente": "cancelleria@tribunale.giustiziapec.it",
                "dimensione_bytes": 12000,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-001",
                "tipo_atto": "Sentenza",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    esito_aggiornato = gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-001",
        tipo_atto="Sentenza definitiva",
        data_deposito="2026-03-30",
        mittente="cancelleria@tribunale.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-001",
                "nome": "sentenza.pdf",
                "tipo": "PROVVEDIMENTO",
                "data_deposito": "2026-03-29",
                "mittente": "cancelleria@tribunale.giustiziapec.it",
                "dimensione_bytes": 12000,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-001",
                "tipo_atto": "Sentenza",
            },
            {
                "id_documento": "DOC-002",
                "nome": "dispositivo.pdf",
                "tipo": "ALLEGATO",
                "data_deposito": "2026-03-30",
                "mittente": "cancelleria@tribunale.giustiziapec.it",
                "dimensione_bytes": 8000,
                "disponibile": False,
                "id_deposito": "BUSTA-PST-001",
                "tipo_atto": "Sentenza definitiva",
            },
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    fascicolo = gf.get(fascicolo_base.id)
    assert len(fascicolo.depositi_pct) == 1
    assert esito_aggiornato.tipo_atto == "Sentenza definitiva"
    assert esito_aggiornato.servizio_portale == "DocumentiFascicolo"
    assert len(esito_aggiornato.documenti_portale) == 2
    assert esito_aggiornato.documenti_portale[0]["nome"] in {"dispositivo.pdf", "sentenza.pdf"}
    assert len([att for att in fascicolo.attivita if att.id_deposito_pct == esito_aggiornato.id]) == 0


def test_riconcilia_documenti_portale_allinea_nome_e_metadati(gf, fascicolo_base):
    gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-002",
        tipo_atto="Verbale di udienza",
        data_deposito="2026-04-06",
        mittente="cancelleria@tribunale.palmi.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-VERB-01",
                "nome": "VerbaleUdienza_33393309.pdf.p7m",
                "tipo": "VERBALE",
                "data_deposito": "2026-04-06",
                "mittente": "cancelleria@tribunale.palmi.giustiziapec.it",
                "dimensione_bytes": 20480,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-002",
                "tipo_atto": "Verbale di udienza",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        "verbaleudienza_33393309.pdf.p7m",
        TipoDocumento.VERBALE,
        b"verbale firmato",
    )

    report = gf.riconcilia_documenti_portale(fascicolo_base.id)
    fascicolo = gf.get(fascicolo_base.id)
    aggiornato = next(item for item in fascicolo.documenti if item.id == doc.id)

    assert report["documenti_allineati"] == 1
    assert aggiornato.nome == "VerbaleUdienza_33393309.pdf.p7m"
    assert aggiornato.nome_originale == "verbaleudienza_33393309.pdf.p7m"
    assert aggiornato.nome_portale == "VerbaleUdienza_33393309.pdf.p7m"
    assert aggiornato.classificazione_portale == "VERBALE"
    assert aggiornato.tipo_atto_portale == "Verbale di udienza"
    assert aggiornato.id_documento_portale == "DOC-VERB-01"
    assert aggiornato.fonte_documento == "PORTALE_TELEMATICO"


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


def test_aggiungi_attivita_persistendo_contenuto_email(gf, fascicolo_base):
    att = gf.aggiungi_attivita(
        fascicolo_base.id,
        tipo=TipoAttivita.COMUNICAZIONE_CANCELLERIA,
        data=date.today().isoformat(),
        titolo="PEC: ACCETTAZIONE DEPOSITO",
        descrizione="Da: cancelleria@example.pec.it",
        email_mittente="cancelleria@example.pec.it",
        email_oggetto="ACCETTAZIONE DEPOSITO RG 1234/2024",
        email_uid_imap="999",
        email_testo="Corpo completo della PEC di cancelleria",
    )
    gf_reload = GestioneFascicoli(
        db_path=str(gf.db_path),
        documents_dir=str(gf.documents_dir),
        archive_dir=str(gf.archive_dir),
    )
    fascicolo = gf_reload.get(fascicolo_base.id)
    salvata = next(a for a in fascicolo.attivita if a.id == att.id)
    assert salvata.email_mittente == "cancelleria@example.pec.it"
    assert salvata.email_oggetto == "ACCETTAZIONE DEPOSITO RG 1234/2024"
    assert salvata.email_uid_imap == "999"
    assert salvata.email_testo == "Corpo completo della PEC di cancelleria"


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


def test_fascicolo_serializza_metadati_sync_portale(gf, fascicolo_base):
    aggiornato = gf.aggiorna(
        fascicolo_base.id,
        source="PST",
        source_external_id="0800570094:1025:2024:CIVILE",
        codice_ufficio_portale="0800570094",
        id_fascicolo_portale="SIECIC-172944",
        tipo_registro="ESIM",
        registro_portale="ESIM",
        servizio_pst="JPW_SIECIC",
        sub_procedimento="CONTENZIOSO",
        id_dfa="DFA-ESIM-3441",
        ruolo_polisweb="CUS",
        last_sync_at="2026-04-06T10:45:00",
        sync_status="SINCRONIZZATO",
        import_log_id="PST-20260406104500-ABC123",
        has_conflicts=True,
        document_sync_enabled=True,
        events_sync_enabled=True,
    )

    data = aggiornato.to_dict()
    ripristinato = Fascicolo.from_dict(data)

    assert ripristinato.source == "PST"
    assert ripristinato.source_external_id == "0800570094:1025:2024:CIVILE"
    assert ripristinato.codice_ufficio_portale == "0800570094"
    assert ripristinato.id_fascicolo_portale == "SIECIC-172944"
    assert ripristinato.tipo_registro == "ESIM"
    assert ripristinato.registro_portale == "ESIM"
    assert ripristinato.servizio_pst == "JPW_SIECIC"
    assert ripristinato.sub_procedimento == "CONTENZIOSO"
    assert ripristinato.id_dfa == "DFA-ESIM-3441"
    assert ripristinato.ruolo_polisweb == "CUS"
    assert ripristinato.last_sync_at == "2026-04-06T10:45:00"
    assert ripristinato.sync_status == "SINCRONIZZATO"
    assert ripristinato.import_log_id == "PST-20260406104500-ABC123"
    assert ripristinato.has_conflicts is True
    assert ripristinato.document_sync_enabled is True
    assert ripristinato.events_sync_enabled is True
