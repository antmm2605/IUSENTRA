"""Metadata-only native template inventory, with explicit normative bindings."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

SOURCES = {"master": "Catalogo professionale", "compiler": "Compilatore guidato", "builtin_workspace": "Archivio dei modelli"}
KINDS = {"master": "Modello di catalogo", "compiler": "Modello guidato", "repository": "Modello documentale"}


@lru_cache(maxsize=4)
def schede_index(directory):
    return {str(data.get("id") or file.stem): data for file in sorted(Path(directory).glob("*.json"))
            for data in [json.loads(file.read_text(encoding="utf-8"))]}


def catalog_from_records(records, schede):
    bindings = {}
    for sid, data in schede.items():
        for code in [sid, *(data.get("template") or []), *(data.get("modelli_compilatore") or [])]:
            bindings.setdefault(str(code).upper(), set()).add(sid)
    output, seen = [], set()
    for record in records:
        identity = str(record.get("global_template_id") or "")
        if not re.fullmatch(r"tpl_[0-9a-f]{20}", identity) or identity in seen:
            raise ValueError("Native template identity missing or duplicated")
        seen.add(identity)
        code = str(record.get("codice") or "")
        linked = sorted(bindings.get(code.upper(), set()))
        references = []
        for sid in linked:
            data = schede[sid]
            references.extend(data.get("base_normativa") or [])
            references.extend(ref for field in data.get("campi") or [] for ref in field.get("norma") or [])
        normative_search = " ".join(f"{ref.get('atto', '')} art{ref.get('articolo', '')} articolo {ref.get('articolo', '')}" for ref in references)
        source = str(record.get("source") or "")
        kind = str(record.get("tipo_template") or "")
        compiler = str(record.get("link_compilatore_code") or code)
        compilation_url = f"/template-atti/{quote(code, safe='')}/usa" if source == "builtin_workspace" else f"/template-atti/compila/{quote(compiler, safe='')}"
        text = " ".join(str(record.get(key) or "") for key in ("titolo", "codice", "descrizione", "search_text", "materia", "area", "famiglia", "procedimento"))
        output.append({"id": identity, "codice": code, "compilazione_url": compilation_url, "titolo": str(record.get("titolo") or code),
            "materia": str(record.get("materia") or record.get("macro_area") or record.get("area") or "Non classificata").replace("_", " "),
            "tipo": KINDS.get(kind, "Modello"), "provenienza": SOURCES.get(source, source),
            "schede_normative": linked, "stato_norme": "associate" if len(linked) == 1 and references else "da_associare",
            "numero_riferimenti": len({(ref.get("atto"), ref.get("articolo")) for ref in references}),
            "ricerca": (text + " " + normative_search).strip()})
    return sorted(output, key=lambda row: (row["titolo"].casefold(), row["provenienza"], row["id"]))


@lru_cache(maxsize=4)
def catalogo_modelli(directory):
    from pct.template_atti_unified_catalog import build_unified_template_catalog
    return catalog_from_records(build_unified_template_catalog(), schede_index(directory))


def modello(directory, identity):
    return next((row for row in catalogo_modelli(directory) if row["id"] == identity), None)
