"""Import guidato di pratiche da pacchetti esterni verso gli archivi IUSENTRA."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from werkzeug.utils import safe_join as werkzeug_safe_join
from werkzeug.utils import secure_filename

from pct.agenda import Agenda, TipoAppuntamento
from pct.clienti import (
    Cliente,
    GestioneClienti,
    Indirizzo,
    Recapiti,
    StatoCliente,
    TipoCliente,
)
from pct.economico_context import costruisci_contesto_economico
from pct.fascicoli import (
    GestioneFascicoli,
    StatoFascicolo,
    TipoAttivita,
    TipoDocumento,
    TipoFascicolo,
)
from pct.ical_import import EventoImportato
from pct.path_security import UnsafeRuntimePath, resolve_runtime_path
from pct.soggetti import GestioneSoggetti, RuoloSoggetto, TipoSoggetto


PACKAGE_FORMAT = "iusentra.quickorganizer.v1"
EXPORT_JSON_NAMES = (
    "quickorganizer-export.json",
    "quickorganizer.json",
    "iusentra-quickorganizer.json",
)
TABLES_REQUIRED = ("PRATICHE", "NOMI", "TAVOLA", "TESTI", "EMAILS", "AGENDA")
CORE_RELATION_TABLES = ("PRATICHE", "NOMI", "TAVOLA")
REQUIRED_TABLE_FIELDS = {
    "PRATICHE": ("NUMEROPRATICA",),
    "NOMI": ("NUM_NOM", "CONTROLLO"),
    "TAVOLA": ("NUMEROPRATICA", "NUM_NOM"),
    "TESTI": ("NUMEROPRATICA", "NOME_DOS"),
    "EMAILS": ("NumeroPratica", "NOME_DOS"),
    "AGENDA": ("NumeroPratica",),
}
PACKAGE_SUFFIXES = {".zip", ".json", ".mdb"}
DEFAULT_CHUNK_UPLOAD_SIZE_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_UPLOAD_BYTES = 30 * 1024 * 1024 * 1024
DEFAULT_AUTO_PREPARE_EXPIRES_HOURS = 24
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
            return _safe_existing_file(package_file.source, extra_roots=_local_import_roots()).read_bytes()
        if package_file.zip_member:
            with zipfile.ZipFile(self.source_path) as archive:
                return archive.read(package_file.zip_member)
        raise QuickOrganizerImportError("File sorgente non disponibile.")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _safe_runtime_dir(
    path: str | Path,
    *,
    create: bool = False,
    extra_roots: Iterable[str | Path] = (),
) -> Path:
    try:
        resolved = resolve_runtime_path(
            path,
            extra_roots=(tempfile.gettempdir(), _repo_root(), *tuple(extra_roots)),
        ).resolve()
    except (OSError, RuntimeError, ValueError, UnsafeRuntimePath) as exc:
        raise QuickOrganizerImportError("Percorso di lavoro import non valido.") from exc
    if create:
        resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _safe_child_path(root: str | Path, *parts: str, extra_roots: Iterable[str | Path] = ()) -> Path:
    root_path = _safe_runtime_dir(root, extra_roots=extra_roots)
    joined = werkzeug_safe_join(str(root_path), *[str(part or "") for part in parts])
    if not joined:
        raise QuickOrganizerImportError("Percorso di lavoro import non valido.")
    return Path(joined)


def _local_import_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    for raw in str(os.getenv("IUSENTRA_STUDIO_TELEMATICO_LOCAL_ROOTS", "") or "").split(os.pathsep):
        raw = raw.strip()
        if raw:
            roots.append(Path(raw).expanduser())
    home = Path.home()
    roots.extend([home, home / "Downloads", home / "Desktop"])
    return tuple(roots)


def _safe_existing_file(
    path: str | Path,
    *,
    allowed_suffixes: set[str] | None = None,
    extra_roots: Iterable[str | Path] = (),
) -> Path:
    suffixes = {suffix.casefold() for suffix in allowed_suffixes} if allowed_suffixes else None
    try:
        resolved = resolve_runtime_path(
            path,
            allowed_suffixes=suffixes,
            extra_roots=(tempfile.gettempdir(), _repo_root(), *tuple(extra_roots)),
        ).resolve(strict=True)
    except (OSError, RuntimeError, ValueError, UnsafeRuntimePath) as exc:
        raise QuickOrganizerImportError("File import non valido o fuori dall'area consentita.") from exc
    if not resolved.is_file():
        raise QuickOrganizerImportError("File import non trovato.")
    return resolved


def _safe_package_path(path: str | Path) -> Path:
    return _safe_existing_file(path, allowed_suffixes=PACKAGE_SUFFIXES)


def _safe_local_package_path(path: str | Path) -> Path:
    return _safe_existing_file(path, allowed_suffixes=PACKAGE_SUFFIXES, extra_roots=_local_import_roots())


def _safe_upload_suffix(filename: Any) -> str:
    suffix = Path(secure_filename(_text(filename)) or "pacchetto.zip").suffix.casefold()
    return suffix if suffix in PACKAGE_SUFFIXES else ".zip"


def _public_upload_name(filename: Any) -> str:
    name = secure_filename(_text(filename, "pacchetto.zip")) or "pacchetto.zip"
    suffix = Path(name).suffix.casefold()
    if suffix not in PACKAGE_SUFFIXES:
        name = f"{Path(name).stem or 'pacchetto'}.zip"
    return name


def _safe_upload_id(upload_id: Any) -> str:
    value = _text(upload_id).lower()
    if not re.fullmatch(r"[a-f0-9]{32}", value):
        raise QuickOrganizerImportError("Sessione di caricamento non riconosciuta.")
    return value


def _env_int(name: str, default: int) -> int:
    try:
        value = int(str(os.getenv(name, "") or "").strip())
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


def max_chunked_upload_bytes() -> int:
    return _env_int("IUSENTRA_STUDIO_TELEMATICO_MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES)


def _chunk_session_dir(staging_root: str | Path, upload_id: str, *, create: bool = False) -> Path:
    root = _safe_runtime_dir(staging_root, create=True)
    session = _safe_child_path(root, "_chunk_uploads", _safe_upload_id(upload_id), extra_roots=(root,))
    if create:
        session.mkdir(parents=True, exist_ok=True)
    return session


def _chunk_metadata_path(staging_root: str | Path, upload_id: str) -> Path:
    root = _safe_runtime_dir(staging_root)
    return _safe_child_path(_chunk_session_dir(staging_root, upload_id), "metadata.json", extra_roots=(root,))


def _chunk_parts_dir(staging_root: str | Path, upload_id: str, *, create: bool = False) -> Path:
    root = _safe_runtime_dir(staging_root)
    parts = _safe_child_path(_chunk_session_dir(staging_root, upload_id), "parts", extra_roots=(root,))
    if create:
        parts.mkdir(parents=True, exist_ok=True)
    return parts


def _read_chunk_metadata(staging_root: str | Path, upload_id: str) -> dict[str, Any]:
    path = _chunk_metadata_path(staging_root, upload_id)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise QuickOrganizerImportError("Sessione di caricamento scaduta o non trovata.") from exc
    except Exception as exc:
        raise QuickOrganizerImportError("Sessione di caricamento non valida.") from exc


def _chunk_path(staging_root: str | Path, upload_id: str, index: int) -> Path:
    if index < 0:
        raise QuickOrganizerImportError("Blocco di caricamento non valido.")
    root = _safe_runtime_dir(staging_root)
    return _safe_child_path(
        _chunk_parts_dir(staging_root, upload_id, create=True),
        f"part-{index:06d}.bin",
        extra_roots=(root,),
    )


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


def _iso_datetime(value: Any, *, default_time: str = "09:00:00") -> str:
    raw = _text(value)
    if not raw:
        return ""
    for suffix in ("Z", "+00:00"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]
            break
    raw = raw.replace("T", " ").strip()
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H.%M.%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    )
    for fmt in formats:
        try:
            parsed = datetime.strptime(raw[:19], fmt)
            if fmt in {"%Y-%m-%d", "%d/%m/%Y"}:
                parsed = datetime.strptime(f"{parsed.date().isoformat()} {default_time}", "%Y-%m-%d %H:%M:%S")
            return parsed.replace(microsecond=0).isoformat()
        except ValueError:
            continue
    date_only = _iso_date(raw)
    return f"{date_only}T{default_time}" if date_only else ""


def _matter_is_archived(row: Mapping[str, Any]) -> bool:
    return _bool(_row_value(row, "ARCHIVIO")) or bool(_iso_date(_row_value(row, "DATA_ARC")))


def _date_it(value: Any) -> str:
    iso = _iso_date(value)
    if not iso:
        return ""
    year, month, day = iso.split("-")
    return f"{day}/{month}/{year}"


def _datetime_it(value: Any) -> str:
    iso = _iso_datetime(value)
    if not iso:
        return ""
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError:
        return _date_it(value)
    return parsed.strftime("%d/%m/%Y %H:%M")


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


def _read_json_payload(path: Path, *, extra_roots: Iterable[str | Path] = ()) -> dict[str, Any]:
    path = _safe_existing_file(path, allowed_suffixes={".json"}, extra_roots=extra_roots)
    try:
        # lgtm[py/path-injection] Percorso già normalizzato da resolve_runtime_path.
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise QuickOrganizerImportError("Il file dati preparato non è un JSON valido.") from exc


def _files_from_directory(root: Path, *, extra_roots: Iterable[str | Path] = ()) -> dict[str, PackageFile]:
    files: dict[str, PackageFile] = {}
    safe_root = _safe_runtime_dir(root, extra_roots=extra_roots)
    for base_name in ("ATTI", "EMAILS"):
        base = _safe_child_path(safe_root, base_name, extra_roots=extra_roots)
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
                    sha256=f"fs-size:{file_path.stat().st_size}",
                    section=base_name,
                    source=file_path,
                ),
            )
    return files


def _package_from_json(path: Path, *, extra_roots: Iterable[str | Path] = ()) -> QuickOrganizerPackage:
    path = _safe_existing_file(path, allowed_suffixes={".json"}, extra_roots=extra_roots)
    payload = _read_json_payload(path, extra_roots=extra_roots)
    files = _files_from_directory(path.parent, extra_roots=extra_roots)
    return QuickOrganizerPackage(path, _table_payload(payload), files, source_kind="json")


def _empty_quickorganizer_tables() -> dict[str, list[dict[str, Any]]]:
    return {name: [] for name in TABLES_REQUIRED}


def _files_from_zip_infos(archive: zipfile.ZipFile, names_to_skip: set[str] | None = None) -> dict[str, PackageFile]:
    skipped = {name.casefold() for name in (names_to_skip or set()) if name}
    files: dict[str, PackageFile] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        filename = Path(info.filename).name
        if not filename or filename.casefold() in skipped:
            continue
        parts = [part.upper() for part in Path(info.filename).parts]
        section = "ATTI" if "ATTI" in parts else "EMAILS" if "EMAILS" in parts else ""
        if not section:
            continue
        file_key = _file_key(filename)
        key = f"{section}:{file_key}"
        if key in files:
            continue
        files[key] = PackageFile(
            name=filename,
            size=info.file_size,
            sha256=f"zip-crc:{info.CRC:08x}",
            section=section,
            zip_member=info.filename,
        )
    return files


def _package_from_nested_mdb_zip(
    path: Path,
    archive: zipfile.ZipFile,
    mdb_name: str,
    files: dict[str, PackageFile],
) -> QuickOrganizerPackage:
    with tempfile.TemporaryDirectory(prefix="iusentra-qo-mdb-") as tmp:
        tmp_path = _safe_child_path(tmp, "QuickOrganizer.mdb")
        tmp_path.write_bytes(archive.read(mdb_name))
        try:
            mdb_package = _package_from_mdb(tmp_path)
        except QuickOrganizerImportError:
            return QuickOrganizerPackage(
                path,
                _empty_quickorganizer_tables(),
                files,
                source_kind="zip-mdb-unreadable",
            )
    return QuickOrganizerPackage(path, mdb_package.tables, files, source_kind="zip-mdb")


def _package_from_zip(path: Path, *, extra_roots: Iterable[str | Path] = ()) -> QuickOrganizerPackage:
    path = _safe_existing_file(path, allowed_suffixes={".zip"}, extra_roots=extra_roots)
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
            files = _files_from_zip_infos(archive, {json_name, *EXPORT_JSON_NAMES})
            if not json_name:
                mdb_name = next(
                    (
                        name
                        for name in names
                        if Path(name).suffix.casefold() == ".mdb"
                        and Path(name).name.casefold() in {"quickorganizer.mdb", "studio.mdb", "archivio.mdb"}
                    ),
                    "",
                ) or next((name for name in names if Path(name).suffix.casefold() == ".mdb"), "")
                if mdb_name:
                    return _package_from_nested_mdb_zip(path, archive, mdb_name, files)
                if files:
                    return QuickOrganizerPackage(path, _empty_quickorganizer_tables(), files, source_kind="zip-files")
                raise QuickOrganizerImportError(
                    "Nel pacchetto non trovo l'archivio dati preparato, i documenti o le comunicazioni."
                )
            payload = json.loads(archive.read(json_name).decode("utf-8-sig"))
    except zipfile.BadZipFile as exc:
        raise QuickOrganizerImportError("Il pacchetto pratiche non è un archivio ZIP valido.") from exc
    except json.JSONDecodeError as exc:
        raise QuickOrganizerImportError("Il file dati nel pacchetto non è leggibile.") from exc
    return QuickOrganizerPackage(path, _table_payload(payload), files, source_kind="zip")


def _powershell32() -> str:
    windir = os.environ.get("WINDIR", r"C:\Windows")
    candidate = Path(windir) / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if candidate.exists():
        return str(candidate)
    return "powershell.exe"


def _package_from_mdb(path: Path, *, extra_roots: Iterable[str | Path] = ()) -> QuickOrganizerPackage:
    path = _safe_existing_file(path, allowed_suffixes={".mdb"}, extra_roots=extra_roots)
    if platform.system().lower() != "windows":
        raise QuickOrganizerImportError(
            "Per l'archivio Access serve il pacchetto preparato dalla postazione autorizzata."
        )
    script = r"""
param([string]$mdb)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$tables = @('PRATICHE','NOMI','TAVOLA','TESTI','EMAILS','AGENDA','Parcelle','Prestazioni','PrecisazioneCredito','Titoli','BeniMobili','BeniImmobili','DirittiReali','Ipoteche')
$requiredTables = @('PRATICHE','NOMI','TAVOLA','TESTI','EMAILS','AGENDA')
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
      if($requiredTables -contains $table) { throw "Tabella obbligatoria $table non leggibile: $($_.Exception.Message)" }
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
        f"& {{ {script} }}",
        str(path),
    ]
    # lgtm[py/command-line-injection] shell=False, eseguibile e file Access validati prima della chiamata.
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=180,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        raise QuickOrganizerImportError("L'archivio dati non è leggibile su questo ambiente.")
    output = completed.stdout.strip()
    json_start = output.find("{")
    if json_start > 0:
        output = output[json_start:]
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise QuickOrganizerImportError("La lettura dell'archivio dati non ha prodotto dati validi.") from exc
    files = _files_from_directory(path.parent, extra_roots=extra_roots)
    return QuickOrganizerPackage(path, _table_payload(payload), files, source_kind="mdb")


def load_quickorganizer_package(path: str | Path, *, local_source: bool = False) -> QuickOrganizerPackage:
    source = _safe_local_package_path(path) if local_source else _safe_package_path(path)
    extra_roots = _local_import_roots() if local_source else ()
    suffix = source.suffix.casefold()
    if suffix == ".zip":
        return _package_from_zip(source, extra_roots=extra_roots)
    if suffix == ".json":
        return _package_from_json(source, extra_roots=extra_roots)
    if suffix == ".mdb":
        return _package_from_mdb(source, extra_roots=extra_roots)
    raise QuickOrganizerImportError("Carica un pacchetto ZIP pratiche o un archivio dati preparato.")


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


def _field_names(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    fields: set[str] = set()
    for row in rows:
        fields.update(str(key).casefold() for key in row.keys())
    return fields


def _missing_required_fields(tables: Mapping[str, list[dict[str, Any]]]) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    for table, fields in REQUIRED_TABLE_FIELDS.items():
        rows = tables.get(table, [])
        if not rows:
            continue
        available = _field_names(rows)
        for field in fields:
            if field.casefold() not in available:
                missing.append({"table": table, "field": field})
    return missing


def _quickorganizer_relation_summary(
    pratiche: list[dict[str, Any]],
    nomi: list[dict[str, Any]],
    tavola: list[dict[str, Any]],
) -> dict[str, Any]:
    nomi_by_id = {_number(_row_value(row, "NUM_NOM")): row for row in nomi}
    matter_numbers = {_number(_row_value(row, "NUMEROPRATICA")) for row in pratiche if _number(_row_value(row, "NUMEROPRATICA"))}
    matters_with_client: set[int] = set()
    client_party_links = 0
    linked_party_numbers: set[int] = set()
    for row in pratiche:
        number = _number(_row_value(row, "NUMEROPRATICA"))
        titolare_id = _number(_row_value(row, "TitolareID"))
        if number and titolare_id:
            matters_with_client.add(number)
    for link in tavola:
        matter_number = _number(_row_value(link, "NUMEROPRATICA"))
        subject_number = _number(_row_value(link, "NUM_NOM"))
        if matter_number:
            linked_party_numbers.add(matter_number)
        subject_row = nomi_by_id.get(subject_number)
        if subject_row and _is_client_control(subject_row):
            client_party_links += 1
            if matter_number:
                matters_with_client.add(matter_number)
    return {
        "mattersWithParties": len(linked_party_numbers),
        "mattersWithoutParties": len(matter_numbers - linked_party_numbers),
        "clientNominatives": sum(1 for row in nomi if _is_client_control(row)),
        "clientPartyLinks": client_party_links,
        "mattersWithClient": len(matters_with_client),
        "mattersWithoutClient": len(matter_numbers - matters_with_client),
    }


@contextmanager
def _package_file_reader(package: QuickOrganizerPackage) -> Iterable[Callable[[PackageFile], bytes]]:
    archive: zipfile.ZipFile | None = None

    def _read(package_file: PackageFile) -> bytes:
        nonlocal archive
        if package_file.source:
            return _safe_existing_file(package_file.source, extra_roots=_local_import_roots()).read_bytes()
        if package_file.zip_member:
            if archive is None:
                archive = zipfile.ZipFile(package.source_path)
            return archive.read(package_file.zip_member)
        return package.read_file(package_file)

    try:
        yield _read
    finally:
        if archive is not None:
            archive.close()


@contextmanager
def _deferred_repository_saves(
    *,
    fascicoli: GestioneFascicoli,
    clienti: GestioneClienti,
    soggetti: GestioneSoggetti,
    agenda: Agenda | None = None,
) -> Iterable[None]:
    originals: list[tuple[Any, str, Any]] = []

    def _defer(obj: Any, method_name: str) -> None:
        original = getattr(obj, method_name, None)
        if not callable(original):
            return
        originals.append((obj, method_name, original))
        setattr(obj, method_name, lambda *args, **kwargs: None)

    _defer(clienti, "_salva")
    _defer(soggetti, "_salva")
    _defer(soggetti, "_salva_parti")
    _defer(fascicoli, "_salva")
    if agenda is not None:
        _defer(agenda, "_salva")
    try:
        yield
    except Exception:
        raise
    else:
        for _obj, _method_name, original in originals:
            original()
    finally:
        for obj, method_name, original in originals:
            setattr(obj, method_name, original)


def analyze_quickorganizer_package(package: QuickOrganizerPackage) -> dict[str, Any]:
    tables = {name: package.table(name) for name in TABLES_REQUIRED}
    pratiche = tables["PRATICHE"]
    nomi = tables["NOMI"]
    tavola = tables["TAVOLA"]
    testi = tables["TESTI"]
    emails = tables["EMAILS"]
    agenda = tables["AGENDA"]
    document_total, document_missing, document_sample = _count_missing_files(testi, package, section="ATTI")
    email_total, email_missing, email_sample = _count_missing_files(emails, package, section="EMAILS")
    archived = sum(1 for row in pratiche if _matter_is_archived(row))
    active = max(len(pratiche) - archived, 0)
    relation_summary = _quickorganizer_relation_summary(pratiche, nomi, tavola)
    agenda_by_matter: dict[int, list[dict[str, Any]]] = {}
    for row in agenda:
        agenda_by_matter.setdefault(_number(_row_value(row, "NumeroPratica")), []).append(row)
    rg_summary = {
        "mattersWithRg": 0,
        "mattersWithoutRg": 0,
        "mattersRgFromAgenda": 0,
    }
    rg_info_by_matter: dict[int, dict[str, Any]] = {}
    for row in pratiche:
        number = _number(_row_value(row, "NUMEROPRATICA"))
        rg_info = _matter_rg_info(row, agenda_by_matter.get(number, []))
        rg_info_by_matter[number] = rg_info
        if rg_info.get("missing"):
            rg_summary["mattersWithoutRg"] += 1
        else:
            rg_summary["mattersWithRg"] += 1
            if _text(rg_info.get("source")).startswith("AGENDA."):
                rg_summary["mattersRgFromAgenda"] += 1
    missing_fields = _missing_required_fields(tables)
    missing_core_tables = [table for table in CORE_RELATION_TABLES if not tables.get(table)]
    warnings = []
    if pratiche:
        for table in missing_core_tables:
            warnings.append(
                {
                    "code": "tabella_export_mancante",
                    "message": f"Nel file dati preparato manca la tabella {table}; prepara nuovamente il pacchetto dalla postazione autorizzata.",
                }
            )
    for item in missing_fields[:12]:
        warnings.append(
            {
                "code": "campo_export_mancante",
                "message": f"Nel file dati preparato manca il campo {item['field']} della tabella {item['table']}.",
            }
        )
    if pratiche and not tavola:
        warnings.append(
            {
                "code": "relazioni_parti_assenti",
                "message": "Il file dati non contiene collegamenti TAVOLA tra pratiche e nominativi: clienti e parti non possono essere ricostruiti in modo affidabile.",
            }
        )
    if pratiche and relation_summary["mattersWithoutClient"]:
        warnings.append(
            {
                "code": "clienti_da_ricostruire",
                "message": (
                    f"{relation_summary['mattersWithoutClient']} pratiche non hanno un nominativo cliente CLI/OWN collegato; "
                    "l'import crea una scheda di recupero dalla pratica e l'audit finale la evidenzia."
                ),
            }
        )
    if pratiche and rg_summary["mattersWithoutRg"]:
        warnings.append(
            {
                "code": "rg_da_acquisire",
                "message": (
                    f"{rg_summary['mattersWithoutRg']} pratiche non contengono un numero RG nel pacchetto importato; "
                    "IUSENTRA le segnala come RG da acquisire senza usare il numero interno pratica."
                ),
            }
        )
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
        if package.source_kind == "zip-mdb-unreadable":
            warnings.append({
                "code": "archivio_dati_non_leggibile",
                "message": (
                    "Il pacchetto contiene l'archivio dati, ma questa installazione non riesce a leggerlo. "
                    "Esegui il preparatore pacchetto sulla postazione autorizzata: "
                    "creerà un pacchetto completo con archivio dati, documenti e comunicazioni."
                ),
            })
        elif package.files:
            warnings.append({
                "code": "archivio_dati_assente",
                "message": (
                    "Il pacchetto contiene documenti o comunicazioni, ma manca l'archivio dati. "
                    "Prepara di nuovo il pacchetto dalla postazione autorizzata completa."
                ),
            })
        else:
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
            **relation_summary,
            **rg_summary,
        },
        "samples": {
            "missingDocuments": document_sample,
            "missingEmails": email_sample,
            "matters": [
                {
                    "id": str(_row_value(row, "NUMEROPRATICA")),
                    "title": _text(_row_value(row, "PRATICA"), "Pratica senza titolo"),
                    "object": _text(_row_value(row, "OGGETTO_PRATICA")),
                    "status": _text(_row_value(row, "Stato_Pratica")) or ("Archiviata" if _matter_is_archived(row) else "Attiva"),
                    "rgStatus": _text(rg_info_by_matter.get(_number(_row_value(row, "NUMEROPRATICA")), {}).get("status")),
                    "rgLabel": _text(rg_info_by_matter.get(_number(_row_value(row, "NUMEROPRATICA")), {}).get("label")),
                }
                for row in pratiche[:8]
            ],
        },
        "warnings": warnings,
        "canImportComplete": (
            document_missing == 0
            and email_missing == 0
            and bool(pratiche)
            and not missing_core_tables
            and not missing_fields
            and bool(tavola)
        ),
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
    if _matter_is_archived(row):
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


DOCUMENT_TITLE_FIELDS = (
    "NOME_DOCUMENTO",
    "NomeDocumento",
    "NOME_DOC",
    "NomeDoc",
    "TITOLO",
    "Titolo",
    "NOME_ATTO",
    "NomeAtto",
    "TIPO_ATTO",
    "TipoAtto",
    "BreveDescrizioneContenutoDocumento",
    "DESCRIZIONE",
    "Descrizione",
    "OGGETTO",
    "Oggetto",
)

EMAIL_TITLE_FIELDS = (
    "Subject",
    "Oggetto",
    "OGGETTO",
    "TITOLO",
    "Titolo",
    "NOME_DOCUMENTO",
    "NomeDocumento",
)


def _clean_display_document_name(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    cleaned = re.sub(r"[\x00-\x1f]+", " ", raw)
    cleaned = cleaned.replace("\\", " - ").replace("/", " - ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned


def _document_name_from_table(row: Mapping[str, Any], fields: Iterable[str], fallback_filename: str) -> str:
    fallback = _normalise_filename(fallback_filename)
    for field in fields:
        name = _clean_display_document_name(_row_value(row, field))
        if name:
            suffix = Path(fallback).suffix
            return name if Path(name).suffix or not suffix else f"{name}{suffix}"
    return fallback


def _import_visible_document_name(table_name: Any, filename: Any) -> str:
    visible = _clean_display_document_name(table_name)
    return visible or _normalise_filename(filename)


def _repair_imported_document_metadata(doc: Any, *, filename: str, table_name: str) -> bool:
    changed = False
    original_filename = _normalise_filename(filename)
    visible_name = _import_visible_document_name(table_name, original_filename)
    for attr, value in (
        ("nome", visible_name),
        ("nome_originale", original_filename),
        ("nome_portale", visible_name),
    ):
        if _text(getattr(doc, attr, "")) != value:
            setattr(doc, attr, value)
            changed = True
    if table_name and _text(getattr(doc, "tipo_atto_portale", "")) != table_name:
        setattr(doc, "tipo_atto_portale", table_name)
        changed = True
    if _text(getattr(doc, "classificazione_portale", "")) != "Gestionale precedente":
        setattr(doc, "classificazione_portale", "Gestionale precedente")
        changed = True
    tags = list(getattr(doc, "tags", []) or [])
    if "import-pratiche" not in tags:
        tags.append("import-pratiche")
        setattr(doc, "tags", tags)
        changed = True
    return changed


def _split_person_name(row: Mapping[str, Any]) -> tuple[str, str]:
    name = _text(_row_value(row, "NOME"))
    surname = _text(_row_value(row, "COGNOME"))
    if surname:
        return name, surname
    parts = name.split()
    if len(parts) >= 2:
        return " ".join(parts[1:]), parts[0]
    return "", name or "Nominativo importato"


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
    nome, cognome = _split_person_name(row)
    return f"name:{nome.casefold()}:{cognome.casefold()}"


def _is_client_control(row: Mapping[str, Any]) -> bool:
    return _text(_row_value(row, "CONTROLLO")).upper().startswith(("CLI", "OWN"))


def _role_from_subject_row(row: Mapping[str, Any], *, primary: bool = False) -> RuoloSoggetto:
    control = _text(_row_value(row, "CONTROLLO")).upper()
    if primary or control.startswith(("CLI", "OWN")):
        return RuoloSoggetto.ASSISTITO
    if control.startswith("COR"):
        return RuoloSoggetto.CORRISPONDENTE
    if control.startswith("TER"):
        return RuoloSoggetto.INTERVENIENTE
    if control.startswith("CTP"):
        return RuoloSoggetto.CONTROPARTE
    return RuoloSoggetto.CONTROPARTE


def _fallback_client_from_title(nomi_by_id: Mapping[int, Mapping[str, Any]], links: list[dict[str, Any]]) -> Mapping[str, Any] | None:
    for link in links:
        row = nomi_by_id.get(_number(_row_value(link, "NUM_NOM")))
        if row and _is_client_control(row):
            return row
    for link in links:
        row = nomi_by_id.get(_number(_row_value(link, "NUM_NOM")))
        if row:
            return row
    return None


def _existing_client_for_subject(clienti: GestioneClienti, row: Mapping[str, Any]) -> Cliente | None:
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
    return existing


def _client_from_subject(
    clienti: GestioneClienti,
    row: Mapping[str, Any],
    *,
    provenance: str,
) -> tuple[Cliente, bool]:
    tipo = _client_type(row)
    cf = _text(_row_value(row, "CODICE_FISCALE")).upper()
    piva = _text(_row_value(row, "PARTITA_IVA"))
    existing = _existing_client_for_subject(clienti, row)
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
    if not valid_piva and cf and clienti.valida_piva(cf):
        valid_piva = cf
    valid_cf = cf if cf and len(cf) == 16 and clienti.valida_cf(cf) else ""
    cliente = clienti.nuovo(
        tipo=tipo,
        ragione_sociale=_text(_row_value(row, "NOME")) or _text(_row_value(row, "COGNOME"), "Cliente importato"),
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


def _client_placeholder_from_matter(
    clienti: GestioneClienti,
    row: Mapping[str, Any],
    *,
    provenance: str,
) -> Cliente:
    title = _text(_row_value(row, "PRATICA")) or _text(_row_value(row, "OGGETTO_PRATICA")) or f"Pratica importata {_row_value(row, 'NUMEROPRATICA')}"
    expected_name = title.casefold()
    existing = next(
        (
            cliente
            for cliente in clienti.tutti()
            if _text(getattr(cliente, "nome_completo", "")).casefold() == expected_name
        ),
        None,
    )
    if existing:
        return existing
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_GIURIDICA,
        ragione_sociale=title,
        stato=StatoCliente.ATTIVO,
        provenienza=provenance,
        note="Cliente ricostruito dalla pratica importata: nel pacchetto non era presente un titolare collegato.",
        data_prima_acquisizione=_iso_date(_row_value(row, "DATA_APE")) or date.today().isoformat(),
    )
    cliente.tag = ["import-pratiche", "cliente-da-pratica"]
    return clienti.aggiorna(cliente.id, tag=cliente.tag)


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


def _agenda_kind(row: Mapping[str, Any]) -> TipoAppuntamento:
    activity_kind = _activity_kind(row)
    if activity_kind == TipoAttivita.UDIENZA:
        return TipoAppuntamento.UDIENZA
    if activity_kind == TipoAttivita.TERMINE_SCADENZA:
        return TipoAppuntamento.SCADENZA
    return TipoAppuntamento.ALTRO


def _agenda_duration(row: Mapping[str, Any]) -> int:
    explicit = _number(_row_value(row, "Duration", "DurataMinuti", "Durata"))
    if explicit > 0:
        return explicit
    start = _iso_datetime(_row_value(row, "StartDateTime"))
    end = _iso_datetime(_row_value(row, "EndDateTime", "End"))
    if start and end:
        try:
            minutes = int((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() // 60)
            if minutes > 0:
                return min(minutes, 24 * 60)
        except ValueError:
            pass
    return 60


RG_NUMBER_FIELDS = (
    "RUOLO_GEN",
    "NUMERORUOLO",
    "NUMERO_RUOLO",
    "NUM_RUOLO",
    "NUMERO_RG",
    "N_RG",
    "NRG",
    "RuoloGen",
)
RG_YEAR_FIELDS = (
    "ANNO_RUOLO_GEN",
    "ANNORUOLO",
    "ANNO_RUOLO",
    "ANNO_RG",
    "AnnoRuolo",
    "Anno_Ruolo_Gen",
)
AGENDA_RG_NUMBER_FIELDS = ("Ruolo", *RG_NUMBER_FIELDS)
AGENDA_RG_YEAR_FIELDS = (*RG_YEAR_FIELDS, "Anno_Ruolo")
RG_FULL_RE = re.compile(r"(?:\bR\.?\s*G\.?\b\s*)?(?P<number>\d{1,7})\s*/\s*(?P<year>(?:19|20)\d{2})", re.IGNORECASE)


def _normalise_rg_number(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    full = RG_FULL_RE.search(raw)
    if full:
        return str(int(full.group("number")))
    match = re.search(r"\d{1,7}", raw)
    if not match:
        return ""
    number = match.group(0)
    # Un anno isolato non e' un numero RG. Il numero interno pratica resta fuori dagli alias.
    if re.fullmatch(r"(?:19|20)\d{2}", number) and len(re.findall(r"\d+", raw)) == 1:
        return ""
    return str(int(number))


def _normalise_rg_year(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    full = RG_FULL_RE.search(raw)
    if full:
        return full.group("year")
    match = re.search(r"(?:19|20)\d{2}", raw)
    return match.group(0) if match else ""


def _rg_candidate_from_row(
    row: Mapping[str, Any],
    *,
    source: str,
    number_fields: Iterable[str],
    year_fields: Iterable[str],
) -> dict[str, str] | None:
    for number_field in number_fields:
        number_raw = _row_value(row, number_field)
        if not _text(number_raw):
            continue
        numero = _normalise_rg_number(number_raw)
        anno = _normalise_rg_year(number_raw)
        for year_field in year_fields:
            anno = anno or _normalise_rg_year(_row_value(row, year_field))
            if anno:
                break
        if numero and anno:
            return {"numero": numero, "anno": anno, "source": f"{source}.{number_field}"}
    for year_field in year_fields:
        raw = _row_value(row, year_field)
        if _normalise_rg_year(raw):
            return {"numero": "", "anno": _normalise_rg_year(raw), "source": f"{source}.{year_field}"}
    return None


def _matter_rg_info(row: Mapping[str, Any], agenda_rows: Iterable[Mapping[str, Any]] = ()) -> dict[str, Any]:
    candidate = _rg_candidate_from_row(
        row,
        source="PRATICHE",
        number_fields=RG_NUMBER_FIELDS,
        year_fields=RG_YEAR_FIELDS,
    )
    if candidate and candidate.get("numero") and candidate.get("anno"):
        return {
            **candidate,
            "label": f"RG {candidate['numero']}/{candidate['anno']}",
            "status": "acquisito",
            "missing": False,
            "action": "",
        }
    partial = candidate or {}
    for agenda_row in agenda_rows:
        agenda_candidate = _rg_candidate_from_row(
            agenda_row,
            source="AGENDA",
            number_fields=AGENDA_RG_NUMBER_FIELDS,
            year_fields=AGENDA_RG_YEAR_FIELDS,
        )
        if agenda_candidate and agenda_candidate.get("numero") and agenda_candidate.get("anno"):
            return {
                **agenda_candidate,
                "label": f"RG {agenda_candidate['numero']}/{agenda_candidate['anno']}",
                "status": "acquisito",
                "missing": False,
                "action": "",
            }
        if agenda_candidate:
            partial = partial or agenda_candidate
    return {
        "numero": _text(partial.get("numero")),
        "anno": _text(partial.get("anno")),
        "source": _text(partial.get("source"), "mancante_archivio_sorgente"),
        "label": "RG da acquisire",
        "status": "da_acquisire",
        "missing": True,
        "action": "Acquisire il numero di ruolo dal portale o da un provvedimento del fascicolo prima di deposito, notifica o scadenze operative.",
    }


def _matter_rg_label(row: Mapping[str, Any], agenda_rows: Iterable[Mapping[str, Any]] = ()) -> str:
    info = _matter_rg_info(row, agenda_rows)
    if not info.get("missing"):
        return _text(info.get("label"))
    return _text(info.get("numero"))


def _matter_counts(
    *,
    number: int,
    links_by_matter: Mapping[int, list[dict[str, Any]]],
    testi_by_matter: Mapping[int, list[dict[str, Any]]],
    emails_by_matter: Mapping[int, list[dict[str, Any]]],
    agenda_by_matter: Mapping[int, list[dict[str, Any]]],
) -> dict[str, int]:
    documenti = len(testi_by_matter.get(number, []))
    emails = len(emails_by_matter.get(number, []))
    eventi = len(agenda_by_matter.get(number, []))
    udienze = sum(1 for row in agenda_by_matter.get(number, []) if _activity_kind(row) == TipoAttivita.UDIENZA)
    return {
        "parti": len(links_by_matter.get(number, [])),
        "documenti": documenti + emails,
        "documenti_atti": documenti,
        "email": emails,
        "documenti_governati": documenti + emails,
        "depositi": 0,
        "eventi": eventi,
        "udienze": udienze,
        "appuntamenti": eventi,
    }


def _hearing_dates(rows: Iterable[Mapping[str, Any]]) -> tuple[str, str]:
    dates = sorted(
        {
            day
            for row in rows
            if _activity_kind(row) == TipoAttivita.UDIENZA
            for day in [_iso_date(_row_value(row, "StartDateTime"))]
            if day
        }
    )
    if not dates:
        return "", ""
    today = date.today().isoformat()
    future = next((day for day in dates if day >= today), "")
    return dates[0], future


def _matter_source_snapshot(
    row: Mapping[str, Any],
    *,
    number: int,
    counts: Mapping[str, int],
    first_hearing: str = "",
    next_hearing: str = "",
    party_names: Iterable[str] = (),
    rg_info: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rg_payload = dict(rg_info or _matter_rg_info(row))
    rg = _text(rg_payload.get("label")) if not rg_payload.get("missing") else ""
    return {
        "portale": "Import pratiche",
        "external_id": f"quickorganizer:{number}",
        "numero": _text(rg_payload.get("numero")),
        "anno": _number(rg_payload.get("anno")),
        "rg_label": _text(rg_payload.get("label")),
        "rg_status": _text(rg_payload.get("status")),
        "rg_missing": bool(rg_payload.get("missing")),
        "rg_source": _text(rg_payload.get("source")),
        "rg_action": _text(rg_payload.get("action")),
        "ufficio_nome": _text(_row_value(row, "AUT_GIUDIZ")),
        "ufficio_codice": "",
        "procedimento": rg or _text(_row_value(row, "PRATICA")),
        "sub_procedimento": "",
        "sezione": _text(_row_value(row, "SEZIONE")),
        "stato": _text(_row_value(row, "Stato_Pratica")),
        "oggetto": _text(_row_value(row, "OGGETTO_PRATICA")),
        "data_iscrizione": _date_it(_row_value(row, "DATA_APE")),
        "data_udienza": _date_it(next_hearing or first_hearing),
        "ultima_attivita": "",
        "acquisito_il": _datetime_it(_iso_now()),
        "parti": [name for name in party_names if name],
        "controparti": [],
        "difensori": [],
        "counts": dict(counts),
    }


def _document_rows_text(rows: Iterable[Mapping[str, Any]], *, fields: Iterable[str], filename_field: str = "NOME_DOS") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for row in rows:
        filename = _normalise_filename(_row_value(row, filename_field))
        title = _document_name_from_table(row, fields, filename) if filename else _clean_display_document_name(_row_value(row, "Subject", "NOME_ATTO", "Oggetto"))
        text = " ".join(part for part in (title, filename) if part)
        if text:
            out.append((title or filename, text.casefold()))
    return out


def _first_document_match(rows: list[tuple[str, str]], *tokens: str) -> str:
    for title, text in rows:
        if all(token in text for token in tokens):
            return title
    return ""


def _payment_seed(
    *,
    kind: str,
    status: str,
    note: str,
    document_source: str = "",
    amount: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": kind,
        "status": status,
        "previsto": status != "non_previsto",
        "pagato": status == "pagato",
        "valuta": "EUR",
        "origine": "Import pratiche",
        "updated_at": _iso_now(),
        "updated_by": "Import pratiche",
        "note": note,
    }
    if amount is not None:
        payload["importo"] = round(float(amount), 2)
    if document_source:
        payload["documento_fonte"] = document_source
    return payload


def _merge_import_economic_context(
    existing: Mapping[str, Any] | None,
    row: Mapping[str, Any],
    *,
    docs_rows: Iterable[Mapping[str, Any]],
    email_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    payments = dict(existing or {})
    valore = _decimal(_row_value(row, "VALORE"))
    document_texts = _document_rows_text(docs_rows, fields=DOCUMENT_TITLE_FIELDS)
    email_texts = _document_rows_text(email_rows, fields=EMAIL_TITLE_FIELDS)
    all_texts = document_texts + email_texts
    contributo_doc = _first_document_match(all_texts, "contribut")
    spese_doc = _first_document_match(all_texts, "spes") or _first_document_match(all_texts, "esbors")
    parcella_doc = (
        _first_document_match(all_texts, "parcell")
        or _first_document_match(all_texts, "fattur")
        or _first_document_match(all_texts, "proforma")
    )
    if "contesto_economico" not in payments:
        payments["contesto_economico"] = costruisci_contesto_economico(
            source="import_pratiche",
            source_label="Import pratiche",
            oggetto=_text(_row_value(row, "OGGETTO_PRATICA")) or _text(_row_value(row, "PRATICA")),
            id_pratica=f"quickorganizer:{_number(_row_value(row, 'NUMEROPRATICA'))}",
            pratica_label=_text(_row_value(row, "PRATICA")),
            tipo_procedimento=_text(_row_value(row, "OGGETTO_PRATICA")),
            grado_sede=_text(_row_value(row, "AUT_GIUDIZ")),
            valore_controversia=valore,
        )
    if "contributo_unificato" not in payments:
        payments["contributo_unificato"] = _payment_seed(
            kind="contributo_unificato",
            status="da_registrare",
            document_source=contributo_doc,
            note=(
                "Presidio creato automaticamente dall'import pratiche; "
                "verificare ricevuta PagoPA/contributo nel fascicolo importato."
            ),
        )
    if spese_doc and "spese_esborsi" not in payments:
        payments["spese_esborsi"] = _payment_seed(
            kind="spese_esborsi",
            status="da_registrare",
            document_source=spese_doc,
            note="Voce economica rilevata automaticamente dai documenti importati.",
        )
    if "parcella" not in payments:
        payments["parcella"] = _payment_seed(
            kind="parcella",
            status="da_emettere",
            document_source=parcella_doc,
            amount=None,
            note="Presidio parcella creato automaticamente dall'import pratiche.",
        )
    return payments


def _sync_agenda_from_import(
    agenda: Agenda,
    *,
    row: Mapping[str, Any],
    matter: Any,
    matter_row: Mapping[str, Any],
    client_name: str,
    actor: str,
) -> tuple[str, bool]:
    task_id = _number(_row_value(row, "TaskID"))
    start = _iso_datetime(_row_value(row, "StartDateTime"))
    if not start:
        return "", False
    title = _text(_row_value(row, "Subject"), "Appuntamento importato")
    uid_seed = task_id or hashlib.sha1(f"{getattr(matter, 'id', '')}|{start}|{title}".encode("utf-8")).hexdigest()[:12]
    marker = f"quickorganizer:agenda:{uid_seed}"
    rg = _matter_rg_label(matter_row, [row])
    description_parts = [
        _text(_row_value(row, "Description")),
        _text(_row_value(row, "Provvedimento")),
        f"Fascicolo importato: {_text(getattr(matter, 'titolo', ''))}",
        f"Riferimento: {_text(getattr(matter, 'source_external_id', ''))}",
    ]
    event = EventoImportato(
        uid=marker,
        titolo=title,
        data_ora=start,
        durata_minuti=_agenda_duration(row),
        tutto_giorno=False,
        luogo=_text(_row_value(row, "Location")),
        descrizione=" | ".join(part for part in description_parts if part),
        stato_ical="CONFIRMED",
        organizzatore=actor,
    )
    report = agenda.upsert_da_evento_importato(
        event,
        provider="import_pratiche",
        source_url=_text(getattr(matter, "source_external_id", "")),
        profile_id=f"fascicolo:{_text(getattr(matter, 'id', ''))}",
        default_tipo=_agenda_kind(row),
        reminder_minuti=60,
        allow_overlap=True,
    )
    appuntamento = report.get("appuntamento")
    agenda_id = _text(getattr(appuntamento, "id", ""))
    if agenda_id:
        agenda.modifica(
            agenda_id,
            cliente=client_name,
            id_cliente=_text(getattr(matter, "id_cliente", "")),
            procedimento=" ".join(part for part in (rg, _text(getattr(matter, "source_external_id", ""))) if part),
            tribunale=_text(getattr(matter, "tribunale", "")),
            avvocato=actor,
        )
    return agenda_id, str(report.get("outcome") or "") in {"created", "updated"}


def import_quickorganizer_package(
    package: QuickOrganizerPackage,
    *,
    fascicoli: GestioneFascicoli,
    clienti: GestioneClienti,
    soggetti: GestioneSoggetti,
    agenda_repo: Agenda | None = None,
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
    agenda_rows = package.table("AGENDA")
    nomi_by_id = {_number(_row_value(row, "NUM_NOM")): row for row in nomi}
    links_by_matter: dict[int, list[dict[str, Any]]] = {}
    for link in tavola:
        links_by_matter.setdefault(_number(_row_value(link, "NUMEROPRATICA")), []).append(link)
    testi_by_matter: dict[int, list[dict[str, Any]]] = {}
    for row in testi:
        testi_by_matter.setdefault(_number(_row_value(row, "NUMEROPRATICA")), []).append(row)
    emails_by_matter: dict[int, list[dict[str, Any]]] = {}
    for row in emails:
        emails_by_matter.setdefault(_number(_row_value(row, "NumeroPratica")), []).append(row)
    agenda_by_matter: dict[int, list[dict[str, Any]]] = {}
    for row in agenda_rows:
        agenda_by_matter.setdefault(_number(_row_value(row, "NumeroPratica")), []).append(row)

    subject_index = _existing_subject_index(soggetti)
    subject_ids_by_num: dict[int, str] = {}
    client_ids_by_num: dict[int, str] = {}
    counters = {
        "clientsCreated": 0,
        "subjectsCreated": 0,
        "partyLinksCreated": 0,
        "mattersCreated": 0,
        "mattersUpdated": 0,
        "documentsImported": 0,
        "documentsMissing": 0,
        "documentsMetadataRepaired": 0,
        "emailsImported": 0,
        "emailsMissing": 0,
        "emailsMetadataRepaired": 0,
        "activitiesImported": 0,
        "appointmentsImported": 0,
        "economicContextsPrepared": 0,
        "sourceContextsPrepared": 0,
        "mattersWithRg": 0,
        "mattersWithoutRg": 0,
        "mattersRgFromAgenda": 0,
        "duplicatesSkipped": 0,
    }
    errors: list[str] = []
    save_guard = _deferred_repository_saves(
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
        agenda=agenda_repo,
    )
    save_guard.__enter__()
    reader_guard = _package_file_reader(package)
    read_package_file = reader_guard.__enter__()

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
        if _is_client_control(row):
            try:
                client, created = _client_from_subject(clienti, row, provenance="Import pratiche")
                client_ids_by_num[num] = client.id
                counters["clientsCreated"] += 1 if created else 0
            except Exception:
                errors.append(f"Cliente nominativo {num}: import non completato per dati non coerenti.")

    matters_by_number: dict[int, Any] = {}
    matter_id_by_number: dict[int, str] = {}
    pratiche_by_number = {_number(_row_value(row, "NUMEROPRATICA")): row for row in pratiche}
    for row in pratiche:
        number = _number(_row_value(row, "NUMEROPRATICA"))
        source_external_id = f"quickorganizer:{number}"
        client_id = ""
        client_name = _text(_row_value(row, "TitolareName"))
        titolare_id = _number(_row_value(row, "TitolareID"))
        matter_links = links_by_matter.get(number, [])
        client_row = nomi_by_id.get(titolare_id) or _fallback_client_from_title(nomi_by_id, matter_links)
        if client_row:
            try:
                client_num = _number(_row_value(client_row, "NUM_NOM"))
                client = clienti.get(client_ids_by_num.get(client_num, "")) if client_num else None
                created = False
                if client is None:
                    client, created = _client_from_subject(clienti, client_row, provenance="Import pratiche")
                    if client_num:
                        client_ids_by_num[client_num] = client.id
                client_id = client.id
                client_name = client.nome_completo
                counters["clientsCreated"] += 1 if created else 0
            except Exception as exc:  # noqa: BLE001 - import deve proseguire sui fascicoli
                errors.append(f"Cliente pratica {number}: import non completato per dati non coerenti.")
        if not client_id:
            client = _client_placeholder_from_matter(
                clienti,
                row,
                provenance="Import pratiche",
            )
            client_id = client.id
            client_name = client.nome_completo
            counters["clientsCreated"] += 1
        existing = _existing_matter_by_source(fascicoli, source_external_id)
        matter_agenda_rows = agenda_by_matter.get(number, [])
        rg_info = _matter_rg_info(row, matter_agenda_rows)
        if rg_info.get("missing"):
            counters["mattersWithoutRg"] += 1
        else:
            counters["mattersWithRg"] += 1
            if _text(rg_info.get("source")).startswith("AGENDA."):
                counters["mattersRgFromAgenda"] += 1
        first_hearing, next_hearing = _hearing_dates(matter_agenda_rows)
        source_counts = _matter_counts(
            number=number,
            links_by_matter=links_by_matter,
            testi_by_matter=testi_by_matter,
            emails_by_matter=emails_by_matter,
            agenda_by_matter=agenda_by_matter,
        )
        party_names = []
        for link in matter_links:
            subject_row = nomi_by_id.get(_number(_row_value(link, "NUM_NOM"))) or {}
            full_name = " ".join(
                part
                for part in (
                    _text(_row_value(subject_row, "COGNOME")),
                    _text(_row_value(subject_row, "NOME")),
                )
                if part
            )
            if full_name:
                party_names.append(full_name)
        existing_payments = getattr(existing, "pagamenti", {}) if existing else {}
        import_payments = _merge_import_economic_context(
            existing_payments if isinstance(existing_payments, Mapping) else {},
            row,
            docs_rows=testi_by_matter.get(number, []),
            email_rows=emails_by_matter.get(number, []),
        )
        payload = {
            "stato": _matter_status(row),
            "id_cliente": client_id,
            "nome_cliente": client_name,
            "controparte": _text(_row_value(row, "ConvenutoPrincipale")),
            "tribunale": _text(_row_value(row, "AUT_GIUDIZ")),
            "numero_rg": _text(rg_info.get("numero")),
            "anno_rg": _number(rg_info.get("anno")),
            "sezione": _text(_row_value(row, "SEZIONE")),
            "giudice": _text(_row_value(row, "ISTRUTTORE")),
            "cancelliere": _text(_row_value(row, "CANCELL")),
            "ctu": _text(_row_value(row, "CTU")),
            "ctp": _text(_row_value(row, "CTP")),
            "oggetto": _text(_row_value(row, "OGGETTO_PRATICA")),
            "valore_causa": _decimal(_row_value(row, "VALORE")),
            "documenti_iniziali_count": source_counts["documenti_atti"],
            "email_iniziali_count": source_counts["email"],
            "riferimento_cartaceo": _text(_row_value(row, "RIF")),
            "attore_principale": _text(_row_value(row, "AttorePrincipale")),
            "stato_pratica_operativa": _text(_row_value(row, "Stato_Pratica")),
            "data_apertura": _iso_date(_row_value(row, "DATA_APE")) or date.today().isoformat(),
            "data_chiusura": _iso_date(_row_value(row, "DATA_ARC")),
            "data_prima_udienza": first_hearing or _text(getattr(existing, "data_prima_udienza", "")),
            "data_prossima_udienza": next_hearing or _text(getattr(existing, "data_prossima_udienza", "")),
            "note": _text(_row_value(row, "NOTE")),
            "pagamenti": import_payments,
            "source": "IMPORT_PRATICHE",
            "source_external_id": source_external_id,
            "sync_status": "IMPORTATO",
            "last_sync_at": _iso_now(),
            "events_sync_enabled": True,
            "source_snapshot": _matter_source_snapshot(
                row,
                number=number,
                counts=source_counts,
                first_hearing=first_hearing,
                next_hearing=next_hearing,
                party_names=party_names,
                rg_info=rg_info,
            ),
        }
        counters["economicContextsPrepared"] += 1
        counters["sourceContextsPrepared"] += 1
        if existing:
            matter = fascicoli.aggiorna(existing.id, **payload)
            counters["mattersUpdated"] += 1
        else:
            title = _text(_row_value(row, "PRATICA")) or _text(_row_value(row, "OGGETTO_PRATICA")) or f"Pratica importata {number}"
            matter = fascicoli.nuovo(
                titolo=title,
                tipo=_matter_type(row),
                **payload,
            )
            matter = fascicoli.aggiorna(matter.id, **payload)
            counters["mattersCreated"] += 1
        matters_by_number[number] = matter
        matter_id_by_number[number] = matter.id

        for link in matter_links:
            subject_num = _number(_row_value(link, "NUM_NOM"))
            subject_id = subject_ids_by_num.get(subject_num)
            if not subject_id:
                continue
            subject_row = nomi_by_id.get(subject_num) or {}
            role = _role_from_subject_row(subject_row, primary=subject_num == titolare_id)
            before = len(soggetti.parti_fascicolo(matter.id))
            soggetti.aggiungi_parte(
                matter.id,
                subject_id,
                role,
                note=f"Import pratiche: pratica {number}",
            )
            after = len(soggetti.parti_fascicolo(matter.id))
            counters["partyLinksCreated"] += max(after - before, 0)

    for row in testi:
        matter_number = _number(_row_value(row, "NUMEROPRATICA"))
        matter_id = matter_id_by_number.get(matter_number)
        filename = _normalise_filename(_row_value(row, "NOME_DOS"))
        if not matter_id or not filename:
            continue
        matter = fascicoli.get(matter_id)
        external_id = f"quickorganizer:testi:{_number(_row_value(row, 'Counter')) or filename}"
        table_document_name = _document_name_from_table(row, DOCUMENT_TITLE_FIELDS, filename)
        existing_doc = next(
            (
                doc
                for doc in getattr(matter, "documenti", [])
                if _text(getattr(doc, "id_documento_portale", "")) == external_id
            ),
            None,
        )
        if existing_doc:
            if _repair_imported_document_metadata(existing_doc, filename=filename, table_name=table_document_name):
                counters["documentsMetadataRepaired"] += 1
            counters["duplicatesSkipped"] += 1
            continue
        source_file = _find_file(package, filename, section="ATTI")
        if not source_file:
            counters["documentsMissing"] += 1
            continue
        data = read_package_file(source_file)
        document_name = _import_visible_document_name(table_document_name, filename)
        fascicoli.aggiungi_documento(
            matter_id,
            document_name,
            _document_type(table_document_name, filename),
            data,
            note=f"Import pratiche. {table_document_name}",
            tags=["import-pratiche"],
            data_documento=_iso_date(_row_value(row, "DATA_ATTO")),
            firmato=_bool(_row_value(row, "signed")),
            caricato_da=actor,
            fonte_documento="IMPORT_ESTERNO",
            nome_originale=filename,
            nome_portale=document_name,
            classificazione_portale="Gestionale precedente",
            tipo_atto_portale=table_document_name,
            id_documento_portale=external_id,
            nome_archivio=filename,
        )
        counters["documentsImported"] += 1

    for row in emails:
        matter_number = _number(_row_value(row, "NumeroPratica"))
        matter_id = matter_id_by_number.get(matter_number)
        filename = _normalise_filename(_row_value(row, "NOME_DOS"))
        if not matter_id or not filename:
            continue
        matter = fascicoli.get(matter_id)
        external_id = f"quickorganizer:email:{_number(_row_value(row, 'Email_ID')) or filename}"
        table_document_name = _document_name_from_table(row, EMAIL_TITLE_FIELDS, filename)
        existing_doc = next(
            (
                doc
                for doc in getattr(matter, "documenti", [])
                if _text(getattr(doc, "id_documento_portale", "")) == external_id
            ),
            None,
        )
        if existing_doc:
            if _repair_imported_document_metadata(existing_doc, filename=filename, table_name=table_document_name):
                counters["emailsMetadataRepaired"] += 1
            counters["duplicatesSkipped"] += 1
            continue
        source_file = _find_file(package, filename, section="EMAILS")
        if not source_file:
            counters["emailsMissing"] += 1
            continue
        data = read_package_file(source_file)
        subject = _text(_row_value(row, "Subject"), filename)
        document_name = _import_visible_document_name(table_document_name, filename)
        fascicoli.aggiungi_documento(
            matter_id,
            document_name,
            TipoDocumento.COMUNICAZIONE,
            data,
            note=f"Email importata dal pacchetto pratiche. Oggetto: {subject}",
            tags=["import-pratiche", "email"],
            data_documento=_iso_date(_row_value(row, "Data")),
            firmato=_bool(_row_value(row, "IsSigned")),
            caricato_da=actor,
            fonte_documento="IMPORT_ESTERNO",
            nome_originale=filename,
            nome_portale=document_name,
            classificazione_portale="Gestionale precedente",
            tipo_atto_portale=table_document_name,
            mittente_portale=_text(_row_value(row, "Mittente")),
            id_documento_portale=external_id,
            nome_archivio=filename,
        )
        counters["emailsImported"] += 1

    for row in agenda_rows:
        matter_number = _number(_row_value(row, "NumeroPratica"))
        matter_id = matter_id_by_number.get(matter_number)
        if not matter_id:
            continue
        task_id = _number(_row_value(row, "TaskID"))
        matter = fascicoli.get(matter_id)
        marker = f"[quickorganizer:agenda:{task_id}]"
        existing_activity = next(
            (
                activity
                for activity in getattr(matter, "attivita", [])
                if marker in _text(getattr(activity, "note", ""))
            ),
            None,
        )
        agenda_id = ""
        if agenda_repo is not None:
            agenda_id, changed = _sync_agenda_from_import(
                agenda_repo,
                row=row,
                matter=matter,
                matter_row=pratiche_by_number.get(matter_number, {}),
                client_name=_text(getattr(matter, "nome_cliente", "")),
                actor=actor,
            )
            if changed:
                counters["appointmentsImported"] += 1
        if existing_activity:
            if agenda_id and not _text(getattr(existing_activity, "id_appuntamento", "")):
                existing_activity.id_appuntamento = agenda_id
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
            note=f"{marker} Import pratiche. {_text(_row_value(row, 'Provvedimento'))}",
            id_appuntamento=agenda_id,
            avvocato=actor,
        )
        counters["activitiesImported"] += 1

    reader_guard.__exit__(None, None, None)
    save_guard.__exit__(None, None, None)

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


def _append_audit_failure(failures: list[dict[str, str]], code: str, message: str, *, limit: int = 40) -> None:
    if len(failures) < limit:
        failures.append({"code": code, "message": message})


def audit_quickorganizer_import(
    package: QuickOrganizerPackage,
    *,
    fascicoli: GestioneFascicoli,
    clienti: GestioneClienti,
    soggetti: GestioneSoggetti,
    agenda_repo: Agenda | None = None,
) -> dict[str, Any]:
    pratiche = package.table("PRATICHE")
    nomi = package.table("NOMI")
    tavola = package.table("TAVOLA")
    testi = package.table("TESTI")
    emails = package.table("EMAILS")
    agenda = package.table("AGENDA")
    nomi_by_id = {_number(_row_value(row, "NUM_NOM")): row for row in nomi}
    subject_index = _existing_subject_index(soggetti)
    matters = {
        _text(getattr(item, "source_external_id", "")): item
        for item in fascicoli.tutti(stato=None, archiviati=True)
        if _text(getattr(item, "source_external_id", ""))
    }
    failures: list[dict[str, str]] = []
    expected = {
        "matters": 0,
        "clients": 0,
        "clientsLinked": 0,
        "subjects": 0,
        "partyLinks": 0,
        "documents": 0,
        "emails": 0,
        "activities": 0,
        "economicContexts": 0,
        "sourceContexts": 0,
    }
    if agenda_repo is not None:
        expected["agendaAppointments"] = 0
    found = dict.fromkeys(expected, 0)

    subject_rows_by_identity: dict[str, Mapping[str, Any]] = {}
    client_rows_by_identity: dict[str, Mapping[str, Any]] = {}
    for row in nomi:
        identity = _subject_identity(row)
        subject_rows_by_identity.setdefault(identity, row)
        if _is_client_control(row):
            client_rows_by_identity.setdefault(identity, row)

    for identity, row in subject_rows_by_identity.items():
        expected["subjects"] += 1
        if subject_index.get(identity):
            found["subjects"] += 1
        else:
            _append_audit_failure(
                failures,
                "soggetto_mancante",
                f"Soggetto importato { _row_value(row, 'NUM_NOM') } non trovato negli archivi IUSENTRA.",
            )

    for row in client_rows_by_identity.values():
        expected["clients"] += 1
        if _existing_client_for_subject(clienti, row):
            found["clients"] += 1
        else:
            _append_audit_failure(
                failures,
                "cliente_nominativo_mancante",
                f"Cliente importato { _row_value(row, 'NUM_NOM') } non trovato negli archivi IUSENTRA.",
            )

    matter_id_by_number: dict[int, str] = {}
    for row in pratiche:
        number = _number(_row_value(row, "NUMEROPRATICA"))
        expected["matters"] += 1
        matter = matters.get(f"quickorganizer:{number}")
        if not matter:
            _append_audit_failure(
                failures,
                "fascicolo_mancante",
                f"Pratica importata {number} non trovata come fascicolo importato.",
            )
            continue
        found["matters"] += 1
        matter_id_by_number[number] = matter.id
        expected["economicContexts"] += 1
        pagamenti = getattr(matter, "pagamenti", {}) or {}
        contesto = pagamenti.get("contesto_economico") if isinstance(pagamenti, Mapping) else None
        if isinstance(contesto, Mapping) and _text(contesto.get("source")) == "import_pratiche":
            found["economicContexts"] += 1
        else:
            _append_audit_failure(
                failures,
                "contesto_economico_mancante",
                f"Pratica importata {number} senza contesto economico automatico.",
            )
        expected["sourceContexts"] += 1
        source_snapshot = getattr(matter, "source_snapshot", {}) or {}
        counts = source_snapshot.get("counts") if isinstance(source_snapshot, Mapping) else None
        if (
            isinstance(source_snapshot, Mapping)
            and _text(source_snapshot.get("portale")) == "Import pratiche"
            and isinstance(counts, Mapping)
        ):
            found["sourceContexts"] += 1
        else:
            _append_audit_failure(
                failures,
                "contesto_sorgente_mancante",
                f"Pratica importata {number} senza contesto sorgente e conteggi import.",
            )
        expected["clientsLinked"] += 1
        linked_client = clienti.get(_text(getattr(matter, "id_cliente", "")))
        if linked_client and _text(getattr(matter, "nome_cliente", "")):
            found["clientsLinked"] += 1
        else:
            _append_audit_failure(
                failures,
                "cliente_pratica_mancante",
                f"Pratica importata {number} senza cliente collegato.",
            )

    for link in tavola:
        matter_number = _number(_row_value(link, "NUMEROPRATICA"))
        matter_id = matter_id_by_number.get(matter_number)
        subject_row = nomi_by_id.get(_number(_row_value(link, "NUM_NOM")))
        if not matter_id or not subject_row:
            continue
        expected["partyLinks"] += 1
        subject_id = subject_index.get(_subject_identity(subject_row))
        parties = soggetti.parti_fascicolo(matter_id)
        if subject_id and any(_text(getattr(parte, "id_soggetto", "")) == subject_id for parte, _soggetto in parties):
            found["partyLinks"] += 1
        else:
            _append_audit_failure(
                failures,
                "parte_pratica_mancante",
                f"Collegamento parte mancante per pratica {matter_number} e soggetto { _row_value(link, 'NUM_NOM') }.",
            )

    docs_by_matter: dict[str, dict[str, Any]] = {}
    for matter in matters.values():
        docs_by_matter[matter.id] = {
            _text(getattr(doc, "id_documento_portale", "")): doc
            for doc in getattr(matter, "documenti", [])
            if _text(getattr(doc, "id_documento_portale", ""))
        }

    for row in testi:
        matter_number = _number(_row_value(row, "NUMEROPRATICA"))
        matter_id = matter_id_by_number.get(matter_number)
        filename = _normalise_filename(_row_value(row, "NOME_DOS"))
        if not matter_id or not filename:
            continue
        expected["documents"] += 1
        external_id = f"quickorganizer:testi:{_number(_row_value(row, 'Counter')) or filename}"
        doc = docs_by_matter.get(matter_id, {}).get(external_id)
        expected_name = _document_name_from_table(row, DOCUMENT_TITLE_FIELDS, filename)
        if (
            doc
            and _text(getattr(doc, "nome", "")) == expected_name
            and _text(getattr(doc, "nome_originale", "")) == filename
            and _text(getattr(doc, "nome_portale", "")) == expected_name
            and (not expected_name or _text(getattr(doc, "tipo_atto_portale", "")) == expected_name)
        ):
            found["documents"] += 1
        else:
            _append_audit_failure(
                failures,
                "documento_non_allineato",
                f"Documento {filename} della pratica {matter_number} non trovato con titolo Studio Telematico {expected_name}.",
            )

    for row in emails:
        matter_number = _number(_row_value(row, "NumeroPratica"))
        matter_id = matter_id_by_number.get(matter_number)
        filename = _normalise_filename(_row_value(row, "NOME_DOS"))
        if not matter_id or not filename:
            continue
        expected["emails"] += 1
        external_id = f"quickorganizer:email:{_number(_row_value(row, 'Email_ID')) or filename}"
        doc = docs_by_matter.get(matter_id, {}).get(external_id)
        expected_name = _document_name_from_table(row, EMAIL_TITLE_FIELDS, filename)
        if (
            doc
            and _text(getattr(doc, "nome", "")) == expected_name
            and _text(getattr(doc, "nome_originale", "")) == filename
            and _text(getattr(doc, "nome_portale", "")) == expected_name
            and (not expected_name or _text(getattr(doc, "tipo_atto_portale", "")) == expected_name)
        ):
            found["emails"] += 1
        else:
            _append_audit_failure(
                failures,
                "email_non_allineata",
                f"Email {filename} della pratica {matter_number} non trovata con oggetto Studio Telematico {expected_name}.",
            )

    for row in agenda:
        matter_number = _number(_row_value(row, "NumeroPratica"))
        matter_id = matter_id_by_number.get(matter_number)
        if not matter_id:
            continue
        task_id = _number(_row_value(row, "TaskID"))
        marker = f"[quickorganizer:agenda:{task_id}]"
        expected["activities"] += 1
        matter = next((item for item in matters.values() if item.id == matter_id), None)
        if matter and any(marker in _text(getattr(activity, "note", "")) for activity in getattr(matter, "attivita", [])):
            found["activities"] += 1
        else:
            _append_audit_failure(
                failures,
                "agenda_non_allineata",
                f"Appuntamento importato {task_id} non trovato nella pratica {matter_number}.",
            )
        if agenda_repo is not None and _iso_datetime(_row_value(row, "StartDateTime")):
            expected["agendaAppointments"] += 1
            external_uid = f"quickorganizer:agenda:{task_id or ''}"
            matter_source = f"quickorganizer:{matter_number}"
            appuntamento = next(
                (
                    item
                    for item in agenda_repo.tutti()
                    if _text(getattr(item, "external_provider", "")) == "import_pratiche"
                    and (
                        _text(getattr(item, "external_uid", "")) == external_uid
                        or matter_source in _text(getattr(item, "procedimento", ""))
                        or matter_source == _text(getattr(item, "external_source_url", ""))
                    )
                ),
                None,
            )
            if appuntamento:
                found["agendaAppointments"] += 1
            else:
                _append_audit_failure(
                    failures,
                    "appuntamento_agenda_mancante",
                    f"Appuntamento Agenda {task_id} della pratica {matter_number} non sincronizzato nel calendario.",
                )

    return {
        "ok": not failures and expected == found,
        "generatedAt": _iso_now(),
        "expected": expected,
        "found": found,
        "failures": failures,
    }


def staging_root_for_anchor(anchor_path: str | Path) -> Path:
    anchor = Path(anchor_path)
    base = anchor.parent if anchor.suffix else anchor
    return base / "importazioni" / "quickorganizer"


def _fast_source_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"local-size:{stat.st_size}:mtime:{int(stat.st_mtime)}"


def stage_uploaded_package(
    source_path: str | Path,
    staging_root: str | Path,
    *,
    move_source: bool = False,
    source_name: str = "",
    source_sha256: str = "",
) -> dict[str, Any]:
    source = _safe_existing_file(
        source_path,
        allowed_suffixes=PACKAGE_SUFFIXES,
        extra_roots=(staging_root,),
    )
    import_id = uuid.uuid4().hex
    root = _safe_runtime_dir(staging_root, create=True)
    target_dir = _safe_child_path(root, import_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = _safe_child_path(target_dir, f"source{source.suffix.lower() or '.zip'}")
    # lgtm[py/path-injection] Sorgente e destinazione sono state validate sotto radici runtime consentite.
    if move_source:
        shutil.move(str(source), str(target_path))
    else:
        shutil.copy2(source, target_path)
    staged_package = load_quickorganizer_package(target_path)
    analysis = analyze_quickorganizer_package(staged_package)
    stage_payload = {
        "importId": import_id,
        "sourceName": source_name or source.name,
        "sourceSha256": source_sha256 or _sha256_file(target_path),
        "createdAt": _iso_now(),
        "analysis": analysis,
    }
    _safe_child_path(target_dir, "stage.json").write_text(
        json.dumps(stage_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return stage_payload


def begin_chunked_upload(
    filename: str,
    total_size: int,
    staging_root: str | Path,
    *,
    chunk_size: int = DEFAULT_CHUNK_UPLOAD_SIZE_BYTES,
    max_size: int | None = None,
) -> dict[str, Any]:
    total = int(total_size or 0)
    max_bytes = int(max_size or max_chunked_upload_bytes())
    if total <= 0:
        raise QuickOrganizerImportError("Dimensione pacchetto non valida.")
    if total > max_bytes:
        raise QuickOrganizerImportError("Il pacchetto supera la dimensione massima consentita.")
    public_name = _public_upload_name(filename)
    safe_chunk_size = max(1, int(chunk_size or DEFAULT_CHUNK_UPLOAD_SIZE_BYTES))
    total_chunks = max(1, (total + safe_chunk_size - 1) // safe_chunk_size)
    upload_id = uuid.uuid4().hex
    session = _chunk_session_dir(staging_root, upload_id, create=True)
    _chunk_parts_dir(staging_root, upload_id, create=True)
    metadata = {
        "uploadId": upload_id,
        "filename": public_name,
        "totalSize": total,
        "chunkSizeBytes": safe_chunk_size,
        "totalChunks": total_chunks,
        "received": [],
        "createdAt": _iso_now(),
    }
    _safe_child_path(session, "metadata.json", extra_roots=(_safe_runtime_dir(staging_root),)).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata


def receive_chunked_upload(
    staging_root: str | Path,
    upload_id: str,
    index: int,
    total_chunks: int,
    file_storage: Any,
) -> dict[str, Any]:
    metadata = _read_chunk_metadata(staging_root, upload_id)
    expected_total = int(metadata.get("totalChunks") or 0)
    index_int = int(index)
    if int(total_chunks or expected_total) != expected_total:
        raise QuickOrganizerImportError("Numero blocchi non coerente con la sessione.")
    if index_int < 0 or index_int >= expected_total:
        raise QuickOrganizerImportError("Blocco di caricamento fuori sequenza.")
    target = _chunk_path(staging_root, upload_id, index_int)
    # lgtm[py/path-injection] Blocco salvato in sessione upload validata con indice numerico.
    file_storage.save(target)
    received = sorted({int(item) for item in metadata.get("received", []) if str(item).isdigit()} | {index_int})
    metadata["received"] = received
    _chunk_metadata_path(staging_root, upload_id).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "ok": True,
        "uploadId": metadata["uploadId"],
        "receivedChunks": len(received),
        "totalChunks": expected_total,
        "complete": len(received) == expected_total,
    }


def complete_chunked_upload(
    staging_root: str | Path,
    upload_id: str,
    *,
    total_chunks: int | None = None,
) -> dict[str, Any]:
    metadata = _read_chunk_metadata(staging_root, upload_id)
    expected_total = int(metadata.get("totalChunks") or 0)
    if total_chunks is not None and int(total_chunks) != expected_total:
        raise QuickOrganizerImportError("Numero blocchi non coerente con la sessione.")
    received = {int(item) for item in metadata.get("received", []) if str(item).isdigit()}
    missing = [index for index in range(expected_total) if index not in received]
    if missing:
        raise QuickOrganizerImportError("Caricamento incompleto: mancano alcuni blocchi del pacchetto.")
    session = _chunk_session_dir(staging_root, upload_id)
    suffix = _safe_upload_suffix(metadata.get("filename"))
    assembled = _safe_child_path(session, f"assembled{suffix}", extra_roots=(_safe_runtime_dir(staging_root),))
    digest = hashlib.sha256()
    staged = False
    try:
        with assembled.open("wb") as output:
            for index in range(expected_total):
                part = _chunk_path(staging_root, upload_id, index)
                with part.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                        output.write(chunk)
        expected_size = int(metadata.get("totalSize") or 0)
        actual_size = assembled.stat().st_size
        if actual_size != expected_size:
            raise QuickOrganizerImportError("Il pacchetto ricomposto non corrisponde alla dimensione attesa.")
        stage = stage_uploaded_package(
            assembled,
            staging_root,
            move_source=True,
            source_name=str(metadata.get("filename") or "pacchetto.zip"),
            source_sha256=digest.hexdigest(),
        )
        staged = True
        return stage
    finally:
        # Se lo staging fallisce, il pacchetto ricomposto resta disponibile per audit e recupero.
        if staged:
            shutil.rmtree(session, ignore_errors=True)


def _safe_prepare_session_id(session_id: Any) -> str:
    value = _text(session_id).lower()
    if not re.fullmatch(r"[a-f0-9]{32}", value):
        raise QuickOrganizerImportError("Sessione preparazione non riconosciuta.")
    return value


def _prepare_token_hash(token: str) -> str:
    return hashlib.sha256(_text(token).encode("utf-8")).hexdigest()


def _prepare_sessions_dir(index_root: str | Path, *, create: bool = False) -> Path:
    root = _safe_runtime_dir(index_root, create=True)
    sessions = _safe_child_path(root, "_auto_prepare_sessions", extra_roots=(root,))
    if create:
        sessions.mkdir(parents=True, exist_ok=True)
    return sessions


def _prepare_session_dir(index_root: str | Path, session_id: str, *, create: bool = False) -> Path:
    sessions = _prepare_sessions_dir(index_root, create=True)
    session = _safe_child_path(sessions, _safe_prepare_session_id(session_id), extra_roots=(sessions,))
    if create:
        session.mkdir(parents=True, exist_ok=True)
    return session


def _prepare_metadata_path(index_root: str | Path, session_id: str) -> Path:
    return _safe_child_path(
        _prepare_session_dir(index_root, session_id),
        "metadata.json",
        extra_roots=(_prepare_sessions_dir(index_root),),
    )


def _parse_utc_datetime(value: Any) -> datetime | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _prepare_session_expired(metadata: Mapping[str, Any]) -> bool:
    expires = _parse_utc_datetime(metadata.get("expiresAt"))
    return bool(expires and expires < datetime.now(timezone.utc))


def _read_prepare_metadata(index_root: str | Path, session_id: str) -> dict[str, Any]:
    path = _prepare_metadata_path(index_root, session_id)
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise QuickOrganizerImportError("Sessione preparazione scaduta o non trovata.") from exc
    except Exception as exc:
        raise QuickOrganizerImportError("Sessione preparazione non valida.") from exc
    if not isinstance(metadata, dict):
        raise QuickOrganizerImportError("Sessione preparazione non valida.")
    if _prepare_session_expired(metadata):
        raise QuickOrganizerImportError("Sessione preparazione scaduta. Avvia di nuovo la preparazione.")
    return metadata


def _write_prepare_metadata(index_root: str | Path, session_id: str, metadata: Mapping[str, Any]) -> None:
    path = _prepare_metadata_path(index_root, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(metadata), ensure_ascii=False, indent=2), encoding="utf-8")


def _public_prepare_status(metadata: Mapping[str, Any]) -> dict[str, Any]:
    stage = metadata.get("stage") if isinstance(metadata.get("stage"), Mapping) else None
    public: dict[str, Any] = {
        "ok": True,
        "sessionId": _text(metadata.get("sessionId")),
        "status": _text(metadata.get("status"), "pending"),
        "progress": max(0, min(100, _number(metadata.get("progress")))),
        "detail": _text(metadata.get("detail")),
        "createdAt": _text(metadata.get("createdAt")),
        "expiresAt": _text(metadata.get("expiresAt")),
        "uploadId": _text(metadata.get("uploadId")),
    }
    if stage:
        preview = dict(stage)
        preview.pop("sourcePath", None)
        public["preview"] = preview
        public["stage"] = preview
    errore = _text(metadata.get("errore"))
    if errore:
        public["errore"] = errore
    return public


def _verify_prepare_token(metadata: Mapping[str, Any], token: str) -> None:
    expected = _text(metadata.get("tokenHash"))
    if not expected or not hmac.compare_digest(expected, _prepare_token_hash(token)):
        raise QuickOrganizerImportError("Sessione preparazione non autorizzata.")


def begin_auto_prepare_session(
    index_root: str | Path,
    staging_root: str | Path,
    *,
    expires_hours: int = DEFAULT_AUTO_PREPARE_EXPIRES_HOURS,
) -> dict[str, Any]:
    session_id = uuid.uuid4().hex
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    expires = now + timedelta(hours=max(1, int(expires_hours or DEFAULT_AUTO_PREPARE_EXPIRES_HOURS)))
    staging = _safe_runtime_dir(staging_root, create=True)
    metadata = {
        "sessionId": session_id,
        "tokenHash": _prepare_token_hash(token),
        "stagingRoot": str(staging),
        "status": "pending",
        "progress": 0,
        "detail": "Preparazione in attesa sulla postazione autorizzata.",
        "createdAt": now.isoformat().replace("+00:00", "Z"),
        "expiresAt": expires.isoformat().replace("+00:00", "Z"),
        "uploadId": "",
        "stage": None,
    }
    _prepare_session_dir(index_root, session_id, create=True)
    _write_prepare_metadata(index_root, session_id, metadata)
    public = _public_prepare_status(metadata)
    public["token"] = token
    return public


def auto_prepare_status(index_root: str | Path, session_id: str) -> dict[str, Any]:
    return _public_prepare_status(_read_prepare_metadata(index_root, session_id))


def update_auto_prepare_status(
    index_root: str | Path,
    session_id: str,
    token: str,
    *,
    status: str = "",
    progress: int | float | None = None,
    detail: str = "",
    errore: str = "",
) -> dict[str, Any]:
    metadata = _read_prepare_metadata(index_root, session_id)
    _verify_prepare_token(metadata, token)
    allowed = {"pending", "preparing", "packing", "uploading", "checking", "ready", "error"}
    status_value = _text(status, _text(metadata.get("status"), "pending")).lower()
    if status_value not in allowed:
        status_value = "preparing"
    metadata["status"] = status_value
    if progress is not None:
        metadata["progress"] = max(0, min(100, int(float(progress))))
    if detail:
        metadata["detail"] = _text(detail)[:500]
    if errore:
        metadata["errore"] = _text(errore)[:500]
    elif status_value != "error":
        metadata.pop("errore", None)
    metadata["updatedAt"] = _iso_now()
    _write_prepare_metadata(index_root, session_id, metadata)
    return _public_prepare_status(metadata)


def start_auto_prepare_upload(
    index_root: str | Path,
    session_id: str,
    token: str,
    *,
    filename: str,
    total_size: int,
    chunk_size: int = DEFAULT_CHUNK_UPLOAD_SIZE_BYTES,
    max_size: int | None = None,
) -> dict[str, Any]:
    metadata = _read_prepare_metadata(index_root, session_id)
    _verify_prepare_token(metadata, token)
    staging_root = _text(metadata.get("stagingRoot"))
    upload = begin_chunked_upload(
        filename,
        total_size,
        staging_root,
        chunk_size=chunk_size,
        max_size=max_size,
    )
    metadata["status"] = "uploading"
    metadata["progress"] = max(_number(metadata.get("progress")), 55)
    metadata["detail"] = "Caricamento del pacchetto verso IUSENTRA in corso."
    metadata["uploadId"] = upload.get("uploadId", "")
    metadata["upload"] = upload
    metadata["updatedAt"] = _iso_now()
    _write_prepare_metadata(index_root, session_id, metadata)
    return {"ok": True, **upload}


def receive_auto_prepare_chunk(
    index_root: str | Path,
    session_id: str,
    token: str,
    upload_id: str,
    index: int,
    total_chunks: int,
    file_storage: Any,
) -> dict[str, Any]:
    metadata = _read_prepare_metadata(index_root, session_id)
    _verify_prepare_token(metadata, token)
    if _text(metadata.get("uploadId")) != _safe_upload_id(upload_id):
        raise QuickOrganizerImportError("Sessione caricamento non coerente.")
    result = receive_chunked_upload(
        _text(metadata.get("stagingRoot")),
        upload_id,
        index,
        total_chunks,
        file_storage,
    )
    total = max(1, int(result.get("totalChunks") or total_chunks or 1))
    received = max(0, int(result.get("receivedChunks") or 0))
    metadata["status"] = "uploading"
    metadata["progress"] = min(94, 55 + int((received / total) * 38))
    metadata["detail"] = f"Caricati {received} blocchi su {total}."
    metadata["updatedAt"] = _iso_now()
    _write_prepare_metadata(index_root, session_id, metadata)
    return result


def complete_auto_prepare_upload(
    index_root: str | Path,
    session_id: str,
    token: str,
    upload_id: str,
    *,
    total_chunks: int | None = None,
) -> dict[str, Any]:
    metadata = _read_prepare_metadata(index_root, session_id)
    _verify_prepare_token(metadata, token)
    if _text(metadata.get("uploadId")) != _safe_upload_id(upload_id):
        raise QuickOrganizerImportError("Sessione caricamento non coerente.")
    metadata["status"] = "checking"
    metadata["progress"] = 96
    metadata["detail"] = "Controllo del pacchetto caricato in corso."
    metadata["updatedAt"] = _iso_now()
    _write_prepare_metadata(index_root, session_id, metadata)
    try:
        stage = complete_chunked_upload(
            _text(metadata.get("stagingRoot")),
            upload_id,
            total_chunks=total_chunks,
        )
    except QuickOrganizerImportError as exc:
        update_auto_prepare_status(
            index_root,
            session_id,
            token,
            status="error",
            progress=100,
            detail=exc.public_message,
            errore=exc.public_message,
        )
        raise
    metadata = _read_prepare_metadata(index_root, session_id)
    metadata["status"] = "ready"
    metadata["progress"] = 100
    metadata["detail"] = "Pacchetto controllato e pronto per l'import."
    metadata["stage"] = stage
    metadata["updatedAt"] = _iso_now()
    _write_prepare_metadata(index_root, session_id, metadata)
    return {"ok": True, **stage}


def stage_referenced_package(source_path: str | Path, staging_root: str | Path) -> dict[str, Any]:
    source = _safe_local_package_path(source_path)
    package = load_quickorganizer_package(source, local_source=True)
    import_id = uuid.uuid4().hex
    root = _safe_runtime_dir(staging_root, create=True)
    target_dir = _safe_child_path(root, import_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    analysis = analyze_quickorganizer_package(package)
    stage_payload = {
        "importId": import_id,
        "sourceName": source.name,
        "sourceSha256": _fast_source_fingerprint(source),
        "sourcePath": str(source),
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
    external_source = _text(stage.get("sourcePath") if isinstance(stage, Mapping) else "")
    if external_source:
        return load_quickorganizer_package(external_source, local_source=True), stage
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
