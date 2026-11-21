"""Presidio delle norme delle schede dei modelli d'atto (passaggio notturno e comandi per l'avvocato).

Uso:
  python tools/schede_fonti.py notturno --db /data/normativa/codici_leggi.sqlite [--stato ...] [--simula]
  python tools/schede_fonti.py proposte --db ... [--scheda CIV_ORD_023]
  python tools/schede_fonti.py decidi --db ... --id 12 --esito approvata|respinta --avvocato "Avv. Nome Cognome" [--nota ...]
  python tools/schede_fonti.py approva-scheda --db ... --scheda CIV_ORD_023 --avvocato "Avv. Nome Cognome"
  python tools/schede_fonti.py ritira-superate --db ... [--simula]   (proposte «fonte da valutare» non più prodotte)

Il notturno: 1) acquisisce dalle fonti ufficiali gli atti richiesti dalle schede e assenti dalla biblioteca;
2) verifica ogni norma citata (presenza, abrogazione, impronta); 3) apre le proposte di revisione; 4) scrive il
rapporto JSON accanto al database. Prima di aprire le fonti suggerite ritira quelle aperte e mai decise che la logica
per atto non produce più (motivo nella nota). Uscita 0 anche con proposte aperte; 1 solo se il database non e' leggibile.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
if str(RADICE) not in sys.path:
    sys.path.insert(0, str(RADICE))

from lex.normativa.biblioteca.acquisizione import acquisisci  # noqa: E402
from pct.schede_fonti.proposte import (  # noqa: E402
    approva_scheda, fonti_suggerite, registra_esiti, ritira_suggerimenti_superati)
from pct.schede_fonti.repository import RepositorySchedeFonti  # noqa: E402
from pct.schede_fonti.verifica import riepilogo, verifica_schede  # noqa: E402


def _repo(args) -> RepositorySchedeFonti:
    return RepositorySchedeFonti(Path(args.stato or Path(args.db).with_name("schede_fonti.sqlite")))


def notturno(args) -> int:
    db = Path(args.db)
    if not db.is_file():
        print(f"ERRORE: biblioteca non trovata: {db}", file=sys.stderr)
        return 1
    acquisizione = acquisisci(db, Path(args.pacchetti or db.with_name("biblioteca_automatica")), simula=args.simula)
    # Atti senza scheda propria (pct/schede_fonti/norme_atti.json): anche le loro fonti mancanti si acquisiscono
    # da Normattiva (es. R.D. 499/1929 per il decreto tavolare), con URN e data nel rapporto.
    from web.services.schede_fonti_runtime import riferimenti_atti_senza_scheda
    altri = acquisisci(db, Path(args.pacchetti or db.with_name("biblioteca_automatica")), simula=args.simula,
                       riferimenti=riferimenti_atti_senza_scheda())
    acquisizione.esiti.extend(altri.esiti)
    recuperi=[]
    if not args.simula:
        from lex.normativa.biblioteca.recupero import riprendi_pendenti

        recuperi=riprendi_pendenti(db,db.parent/"recuperi_normativi")
    esiti = verifica_schede(db)
    # Anche le norme degli atti senza scheda propria (tabella verificata) si controllano ogni notte.
    from web.services.schede_fonti_runtime import riferimenti_atti_senza_scheda
    esiti += verifica_schede(db, riferimenti=riferimenti_atti_senza_scheda())
    repo = _repo(args)
    conteggi = registra_esiti(repo, esiti)
    conteggi["fonti_suggerite_ritirate"] = len(ritira_suggerimenti_superati(repo))
    conteggi["fonti_suggerite_nuove"] = fonti_suggerite(repo)
    rapporto = {"eseguito_il": dt.datetime.now().isoformat(timespec="seconds"), "acquisizione": acquisizione.to_dict(),
                "recuperi_puntuali": recuperi, "verifica": riepilogo(esiti), "conteggi": conteggi, "proposte_aperte": len(repo.proposte())}
    Path(args.rapporto or db.with_name("schede_fonti_rapporto.json")).write_text(
        json.dumps(rapporto, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: rapporto[k] for k in ("conteggi", "proposte_aperte")} |
                     {"acquisiti": [e.chiave for e in acquisizione.esiti if e.stato == "importato"],
                      "non_acquisiti": [(e.chiave, e.stato) for e in acquisizione.esiti if e.stato != "importato"]},
                     ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="comando", required=True)
    for nome in ("notturno", "proposte", "decidi", "approva-scheda", "ritira-superate"):
        s = sub.add_parser(nome)
        s.add_argument("--db", required=True, help="biblioteca codici_leggi.sqlite")
        s.add_argument("--stato", default="", help="database del presidio (default: schede_fonti.sqlite accanto)")
    sub.choices["notturno"].add_argument("--pacchetti", default="")
    sub.choices["notturno"].add_argument("--rapporto", default="")
    sub.choices["notturno"].add_argument("--simula", action="store_true", help="non scarica e non importa")
    sub.choices["proposte"].add_argument("--scheda", default="")
    for k in ("--id", "--esito", "--avvocato"):
        sub.choices["decidi"].add_argument(k, required=True)
    sub.choices["decidi"].add_argument("--nota", default="")
    sub.choices["approva-scheda"].add_argument("--scheda", required=True)
    sub.choices["approva-scheda"].add_argument("--avvocato", required=True)
    sub.choices["ritira-superate"].add_argument("--simula", action="store_true", help="elenca senza ritirare")
    a = p.parse_args(argv)
    if a.comando == "notturno":
        return notturno(a)
    repo = _repo(a)
    if a.comando == "proposte":
        for r in repo.proposte(scheda=a.scheda):
            print(f"[{r['id']}] {r['tipo']} {r['scheda']} — {r['motivo']}")
        return 0
    if a.comando == "ritira-superate":
        ritirate = ritira_suggerimenti_superati(repo, simula=a.simula)
        print(json.dumps({"simula": a.simula, "ritirate": len(ritirate), "elenco": ritirate}, ensure_ascii=False))
        return 0
    if a.comando == "decidi":
        repo.decidi_proposta(int(a.id), a.esito, avvocato=a.avvocato, nota=a.nota)
        print("registrato")
        return 0
    n = approva_scheda(repo, verifica_schede(Path(a.db), solo_scheda=a.scheda), a.scheda, a.avvocato)
    print(f"{n} norme approvate per {a.scheda}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
