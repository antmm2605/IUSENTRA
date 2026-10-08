"""Resa del DOCX effettivamente generato, con profilo privato per operazione."""
from __future__ import annotations

import subprocess
import os
from pathlib import Path


def render_word(path: Path, output: Path, font_config: Path | None = None) -> Path:
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    profile = output / 'profile'
    environment = {**os.environ, 'HOME': str(output), 'XDG_CACHE_HOME': str(output / 'cache')}
    (output / 'cache').mkdir(mode=0o700, exist_ok=True)
    if font_config:
        environment['FONTCONFIG_FILE'] = str(font_config.resolve())
    completed = subprocess.run(
        ['soffice', '-env:UserInstallation=' + profile.resolve().as_uri(),
         '--headless', '--nologo', '--nodefault', '--norestore',
         '--convert-to', 'pdf:writer_pdf_Export', '--outdir', str(output), str(path)],
        capture_output=True, timeout=30, check=False, env=environment,
    )
    rendered = output / (path.stem + '.pdf')
    if completed.returncode or not rendered.is_file():
        raise RuntimeError('Resa del documento Word non disponibile')
    return rendered
