"""Genera, riconvalida e pubblica le schede di istituto (lex/conoscenza).

Uso:
  python scripts/conoscenza_schede_istituto.py genera     # rigenera dalle fonti, nuova revisione se cambia qualcosa
  python scripts/conoscenza_schede_istituto.py viste      # solo index.md, log.md e pagine (proiezioni dei record)
  python scripts/conoscenza_schede_istituto.py verifica   # stato di oggi: schede da riesaminare (fonte cambiata)
  python scripts/conoscenza_schede_istituto.py lint [--registra]  # controllo della wiki (rapporto nel registro)
  python scripts/conoscenza_schede_istituto.py notturno   # riconvalida notturna nella cartella dei dati

La generazione legge solo fonti già canoniche del software (regole dell'harness, norme vigenti, passaggi delle
pronunce, modelli d'atto, calcolatori); non chiama modelli linguistici né la rete.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))
os.environ.setdefault("LEX_HARNESS_GIURISPRUDENZA", "0")
os.environ.setdefault("LEX_HARNESS_ARCHIVIO_VIVO", "0")  # versioni riproducibili: istantanea delle norme del prodotto


def main(argv: list[str]) -> int:
    from lex.conoscenza import deposito
    from lex.conoscenza.consultazione import schede, stato_attuale
    from lex.conoscenza.generatore import genera_scheda
    from lex.conoscenza.istituti import carica

    passo = argv[1] if len(argv) > 1 else "genera"
    materie, istituti = carica()
    if passo == "genera":
        t = time.time()
        nuove = [genera_scheda(i) for i in istituti]
        esito = deposito.aggiorna(nuove)
        viste = deposito.scrivi_viste(materie)
        print(json.dumps({"schede": len(nuove), **esito, **viste, "secondi": round(time.time() - t, 1)}, ensure_ascii=False))
    elif passo == "viste":
        print(json.dumps(deposito.scrivi_viste(materie), ensure_ascii=False))
    elif passo == "verifica":
        da_rivedere = []
        for s in schede():
            st = stato_attuale(s)
            if st["stato"] == "da_riesaminare":
                da_rivedere.append({"id": s["id"], "motivi": st["motivi"]})
        print(json.dumps({"schede": len(schede()), "da_riesaminare": da_rivedere}, ensure_ascii=False, indent=1))
        return 1 if da_rivedere else 0
    elif passo == "lint":
        from lex.conoscenza.lint import controlla, registra

        rapporto = controlla(viste=deposito.VISTE)
        if "--registra" in argv:
            registra(rapporto)
        print(json.dumps({k: rapporto[k] for k in ("eseguito_il", "schede", "conteggi")}, ensure_ascii=False))
        for x in rapporto["segnalazioni"]:
            print(f"- [{x['gravita']}] {x['categoria']} {x['scheda']} {x['oggetto']}: {x['descrizione']}")
        return 1 if rapporto["segnalazioni"] else 0
    elif passo == "notturno":
        from lex.conoscenza.notturno import riconvalida_notturna

        esito = riconvalida_notturna()
        print(json.dumps(esito, ensure_ascii=False, indent=1))
        return 0 if esito.get("ok") else 1
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
