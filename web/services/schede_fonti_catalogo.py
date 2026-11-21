"""Metadata-only native template inventory, with explicit normative bindings."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

SOURCES = {"master": "Catalogo professionale", "compiler": "Compilatore guidato", "builtin_workspace": "Archivio dei modelli"}
KINDS = {"master": "Modello di catalogo", "compiler": "Modello guidato", "repository": "Modello documentale"}


# Stessa materia scritta in modo diverso dai cataloghi d'origine: un solo nome (collaudo 21/11/2026).
MATERIE_EQUIVALENTI = {
    "amministrativo": "Diritto amministrativo", "civile": "Diritto civile", "penale": "Diritto penale",
    "tributario": "Diritto tributario", "diritto del lavoro": "Lavoro e previdenza", "lavoro e previdenza": "Lavoro e previdenza",
    "diritto di famiglia": "Famiglia e persone", "famiglia e persone": "Famiglia e persone",
}
_PAROLE_VUOTE = {"di", "del", "della", "dei", "delle", "e", "o", "a", "al", "alla", "per", "nel", "nella", "in", "da", "il",
                 "la", "lo", "le", "gli", "i", "un", "una", "con", "su", "ex", "art", "c", "p"}


def materia_canonica(value):
    nome = " ".join(str(value or "").replace("_", " ").split())
    return MATERIE_EQUIVALENTI.get(nome.casefold(), nome)


def _parole(titolo):
    return [w for w in re.split(r"[^0-9a-zàèéìòù]+", str(titolo or "").casefold().replace("’", "'")) if w]


@lru_cache(maxsize=1)
def collegamenti_verificati():
    """Tabella dei collegamenti modello -> scheda verificati a mano (stesso atto, stessa procedura)."""
    path = Path(__file__).resolve().parents[2] / "pct" / "schede_fonti" / "collegamenti_verificati.json"
    if not path.is_file():
        return {}
    return {str(k).upper(): str(v) for k, v in (json.loads(path.read_text(encoding="utf-8")).get("collegamenti") or {}).items()}


@lru_cache(maxsize=1)
def norme_atti():
    """Atti senza scheda propria con le norme che li disciplinano (``pct/schede_fonti/norme_atti.json``).

    Restituisce {id_atto: {"titolo", "modelli", "norme": [{"atto", "articolo", "perche"}]}}.
    """
    path = Path(__file__).resolve().parents[2] / "pct" / "schede_fonti" / "norme_atti.json"
    if not path.is_file():
        return {}
    dati = json.loads(path.read_text(encoding="utf-8")).get("atti") or {}
    return {aid: {"titolo": str(v.get("titolo") or aid), "modelli": [str(c).upper() for c in v.get("modelli") or []],
                  "norme": [{"atto": a, "articolo": r, "perche": perche} for a, r, perche in v.get("norme") or []]}
            for aid, v in dati.items()}


def _atto_senza_scheda(code):
    return next((aid for aid, v in norme_atti().items() if code.upper() in v["modelli"]), None)


def _collegamento_derivato(record, schede, bindings):
    """Scheda normativa di un modello senza collegamento esplicito, solo con una base certa nelle fonti del software.

    0. Tabella ``pct/schede_fonti/collegamenti_verificati.json`` (verificata titolo per titolo).
    1. Titolo identico a quello di una sola scheda (stesso atto, scritto uguale).
    2. Compilatore collegato espressamente (non di ripiego) a una sola scheda, e tutte le parole significative del
       titolo del modello presenti nel titolo della scheda (es. «Atto di citazione» -> «Atto di citazione ordinario»).
    Restituisce (scheda, motivo) oppure None: nei casi dubbi il modello resta «da associare».
    """
    verificata = collegamenti_verificati().get(str(record.get("codice") or "").upper())
    if verificata in schede:
        return verificata, "collegamento verificato allo stesso atto"
    titolo = " ".join(_parole(record.get("titolo")))
    if titolo:
        uguali = [sid for sid, data in schede.items() if " ".join(_parole(data.get("titolo"))) == titolo]
        if len(uguali) == 1:
            return uguali[0], "stesso titolo della scheda"
    compilatore = str(record.get("link_compilatore_code") or "").upper()
    esplicito = (str(record.get("compiler_binding_source") or "") == "link_compilatore_code"
                 and str(record.get("link_compilatore_tipo") or "") != "fallback")
    collegate = sorted(bindings.get(compilatore, set())) if compilatore and esplicito else []
    if len(collegate) == 1:
        significative = {w for w in _parole(record.get("titolo")) if w not in _PAROLE_VUOTE}
        della_scheda = set(_parole(schede[collegate[0]].get("titolo")))
        if len(significative) >= 2 and significative <= della_scheda:
            return collegate[0], f"compilatore {compilatore} della scheda"
    return None


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
        collegamento = "codice del modello" if linked else ""
        if not linked:
            derivato = _collegamento_derivato(record, schede, bindings)
            if derivato:
                linked, collegamento = [derivato[0]], derivato[1]
        atto = None if linked else _atto_senza_scheda(code)
        if atto:
            linked, collegamento = [atto], "norme dell'atto dalla tabella verificata"
        references = []
        for sid in linked:
            if sid not in schede:
                references.extend(norme_atti()[sid]["norme"])
                continue
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
            "materia": materia_canonica(record.get("materia") or record.get("macro_area") or record.get("area") or "Non classificata"),
            "tipo": KINDS.get(kind, "Modello"), "provenienza": SOURCES.get(source, source),
            "schede_normative": linked, "stato_norme": "associate" if len(linked) == 1 and references else "da_associare",
            "numero_riferimenti": len({(ref.get("atto"), ref.get("articolo")) for ref in references}),
            "collegamento": collegamento,
            "ricerca": (text + " " + normative_search).strip()})
    return sorted(output, key=lambda row: (row["titolo"].casefold(), row["provenienza"], row["id"]))


@lru_cache(maxsize=4)
def catalogo_modelli(directory):
    from pct.template_atti_unified_catalog import build_unified_template_catalog
    return catalog_from_records(build_unified_template_catalog(), schede_index(directory))


def modello(directory, identity):
    return next((row for row in catalogo_modelli(directory) if row["id"] == identity), None)
