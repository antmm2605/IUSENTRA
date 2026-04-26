from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Permette di eseguire questo file direttamente con:
#   python tools/normattiva_multi_sync.py --list
# anche su Windows, senza impostare manualmente PYTHONPATH.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lex.normativa.normattiva_client import NormattivaClient, write_manifest


DEFAULT_STUDIO_LEGALE_CORE = [
    # Più utili per Lex AI e pratica professionale
    "Codici",
    "Testi Unici",
    "Decreti Legislativi",
    "DPR",
    "DPCM",
    "DL e leggi di conversione",
    "Regolamenti ministeriali",
    "Regolamenti governativi",
    "Regolamenti di delegificazione",
    "Leggi costituzionali",
    "Leggi finanziarie e di bilancio",
    "Leggi di ratifica",
    "Leggi delega e relativi provvedimenti delegati",
    "Leggi di delegazione europea",

    # Da tenere opzionali/storiche
    # "Atti normativi abrogati (in originale)",
    # "DL decaduti",
    # "DL proroghe",
    # "Regi decreti",
    # "Regi decreti legislativi",
    # "Decreti legislativi luogotenenziali",
]


def load_names_from_json(path: str | Path) -> list[str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    if isinstance(data, list):
        return [str(x).strip() for x in data if str(x).strip()]

    if isinstance(data, dict):
        for key in ("collections", "nomi", "names"):
            if isinstance(data.get(key), list):
                return [str(x).strip() for x in data[key] if str(x).strip()]

    raise ValueError("Formato JSON non valido. Usa una lista o {'collections': [...]}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Normattiva multi-collezione downloader")
    parser.add_argument("--list", action="store_true", help="Mostra le collezioni disponibili")
    parser.add_argument("--save-list", help="Salva l'elenco collezioni in JSON")
    parser.add_argument("--download", action="append", help="Scarica una specifica collezione. Ripetibile.")
    parser.add_argument("--download-core", action="store_true", help="Scarica il set core per studio legale")
    parser.add_argument("--download-all-from-api", action="store_true", help="Scarica tutte le collezioni restituite dall'API")
    parser.add_argument("--names-file", help="File JSON con elenco collezioni da scaricare")
    parser.add_argument("--out", default="data/normativa/raw", help="Cartella output ZIP")
    parser.add_argument("--manifest", default="data/normativa/manifests/normattiva_download_manifest.json")
    parser.add_argument("--formato", default="XML", choices=["XML"], help="Formato download")
    parser.add_argument("--vigenza", default="ORIGINALE", choices=["ORIGINALE", "VIGENTE"], help="Vigenza richiesta")
    parser.add_argument("--formato-richiesta", default=None, help="Codice diretto, es. O o V. Sovrascrive --vigenza.")
    parser.add_argument("--overwrite", action="store_true", help="Riscarica anche se il file esiste")
    parser.add_argument("--sleep", type=float, default=2.0, help="Secondi tra un download e l'altro")
    args = parser.parse_args()

    client = NormattivaClient(sleep_seconds=args.sleep)

    if args.list or args.save_list:
        names = client.list_collection_names()
        for n in names:
            print(n)

        if args.save_list:
            Path(args.save_list).parent.mkdir(parents=True, exist_ok=True)
            Path(args.save_list).write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\nSalvato: {args.save_list}")

        if args.list and not (args.download or args.download_core or args.download_all_from_api or args.names_file):
            return

    names_to_download: list[str] = []

    if args.download:
        names_to_download.extend(args.download)

    if args.download_core:
        names_to_download.extend(DEFAULT_STUDIO_LEGALE_CORE)

    if args.names_file:
        names_to_download.extend(load_names_from_json(args.names_file))

    if args.download_all_from_api:
        names_to_download.extend(client.list_collection_names())

    # Dedup mantenendo ordine
    seen = set()
    names_to_download = [n for n in names_to_download if not (n in seen or seen.add(n))]

    if not names_to_download:
        parser.error("Nessuna collezione indicata. Usa --list, --download-core, --download, --names-file o --download-all-from-api.")

    results = client.download_many(
        names_to_download,
        output_dir=args.out,
        formato=args.formato,
        vigenza=args.vigenza,
        formato_richiesta=args.formato_richiesta,
        overwrite=args.overwrite,
    )

    write_manifest(results, args.manifest)

    print("\nDownload completato.")
    print(f"ZIP salvati in: {args.out}")
    print(f"Manifest: {args.manifest}")


if __name__ == "__main__":
    main()
