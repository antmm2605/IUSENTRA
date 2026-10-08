"""Catalogo condiviso: soltanto font dei pacchetti aperti governati."""
from functools import lru_cache
import hashlib
from pathlib import Path
import subprocess


PACKAGES = ('fonts-noto-core', 'fonts-noto-extra', 'fonts-noto-mono',
            'fonts-crosextra-carlito', 'fonts-crosextra-caladea',
            'fonts-liberation', 'fonts-liberation2', 'fonts-dejavu-core')


@lru_cache(maxsize=1)
def font_library():
    """Una lettura per processo, nessuna scansione tenant o di documenti."""
    approved = {}
    for package in PACKAGES:
        license_path = Path('/usr/share/doc') / package / 'copyright'
        if not license_path.is_file():
            continue
        result = subprocess.run(['dpkg-query', '-L', package], capture_output=True,
                                text=True, timeout=5, check=False)
        if result.returncode:
            continue
        for line in result.stdout.splitlines():
            path = Path(line)
            if (path.suffix.lower() in {'.ttf', '.otf'} and path.is_file()
                    and path.resolve().is_relative_to('/usr/share/fonts')):
                approved[str(path)] = (path, license_path, package)
    result = subprocess.run(['fc-list', '--format', '%{file}|%{family[0]}|%{style[0]}\n'],
                            capture_output=True, text=True, timeout=8, check=True)
    families, files = {}, {}
    for line in result.stdout.splitlines():
        parts = line.split('|')
        if len(parts) != 3 or parts[0] not in approved:
            continue
        filename, family, style = parts
        if not family or len(family) > 100:
            continue
        # Le varianti standard sono quelle offerte dagli editor (B/I).
        normalized = style.casefold().replace(' ', '')
        if normalized not in {'regular', 'book', 'roman', 'normal', 'italic', 'bold', 'bolditalic', 'oblique', 'boldoblique'}:
            continue
        token = hashlib.sha256(filename.encode()).hexdigest()[:24]
        path, license_path, package = approved[filename]
        files[token] = (path, license_path)
        families.setdefault(family, []).append({
            'id': token, 'weight': 700 if 'bold' in normalized else 400,
            'style': 'italic' if ('italic' in normalized or 'oblique' in normalized) else 'normal',
            'package': package,
        })
    return [{'family': family, 'faces': sorted(faces, key=lambda f: (f['weight'], f['style']))}
            for family, faces in sorted(families.items())], files


def resolve_font_file(token, license_only=False):
    entry = font_library()[1].get(token)
    if not entry:
        return None
    return entry[1 if license_only else 0]
