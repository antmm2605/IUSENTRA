"""Importatore codici oggetto/materia dai pacchetti XSD/XLSX ufficiali PST."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from io import BytesIO
import json
import re
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET

XSD_NS = "{http://www.w3.org/2001/XMLSchema}"
CODE_RE = re.compile(r"^\d{3,8}$")
YEAR_RE = re.compile(r"^(19|20)\d{2}$")
CONTEXT_RE = re.compile(r"(oggett|materia|codice.?oggetto|tipo.?oggetto|sici|sicid|sigp|cassaz|unep|rito|registro)", re.I)
DESC_RE = re.compile(r"(procediment|ricors|citazion|sfratt|ingiunz|opposizion|esecuz|deposit|istanza|cautelar|sequest|famiglia|lavor|previd|possessor|falliment|volontaria|cassaz)", re.I)


@dataclass(frozen=True)
class OfficialPstDownload:
    key: str
    label: str
    url: str
    portal_page: str
    published_label: str
    category: str


DEFAULT_OFFICIAL_DOWNLOADS: tuple[OfficialPstDownload, ...] = (
    OfficialPstDownload("sici", "Nuovi XSD SICI - 26/01/2026", "https://pst.giustizia.it/PST/resources/cms/documents/XSD_SICI_20260116.zip", "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3277", "Riferimento notizia 28/01/2026", "XSD SICI"),
    OfficialPstDownload("sigp", "Nuovi XSD SIGP - 29/11/2024", "https://pst.giustizia.it/PST/resources/cms/documents/XSD_SIGP_20241128.zip", "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3199", "Riferimento news 29/11/2024", "XSD Giudici di pace / SIGP"),
    OfficialPstDownload("cassazione", "XSD Cassazione 27/02/2026", "https://pst.giustizia.it/PST/resources/cms/documents/XSD_Cassazione_20260227.zip", "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4671", "Ultimo aggiornamento 02/03/2026", "XSD Corte Suprema di Cassazione"),
    OfficialPstDownload("reginde", "Nuovi XSD REGINDE - 15/10/2025", "https://pst.giustizia.it/PST/resources/cms/documents/XSD_REGINDE_20251010.zip", "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4437", "Riferimento news 15/10/2025", "XSD REGINDE"),
    OfficialPstDownload("unep", "XSD UNEP - 06/11/2024", "https://pst.giustizia.it/PST/resources/cms/documents/XSD_PLO118_FASE2_per_SW_House_20241106.zip", "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3136", "Riferimento news 18/11/2024", "XSD UNEP"),
)


@dataclass
class CatalogRecord:
    codice: str
    descrizione: str
    area: str = ""
    codicePadre: str = ""
    descrizionePadre: str = ""
    registri: list[str] | None = None
    fileFonte: str = ""
    schemaXsd: str = ""
    fontePacchetto: str = ""
    sourceKind: str = "xsd_enum"
    confidence: str = "media"
    context: str = ""

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["registri"] = self.registri or []
        return data


def text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalizza_codice(value: Any) -> str:
    raw = re.sub(r"\D+", "", str(value or ""))
    return raw.zfill(6) if len(raw) == 5 else raw


def looks_like_code(value: Any) -> bool:
    code = normalizza_codice(value)
    return bool(CODE_RE.match(code)) and not (len(code) == 4 and YEAR_RE.match(code))


def node_text(node: ET.Element | None) -> str:
    return text(" ".join(p for p in node.itertext() if p)) if node is not None else ""


def first_doc(node: ET.Element) -> str:
    for child in node.iter():
        if child.tag.endswith("documentation"):
            value = node_text(child)
            if value:
                return value
    return ""


def confidence(simple_name: str, desc: str, file_name: str) -> str:
    ctx = f"{simple_name} {desc} {file_name}"
    if CONTEXT_RE.search(ctx) and DESC_RE.search(ctx):
        return "alta"
    if CONTEXT_RE.search(ctx) or DESC_RE.search(ctx):
        return "media"
    return "bassa"


def parse_xsd_bytes(data: bytes, *, file_name: str, package_key: str, package_label: str) -> list[CatalogRecord]:
    records: list[CatalogRecord] = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        root = None
    if root is not None:
        for simple in root.iter(f"{XSD_NS}simpleType"):
            simple_name = text(simple.attrib.get("name"))
            simple_doc = first_doc(simple)
            restriction = simple.find(f"{XSD_NS}restriction")
            if restriction is None:
                continue
            for enum in restriction.findall(f"{XSD_NS}enumeration"):
                code = normalizza_codice(enum.attrib.get("value"))
                if not looks_like_code(code):
                    continue
                desc = first_doc(enum) or simple_doc or f"Codice {code}"
                conf = confidence(simple_name, desc, file_name)
                if conf == "bassa" and not DESC_RE.search(desc):
                    continue
                records.append(CatalogRecord(code, desc, package_label, registri=[package_key.upper()], fileFonte=Path(file_name).name, schemaXsd=Path(file_name).name, fontePacchetto=package_key, confidence=conf, context=simple_name))
    raw = data.decode("utf-8", errors="ignore")
    enum_re = re.compile(r"<[^>]*enumeration[^>]*(?:value|valore)=[\"'](?P<code>\d{3,8})[\"'][^>]*>(?P<body>.*?)</[^>]*enumeration>", re.I | re.S)
    doc_re = re.compile(r"<[^>]*documentation[^>]*>(?P<doc>.*?)</[^>]*documentation>", re.I | re.S)
    for match in enum_re.finditer(raw):
        code = normalizza_codice(match.group("code"))
        if not looks_like_code(code):
            continue
        doc_match = doc_re.search(match.group("body"))
        desc = text(re.sub(r"<[^>]+>", " ", doc_match.group("doc") if doc_match else "")) or f"Codice {code}"
        conf = confidence("", desc, file_name)
        if conf == "bassa" and not DESC_RE.search(desc):
            continue
        records.append(CatalogRecord(code, desc, package_label, registri=[package_key.upper()], fileFonte=Path(file_name).name, schemaXsd=Path(file_name).name, fontePacchetto=package_key, sourceKind="xsd_enum_regex", confidence=conf))
    return dedupe_records(records)


def find_header(headers: dict[str, int], candidates: Iterable[str]) -> int | None:
    for header, index in headers.items():
        clean = header.replace("_", " ").replace("-", " ")
        if any(candidate in clean for candidate in candidates):
            return index
    return None


def parse_xlsx_bytes(data: bytes, *, file_name: str, package_key: str, package_label: str) -> list[CatalogRecord]:
    try:
        import openpyxl  # type: ignore
    except Exception:
        return []
    wb = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)
    out: list[CatalogRecord] = []
    for sheet in wb.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue
        headers: dict[str, int] = {}
        start = 0
        for idx, row in enumerate(rows[:10]):
            vals = {text(cell).casefold(): col for col, cell in enumerate(row) if text(cell)}
            if any("codice" in key for key in vals):
                headers, start = vals, idx
                break
        code_col = find_header(headers, ("codice oggetto", "codice materia", "codice"))
        desc_col = find_header(headers, ("descrizione", "oggetto", "materia"))
        parent_col = find_header(headers, ("codice padre", "codicepadre", "parent", "padre"))
        if code_col is None:
            continue
        for row in rows[start + 1:]:
            code = normalizza_codice(row[code_col] if code_col < len(row) else "")
            if not looks_like_code(code):
                continue
            desc = text(row[desc_col] if desc_col is not None and desc_col < len(row) else "") or f"Codice {code}"
            parent = normalizza_codice(row[parent_col] if parent_col is not None and parent_col < len(row) else "")
            out.append(CatalogRecord(code, desc, text(sheet.title) or package_label, codicePadre=parent, registri=[package_key.upper()], fileFonte=Path(file_name).name, schemaXsd=Path(file_name).name, fontePacchetto=package_key, sourceKind="xlsx", confidence="alta" if desc else "media", context=sheet.title))
    return dedupe_records(out)


def records_from_zip_bytes(data: bytes, *, archive_name: str, package_key: str, package_label: str) -> list[CatalogRecord]:
    out: list[CatalogRecord] = []
    with zipfile.ZipFile(BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            payload = zf.read(info)
            suffix = Path(name).suffix.casefold()
            if suffix == ".zip":
                out.extend(records_from_zip_bytes(payload, archive_name=name, package_key=package_key, package_label=package_label))
            elif suffix == ".xsd":
                out.extend(parse_xsd_bytes(payload, file_name=name, package_key=package_key, package_label=package_label))
            elif suffix == ".xlsx":
                out.extend(parse_xlsx_bytes(payload, file_name=name, package_key=package_key, package_label=package_label))
    return dedupe_records(out)


def records_from_path(path: str | Path, *, package_key: str = "locale", package_label: str = "Pacchetto locale") -> list[CatalogRecord]:
    source = Path(path)
    if source.is_dir():
        out: list[CatalogRecord] = []
        for item in source.rglob("*"):
            if item.suffix.casefold() in {".zip", ".xsd", ".xlsx"}:
                out.extend(records_from_path(item, package_key=package_key, package_label=package_label))
        return dedupe_records(out)
    data = source.read_bytes()
    if source.suffix.casefold() == ".zip":
        return records_from_zip_bytes(data, archive_name=source.name, package_key=package_key, package_label=package_label)
    if source.suffix.casefold() == ".xsd":
        return parse_xsd_bytes(data, file_name=source.name, package_key=package_key, package_label=package_label)
    if source.suffix.casefold() == ".xlsx":
        return parse_xlsx_bytes(data, file_name=source.name, package_key=package_key, package_label=package_label)
    return []


def download_official_package(download: OfficialPstDownload, cache_dir: str | Path) -> Path:
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / Path(download.url).name
    if target.exists() and target.stat().st_size > 0:
        return target
    req = urllib.request.Request(download.url, headers={"User-Agent": "IUSENTRA catalog updater"})
    with urllib.request.urlopen(req, timeout=60) as response:  # nosec B310
        target.write_bytes(response.read())
    return target


def download_and_extract_records(cache_dir: str | Path, downloads: Iterable[OfficialPstDownload] = DEFAULT_OFFICIAL_DOWNLOADS) -> list[CatalogRecord]:
    out: list[CatalogRecord] = []
    for item in downloads:
        archive = download_official_package(item, cache_dir)
        out.extend(records_from_path(archive, package_key=item.key, package_label=item.category))
    return dedupe_records(out)


def load_kb_records(path: str | Path) -> list[CatalogRecord]:
    p = Path(path)
    if not p.exists():
        return []
    payload = json.loads(p.read_text(encoding="utf-8"))
    out: list[CatalogRecord] = []
    for item in payload.get("codici_materia", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        code = normalizza_codice(item.get("codice"))
        if not looks_like_code(code):
            continue
        atto = item.get("atto_principale") if isinstance(item.get("atto_principale"), dict) else {}
        out.append(CatalogRecord(code, text(item.get("denominazione")) or f"Codice {code}", text(item.get("categoria")), codicePadre=normalizza_codice(item.get("eredita_da")), registri=[text(item.get("registro_sicid"))] if text(item.get("registro_sicid")) else [], fileFonte=text(atto.get("schema_xsd_ministeriale")) or "legal_knowledge_base.json", schemaXsd=text(atto.get("schema_xsd_ministeriale")), fontePacchetto="legal_knowledge_base", sourceKind="kb_curated", confidence="alta"))
    return dedupe_records(out)


def load_seed_catalog_records(path: str | Path) -> list[CatalogRecord]:
    p = Path(path)
    if not p.exists():
        return []
    payload = json.loads(p.read_text(encoding="utf-8"))
    fonte = payload.get("fonte", {}) if isinstance(payload, dict) else {}
    out: list[CatalogRecord] = []
    for area in payload.get("areas", []) if isinstance(payload, dict) else []:
        area_label = text(area.get("label")) if isinstance(area, dict) else ""
        for item in area.get("items", []) if isinstance(area.get("items"), list) else []:
            parent_code, parent_label = normalizza_codice(item.get("codice")), text(item.get("label"))
            children = item.get("children") if isinstance(item.get("children"), list) else []
            if children and looks_like_code(parent_code):
                out.append(CatalogRecord(parent_code, parent_label or f"Codice {parent_code}", area_label, fileFonte=text(fonte.get("fileFontePrevalente")) or "pratiche_collegate_catalog.json", fontePacchetto="seed_catalog", sourceKind="seed_parent", confidence="media"))
            targets = children or [item]
            for child in targets:
                code = normalizza_codice(child.get("codice"))
                if not looks_like_code(code) or code == parent_code:
                    continue
                out.append(CatalogRecord(code, text(child.get("label")) or f"Codice {code}", area_label, codicePadre=parent_code if children else "", descrizionePadre=parent_label if children else "", fileFonte=text(fonte.get("fileFontePrevalente")) or "pratiche_collegate_catalog.json", fontePacchetto="seed_catalog", sourceKind="seed_child" if children else "seed_item", confidence="media"))
    return dedupe_records(out)


def build_catalog_payload(records: Iterable[CatalogRecord], *, source_label: str, official_downloads: Iterable[OfficialPstDownload] = DEFAULT_OFFICIAL_DOWNLOADS) -> dict[str, Any]:
    recs = dedupe_records(records)
    index = {r.codice: r for r in recs}
    for r in recs:
        if not r.codicePadre and len(r.codice) == 6 and r.codice[:3] in index:
            r.codicePadre = r.codice[:3]
            r.descrizionePadre = index[r.codicePadre].descrizione
        elif r.codicePadre and not r.descrizionePadre and r.codicePadre in index:
            r.descrizionePadre = index[r.codicePadre].descrizione
    return {"$schema": "iusentra/codici-oggetto-pst/v1", "versione": datetime.now(UTC).strftime("%Y-%m-%d.import"), "fonte": {"tipo": "PST_XSD", "nome": source_label, "url": "https://pst.giustizia.it/PST/it/download.page", "downloadUfficiali": [asdict(d) for d in official_downloads], "generatoIl": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "note": "Catalogo normalizzato da XSD/XLSX PST; i record non curati richiedono review per guida normativa completa."}, "records": [r.to_json() for r in sorted(recs, key=lambda x: (x.codice, x.descrizione.casefold()))]}


def build_catalog_from_sources(*, source_paths: Iterable[str | Path] = (), download: bool = False, cache_dir: str | Path = ".cache/pst_xsd", kb_path: str | Path | None = None, seed_catalog_path: str | Path | None = None) -> dict[str, Any]:
    records: list[CatalogRecord] = []
    for source in source_paths:
        records.extend(records_from_path(source))
    if download:
        records.extend(download_and_extract_records(cache_dir))
    if seed_catalog_path:
        records.extend(load_seed_catalog_records(seed_catalog_path))
    if kb_path:
        records.extend(load_kb_records(kb_path))
    return build_catalog_payload(records, source_label="PST Giustizia - File ufficiali PCT/XSD")


def write_catalog(payload: dict[str, Any], output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def dedupe_records(records: Iterable[CatalogRecord]) -> list[CatalogRecord]:
    merged: dict[str, CatalogRecord] = {}
    for rec in records:
        rec.codice = normalizza_codice(rec.codice)
        if not looks_like_code(rec.codice):
            continue
        old = merged.get(rec.codice)
        merged[rec.codice] = rec if old is None else merge_record(old, rec)
    return list(merged.values())


def merge_record(left: CatalogRecord, right: CatalogRecord) -> CatalogRecord:
    score = {"alta": 3, "media": 2, "bassa": 1}
    bonus = {"kb_curated": 5, "xlsx": 4, "seed_child": 3, "seed_item": 3, "seed_parent": 2, "xsd_enum": 2, "xsd_enum_regex": 1}
    lscore = score.get(left.confidence, 0) + bonus.get(left.sourceKind, 0)
    rscore = score.get(right.confidence, 0) + bonus.get(right.sourceKind, 0)
    primary, secondary = (right, left) if rscore > lscore else (left, right)
    registri = sorted({*(left.registri or []), *(right.registri or [])})
    sources = " | ".join(p for p in [text(left.fontePacchetto), text(right.fontePacchetto)] if p)
    return CatalogRecord(primary.codice, primary.descrizione or secondary.descrizione, primary.area or secondary.area, primary.codicePadre or secondary.codicePadre, primary.descrizionePadre or secondary.descrizionePadre, registri, primary.fileFonte or secondary.fileFonte, primary.schemaXsd or secondary.schemaXsd, sources or primary.fontePacchetto, primary.sourceKind, primary.confidence, primary.context or secondary.context)


__all__ = ["CatalogRecord", "DEFAULT_OFFICIAL_DOWNLOADS", "OfficialPstDownload", "build_catalog_from_sources", "build_catalog_payload", "download_and_extract_records", "load_kb_records", "load_seed_catalog_records", "normalizza_codice", "parse_xsd_bytes", "parse_xlsx_bytes", "records_from_path", "records_from_zip_bytes", "write_catalog"]
