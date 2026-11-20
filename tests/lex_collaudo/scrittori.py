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


def _attendi_carico(massimo: float) -> None:
    while _carico() > massimo:
        time.sleep(30)


def _certa(domanda: str) -> str:
    from lex.risposte_certe import risposta_certa

    esito = risposta_certa(domanda)
    return esito.testo if esito else ""


def misura(scrittore: str, *, solo_casi: bool = False, massimo: int | None = None) -> dict:
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
        st = scrivi(testo, None if scrittore == "deterministico" else scrittore) if payload and payload.get("query_type") == "lex_harness" else None
        finale = st.testo if st else testo
        if st:
            tempi.append(st.secondi)
        esito = valuta_caso(voce, finale) if tipo == "caso" else valuta(voce, finale, operativa=operativa)
        corretta = esito.corretto if tipo == "caso" else esito.corretta
        inventate = (not esito.criteri.get("inventate", True)) if tipo == "caso" else bool(esito.inventate)
        righe.append({"tipo": tipo, "id": voce["id"], "corretta": corretta, "inventate": inventate,
                      "stesura_accettata": bool(st and st.accettata), "motivo": st.motivo if st else "",
                      "secondi": round(st.secondi, 1) if st else 0.0, "carico": _carico(), "ram_libera_mb": _ram_libera_mb()})
        print(scrittore, voce["id"], corretta, righe[-1]["stesura_accettata"], righe[-1]["secondi"], righe[-1]["motivo"][:80], flush=True)
    casi = [r for r in righe if r["tipo"] == "caso"]
    bat = [r for r in righe if r["tipo"] == "batteria"]
    return {"scrittore": scrittore, "casi_corretti": sum(r["corretta"] for r in casi), "casi": len(casi),
            "batteria_corrette": sum(r["corretta"] for r in bat), "batteria": len(bat),
            "norme_inventate": sum(r["inventate"] for r in righe),
            "stesure_accettate": sum(r["stesura_accettata"] for r in righe),
            "tempo_medio_s": round(sum(tempi) / len(tempi), 1) if tempi else 0.0, "tempo_max_s": round(max(tempi), 1) if tempi else 0.0,
            "ram_libera_min_mb": min((r["ram_libera_mb"] for r in righe), default=0), "righe": righe}


def main(argv: list[str]) -> int:
    solo = "--solo-casi" in argv
    massimo = int(argv[argv.index("--max") + 1]) if "--max" in argv else None
    scrittori = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] != "--max")]
    risultati = json.loads(USCITA.read_text(encoding="utf-8")) if USCITA.is_file() else {}
    for s in scrittori:
        risultati[s] = misura(s, solo_casi=solo, massimo=massimo)
        USCITA.write_text(json.dumps(risultati, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        r = risultati[s]
        print(f"== {s}: casi {r['casi_corretti']}/{r['casi']}, batteria {r['batteria_corrette']}/{r['batteria']}, "
              f"norme inventate {r['norme_inventate']}, stesure accettate {r['stesure_accettate']}, tempo medio "
              f"{r['tempo_medio_s']} s, massimo {r['tempo_max_s']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
