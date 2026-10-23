"""Il gate deve chiudere il collegamento quando le prove non confermano il vantaggio."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("failure", [None, "perdita", "ricaricamento"])
def test_gate_server_blocca_perdite_e_ricaricamenti(tmp_path, monkeypatch, capsys, failure):
    source = Path(__file__).resolve().parents[1] / "deploy/openga/benchmark_server.py"
    spec = importlib.util.spec_from_file_location("benchmark_openga_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "__file__", str(tmp_path / "benchmark_server.py"))
    cases = [{"id": f"S{i}", "q": str(i), "dal": 2023, "al": 2023,
              "attesa_decisione": f"D{i}"} for i in range(30)]
    data = json.dumps(cases).encode()
    (tmp_path / "benchmark-server-30.json").write_bytes(data)
    (tmp_path / "benchmark-server-protocollo.json").write_text(json.dumps({"sha256": hashlib.sha256(data).hexdigest()}))
    health_calls = 0

    def request(path, payload=None):
        nonlocal health_calls
        if path == "/health":
            health_calls += 1
            loaded = health_calls > 1
            return {"configured": True, "pid": 1, "reranker_cache": {
                "caricati": int(loaded), "misses": (2 if failure == "ricaricamento" else 1) if loaded else 0,
                "hits": 30 if loaded else 0}}
        i = int(payload["q"])
        hit = (i < 29 if not payload["semantica"] else not (failure == "perdita" and i == 0))
        return {"ok": True, "evidence_scope": "metadata_only", "semantic_available": payload["semantica"],
                "risultati": [{"decisione_id": f"D{i}"}] if hit else []}

    monkeypatch.setattr(module, "request", request)
    monkeypatch.setattr(module, "memory", lambda: {})
    if failure:
        with pytest.raises(SystemExit):
            module.run()
    else:
        module.run()
    output = capsys.readouterr().out
    report = json.loads(output.split("RAPPORTO_SERVER_JSON=")[1])
    assert len(report["casi"]) == 30
    assert report["gate_superato"] is (failure is None)
    assert report["lessicale_top10"] == 29
    if failure == "perdita":
        assert report["perdite"] == ["S0"]
