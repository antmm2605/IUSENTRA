from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica integrita' backup IUSENTRA.")
    parser.add_argument("backup")
    args = parser.parse_args()
    target = Path(args.backup)
    if not target.exists() or target.stat().st_size == 0:
        print(json.dumps({"ok": False, "errore": "Backup assente o vuoto"}, ensure_ascii=False))
        return 1
    try:
        with zipfile.ZipFile(target) as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            names = set(zf.namelist())
            for item in manifest.get("files", []):
                name = item["path"]
                if name not in names:
                    raise RuntimeError(f"File mancante: {name}")
                digest = hashlib.sha256(zf.read(name)).hexdigest()
                if digest != item["sha256"]:
                    raise RuntimeError(f"Checksum non valido: {name}")
    except Exception as exc:
        print(json.dumps({"ok": False, "errore": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "backup": str(target)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
