"""Confini del pacchetto del modello prima della copia nel sidecar."""
import importlib.util
from pathlib import Path
import tarfile

import pytest


@pytest.fixture
def installer():
    path = Path(__file__).resolve().parents[1] / "deploy/hetzner/install_lex_modello.py"
    spec = importlib.util.spec_from_file_location("lex_model_install", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_accepts_only_regular_manifest_and_named_hash_blobs(installer):
    manifest = "manifests/registry.ollama.ai/library/iusentra-lex-v3/9b"
    assert installer.valid_member(tarfile.TarInfo(manifest), manifest)
    assert installer.valid_member(tarfile.TarInfo("blobs/sha256-" + "a" * 64), manifest)
    for name in ("../outside", "blobs/sha256-../" + "a" * 60, "blobs/sha256-" + "z" * 64):
        assert not installer.valid_member(tarfile.TarInfo(name), manifest)
    link = tarfile.TarInfo(manifest)
    link.type = tarfile.SYMTYPE
    assert not installer.valid_member(link, manifest)


def test_rejects_model_or_prefix_with_shell_and_path_syntax(installer, tmp_path):
    args = ["iusentra-lex-v3:9b", "a" * 64, str(tmp_path), "lex-v3"]
    assert installer.configuration(args) == tuple(args)
    for index, value in ((0, "../../model:9b"), (0, "model:9b;id"), (1, "unknown"), (3, "../outside")):
        invalid = args.copy()
        invalid[index] = value
        with pytest.raises(ValueError):
            installer.configuration(invalid)


@pytest.mark.parametrize("suffix", ["", "/api", "/api/", "/api/version", "/version"])
def test_lex_runtime_uses_api_root_for_configured_readiness_url(suffix):
    from lex.providers.ollama_runtime import normalize_ollama_api_base_url

    assert normalize_ollama_api_base_url("http://ollama:11434" + suffix) == "http://ollama:11434/api"
