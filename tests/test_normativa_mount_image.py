"""Il mount offline riusa il dispositivo, senza duplicare backing file o formattare."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def helper(monkeypatch, tmp_path):
    pytest.importorskip("fcntl", reason="Helper del mount riservato al kernel Linux")
    source = Path(__file__).resolve().parents[1] / "deploy/normativa/mount_data_image.py"
    spec = importlib.util.spec_from_file_location("normativa_mount_image", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "open", lambda *args, **kwargs: (tmp_path / "lock").open("a"), raising=False)
    return module


def setup_config(module, monkeypatch, tmp_path, *, check=False):
    image = tmp_path / "image.ext4"
    image.write_bytes(b"controlled-placeholder")
    target = tmp_path / "mounted"
    target.mkdir()
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"image": str(image), "target": str(target), "uuid": "expected-uuid"}))
    monkeypatch.setattr(module, "dispositivi_immagine", lambda image: ["/dev/loop7"])
    monkeypatch.setattr("sys.argv", ["mount-helper", "--config", str(config)] + (["--check"] if check else []))
    return image, target


def test_duplice_dispositivo_blocca_prima_di_qualsiasi_mount(helper, monkeypatch, tmp_path):
    setup_config(helper, monkeypatch, tmp_path)
    monkeypatch.setattr(helper, "dispositivi_immagine", lambda image: ["/dev/loop1", "/dev/loop2"])
    monkeypatch.setattr(helper.subprocess, "run", lambda *a, **kw: pytest.fail("Nessun comando deve partire"))
    with pytest.raises(RuntimeError, match="piu loop device"):
        helper.main()


@pytest.mark.parametrize("dispositivo_esistente", [True, False])
def test_mount_usa_unico_dispositivo(helper, monkeypatch, tmp_path, capsys, dispositivo_esistente):
    image, target = setup_config(helper, monkeypatch, tmp_path)
    if not dispositivo_esistente:
        devices = iter([[], ["/dev/loop7"], ["/dev/loop7"]])
        monkeypatch.setattr(helper, "dispositivi_immagine", lambda image: next(devices))
    calls = []
    def command(*args):
        calls.append(args)
        if args == ("losetup", "--find", "--show", "--nooverlap", str(image)):
            return "/dev/loop7\n"
        if args[0] == "blkid":
            return "expected-uuid\n"
        if args[:3] == ("losetup", "--json", "--list"):
            return json.dumps({"loopdevices": [{"back-file": str(image)}]})
        if args == ("mount", "-t", "ext4", "/dev/loop7", str(target)):
            return ""
        pytest.fail("Comando non previsto: " + repr(args))
    probes = iter([SimpleNamespace(returncode=1, stdout=""), SimpleNamespace(returncode=0, stdout=json.dumps({"filesystems": [{"source": "/dev/loop7", "fstype": "ext4"}]}))])
    monkeypatch.setattr(helper, "run", command)
    monkeypatch.setattr(helper.subprocess, "run", lambda *a, **kw: next(probes))
    helper.main()
    assert ("mount", "-t", "ext4", "/dev/loop7", str(target)) in calls
    creations = [args for args in calls if "--find" in args]
    assert len(creations) == (0 if dispositivo_esistente else 1)
    assert all("--nooverlap" in args for args in creations)
    assert not any(args[0].startswith("mkfs") for args in calls)
    assert not any(args[0] == "mount" and "-o" in args for args in calls)
    assert json.loads(capsys.readouterr().out)["stato"] == "montato_verificato"


def test_check_senza_mount_non_monta(helper, monkeypatch, tmp_path):
    setup_config(helper, monkeypatch, tmp_path, check=True)
    monkeypatch.setattr(helper.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1, stdout=""))
    monkeypatch.setattr(helper, "run", lambda *a: pytest.fail("Check non deve montare"))
    with pytest.raises(RuntimeError, match="non montato"):
        helper.main()


def test_vista_diversa_blocca_anche_con_filesystem_corretto(helper, monkeypatch, tmp_path):
    setup_config(helper, monkeypatch, tmp_path, check=True)
    monkeypatch.setattr(helper.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout=json.dumps({"filesystems": [{"source": "/dev/loop9", "fstype": "ext4"}]})))
    monkeypatch.setattr(helper, "run", lambda *a: pytest.fail("Dispositivo discordante non va accettato"))
    with pytest.raises(RuntimeError, match="Vista montata non univoca"):
        helper.main()


def test_backing_file_riscontrato_per_inode_anche_con_hardlink(helper, monkeypatch, tmp_path):
    image = tmp_path / "image.ext4"
    image.write_bytes(b"original")
    alias = tmp_path / "alias.ext4"
    alias.hardlink_to(image)
    block = tmp_path / "sys-block"
    for name, path in [("loop1", image), ("loop2", alias), ("loop3", tmp_path / "assente")]:
        entry = block / name / "loop" / "backing_file"
        entry.parent.mkdir(parents=True)
        entry.write_text(str(path))
    monkeypatch.setattr(helper, "Path", lambda value: block if value == "/sys/block" else Path(value))
    assert helper.dispositivi_immagine(image) == ["/dev/loop1", "/dev/loop2"]
