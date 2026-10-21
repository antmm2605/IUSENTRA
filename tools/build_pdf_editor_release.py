"""Pubblica asset PDF con indirizzo immutabile, senza dipendenze aggiuntive."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def files(folder: Path, *, normalize: bool = True) -> dict[str, bytes]:
    result = {}
    for path in sorted(folder.rglob('*')):
        if path.is_symlink():
            raise ValueError('Collegamento simbolico negli asset PDF non ammesso.')
        if not path.is_file():
            continue
        data = path.read_bytes()
        try:
            text = data.decode('utf-8')
            if normalize and '\0' not in text:
                data = text.replace('\r\n', '\n').encode('utf-8')
        except UnicodeDecodeError:
            pass
        result[path.relative_to(folder).as_posix()] = data
    return result


def build(root: Path, *, check: bool = False) -> str:
    vendor = root / 'web/static/vendor/pdfcraft-direct'
    payloads = files(vendor / 'editor')
    if 'index.html' not in payloads or 'editcore.wasm' not in payloads:
        raise ValueError('Sorgenti dell’editor PDF incomplete.')
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}
    identity = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:20]
    target = vendor / 'releases' / identity / 'editor'
    base = f'/static/vendor/pdfcraft-direct/releases/{identity}/editor'
    entry = root / 'frontend/src/pdfEditorRelease.ts'
    if any(path.is_symlink() for path in (vendor, vendor / 'editor', vendor / 'releases',
                                           target.parent, target, entry)):
        raise ValueError('Destinazione degli asset PDF non ammessa.')
    source = '// Generato da tools/build_pdf_editor_release.py; non modificare a mano.\n'
    source += f"export const PDF_EDITOR_ASSET_BASE = '{base}'\n"
    if check:
        if not entry.is_file() or entry.read_text(encoding='utf-8') != source or files(target, normalize=False) != payloads:
            raise ValueError('Asset PDF pubblicati discordanti: eseguire tools/build_pdf_editor_release.py.')
    else:
        if target.exists() and files(target, normalize=False) != payloads:
            raise ValueError('Release PDF esistente alterata: nessuna sovrascrittura eseguita.')
        for name, data in payloads.items():
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                destination.write_bytes(data)
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text(source, encoding='utf-8')
    return base


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(build(Path(__file__).resolve().parents[1], check=args.check))
