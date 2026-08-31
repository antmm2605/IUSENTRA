#!/usr/bin/env python3
"""Crea e verifica un backup completo e ripristinabile della procedura PST."""

from __future__ import annotations

import argparse
import os
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
ROME = ZoneInfo("Europe/Rome")
INSTALLED_SIGNER_ROOT = Path(os.environ.get("APPDATA", "")) / "IUSENTRA" / "LocalSigner"


@dataclass(frozen=True)
class RequiredPath:
    path: str
    recursive: bool = False
    required: bool = True


INSTALLED_REQUIRED_PATHS = (
    RequiredPath("local_signer.py"),
    RequiredPath("local_signer_mod", recursive=True),
    RequiredPath("local_signer_foreground_helper.py"),
    RequiredPath("local_signer_windows_http.ps1"),
    RequiredPath("local_ai_host_bridge.py"),
    RequiredPath("lex_document_context.py"),
    RequiredPath("visible_signature.py"),
    RequiredPath("requirements_local_signer.txt"),
    RequiredPath("start_local_signer.cmd"),
    RequiredPath("start_local_signer.vbs"),
)


REQUIRED_PATHS = (
    RequiredPath("tools/local_signer.py"),
    RequiredPath("tools/dist/local_signer.py"),
    RequiredPath("local_signer_mod", recursive=True),
    RequiredPath("tools/local_signer_foreground_helper.py"),
    RequiredPath("tools/local_signer_windows_http.ps1"),
    RequiredPath("visible_signature.py"),
    RequiredPath("tools/local_ai_host_bridge.py"),
    RequiredPath("tools/lex_document_context.py"),
    RequiredPath("lex/context", recursive=True),
    RequiredPath("pct/firma_pkcs11.py"),
    RequiredPath("frontend/src/features/telematico/localSignerForeground.ts"),
    RequiredPath("frontend/src/features/telematico/LocalSignerPanel.tsx"),
    RequiredPath("frontend/src/components/TelematicoSurfacePage.tsx"),
    RequiredPath("frontend/src/components/OfficeDocumentsPanel.tsx"),
    RequiredPath("frontend/src/components/FascicoliPage.tsx"),
    RequiredPath("frontend/src/components/FascicoloDepositoPage.tsx"),
    RequiredPath("frontend/src/components/NotificheLegaliPage.tsx"),
    RequiredPath("tools/installa_local_signer_locale.ps1"),
    RequiredPath("tools/build_local_signer_windows_exe.ps1"),
    RequiredPath("tools/build_dist.py"),
    RequiredPath("tools/requirements_local_signer.txt"),
    RequiredPath("tools/avvia_local_signer.bat"),
    RequiredPath("web/blueprints/api_v1_react.py"),
    RequiredPath("web/bootstrap/telematico_local_signer_routes.py"),
    RequiredPath("web/bootstrap/deposito_routes.py"),
    RequiredPath("web/bootstrap/deposito_receipt_routes.py"),
    RequiredPath("web/blueprints/notifiche.py"),
    RequiredPath("web/services/deposito_pec_runtime.py"),
    RequiredPath("web/services/deposito_signature_runtime.py"),
    RequiredPath("pct/telematic_deposit_workflow.py"),
    RequiredPath("pct/uffici_giudiziari.py"),
    RequiredPath("pct/uffici_competenti.py"),
    RequiredPath("pct/data/uffici_ministero.json"),
    RequiredPath("tests/test_local_signer.py"),
    RequiredPath("tests/test_local_signer_installer_atomic.py"),
    RequiredPath("tests/test_firma_pkcs11.py"),
    RequiredPath("tests/test_react_shell.py"),
    RequiredPath("tests/test_deposito.py"),
    RequiredPath("tests/test_notifiche_legali.py"),
    RequiredPath("artifacts/react-migration/log-tecnico-fascicolo-ufficio-20260829.md"),
    RequiredPath("artifacts/react-migration/test-fascicolo-ufficio-vicenza-20260830-0105.md"),
    RequiredPath("artifacts/react-migration/pst-wizard-fascicolo-ufficio-20260831.md"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True, encoding="utf-8").strip()


def signer_version(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if "IUSENTRA Local Signer - v" in line:
            return line.rsplit("v", 1)[-1].strip()
    return "sconosciuta"


def copy_required(source: Path, target_root: Path, recursive: bool) -> list[dict[str, object]]:
    files = sorted(path for path in (source.rglob("*") if recursive else (source,)) if path.is_file())
    copied: list[dict[str, object]] = []
    for file in files:
        relative = file.relative_to(ROOT)
        destination = target_root / "code" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, destination)
        copied.append({
            "percorso_originale": relative.as_posix(),
            "percorso_backup": (Path("code") / relative).as_posix(),
            "byte": file.stat().st_size,
            "sha256": sha256(file),
        })
    return copied


def copy_installed_required(source: Path, target_root: Path, recursive: bool) -> list[dict[str, object]]:
    files = sorted(path for path in (source.rglob("*") if recursive else (source,)) if path.is_file())
    copied: list[dict[str, object]] = []
    for file in files:
        relative = file.relative_to(INSTALLED_SIGNER_ROOT)
        destination = target_root / "installed-local-signer" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, destination)
        copied.append({
            "percorso_originale": f"installato:{relative.as_posix()}",
            "percorso_backup": (Path("installed-local-signer") / relative).as_posix(),
            "byte": file.stat().st_size,
            "sha256": sha256(file),
        })
    return copied


def build_backup(output: Path) -> Path:
    if output.exists():
        raise SystemExit(f"Destinazione già esistente: {output}")
    output.mkdir(parents=True)
    missing = [item.path for item in REQUIRED_PATHS if item.required and not (ROOT / item.path).exists()]
    installed_missing = [item.path for item in INSTALLED_REQUIRED_PATHS if item.required and not (INSTALLED_SIGNER_ROOT / item.path).exists()]
    if missing or installed_missing:
        details = []
        if missing:
            details.append("repository: " + ", ".join(missing))
        if installed_missing:
            details.append("installato: " + ", ".join(installed_missing))
        raise SystemExit("Percorsi obbligatori mancanti: " + " | ".join(details))

    copied: list[dict[str, object]] = []
    for item in REQUIRED_PATHS:
        source = ROOT / item.path
        if source.exists():
            copied.extend(copy_required(source, output, item.recursive))
    for item in INSTALLED_REQUIRED_PATHS:
        source = INSTALLED_SIGNER_ROOT / item.path
        if source.exists():
            copied.extend(copy_installed_required(source, output, item.recursive))

    commit = command("git", "rev-parse", "HEAD")
    branch = command("git", "branch", "--show-current")
    git_status = command("git", "status", "--short")
    status_file = output / "git-status.txt"
    status_file.write_text(git_status + ("\n" if git_status else ""), encoding="utf-8")
    copied.append({
        "percorso_originale": "git:status --short",
        "percorso_backup": status_file.name,
        "byte": status_file.stat().st_size,
        "sha256": sha256(status_file),
    })
    patch_file = output / "git-worktree.patch"
    with patch_file.open("wb") as handle:
        subprocess.run(["git", "diff", "--binary", "HEAD"], cwd=ROOT, check=True, stdout=handle)
    copied.append({
        "percorso_originale": "git:diff --binary HEAD",
        "percorso_backup": patch_file.name,
        "byte": patch_file.stat().st_size,
        "sha256": sha256(patch_file),
    })
    bundle = output / "repository-head.bundle"
    subprocess.run(["git", "bundle", "create", str(bundle), "HEAD"], cwd=ROOT, check=True)
    copied.append({
        "percorso_originale": "git:HEAD",
        "percorso_backup": bundle.name,
        "byte": bundle.stat().st_size,
        "sha256": sha256(bundle),
    })

    created = datetime.now(ROME)
    manifest = {
        "schema": "iusentra.local-signer-procedure-backup/v1",
        "creato_il": created.strftime("%d/%m/%Y %H:%M:%S %Z"),
        "fuso_orario": "Europe/Rome",
        "versione_local_signer": signer_version(INSTALLED_SIGNER_ROOT / "local_signer.py"),
        "versione_local_signer_sorgente": signer_version(ROOT / "tools/local_signer.py"),
        "radice_local_signer_installato": str(INSTALLED_SIGNER_ROOT),
        "commit_git": commit,
        "branch_git": branch,
        "worktree_modificato": bool(git_status),
        "protezione_dati": "Non contiene PIN, certificati privati, cookie, sessioni PST né dati dello studio.",
        "voci_richieste": [item.path for item in REQUIRED_PATHS],
        "file": copied,
    }
    manifest_path = output / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verify_backup(output)
    return output


def verify_backup(output: Path) -> None:
    manifest_path = output / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "iusentra.local-signer-procedure-backup/v1":
        raise SystemExit("Schema MANIFEST non riconosciuto.")
    backed_up = {str(item["percorso_originale"]) for item in manifest.get("file", [])}
    missing = []
    for item in REQUIRED_PATHS:
        source = ROOT / item.path
        if item.recursive:
            expected = {path.relative_to(ROOT).as_posix() for path in source.rglob("*") if path.is_file()}
        else:
            expected = {item.path}
        missing.extend(sorted(expected - backed_up))
    for item in INSTALLED_REQUIRED_PATHS:
        source = INSTALLED_SIGNER_ROOT / item.path
        if item.recursive:
            expected = {f"installato:{path.relative_to(INSTALLED_SIGNER_ROOT).as_posix()}" for path in source.rglob("*") if path.is_file()}
        else:
            expected = {f"installato:{item.path}"}
        missing.extend(sorted(expected - backed_up))
    if missing:
        raise SystemExit("MANIFEST incompleto: " + ", ".join(missing))
    for item in manifest["file"]:
        backup_file = output / str(item["percorso_backup"])
        if not backup_file.is_file() or backup_file.stat().st_size != item["byte"] or sha256(backup_file) != item["sha256"]:
            raise SystemExit(f"Verifica hash non superata: {item['percorso_backup']}")
    print(f"Backup valido: {output} ({len(manifest['file'])} file verificati)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        verify_backup(args.verify.resolve())
        return 0
    stamp = datetime.now(ROME).strftime("%Y%m%d-%H%M%S")
    output = args.output or ROOT / "artifacts/local-signer-procedure-backups" / f"local-signer-pst-complete-{stamp}"
    print(build_backup(output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
