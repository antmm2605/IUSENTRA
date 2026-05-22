"""Servizio deterministicamente verificabile per la Guida Pratica IUSENTRA.

Obiettivo operativo:
- quando l'avvocato apre un fascicolo, risolvere il codice oggetto/materia;
- mostrare una guida concreta: cosa verificare, cosa redigere, quali allegati/campi/avvertimenti servono;
- coprire tutti i codici presenti nel catalogo PST/XSD con guide curate, lasciando gli alias interni fuori dal deposito.

Le guide curate vivono nel knowledge base separato in `pct/data/legal_knowledge_base.full.json`
e nei moduli `pct/data/legal_knowledge_base_modules/`.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Iterable


class GuidaPraticaError(ValueError):
    """Errore applicativo del modulo Guida Pratica."""


def _text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text if text else default


_SEARCH_STOPWORDS = {
    "a",
    "ad",
    "al",
    "alla",
    "alle",
    "anche",
    "art",
    "azione",
    "azioni",
    "causa",
    "che",
    "con",
    "contro",
    "da",
    "dal",
    "dei",
    "del",
    "della",
    "delle",
    "di",
    "e",
    "ed",
    "ex",
    "fase",
    "fascicolo",
    "giudice",
    "il",
    "in",
    "la",
    "le",
    "materia",
    "nel",
    "per",
    "procedimento",
    "rg",
    "ricorso",
    "studio",
    "tribunale",
}


def _fold_for_search(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", _text(value).casefold())
    ascii_text = "".join(char for char in raw if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()


def _search_tokens(*values: Any) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for token in _fold_for_search(value).split():
            if token.isdigit() or len(token) < 3 or token in _SEARCH_STOPWORDS:
                continue
            tokens.add(token)
    return tokens


def normalize_codice_materia(value: Any) -> str:
    """Normalizza un codice materia/PST mantenendo zero iniziali e codici logici.

    I codici SICID/SIVG numerici restano numerici; se arrivano come 5 cifre vengono
    riallineati a 6 cifre (`30011` -> `030011`). I codici logici usati quando la
    tabella ministeriale puntuale non è disponibile, ad esempio `ESEC_MOB_001` o
    `LAV_LIC_001`, vengono conservati in maiuscolo.
    """

    raw = _text(value)
    if not raw:
        return ""
    if re.search(r"[A-Za-z]", raw):
        return re.sub(r"[^A-Za-z0-9_-]+", "_", raw.strip().upper()).strip("_")
    raw = re.sub(r"[^0-9]", "", raw)
    if len(raw) == 5:
        return raw.zfill(6)
    return raw


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _unique_by_json(items: Iterable[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _deep_merge(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    """Merge profondo standard: dict ricorsivi, liste additive, scalari override."""

    result = deepcopy(parent)
    for key, value in child.items():
        if key in {"differenze_rispetto_a_padre", "eredita_da"}:
            continue
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        elif isinstance(value, list) and isinstance(result.get(key), list):
            result[key] = _unique_by_json([*result[key], *deepcopy(value)])
        else:
            result[key] = deepcopy(value)
    return result


@dataclass(frozen=True)
class GuidaPraticaCoverage:
    level: str
    source: str
    needs_reviewer: bool
    message: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "source": self.source,
            "needs_reviewer": self.needs_reviewer,
            "message": self.message,
        }


class GuidaPraticaService:
    """Risoluzione guida per codice materia/PST e checklist fascicolo.

    Il servizio è volutamente stateless e caricabile anche nei test. In produzione viene creato dal bridge Flask.
    """

    def __init__(self, kb_path: str | Path | None = None, catalog_records: Iterable[dict[str, Any]] | None = None) -> None:
        data_dir = Path(__file__).resolve().parents[1] / "data"
        self.kb_path = Path(kb_path) if kb_path else data_dir / "legal_knowledge_base.full.json"
        self._kb = self._load_kb(self.kb_path)
        # Se il file full non esiste ancora, carica il KB storico + i moduli separati.
        if not self._kb.get("codici_materia") and kb_path is None:
            self._kb = self._load_kb_modules(data_dir)
        self._kb_index = self._build_kb_index(self._kb)
        self._catalog_records = list(catalog_records) if catalog_records is not None else self._load_catalog_records()
        self._official_catalog_index = {
            normalize_codice_materia(row.get("codice") or row.get("codice_logico")): row
            for row in self._catalog_records
            if normalize_codice_materia(row.get("codice") or row.get("codice_logico"))
        }
        self._catalog_index = dict(self._official_catalog_index)
        # I codici guida devono comparire nella ricerca anche quando sono alias interni.
        for codice, item in self._kb_index.items():
            if codice not in self._catalog_index:
                self._catalog_index[codice] = self._catalog_row_from_kb_item(codice, item)

    @staticmethod
    def _load_kb(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"codici_materia": []}
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {"codici_materia": []}

    @staticmethod
    def _load_kb_modules(data_dir: Path) -> dict[str, Any]:
        """Carica moduli KB anche senza full JSON.

        Supporta moduli con `codici_materia` top-level e addendum con
        `sezioni[].codici_materia`; fonde i duplicati, dando priorità ai file top9
        e al modulo sfratti storico.
        """

        modules_dir = data_dir / "legal_knowledge_base_modules"
        if not modules_dir.exists():
            modules_dir = data_dir / "legal_kb"
        files: list[Path] = []
        storico = data_dir / "legal_knowledge_base.json"
        if storico.exists():
            files.append(storico)
        if modules_dir.exists():
            files.extend(sorted(path for path in modules_dir.glob("kb_*.json") if path.name != "kb_index.json"))

        def _priority(path: Path) -> int:
            name = path.name.lower()
            if "top9" in name:
                return 900
            if "sfratti" in name or "kb_00" in name:
                return 800
            if "logiche_legacy" in name:
                return 100
            if "addendum" in name or "kb_15" in name:
                return 650
            return 500

        def _meta(path: Path, payload: dict[str, Any], section: dict[str, Any] | None = None) -> dict[str, str]:
            section = section if isinstance(section, dict) else {}
            macro = _as_dict(payload.get("macro_area"))
            return {
                "file": path.name,
                "macro_area_id": _text(payload.get("macro_area_id") or section.get("macro_area_riferimento") or macro.get("codice") or path.stem),
                "denominazione": _text(payload.get("denominazione") or section.get("sezione") or macro.get("label") or path.stem),
                "registro": _text(payload.get("registro") or section.get("registro") or macro.get("registro") or macro.get("registro_sicid")),
            }

        def _iter_items(path: Path, payload: dict[str, Any]):
            base_meta = _meta(path, payload)
            for item in _as_list(payload.get("codici_materia")):
                if isinstance(item, dict):
                    yield base_meta, item
            for section in _as_list(payload.get("sezioni")):
                if not isinstance(section, dict):
                    continue
                meta = _meta(path, payload, section)
                for item in _as_list(section.get("codici_materia")):
                    if isinstance(item, dict):
                        yield meta, item

        by_code: dict[str, dict[str, Any]] = {}
        modules: list[dict[str, str]] = []
        module_names: set[str] = set()
        duplicates: dict[str, list[str]] = {}
        for path in sorted(files, key=lambda item: (_priority(item), item.name)):
            try:
                payload = GuidaPraticaService._load_kb(path)
            except Exception:
                continue
            base_meta = _meta(path, payload)
            if path.name not in module_names:
                modules.append(base_meta)
                module_names.add(path.name)
            for meta, item in _iter_items(path, payload):
                codice = normalize_codice_materia(item.get("codice") or item.get("codice_logico"))
                if not codice:
                    continue
                row = deepcopy(item)
                row.setdefault("codice", codice)
                row.setdefault("categoria", meta["denominazione"])
                row.setdefault("_source_file", path.name)
                row.setdefault("_macro_area_id", meta["macro_area_id"])
                row.setdefault("_macro_area_denominazione", meta["denominazione"])
                row.setdefault("_registro", meta["registro"])
                if codice in by_code:
                    previous = by_code[codice]
                    row = _deep_merge(previous, row)
                    row["_source_files"] = _unique_by_json([*(previous.get("_source_files") or [previous.get("_source_file")]), path.name])
                    row["_source_file"] = path.name
                    duplicates.setdefault(codice, []).append(path.name)
                else:
                    row["_source_files"] = [path.name]
                by_code[codice] = row
        combined: dict[str, Any] = {
            "$schema": "iusentra/legal-knowledge-base/v1",
            "name": "IUSENTRA Legal Knowledge Base modulare",
            "version": "modulare-v4",
            "codici_materia": [by_code[codice] for codice in sorted(by_code)],
            "moduli": modules,
            "duplicates_merged": duplicates,
        }
        combined["n_codici"] = len(combined["codici_materia"])
        return combined

    @staticmethod
    def _catalog_row_from_kb_item(codice: str, item: dict[str, Any]) -> dict[str, Any]:
        atto = _as_dict(item.get("atto_principale"))
        registri = item.get("uffici_destinatari") if isinstance(item.get("uffici_destinatari"), list) else []
        if item.get("_registro") and item.get("_registro") not in registri:
            registri = [item.get("_registro"), *registri]
        return {
            "codice": codice,
            "descrizione": _text(item.get("denominazione"), f"Codice materia {codice}"),
            "area": _text(item.get("_macro_area_denominazione") or item.get("categoria")),
            "area_label": _text(item.get("_macro_area_denominazione") or item.get("categoria")),
            "parent_codice": _text(item.get("eredita_da")),
            "parent_label": "",
            "registri": ", ".join(_text(value) for value in registri if _text(value)),
            "file_fonte": _text(atto.get("schema_xsd_ministeriale")),
            "source_file": _text(item.get("_source_file") or item.get("kb_source_file")),
        }

    @staticmethod
    def _build_kb_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for item in _as_list(payload.get("codici_materia")):
            if not isinstance(item, dict):
                continue
            codice = normalize_codice_materia(item.get("codice") or item.get("codice_logico"))
            if codice:
                row = deepcopy(item)
                row.setdefault("codice", codice)
                out[codice] = row
        return out

    @staticmethod
    def _load_catalog_records() -> list[dict[str, Any]]:
        """Carica i codici oggetto PST/XSD dal loader di prodotto o dal JSON diretto.

        Il loader `pct.pratiche_collegate_catalog` resta la fonte canonica nel prodotto.
        Il fallback diretto rende però il modulo testabile anche quando si applica questa patch
        prima del wiring completo del repository.
        """

        try:
            from pct.pratiche_collegate_catalog import list_codici_oggetto_pst

            rows = [dict(row) for row in list_codici_oggetto_pst()]
            if rows:
                return rows
        except Exception:
            pass

        catalog_path = Path(__file__).resolve().parents[1] / "data" / "cataloghi" / "codici_oggetto_pst.json"
        try:
            with catalog_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return []
        records = payload.get("records") if isinstance(payload, dict) else []
        out: list[dict[str, Any]] = []
        for record in records if isinstance(records, list) else []:
            if not isinstance(record, dict):
                continue
            out.append(
                {
                    "codice": _text(record.get("codice")),
                    "descrizione": _text(record.get("descrizione")),
                    "area": _text(record.get("area")),
                    "area_label": _text(record.get("area_label") or record.get("area")),
                    "parent_codice": _text(record.get("parent_codice") or record.get("codicePadre")),
                    "parent_label": _text(record.get("parent_label") or record.get("descrizionePadre")),
                    "registri": ", ".join(_text(item) for item in record.get("registri", []) if _text(item))
                    if isinstance(record.get("registri"), list)
                    else _text(record.get("registri")),
                    "file_fonte": _text(record.get("file_fonte") or record.get("fileFonte")),
                }
            )
        return out

    def catalog_size(self) -> int:
        return len(self._catalog_index)

    def official_catalog_size(self) -> int:
        return len(self._official_catalog_index)

    def list_guidance(self, *, query: str = "", coverage: str = "", limit: int = 2000) -> list[dict[str, Any]]:
        """Lista sintetica di copertura guida per catalogo UI/admin."""

        needle = query.strip().casefold()
        wanted_coverage = coverage.strip().casefold()
        rows: list[dict[str, Any]] = []
        for codice, catalog_row in sorted(self._catalog_index.items()):
            guida_curata = codice in self._kb_index
            cov = self._coverage_for(codice, guida_curata=guida_curata)
            if wanted_coverage and cov.level.casefold() != wanted_coverage:
                continue
            label = _text(catalog_row.get("descrizione")) or _text(self._kb_index.get(codice, {}).get("denominazione"))
            haystack = f"{codice} {label} {_text(catalog_row.get('area'))} {_text(catalog_row.get('parent_codice'))}".casefold()
            if needle and needle not in haystack:
                continue
            rows.append(
                {
                    "codice": codice,
                    "denominazione": label,
                    "area": _text(catalog_row.get("area")),
                    "area_label": _text(catalog_row.get("area_label")),
                    "parent_codice": _text(catalog_row.get("parent_codice")),
                    "parent_label": _text(catalog_row.get("parent_label")),
                    "registri": _text(catalog_row.get("registri")),
                    "file_fonte": _text(catalog_row.get("file_fonte")),
                    "codice_deposito": self._deposit_code_payload(codice),
                    "coverage": cov.to_payload(),
                }
            )
            if len(rows) >= limit:
                break
        # Se il KB contiene codici non presenti nel catalogo seed, li mostriamo comunque come curati.
        for codice, item in sorted(self._kb_index.items()):
            if codice in self._catalog_index:
                continue
            label = _text(item.get("denominazione"))
            if needle and needle not in f"{codice} {label}".casefold():
                continue
            cov = self._coverage_for(codice, guida_curata=True)
            if wanted_coverage and cov.level.casefold() != wanted_coverage:
                continue
            rows.append(
                {
                    "codice": codice,
                    "denominazione": label,
                    "area": _text(item.get("categoria")),
                    "area_label": _text(item.get("categoria")),
                    "parent_codice": "",
                    "parent_label": "",
                    "registri": _text(item.get("registro_sicid")),
                    "file_fonte": _text(_as_dict(item.get("atto_principale")).get("schema_xsd_ministeriale")),
                    "codice_deposito": self._deposit_code_payload(codice),
                    "coverage": cov.to_payload(),
                }
            )
            if len(rows) >= limit:
                break
        return rows

    def suggest_guidance_from_fascicolo(self, fascicolo: dict[str, Any], *, min_score: float = 0.72) -> dict[str, Any] | None:
        """Suggerisce una guida ufficiale quando il fascicolo non ha ancora il codice PST.

        La Guida Pratica è un supporto facoltativo per l'avvocato: quando oggetto o
        titolo sono sufficientemente chiari, propone una scheda coerente senza rendere
        quel collegamento un requisito per continuare il lavoro sul fascicolo.
        """

        candidates = [
            ("oggetto", fascicolo.get("oggetto") or fascicolo.get("object")),
            ("titolo", fascicolo.get("titolo") or fascicolo.get("title")),
            ("tipo_procedimento", fascicolo.get("tipo_procedimento") or fascicolo.get("procedureType")),
            ("area_pratica", fascicolo.get("area_pratica") or fascicolo.get("practiceArea")),
            ("procedura_operativa", fascicolo.get("procedura_operativa_nome") or fascicolo.get("proceduraOperativaNome")),
        ]
        best: dict[str, Any] | None = None
        for source, raw_query in candidates:
            query = _text(raw_query)
            query_folded = _fold_for_search(query)
            query_tokens = _search_tokens(query)
            if not query_folded or len(query_tokens) < 2:
                continue
            for codice, row in self._official_catalog_index.items():
                candidate_label = self._candidate_label(codice, row)
                candidate_folded = _fold_for_search(candidate_label)
                candidate_tokens = _search_tokens(candidate_label)
                if not candidate_tokens:
                    continue
                score = 0.0
                reason = "token"
                if len(candidate_folded) >= 18 and candidate_folded in query_folded:
                    score = 0.99
                    reason = "descrizione completa nel fascicolo"
                elif len(query_folded) >= 18 and query_folded in candidate_folded:
                    score = 0.97
                    reason = "oggetto completo nel catalogo"
                else:
                    overlap = query_tokens & candidate_tokens
                    if len(overlap) < 3:
                        continue
                    recall = len(overlap) / max(1, len(query_tokens))
                    precision = len(overlap) / max(1, len(candidate_tokens))
                    score = (recall * 0.72) + (precision * 0.28)
                    if recall < 0.58:
                        continue
                if score < min_score:
                    continue
                if best is None or score > float(best["score"]):
                    best = {
                        "codice": codice,
                        "denominazione": _text(row.get("descrizione")) or _text(self._kb_index.get(codice, {}).get("denominazione")),
                        "score": round(score, 3),
                        "source_field": source,
                        "matched_by": reason,
                        "confirmation_required": True,
                        "message": "Guida pratica facoltativa suggerita dal contesto del fascicolo. Il codice ufficiale resta nella scheda fascicolo e la guida non blocca il lavoro.",
                    }
        return best

    def _candidate_label(self, codice: str, catalog_row: dict[str, Any]) -> str:
        item = self._kb_index.get(codice, {})
        values = [
            catalog_row.get("descrizione"),
            catalog_row.get("parent_label"),
            catalog_row.get("area_label"),
            catalog_row.get("area"),
            item.get("denominazione"),
            item.get("categoria"),
            item.get("sottocategoria"),
        ]
        return " ".join(_text(value) for value in values if _text(value))

    def get_guidance(self, codice_materia: Any, *, fascicolo: dict[str, Any] | None = None) -> dict[str, Any]:
        """Restituisce la guida completa per codice.

        Se il codice è curato, applica l'ereditarietà e normalizza i campi.
        Se manca, genera una guida base partendo dal catalogo PST/XSD.
        """

        codice = normalize_codice_materia(codice_materia)
        if not codice:
            raise GuidaPraticaError("Codice materia non indicato.")
        if codice in self._kb_index:
            payload = self._resolve_curated(codice)
            coverage = self._coverage_for(codice, guida_curata=True)
        else:
            payload = self._generate_from_catalog(codice)
            coverage = self._coverage_for(codice, guida_curata=False)
        payload = self._normalise_guidance_payload(payload, codice=codice, coverage=coverage, fascicolo=fascicolo or {})
        return payload

    def _coverage_for(self, codice: str, *, guida_curata: bool) -> GuidaPraticaCoverage:
        if guida_curata:
            item = self._kb_index.get(codice, {})
            atto = _as_dict(item.get("atto_principale"))
            diff = _as_dict(item.get("differenze_rispetto_a_padre"))
            parent = self._kb_index.get(normalize_codice_materia(item.get("eredita_da")), {})
            parent_atto = _as_dict(parent.get("atto_principale"))
            has_practical_fields = bool(
                _as_list(atto.get("campi_chiave"))
                or _as_list(atto.get("campi_obbligatori"))
                or _as_list(atto.get("campi_specifici"))
                or _as_list(diff.get("campi_aggiuntivi"))
                or _as_list(diff.get("campi_obbligatori_aggiuntivi"))
                or _as_list(item.get("allegati_obbligatori"))
                or _as_list(item.get("adempimenti_propedeutici"))
                or _as_list(parent_atto.get("campi_chiave"))
                or _as_list(parent_atto.get("campi_obbligatori"))
                or _as_list(parent.get("allegati_obbligatori"))
                or _as_list(parent.get("adempimenti_propedeutici"))
            )
            if not has_practical_fields:
                return GuidaPraticaCoverage(
                    level="curata_parziale",
                    source="legal_knowledge_base.full.json / moduli KB + profilo pratico base",
                    needs_reviewer=True,
                    message="Scheda normativa presente nel KB; campi, allegati e adempimenti sono integrati con profilo pratico base da revisionare.",
                )
            return GuidaPraticaCoverage(
                level="curata",
                source="legal_knowledge_base.full.json / moduli KB",
                needs_reviewer=False,
                message="Guida curata nel knowledge base modulare e pronta per l'uso operativo.",
            )
        if codice in self._catalog_index:
            return GuidaPraticaCoverage(
                level="profilo_generato",
                source="catalogo PST/XSD + profilo operativo prudenziale",
                needs_reviewer=True,
                message="Codice presente nel catalogo XSD/PST: guida base generata, da completare con revisione normativa.",
            )
        return GuidaPraticaCoverage(
            level="catalogo_base",
            source="fallback manuale",
            needs_reviewer=True,
            message="Codice non trovato nel catalogo caricato: guida minima, verificare XSD ministeriale e classificazione.",
        )

    def _resolve_curated(self, codice: str, seen: set[str] | None = None) -> dict[str, Any]:
        seen = seen or set()
        if codice in seen:
            raise GuidaPraticaError(f"Ereditarietà circolare nel knowledge base: {codice}.")
        seen.add(codice)
        item = deepcopy(self._kb_index[codice])
        parent_code = normalize_codice_materia(item.get("eredita_da"))
        if parent_code:
            if parent_code not in self._kb_index:
                raise GuidaPraticaError(f"Padre {parent_code} non presente per codice {codice}.")
            parent = self._resolve_curated(parent_code, seen)
            item = _deep_merge(parent, item)
            item = self._apply_differences(item, _as_dict(self._kb_index[codice].get("differenze_rispetto_a_padre")))
            item["eredita_da"] = parent_code
        return item

    def _apply_differences(self, payload: dict[str, Any], differences: dict[str, Any]) -> dict[str, Any]:
        """Applica le differenze semantiche usate nel KB iniziale."""

        if not differences:
            return payload
        out = deepcopy(payload)
        atto = out.setdefault("atto_principale", {})
        for key, value in differences.items():
            if key in {"presupposti_sostanziali_aggiuntivi", "presupposti_aggiuntivi"}:
                out["presupposti_sostanziali"] = _unique_by_json([*_as_list(out.get("presupposti_sostanziali")), *_as_list(value)])
            elif key in {"campi_obbligatori_aggiuntivi", "campi_aggiuntivi"}:
                atto["campi_obbligatori"] = _unique_by_json([*_as_list(atto.get("campi_obbligatori")), *_as_list(value)])
            elif key in {"normativa_aggiuntiva", "normativa_principale"}:
                normativa = out.setdefault("normativa", {})
                if isinstance(normativa, list):
                    normativa = {"riferimenti_primari": normativa, "riferimenti_secondari": []}
                    out["normativa"] = normativa
                target = "riferimenti_primari" if key == "normativa_principale" else "riferimenti_secondari"
                normativa[target] = _unique_by_json([*_as_list(normativa.get(target)), *_as_list(value)])
            elif key in {"atto_principale_specifico", "atto_specifico"}:
                if isinstance(value, dict):
                    atto.update(deepcopy(value))
            elif key in {"presupposti_specifici", "presupposti_sostanziali_specifici"}:
                out["presupposti_sostanziali"] = _unique_by_json([*_as_list(out.get("presupposti_sostanziali")), *_as_list(value)])
            elif key == "avvertimenti_obbligatori_aggiuntivi":
                atto["avvertimenti_obbligatori"] = _unique_by_json([*_as_list(atto.get("avvertimenti_obbligatori")), *_as_list(value)])
            elif key == "allegati_obbligatori_aggiuntivi":
                out["allegati_obbligatori"] = _unique_by_json([*_as_list(out.get("allegati_obbligatori")), *_as_list(value)])
            elif key == "adempimenti_propedeutici_aggiuntivi":
                out["adempimenti_propedeutici"] = _unique_by_json([*_as_list(out.get("adempimenti_propedeutici")), *_as_list(value)])
            else:
                out[key] = deepcopy(value)
        termine_grazia = _as_dict(out.get("termine_grazia"))
        if termine_grazia.get("applicabile") is False:
            warnings = [
                warning
                for warning in _as_list(atto.get("avvertimenti_obbligatori"))
                if "art. 55" not in _text(warning).lower() and "termine di grazia" not in _text(warning).lower()
            ]
            atto["avvertimenti_obbligatori"] = warnings
            redazionali = _as_list(out.get("avvertenze_redazionali"))
            out["avvertenze_redazionali"] = _unique_by_json([
                *redazionali,
                "Il termine di grazia ex art. 55 L. 392/1978 risulta non applicabile: non inserire il relativo avvertimento se il profilo conferma l'uso diverso.",
            ])
        return out

    def _generate_from_catalog(self, codice: str) -> dict[str, Any]:
        catalog = self._catalog_index.get(codice, {})
        label = _text(catalog.get("descrizione")) or f"Codice materia {codice}"
        parent_label = _text(catalog.get("parent_label"))
        area_label = _text(catalog.get("area_label") or catalog.get("area"))
        profile = self._profile_for(label, parent_label, area_label)
        return {
            "codice": codice,
            "denominazione": label,
            "categoria": area_label or "Catalogo PST/XSD",
            "sottocategoria": parent_label,
            "registro_sicid": _text(catalog.get("registri")) or "Da verificare in base al registro ministeriale",
            "uffici_destinatari": ["SICID"],
            "normativa": profile["normativa"],
            "presupposti_sostanziali": profile["presupposti"],
            "adempimenti_propedeutici": profile["adempimenti"],
            "atto_principale": {
                "tipo_atto": profile["tipo_atto"],
                "denominazione": label,
                "schema_xsd_ministeriale": _text(catalog.get("file_fonte")) or "tipi-base.xsd",
                "struttura_obbligatoria": profile["struttura"],
                "campi_obbligatori": profile["campi"],
                "avvertimenti_obbligatori": profile["avvertimenti"],
            },
            "allegati_obbligatori": profile["allegati"],
            "adempimenti_fiscali_telematici": profile["fiscali"],
            "termini_processuali": profile["termini"],
            "avvertenze_redazionali": profile["avvertenze"],
        }

    def _profile_for(self, label: str, parent_label: str, area_label: str) -> dict[str, Any]:
        hay = f"{label} {parent_label} {area_label}".casefold()
        base = self._base_profile()
        if "ingiun" in hay or "decreto ingiuntivo" in hay:
            return self._profile_ingiunzione(base)
        if "sequestro" in hay or "cautelar" in hay or "urgenza" in hay or "700" in hay:
            return self._profile_cautelare(base)
        if "accertamento tecnico" in hay or "696" in hay or "istruzione preventiva" in hay:
            return self._profile_atp(base)
        if "possess" in hay or "reintegrazione" in hay or "manutenzione" in hay:
            return self._profile_possessorio(base)
        if "sfratto" in hay or "rilascio" in hay or "locazione" in hay:
            return self._profile_locazione(base)
        if "lavor" in hay or "previd" in hay:
            return self._profile_lavoro(base)
        if "esecuz" in hay or "precetto" in hay or "pignor" in hay:
            return self._profile_esecuzione(base)
        if "famiglia" in hay or "mantenimento" in hay or "minori" in hay:
            return self._profile_famiglia(base)
        return base

    def _base_profile(self) -> dict[str, Any]:
        campi = [
            {"id": "tribunale", "label": "Ufficio giudiziario competente", "type": "select_ufficio", "required": True},
            {"id": "parte_assistita", "label": "Parte assistita / ricorrente / attrice", "type": "object_persona", "required": True},
            {"id": "controparte", "label": "Controparte / resistente / convenuta", "type": "object_persona", "required": True},
            {"id": "difensore", "label": "Difensore e domicilio digitale", "type": "object_avvocato", "required": True},
            {"id": "oggetto_domanda", "label": "Oggetto della domanda", "type": "textarea", "required": True},
            {"id": "valore_causa", "label": "Valore della causa", "type": "currency", "required": True},
        ]
        return {
            "tipo_atto": "atto_introduttivo_o_deposito_generico",
            "normativa": {
                "riferimenti_primari": [
                    {"fonte": "c.p.c.", "articolo": "125", "descrizione": "Contenuto degli atti di parte"},
                    {"fonte": "c.p.c.", "articolo": "163 o 414 / rito applicabile", "descrizione": "Contenuto atto introduttivo da verificare in base al rito"},
                ],
                "riferimenti_secondari": [
                    {"fonte": "D.P.R. 115/2002", "articolo": "9 ss.", "descrizione": "Contributo unificato e spese di giustizia"},
                ],
            },
            "presupposti": [
                "Identificare esattamente rito, competenza, parti e legittimazione attiva/passiva.",
                "Verificare prescrizione/decadenza e condizioni di procedibilità applicabili.",
                "Raccogliere documenti essenziali e prova del mandato professionale.",
            ],
            "adempimenti": [
                {"step": 1, "azione": "Verifica competenza per materia, valore e territorio", "obbligatorio": True},
                {"step": 2, "azione": "Verifica condizioni di procedibilità e ADR obbligatorie", "obbligatorio": True},
                {"step": 3, "azione": "Acquisizione procura alle liti", "obbligatorio": True},
                {"step": 4, "azione": "Calcolo contributo unificato e anticipazione forfetaria", "obbligatorio": True},
            ],
            "struttura": [
                {"sezione": "Intestazione", "contenuto": "Ufficio, registro e parti"},
                {"sezione": "Parti", "contenuto": "Dati anagrafici/fiscali e difensore"},
                {"sezione": "Premesse", "contenuto": "Fatti rilevanti e documenti"},
                {"sezione": "Diritto", "contenuto": "Norme e argomentazioni"},
                {"sezione": "Conclusioni", "contenuto": "Domande al giudice"},
                {"sezione": "Valore", "contenuto": "Valore causa e contributo unificato"},
                {"sezione": "Allegati", "contenuto": "Elenco numerato"},
            ],
            "campi": campi,
            "avvertimenti": [
                "Avvertimenti di rito applicabili al procedimento selezionato, da verificare prima della notifica/deposito.",
                "Avvertimento sulla possibilità di patrocinio a spese dello Stato quando dovuto.",
            ],
            "allegati": [
                {"id": "procura", "label": "Procura alle liti", "required": True},
                {"id": "documenti_fondativi", "label": "Documenti fondativi della domanda", "required": True},
                {"id": "documento_identita_cliente", "label": "Documento identità / visura della parte assistita", "required": False},
            ],
            "fiscali": {
                "contributo_unificato": {"scaglione": "Da calcolare in base al valore e al rito"},
                "marca_bollo": {"importo_euro": 27.0, "note": "Verificare esenzioni e aggiornamenti"},
                "deposito_telematico": {"obbligatorio": True, "modalita": "Busta telematica con atto principale e DatiAtto.xml coerente con XSD"},
            },
            "termini": [
                {"termine": "Termini di costituzione/notifica", "durata_giorni": None, "decorrenza": "Da verificare secondo il rito", "tipo": "variabile"},
            ],
            "avvertenze": [
                "Profilo generato automaticamente: completare la guida con revisione normativa specifica del codice ministeriale.",
            ],
        }

    def _add(self, base: dict[str, Any], *, campi: list[dict[str, Any]] = None, allegati: list[dict[str, Any]] = None, struttura: list[dict[str, str]] = None, normativa: list[dict[str, str]] = None, avvertimenti: list[str] = None, presupposti: list[str] = None, tipo_atto: str = "") -> dict[str, Any]:
        out = deepcopy(base)
        if tipo_atto:
            out["tipo_atto"] = tipo_atto
        out["campi"] = _unique_by_json([*out["campi"], *(campi or [])])
        out["allegati"] = _unique_by_json([*out["allegati"], *(allegati or [])])
        out["struttura"] = _unique_by_json([*out["struttura"], *(struttura or [])])
        out["normativa"]["riferimenti_primari"] = _unique_by_json([*out["normativa"]["riferimenti_primari"], *(normativa or [])])
        out["avvertimenti"] = _unique_by_json([*out["avvertimenti"], *(avvertimenti or [])])
        out["presupposti"] = _unique_by_json([*out["presupposti"], *(presupposti or [])])
        return out

    def _profile_ingiunzione(self, base: dict[str, Any]) -> dict[str, Any]:
        return self._add(
            base,
            tipo_atto="ricorso_decreto_ingiuntivo",
            normativa=[{"fonte": "c.p.c.", "articolo": "633-642", "descrizione": "Procedimento di ingiunzione"}],
            campi=[
                {"id": "credito_importo", "label": "Importo credito", "type": "currency", "required": True},
                {"id": "titolo_credito", "label": "Titolo/prova scritta del credito", "type": "textarea", "required": True},
                {"id": "richiesta_provvisoria_esecuzione", "label": "Richiesta provvisoria esecuzione", "type": "boolean", "required": False},
            ],
            allegati=[{"id": "prova_scritta_credito", "label": "Prova scritta del credito", "required": True}],
            struttura=[{"sezione": "Prova_scritta", "contenuto": "Descrizione puntuale del titolo documentale"}],
            avvertimenti=["Verificare requisiti di prova scritta e liquidità/esigibilità del credito prima del deposito."],
        )

    def _profile_cautelare(self, base: dict[str, Any]) -> dict[str, Any]:
        return self._add(
            base,
            tipo_atto="ricorso_cautelare",
            normativa=[{"fonte": "c.p.c.", "articolo": "669-bis ss.", "descrizione": "Procedimento cautelare uniforme"}],
            campi=[
                {"id": "fumus_boni_iuris", "label": "Fumus boni iuris", "type": "textarea", "required": True},
                {"id": "periculum_in_mora", "label": "Periculum in mora", "type": "textarea", "required": True},
                {"id": "misura_richiesta", "label": "Misura cautelare richiesta", "type": "textarea", "required": True},
            ],
            allegati=[{"id": "documentazione_urgenza", "label": "Documentazione su urgenza/periculum", "required": True}],
            avvertimenti=["Motivare in modo separato fumus e periculum; valutare richiesta inaudita altera parte solo se realmente necessaria."],
        )

    def _profile_atp(self, base: dict[str, Any]) -> dict[str, Any]:
        return self._add(
            base,
            tipo_atto="ricorso_accertamento_tecnico_preventivo",
            normativa=[{"fonte": "c.p.c.", "articolo": "696 / 696-bis", "descrizione": "Accertamento tecnico preventivo e consulenza tecnica preventiva"}],
            campi=[
                {"id": "quesiti_ctu", "label": "Quesiti da sottoporre al CTU", "type": "textarea", "required": True},
                {"id": "urgenza_accertamento", "label": "Ragioni di urgenza o finalità conciliativa", "type": "textarea", "required": True},
            ],
            allegati=[{"id": "documenti_tecnici", "label": "Documentazione tecnica / sanitaria / fotografica", "required": True}],
            avvertimenti=["Verificare se il procedimento scelto è ATP ordinario ex art. 696 o CTU conciliativa ex art. 696-bis."],
        )

    def _profile_possessorio(self, base: dict[str, Any]) -> dict[str, Any]:
        return self._add(
            base,
            tipo_atto="ricorso_possessorio",
            normativa=[{"fonte": "c.p.c.", "articolo": "703", "descrizione": "Domande possessorie"}, {"fonte": "c.c.", "articolo": "1168-1170", "descrizione": "Reintegrazione e manutenzione nel possesso"}],
            campi=[
                {"id": "possesso_esercitato", "label": "Possesso esercitato", "type": "textarea", "required": True},
                {"id": "spoglio_o_turbativa", "label": "Spoglio/turbativa e data", "type": "textarea", "required": True},
            ],
            allegati=[{"id": "prove_possesso", "label": "Prove del possesso e dello spoglio/turbativa", "required": True}],
            avvertimenti=["Controllare il termine annuale e distinguere reintegrazione/manutenzione."],
        )

    def _profile_locazione(self, base: dict[str, Any]) -> dict[str, Any]:
        return self._add(
            base,
            tipo_atto="atto_locatizio_o_rilascio",
            normativa=[{"fonte": "c.p.c.", "articolo": "447-bis / 657 ss. / 608 ss.", "descrizione": "Riti locatizi, convalida o rilascio secondo fase"}],
            campi=[
                {"id": "immobile", "label": "Immobile", "type": "object_immobile", "required": True},
                {"id": "contratto_o_titolo", "label": "Contratto/titolo di occupazione", "type": "textarea", "required": True},
            ],
            allegati=[{"id": "contratto_o_titolo", "label": "Contratto/titolo e prova registrazione se dovuta", "required": True}],
            avvertimenti=["Verificare se il codice appartiene a fase di convalida, rito locatizio o esecuzione per rilascio."],
        )

    def _profile_lavoro(self, base: dict[str, Any]) -> dict[str, Any]:
        return self._add(
            base,
            tipo_atto="ricorso_lavoro",
            normativa=[{"fonte": "c.p.c.", "articolo": "414 ss.", "descrizione": "Rito del lavoro"}],
            campi=[
                {"id": "rapporto_lavoro", "label": "Rapporto di lavoro/previdenziale", "type": "textarea", "required": True},
                {"id": "conteggi", "label": "Conteggi e differenze richieste", "type": "table", "required": False},
            ],
            allegati=[{"id": "documenti_lavoro", "label": "Contratto, buste paga, comunicazioni e conteggi", "required": True}],
            avvertimenti=["Nel rito lavoro indicare mezzi di prova e documenti già nel ricorso/resistenza."],
        )

    def _profile_esecuzione(self, base: dict[str, Any]) -> dict[str, Any]:
        return self._add(
            base,
            tipo_atto="atto_esecutivo",
            normativa=[{"fonte": "c.p.c.", "articolo": "474 ss.", "descrizione": "Titolo esecutivo, precetto ed esecuzione"}],
            campi=[
                {"id": "titolo_esecutivo", "label": "Titolo esecutivo", "type": "string", "required": True},
                {"id": "precetto", "label": "Precetto / intimazione", "type": "string", "required": False},
            ],
            allegati=[{"id": "titolo_precetto", "label": "Titolo esecutivo e precetto/notifica se applicabile", "required": True}],
            avvertimenti=["Verificare efficacia esecutiva del titolo e regolarità delle notifiche prima dell'istanza/deposito."],
        )

    def _profile_famiglia(self, base: dict[str, Any]) -> dict[str, Any]:
        return self._add(
            base,
            tipo_atto="ricorso_famiglia",
            normativa=[{"fonte": "c.p.c.", "articolo": "473-bis ss.", "descrizione": "Procedimenti in materia di persone, minorenni e famiglie"}],
            campi=[
                {"id": "nucleo_familiare", "label": "Nucleo familiare e figli", "type": "textarea", "required": True},
                {"id": "documentazione_economica", "label": "Documentazione reddituale/patrimoniale", "type": "file_multi", "required": True},
            ],
            allegati=[{"id": "documenti_famiglia", "label": "Certificati, dichiarazioni reddituali e documentazione familiare", "required": True}],
            avvertimenti=["Verificare allegazioni economiche, minori coinvolti e obblighi documentali del rito famiglia."],
        )

    def _normalise_guidance_payload(self, payload: dict[str, Any], *, codice: str, coverage: GuidaPraticaCoverage, fascicolo: dict[str, Any]) -> dict[str, Any]:
        out = deepcopy(payload)
        out["codice"] = normalize_codice_materia(out.get("codice") or codice)
        out["denominazione"] = _text(out.get("denominazione"), f"Codice materia {codice}")
        out["coverage"] = coverage.to_payload()
        out["catalogo_xsd"] = self._official_catalog_index.get(codice) or self._catalog_index.get(codice, {})
        out["codice_deposito"] = self._deposit_code_payload(codice)
        out["macro_area"] = {
            "id": _text(out.get("_macro_area_id") or _as_dict(self._kb.get("macro_area")).get("codice")),
            "label": _text(out.get("_macro_area_denominazione") or _as_dict(self._kb.get("macro_area")).get("label") or out.get("categoria")),
            "registro": _text(out.get("_registro") or self._kb.get("registro")),
        }
        out["kb_version"] = _text(self._kb.get("version"))
        out["ultimo_aggiornamento"] = _text(self._kb.get("ultimo_aggiornamento") or self._kb.get("data_generazione"))
        if isinstance(out.get("normativa"), list):
            out["normativa"] = {"riferimenti_primari": deepcopy(out.get("normativa") or []), "riferimenti_secondari": []}
        elif not isinstance(out.get("normativa"), dict):
            out["normativa"] = {"riferimenti_primari": [], "riferimenti_secondari": []}
        else:
            normativa = out.setdefault("normativa", {})
            if not normativa.get("riferimenti_primari") and normativa.get("normativa_principale"):
                normativa["riferimenti_primari"] = deepcopy(_as_list(normativa.get("normativa_principale")))
            normativa.setdefault("riferimenti_primari", [])
            normativa.setdefault("riferimenti_secondari", [])
        out["fascicolo_context"] = {
            "id": _text(fascicolo.get("id")),
            "titolo": _text(fascicolo.get("title") or fascicolo.get("titolo")),
            "codice_oggetto_pst": _text(fascicolo.get("codiceOggettoPst") or fascicolo.get("codice_oggetto_pst")),
            "fonte_codice_oggetto": _text(fascicolo.get("fonteCodiceOggetto") or fascicolo.get("fonte_codice_oggetto")),
            "file_fonte_codice_oggetto": _text(fascicolo.get("fileFonteCodiceOggetto") or fascicolo.get("file_fonte_codice_oggetto")),
        }
        atto = out.setdefault("atto_principale", {})
        if not atto.get("denominazione"):
            atto["denominazione"] = _text(out.get("denominazione"), "Atto principale")
        # Nei KB caricati i campi possono chiamarsi campi_chiave, campi_specifici
        # o campi_obbligatori. Li unifichiamo senza perdere i campi ereditati.
        merged_fields: list[Any] = []
        for source_key in ("campi_chiave", "campi_obbligatori", "campi_obbligatori_specifici", "campi_specifici"):
            merged_fields.extend(deepcopy(_as_list(atto.get(source_key))))
        if merged_fields:
            atto["campi_obbligatori"] = _unique_by_json(merged_fields)
        atto.setdefault("campi_obbligatori", [])
        atto.setdefault("avvertimenti_obbligatori", [])
        if not atto.get("struttura_obbligatoria"):
            atto["struttura_obbligatoria"] = [
                {"sezione": "Intestazione", "contenuto": "Ufficio, registro e parti"},
                {"sezione": "Premesse", "contenuto": "Fatti e documenti rilevanti"},
                {"sezione": "Domande", "contenuto": "Richieste al giudice/cancelleria"},
                {"sezione": "Allegati", "contenuto": "Elenco numerato"},
            ]
        out.setdefault("allegati_obbligatori", [])
        out.setdefault("adempimenti_propedeutici", [])
        out.setdefault("avvertenze_redazionali", [])
        if not out["codice_deposito"]["depositabile"]:
            out["avvertenze_redazionali"] = _unique_by_json(
                [
                    *_as_list(out.get("avvertenze_redazionali")),
                    "Questa scheda è una guida pratica interna: usala per orientare il lavoro. Se devi depositare un atto, seleziona nella scheda fascicolo il codice ministeriale ufficiale corrispondente.",
                ]
            )
        # Molti codici del KB completo sono schede normative sintetiche.
        # Per renderle davvero operative nel fascicolo, integriamo campi/allegati/adempimenti
        # con un profilo prudenziale, senza sovrascrivere i dati curati già presenti.
        if not _as_list(atto.get("campi_obbligatori")) or not _as_list(out.get("allegati_obbligatori")) or not _as_list(out.get("adempimenti_propedeutici")):
            profile = self._profile_for(out.get("denominazione", ""), out.get("sottocategoria", ""), out.get("categoria", ""))
            if not _as_list(atto.get("campi_obbligatori")):
                atto["campi_obbligatori"] = deepcopy(profile.get("campi") or [])
            if not _text(atto.get("tipo_atto")):
                atto["tipo_atto"] = _text(profile.get("tipo_atto"), "atto_introduttivo_o_deposito_generico")
            if not _as_list(atto.get("avvertimenti_obbligatori")):
                atto["avvertimenti_obbligatori"] = deepcopy(profile.get("avvertimenti") or [])
            if not _as_list(out.get("allegati_obbligatori")):
                out["allegati_obbligatori"] = deepcopy(profile.get("allegati") or [])
            if not _as_list(out.get("adempimenti_propedeutici")):
                out["adempimenti_propedeutici"] = deepcopy(profile.get("adempimenti") or [])
            if not _as_list(out.get("adempimenti_fiscali_telematici")):
                out["adempimenti_fiscali_telematici"] = deepcopy(profile.get("fiscali") or [])
            if not _as_list(out.get("termini_processuali")):
                out["termini_processuali"] = deepcopy(profile.get("termini") or [])
            out["profilo_pratico_integrato"] = True
        out["quick_help"] = self._quick_help(out)
        return out

    def _deposit_code_payload(self, codice: str) -> dict[str, Any]:
        official = self._official_catalog_index.get(codice)
        if official:
            return {
                "codice": codice,
                "ufficiale": True,
                "depositabile": True,
                "fonte": _text(official.get("file_fonte") or official.get("fileFonte")),
                "messaggio": "Codice presente nel catalogo ufficiale PST/XSD caricato.",
            }
        return {
            "codice": "",
            "ufficiale": False,
            "depositabile": False,
            "fonte": "",
            "messaggio": "Guida pratica interna non presente nel catalogo PST/XSD ufficiale.",
        }

    def _quick_help(self, guidance: dict[str, Any]) -> dict[str, Any]:
        atto = _as_dict(guidance.get("atto_principale"))
        campi = _as_list(atto.get("campi_obbligatori"))
        allegati = _as_list(guidance.get("allegati_obbligatori"))
        warnings = _as_list(atto.get("avvertimenti_obbligatori"))
        adempimenti = _as_list(guidance.get("adempimenti_propedeutici"))
        return {
            "titolo": f"Come affrontare: {_text(guidance.get('denominazione'))}",
            "prima_cosa_da_fare": _text(_as_dict(adempimenti[0]).get("azione")) if adempimenti and isinstance(adempimenti[0], dict) else "Verificare competenza, rito e documenti fondativi.",
            "atto_da_redigere": _text(atto.get("denominazione") or guidance.get("denominazione")),
            "schema_xsd": _text(atto.get("schema_xsd_ministeriale") or _as_dict(guidance.get("catalogo_xsd")).get("file_fonte")),
            "totale_campi_obbligatori": len([item for item in campi if _as_dict(item).get("required") is not False]),
            "totale_allegati_obbligatori": len([item for item in allegati if _as_dict(item).get("required") is not False]),
            "totale_avvertimenti": len(warnings),
        }

    def get_checklist(self, codice_materia: Any, dati_pratica: dict[str, Any] | None = None) -> dict[str, Any]:
        dati = dati_pratica or {}
        guidance = self.get_guidance(codice_materia, fascicolo=_as_dict(dati.get("fascicolo")))
        atto = _as_dict(guidance.get("atto_principale"))
        fields = [_as_dict(item) for item in _as_list(atto.get("campi_obbligatori")) if isinstance(item, dict)]
        attachments = [_as_dict(item) for item in _as_list(guidance.get("allegati_obbligatori")) if isinstance(item, dict)]
        warnings = [_text(item) for item in _as_list(atto.get("avvertimenti_obbligatori")) if _text(item)]
        adempimenti = [_as_dict(item) for item in _as_list(guidance.get("adempimenti_propedeutici")) if isinstance(item, dict)]
        missing_fields = [field for field in fields if field.get("required") is not False and not self._field_present(dati, _text(field.get("id")))]
        missing_attachments = [item for item in attachments if item.get("required") is not False and not self._attachment_present(dati, _text(item.get("id")))]
        warning_status = [{"testo": warning, "presente": self._warning_present(dati, warning), "bloccante": True} for warning in warnings]
        missing_warnings = [item for item in warning_status if not item["presente"]]
        adempimenti_status = [{**item, "completato": self._adempimento_done(dati, item)} for item in adempimenti]
        total = len(fields) + len([a for a in attachments if a.get("required") is not False]) + len(warnings) + len([a for a in adempimenti if a.get("obbligatorio") is not False])
        missing_total = len(missing_fields) + len(missing_attachments) + len(missing_warnings) + len([a for a in adempimenti_status if a.get("obbligatorio") is not False and not a.get("completato")])
        completed = max(0, total - missing_total)
        depositabile = bool(_as_dict(guidance.get("codice_deposito")).get("depositabile"))
        return {
            "ok": True,
            "codice": guidance["codice"],
            "denominazione": guidance["denominazione"],
            "coverage": guidance["coverage"],
            "codice_deposito": guidance.get("codice_deposito", {}),
            "campi_mancanti": missing_fields,
            "allegati_mancanti": missing_attachments,
            "avvertimenti": warning_status,
            "avvertimenti_mancanti": missing_warnings,
            "adempimenti": adempimenti_status,
            "totale": total,
            "completati": completed,
            "percentuale_completamento": int(round((completed / total) * 100)) if total else 100,
            "pronto_per_generazione": missing_total == 0 and not guidance["coverage"].get("needs_reviewer", False) and depositabile,
            "requires_review": bool(guidance["coverage"].get("needs_reviewer")),
            "blockers": self._build_blockers(missing_fields, missing_attachments, missing_warnings, guidance),
        }

    def _field_present(self, dati: dict[str, Any], field_id: str) -> bool:
        if not field_id:
            return False
        for container_name in ("fields", "campi", "atto", "fascicolo", "dati"):
            container = dati.get(container_name)
            if isinstance(container, dict) and self._truthy(container.get(field_id)):
                return True
        return self._truthy(dati.get(field_id))

    def _attachment_present(self, dati: dict[str, Any], attachment_id: str) -> bool:
        if not attachment_id:
            return False
        for container_name in ("attachments", "allegati", "documenti"):
            container = dati.get(container_name)
            if isinstance(container, dict) and self._truthy(container.get(attachment_id)):
                return True
            if isinstance(container, list):
                for item in container:
                    if isinstance(item, dict) and _text(item.get("id") or item.get("tipo") or item.get("codice")) == attachment_id:
                        return True
                    if _text(item) == attachment_id:
                        return True
        return False

    def _warning_present(self, dati: dict[str, Any], warning: str) -> bool:
        text = " ".join(
            _text(value)
            for value in [dati.get("corpo_atto"), dati.get("testo_atto"), _as_dict(dati.get("atto")).get("corpo_atto")]
            if _text(value)
        ).casefold()
        if not text:
            return False
        tokens = [token for token in re.split(r"[^a-z0-9]+", warning.casefold()) if len(token) >= 3]
        key_tokens = [token for token in tokens if token in {"art", "663", "665", "660", "664", "55", "patrocinio", "grazia", "comparizione", "opposizione"}]
        if not key_tokens:
            key_tokens = tokens[:4]
        return all(token in text for token in key_tokens[:4])

    def _adempimento_done(self, dati: dict[str, Any], adempimento: dict[str, Any]) -> bool:
        step = _text(adempimento.get("step"))
        action = _text(adempimento.get("azione"))
        done = dati.get("adempimenti") or dati.get("tasks") or {}
        if isinstance(done, dict):
            return bool(done.get(step) or done.get(action) or done.get(action.casefold()))
        if isinstance(done, list):
            done_text = " ".join(_text(item) for item in done).casefold()
            return bool(action and action.casefold() in done_text)
        return bool(adempimento.get("obbligatorio") is False)

    @staticmethod
    def _truthy(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set, dict)):
            return bool(value)
        return bool(value)

    @staticmethod
    def _build_blockers(fields: list[dict[str, Any]], attachments: list[dict[str, Any]], warnings: list[dict[str, Any]], guidance: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if guidance.get("coverage", {}).get("needs_reviewer"):
            out.append({"type": "coverage_review", "message": "Guida generata: serve revisione normativa prima di usarla come guida completa.", "bloccante": False})
        if not _as_dict(guidance.get("codice_deposito")).get("depositabile"):
            out.append(
                {
                    "type": "codice_deposito_non_ufficiale",
                    "message": "Questa guida non corrisponde a un codice PST/XSD ufficiale: se devi depositare un atto, seleziona un codice ministeriale nella scheda fascicolo.",
                    "bloccante": True,
                }
            )
        out.extend({"type": "campo_mancante", "id": _text(item.get("id")), "message": _text(item.get("label")), "bloccante": True} for item in fields)
        out.extend({"type": "allegato_mancante", "id": _text(item.get("id")), "message": _text(item.get("label")), "bloccante": True} for item in attachments)
        out.extend({"type": "avvertimento_mancante", "message": _text(item.get("testo")), "bloccante": True} for item in warnings)
        return out
