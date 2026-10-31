import hashlib
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("translation_verified_worker", Path(__file__).resolve().parents[1] / "deploy/translation/run_verified_worker.py")
worker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(worker)


def test_verified_runtime_rejects_changed_missing_and_extra_binaries(tmp_path):
    binary = tmp_path / "llama-server"
    binary.write_bytes(b"verified binary")
    manifest = {"files": {"llama-server": {"sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}}}
    assert worker.verify_runtime(tmp_path, manifest) == binary
    binary.write_bytes(b"altered")
    with pytest.raises(ValueError):
        worker.verify_runtime(tmp_path, manifest)
    binary.write_bytes(b"verified binary")
    extra = tmp_path / "untrusted-library.so"
    extra.write_bytes(b"extra")
    with pytest.raises(ValueError):
        worker.verify_runtime(tmp_path, manifest)
    extra.unlink()
    binary.unlink()
    with pytest.raises(FileNotFoundError):
        worker.verify_runtime(tmp_path, manifest)


@pytest.mark.parametrize("name", ["../outside", "/outside"])
def test_runtime_manifest_cannot_escape_verified_directory(tmp_path, name):
    with pytest.raises(ValueError):
        worker.verify_runtime(tmp_path, {"files": {name: {"sha256": "a"*64}}})


def test_verified_runtime_rejects_symlink_to_untrusted_library(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    outside = tmp_path / "outside.so"
    outside.write_bytes(b"untrusted")
    (runtime / "lib.so").symlink_to(outside)
    with pytest.raises(ValueError):
        worker.verify_runtime(runtime, {"files": {"lib.so": {"link": "../outside.so"}}})
