from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

# Permette di eseguire questo file direttamente con:
#   python tools/normattiva_multi_sync.py --list
# anche su Windows, senza impostare manualmente PYTHONPATH.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lex.normativa.normattiva_client import (  # noqa: E402
    VIGENZA_TO_FORMATO_RICHIESTA,
    NormattivaClient,
    write_manifest,
)


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


def load_json(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def catalog_state_path(manifest_path: str | Path) -> Path:
    manifest = Path(manifest_path)
    return manifest.with_name(f"{manifest.stem}_catalog_state.json")


def catalog_signatures(raw: object, formato_richiesta: str) -> dict[str, dict]:
    signatures: dict[str, dict] = {}
    if not isinstance(raw, list):
        return signatures
    expected = str(formato_richiesta or "").strip().upper()
    for row in raw:
        if not isinstance(row, dict):
            continue
        name = str(row.get("nomeCollezione") or row.get("nome") or "").strip()
        formato = str(row.get("formatoCollezione") or "").strip().upper()
        if not name or (expected and formato and formato != expected):
            continue
        signatures[name] = {
            "nomeCollezione": name,
            "formatoCollezione": formato or expected,
            "descrizioneFormatoCollezione": row.get("descrizioneFormatoCollezione") or "",
            "dataCreazione": row.get("dataCreazione") or "",
            "numeroAtti": row.get("numeroAtti") or 0,
        }
    return signatures


def state_key(name: str, formato_richiesta: str) -> str:
    return f"{name}|{formato_richiesta.strip().upper()}"


def manifest_has_existing_file(manifest: dict, name: str, formato_richiesta: str) -> bool:
    for item in list(manifest.get("items") or []):
        if not isinstance(item, dict):
            continue
        if str(item.get("collection_name") or "") != name:
            continue
        if str(item.get("formato_richiesta") or "").strip().upper() != formato_richiesta.strip().upper():
            continue
        output_path = Path(str(item.get("output_path") or ""))
        if output_path.exists() and output_path.is_file():
            return True
    return False


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
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Mantiene una sola copia per collezione/formato/vigenza, eliminando ZIP precedenti quando il contenuto cambia.",
    )
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

    formato_richiesta = args.formato_richiesta or VIGENZA_TO_FORMATO_RICHIESTA.get(args.vigenza.strip().upper())
    previous_manifest = load_json(args.manifest)
    previous_state = load_json(catalog_state_path(args.manifest)).get("collections") or {}
    remote_signatures: dict[str, dict] = {}
    if formato_richiesta and not args.overwrite:
        try:
            remote_signatures = catalog_signatures(client.list_collections_raw(), formato_richiesta)
        except Exception as exc:
            print(f"[AVVISO] Catalogo Normattiva non letto, procedo con verifica download: {exc}")

    skipped: list[str] = []
    download_now: list[str] = []
    for name in names_to_download:
        signature = remote_signatures.get(name)
        key = state_key(name, formato_richiesta or "")
        if (
            signature
            and previous_state.get(key) == signature
            and manifest_has_existing_file(previous_manifest, name, formato_richiesta or "")
        ):
            skipped.append(name)
            continue
        download_now.append(name)

    if skipped:
        print("Collezioni gia' aggiornate, download saltato:")
        for name in skipped:
            print(f"- {name}")

    results = client.download_many(
        download_now,
        output_dir=args.out,
        formato=args.formato,
        vigenza=args.vigenza,
        formato_richiesta=formato_richiesta,
        overwrite=args.overwrite,
        replace_existing=args.replace_existing,
    )

    write_manifest(
        results,
        args.manifest,
        previous_items=[item for item in list(previous_manifest.get("items") or []) if isinstance(item, dict)],
    )
    if remote_signatures:
        next_state = dict(previous_state)
        result_names = {result.collection_name for result in results}
        for name in sorted(set(skipped) | result_names):
            signature = remote_signatures.get(name)
            if signature:
                next_state[state_key(name, formato_richiesta or "")] = signature
        state_payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "collections": next_state,
        }
        state_target = catalog_state_path(args.manifest)
        state_target.parent.mkdir(parents=True, exist_ok=True)
        state_target.write_text(json.dumps(state_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nDownload completato.")
    print(f"ZIP salvati in: {args.out}")
    print(f"Manifest: {args.manifest}")
    print(f"Nuovi/scaricati: {len(results)} - gia' presenti: {len(skipped)}")


if __name__ == "__main__":
    main()
