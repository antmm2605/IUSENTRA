import hashlib
import io
import json
import tarfile

import pytest

from deploy.openga.install import install


def package(tmp_path, name="catalogo.db", symlink=False):
    bundle = tmp_path / "dati.tar.gz"
    with tarfile.open(bundle, "w:gz") as archive:
        item = tarfile.TarInfo(name)
        item.size = 1
        if symlink:
            item.type = tarfile.SYMTYPE
            item.linkname = "/etc/passwd"
        archive.addfile(item, io.BytesIO(b"x") if not symlink else None)
    manifest = tmp_path / "manifesti"
    manifest.mkdir()
    (manifest / "pacchetto.json").write_text(json.dumps({"sha256": hashlib.sha256(bundle.read_bytes()).hexdigest()}))
    (manifest / "catalogo-manifest.json").write_text(json.dumps({"files": [{"file": name, "bytes": 1, "sha256": hashlib.sha256(b"x").hexdigest()}]}))
    (manifest / "modello-manifest.json").write_text("{}")
    return bundle, manifest


def test_pacchetto_alterato_non_crea_destinazione(tmp_path):
    bundle, manifest = package(tmp_path)
    bundle.write_bytes(bundle.read_bytes() + b"alterato")
    dest = tmp_path / "dest"
    with pytest.raises(ValueError, match="Impronta"):
        install(bundle, dest, manifest)
    assert not dest.exists()


@pytest.mark.parametrize("name,symlink", [("../fuori", False), ("catalogo.db", True)])
def test_archivio_non_puo_uscire_dalla_cartella(tmp_path, name, symlink):
    bundle, manifest = package(tmp_path, name, symlink)
    with pytest.raises(ValueError, match="Percorso"):
        install(bundle, tmp_path / "dest", manifest)
    assert not (tmp_path / "fuori").exists()
    assert not (tmp_path / "dest/INSTALLATO.json").exists()


def test_installazione_precedente_non_viene_sovrascritta(tmp_path):
    bundle, manifest = package(tmp_path)
    dest = tmp_path / "dest"
    dest.mkdir()
    marker = dest / "conservare"
    marker.write_text("originale")
    with pytest.raises(ValueError, match="già presente"):
        install(bundle, dest, manifest)
    assert marker.read_text() == "originale"
