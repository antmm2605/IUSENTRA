"""Importa l'archivio open data della Corte costituzionale (pronunce + massime) nel corpus giurisprudenziale di Lex.

Dati: https://dati.cortecostituzionale.it — licenza CC BY-SA 3.0, attribuzione «Corte costituzionale».
Vedi pct/corte_costituzionale_opendata.py e docs/LEX_FONTI_LOCALI_E_SERVER.md.

Uso:
    # zip gia' scaricati nella cartella (P_json<periodo>.zip, CC_OpenMassime_<periodo>.zip)
    python tools/cortecost_importa.py --cartella /data/fonti/cortecost --db /data/intelligence/giurisprudenza_corpus.db
    # scarica dal sito ufficiale e importa tutti i corpus (globale + ogni studio)
    python tools/cortecost_importa.py --cartella /data/fonti/cortecost --scarica --tutti-i-tenant
    # aggiornamento settimanale: solo 2001_oggi, solo anno corrente e precedente
    python tools/cortecost_importa.py --cartella ... --scarica --periodi 2001_oggi --anni-recenti 2 --tutti-i-tenant
    # solo se il corpus non contiene ancora la Consulta (deploy una tantum)
    python tools/cortecost_importa.py --cartella ... --scarica --tutti-i-tenant --se-assente

Codice di uscita: 0 riuscito (anche nulla da fare), 1 errore di lettura/scrittura, 2 download non riuscito.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
if str(RADICE) not in sys.path:
    sys.path.insert(0, str(RADICE))

from pct.corte_costituzionale_opendata import (  # noqa: E402
    PERIODI,
    archivio_completo_presente,
    file_periodo,
    importa,
    scarica,
)
from pct.giurisprudenza_corpus import derive_corpus_db_path  # noqa: E402


def corpus_dei_tenant(registry: str, data_root: str) -> list[str]:
    """Corpus del dato globale e di ogni studio registrato (o, senza registro, delle cartelle tenants/*)."""

    percorsi: list[str] = []
    radice = Path(data_root)
    globale = os.getenv("PCT_GIURISPRUDENZA_DB") or str(radice / "intelligence" / "giurisprudenza.json")
    percorsi.append(derive_corpus_db_path(globale))
    cartelle: list[Path] = []
    registro = Path(registry)
    if registro.exists():
        try:
            from pct.tenant import GestioneTenant

            gestore = GestioneTenant(str(registro))
            for studio in gestore.lista():
                cartelle.append(gestore._data_dir(studio.slug))
        except Exception as exc:  # registro illeggibile: si ripiega sulle cartelle
            print(f"Attenzione: registro tenant non leggibile ({exc}); uso le cartelle {radice / 'tenants'}", file=sys.stderr)
    if not cartelle and (radice / "tenants").is_dir():
        cartelle = [path for path in sorted((radice / "tenants").iterdir()) if path.is_dir()]
    for cartella in cartelle:
        percorso = derive_corpus_db_path(str(cartella / "intelligence" / "giurisprudenza.json"))
        if percorso not in percorsi:
            percorsi.append(percorso)
    return percorsi


def _blocca(percorso: Path):
    """Lock esclusivo non bloccante (deploy e job settimanale non scrivono insieme). False se occupato."""

    try:
        import fcntl
    except ImportError:  # Windows: nessun lock, uso da riga di comando
        return None
    handle = open(percorso, "a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return False
    return handle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cartella", required=True, help="cartella degli zip (P_json<periodo>.zip, CC_OpenMassime_<periodo>.zip)")
    parser.add_argument("--periodi", nargs="*", default=list(PERIODI), choices=list(PERIODI), help="periodi da leggere (default: tutti)")
    parser.add_argument("--scarica", action="store_true", help="scarica prima gli zip dal sito ufficiale")
    parser.add_argument("--db", action="append", default=[], help="corpus SQLite di destinazione (ripetibile)")
    parser.add_argument("--tenant-dir", action="append", default=[], help="cartella dati di uno studio (usa <dir>/intelligence/giurisprudenza_corpus.db)")
    parser.add_argument("--tutti-i-tenant", action="store_true", help="corpus globale e di ogni studio del registro tenant")
    parser.add_argument("--registry", default=os.getenv("PCT_TENANTS_REGISTRY", "/data/tenants.json"), help="registro tenant")
    parser.add_argument("--data-root", default=os.getenv("PCT_DATA_ROOT", "/data"), help="radice dati")
    parser.add_argument("--dal-anno", type=int, default=0, help="importa solo le pronunce da quest'anno")
    parser.add_argument("--anni-recenti", type=int, default=0, help="importa solo gli ultimi N anni (1 = anno corrente)")
    parser.add_argument("--se-assente", action="store_true", help="salta i corpus che hanno gia' completato l'import dell'archivio intero")
    parser.add_argument("--blocco", type=int, default=500, help="righe per transazione")
    parser.add_argument("--dry-run", action="store_true", help="legge e conta senza scrivere")
    parser.add_argument("--json", action="store_true", help="riepilogo in JSON")
    args = parser.parse_args(argv)

    destinazioni: list[str] = list(args.db)
    for cartella in args.tenant_dir:
        destinazioni.append(derive_corpus_db_path(str(Path(cartella) / "intelligence" / "giurisprudenza.json")))
    if args.tutti_i_tenant:
        destinazioni.extend(corpus_dei_tenant(args.registry, args.data_root))
    destinazioni = list(dict.fromkeys(destinazioni))
    if not destinazioni and not args.dry_run:
        print("ERRORE: indicare --db, --tenant-dir o --tutti-i-tenant", file=sys.stderr)
        return 1
    if args.se_assente:
        gia = [path for path in destinazioni if archivio_completo_presente(path)]
        destinazioni = [path for path in destinazioni if path not in gia]
        for path in gia:
            print(f"Archivio della Corte costituzionale gia' importato: {path}")
        if not destinazioni and not args.dry_run:
            print("Nulla da importare.")
            return 0

    Path(args.cartella).mkdir(parents=True, exist_ok=True)
    blocco_lock = _blocca(Path(args.cartella) / ".cortecost_importa.lock")
    if blocco_lock is False:
        print("Un altro import della Corte costituzionale e' in corso: nulla da fare.")
        return 0

    dal_anno = args.dal_anno
    if args.anni_recenti > 0:
        dal_anno = max(dal_anno, date.today().year - args.anni_recenti + 1)

    if args.scarica:
        try:
            scaricati = scarica(args.cartella, args.periodi)
            print(f"Scaricati {len(scaricati)} file in {args.cartella}")
        except Exception as exc:
            print(f"ERRORE: download open data della Corte costituzionale non riuscito: {exc}", file=sys.stderr)
            return 2

    coppie = []
    for periodo in args.periodi:
        pronunce, massime = file_periodo(args.cartella, periodo)
        if pronunce is None:
            print(f"Attenzione: manca il file delle pronunce {periodo} in {args.cartella}", file=sys.stderr)
            continue
        if massime is None:
            print(f"Attenzione: manca il file delle massime {periodo}: pronunce senza massime", file=sys.stderr)
        coppie.append((pronunce, massime))
    if not coppie:
        print("ERRORE: nessun file di pronunce da importare", file=sys.stderr)
        return 1

    try:
        esito = importa(
            coppie,
            destinazioni,
            dal_anno=dal_anno,
            dry_run=args.dry_run,
            blocco=args.blocco,
            progresso=None if args.json else (lambda riga: print(f"  {riga}", flush=True)),
            completo=set(args.periodi) == set(PERIODI) and not dal_anno,
        )
    except Exception as exc:
        print(f"ERRORE: import non riuscito: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(esito.to_dict(), ensure_ascii=False, indent=1))
    else:
        print(
            f"Corte costituzionale: {esito.pronunce_lette} pronunce lette ({esito.con_massime} con massime, "
            f"{esito.massime} massime), {esito.inserite} inserite, {esito.aggiornate} aggiornate, "
            f"{esito.invariate} invariate, {esito.pronunce_scartate} scartate in {esito.secondi}s"
            + (" [dry-run]" if esito.dry_run else "")
        )
        for path, mb in esito.dimensione_db_mb.items():
            print(f"  {path}: {mb} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
