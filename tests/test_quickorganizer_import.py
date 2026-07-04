from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from werkzeug.datastructures import FileStorage

import web.services.quickorganizer_import as quickorganizer_import
from pct.agenda import Agenda, TipoAppuntamento
from pct.clienti import GestioneClienti
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.soggetti import GestioneSoggetti
from pct.storage import StudioDB
from web.services.quickorganizer_import import (
    QuickOrganizerImportError,
    analyze_quickorganizer_package,
    audit_quickorganizer_import,
    auto_prepare_status,
    begin_auto_prepare_session,
    begin_chunked_upload,
    complete_auto_prepare_upload,
    complete_chunked_upload,
    import_quickorganizer_package,
    load_staged_package,
    load_quickorganizer_package,
    receive_auto_prepare_chunk,
    receive_chunked_upload,
    start_auto_prepare_upload,
    stage_referenced_package,
    update_auto_prepare_status,
)


def _write_package(path: Path, *, include_atto: bool = True, include_email: bool = True) -> Path:
    payload = {
        "format": "iusentra.quickorganizer.v1",
        "tables": {
            "PRATICHE": [
                {
                    "NUMEROPRATICA": 101,
                    "PRATICA": "Rossi Mario / Bianchi Luigi",
                    "OGGETTO_PRATICA": "Recupero credito",
                    "TitolareID": 1,
                    "TitolareName": "Rossi Mario",
                    "AUT_GIUDIZ": "Tribunale di Milano",
                    "RUOLO_GEN": "1234",
                    "ANNO_RUOLO_GEN": 2025,
                    "VALORE": "1200,50",
                    "DATA_APE": "10/01/2025",
                    "Stato_Pratica": "In corso",
                }
            ],
            "NOMI": [
                {"NUM_NOM": 1, "CONTROLLO": "CLI", "NOME": "Mario", "COGNOME": "Rossi", "EMAIL": "mario.rossi@example.it"},
                {"NUM_NOM": 2, "CONTROLLO": "CTP", "NOME": "Luigi", "COGNOME": "Bianchi", "EMAIL": "luigi.bianchi@example.it"},
            ],
            "TAVOLA": [
                {"NUMEROPRATICA": 101, "NUM_NOM": 1},
                {"NUMEROPRATICA": 101, "NUM_NOM": 2},
            ],
            "TESTI": [
                {
                    "NUMEROPRATICA": 101,
                    "Counter": 77,
                    "NOME_DOS": "scansione-da-pdf-0001.pdf",
                    "NOME_ATTO": "Ricorso introduttivo da tabella",
                    "DATA_ATTO": "2025-01-12",
                }
            ],
            "EMAILS": [
                {
                    "NumeroPratica": 101,
                    "Email_ID": 88,
                    "NOME_DOS": "MSG000088.eml",
                    "Subject": "Invio documenti da tabella",
                    "Data": "2025-01-13",
                    "Mittente": "cliente@example.it",
                }
            ],
            "AGENDA": [
                {
                    "NumeroPratica": 101,
                    "TaskID": 99,
                    "Subject": "Udienza comparizione",
                    "StartDateTime": "2025-02-20T09:30:00",
                    "EndDateTime": "2025-02-20T10:15:00",
                    "Location": "Tribunale di Milano",
                    "Description": "Prima comparizione parti",
                }
            ],
        },
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("quickorganizer-export.json", json.dumps(payload, ensure_ascii=False))
        if include_atto:
            archive.writestr("ATTI/scansione-da-pdf-0001.pdf", b"%PDF-1.4\ncontenuto atto")
        if include_email:
            archive.writestr("EMAILS/MSG000088.eml", b"Subject: Invio documenti\n\nTesto")
    return path


def _write_package_without_titolare(path: Path) -> Path:
    payload = {
        "format": "iusentra.quickorganizer.v1",
        "tables": {
            "PRATICHE": [
                {
                    "NUMEROPRATICA": 202,
                    "PRATICA": "Verdi Anna / Ministero",
                    "OGGETTO_PRATICA": "Retribuzione",
                    "DATA_APE": "2025-01-10",
                    "Stato_Pratica": "In corso",
                },
                {
                    "NUMEROPRATICA": 203,
                    "PRATICA": "Pratica senza parti",
                    "OGGETTO_PRATICA": "Accertamento",
                    "DATA_APE": "2025-02-10",
                    "Stato_Pratica": "In corso",
                },
            ],
            "NOMI": [
                {"NUM_NOM": 10, "CONTROLLO": "CLI", "NOME": "Anna", "COGNOME": "Verdi", "EMAIL": "anna@example.it"},
                {"NUM_NOM": 11, "CONTROLLO": "CTP", "NOME": "Ministero"},
            ],
            "TAVOLA": [
                {"NUMEROPRATICA": 202, "NUM_NOM": 10},
                {"NUMEROPRATICA": 202, "NUM_NOM": 11},
            ],
            "TESTI": [],
            "EMAILS": [],
            "AGENDA": [],
        },
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("quickorganizer-export.json", json.dumps(payload, ensure_ascii=False))
    return path


def _write_package_persona_giuridica_cf_numerico(path: Path) -> Path:
    payload = {
        "format": "iusentra.quickorganizer.v1",
        "tables": {
            "PRATICHE": [
                {
                    "NUMEROPRATICA": 259,
                    "PRATICA": "Associazione / Ministero",
                    "OGGETTO_PRATICA": "Riconoscimento",
                    "DATA_APE": "2025-03-10",
                    "Stato_Pratica": "In corso",
                }
            ],
            "NOMI": [
                {
                    "NUM_NOM": 195,
                    "CONTROLLO": "CLI",
                    "NOME": "",
                    "COGNOME": "Associazione Italiana Maestri Cattolici",
                    "CODICE_FISCALE": "92043820791",
                    "PARTITA_IVA": "03905310797",
                    "NaturaGiuridica": "ASS",
                }
            ],
            "TAVOLA": [{"NUMEROPRATICA": 259, "NUM_NOM": 195}],
            "TESTI": [],
            "EMAILS": [],
            "AGENDA": [],
        },
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("quickorganizer-export.json", json.dumps(payload, ensure_ascii=False))
    return path


def _write_files_only_package(path: Path) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("ATTI/ricorso.pdf", b"%PDF-1.4\ncontenuto atto")
        archive.writestr("EMAILS/messaggio.eml", b"Subject: Invio documenti\n\nTesto")
    return path


def _write_mdb_package(path: Path) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("QuickOrganizer.mdb", b"non e un database Access reale")
        archive.writestr("ATTI/ricorso.pdf", b"%PDF-1.4\ncontenuto atto")
        archive.writestr("EMAILS/messaggio.eml", b"Subject: Invio documenti\n\nTesto")
    return path


def _repositories(tmp_path: Path):
    fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
    )
    clienti = GestioneClienti(db_path=str(tmp_path / "clienti" / "anagrafica.json"))
    soggetti = GestioneSoggetti(
        str(tmp_path / "soggetti" / "anagrafica.json"),
        str(tmp_path / "soggetti" / "parti.json"),
    )
    return fascicoli, clienti, soggetti


def _agenda_repository(tmp_path: Path):
    return Agenda(db_path=str(tmp_path / "agenda" / "appuntamenti.json"))


def _sql_repositories(tmp_path: Path):
    studio_db = StudioDB.get(str(tmp_path / "tenant" / "studio.db"))
    fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "tenant" / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "tenant" / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "tenant" / "fascicoli" / "archivio"),
        studio_db=studio_db,
    )
    clienti = GestioneClienti(
        db_path=str(tmp_path / "tenant" / "clienti" / "anagrafica.json"),
        studio_db=studio_db,
    )
    soggetti = GestioneSoggetti(
        str(tmp_path / "tenant" / "soggetti" / "anagrafica.json"),
        str(tmp_path / "tenant" / "soggetti" / "parti.json"),
        studio_db=studio_db,
    )
    return studio_db, fascicoli, clienti, soggetti


def test_import_studio_telematico_legge_documenti_da_atti_ed_emails(tmp_path: Path):
    package = load_quickorganizer_package(_write_package(tmp_path / "studio-telematico.zip"))
    analysis = analyze_quickorganizer_package(package)
    fascicoli, clienti, soggetti = _repositories(tmp_path)

    result = import_quickorganizer_package(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
        actor="Operatore Test",
    )

    fascicolo = fascicoli.tutti(archiviati=True)[0]
    parti = soggetti.parti_fascicolo(fascicolo.id)
    assert analysis["canImportComplete"] is True
    assert result["summary"]["mattersCreated"] == 1
    assert result["summary"]["clientsCreated"] == 1
    assert result["summary"]["subjectsCreated"] == 2
    assert result["summary"]["documentsImported"] == 1
    assert result["summary"]["emailsImported"] == 1
    assert result["summary"]["activitiesImported"] == 1
    audit = audit_quickorganizer_import(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
    )
    assert audit["ok"] is True
    assert audit["expected"] == audit["found"]
    assert audit["expected"]["clients"] == 1
    assert fascicolo.source_external_id == "quickorganizer:101"
    assert len(fascicolo.documenti) == 2
    documenti_by_originale = {doc.nome_originale: doc for doc in fascicolo.documenti}
    atto = documenti_by_originale["scansione-da-pdf-0001.pdf"]
    email = documenti_by_originale["MSG000088.eml"]
    assert atto.nome == "Ricorso introduttivo da tabella.pdf"
    assert atto.nome_portale == "Ricorso introduttivo da tabella.pdf"
    assert atto.tipo_atto_portale == "Ricorso introduttivo da tabella.pdf"
    assert Path(atto.percorso).name == "scansione-da-pdf-0001.pdf"
    assert email.nome == "Invio documenti da tabella.eml"
    assert email.nome_portale == "Invio documenti da tabella.eml"
    assert email.tipo_atto_portale == "Invio documenti da tabella.eml"
    assert Path(email.percorso).name == "MSG000088.eml"
    assert len(parti) == 2
    cliente = clienti.tutti()[0]
    assert fascicolo.id_cliente == cliente.id
    assert fascicolo.nome_cliente == "Rossi Mario"
    assert cliente.nome == "Mario"
    assert cliente.cognome == "Rossi"
    assert cliente.recapiti.email == "mario.rossi@example.it"
    soggetti_by_name = {(s.cognome, s.nome): s for s in soggetti.tutti()}
    assert set(soggetti_by_name) == {("Rossi", "Mario"), ("Bianchi", "Luigi")}
    ruoli = {(soggetto.cognome, soggetto.nome): parte.ruolo.value for parte, soggetto in parti}
    assert ruoli == {("Rossi", "Mario"): "ASSISTITO", ("Bianchi", "Luigi"): "CONTROPARTE"}

    second = import_quickorganizer_package(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
        actor="Operatore Test",
    )

    assert second["summary"]["mattersUpdated"] == 1
    assert second["summary"]["clientsCreated"] == 0
    assert second["summary"]["subjectsCreated"] == 0
    assert second["summary"]["duplicatesSkipped"] >= 3
    assert len(fascicoli.tutti(archiviati=True)) == 1
    assert len(clienti.tutti()) == 1
    assert len(soggetti.tutti()) == 2


def test_import_studio_telematico_reimport_riallinea_nomi_documenti_esistenti(tmp_path: Path):
    package = load_quickorganizer_package(_write_package(tmp_path / "studio-telematico.zip"))
    partial_package = load_quickorganizer_package(
        _write_package(
            tmp_path / "studio-telematico-solo-dati.zip",
            include_atto=False,
            include_email=False,
        )
    )
    fascicoli, clienti, soggetti = _repositories(tmp_path)
    import_quickorganizer_package(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
        actor="Operatore Test",
    )
    fascicolo = fascicoli.tutti(archiviati=True)[0]
    for doc in fascicolo.documenti:
        if doc.nome_originale == "scansione-da-pdf-0001.pdf":
            doc.nome = "scansione-da-pdf-0001.pdf"
            doc.nome_portale = "scansione-da-pdf-0001.pdf"
            doc.classificazione_portale = "QuickOrganizer"
            doc.tags = ["quickorganizer"]
        if doc.nome_originale == "MSG000088.eml":
            doc.nome = "MSG000088.eml"
            doc.nome_portale = "MSG000088.eml"
            doc.classificazione_portale = "QuickOrganizer"
            doc.tags = ["quickorganizer"]
    fascicoli._salva()

    result = import_quickorganizer_package(
        partial_package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
        actor="Operatore Test",
        allow_partial=True,
    )
    fascicoli, clienti, soggetti = _repositories(tmp_path)
    audit = audit_quickorganizer_import(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
    )
    updated = fascicoli.tutti(archiviati=True)[0]
    docs = {doc.nome_originale: doc for doc in updated.documenti}

    assert result["summary"]["documentsMetadataRepaired"] == 1
    assert result["summary"]["emailsMetadataRepaired"] == 1
    assert docs["scansione-da-pdf-0001.pdf"].nome == "Ricorso introduttivo da tabella.pdf"
    assert docs["scansione-da-pdf-0001.pdf"].nome_portale == "Ricorso introduttivo da tabella.pdf"
    assert docs["scansione-da-pdf-0001.pdf"].tipo_atto_portale == "Ricorso introduttivo da tabella.pdf"
    assert docs["scansione-da-pdf-0001.pdf"].classificazione_portale == "Gestionale precedente"
    assert "import-pratiche" in docs["scansione-da-pdf-0001.pdf"].tags
    assert docs["MSG000088.eml"].nome == "Invio documenti da tabella.eml"
    assert docs["MSG000088.eml"].nome_portale == "Invio documenti da tabella.eml"
    assert docs["MSG000088.eml"].tipo_atto_portale == "Invio documenti da tabella.eml"
    assert audit["ok"] is True


def test_import_studio_telematico_crea_contesto_agenda_ed_economico(tmp_path: Path):
    package = load_quickorganizer_package(_write_package(tmp_path / "studio-telematico.zip"))
    fascicoli, clienti, soggetti = _repositories(tmp_path)
    agenda = _agenda_repository(tmp_path)

    result = import_quickorganizer_package(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
        agenda_repo=agenda,
        actor="Operatore Test",
    )
    fascicolo = fascicoli.tutti(archiviati=True)[0]
    appuntamenti = agenda.tutti()
    audit = audit_quickorganizer_import(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
        agenda_repo=agenda,
    )

    assert result["summary"]["appointmentsImported"] == 1
    assert result["summary"]["economicContextsPrepared"] == 1
    assert result["summary"]["sourceContextsPrepared"] == 1
    assert fascicolo.valore_causa == pytest.approx(1200.5)
    assert fascicolo.data_prima_udienza == "2025-02-20"
    assert fascicolo.data_prossima_udienza == ""
    assert fascicolo.events_sync_enabled is True
    assert fascicolo.source_snapshot["portale"] == "Import pratiche"
    assert fascicolo.source_snapshot["counts"]["documenti"] == 2
    assert fascicolo.source_snapshot["counts"]["udienze"] == 1
    assert fascicolo.pagamenti["contesto_economico"]["source"] == "import_pratiche"
    assert fascicolo.pagamenti["contesto_economico"]["valore_controversia"] == pytest.approx(1200.5)
    assert fascicolo.pagamenti["contributo_unificato"]["status"] == "da_registrare"
    assert fascicolo.pagamenti["parcella"]["status"] == "da_emettere"
    assert len(appuntamenti) == 1
    assert appuntamenti[0].tipo == TipoAppuntamento.UDIENZA
    assert appuntamenti[0].cliente == "Rossi Mario"
    assert appuntamenti[0].durata_minuti == 45
    assert "RG 1234/2025" in appuntamenti[0].procedimento
    assert "quickorganizer:101" in appuntamenti[0].procedimento
    assert audit["ok"] is True
    assert audit["expected"] == audit["found"]


def test_import_studio_telematico_sqlite_scrive_tabelle_core_con_json_solo_mirror(tmp_path: Path):
    package = load_quickorganizer_package(_write_package(tmp_path / "studio-telematico.zip"))
    studio_db, fascicoli, clienti, soggetti = _sql_repositories(tmp_path)

    result = import_quickorganizer_package(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
        actor="Operatore SQL",
    )
    audit = audit_quickorganizer_import(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
    )

    assert result["summary"]["mattersCreated"] == 1
    assert audit["ok"] is True
    assert studio_db.conn.execute("SELECT COUNT(*) FROM fascicoli").fetchone()[0] == 1
    assert studio_db.conn.execute("SELECT COUNT(*) FROM clienti").fetchone()[0] == 1
    assert studio_db.conn.execute("SELECT COUNT(*) FROM soggetti").fetchone()[0] == 2
    assert studio_db.conn.execute("SELECT COUNT(*) FROM soggetti_parti").fetchone()[0] == 2
    assert studio_db.conn.execute("SELECT COUNT(*) FROM soggetti_parti WHERE id_fascicolo IS NOT NULL").fetchone()[0] == 2
    fascicoli_mirror = tmp_path / "tenant" / "fascicoli" / "fascicoli.json"
    assert fascicoli_mirror.exists()
    assert len(json.loads(fascicoli_mirror.read_text(encoding="utf-8"))) == 1
    assert not (tmp_path / "tenant" / "clienti" / "anagrafica.json").exists()
    assert not (tmp_path / "tenant" / "soggetti" / "anagrafica.json").exists()
    assert not (tmp_path / "tenant" / "soggetti" / "parti.json").exists()


def test_import_studio_telematico_salva_repository_solo_a_fine_lotto(tmp_path: Path):
    package = load_quickorganizer_package(_write_package(tmp_path / "studio-telematico.zip"))
    fascicoli, clienti, soggetti = _repositories(tmp_path)
    counts = {"fascicoli": 0, "clienti": 0, "soggetti": 0, "parti": 0}

    def _wrap(obj, method_name: str, key: str):
        original = getattr(obj, method_name)

        def _counted():
            counts[key] += 1
            return original()

        setattr(obj, method_name, _counted)

    _wrap(fascicoli, "_salva", "fascicoli")
    _wrap(clienti, "_salva", "clienti")
    _wrap(soggetti, "_salva", "soggetti")
    _wrap(soggetti, "_salva_parti", "parti")

    import_quickorganizer_package(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
        actor="Operatore Test",
    )

    assert counts == {"fascicoli": 1, "clienti": 1, "soggetti": 1, "parti": 1}


def test_import_studio_telematico_ricostruisce_cliente_da_parti_cli_se_titolare_manca(tmp_path: Path):
    package = load_quickorganizer_package(_write_package_without_titolare(tmp_path / "studio-telematico.zip"))
    fascicoli, clienti, soggetti = _repositories(tmp_path)

    result = import_quickorganizer_package(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
        actor="Operatore Test",
    )
    audit = audit_quickorganizer_import(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
    )
    matters = {f.source_external_id: f for f in fascicoli.tutti(archiviati=True)}
    first = matters["quickorganizer:202"]
    second = matters["quickorganizer:203"]

    assert result["summary"]["mattersCreated"] == 2
    assert result["summary"]["clientsCreated"] == 2
    assert first.nome_cliente == "Verdi Anna"
    assert clienti.get(first.id_cliente).recapiti.email == "anna@example.it"
    assert second.nome_cliente == "Pratica senza parti"
    assert "cliente-da-pratica" in clienti.get(second.id_cliente).tag
    assert audit["ok"] is True
    assert audit["expected"]["clients"] == 1
    assert audit["found"]["clients"] == 1
    assert audit["expected"]["clientsLinked"] == 2
    assert audit["found"]["clientsLinked"] == 2


def test_import_studio_telematico_persona_giuridica_con_cf_numerico_usa_partita_iva(tmp_path: Path):
    package = load_quickorganizer_package(_write_package_persona_giuridica_cf_numerico(tmp_path / "studio-telematico.zip"))
    fascicoli, clienti, soggetti = _repositories(tmp_path)

    result = import_quickorganizer_package(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
        actor="Operatore Test",
    )
    audit = audit_quickorganizer_import(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
    )
    matter = next(f for f in fascicoli.tutti(archiviati=True) if f.source_external_id == "quickorganizer:259")
    cliente = clienti.get(matter.id_cliente)

    assert result["summary"]["clientsCreated"] == 1
    assert cliente.ragione_sociale == "Associazione Italiana Maestri Cattolici"
    assert cliente.codice_fiscale == ""
    assert cliente.partita_iva == "03905310797"
    assert audit["ok"] is True


def test_import_studio_telematico_non_riusa_numero_fascicolo_con_buchi_sqlite(tmp_path: Path):
    package = load_quickorganizer_package(_write_package(tmp_path / "studio-telematico.zip"))
    studio_db = StudioDB.get(str(tmp_path / "tenant" / "studio.db"))
    fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "tenant" / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "tenant" / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "tenant" / "fascicoli" / "archivio"),
        studio_db=studio_db,
    )
    clienti = GestioneClienti(db_path=str(tmp_path / "clienti" / "anagrafica.json"))
    soggetti = GestioneSoggetti(
        str(tmp_path / "soggetti" / "anagrafica.json"),
        str(tmp_path / "soggetti" / "parti.json"),
    )
    year = __import__("datetime").date.today().year
    primo = fascicoli.nuovo("Pratica esistente 1", TipoFascicolo.CIVILE)
    secondo = fascicoli.nuovo("Pratica esistente 3", TipoFascicolo.CIVILE)
    primo.numero = f"{year}/001"
    secondo.numero = f"{year}/003"
    fascicoli._salva()

    result = import_quickorganizer_package(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
        actor="Operatore Test",
    )

    imported = next(
        item
        for item in fascicoli.tutti(archiviati=True)
        if item.source_external_id == "quickorganizer:101"
    )
    assert result["summary"]["mattersCreated"] == 1
    assert imported.numero == f"{year}/004"
    studio_db.chiudi()


def test_import_studio_telematico_legge_zip_con_sole_cartelle_senza_errore_generico(tmp_path: Path):
    package = load_quickorganizer_package(_write_files_only_package(tmp_path / "atti-emails.zip"))
    analysis = analyze_quickorganizer_package(package)

    assert package.source_kind == "zip-files"
    assert analysis["ok"] is False
    assert analysis["canImportComplete"] is False
    assert analysis["summary"]["availableFiles"] == 2
    assert analysis["warnings"] == [
        {
            "code": "archivio_dati_assente",
            "message": (
                "Il pacchetto contiene documenti o comunicazioni, ma manca l'archivio dati. "
                "Prepara di nuovo il pacchetto dalla postazione autorizzata completa."
            ),
        }
    ]


def test_import_studio_telematico_stage_percorso_locale_non_copia_zip_grande(tmp_path: Path):
    source = _write_files_only_package(tmp_path / "QuickOrganizer.zip")
    stage_root = tmp_path / "staging"

    stage = stage_referenced_package(source, stage_root)
    package, loaded = load_staged_package(stage_root, stage["importId"])

    assert stage["sourceName"] == "QuickOrganizer.zip"
    assert stage["sourceSha256"].startswith("local-size:")
    assert stage["analysis"]["summary"]["availableFiles"] == 2
    assert package.source_path == source.resolve()
    assert loaded["sourcePath"] == str(source.resolve())
    assert not list((stage_root / stage["importId"]).glob("source.*"))


def test_import_studio_telematico_upload_a_blocchi_ricompone_e_stagia(tmp_path: Path):
    source = _write_package(tmp_path / "IUSENTRA-PacchettoPratiche.zip")
    payload = source.read_bytes()
    stage_root = tmp_path / "staging"
    session = begin_chunked_upload(
        source.name,
        len(payload),
        stage_root,
        chunk_size=97,
        max_size=len(payload) + 1024,
    )

    total_chunks = int(session["totalChunks"])
    chunk_size = int(session["chunkSizeBytes"])
    for index in range(total_chunks):
        chunk = payload[index * chunk_size : (index + 1) * chunk_size]
        result = receive_chunked_upload(
            stage_root,
            session["uploadId"],
            index,
            total_chunks,
            FileStorage(stream=io.BytesIO(chunk), filename=f"part-{index}.bin"),
        )
        assert result["ok"] is True

    stage = complete_chunked_upload(stage_root, session["uploadId"], total_chunks=total_chunks)
    package, loaded = load_staged_package(stage_root, stage["importId"])

    assert stage["sourceName"] == source.name
    assert stage["analysis"]["summary"]["matters"] == 1
    assert package.source_path.name == "source.zip"
    assert loaded["sourceSha256"] == stage["sourceSha256"]
    assert not (stage_root / "_chunk_uploads" / session["uploadId"]).exists()


def test_import_studio_telematico_preparazione_automatica_tokenizzata(tmp_path: Path):
    index_root = tmp_path / "prepare-index"
    staging_root = tmp_path / "staging"

    started = begin_auto_prepare_session(index_root, staging_root)
    token = started.pop("token")

    assert started["ok"] is True
    assert started["status"] == "pending"
    assert "stagingRoot" not in json.dumps(started)
    assert "tokenHash" not in json.dumps(started)

    status = update_auto_prepare_status(
        index_root,
        started["sessionId"],
        token,
        status="preparing",
        progress=25,
        detail="Lettura archivio dati.",
    )
    assert status["status"] == "preparing"
    assert status["progress"] == 25
    assert auto_prepare_status(index_root, started["sessionId"])["detail"] == "Lettura archivio dati."

    with pytest.raises(QuickOrganizerImportError):
        update_auto_prepare_status(index_root, started["sessionId"], "token-sbagliato", status="ready")


def test_import_studio_telematico_preparazione_automatica_carica_e_controlla_zip(tmp_path: Path):
    source = _write_package(tmp_path / "IUSENTRA-PacchettoPratiche.zip")
    payload = source.read_bytes()
    index_root = tmp_path / "prepare-index"
    staging_root = tmp_path / "staging"

    started = begin_auto_prepare_session(index_root, staging_root)
    token = started["token"]
    session_id = started["sessionId"]
    upload = start_auto_prepare_upload(
        index_root,
        session_id,
        token,
        filename=source.name,
        total_size=len(payload),
        chunk_size=97,
        max_size=len(payload) + 1024,
    )
    total_chunks = int(upload["totalChunks"])
    chunk_size = int(upload["chunkSizeBytes"])

    for index in range(total_chunks):
        chunk = payload[index * chunk_size : (index + 1) * chunk_size]
        result = receive_auto_prepare_chunk(
            index_root,
            session_id,
            token,
            upload["uploadId"],
            index,
            total_chunks,
            FileStorage(stream=io.BytesIO(chunk), filename=f"part-{index}.bin"),
        )
        assert result["ok"] is True

    stage = complete_auto_prepare_upload(
        index_root,
        session_id,
        token,
        upload["uploadId"],
        total_chunks=total_chunks,
    )
    status = auto_prepare_status(index_root, session_id)

    assert stage["ok"] is True
    assert stage["analysis"]["summary"]["matters"] == 1
    assert status["status"] == "ready"
    assert status["preview"]["importId"] == stage["importId"]
    assert "sourcePath" not in status["preview"]


def test_import_studio_telematico_upload_a_blocchi_preserva_sessione_se_staging_fallisce(
    tmp_path: Path,
    monkeypatch,
):
    source = _write_package(tmp_path / "IUSENTRA-PacchettoPratiche.zip")
    payload = source.read_bytes()
    stage_root = tmp_path / "staging"
    session = begin_chunked_upload(
        source.name,
        len(payload),
        stage_root,
        chunk_size=97,
        max_size=len(payload) + 1024,
    )
    total_chunks = int(session["totalChunks"])
    chunk_size = int(session["chunkSizeBytes"])
    for index in range(total_chunks):
        chunk = payload[index * chunk_size : (index + 1) * chunk_size]
        receive_chunked_upload(
            stage_root,
            session["uploadId"],
            index,
            total_chunks,
            FileStorage(stream=io.BytesIO(chunk), filename=f"part-{index}.bin"),
        )

    def _raise_stage_failure(*args, **kwargs):
        raise QuickOrganizerImportError("Staging fallito")

    monkeypatch.setattr(quickorganizer_import, "stage_uploaded_package", _raise_stage_failure)

    with pytest.raises(QuickOrganizerImportError, match="Staging fallito"):
        complete_chunked_upload(stage_root, session["uploadId"], total_chunks=total_chunks)

    preserved_session = stage_root / "_chunk_uploads" / session["uploadId"]
    assert preserved_session.exists()
    assert (preserved_session / "assembled.zip").exists()
    assert (preserved_session / "parts" / "part-000000.bin").exists()


def test_import_studio_telematico_zip_mdb_non_leggibile_mostra_avviso_utile(
    tmp_path: Path,
    monkeypatch,
):
    def _raise_unreadable(path: Path, **kwargs):
        raise QuickOrganizerImportError("L'archivio dati non è leggibile su questo ambiente.")

    monkeypatch.setattr(quickorganizer_import, "_package_from_mdb", _raise_unreadable)

    package = load_quickorganizer_package(_write_mdb_package(tmp_path / "QuickOrganizer.zip"))
    analysis = analyze_quickorganizer_package(package)

    assert package.source_kind == "zip-mdb-unreadable"
    assert analysis["ok"] is False
    assert analysis["summary"]["availableFiles"] == 2
    assert analysis["warnings"][0]["code"] == "archivio_dati_non_leggibile"
    assert "preparatore pacchetto" in analysis["warnings"][0]["message"]


def test_import_studio_telematico_mdb_passa_percorso_a_powershell_come_parametro(
    tmp_path: Path,
    monkeypatch,
):
    mdb = tmp_path / "QuickOrganizer.mdb"
    mdb.write_bytes(b"access placeholder")
    (tmp_path / "ATTI").mkdir()
    (tmp_path / "EMAILS").mkdir()
    (tmp_path / "ATTI" / "ricorso.pdf").write_bytes(b"%PDF")
    (tmp_path / "EMAILS" / "MSG000001.eml").write_text("Subject: prova", encoding="utf-8")
    captured: dict[str, object] = {}

    class Completed:
        returncode = 0
        stdout = json.dumps({"format": "iusentra.quickorganizer.v1", "tables": {"PRATICHE": []}})
        stderr = ""

    def _fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return Completed()

    monkeypatch.setattr(quickorganizer_import.platform, "system", lambda: "Windows")
    monkeypatch.setattr(quickorganizer_import, "_powershell32", lambda: "powershell.exe")
    monkeypatch.setattr(quickorganizer_import.subprocess, "run", _fake_run)

    package = load_quickorganizer_package(mdb)

    command = captured["command"]
    kwargs = captured["kwargs"]
    assert package.source_kind == "mdb"
    assert "ATTI:ricorso.pdf" in package.files
    assert "EMAILS:msg000001.eml" in package.files
    assert isinstance(command, list)
    assert command[-1] == str(mdb.resolve())
    assert command[command.index("-Command") + 1].lstrip().startswith("& {")
    assert "param([string]$mdb)" in command[command.index("-Command") + 1]
    assert "$mdb = $args[0]" not in command[command.index("-Command") + 1]
    assert kwargs["encoding"] == "utf-8"


def test_import_studio_telematico_blocca_pacchetto_senza_atti_o_emails(tmp_path: Path):
    package = load_quickorganizer_package(
        _write_package(tmp_path / "studio-telematico-incompleto.zip", include_atto=False, include_email=False)
    )
    analysis = analyze_quickorganizer_package(package)
    fascicoli, clienti, soggetti = _repositories(tmp_path)

    assert analysis["canImportComplete"] is False
    assert analysis["summary"]["documentFilesMissing"] == 1
    assert analysis["summary"]["emailFilesMissing"] == 1

    try:
        import_quickorganizer_package(
            package,
            fascicoli=fascicoli,
            clienti=clienti,
            soggetti=soggetti,
            actor="Operatore Test",
        )
    except QuickOrganizerImportError as exc:
        assert "file collegati" in str(exc)
    else:
        raise AssertionError("Import incompleto non bloccato")

    partial = import_quickorganizer_package(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
        actor="Operatore Test",
        allow_partial=True,
    )

    assert partial["summary"]["mattersCreated"] == 1
    assert partial["summary"]["documentsMissing"] == 1
    assert partial["summary"]["emailsMissing"] == 1
