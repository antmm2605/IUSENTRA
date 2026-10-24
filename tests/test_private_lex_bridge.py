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
