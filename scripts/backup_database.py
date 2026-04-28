from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

from core.database import is_sqlite_url, sqlite_path_from_url


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea backup database/storage IUSENTRA.")
    parser.add_argument("--database-url", default="sqlite:///data/iusentra.sqlite")
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--backup-dir", default="data/backup")
    args = parser.parse_args()

    backup_dir = Path(args.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = backup_dir / f"iusentra-backup-{stamp}.zip"
    manifest: dict[str, object] = {"created_at": stamp, "files": []}
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if is_sqlite_url(args.database_url):
            db_path = sqlite_path_from_url(args.database_url)
            if db_path.exists():
                copy_path = backup_dir / f"db-{stamp}.sqlite"
                src = sqlite3.connect(str(db_path))
                dst = sqlite3.connect(str(copy_path))
                with dst:
                    src.backup(dst)
                src.close()
                dst.close()
                _write_file(zf, copy_path, f"database/{copy_path.name}", manifest)
                copy_path.unlink(missing_ok=True)
        else:
            dump_path = backup_dir / f"postgres-{stamp}.sql"
            subprocess.run(["pg_dump", args.database_url, "-f", str(dump_path)], check=True)
            _write_file(zf, dump_path, f"database/{dump_path.name}", manifest)
            dump_path.unlink(missing_ok=True)
        data_root = Path(args.data_root)
        if data_root.exists():
            for path in data_root.rglob("*"):
                if path.is_file() and backup_dir not in path.parents:
                    _write_file(zf, path, f"storage/{path.relative_to(data_root).as_posix()}", manifest)
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps({"ok": True, "backup": str(target), "sha256": _sha256(target)}, ensure_ascii=False, indent=2))
    return 0


def _write_file(zf: zipfile.ZipFile, path: Path, arcname: str, manifest: dict[str, object]) -> None:
    zf.write(path, arcname)
    files = manifest.setdefault("files", [])
    assert isinstance(files, list)
    files.append({"path": arcname, "size": path.stat().st_size, "sha256": _sha256(path)})


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
