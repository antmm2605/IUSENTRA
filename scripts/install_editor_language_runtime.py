"""Installazione riproducibile del revisore locale dalla distribuzione ufficiale."""
import hashlib
import io
from pathlib import Path
from urllib.request import Request, urlopen
import zipfile

VERSION = "6.6"
SHA256 = "53600506b399bb5ffe1e4c8dec794fd378212f14aaf38ccef9b6f89314d11631"


def installa(destinazione: Path, archivio: bytes) -> None:
    if hashlib.sha256(archivio).hexdigest() != SHA256:
        raise RuntimeError("Impronta della distribuzione linguistica non valida.")
    destinazione.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archivio)) as pacchetto:
        for voce in pacchetto.infolist():
            parti = Path(voce.filename).parts[1:]
            if not parti:
                continue
            percorso = destinazione.joinpath(*parti).resolve()
            if not percorso.is_relative_to(destinazione.resolve()):
                raise RuntimeError("Percorso non consentito nella distribuzione.")
            if voce.is_dir():
                percorso.mkdir(parents=True, exist_ok=True)
            else:
                percorso.parent.mkdir(parents=True, exist_ok=True)
                percorso.write_bytes(pacchetto.read(voce))


if __name__ == "__main__":
    richiesta = Request(f"https://languagetool.org/download/LanguageTool-{VERSION}.zip", headers={"User-Agent": "IUSENTRA-build/1.0", "Accept": "application/zip"})
    with urlopen(richiesta, timeout=120) as risposta:
        installa(Path("/opt/iusentra/languagetool"), risposta.read())
