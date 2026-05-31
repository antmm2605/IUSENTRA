from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from werkzeug.datastructures import FileStorage

import web.services.quickorganizer_import as quickorganizer_import
from pct.clienti import GestioneClienti
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.soggetti import GestioneSoggetti
from pct.storage import StudioDB
from web.services.quickorganizer_import import (
    QuickOrganizerImportError,
    analyze_quickorganizer_package,
    begin_chunked_upload,
    complete_chunked_upload,
    import_quickorganizer_package,
    load_staged_package,
    load_quickorganizer_package,
    receive_chunked_upload,
    stage_referenced_package,
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
                    "DATA_APE": "10/01/2025",
                    "Stato_Pratica": "In corso",
                }
            ],
            "NOMI": [
                {"NUM_NOM": 1, "NOME": "Mario", "COGNOME": "Rossi", "EMAIL": "mario.rossi@example.it"},
                {"NUM_NOM": 2, "NOME": "Luigi", "COGNOME": "Bianchi", "EMAIL": "luigi.bianchi@example.it"},
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
                    "Location": "Tribunale di Milano",
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
    assert fascicolo.source_external_id == "quickorganizer:101"
    assert len(fascicolo.documenti) == 2
    documenti_by_originale = {doc.nome_originale: doc for doc in fascicolo.documenti}
    atto = documenti_by_originale["scansione-da-pdf-0001.pdf"]
    email = documenti_by_originale["MSG000088.eml"]
    assert atto.nome == "Ricorso introduttivo da tabella.pdf"
    assert atto.nome_portale == "Ricorso introduttivo da tabella.pdf"
    assert Path(atto.percorso).name == "scansione-da-pdf-0001.pdf"
    assert email.nome == "Invio documenti da tabella.eml"
    assert email.nome_portale == "Invio documenti da tabella.eml"
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
                "Il pacchetto contiene file da ATTI o EMAILS, ma manca l'archivio dati QuickOrganizer. "
                "Prepara di nuovo il pacchetto dalla postazione Studio Telematico completa."
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
    source = _write_package(tmp_path / "IUSENTRA-StudioTelematico.zip")
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


def test_import_studio_telematico_upload_a_blocchi_preserva_sessione_se_staging_fallisce(
    tmp_path: Path,
    monkeypatch,
):
    source = _write_package(tmp_path / "IUSENTRA-StudioTelematico.zip")
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
        raise QuickOrganizerImportError("Il database QuickOrganizer non è leggibile su questo ambiente.")

    monkeypatch.setattr(quickorganizer_import, "_package_from_mdb", _raise_unreadable)

    package = load_quickorganizer_package(_write_mdb_package(tmp_path / "QuickOrganizer.zip"))
    analysis = analyze_quickorganizer_package(package)

    assert package.source_kind == "zip-mdb-unreadable"
    assert analysis["ok"] is False
    assert analysis["summary"]["availableFiles"] == 2
    assert analysis["warnings"][0]["code"] == "archivio_dati_non_leggibile"
    assert "PreparaPacchettoStudioTelematico.exe" in analysis["warnings"][0]["message"]


def test_import_studio_telematico_mdb_passa_percorso_a_powershell_come_parametro(
    tmp_path: Path,
    monkeypatch,
):
    mdb = tmp_path / "QuickOrganizer.mdb"
    mdb.write_bytes(b"access placeholder")
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
