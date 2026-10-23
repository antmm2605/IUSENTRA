"""Gate sul server: dati congelati, processo HTTP persistente e lista unica."""
import hashlib
import json
import statistics
import time
import urllib.request
from pathlib import Path


def request(path, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request("http://127.0.0.1:8092" + path, body,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as response:
        return json.load(response)


def memory():
    result = {}
    for name in ("memory.current", "memory.peak", "memory.max"):
        path = Path("/sys/fs/cgroup") / name
        if path.exists():
            result[name] = path.read_text().strip()
    for line in Path("/proc/1/status").read_text().splitlines():
        if line.startswith(("VmRSS:", "VmHWM:")):
            key, value = line.split(":", 1)
            result[key] = value.strip()
    return result


def run():
    source = Path(__file__).with_name("benchmark-server-30.json")
    protocol = json.loads(source.with_name("benchmark-server-protocollo.json").read_text())
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == protocol["sha256"]
    cases = json.loads(source.read_text())
    assert len(cases) >= 30 and len({c["attesa_decisione"] for c in cases}) == len(cases)
    # Aspetta solo il servizio: nessuna inferenza durante l'attesa.
    for attempt in range(60):
        try:
            before = request("/health")
            if before["configured"]:
                break
        except (OSError, ValueError):
            pass
        time.sleep(1)
    else:
        raise RuntimeError("Motore non pronto")
    assert before["reranker_cache"]["caricati"] == 0, "Serve un processo nuovo per misurare il freddo"
    report = {"sha256_domande": digest, "protocollo": protocol, "health_prima": before,
              "memoria_prima": memory(), "casi": [], "errori": [], "training": False}
    for case in cases:
        row = {"id": case["id"], "attesa_decisione": case["attesa_decisione"]}
        payload = {key: case[key] for key in ("q", "dal", "al")}
        for mode, semantic in (("lessicale", False), ("ibrida", True)):
            started = time.perf_counter()
            result = request("/search", {**payload, "semantica": semantic})
            elapsed = time.perf_counter() - started
            ids = [r["decisione_id"] for r in result.get("risultati", [])]
            valid = (result.get("ok") and result.get("evidence_scope") == "metadata_only"
                     and len(ids) <= 10 and (not semantic or result.get("semantic_available")))
            row[mode] = {"top10": ids, "secondi": elapsed, "valida": bool(valid),
                         "posizione": ids.index(case["attesa_decisione"]) + 1 if case["attesa_decisione"] in ids else None}
            if not valid:
                report["errori"].append({"id": case["id"], "canale": mode})
        row["memoria"] = memory()
        report["casi"].append(row)
        print(json.dumps({"progresso": case["id"], "lessicale": row["lessicale"]["posizione"],
                          "ibrida": row["ibrida"]["posizione"], "secondi": row["ibrida"]["secondi"]}), flush=True)
    start = time.perf_counter()
    first = cases[0]
    repeated = request("/search", {"q": first["q"], "dal": first["dal"], "al": first["al"], "semantica": True})
    report["ripetizione_caldo_s"] = time.perf_counter() - start
    report["ripetizione_stabile"] = ([r["decisione_id"] for r in repeated["risultati"]]
                                        == report["casi"][0]["ibrida"]["top10"])
    report["health_dopo"] = after = request("/health")
    report["memoria_dopo"] = memory()
    lexical = sum(bool(r["lessicale"]["posizione"]) for r in report["casi"])
    hybrid = sum(bool(r["ibrida"]["posizione"]) for r in report["casi"])
    losses = [r["id"] for r in report["casi"] if r["lessicale"]["posizione"] and not r["ibrida"]["posizione"]]
    warm = sorted(r["ibrida"]["secondi"] for r in report["casi"][1:])
    report.update({"lessicale_top10": lexical, "ibrida_top10": hybrid, "perdite": losses,
                   "freddo_s": report["casi"][0]["ibrida"]["secondi"],
                   "caldo_mediana_s": statistics.median(warm), "caldo_p95_s": warm[int(.95 * (len(warm) - 1))],
                   "caldo_massimo_s": max(warm)})
    persistent = (before["pid"] == after["pid"] and after["reranker_cache"]["caricati"] == 1
                  and after["reranker_cache"]["misses"] == 1 and after["reranker_cache"]["hits"] >= len(cases))
    report["classificatore_persistente"] = persistent
    report["gate_superato"] = (hybrid > lexical and not losses and not report["errori"]
                               and persistent and report["ripetizione_stabile"])
    print("RAPPORTO_SERVER_JSON=" + json.dumps(report, ensure_ascii=False), flush=True)
    if not report["gate_superato"]:
        raise SystemExit("Nuovo campione non conferma il vantaggio senza perdite: collegamento al gestionale invariato")


if __name__ == "__main__":
    run()
