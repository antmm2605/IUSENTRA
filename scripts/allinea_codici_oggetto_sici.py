#!/usr/bin/env python3
"""Allinea catalogo codici oggetto, catalogo UI e Guida Pratica agli XSD SICI in esercizio.

Fonte: PST, "Nuovi XSD SICI - 12/05/2026" (XSD_SICI_20260508.zip, in esercizio dal
14/05/2026) e Nota modifiche XSD versione 1 dell'11/05/2026. Il pacchetto differisce dal
precedente (XSD_SICI_20260116.zip) solo per `Atti/sici/tipi-base.xsd`: gli altri schemi sono
identici, quindi i riferimenti di provenienza vengono aggiornati al pacchetto in esercizio.

Uso dalla root del repository:
    python scripts/allinea_codici_oggetto_sici.py            # scrive i file
    python scripts/allinea_codici_oggetto_sici.py --check    # verifica senza scrivere
Dopo la scrittura rigenerare la KB completa con `python scripts/merge_legal_kb_modules.py`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.guida_pratica.sici_catalog_alignment import (  # noqa: E402
    align_catalog_records,
    align_kb_items,
    build_ui_catalog,
    load_sici_codici_oggetto,
)
from pct.pst_catalog import (  # noqa: E402
    PST_SICI_XSD_20260512_PACKAGE_NAME,
    PST_SICI_XSD_20260512_PACKAGE_SHA256,
    PST_SICI_XSD_ACTIVE_TIPI_BASE,
)

CATALOG = ROOT / "pct" / "data" / "cataloghi" / "codici_oggetto_pst.json"
UI_CATALOG = ROOT / "pct" / "data" / "cataloghi" / "codici_oggetto_pst_ui.json"
KB_MODULE = ROOT / "pct" / "data" / "legal_knowledge_base_modules" / "kb_99_completamento_codici_ufficiali.json"
OLD_SOURCE = "XSD_SICI_20260116/XSD_SICI_20260116/Atti/sici/tipi-base.xsd"
NEW_SOURCE = "XSD_SICI_20260508/XSD_SICI_20260508/Atti/sici/tipi-base.xsd"
CATALOG_VERSION = "2026-09-11.pst-xsd-official"
CATALOG_DATE = "2026-09-11"
# Nota modifiche 11/05/2026: l'oggetto 171404 riguarda l'amministrazione straordinaria
# delle grandi imprese in stato di insolvenza (D.L. 347/2003, conv. L. 39/2004).
MARZANO_NORMATIVA = {
    "fonte": "D.L. 347/2003 conv. L. 39/2004",
    "articolo": "1 ss.",
    "descrizione": "Amministrazione straordinaria delle grandi imprese in stato di insolvenza (legge Marzano)",
}


def dump_indented(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def dump_compact(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"


def align_sources(catalog: dict) -> None:
    for source in catalog.get("fonti") or []:
        if source.get("registro") == "SICID":
            source["zipFonte"] = PST_SICI_XSD_20260512_PACKAGE_NAME
            source["sha256Zip"] = PST_SICI_XSD_20260512_PACKAGE_SHA256
            source["aggiornatoPst"] = "2026-05-12"


def build_outputs() -> tuple[dict[Path, str], dict]:
    official = load_sici_codici_oggetto(ROOT / PST_SICI_XSD_ACTIVE_TIPI_BASE)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    ui_previous = json.loads(UI_CATALOG.read_text(encoding="utf-8"))
    records, report = align_catalog_records(catalog["records"], official, old_source=OLD_SOURCE, new_source=NEW_SOURCE)
    catalog["records"] = records
    catalog["versione"] = CATALOG_VERSION
    catalog["generatoIl"] = CATALOG_DATE
    align_sources(catalog)
    ui_keys = list(ui_previous["records"][0].keys())
    ui_catalog = build_ui_catalog(catalog, ui_keys)

    kb = json.loads(KB_MODULE.read_text(encoding="utf-8").replace(OLD_SOURCE, NEW_SOURCE))
    by_code = {record["codice"]: record for record in records}
    codes = set(report.descrizioni_corrette) | set(report.registro_aggiunto)
    kb_changed = align_kb_items(kb["codici_materia"], by_code, codes, old_source=OLD_SOURCE, new_source=NEW_SOURCE)
    for item in kb["codici_materia"]:
        if item.get("codice") == "171404" and MARZANO_NORMATIVA not in item.get("normativa", []):
            item.setdefault("normativa", []).insert(3, dict(MARZANO_NORMATIVA))
    outputs = {
        CATALOG: dump_indented(catalog),
        UI_CATALOG: dump_compact(ui_catalog),
        KB_MODULE: dump_indented(kb),
    }
    return outputs, {**report.to_dict(), "schede_guida_pratica": kb_changed, "codici_ufficiali": len(official)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Non scrive: esce con 1 se i file non sono allineati.")
    args = parser.parse_args()
    outputs, report = build_outputs()
    stale = [str(path.relative_to(ROOT)) for path, content in outputs.items() if path.read_text(encoding="utf-8") != content]
    if not args.check:
        for path, content in outputs.items():
            path.write_text(content, encoding="utf-8")
    print(json.dumps({"ok": not (args.check and stale), "file_da_aggiornare": stale, **report}, ensure_ascii=False, indent=2))
    return 1 if args.check and stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
