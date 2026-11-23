"""Confronto degli scrittori sul banco di Lex (22 casi dell'avvocato + batteria), con il controllo dello schema.

Uso: python -m tests.lex_collaudo.scrittori <scrittore> [<scrittore> ...] [--solo-casi] [--max N]
     scrittore = «deterministico» | «ollama:<modello>» | «openai:<url base>|<modello>»
Attende che il carico del PC scenda sotto LEX_BANCO_CARICO_MAX (predefinito 16) prima di ogni domanda: i tempi
misurati sotto carico non valgono. Scrive i risultati in tests/lex_collaudo/risultati_scrittori.json.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from lex.harness.http import payload_harness
from lex.harness.scrittura import scrivi
from tests.lex_collaudo.punteggio import carica, carica_casi, valuta, valuta_caso

USCITA = Path(__file__).with_name("risultati_scrittori.json")


def _carico() -> float:
    return float(Path("/proc/loadavg").read_text().split()[0])


def _ram_libera_mb() -> int:
    for riga in Path("/proc/meminfo").read_text().splitlines():
        if riga.startswith("MemAvailable:"):
            return int(riga.split()[1]) // 1024
    return 0


def _gpu_mb() -> int:
    import subprocess

    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout
        return int(out.strip().splitlines()[0])
    except Exception:
        return -1


def _pressione_io() -> float:
    try:
        riga = Path("/proc/pressure/io").read_text().splitlines()[0]
        return float(riga.split("avg60=")[1].split()[0])
    except Exception:
        return 0.0


def _app_8080_risponde() -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/api/pronto", timeout=20) as r:
            return r.status == 200
    except Exception:
        return False


def _attendi_carico(massimo: float) -> None:
    """Pausa se il PC è carico, se l'8080 non risponde entro 20 s o se la pressione di I/O supera l'80% (avg60)."""
    while _carico() > massimo:
        time.sleep(30)
    pausa = 0
    while _pressione_io() > float(os.environ.get("LEX_BANCO_IO_MAX", "80")) or not _app_8080_risponde():
        if pausa == 0:
            print(f"[pausa] I/O {_pressione_io():.0f}% o 8080 lenta: attendo", flush=True)
        pausa += 1
        time.sleep(30)
    if pausa:
        print(f"[ripresa] dopo {pausa * 30} s", flush=True)


def _certa(domanda: str) -> str:
    from lex.risposte_certe import risposta_certa

    esito = risposta_certa(domanda)
    return esito.testo if esito else ""


def attiva_registro_grezzi() -> None:
    """Solo nel banco: con LEX_BANCO_GREZZI impostata, le risposte grezze dello scrittore vanno in quel file (0600)."""
    percorso = os.environ.get("LEX_BANCO_GREZZI")
    if not percorso:
        return
    import lex.harness.scrittura_segnaposto as segnaposto

    def registra(scrittore: str, schema: str, grezza: str) -> None:
        fd = os.open(percorso, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"scrittore": scrittore, "schema": schema, "grezza": grezza}, ensure_ascii=False) + "\n")

    segnaposto.registra_grezza = registra


def misura(scrittore: str, *, solo_casi: bool = False, massimo: int | None = None, modalita: str = "libera") -> dict:
    os.environ["LEX_HARNESS_SCRITTORE"] = ""  # lo schema si calcola sempre deterministico; la stesura si applica dopo
    carico_max = float(os.environ.get("LEX_BANCO_CARICO_MAX", "16"))
    voci = [("caso", c, c["domanda"]) for c in carica_casi()]
    if not solo_casi:
        voci += [("batteria", d, d["domanda"]) for d in carica()]
    if massimo:
        voci = voci[:massimo]
    righe, tempi = [], []
    for tipo, voce, domanda in voci:
        _attendi_carico(carico_max)
        payload = payload_harness(domanda, risposta_certa=_certa)
        testo = str(payload.get("answer") or "") if payload else ""
        operativa = payload is None
        if not (payload and payload.get("query_type") == "lex_harness"):
            st = None
        elif modalita == "segnaposto" and scrittore != "deterministico":
            from lex.harness.scrittura_segnaposto import scrivi_per_punto

            st = scrivi_per_punto(testo, scrittore, float(os.environ.get("LEX_HARNESS_SCRITTORE_TIMEOUT", "300")))
        else:
            st = scrivi(testo, None if scrittore == "deterministico" else scrittore)
        finale = st.testo if st else testo
        if st:
            tempi.append(st.secondi)
        esito = valuta_caso(voce, finale) if tipo == "caso" else valuta(voce, finale, operativa=operativa)
        corretta = esito.corretto if tipo == "caso" else esito.corretta
        inventate = (not esito.criteri.get("inventate", True)) if tipo == "caso" else bool(esito.inventate)
        righe.append({"tipo": tipo, "id": voce["id"], "corretta": corretta, "inventate": inventate,
                      "stesura_accettata": bool(st and st.accettata), "motivo": st.motivo if st else "",
                      "secondi": round(st.secondi, 1) if st else 0.0, "carico": _carico(), "ram_libera_mb": _ram_libera_mb(),
                      "gpu_mb": _gpu_mb()})
        if os.environ.get("LEX_BANCO_TESTI"):
            with open(os.environ["LEX_BANCO_TESTI"], "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"scrittore": scrittore, "modalita": modalita, "id": voce["id"], "schema": testo, "stesura": st.testo if st else "",
                                     "accettata": bool(st and st.accettata), "motivo": st.motivo if st else ""},
                                    ensure_ascii=False) + "\n")
        print(scrittore, modalita, voce["id"], corretta, righe[-1]["stesura_accettata"], righe[-1]["secondi"], righe[-1]["motivo"][:80], flush=True)
    casi = [r for r in righe if r["tipo"] == "caso"]
    bat = [r for r in righe if r["tipo"] == "batteria"]
    return {"scrittore": scrittore, "modalita": modalita, "casi_corretti": sum(r["corretta"] for r in casi), "casi": len(casi),
            "batteria_corrette": sum(r["corretta"] for r in bat), "batteria": len(bat),
            "norme_inventate": sum(r["inventate"] for r in righe),
            "stesure_accettate": sum(r["stesura_accettata"] for r in righe),
            "tempo_medio_s": round(sum(tempi) / len(tempi), 1) if tempi else 0.0, "tempo_max_s": round(max(tempi), 1) if tempi else 0.0,
            "ram_libera_min_mb": min((r["ram_libera_mb"] for r in righe), default=0),
            "gpu_max_mb": max((r["gpu_mb"] for r in righe), default=0),
            "carico_medio": round(sum(r["carico"] for r in righe) / len(righe), 1) if righe else 0.0, "righe": righe}


def main(argv: list[str]) -> int:
    attiva_registro_grezzi()
    solo = "--solo-casi" in argv
    massimo = int(argv[argv.index("--max") + 1]) if "--max" in argv else None
    scrittori = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] != "--max")]
    risultati = json.loads(USCITA.read_text(encoding="utf-8")) if USCITA.is_file() else {}
    modalita = [m for m in os.environ.get("LEX_BANCO_MODALITA", "libera,segnaposto").split(",") if m]
    for s, m in [(s, m) for s in scrittori for m in (modalita if s != "deterministico" else ["libera"])]:
        nome = s if m == "libera" else f"{s} [segnaposto]"
        risultati[nome] = misura(s, solo_casi=solo, massimo=massimo, modalita=m)
        USCITA.write_text(json.dumps(risultati, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        r = risultati[nome]
        print(f"== {nome}: casi {r['casi_corretti']}/{r['casi']}, batteria {r['batteria_corrette']}/{r['batteria']}, "
              f"norme inventate {r['norme_inventate']}, stesure accettate {r['stesure_accettate']}, tempo medio "
              f"{r['tempo_medio_s']} s, massimo {r['tempo_max_s']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
