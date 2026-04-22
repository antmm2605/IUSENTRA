from __future__ import annotations

import importlib.util
from pathlib import Path

ENTRYPOINT_PATH = Path(__file__).resolve().parents[1] / "docker" / "entrypoint.py"
SPEC = importlib.util.spec_from_file_location("iusentra_docker_entrypoint", ENTRYPOINT_PATH)
assert SPEC and SPEC.loader
ENTRYPOINT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENTRYPOINT)


def test_should_drop_privileges_quando_tutti_i_probe_passano(monkeypatch, capsys):
    roots = [Path("/data"), Path("/data/search")]
    monkeypatch.setattr(ENTRYPOINT, "_candidate_write_roots", lambda: roots)
    monkeypatch.setattr(ENTRYPOINT, "_probe_write_as_user", lambda path, uid, gid: True)

    assert ENTRYPOINT._should_drop_privileges(1000, 1000) is True
    assert capsys.readouterr().err == ""


def test_should_drop_privileges_fa_fallback_esplicito_se_un_probe_fallisce(monkeypatch, capsys):
    roots = [Path("/data"), Path("/data/search")]
    monkeypatch.setattr(ENTRYPOINT, "_candidate_write_roots", lambda: roots)
    monkeypatch.setattr(
        ENTRYPOINT,
        "_probe_write_as_user",
        lambda path, uid, gid: path != Path("/data/search"),
    )

    assert ENTRYPOINT._should_drop_privileges(1000, 1000) is False
    err = capsys.readouterr().err.replace("\\", "/")
    assert "/data/search" in err


def test_prepare_data_root_crea_la_radice_senza_scansione_ricorsiva(monkeypatch, tmp_path):
    target = tmp_path / "data"
    touched: list[tuple[object, ...]] = []

    monkeypatch.setattr(
        ENTRYPOINT.os,
        "chown",
        lambda path, uid, gid: touched.append(("chown", Path(path), uid, gid)),
        raising=False,
    )

    ENTRYPOINT._prepare_data_root(target, 1000, 1000)

    assert target.exists()
    assert touched == [("chown", target, 1000, 1000)]
