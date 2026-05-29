from __future__ import annotations

import json
import zipfile
from pathlib import Path

from pct.clienti import GestioneClienti
from pct.fascicoli import GestioneFascicoli
from pct.soggetti import GestioneSoggetti
from web.services.quickorganizer_import import (
    QuickOrganizerImportError,
    analyze_quickorganizer_package,
    import_quickorganizer_package,
    load_quickorganizer_package,
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
                    "NOME_DOS": "ricorso.pdf",
                    "NOME_ATTO": "Ricorso",
                    "DATA_ATTO": "2025-01-12",
                }
            ],
            "EMAILS": [
                {
                    "NumeroPratica": 101,
                    "Email_ID": 88,
                    "NOME_DOS": "messaggio.eml",
                    "Subject": "Invio documenti",
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
            archive.writestr("ATTI/ricorso.pdf", b"%PDF-1.4\ncontenuto atto")
        if include_email:
            archive.writestr("EMAILS/messaggio.eml", b"Subject: Invio documenti\n\nTesto")
    return path


def _write_files_only_package(path: Path) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
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
    assert {doc.nome for doc in fascicolo.documenti} == {"ricorso.pdf", "messaggio.eml"}
    assert len(parti) == 2

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


def test_import_studio_telematico_legge_zip_con_sole_cartelle_senza_errore_generico(tmp_path: Path):
    package = load_quickorganizer_package(_write_files_only_package(tmp_path / "atti-emails.zip"))
    analysis = analyze_quickorganizer_package(package)

    assert package.source_kind == "zip-files"
    assert analysis["ok"] is False
    assert analysis["canImportComplete"] is False
    assert analysis["summary"]["availableFiles"] == 2
    assert analysis["warnings"] == [
        {"code": "pratiche_assenti", "message": "Nessuna pratica rilevata nel pacchetto."}
    ]


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
