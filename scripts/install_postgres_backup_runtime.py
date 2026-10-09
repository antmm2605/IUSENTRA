"""Installa il client 16 dal repository ufficiale PGDG, per il profilo Hetzner."""
from pathlib import Path
import platform
import subprocess
from urllib.request import urlopen


def main():
    codename = platform.freedesktop_os_release()['VERSION_CODENAME']
    if codename not in {'bookworm', 'trixie'}:
        raise RuntimeError('Distribuzione non prevista per il client PostgreSQL governato.')
    key = Path('/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc')
    key.parent.mkdir(parents=True, exist_ok=True)
    with urlopen('https://www.postgresql.org/media/keys/ACCC4CF8.asc', timeout=30) as response:
        content = response.read()
    if not content.startswith(b'-----BEGIN PGP PUBLIC KEY BLOCK-----'):
        raise RuntimeError('Chiave ufficiale PostgreSQL non valida.')
    key.write_bytes(content)
    Path('/etc/apt/sources.list.d/pgdg.sources').write_text(
        f'Types: deb\nURIs: https://apt.postgresql.org/pub/repos/apt\nSuites: {codename}-pgdg\n'
        f'Components: main\nSigned-By: {key}\n', encoding='utf-8')
    subprocess.run(['apt-get', 'update'], check=True)
    subprocess.run(['apt-get', 'install', '-y', '--no-install-recommends', 'postgresql-client-16'], check=True)


if __name__ == '__main__':
    main()
