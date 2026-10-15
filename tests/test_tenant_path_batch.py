"""La risoluzione in gruppo conserva i confini fisici dello studio."""
import os
from pathlib import Path

import pytest

from web.services.tenant_path_batch import resolve_private_paths


def test_percorsi_esistenti_mancanti_e_dotdot_equivalgono_a_pathlib(tmp_path):
    root = (tmp_path / 'studio').resolve()
    root.mkdir()
    (root / 'docs').mkdir()
    (root / 'docs' / 'a.pdf').write_bytes(b'controlled')
    paths = {'root': str(root), 'file': str(root / 'docs' / 'a.pdf'),
             'missing': str(root / 'missing' / 'b.pdf'),
             'parent': str(root / 'docs' / '..' / 'other'),
             'outside': str(tmp_path / 'studio-other' / 'file')}
    assert resolve_private_paths(paths, root) == {key: Path(value).resolve() for key, value in paths.items()}


@pytest.mark.skipif(os.name != 'posix', reason='Ottimizzazione POSIX provata nel Docker reale')
def test_alias_fisici_cambio_destinazione_e_cicli_non_sono_nascosti(tmp_path):
    root = (tmp_path / 'studio').resolve(); root.mkdir()
    inside = root / 'docs'; inside.mkdir()
    outside = tmp_path / 'other'; outside.mkdir()
    link = root / 'alias'; link.symlink_to(inside, target_is_directory=True)
    external_alias = tmp_path / 'external-alias'; external_alias.symlink_to(inside, target_is_directory=True)
    paths = {'first': str(link / 'a.pdf'), 'second': str(link / 'b.pdf'),
             'external_alias': str(external_alias / 'a.pdf')}
    assert resolve_private_paths(paths, root) == {key: Path(value).resolve() for key, value in paths.items()}
    link.unlink(); link.symlink_to(outside, target_is_directory=True)
    result = resolve_private_paths(paths, root)
    assert result['first'] == outside / 'a.pdf' and not result['first'].is_relative_to(root)
    loop = root / 'loop'; loop.symlink_to(loop)
    with pytest.raises(RuntimeError):
        resolve_private_paths({'loop': str(loop / 'a.pdf')}, root)


@pytest.mark.skipif(os.name != 'posix', reason='Ottimizzazione POSIX provata nel Docker reale')
def test_componenti_comuni_riscontrati_una_volta_nel_gruppo(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    (root / 'docs').mkdir()
    original = Path.lstat
    calls = []
    def counted(path, *args, **kwargs):
        calls.append(path)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'lstat', counted)
    paths = {str(i): str(root / 'docs' / f'{i}.pdf') for i in range(20)}
    resolve_private_paths(paths, root)
    assert calls.count(root / 'docs') == 1
    assert len(calls) == 21
