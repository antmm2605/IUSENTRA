"""Import guidato da QuickOrganizer verso gli archivi IUSENTRA."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from werkzeug.utils import safe_join as werkzeug_safe_join
from werkzeug.utils import secure_filename

from pct.clienti import (
    Cliente,
    GestioneClienti,
    Indirizzo,
    Recapiti,
    StatoCliente,
    TipoCliente,
)
from pct.fascicoli import (
    GestioneFascicoli,
    StatoFascicolo,
    TipoAttivita,
    TipoDocumento,
    TipoFascicolo,
)
from pct.path_security import UnsafeRuntimePath, resolve_runtime_path
from pct.soggetti import GestioneSoggetti, RuoloSoggetto, TipoSoggetto


PACKAGE_FORMAT = "iusentra.quickorganizer.v1"
EXPORT_JSON_NAMES = (
    "quickorganizer-export.json",
    "quickorganizer.json",
    "iusentra-quickorganizer.json",
)
TABLES_REQUIRED = ("PRATICHE", "NOMI", "TAVOLA", "TESTI", "EMAILS", "AGENDA")
PACKAGE_SUFFIXES = {".zip", ".json", ".mdb"}
TABLE_ALIASES = {
    "PRATICHE": "PRATICHE",
    "NOMI": "NOMI",
    "TAVOLA": "TAVOLA",
    "TESTI": "TESTI",
    "EMAILS": "EMAILS",
    "AGENDA": "AGENDA",
}


class QuickOrganizerImportError(RuntimeError):
    """Errore recuperabile mostrabile nella pagina import."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.public_message = message


@dataclass(frozen=True)
class PackageFile:
    name: str
    size: int
    sha256: str
    section: str = ""
    source: Path | None = None
    zip_member: str = ""


@dataclass
class QuickOrganizerPackage:
    source_path: Path
    tables: dict[str, list[dict[str, Any]]]
    files: dict[str, PackageFile]
    source_kind: str = "package"

    def table(self, name: str) -> list[dict[str, Any]]:
        return list(self.tables.get(TABLE_ALIASES.get(name.upper(), name.upper()), []))

    def read_file(self, package_file: PackageFile) -> bytes:
        if package_file.source:
            return _safe_existing_file(package_file.source).read_bytes()
        if package_file.zip_member:
            with zipfile.ZipFile(self.source_path) as archive:
                return archive.read(package_file.zip_member)
        raise QuickOrganizerImportError("File sorgente non disponibile.")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _safe_runtime_dir(path: str | Path, *, create: bool = False) -> Path:
    try:
        resolved = resolve_runtime_path(path, extra_roots=(tempfile.gettempdir(), _repo_root())).resolve()
    except (OSError, RuntimeError, ValueError, UnsafeRuntimePath) as exc:
        raise QuickOrganizerImportError("Percorso di lavoro import non valido.") from exc
    if create:
        resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _safe_child_path(root: str | Path, *parts: str) -> Path:
    root_path = _safe_runtime_dir(root)
    joined = werkzeug_safe_join(str(root_path), *[str(part or "") for part in parts])
    if not joined:
        raise QuickOrganizerImportError("Percorso di lavoro import non valido.")
    return Path(joined)


def _safe_existing_file(path: str | Path, *, allowed_suffixes: set[str] | None = None) -> Path:
    suffixes = {suffix.casefold() for suffix in allowed_suffixes} if allowed_suffixes else None
    try:
        resolved = resolve_runtime_path(
            path,
            allowed_suffixes=suffixes,
            extra_roots=(tempfile.gettempdir(), _repo_root()),
        ).resolve(strict=True)
    except (OSError, RuntimeError, ValueError, UnsafeRuntimePath) as exc:
        raise QuickOrganizerImportError("File import non valido o fuori dall'area consentita.") from exc
    if not resolved.is_file():
        raise QuickOrganizerImportError("File import non trovato.")
    return resolved


def _safe_package_path(path: str | Path) -> Path:
    return _safe_existing_file(path, allowed_suffixes=PACKAGE_SUFFIXES)


def _safe_upload_suffix(filename: Any) -> str:
    suffix = Path(secure_filename(_text(filename)) or "pacchetto.zip").suffix.casefold()
    return suffix if suffix in PACKAGE_SUFFIXES else ".zip"


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any, fallback: str = "") -> str:
    raw = str(value if value is not None else fallback).strip()
    return raw or fallback


def _number(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _decimal(value: Any) -> float:
    raw = _text(value).replace(".", "").replace(",", ".") if isinstance(value, str) else value
    try:
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    raw = _text(value).lower()
    return raw in {"1", "true", "vero", "si", "sì", "yes", "on"}


def _row_value(row: Mapping[str, Any], *names: str, default: Any = "") -> Any:
    index = {str(key).casefold(): value for key, value in row.items()}
    for name in names:
        key = name.casefold()
        if key in index:
            return index[key]
    return default


def _iso_date(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    for suffix in ("Z", "+00:00"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]
            break
    raw = raw.replace("T", " ")
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H.%M.%S",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(raw[:19], fmt).date().isoformat()
        except ValueError:
            continue
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return ""


def _normalise_filename(name: Any) -> str:
    return Path(_text(name)).name.strip()


def _file_key(name: Any) -> str:
    return _normalise_filename(name).casefold()


def _sha256_file(path: Path) -> str:
    path = _safe_existing_file(path)
    h = hashlib.sha256()
    # lgtm[py/path-injection] Percorso già normalizzato da resolve_runtime_path.
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _table_payload(raw: Any) -> dict[str, list[dict[str, Any]]]:
    if isinstance(raw, Mapping) and isinstance(raw.get("tables"), Mapping):
        raw_tables = raw.get("tables") or {}
    elif isinstance(raw, Mapping):
        raw_tables = raw
    else:
        raise QuickOrganizerImportError("Il pacchetto non contiene tabelle leggibili.")
    tables: dict[str, list[dict[str, Any]]] = {}
    for name, rows in raw_tables.items():
        upper = str(name or "").strip().upper()
        if not upper or not isinstance(rows, list):
            continue
        tables[upper] = [dict(row) for row in rows if isinstance(row, Mapping)]
    return tables


def _read_json_payload(path: Path) -> dict[str, Any]:
    path = _safe_existing_file(path, allowed_suffixes={".json"})
    try:
        # lgtm[py/path-injection] Percorso già normalizzato da resolve_runtime_path.
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise QuickOrganizerImportError("Il file dati QuickOrganizer non è un JSON valido.") from exc


def _files_from_directory(root: Path) -> dict[str, PackageFile]:
    files: dict[str, PackageFile] = {}
    safe_root = _safe_runtime_dir(root)
    for base_name in ("ATTI", "EMAILS"):
        base = _safe_child_path(safe_root, base_name)
        # lgtm[py/path-injection] Sotto-directory costante dentro root validata.
        if not base.exists():
            continue
        # lgtm[py/path-injection] Enumerazione confinata a root validata.
        for file_path in base.rglob("*"):
            if not file_path.is_file():
                continue
            key = f"{base_name}:{_file_key(file_path.name)}"
            files.setdefault(
                key,
                PackageFile(
                    name=file_path.name,
                    size=file_path.stat().st_size,
                    sha256=_sha256_file(file_path),
                    section=base_name,
                    source=file_path,
                ),
            )
    return files


def _package_from_json(path: Path) -> QuickOrganizerPackage:
    path = _safe_existing_file(path, allowed_suffixes={".json"})
    payload = _read_json_payload(path)
    files = _files_from_directory(path.parent)
    return QuickOrganizerPackage(path, _table_payload(payload), files, source_kind="json")


def _package_from_zip(path: Path) -> QuickOrganizerPackage:
    path = _safe_existing_file(path, allowed_suffixes={".zip"})
    try:
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            json_name = next(
                (
                    name
                    for expected in EXPORT_JSON_NAMES
                    for name in names
                    if Path(name).name.casefold() == expected.casefold()
                ),
                "",
            )
            if not json_name:
                raise QuickOrganizerImportError("Nel pacchetto manca il file dati QuickOrganizer.")
            payload = json.loads(archive.read(json_name).decode("utf-8-sig"))
            files: dict[str, PackageFile] = {}
            for info in archive.infolist():
                if info.is_dir():
                    continue
                filename = Path(info.filename).name
                if not filename or filename.casefold() in {name.casefold() for name in EXPORT_JSON_NAMES}:
                    continue
                parts = [part.upper() for part in Path(info.filename).parts]
                section = "ATTI" if "ATTI" in parts else "EMAILS" if "EMAILS" in parts else ""
                file_key = _file_key(filename)
                key = f"{section}:{file_key}" if section else file_key
                if key in files:
                    continue
                files[key] = PackageFile(
                    name=filename,
                    size=info.file_size,
                    sha256=f"zip-crc:{info.CRC:08x}",
                    section=section,
                    zip_member=info.filename,
                )
    except zipfile.BadZipFile as exc:
        raise QuickOrganizerImportError("Il pacchetto QuickOrganizer non è un archivio ZIP valido.") from exc
    except json.JSONDecodeError as exc:
        raise QuickOrganizerImportError("Il file dati nel pacchetto non è leggibile.") from exc
    return QuickOrganizerPackage(path, _table_payload(payload), files, source_kind="zip")


def _powershell32() -> str:
    windir = os.environ.get("WINDIR", r"C:\Windows")
    candidate = Path(windir) / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if candidate.exists():
        return str(candidate)
    return "powershell.exe"


def _package_from_mdb(path: Path) -> QuickOrganizerPackage:
    path = _safe_existing_file(path, allowed_suffixes={".mdb"})
    if platform.system().lower() != "windows":
        raise QuickOrganizerImportError(
            "Per l'archivio Access serve il pacchetto preparato dal PC QuickOrganizer."
        )
    script = r"""
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$mdb = $args[0]
$tables = @('PRATICHE','NOMI','TAVOLA','TESTI','EMAILS','AGENDA','Parcelle','Prestazioni','PrecisazioneCredito','Titoli','BeniMobili','BeniImmobili','DirittiReali','Ipoteche')
$conn = New-Object System.Data.OleDb.OleDbConnection("Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$mdb;Persist Security Info=False;")
$conn.Open()
try {
  $result = @{ format = 'iusentra.quickorganizer.v1'; generated_at = (Get-Date).ToUniversalTime().ToString('o'); tables = @{} }
  foreach($table in $tables) {
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = "SELECT * FROM [$table]"
    try {
      $reader = $cmd.ExecuteReader()
      $rows = New-Object System.Collections.ArrayList
      while($reader.Read()) {
        $obj = [ordered]@{}
        for($i=0; $i -lt $reader.FieldCount; $i++) {
          $name = $reader.GetName($i)
          if($reader.IsDBNull($i)) { $obj[$name] = $null; continue }
          $value = $reader.GetValue($i)
          if($value -is [datetime]) { $obj[$name] = $value.ToString('o') }
          else { $obj[$name] = $value }
        }
        [void]$rows.Add($obj)
      }
      $reader.Close()
      $result.tables[$table] = $rows
    } catch {
      $result.tables[$table] = @()
    }
  }
  $result | ConvertTo-Json -Depth 8 -Compress
} finally {
  $conn.Close()
}
"""
    command = [
        _powershell32(),
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
        str(path),
    ]
    # lgtm[py/command-line-injection] shell=False, eseguibile e file Access validati prima della chiamata.
    completed = subprocess.run(command, text=True, capture_output=True, timeout=180, check=False, shell=False)
    if completed.returncode != 0:
        raise QuickOrganizerImportError("Il database QuickOrganizer non è leggibile su questo ambiente.")
    output = completed.stdout.strip()
    json_start = output.find("{")
    if json_start > 0:
        output = output[json_start:]
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise QuickOrganizerImportError("La lettura del database QuickOrganizer non ha prodotto dati validi.") from exc
    return QuickOrganizerPackage(path, _table_payload(payload), {}, source_kind="mdb")


def load_quickorganizer_package(path: str | Path) -> QuickOrganizerPackage:
    source = _safe_package_path(path)
    suffix = source.suffix.casefold()
    if suffix == ".zip":
        return _package_from_zip(source)
    if suffix == ".json":
        return _package_from_json(source)
    if suffix == ".mdb":
        return _package_from_mdb(source)
    raise QuickOrganizerImportError("Carica un pacchetto ZIP QuickOrganizer o un archivio dati preparato.")


def _find_file(package: QuickOrganizerPackage, filename: Any, *, section: str = "") -> PackageFile | None:
    name = _file_key(filename)
    if not name:
        return None
    item = package.files.get(f"{section}:{name}") if section else None
    if not item:
        item = package.files.get(name)
    if item and section and item.section and item.section != section:
        return None
    return item


def _count_missing_files(
    rows: Iterable[Mapping[str, Any]],
    package: QuickOrganizerPackage,
    *,
    section: str,
) -> tuple[int, int, list[str]]:
    total = 0
    missing = 0
    sample: list[str] = []
    for row in rows:
        filename = _normalise_filename(_row_value(row, "NOME_DOS"))
        if not filename:
            continue
        total += 1
        if not _find_file(package, filename, section=section):
            missing += 1
            if len(sample) < 8:
                sample.append(filename)
    return total, missing, sample


def analyze_quickorganizer_package(package: QuickOrganizerPackage) -> dict[str, Any]:
    pratiche = package.table("PRATICHE")
    nomi = package.table("NOMI")
    tavola = package.table("TAVOLA")
    testi = package.table("TESTI")
    emails = package.table("EMAILS")
    agenda = package.table("AGENDA")
    document_total, document_missing, document_sample = _count_missing_files(testi, package, section="ATTI")
    email_total, email_missing, email_sample = _count_missing_files(emails, package, section="EMAILS")
    archived = sum(1 for row in pratiche if _bool(_row_value(row, "ARCHIVIO")))
    active = max(len(pratiche) - archived, 0)
    warnings = []
    if document_missing:
        warnings.append(
            {
                "code": "documenti_mancanti",
                "message": f"Mancano {document_missing} documenti collegati alle pratiche.",
            }
        )
    if email_missing:
        warnings.append(
            {
                "code": "email_mancanti",
                "message": f"Mancano {email_missing} messaggi email collegati alle pratiche.",
            }
        )
    if not pratiche:
        warnings.append({"code": "pratiche_assenti", "message": "Nessuna pratica rilevata nel pacchetto."})
    return {
        "ok": bool(pratiche),
        "sourceKind": package.source_kind,
        "generatedAt": _iso_now(),
        "summary": {
            "matters": len(pratiche),
            "activeMatters": active,
            "archivedMatters": archived,
            "people": len(nomi),
            "partyLinks": len(tavola),
            "documents": document_total,
            "documentFilesFound": max(document_total - document_missing, 0),
            "documentFilesMissing": document_missing,
            "emails": email_total,
            "emailFilesFound": max(email_total - email_missing, 0),
            "emailFilesMissing": email_missing,
            "appointments": len(agenda),
            "availableFiles": len(package.files),
        },
        "samples": {
            "missingDocuments": document_sample,
            "missingEmails": email_sample,
            "matters": [
                {
                    "id": str(_row_value(row, "NUMEROPRATICA")),
                    "title": _text(_row_value(row, "PRATICA"), "Pratica senza titolo"),
                    "object": _text(_row_value(row, "OGGETTO_PRATICA")),
                    "status": _text(_row_value(row, "Stato_Pratica")) or ("Archiviata" if _bool(_row_value(row, "ARCHIVIO")) else "Attiva"),
                }
                for row in pratiche[:8]
            ],
        },
        "warnings": warnings,
        "canImportComplete": document_missing == 0 and email_missing == 0 and bool(pratiche),
    }


def _matter_type(row: Mapping[str, Any]) -> TipoFascicolo:
    text = " ".join(
        _text(_row_value(row, field))
        for field in ("TIPO", "OGGETTO_PRATICA", "PRATICA")
    ).casefold()
    if "penal" in text:
        return TipoFascicolo.PENALE
    if "tribut" in text:
        return TipoFascicolo.TRIBUTARIO
    if "amministr" in text or "tar" in text:
        return TipoFascicolo.AMMINISTRATIVO
    if "lavor" in text:
        return TipoFascicolo.LAVORO
    if "famigl" in text or "separ" in text or "divorz" in text:
        return TipoFascicolo.FAMIGLIA
    if "stragiud" in text:
        return TipoFascicolo.STRAGIUDIZIALE
    return TipoFascicolo.CIVILE


def _matter_status(row: Mapping[str, Any]) -> StatoFascicolo:
    if _bool(_row_value(row, "ARCHIVIO")):
        return StatoFascicolo.ARCHIVIATO
    text = _text(_row_value(row, "Stato_Pratica")).casefold()
    if "definit" in text or "chius" in text or "conclus" in text:
        return StatoFascicolo.DEFINITO
    if "sospes" in text:
        return StatoFascicolo.SOSPESO
    return StatoFascicolo.IN_CORSO


def _document_type(label: Any, filename: Any = "") -> TipoDocumento:
    text = f"{_text(label)} {_text(filename)}".casefold()
    if "ricorso" in text:
        return TipoDocumento.RICORSO
    if "citazione" in text:
        return TipoDocumento.CITAZIONE
    if "comparsa" in text:
        return TipoDocumento.COMPARSA
    if "sentenza" in text:
        return TipoDocumento.SENTENZA
    if "ordinanza" in text:
        return TipoDocumento.ORDINANZA
    if "decreto" in text:
        return TipoDocumento.DECRETO
    if "procura" in text:
        return TipoDocumento.PROCURA
    if filename and str(filename).lower().endswith(".eml"):
        return TipoDocumento.COMUNICAZIONE
    return TipoDocumento.ATTO_GIUDIZIARIO if label else TipoDocumento.ALLEGATO


def _split_person_name(row: Mapping[str, Any]) -> tuple[str, str]:
    name = _text(_row_value(row, "NOME"))
    surname = _text(_row_value(row, "COGNOME"))
    if surname:
        return name, surname
    parts = name.split()
    if len(parts) >= 2:
        return " ".join(parts[1:]), parts[0]
    return "", name or "Nominativo QuickOrganizer"


def _subject_type(row: Mapping[str, Any]) -> TipoSoggetto:
    natura = _text(_row_value(row, "NaturaGiuridica")).casefold()
    if _text(_row_value(row, "PARTITA_IVA")) or any(token in natura for token in ("soc", "ente", "pa", "condominio")):
        return TipoSoggetto.PERSONA_GIURIDICA
    return TipoSoggetto.PERSONA_FISICA


def _client_type(row: Mapping[str, Any]) -> TipoCliente:
    return TipoCliente.PERSONA_GIURIDICA if _subject_type(row) != TipoSoggetto.PERSONA_FISICA else TipoCliente.PERSONA_FISICA


def _address_from_row(row: Mapping[str, Any]) -> Indirizzo:
    return Indirizzo(
        via=_text(_row_value(row, "INDIRIZZO")),
        civico=_text(_row_value(row, "NumeroCivico")),
        cap=_text(_row_value(row, "CAP")),
        comune=_text(_row_value(row, "CITTA")),
        provincia=_text(_row_value(row, "PROVINCIA")),
        nazione=_text(_row_value(row, "NAZIONE"), "Italia"),
    )


def _recapiti_from_row(row: Mapping[str, Any]) -> Recapiti:
    return Recapiti(
        telefono=_text(_row_value(row, "TEL")),
        cellulare=_text(_row_value(row, "CELLU")),
        email=_text(_row_value(row, "EMAIL")),
        pec=_text(_row_value(row, "PEC")),
        fax=_text(_row_value(row, "FAX")),
    )


def _subject_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    nome, cognome = _split_person_name(row)
    tipo = _subject_type(row)
    payload = {
        "codice_fiscale": _text(_row_value(row, "CODICE_FISCALE")).upper(),
        "partita_iva": _text(_row_value(row, "PARTITA_IVA")),
        "indirizzo": _address_from_row(row),
        "recapiti": _recapiti_from_row(row),
        "note": _text(_row_value(row, "NOTE")),
        "tag": ["quickorganizer"],
    }
    if tipo == TipoSoggetto.PERSONA_FISICA:
        payload.update(
            {
                "nome": nome,
                "cognome": cognome,
                "data_nascita": _iso_date(_row_value(row, "DATA_NA")),
                "luogo_nascita": _text(_row_value(row, "LUOGO_NA")),
                "provincia_nascita": _text(_row_value(row, "ProvinciaNascita")),
            }
        )
    else:
        payload.update(
            {
                "ragione_sociale": _text(_row_value(row, "NOME")) or _text(_row_value(row, "COGNOME")),
                "rappresentante_legale": _text(_row_value(row, "LEG_RAPP")),
                "forma_giuridica": _text(_row_value(row, "NaturaGiuridica")),
            }
        )
    return payload


def _subject_identity(row: Mapping[str, Any]) -> str:
    cf = _text(_row_value(row, "CODICE_FISCALE")).upper()
    piva = _text(_row_value(row, "PARTITA_IVA"))
    if cf:
        return f"cf:{cf}"
    if piva:
        return f"piva:{piva}"
    return f"name:{_text(_row_value(row, 'NOME')).casefold()}:{_text(_row_value(row, 'COGNOME')).casefold()}"


def _client_from_subject(
    clienti: GestioneClienti,
    row: Mapping[str, Any],
    *,
    provenance: str,
) -> tuple[Cliente, bool]:
    tipo = _client_type(row)
    cf = _text(_row_value(row, "CODICE_FISCALE")).upper()
    piva = _text(_row_value(row, "PARTITA_IVA"))
    existing = clienti.get_by_codice_fiscale(cf) if cf and len(cf) in {11, 16} else None
    if not existing and piva:
        existing = clienti.get_by_partita_iva(piva)
    if not existing and not cf and not piva:
        nome, cognome = _split_person_name(row)
        expected_name = " ".join(part for part in (cognome, nome) if part).casefold()
        if expected_name:
            existing = next(
                (
                    cliente
                    for cliente in clienti.tutti()
                    if _text(getattr(cliente, "nome_completo", "")).casefold() == expected_name
                ),
                None,
            )
    if existing:
        return existing, False
    nome, cognome = _split_person_name(row)
    common = {
        "stato": StatoCliente.ATTIVO,
        "provenienza": provenance,
        "note": _text(_row_value(row, "NOTE")),
        "recapiti": _recapiti_from_row(row),
        "data_prima_acquisizione": _iso_date(_row_value(row, "DATA_IDENTIFICAZIONE")) or date.today().isoformat(),
    }
    if tipo == TipoCliente.PERSONA_FISICA:
        valid_cf = cf if cf and clienti.valida_cf(cf) else ""
        cliente = clienti.nuovo(
            tipo=tipo,
            nome=nome,
            cognome=cognome,
            codice_fiscale=valid_cf,
            data_nascita=_iso_date(_row_value(row, "DATA_NA")),
            luogo_nascita=_text(_row_value(row, "LUOGO_NA")),
            provincia_nascita=_text(_row_value(row, "ProvinciaNascita")),
            indirizzo_residenza=_address_from_row(row),
            **common,
        )
        cliente = clienti.aggiorna(
            cliente.id,
            recapiti=common["recapiti"],
            indirizzo_residenza=_address_from_row(row),
            note=common["note"],
            data_prima_acquisizione=common["data_prima_acquisizione"],
        )
        return cliente, True
    valid_piva = piva if piva and clienti.valida_piva(piva) else ""
    valid_cf = cf if cf and len(cf) in {11, 16} else ""
    cliente = clienti.nuovo(
        tipo=tipo,
        ragione_sociale=_text(_row_value(row, "NOME")) or _text(_row_value(row, "COGNOME"), "Cliente QuickOrganizer"),
        codice_fiscale=valid_cf,
        partita_iva=valid_piva,
        rappresentante_legale=_text(_row_value(row, "LEG_RAPP")),
        forma_giuridica=_text(_row_value(row, "NaturaGiuridica")),
        indirizzo_sede_legale=_address_from_row(row),
        **common,
    )
    cliente = clienti.aggiorna(
        cliente.id,
        recapiti=common["recapiti"],
        indirizzo_sede_legale=_address_from_row(row),
        note=common["note"],
        data_prima_acquisizione=common["data_prima_acquisizione"],
    )
    return cliente, True


def _existing_matter_by_source(fascicoli: GestioneFascicoli, source_external_id: str) -> Any:
    for item in fascicoli.tutti(stato=None, archiviati=True):
        if _text(getattr(item, "source_external_id", "")) == source_external_id:
            return item
        if _text(getattr(item, "id_pratica", "")) == source_external_id:
            return item
    return None


def _existing_subject_index(soggetti: GestioneSoggetti) -> dict[str, str]:
    index: dict[str, str] = {}
    for soggetto in soggetti.tutti():
        cf = _text(getattr(soggetto, "codice_fiscale", "")).upper()
        piva = _text(getattr(soggetto, "partita_iva", ""))
        if cf:
            index.setdefault(f"cf:{cf}", soggetto.id)
        if piva:
            index.setdefault(f"piva:{piva}", soggetto.id)
        nome = _text(getattr(soggetto, "nome", "")).casefold()
        cognome = _text(getattr(soggetto, "cognome", "")).casefold()
        if nome or cognome:
            index.setdefault(f"name:{nome}:{cognome}", soggetto.id)
        full_name = _text(getattr(soggetto, "nome_completo", "")).casefold()
        if full_name:
            index.setdefault(f"name:{full_name}:", soggetto.id)
    return index


def _activity_kind(row: Mapping[str, Any]) -> TipoAttivita:
    subject = _text(_row_value(row, "Subject")).casefold()
    if "udienza" in subject or _text(_row_value(row, "Ruolo")):
        return TipoAttivita.UDIENZA
    if "scaden" in subject or "termine" in subject:
        return TipoAttivita.TERMINE_SCADENZA
    return TipoAttivita.ALTRO


def import_quickorganizer_package(
    package: QuickOrganizerPackage,
    *,
    fascicoli: GestioneFascicoli,
    clienti: GestioneClienti,
    soggetti: GestioneSoggetti,
    actor: str = "",
    allow_partial: bool = False,
) -> dict[str, Any]:
    analysis = analyze_quickorganizer_package(package)
    if not allow_partial and not analysis.get("canImportComplete"):
        raise QuickOrganizerImportError(
            "Il pacchetto non contiene tutti i file collegati. Completa le cartelle del cliente o abilita l'import dei soli dati disponibili."
        )

    nomi = package.table("NOMI")
    pratiche = package.table("PRATICHE")
    tavola = package.table("TAVOLA")
    testi = package.table("TESTI")
    emails = package.table("EMAILS")
    agenda = package.table("AGENDA")
    nomi_by_id = {_number(_row_value(row, "NUM_NOM")): row for row in nomi}
    links_by_matter: dict[int, list[dict[str, Any]]] = {}
    for link in tavola:
        links_by_matter.setdefault(_number(_row_value(link, "NUMEROPRATICA")), []).append(link)

    subject_index = _existing_subject_index(soggetti)
    subject_ids_by_num: dict[int, str] = {}
    counters = {
        "clientsCreated": 0,
        "subjectsCreated": 0,
        "partyLinksCreated": 0,
        "mattersCreated": 0,
        "mattersUpdated": 0,
        "documentsImported": 0,
        "documentsMissing": 0,
        "emailsImported": 0,
        "emailsMissing": 0,
        "activitiesImported": 0,
        "duplicatesSkipped": 0,
    }
    errors: list[str] = []

    for num, row in nomi_by_id.items():
        identity = _subject_identity(row)
        subject_id = subject_index.get(identity)
        if not subject_id:
            payload = _subject_payload(row)
            tipo = _subject_type(row)
            subject = soggetti.crea(tipo, **payload)
            subject_id = subject.id
            subject_index[identity] = subject_id
            counters["subjectsCreated"] += 1
        subject_ids_by_num[num] = subject_id

    matters_by_number: dict[int, Any] = {}
    matter_id_by_number: dict[int, str] = {}
    for row in pratiche:
        number = _number(_row_value(row, "NUMEROPRATICA"))
        source_external_id = f"quickorganizer:{number}"
        client_id = ""
        client_name = _text(_row_value(row, "TitolareName"))
        titolare_id = _number(_row_value(row, "TitolareID"))
        client_row = nomi_by_id.get(titolare_id)
        if client_row:
            try:
                client, created = _client_from_subject(clienti, client_row, provenance="Import QuickOrganizer")
                client_id = client.id
                client_name = client.nome_completo
                counters["clientsCreated"] += 1 if created else 0
            except Exception as exc:  # noqa: BLE001 - import deve proseguire sui fascicoli
                errors.append(f"Cliente pratica {number}: import non completato per dati non coerenti.")
        existing = _existing_matter_by_source(fascicoli, source_external_id)
        payload = {
            "stato": _matter_status(row),
            "id_cliente": client_id,
            "nome_cliente": client_name,
            "controparte": _text(_row_value(row, "ConvenutoPrincipale")),
            "tribunale": _text(_row_value(row, "AUT_GIUDIZ")),
            "numero_rg": _text(_row_value(row, "RUOLO_GEN")),
            "anno_rg": _number(_row_value(row, "ANNO_RUOLO_GEN")),
            "sezione": _text(_row_value(row, "SEZIONE")),
            "giudice": _text(_row_value(row, "ISTRUTTORE")),
            "cancelliere": _text(_row_value(row, "CANCELL")),
            "ctu": _text(_row_value(row, "CTU")),
            "ctp": _text(_row_value(row, "CTP")),
            "oggetto": _text(_row_value(row, "OGGETTO_PRATICA")),
            "valore_causa": _decimal(_row_value(row, "VALORE")),
            "riferimento_cartaceo": _text(_row_value(row, "RIF")),
            "attore_principale": _text(_row_value(row, "AttorePrincipale")),
            "stato_pratica_operativa": _text(_row_value(row, "Stato_Pratica")),
            "data_apertura": _iso_date(_row_value(row, "DATA_APE")) or date.today().isoformat(),
            "data_chiusura": _iso_date(_row_value(row, "DATA_ARC")),
            "note": _text(_row_value(row, "NOTE")),
            "source": "QUICKORGANIZER",
            "source_external_id": source_external_id,
            "sync_status": "IMPORTATO",
            "last_sync_at": _iso_now(),
            "source_snapshot": {
                "numero_pratica": number,
                "pratica": _text(_row_value(row, "PRATICA")),
                "oggetto": _text(_row_value(row, "OGGETTO_PRATICA")),
            },
        }
        if existing:
            matter = fascicoli.aggiorna(existing.id, **payload)
            counters["mattersUpdated"] += 1
        else:
            title = _text(_row_value(row, "PRATICA")) or _text(_row_value(row, "OGGETTO_PRATICA")) or f"Pratica QuickOrganizer {number}"
            matter = fascicoli.nuovo(
                titolo=title,
                tipo=_matter_type(row),
                **payload,
            )
            matter = fascicoli.aggiorna(matter.id, **payload)
            counters["mattersCreated"] += 1
        matters_by_number[number] = matter
        matter_id_by_number[number] = matter.id

        for link in links_by_matter.get(number, []):
            subject_num = _number(_row_value(link, "NUM_NOM"))
            subject_id = subject_ids_by_num.get(subject_num)
            if not subject_id:
                continue
            role = RuoloSoggetto.ASSISTITO if subject_num == titolare_id else RuoloSoggetto.CONTROPARTE
            before = len(soggetti.parti_fascicolo(matter.id))
            soggetti.aggiungi_parte(
                matter.id,
                subject_id,
                role,
                note=f"Import QuickOrganizer pratica {number}",
            )
            after = len(soggetti.parti_fascicolo(matter.id))
            counters["partyLinksCreated"] += max(after - before, 0)

    for row in testi:
        matter_number = _number(_row_value(row, "NUMEROPRATICA"))
        matter_id = matter_id_by_number.get(matter_number)
        filename = _normalise_filename(_row_value(row, "NOME_DOS"))
        if not matter_id or not filename:
            continue
        source_file = _find_file(package, filename, section="ATTI")
        if not source_file:
            counters["documentsMissing"] += 1
            continue
        matter = fascicoli.get(matter_id)
        external_id = f"quickorganizer:testi:{_number(_row_value(row, 'Counter')) or filename}"
        if any(_text(getattr(doc, "id_documento_portale", "")) == external_id for doc in getattr(matter, "documenti", [])):
            counters["duplicatesSkipped"] += 1
            continue
        data = package.read_file(source_file)
        fascicoli.aggiungi_documento(
            matter_id,
            filename,
            _document_type(_row_value(row, "NOME_ATTO"), filename),
            data,
            note=f"Import QuickOrganizer. {_text(_row_value(row, 'BreveDescrizioneContenutoDocumento'))}",
            tags=["quickorganizer"],
            data_documento=_iso_date(_row_value(row, "DATA_ATTO")),
            firmato=_bool(_row_value(row, "signed")),
            caricato_da=actor,
            fonte_documento="IMPORT_ESTERNO",
            nome_originale=filename,
            classificazione_portale="QuickOrganizer",
            id_documento_portale=external_id,
        )
        counters["documentsImported"] += 1

    for row in emails:
        matter_number = _number(_row_value(row, "NumeroPratica"))
        matter_id = matter_id_by_number.get(matter_number)
        filename = _normalise_filename(_row_value(row, "NOME_DOS"))
        if not matter_id or not filename:
            continue
        source_file = _find_file(package, filename, section="EMAILS")
        if not source_file:
            counters["emailsMissing"] += 1
            continue
        matter = fascicoli.get(matter_id)
        external_id = f"quickorganizer:email:{_number(_row_value(row, 'Email_ID')) or filename}"
        if any(_text(getattr(doc, "id_documento_portale", "")) == external_id for doc in getattr(matter, "documenti", [])):
            counters["duplicatesSkipped"] += 1
            continue
        data = package.read_file(source_file)
        subject = _text(_row_value(row, "Subject"), filename)
        fascicoli.aggiungi_documento(
            matter_id,
            filename,
            TipoDocumento.COMUNICAZIONE,
            data,
            note=f"Email importata da QuickOrganizer. Oggetto: {subject}",
            tags=["quickorganizer", "email"],
            data_documento=_iso_date(_row_value(row, "Data")),
            firmato=_bool(_row_value(row, "IsSigned")),
            caricato_da=actor,
            fonte_documento="IMPORT_ESTERNO",
            nome_originale=filename,
            classificazione_portale="QuickOrganizer",
            mittente_portale=_text(_row_value(row, "Mittente")),
            id_documento_portale=external_id,
        )
        counters["emailsImported"] += 1

    for row in agenda:
        matter_number = _number(_row_value(row, "NumeroPratica"))
        matter_id = matter_id_by_number.get(matter_number)
        if not matter_id:
            continue
        task_id = _number(_row_value(row, "TaskID"))
        matter = fascicoli.get(matter_id)
        marker = f"[quickorganizer:agenda:{task_id}]"
        if any(marker in _text(getattr(activity, "note", "")) for activity in getattr(matter, "attivita", [])):
            counters["duplicatesSkipped"] += 1
            continue
        title = _text(_row_value(row, "Subject"), "Appuntamento importato")
        fascicoli.aggiungi_attivita(
            matter_id,
            _activity_kind(row),
            _iso_date(_row_value(row, "StartDateTime")) or date.today().isoformat(),
            title,
            descrizione=_text(_row_value(row, "Description")),
            luogo=_text(_row_value(row, "Location")),
            note=f"{marker} Import QuickOrganizer. {_text(_row_value(row, 'Provvedimento'))}",
            avvocato=actor,
        )
        counters["activitiesImported"] += 1

    return {
        "ok": True,
        "generatedAt": _iso_now(),
        "summary": counters,
        "errors": errors,
        "warnings": analysis.get("warnings", []),
        "matters": [
            {"id": matter.id, "title": matter.titolo, "href": f"/fascicoli/{matter.id}"}
            for matter in matters_by_number.values()
        ][:20],
    }


def staging_root_for_anchor(anchor_path: str | Path) -> Path:
    anchor = Path(anchor_path)
    base = anchor.parent if anchor.suffix else anchor
    return base / "importazioni" / "quickorganizer"


def stage_uploaded_package(source_path: str | Path, staging_root: str | Path) -> dict[str, Any]:
    source = _safe_package_path(source_path)
    package = load_quickorganizer_package(source)
    import_id = uuid.uuid4().hex
    root = _safe_runtime_dir(staging_root, create=True)
    target_dir = _safe_child_path(root, import_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = _safe_child_path(target_dir, f"source{source.suffix.lower() or '.zip'}")
    # lgtm[py/path-injection] Sorgente e destinazione sono state validate sotto radici runtime consentite.
    shutil.copy2(source, target_path)
    staged_package = load_quickorganizer_package(target_path)
    analysis = analyze_quickorganizer_package(staged_package)
    stage_payload = {
        "importId": import_id,
        "sourceName": source.name,
        "sourceSha256": _sha256_file(target_path),
        "createdAt": _iso_now(),
        "analysis": analysis,
    }
    _safe_child_path(target_dir, "stage.json").write_text(
        json.dumps(stage_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return stage_payload


def load_staged_package(staging_root: str | Path, import_id: str) -> tuple[QuickOrganizerPackage, dict[str, Any]]:
    safe_id = re.sub(r"[^a-f0-9]", "", _text(import_id).lower())
    if not safe_id or safe_id != _text(import_id).lower():
        raise QuickOrganizerImportError("Import non riconosciuto.")
    root = _safe_runtime_dir(staging_root)
    target_dir = _safe_child_path(root, safe_id)
    stage_path = _safe_child_path(target_dir, "stage.json")
    # lgtm[py/path-injection] Percorso stage confinato a directory import validata.
    if not stage_path.exists():
        raise QuickOrganizerImportError("Anteprima import non trovata. Carica di nuovo il pacchetto.")
    # lgtm[py/path-injection] Percorso stage confinato a directory import validata.
    stage = json.loads(stage_path.read_text(encoding="utf-8"))
    # lgtm[py/path-injection] Directory import_id validata e non derivata direttamente dal nome file.
    source = next((path for path in target_dir.iterdir() if path.name.startswith("source.")), None)
    if not source:
        raise QuickOrganizerImportError("Pacchetto import non disponibile.")
    return load_quickorganizer_package(source), stage


def save_upload_to_temp(file_storage: Any) -> Path:
    suffix = _safe_upload_suffix(getattr(file_storage, "filename", ""))
    tmp_dir = Path(tempfile.mkdtemp(prefix="iusentra-qo-upload-"))
    target = _safe_child_path(tmp_dir, f"upload{suffix}")
    # lgtm[py/path-injection] Nome file scartato: salvataggio in tmp generato con suffisso whitelist.
    file_storage.save(target)
    return target


def cleanup_upload_temp(path: str | Path) -> None:
    parent = _safe_runtime_dir(Path(path).parent)
    if not parent.name.startswith("iusentra-qo-upload-"):
        return
    # lgtm[py/path-injection] Rimozione confinata alla directory temporanea generata da save_upload_to_temp.
    shutil.rmtree(parent, ignore_errors=True)
