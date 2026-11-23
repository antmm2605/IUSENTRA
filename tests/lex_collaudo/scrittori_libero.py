"""I 22 casi dell'avvocato in testo libero con uno scrittore: schema deterministico, stesura, controllo, punteggio."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from lex.harness.http import payload_harness
from lex.harness.scrittura import scrivi
from tests.lex_collaudo.punteggio import carica_casi, valuta_caso
from tests.lex_collaudo.scrittori import _attendi_carico, _carico, _gpu_mb, _ram_libera_mb, attiva_registro_grezzi

LIBERO = Path(__file__).with_name("casi_avvocato_testo_libero.json")


def main(scrittore: str, uscita: str) -> int:
    os.environ["LEX_HARNESS_SCRITTORE"] = ""
    os.environ.setdefault("LEX_HARNESS_GIURISPRUDENZA", "0")
    attese = {c["id"]: c for c in carica_casi()}
    righe = []
    for caso in json.loads(LIBERO.read_text(encoding="utf-8"))["casi"]:
        _attendi_carico(999)
        p = payload_harness(caso["domanda"])
        schema = str((p or {}).get("answer") or "")
        if os.environ.get("LEX_BANCO_MODALITA_LIBERO", "") == "segnaposto":
            from lex.harness.scrittura_segnaposto import scrivi_per_punto

            st = scrivi_per_punto(schema, scrittore, float(os.environ.get("LEX_HARNESS_SCRITTORE_TIMEOUT", "300")))
        else:
            st = scrivi(schema, scrittore)
        e = valuta_caso(attese[caso["id"]], st.testo)
        r = {"id": caso["id"], "corretto": e.corretto, "mancanze": e.mancanze, "accettata": st.accettata, "motivo": st.motivo,
             "secondi": round(st.secondi, 1), "carico": _carico(), "gpu_mb": _gpu_mb(), "ram_libera_mb": _ram_libera_mb(),
             "schema": schema, "stesura": st.testo}
        righe.append(r)
        print("libero", scrittore, caso["id"], e.corretto, st.accettata, r["secondi"], st.motivo[:90], flush=True)
        with open(uscita, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"scrittore": scrittore, "modalita": os.environ.get("LEX_BANCO_MODALITA_LIBERO", "") or "libera", **r}, ensure_ascii=False) + "\n")
    tempi = [r["secondi"] for r in righe if r["secondi"]]
    print(f"== libero {os.environ.get('LEX_BANCO_MODALITA_LIBERO', '') or 'libera'} {scrittore}: corretti {sum(r['corretto'] for r in righe)}/{len(righe)}, accettate "
          f"{sum(r['accettata'] for r in righe)}, tempo medio {round(sum(tempi) / len(tempi), 1) if tempi else 0} s, "
          f"massimo {max(tempi) if tempi else 0} s", flush=True)
    return 0


if __name__ == "__main__":
    attiva_registro_grezzi()
    # Entrambe le modalità, una dopo l'altra: stesura libera e stesura con segnaposto.
    for modo in (os.environ.get("LEX_BANCO_MODALITA_LIBERO") or "libera,segnaposto").split(","):
        os.environ["LEX_BANCO_MODALITA_LIBERO"] = "" if modo == "libera" else modo
        main(sys.argv[1], sys.argv[2])
    raise SystemExit(0)
