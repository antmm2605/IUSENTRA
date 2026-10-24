"""Private bridge rejects unauthenticated, foreign and oversized requests."""
import importlib.util
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

spec = importlib.util.spec_from_file_location("private_bridge", "deploy/private-lex/bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def test_configuration_rejects_public_bind(monkeypatch):
    monkeypatch.setenv("LEX_BRIDGE_BIND", "0.0.0.0")
    import pytest
    with pytest.raises(ValueError, match="Tailscale"):
        bridge.configuration()


def test_authentication_and_limits():
    server = bridge.ThreadingHTTPServer(("127.0.0.1", 0), bridge.Handler)
    server.allowed = {"127.0.0.1"}
    server.secret = "test-secret-only-" * 4
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:" + str(server.server_port)
    def status(path, headers=None, body=None):
        try:
            with urlopen(Request(base + path, data=body, headers=headers or {}), timeout=3) as response:
                return response.status
        except HTTPError as error:
            return error.code
    try:
        assert status("/v1/models") == 401
        auth = {"Authorization": "Bearer " + server.secret}
        assert status("/arbitrary", auth) == 404
        assert status("/v1/chat/completions", auth, b'{"stream":true}') == 400
        assert status("/v1/chat/completions", auth, b"[]") == 400
        assert status("/v1/chat/completions", {**auth, "Content-Length": str(bridge.MAX_BODY + 1)}, b"x") == 413
        server.allowed = {"100.64.0.1"}
        assert status("/v1/models", auth) == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


def test_configurazione_server_atomica_senza_perdere_impostazioni(tmp_path, monkeypatch, capsys):
    import io
    import json
    import os
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("private_config", "deploy/private-lex/configure_server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target=tmp_path/".env.hetzner"
    target.write_text("OTHER_VALUE=preserved\nLLAMACPP_ENABLED=0\n")
    monkeypatch.setattr(module,"Path",lambda name:target if name=="/opt/iusentra/.env.hetzner" else Path(name))
    monkeypatch.setattr(module.subprocess,"check_output",lambda args:b'{"BackendState":"Running"}')
    class Response(io.BytesIO):
        pass
    monkeypatch.setattr(module,"urlopen",lambda request,timeout:Response(b'{"data":[{"id":"fixture-model"}]}'))
    key="fixture-key-never-real-"*3
    monkeypatch.setattr(module.sys,"stdin",io.StringIO(json.dumps({"pc_address":"100.69.184.43","api_key":key})))
    module.main()
    text=target.read_text()
    assert "OTHER_VALUE=preserved" in text and "LLAMACPP_ENABLED='1'" in text
    assert text.count("LLAMACPP_ENABLED=")==1
    assert "LLAMACPP_DEFAULT_MODEL='fixture-model'" in text
    assert os.stat(target).st_mode & 0o777==0o600
    backups=list(tmp_path.glob(".env.hetzner.before-private-lex-*"))
    assert len(backups)==1 and backups[0].read_text()=="OTHER_VALUE=preserved\nLLAMACPP_ENABLED=0\n"
    assert key not in capsys.readouterr().out
