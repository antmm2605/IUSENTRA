from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "react-migration"
TEMP = Path(os.environ["TEMP"])

QUICK_ROOT = Path("C:/QuickOrganizer")
CATALOG_SRC = TEMP / "quickorganizer_deposito_schemi.json"
OBJECT_SRC = TEMP / "quickorganizer_oggetti_pratica.json"
DECOMP = TEMP / "quickorganizer_decompiled_full"

FORM = DECOMP / "FormSentMailBee.cs"
PCT = DECOMP / "QuickOrganizer" / "PCT.cs"
QUAL = DECOMP / "QuickOrganizer" / "QualifiedCertificate.cs"
BROWSER = DECOMP / "QuickOrganizer" / "BrowserForm.cs"
WIZARD = DECOMP / "QuickOrganizer" / "WizardImportaPraticheDaPolisWeb.cs"
COMMON = DECOMP / "QuickOrganizer" / "Common.cs"
FORM_MAIN = DECOMP / "QuickOrganizer" / "FormMain.cs"
FORM_ALLEGATO = DECOMP / "QuickOrganizer" / "FormQualeAllegato.cs"

QUICK_CERT_DIR = QUICK_ROOT / "Certificati"
QUICK_UFFICI_XML = QUICK_ROOT / "ListaUfficiGiudiziari.xml"
QUICK_QC_UFFICI_XML = QUICK_ROOT / "QC_Uffici.xml"
QUICK_MDB = QUICK_ROOT / "QuickOrganizer.mdb"
TEMPLATE_MDB = DECOMP / "QuickOrganizer.Databases.QuickOrganizer.mdb"
QUICK_CSPROJ = DECOMP / "QuickOrganizer.csproj"

IUS_CERT_DIR = ROOT / "data" / "pst" / "certificati_cifratura"
IUS_CERT_AUDIT = IUS_CERT_DIR / "audit_certificati_cifratura_pst.json"
IUS_OBJECT_CATALOG = ROOT / "pct" / "data" / "cataloghi" / "codici_oggetto_pst.json"
IUS_DEPOSIT_CATALOG = ROOT / "pct" / "data" / "cataloghi" / "quickorganizer_depositi_studio_telematico.json"
IUS_UFFICI = ROOT / "pct" / "data" / "uffici_ministero.json"
IUS_UFFICI_EXTRA = ROOT / "pct" / "data" / "uffici_ministero_extra.json"

GENERATED_AT = datetime.now(ZoneInfo("Europe/Rome")).strftime("%d/%m/%Y %H:%M (Europe/Rome)")

OFFICIAL_SOURCES = [
    {
        "name": "PST - Specifiche Tecniche ex art. 34 DM 44/2011",
        "url": "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3429",
        "note": "Provvedimento DGSIA 7 agosto 2024, efficace dal 30 settembre 2024, con rettifiche pubblicate dal PST.",
    },
    {
        "name": "Normattiva - Decreto 21 febbraio 2011, n. 44",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=011G0087",
        "note": "Regole tecniche per processo civile e penale telematico; art. 34 come fonte delle specifiche tecniche.",
    },
    {
        "name": "PST - XSD ufficiali Processo Civile Telematico",
        "url": "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC1579",
        "note": "Pagina storica XSD ufficiali PCT; IUSENTRA usa anche il catalogo PST/XSD più recente già presente nel repository.",
    },
    {
        "name": "PST - comunicazione software house aggiornamento XSD SICID",
        "url": "https://pst.giustizia.it/PST/page/it/processo_civile_telematico__comunicazione_alle_software_house_aggiornamento_specifiche_tecniche_deposito_atti_sicid?contentId=NWS4594",
        "note": "News PST del 26/01/2026 sugli XSD SICID anticipati alle software house.",
    },
]

SECTOR_FILES = {
    "Contenzioso civile, Lavoro, Minorenni e Volontaria giurisdizione": "quickorganizer-catalogo-contenzioso-sicid.md",
    "Processo esecutivo": "quickorganizer-catalogo-esecuzioni-siecic.md",
    "Procedimenti concorsuali": "quickorganizer-catalogo-concorsuali-siecic.md",
    "Corte di Cassazione (civile)": "quickorganizer-catalogo-cassazione.md",
    "Giudice di Pace": "quickorganizer-catalogo-gdp-sigp.md",
    "UNEP - Ufficio Notificazioni, Esecuzioni e Protesti": "quickorganizer-catalogo-unep.md",
}

KEYWORDS = [
    "processotelematico",
    "CatalogoServizi",
    "getCertificato",
    "DatiAtto",
    "Atto.enc",
    "IndiceBusta",
    "IndiceDocumenti",
    "QualifiedCertificate",
    "MailBee",
    "SignLib",
    "PolisWeb",
    "WebView2",
    "PortaleNotifiche",
    "ReGIndE",
    "PAVVP",
    "PEC",
    "Notificazione",
    "L. 53",
    "CAdES",
    "PAdES",
    "pkcs",
    "AES256",
    "2.16.840.1.101.3.4.1.42",
    "pin",
]


def clean(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value
    for _ in range(3):
        if not any(marker in text for marker in ("\u00c3", "\u00c2", "\u00e2", "\ufffd")):
            break
        try:
            fixed = text.encode("latin-1").decode("utf-8")
        except UnicodeError:
            fixed = text
        replacements = {
            "\u00e2\u0080\u0099": "'",
            "\u00e2\u20ac\u2122": "'",
            "\u00e2\u0080\u0098": "'",
            "\u00e2\u20ac\u02dc": "'",
            "\u00e2\u0080\u009c": '"',
            "\u00e2\u20ac\u0153": '"',
            "\u00e2\u0080\u009d": '"',
            "\u00e2\u20ac\ufffd": '"',
            "\u00e2\u0080\u0093": "-",
            "\u00e2\u20ac\u201c": "-",
            "\u00e2\u0080\u0094": "-",
            "\u00e2\u20ac\u201d": "-",
            "\u00e2\u0080\u00a6": "...",
            "\u00e2\u0082\u00ac": "euro",
            "\ufffd": "?",
        }
        for bad, good in replacements.items():
            fixed = fixed.replace(bad, good)
        if fixed == text:
            break
        text = fixed
    return text


def scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {clean(k): scrub(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    return clean(obj)


def read_text(path: Path) -> str:
    try:
        return clean(path.read_text(encoding="utf-8", errors="replace"))
    except FileNotFoundError:
        return ""


def read_json(path: Path, default: Any) -> Any:
    try:
        return scrub(json.loads(path.read_text(encoding="utf-8-sig")))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_utf8(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = clean(content).rstrip() + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(scrub(data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def md_table(rows: list[tuple[Any, ...]], headers: list[str]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        cells = []
        for cell in row:
            cells.append(str(clean(str(cell))).replace("|", "\\|").replace("\n", " "))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def slug_filename(value: str) -> str:
    text = normalize_label(value)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "non-classificato"


def compact_join(values: list[Any], limit: int = 6) -> str:
    cleaned = [clean(str(value)).strip() for value in values if clean(str(value)).strip()]
    if not cleaned:
        return ""
    head = cleaned[:limit]
    suffix = f" (+{len(cleaned) - limit})" if len(cleaned) > limit else ""
    return ", ".join(head) + suffix


def sha256_file(path: Path, max_bytes: int | None = None) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        remaining = max_bytes
        while True:
            if remaining is None:
                chunk = fh.read(1024 * 1024)
            elif remaining <= 0:
                break
            else:
                chunk = fh.read(min(1024 * 1024, remaining))
                remaining -= len(chunk)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def split_prefix(key: str) -> str:
    return key.split("::", 1)[0] + "::" if "::" in key else ""


def infer_channel(prefix: str, macro: str) -> str:
    if "UNEP" in prefix or "UNEP" in macro:
        return "UNEP"
    if "CASSAZIONE" in prefix or "Cassazione" in macro:
        return "Cassazione civile"
    if "SIGP" in prefix or "Giudice di Pace" in macro:
        return "SIGP / Giudice di Pace"
    if "CONCORSUALI_SIECIC" in prefix or "concorsuali" in macro.lower():
        return "SIECIC concorsuali"
    if "ESECUZIONI_SIECIC" in prefix or "esecutivo" in macro.lower():
        return "SIECIC esecuzioni"
    if "SICID" in prefix:
        return "SICID"
    return "Da classificare"


def normalize_label(value: str) -> str:
    text = re.sub(r"^[A-Z]?\d{3,8}\s*[-.]\s*", "", str(clean(value or "")).strip())
    text = text.lower()
    trans = str.maketrans("àèéìòù", "aeeiou")
    text = text.translate(trans)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def extract_code(value: str) -> str:
    match = re.match(r"^\s*([A-Z]?\d{3,11})", str(value or ""))
    return match.group(1) if match else ""


def cert_code_from_name(name: str) -> str:
    match = re.match(r"^(\d{7,11})", str(name or ""))
    return match.group(1) if match else ""


def load_catalog() -> list[dict[str, Any]]:
    catalog = read_json(CATALOG_SRC, [])
    for item in catalog:
        item["prefix"] = split_prefix(item.get("key", ""))
        item["channel"] = infer_channel(item["prefix"], item.get("macro", ""))
    return catalog


def extract_schema_manifest() -> tuple[list[dict[str, Any]], Counter, list[dict[str, Any]]]:
    namespace_groups: dict[str, dict[str, Any]] = {}
    xml_namespace_counter: Counter = Counter()
    root_classes: list[dict[str, Any]] = []
    ns_re = re.compile(r'Namespace\s*=\s*"([^"]+)"')
    class_re = re.compile(r"\bpublic\s+(?:partial\s+)?(?:class|enum|struct)\s+([A-Za-z_][A-Za-z0-9_]*)")
    namespace_re = re.compile(r"\bnamespace\s+([A-Za-z_][A-Za-z0-9_\.]*)")
    xmlroot_re = re.compile(r"\[XmlRoot\((.*?)\)\]", re.S)
    for path in DECOMP.rglob("*.cs"):
        rel_path = path.relative_to(DECOMP)
        folder = rel_path.parts[0]
        text = read_text(path)
        if "Xml" not in text and folder in {"QuickOrganizer", "QuickWord", "Properties"}:
            continue
        ns_match = namespace_re.search(text)
        code_ns = ns_match.group(1) if ns_match else folder
        cls_match = class_re.search(text)
        cls_name = cls_match.group(1) if cls_match else path.stem
        group = namespace_groups.setdefault(
            code_ns,
            {
                "code_namespace": code_ns,
                "folder": folder,
                "file_count": 0,
                "class_count": 0,
                "xml_namespaces": set(),
                "root_classes": [],
                "sample_classes": [],
            },
        )
        group["file_count"] += 1
        group["class_count"] += 1 if cls_match else 0
        if len(group["sample_classes"]) < 12:
            group["sample_classes"].append(cls_name)
        for xml_ns in sorted(set(ns_re.findall(text))):
            group["xml_namespaces"].add(xml_ns)
            xml_namespace_counter[xml_ns] += 1
        if xmlroot_re.search(text):
            entry = {
                "namespace": code_ns,
                "class": cls_name,
                "file": str(rel_path).replace("\\", "/"),
            }
            group["root_classes"].append(entry)
            root_classes.append(entry)
    manifest: list[dict[str, Any]] = []
    for group in sorted(namespace_groups.values(), key=lambda item: item["code_namespace"]):
        manifest.append(
            {
                "code_namespace": group["code_namespace"],
                "folder": group["folder"],
                "file_count": group["file_count"],
                "class_count": group["class_count"],
                "xml_namespaces": sorted(group["xml_namespaces"]),
                "root_classes": group["root_classes"],
                "sample_classes": group["sample_classes"],
            }
        )
    return manifest, xml_namespace_counter, root_classes


def _switch_datiatto_text(form_text: str) -> str:
    method_start = form_text.find("private void ElencoXSD")
    switch_start = form_text.find("switch (AttoDaInviareKey)", method_start if method_start >= 0 else 0)
    if switch_start < 0:
        return ""
    line_start = form_text.rfind("\n", 0, switch_start) + 1
    switch_indent = form_text[line_start:switch_start]
    closing = re.search(
        rf"^{re.escape(switch_indent)}\}}\s*$",
        form_text[switch_start:],
        re.M,
    )
    if not closing:
        return ""
    switch_end = switch_start + closing.end()
    return form_text[switch_start:switch_end]


def _outer_case_groups(switch_text: str) -> list[tuple[list[tuple[str, int]], str]]:
    """Raggruppa i case per livello, preservando gli switch annidati di dispatch."""

    all_matches = list(
        re.finditer(r'^(?P<indent>[ \t]*)case\s+"(?P<key>[^"]+)"\s*:', switch_text, re.M)
    )
    if not all_matches:
        return []
    outer_indent = all_matches[0].group("indent")
    grouped_by_position: list[tuple[int, int, list[tuple[str, int]], str]] = []
    for indent in dict.fromkeys(match.group("indent") for match in all_matches):
        matches = [match for match in all_matches if match.group("indent") == indent]
        index = 0
        while index < len(matches):
            group_matches = [matches[index]]
            last = index
            while last + 1 < len(matches):
                between = switch_text[matches[last].end() : matches[last + 1].start()]
                if between.strip():
                    break
                last += 1
                group_matches.append(matches[last])
            body_start = group_matches[-1].end()
            body_end = matches[last + 1].start() if last + 1 < len(matches) else len(switch_text)
            body = switch_text[body_start:body_end]
            if len(indent) > len(outer_indent):
                nested_break = re.search(
                    rf"^{re.escape(indent + chr(9))}break;\s*$",
                    body,
                    re.M,
                )
                if nested_break:
                    body = body[: nested_break.end()]
            keys = [
                (clean(match.group("key")), switch_text[: match.start()].count("\n") + 1)
                for match in group_matches
            ]
            grouped_by_position.append(
                (group_matches[0].start(), len(indent), keys, body)
            )
            index = last + 1
    grouped_by_position.sort(key=lambda item: (item[0], item[1]))
    return [(keys, body) for _, _, keys, body in grouped_by_position]


def _compact_strings(values: list[str], limit: int = 80) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _assignments_in_block(body: str) -> list[dict[str, str]]:
    assignments: list[dict[str, str]] = []
    assignment_re = re.compile(
        r"(?P<target>\b(?:needProcura|needValoreControversia|needContributoUnificato|needNotaIscrizioneRuolo|"
        r"SingleSelect|VisualizzaAnagraficaProcedimento|VisualizzaIntroduttiviCassazione|"
        r"VisualizzaSanzioniGDP|VisualizzaGrigliaTerzi|isProcessoEsecutivo|"
        r"isEredit[\u00e0\u00c3 ]*Successioni|TipoOrganoRequired|"
        r"[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+))\s*=\s*(?P<value>[^;\n]+);"
    )
    for match in assignment_re.finditer(body):
        target = clean(match.group("target"))
        value = clean(match.group("value").strip())
        if len(value) > 180:
            value = value[:177] + "..."
        assignments.append({"target": target, "value": value})
    return assignments


def _controls_in_block(body: str) -> list[dict[str, str]]:
    controls: dict[str, dict[str, str]] = {}
    for match in re.finditer(
        r"\b(?P<control>[A-Za-z_][A-Za-z0-9_À-ÿ]*)\."
        r"(?P<prop>Enabled|Visible|Text|Tag|SelectedIndex)\s*=\s*(?P<value>[^;\n]+);",
        body,
    ):
        control = clean(match.group("control"))
        prop = clean(match.group("prop"))
        value = clean(match.group("value").strip())
        if len(value) > 160:
            value = value[:157] + "..."
        controls.setdefault(control, {"control": control})[prop] = value
    return list(controls.values())


def _fixed_object_codes(body: str) -> list[dict[str, str]]:
    codes: list[dict[str, str]] = []
    text_matches = list(re.finditer(r'cboOggettoPratica\.Text\s*=\s*"([^"]+)"\s*;', body))
    tag_matches = list(re.finditer(r'cboOggettoPratica\.Tag\s*=\s*"([^"]+)"\s*;', body))
    for idx, text_match in enumerate(text_matches):
        tag = tag_matches[idx].group(1) if idx < len(tag_matches) else extract_code(text_match.group(1))
        codes.append({"code": clean(tag), "label": clean(text_match.group(1))})
    return codes


def _flags_in_block(body: str) -> dict[str, bool]:
    flags: dict[str, bool] = {}
    flag_names = (
        "needProcura",
        "needValoreControversia",
        "needContributoUnificato",
        "needNotaIscrizioneRuolo",
        "SingleSelect",
        "VisualizzaAnagraficaProcedimento",
        "VisualizzaIntroduttiviCassazione",
        "VisualizzaSanzioniGDP",
        "VisualizzaGrigliaTerzi",
        "isProcessoEsecutivo",
        "isEreditàSuccessioni",
        "isEredit\u00c3 Successioni",
        "TipoOrganoRequired",
    )
    pattern = r"\b(" + "|".join(re.escape(name) for name in flag_names) + r")\s*=\s*(true|false)\s*;"
    for match in re.finditer(pattern, body):
        flags[match.group(1)] = match.group(2) == "true"
    return flags


def _combo_sources_in_block(body: str) -> list[str]:
    sources: list[str] = []
    for match in re.finditer(r"(PopulateComboIstanze(?:Enum)?|PopulateComboRuolo|PopulateComboRito)\s*\(([^;\n]+)\);", body):
        sources.append(clean(f"{match.group(1)}({match.group(2).strip()})"))
    return _compact_strings(sources, limit=40)


def _method_required_data(body: str) -> list[str]:
    checks = [
        ("IndiceBusta", "IndiceBusta"),
        ("AttoPrincipale.id", "AttoPrincipale.id"),
        ("_AttoPrincipale.ID", "AttoPrincipale.id"),
        ("Create_ListAllegati", "Allegati in IndiceBusta"),
        ("RefID_Deposito", "RefId deposito multiplo"),
        ("groupedFiles.Count", "Deposito multiplo"),
        ("CaricaDati_Introduttivi_AnagraficaProcedimento", "AnagraficaProcedimento"),
        ("AnagraficaProcedimento", "AnagraficaProcedimento"),
        ("CaricaDati_Parte_RiferimentoProcedimento", "RiferimentoProcedimento"),
        ("procedimento", "RiferimentoProcedimento"),
        ("CaricaDati_Introduttivi_ContributoUnificato", "ContributoUnificato"),
        ("ContributoUnificato", "ContributoUnificato"),
        ("CaricaKeyCodiceOggettoPratica", "CodiceOggetto"),
        ("CodiceOggetto", "CodiceOggetto"),
        ("Datacitazione", "Data citazione"),
        ("dataCitazione", "Data citazione"),
        ("ValoreCausa", "ValoreCausa"),
        ("ModificheAnagrafica", "ModificheAnagrafica"),
        ("checkBoxUrgente", "Urgenza"),
        ("urgente", "Urgenza"),
        ("cboIstanze", "Istanze"),
        ("istanze", "Istanze"),
        ("cboRito", "Rito"),
        ("cboRuolo", "Ruolo"),
        ("cboAutorit", "Ufficio giudiziario"),
    ]
    found: list[str] = []
    seen: set[str] = set()
    for needle, label in checks:
        if needle in body and label not in seen:
            found.append(label)
            seen.add(label)
    return found


def _method_profile(body: str, saved_root_variables: set[str]) -> dict[str, Any]:
    root_assignments = []
    for variable in sorted(saved_root_variables):
        pattern = re.compile(rf"\b{re.escape(variable)}\.(?P<field>[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*)\s*=\s*(?P<value>[^;\n]+);")
        for match in pattern.finditer(body):
            value = clean(match.group("value").strip())
            if len(value) > 180:
                value = value[:177] + "..."
            root_assignments.append(
                {"target": f"{variable}.{clean(match.group('field'))}", "value": value}
            )
    helper_calls = _compact_strings(
        re.findall(
            r"\b(?:CaricaDati|Create_ListAllegati|CaricaKey|PopulateCombo|ImpostaSingolaIstanza|FindSchemaXSD|InsertCommentAfterDatiAttoXML)[A-Za-z0-9_]*\s*\(",
            body,
        ),
        limit=80,
    )
    helper_calls = [value.rstrip("(") for value in helper_calls]
    return {
        "required_data": _method_required_data(body),
        "busta_contract": _compact_strings(
            [
                label
                for needle, label in [
                    ("IndiceBusta.AttoPrincipale.id", "IndiceBusta.AttoPrincipale.id collegato all'atto principale"),
                    ("IndiceBusta.Any", "IndiceBusta.Any popolato con allegati fisici"),
                    ("Create_ListAllegati", "Mappa allegati -> riferimenti IndiceBusta"),
                    ("RefID_Deposito", "RefId per deposito con più buste"),
                    ("SaveToFile(\"DatiAtto.xml", "Salvataggio DatiAtto.xml principale"),
                    ("SaveToFile(\"BUSTA\" + numeroBusta", "Salvataggio DatiAtto.xml complementare"),
                    ("ContributoUnificato", "Contributo unificato quando previsto"),
                    ("checkBoxUrgente", "Flag urgenza quando previsto"),
                ]
                if needle in body
            ],
            limit=40,
        ),
        "root_assignments": root_assignments,
        "helper_calls": helper_calls,
        "ui_controls_read": _compact_strings(
            re.findall(r"\b(?:cbo|txt|dtp|checkBox|UltraCurrencyEditor)[A-Za-z0-9_]+", body),
            limit=80,
        ),
    }


def extract_datiatto() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    form_text = read_text(FORM)
    starts = list(
        re.finditer(
            r"^\tprivate\s+[A-Za-z_][\w.<>,\[\]]*\s+(Create_DatiAtto_[\w]+)\s*\(",
            form_text,
            re.M,
        )
    )
    methods: list[dict[str, Any]] = []
    method_by_name: dict[str, dict[str, Any]] = {}
    for idx, match in enumerate(starts):
        name = match.group(1)
        start = match.start()
        end = starts[idx + 1].start() if idx + 1 < len(starts) else min(len(form_text), start + 25000)
        body = form_text[start:end]
        var_types: dict[str, str] = {}
        for vm in re.finditer(
            r"(?:var|[A-Za-z_][\w\.<>]*)\s+([A-Za-z_][\w]*)\s*=\s*new\s+([A-Za-z_][\w\.]*)\s*\(",
            body,
        ):
            var_types[vm.group(1)] = vm.group(2)
        saved_roots = []
        for sm in re.finditer(r'([A-Za-z_][\w]*)\.SaveToFile\(\s*"(?:BUSTA"\s*\+\s*numeroBusta\s*\+\s*"\\\\)?DatiAtto\.xml"', body):
            var_name = sm.group(1)
            saved_roots.append({"variable": var_name, "type": var_types.get(var_name, "")})
        profile = _method_profile(body, {root["variable"] for root in saved_roots})
        entry = {
            "method": name,
            "generated_types": sorted(set(re.findall(r"new\s+([A-Za-z_][\w\.]*)\s*\(", body)))[:60],
            "saved_roots": saved_roots,
            "uses_indice_busta": "IndiceBusta" in body,
            "uses_anagrafica_procedimento": "AnagraficaProcedimento" in body,
            "uses_contributo_unificato": "ContributoUnificato" in body,
            "uses_notifiche": "Notifica" in body or "SoggettoNotificato" in body,
            "required_data": profile["required_data"],
            "busta_contract": profile["busta_contract"],
            "root_assignments": profile["root_assignments"],
            "helper_calls": profile["helper_calls"],
            "ui_controls_read": profile["ui_controls_read"],
            "line_start_estimate": form_text[: match.start()].count("\n") + 1,
        }
        methods.append(entry)
        method_by_name[name] = entry

    switch_text = _switch_datiatto_text(form_text)
    key_to_methods: list[dict[str, Any]] = []
    key_method_map: dict[str, dict[str, Any]] = {}
    for grouped_keys, body in _outer_case_groups(switch_text):
        method_names = _compact_strings(
            re.findall(r"(Create_DatiAtto_[\w]+)\s*\(", body),
            limit=20,
        )
        saved = [
            root
            for method_name in method_names
            for root in method_by_name.get(method_name, {}).get("saved_roots", [])
        ]
        method_required_data = []
        for method_name in method_names:
            method_required_data.extend(method_by_name.get(method_name, {}).get("required_data", []))
        for key, line_start in grouped_keys:
            entry = {
                "key": key,
                "methods": method_names,
                "saved_roots": saved,
                "flags": _flags_in_block(body),
                "controls": _controls_in_block(body),
                "fixed_object_codes": _fixed_object_codes(body),
                "combo_sources": _combo_sources_in_block(body),
                "assignments": _assignments_in_block(body),
                "required_data": _compact_strings(method_required_data + _method_required_data(body), limit=80),
                "line_start_estimate": line_start,
            }
            key_to_methods.append(entry)
            key_method_map[key] = entry
    return methods, key_to_methods, key_method_map


def line_hits(paths: list[Path], terms: list[str], per_term: int = 30) -> dict[str, list[dict[str, Any]]]:
    hits: dict[str, list[dict[str, Any]]] = {term: [] for term in terms}
    for path in paths:
        text = read_text(path)
        if not text:
            continue
        for no, line in enumerate(text.splitlines(), 1):
            lower = line.lower()
            if len(line) > 800:
                continue
            for term in terms:
                if len(hits[term]) >= per_term:
                    continue
                if term.lower() in lower:
                    hits[term].append(
                        {
                            "file": str(path.relative_to(DECOMP)).replace("\\", "/") if path.is_relative_to(DECOMP) else str(path),
                            "line": no,
                            "text": clean(line.strip())[:260],
                        }
                    )
    return {term: values for term, values in hits.items() if values}


def extract_runtime_refs() -> dict[str, Any]:
    source_paths = [FORM, PCT, QUAL, BROWSER, WIZARD, COMMON, FORM_MAIN, FORM_ALLEGATO]
    texts = {path.name: read_text(path) for path in source_paths}
    urls = sorted(
        set(
            url.rstrip('";),')
            for text in texts.values()
            for url in re.findall(r"https?://[^\s\"<>]+", text)
        )
    )
    subject_prefixes = sorted(
        set(
            clean(m.group(1))
            for m in re.finditer(r'"([^"]*(?:DEPOSITO TELEMATICO|NOTIFICAZIONE|ACCETTAZIONE|CONSEGNA)[^"]*)"', texts.get("FormMain.cs", "") + texts.get("FormSentMailBee.cs", ""))
        )
    )
    return {
        "source_hits": line_hits(source_paths, KEYWORDS, per_term=20),
        "urls": urls,
        "subject_prefixes": subject_prefixes[:120],
    }


def quick_uffici_rows() -> list[dict[str, Any]]:
    if not QUICK_UFFICI_XML.exists():
        return []
    root = ET.parse(QUICK_UFFICI_XML).getroot()
    rows: list[dict[str, Any]] = []
    for ret in root.iter("return"):
        rec: dict[str, Any] = {}
        services: list[str] = []
        service_descriptions: list[str] = []
        for child in ret:
            tag = local_name(child.tag)
            if tag == "servizi":
                service: dict[str, str] = {}
                for sub in child:
                    service[local_name(sub.tag)] = clean((sub.text or "").strip())
                code = service.get("codice")
                if code:
                    services.append(code)
                desc = service.get("descrizione")
                if desc:
                    service_descriptions.append(desc)
            else:
                rec[tag] = clean((child.text or "").strip())
        rec["servizi_codici"] = services
        rec["servizi_descrizioni"] = service_descriptions
        rows.append(rec)
    return rows


def qc_uffici_summary() -> dict[str, Any]:
    if not QUICK_QC_UFFICI_XML.exists():
        return {"rows": 0, "tags": {}}
    root = ET.parse(QUICK_QC_UFFICI_XML).getroot()
    tags = Counter(local_name(item.tag) for item in root.iter())
    return {
        "rows": sum(1 for item in root.iter("row")),
        "tags": dict(tags.most_common(20)),
        "bytes": QUICK_QC_UFFICI_XML.stat().st_size,
    }


REGISTRY_RUNTIME: dict[str, dict[str, Any]] = {
    "CC": {
        "ius_aliases": ["SICID", "RGN", "RNG", "civile ordinario"],
        "quick_registry_code": "CC",
        "logical_service_iusentra": "JPW_SICID",
        "quick_target_path": "JPW_SICID",
        "urn": "CONS-SICC-BE",
        "query_number_type": "RNG",
        "quick_search_method": "ExecuteRicercaInformazioniFascicoloPerTipo",
        "history_method": "ExecuteStoricoFascicolo",
        "roles": ["AVV", "DEL", "CTU", "NOT", "TUT", "AUS"],
        "notes": "Civile ordinario: in QuickOrganizer il registro è CC; IUSENTRA può mantenere alias RGN/RNG ma deve inviare il registro reale CC quando interroga il servizio.",
    },
    "LAV": {
        "ius_aliases": ["SIL", "LAV", "lavoro", "previdenza"],
        "quick_registry_code": "LAV",
        "logical_service_iusentra": "JPW_SIL / JPW_SIL_DISTR",
        "quick_target_path": "JPW_SICID",
        "urn": "CONS-SIL-BE",
        "query_number_type": "RNG",
        "quick_search_method": "ExecuteRicercaInformazioniFascicoloPerTipo",
        "history_method": "ExecuteStoricoFascicolo",
        "roles": ["AVV", "DEL", "CTU", "NOT", "TUT", "AUS"],
        "notes": "QuickOrganizer usa gateway JPW_SICID, ma namespace lavoro CONS-SIL-BE. IUSENTRA ha già fallback logico JPW_SIL_DISTR/JPW_SIL.",
    },
    "VG": {
        "ius_aliases": ["SIVG", "VG", "volontaria giurisdizione"],
        "quick_registry_code": "VG",
        "logical_service_iusentra": "JPW_SIVG",
        "quick_target_path": "JPW_SICID",
        "urn": "CONS-SIVG-BE",
        "query_number_type": "RNG",
        "quick_search_method": "ExecuteRicercaInformazioniFascicoloPerTipo",
        "history_method": "ExecuteStoricoFascicolo",
        "roles": ["AVV", "CTU", "AUS"],
        "notes": "Volontaria giurisdizione: servizio logico SIVG, gateway QuickOrganizer JPW_SICID.",
    },
    "MIN": {
        "ius_aliases": ["MIN", "SIMIN", "minorenni", "minori"],
        "quick_registry_code": "MIN",
        "logical_service_iusentra": "JPW_MIN / JPW_SIMIN",
        "quick_target_path": "JPW_SICID",
        "urn": "CONS-MIN-BE",
        "query_number_type": "RNG",
        "quick_search_method": "ExecuteRicercaInformazioniFascicoloPerTipo",
        "history_method": "ExecuteStoricoFascicolo",
        "roles": ["AVV", "DEL", "CTU", "NOT", "TUT", "AUS"],
        "notes": "Il XML ministeriale QuickOrganizer espone MIN per i tribunali per i minorenni; IUSENTRA distingue MIN e SIMIN come servizi logici già provati.",
    },
    "FALL": {
        "ius_aliases": ["SIECIC", "FALL", "procedure concorsuali", "fallimentare"],
        "quick_registry_code": "FALL",
        "logical_service_iusentra": "JPW_SIECIC",
        "quick_target_path": "JPW_SIECIC",
        "urn": "CONS-SIECIC-BE",
        "query_number_type": "RNG",
        "quick_search_method": "ExecuteRicercaInformazioniFascicoloPerNumero",
        "history_method": "ExecuteStoricoFascicolo con idDfa",
        "roles": ["AVV", "DEL", "CTU", "CUR", "CUS", "AUS"],
        "notes": "Procedure concorsuali SIECIC; per dettaglio può servire idRuoloJPW/idDfa reale, non inventabile.",
    },
    "ESM": {
        "ius_aliases": ["SIECIC", "ESM", "esecuzione mobiliare"],
        "quick_registry_code": "ESM",
        "logical_service_iusentra": "JPW_SIECIC",
        "quick_target_path": "JPW_SIECIC",
        "urn": "CONS-SIECIC-BE",
        "query_number_type": "RNG",
        "quick_search_method": "ExecuteRicercaInformazioniFascicoloPerNumero",
        "history_method": "ExecuteStoricoFascicolo con idDfa",
        "roles": ["AVV", "DEL", "CTU", "CUS", "AUS"],
        "notes": "Esecuzioni mobiliari SIECIC; stesso gateway delle concorsuali ma registro diverso.",
    },
    "ESIM": {
        "ius_aliases": ["SIECIC", "ESIM", "esecuzione immobiliare"],
        "quick_registry_code": "ESIM",
        "logical_service_iusentra": "JPW_SIECIC",
        "quick_target_path": "JPW_SIECIC",
        "urn": "CONS-SIECIC-BE",
        "query_number_type": "RNG",
        "quick_search_method": "ExecuteRicercaInformazioniFascicoloPerNumero",
        "history_method": "ExecuteStoricoFascicolo con idDfa",
        "roles": ["AVV", "DEL", "CTU", "CUS", "AUS"],
        "notes": "Esecuzioni immobiliari SIECIC; richiede gestione ruolo/dfa reale.",
    },
    "GDP": {
        "ius_aliases": ["SIGP", "GDP", "GP", "giudice di pace"],
        "quick_registry_code": "GP",
        "xml_registry_code": "GDP",
        "logical_service_iusentra": "JPW_SIGP",
        "quick_target_path": "JPW_SIGP",
        "urn": "CONS-SIGP-BE",
        "query_number_type": "RNG",
        "quick_search_method": "ExecuteRicercaInformazioniFascicoloPerTipo / ExecuteRicercaInformazioniFascicoloPerRMO",
        "history_method": "ExecuteStoricoFascicolo",
        "roles": ["AVV", "DEL", "CTU", "AUS"],
        "notes": "Nel XML il registro è GDP; nel codice QuickOrganizer il filtro storico usa GP. IUSENTRA deve accettare entrambi come alias.",
    },
    "CASSCI": {
        "ius_aliases": ["CASSCI", "cassazione civile"],
        "quick_registry_code": "CASSCI",
        "logical_service_iusentra": "JPW_CASSCI",
        "quick_target_path": "JPW_CASS",
        "urn": "CONS-CASSCI",
        "query_number_type": "",
        "quick_search_method": "ExecuteRicercaRicorsiCassazione",
        "history_method": "profilo/documenti Cassazione",
        "roles": ["AVV", "DEL", "CTU", "AUS", "AVV@AVV"],
        "notes": "QuickOrganizer usa anche URL browser PST con ufficio 80417740588, registroRicerca=CASSCI e ruoloRicerca=AVV@AVV.",
    },
    "CASSPE": {
        "ius_aliases": ["CASSPE", "cassazione penale"],
        "quick_registry_code": "CASSPE",
        "logical_service_iusentra": "JPW_CASSPE",
        "quick_target_path": "JPW_CASS",
        "urn": "CONS-CASSPE",
        "query_number_type": "",
        "quick_search_method": "consultazione browser PST / QP_Ricorsi in IUSENTRA",
        "history_method": "profilo/documenti Cassazione penale",
        "roles": ["AVV@AVV"],
        "notes": "Il XML QuickOrganizer espone CASSPE e il menu apre il PST penale; IUSENTRA ha già prove live su JPW_CASSPE/QP_Ricorsi.",
    },
    "Agrarie": {
        "ius_aliases": ["AGRARIE", "controversie agrarie"],
        "quick_registry_code": "Agrarie",
        "logical_service_iusentra": "da verificare",
        "quick_target_path": "",
        "urn": "",
        "query_number_type": "",
        "quick_search_method": "non rilevata nel wizard import fascicoli",
        "history_method": "solo filtro locale PRATICHE",
        "roles": [],
        "notes": "QuickOrganizer lo conserva come tipo registro locale/filtro, ma non ho trovato una combinazione JPW autonoma nel XML ministeriale.",
    },
    "Speciali": {
        "ius_aliases": ["SPECIALI", "procedimenti speciali", "sommari"],
        "quick_registry_code": "Speciali",
        "logical_service_iusentra": "da verificare",
        "quick_target_path": "",
        "urn": "",
        "query_number_type": "",
        "quick_search_method": "non rilevata nel wizard import fascicoli",
        "history_method": "solo filtro locale PRATICHE",
        "roles": [],
        "notes": "QuickOrganizer lo conserva come tipo registro locale/filtro, ma non ho trovato una combinazione JPW autonoma nel XML ministeriale.",
    },
}


def collect_registry_download_catalog() -> dict[str, Any]:
    rows = quick_uffici_rows()
    combo_map: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        office_type = row.get("tipoUfficio", "")
        office_name = row.get("descrizione", "")
        office_code = row.get("codiceUfficio", "")
        for servizio in row.get("servizi_codici", []):
            pass
        for service_idx, service_code in enumerate(row.get("servizi_codici", [])):
            # The compact row data keeps service codes and registry details in the
            # original XML parser below; this loop is only for service counts.
            _ = (service_idx, service_code)

    if not QUICK_UFFICI_XML.exists():
        return {"generated_at": GENERATED_AT, "records": [], "service_counts": {}}

    root = ET.parse(QUICK_UFFICI_XML).getroot()
    service_counts: Counter = Counter()
    for ret in root.iter("return"):
        office: dict[str, str] = {}
        for child in ret:
            tag = local_name(child.tag)
            if tag in {"codiceUfficio", "descrizione", "tipoUfficio", "descTipoUfficio", "indirizzoPec"}:
                office[tag] = clean((child.text or "").strip())
        for service_node in ret:
            if local_name(service_node.tag) != "servizi":
                continue
            service: dict[str, str] = {}
            registry_nodes = []
            for child in service_node:
                if local_name(child.tag) == "registri":
                    registry_nodes.append(child)
                else:
                    service[local_name(child.tag)] = clean((child.text or "").strip())
            service_code = service.get("codice", "")
            if service_code:
                service_counts[service_code] += 1
            for registry_node in registry_nodes:
                registry = {local_name(child.tag): clean((child.text or "").strip()) for child in registry_node}
                key = (
                    service_code,
                    registry.get("codiceApplicazione", ""),
                    registry.get("codice", ""),
                    registry.get("descrizione", ""),
                )
                entry = combo_map.setdefault(
                    key,
                    {
                        "service_code_xml": service_code,
                        "service_description_xml": service.get("descrizione", ""),
                        "application_code_xml": registry.get("codiceApplicazione", ""),
                        "registry_code_xml": registry.get("codice", ""),
                        "registry_description_xml": registry.get("descrizione", ""),
                        "office_count": 0,
                        "office_types": set(),
                        "sample_offices": [],
                    },
                )
                entry["office_count"] += 1
                if office_type := office.get("tipoUfficio", ""):
                    entry["office_types"].add(office_type)
                if len(entry["sample_offices"]) < 8:
                    entry["sample_offices"].append(
                        {
                            "codiceUfficio": office.get("codiceUfficio", ""),
                            "descrizione": office.get("descrizione", ""),
                            "tipoUfficio": office.get("tipoUfficio", ""),
                            "pec": office.get("indirizzoPec", ""),
                        }
                    )

    records: list[dict[str, Any]] = []
    for entry in combo_map.values():
        xml_code = entry["registry_code_xml"]
        runtime = REGISTRY_RUNTIME.get(xml_code) or REGISTRY_RUNTIME.get("GDP" if xml_code == "GDP" else "")
        if entry["service_code_xml"] == "JPW_UNEP":
            runtime = {
                "ius_aliases": ["UNEP", xml_code],
                "quick_registry_code": xml_code,
                "logical_service_iusentra": "JPW_UNEP",
                "quick_target_path": "JPW_UNEP",
                "urn": "",
                "query_number_type": "",
                "quick_search_method": "non rilevata nel wizard import fascicoli",
                "history_method": "canale UNEP separato",
                "roles": [],
                "notes": "Registro UNEP esposto dal catalogo uffici; non è scarico fascicolo civile ordinario.",
            }
        runtime = runtime or {}
        record = {
            **entry,
            "office_types": sorted(entry["office_types"]),
            "ius_aliases": runtime.get("ius_aliases", []),
            "quick_registry_code": runtime.get("quick_registry_code", xml_code),
            "logical_service_iusentra": runtime.get("logical_service_iusentra", entry["service_code_xml"]),
            "quick_target_path": runtime.get("quick_target_path", entry["service_code_xml"]),
            "urn": runtime.get("urn", ""),
            "query_number_type": runtime.get("query_number_type", ""),
            "quick_search_method": runtime.get("quick_search_method", ""),
            "history_method": runtime.get("history_method", ""),
            "allowed_roles": runtime.get("roles", []),
            "notes": runtime.get("notes", ""),
        }
        records.append(record)
    records.sort(key=lambda item: (item["service_code_xml"], item["registry_code_xml"]))
    for legacy_code in ("Agrarie", "Speciali"):
        runtime = REGISTRY_RUNTIME[legacy_code]
        records.append(
            {
                "service_code_xml": "",
                "service_description_xml": "Tipo registro locale QuickOrganizer",
                "application_code_xml": "",
                "registry_code_xml": legacy_code,
                "registry_description_xml": "Controversie Agrarie" if legacy_code == "Agrarie" else "Procedimenti Speciali o Sommari",
                "office_count": 0,
                "office_types": [],
                "sample_offices": [],
                "ius_aliases": runtime["ius_aliases"],
                "quick_registry_code": runtime["quick_registry_code"],
                "logical_service_iusentra": runtime["logical_service_iusentra"],
                "quick_target_path": runtime["quick_target_path"],
                "urn": runtime["urn"],
                "query_number_type": runtime["query_number_type"],
                "quick_search_method": runtime["quick_search_method"],
                "history_method": runtime["history_method"],
                "allowed_roles": runtime["roles"],
                "notes": runtime["notes"],
            }
        )
    return {
        "generated_at": GENERATED_AT,
        "source": {
            "quickorganizer_xml": str(QUICK_UFFICI_XML),
            "quickorganizer_common_cs": str(COMMON),
            "quickorganizer_wizard_cs": str(WIZARD),
            "iusentra_surface": "frontend/src/components/TelematicoSurfacePage.tsx",
            "iusentra_api_matrix": "web/blueprints/api_v1_react.py",
            "iusentra_live_log": "artifacts/audit/pst-mappatura-live-log-20260602.md",
        },
        "service_counts": dict(service_counts.most_common()),
        "records": records,
    }


def collect_portal_download_flow() -> dict[str, Any]:
    return {
        "generated_at": GENERATED_AT,
        "source": {
            "wizard": str(WIZARD),
            "pct": str(PCT),
            "browser": str(BROWSER),
            "common": str(COMMON),
            "form_main": str(FORM_MAIN),
            "ufficio_registro_ruolo": str(DECOMP / "QuickOrganizer" / "UfficioRegistroRuolo.cs"),
        },
        "studio_telematico_menu": {
            "access_menu_caption": "Accesso al PolisWeb...",
            "commands": [
                {
                    "key": "Importa_Pratiche_PolisWeb",
                    "caption": "Importa Pratiche dal PolisWeb",
                    "launcher": "ImportaPratichePolisWeb(-1)",
                    "kind": "wizard_servizi",
                    "behavior": "Apre `WizardImportaPraticheDaPolisWeb` in modalità importazione; interroga i servizi e crea/aggiorna pratiche, profilo, eventi e documenti.",
                },
                {
                    "key": "Cerca_Eventi_Polisweb",
                    "caption": "Eventi di Cancelleria",
                    "launcher": "ImportaPratichePolisWeb(-2)",
                    "kind": "wizard_servizi",
                    "behavior": "Apre lo stesso wizard con `PCT.RicercaNuoviEventi=true` per cercare eventi di cancelleria.",
                },
                {
                    "key": "Fascicolo_Ufficio",
                    "caption": "Fascicolo d'ufficio",
                    "launcher": "RecuperaDatiFascicoloUfficio(numeroPratica, showBrowser:true)",
                    "kind": "portale_pst_browser",
                    "behavior": "Parte dalla pratica selezionata e apre la pagina PST `_infofascicolo` nel browser interno.",
                },
                {
                    "key": "Fascicolo_Ufficio_Eventi",
                    "caption": "Eventi fascicolo d'ufficio",
                    "launcher": "RecuperaDatiFascicoloUfficio(...); BrowserForm.SelezionaTabEventiFascicolo()",
                    "kind": "portale_pst_browser",
                    "behavior": "Dopo `_infofascicolo` cerca link contenente `storicofascicolo` e naviga alla scheda eventi/storico.",
                },
                {
                    "key": "Fascicolo_Ufficio_Documenti",
                    "caption": "Documenti fascicolo d'ufficio",
                    "launcher": "RecuperaDatiFascicoloUfficio(...); BrowserForm.SelezionaTabDocumentiFascicolo()",
                    "kind": "portale_pst_browser",
                    "behavior": "Dopo `_infofascicolo` cerca link contenente `documentifascicolo` e naviga alla scheda documenti.",
                },
                {
                    "key": "Fascicolo_Ufficio_Notifiche",
                    "caption": "Comunicazioni/notifiche fascicolo d'ufficio",
                    "launcher": "RecuperaDatiFascicoloUfficio(...); BrowserForm.SelezionaTabNotificheFascicolo()",
                    "kind": "portale_pst_browser",
                    "behavior": "Dopo `_infofascicolo` cerca link contenente `comunicazionifascicolo` e naviga alla scheda comunicazioni/notifiche.",
                },
                {
                    "key": "Agenda_PolisWeb",
                    "caption": "Ricerca nello storico delle attività",
                    "launcher": "UfficioRegistroRuolo(\"Agenda\")",
                    "kind": "portale_pst_browser",
                    "behavior": "Costruisce URL PST agenda per registro/ufficio/ruolo; BrowserForm compila `dataDal`, `dataAl` e clicca dopo `ruoloRicerca`.",
                },
                {
                    "key": "Scarica_Udienze_Scadenze_PolisWeb",
                    "caption": "Ricerca nel registro delle scadenze",
                    "launcher": "UfficioRegistroRuolo(\"Scadenze\")",
                    "kind": "portale_pst_browser",
                    "behavior": "Costruisce URL PST scadenze per registro/ufficio/ruolo; BrowserForm compila intervallo date e avvia la ricerca.",
                },
                {
                    "key": "Scarica_Documenti_PolisWeb",
                    "caption": "Scarica documenti dal PolisWeb",
                    "launcher": "UfficioRegistroRuolo(\"Documenti\")",
                    "kind": "portale_pst_browser_download",
                    "behavior": "Costruisce URL PST documenti; BrowserForm seleziona `tipiDocumento-5`, date deposito e intercetta i download WebView2.",
                },
                {
                    "key": "Ricerca_Fascicoli_Costituzione",
                    "caption": "Ricerca RG per costituzione",
                    "launcher": "UfficioRegistroRuolo(\"Costituzione\")",
                    "kind": "portale_pst_browser",
                    "behavior": "Costruisce URL PST per ricerca fascicoli ai fini della costituzione.",
                },
                {
                    "key": "Consultazione_Fascicoli_Cassazione_Civile",
                    "caption": "Cassazione civile",
                    "launcher": "URL diretto PST",
                    "kind": "portale_pst_browser",
                    "behavior": "Apre `pst_2_9_2_2.wp?ufficioRicerca=80417740588&registroRicerca=CASSCI&ruoloRicerca=AVV@AVV`.",
                },
                {
                    "key": "Consultazione_Fascicoli_Cassazione_Penale",
                    "caption": "Cassazione penale",
                    "launcher": "URL diretto PST",
                    "kind": "portale_pst_browser",
                    "behavior": "Apre `pst_2_9_1_2.wp?ufficioRicerca=80417740588&registroRicerca=CASSPE&ruoloRicerca=AVV@AVV`.",
                },
                {
                    "key": "NotificheNonPerfezionate",
                    "caption": "Area notifiche non perfezionate",
                    "launcher": "BrowserForm via autenticazione PST",
                    "kind": "portale_pst_browser",
                    "behavior": "Parte da `authentication/it/pst_ar.wp`; BrowserForm rimappa la descrizione su `https://servizipst.giustizia.it/PST/PortaleNotifiche`.",
                },
            ],
        },
        "portal_url_matrix": {
            "base": "https://servizipst.giustizia.it/PST/it/",
            "query": ["registroRicerca", "ufficioRicerca", "ruoloRicerca={role}@{role}"],
            "registry_paths": [
                {"registry": "CC", "description": "Contenzioso civile", "area": "pst_2_1_1"},
                {"registry": "MIN", "description": "Minorenni", "area": "pst_2_1_1"},
                {"registry": "LAV", "description": "Lavoro", "area": "pst_2_1_2"},
                {"registry": "FALL", "description": "Procedure concorsuali", "area": "pst_2_1_3"},
                {"registry": "ESIM", "description": "Esecuzioni immobiliari", "area": "pst_2_1_4"},
                {"registry": "ESM", "description": "Esecuzioni mobiliari", "area": "pst_2_1_5"},
                {"registry": "GP/GDP", "description": "Giudice di Pace", "area": "pst_2_1_6", "registroRicerca": "GDP"},
                {"registry": "VG", "description": "Volontaria giurisdizione", "area": "pst_2_1_14"},
            ],
            "function_suffixes": [
                {"function": "Agenda", "suffix": "_1.wp"},
                {"function": "Scadenze", "suffix": "_2.wp"},
                {"function": "Documenti", "suffix": "_4.wp"},
                {"function": "Costituzione", "suffix": "_5.wp"},
            ],
            "cassazione": [
                {
                    "registry": "CASSCI",
                    "url": "https://servizipst.giustizia.it/PST/it/pst_2_9_2_2.wp?ufficioRicerca=80417740588&registroRicerca=CASSCI&ruoloRicerca=AVV@AVV",
                },
                {
                    "registry": "CASSPE",
                    "url": "https://servizipst.giustizia.it/PST/it/pst_2_9_1_2.wp?ufficioRicerca=80417740588&registroRicerca=CASSPE&ruoloRicerca=AVV@AVV",
                },
            ],
        },
        "browser_download_handler": {
            "webview2_event": "OnWebView2DownloadStarting",
            "accepted_extensions_or_patterns": [
                ".PDF",
                ".RTF",
                ".TXT",
                ".JPG",
                ".GIF",
                ".TIFF",
                ".XML",
                ".P7M",
                ".ZIP",
                ".RAR",
                "action?crs=",
            ],
            "save_targets": [
                {
                    "target": "PRATICA",
                    "behavior": "Se non c'è pratica corrente chiede una pratica; poi salva file e record in `TESTI` con `TIPO=PCT` e `NUMEROPRATICA`.",
                },
                {
                    "target": "DESKTOP",
                    "behavior": "Sposta il file in `Desktop\\POLISWEB\\` o `Desktop\\WHATSAPP\\`.",
                },
                {
                    "target": "HASH",
                    "behavior": "Sposta in cartella temporanea e mostra SHA-256 tramite `FormHash`.",
                },
            ],
            "p7m_handling": "Se il `.p7m` non risulta firma CAdES valida, prova a normalizzare l'estensione verso il contenuto originale (`.pdf`, `.xml`, `.zip`, ecc.).",
        },
        "search_modes": [
            {
                "mode": "ricerca_esatta_numero_anno",
                "quick_behavior": "Se `NumeroPratica > 0`, il wizard passa numero ruolo e anno ruolo ai metodi di ricerca.",
                "methods": [
                    "ExecuteRicercaInformazioniFascicoloPerTipo",
                    "ExecuteRicercaInformazioniFascicoloPerNumero",
                    "ExecuteRicercaRicorsiCassazione",
                ],
                "payload_fields": ["idUfficio", "tipo=RNG/RGN", "numero", "anno", "role", "registro"],
            },
            {
                "mode": "ricerca_per_anno",
                "quick_behavior": "Se non c'è numero ruolo, il wizard passa `numeroRuolo=0` e `anno=cboAnno.Text`; il portale restituisce l'elenco dei fascicoli visibili per quell'anno.",
                "methods": [
                    "ExecuteRicercaInformazioniFascicoloPerTipo",
                    "ExecuteRicercaInformazioniFascicoloPerNumero",
                    "ExecuteRicercaRicorsiCassazione",
                    "ExecuteRicercaInformazioniFascicoloPerRMO per SIGP senza numero",
                ],
                "payload_fields": ["idUfficio", "tipo=RNG/RGN", "numero=0", "anno", "role", "registro"],
            },
            {
                "mode": "cassazione_per_anno",
                "quick_behavior": "La busta `EnvelopeRicercaRicorsiCassazione` usa `QC_Ricorsi` per civile e in IUSENTRA `QP_Ricorsi` per penale; per annuale si usano intervalli data dell'anno.",
                "methods": ["ExecuteRicercaRicorsiCassazione"],
                "payload_fields": ["DATADEP_DA/DATADEP_AL o DATAISCR_DA/DATAISCR_AL", "ufficio 80417740588", "registro CASSCI/CASSPE"],
            },
        ],
        "fascicolo_flow": [
            {
                "step": 1,
                "name": "selezione registro/ufficio/ruolo/anno",
                "details": "Il wizard sceglie `sUrn`, `sTargetPath`, `sRole`, `sIDUfficio`, `sAnnoRuoloGenerale`, `sIdRegistro`.",
            },
            {
                "step": 2,
                "name": "ricerca elenco fascicoli",
                "details": "Chiama `RicercaInformazioniFascicoloPerTipo`, `RicercaInformazioniFascicoloPerNumero`, `RicercaInformazioniFascicoloPerRMO` o `RicercaRicorsiCassazione`.",
            },
            {
                "step": 3,
                "name": "profilo fascicolo",
                "details": "`ExecuteProfiloFascicolo` recupera oggetto, stato, data iscrizione, sezione, numero sezionale e dati base.",
            },
            {
                "step": 4,
                "name": "storico fascicolo",
                "details": "`ExecuteStoricoFascicolo` recupera eventi/storico e `IDDOCUMENTO` degli atti collegati.",
            },
            {
                "step": 5,
                "name": "master/detail documenti",
                "details": "`SelezionaDocumentiFascicolo` scorre lo storico; per ogni `IDDOCUMENTO` chiama `EstraiMasterDetailAtto` o `EstraiMasterDetailAttoSIECIC`.",
            },
            {
                "step": 6,
                "name": "download singolo documento",
                "details": "`DownloadDocumentoDIGSIA` invia `downloadDocumento` con `idCat` e `original=true/false`; estrae la parte MIME base64 e salva il file.",
            },
            {
                "step": 7,
                "name": "download intero fascicolo",
                "details": "Non risulta un endpoint unico: QuickOrganizer scarica l'intero fascicolo iterando tutti i documenti selezionati nella griglia, inclusi allegati.",
            },
        ],
        "download_options": [
            {"label": "Scarica come duplicato", "duplicato": True, "original": True, "effect": "salva duplicato; se PDF marca `signed=true` nel record TESTI"},
            {"label": "Scarica come copia", "duplicato": False, "original": False, "effect": "salva copia informatica e normalizza estensioni `.p7m` verso estensione originale quando possibile"},
            {"label": "Non scaricare", "effect": "salta il documento"},
        ],
        "document_fields": [
            "dataDeposito",
            "autore",
            "tipo",
            "idUfficio",
            "IdDocumento",
            "IdDocMittente",
            "stato",
            "annoDocumento",
            "numeroDocumento",
            "annoFascicolo",
            "numeroFascicolo",
            "subprocedimento",
            "IdCat",
            "nomeFileOriginale",
            "CognomeNomeDepositante",
            "TIPOLOGIA",
            "DOWNLOAD",
        ],
        "local_persistence": {
            "PRATICHE": ["TIPO", "AUT_GIUDIZ", "RUOLO_GEN", "ANNO_RUOLO_GEN", "SUB_PROCEDIMENTO", "SEZIONE", "ISTRUTTORE", "Stato_Pratica"],
            "TESTI": ["TIPO=PCT", "NUMEROPRATICA", "IdCat", "NOME_ATTO", "NOME_DOS", "Tipologia", "signed", "DATA_ATTO"],
            "AGENDA": ["IdStorico", "Controllo", "NumeroPratica", "StartDateTime", "Subject", "Ruolo", "Anno_Ruolo_Gen", "SUB_PROCEDIMENTO"],
        },
        "iusentra_rules": [
            "Salvare ogni documento con hash, idCat/IdDocumento, origine portale, registro, ufficio, ruolo e data italiana.",
            "Deduplicare per tenant/fascicolo/idCat/hash prima di scaricare di nuovo.",
            "Scarico intero fascicolo = batch governato di download singoli con progress e ripresa su errore.",
            "Non inventare `idRuoloJPW`/`idDfa`: se il portale non li espone, il job deve fermarsi con motivo puntuale.",
        ],
    }


def ius_cert_codes() -> set[str]:
    codes = set()
    if IUS_CERT_DIR.exists():
        for path in IUS_CERT_DIR.glob("*.cer"):
            code = cert_code_from_name(path.name)
            if code:
                codes.add(code)
    return codes


def ius_object_records() -> list[dict[str, Any]]:
    data = read_json(IUS_OBJECT_CATALOG, {})
    records = data.get("records", []) if isinstance(data, dict) else []
    return records


def compare_certificates_and_codes() -> dict[str, Any]:
    rows = quick_uffici_rows()
    rows_with_cert = [row for row in rows if row.get("nomeCertificatoCifra")]
    quick_cert_names = sorted({row.get("nomeCertificatoCifra", "") for row in rows_with_cert if row.get("nomeCertificatoCifra")})
    quick_cert_codes = sorted({cert_code_from_name(name) for name in quick_cert_names if cert_code_from_name(name)})
    quick_local_cers = sorted(QUICK_CERT_DIR.glob("*.cer")) if QUICK_CERT_DIR.exists() else []
    quick_local_names = sorted(path.name for path in quick_local_cers)

    ius_codes = sorted(ius_cert_codes())
    ius_names = sorted(path.name for path in IUS_CERT_DIR.glob("*.cer")) if IUS_CERT_DIR.exists() else []
    missing_by_code = sorted(set(quick_cert_codes) - set(ius_codes))
    common_by_code = sorted(set(quick_cert_codes) & set(ius_codes))
    extra_by_code = sorted(set(ius_codes) - set(quick_cert_codes))
    missing_rows = [row for row in rows_with_cert if cert_code_from_name(row.get("nomeCertificatoCifra", "")) in missing_by_code]
    missing_by_type = Counter(row.get("tipoUfficio") or "" for row in missing_rows)
    missing_with_services = [
        {
            "codiceUfficio": row.get("codiceUfficio", ""),
            "descrizione": row.get("descrizione", ""),
            "tipoUfficio": row.get("tipoUfficio", ""),
            "cert": row.get("nomeCertificatoCifra", ""),
            "servizi": row.get("servizi_codici", []),
        }
        for row in missing_rows
        if row.get("servizi_codici")
    ]

    quick_objects = read_json(OBJECT_SRC, [])
    quick_leaf_objects = [item for item in quick_objects if item.get("key")]
    quick_code_to_label = {
        extract_code(item.get("key", "")): item.get("text") or item.get("categoria") or item.get("path", "")
        for item in quick_leaf_objects
        if extract_code(item.get("key", ""))
    }
    ius_records = ius_object_records()
    ius_code_to_label = {
        str(item.get("codice", "")): item.get("descrizione", "")
        for item in ius_records
        if item.get("codice")
    }
    missing_codes = sorted(set(quick_code_to_label) - set(ius_code_to_label))
    extra_codes = sorted(set(ius_code_to_label) - set(quick_code_to_label))
    common_codes = sorted(set(quick_code_to_label) & set(ius_code_to_label))
    label_diffs = []
    for code in common_codes:
        q = quick_code_to_label[code]
        i = ius_code_to_label[code]
        if normalize_label(q) != normalize_label(i):
            label_diffs.append({"codice": code, "quickorganizer": q, "iusentra": i})

    return {
        "generated_at": GENERATED_AT,
        "quickorganizer": {
            "uffici_rows": len(rows),
            "uffici_with_pec": sum(1 for row in rows if row.get("indirizzoPec")),
            "cert_names_in_xml": len(quick_cert_names),
            "cert_codes_in_xml": len(quick_cert_codes),
            "local_cer_files": quick_local_names,
            "qc_uffici": qc_uffici_summary(),
        },
        "iusentra": {
            "cert_files": len(ius_names),
            "cert_codes": len(ius_codes),
            "audit": read_json(IUS_CERT_AUDIT, {}),
        },
        "certificate_compare": {
            "common_by_code": len(common_by_code),
            "missing_by_code": len(missing_by_code),
            "extra_by_code": len(extra_by_code),
            "missing_codes": missing_by_code,
            "missing_by_type": dict(missing_by_type),
            "missing_with_services": missing_with_services,
            "interpretation": "Le righe mancanti per codice QuickOrganizer sono in larga parte sezioni distaccate o righe senza servizi telematici; non vanno confuse con il perimetro operativo IUSENTRA già auditato.",
        },
        "object_compare": {
            "quick_leaf_codes": len(quick_code_to_label),
            "ius_records": len(ius_code_to_label),
            "common": len(common_codes),
            "missing_in_iusentra": missing_codes,
            "extra_in_iusentra": len(extra_codes),
            "label_diffs_count": len(label_diffs),
            "label_diffs_sample": label_diffs[:80],
        },
    }


def powershell_json(script: str, executable: str = "powershell") -> Any:
    try:
        result = subprocess.run(
            [executable, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "-"],
            input=script,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=120,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}
    if result.returncode != 0:
        return {"error": result.stderr.strip() or result.stdout.strip()}
    out = result.stdout.strip()
    if not out:
        return None
    try:
        return scrub(json.loads(out))
    except json.JSONDecodeError:
        return {"raw": clean(out[:4000])}


def dll_exe_inventory() -> list[dict[str, Any]]:
    ps = r"""
$ErrorActionPreference = 'SilentlyContinue'
$files = Get-ChildItem -LiteralPath 'C:\QuickOrganizer' -Recurse -Force -File |
  Where-Object { $_.Extension -in '.dll','.exe' } |
  Sort-Object FullName
$rows = foreach ($f in $files) {
  $asm = $null
  $refs = @()
  try {
    $an = [System.Reflection.AssemblyName]::GetAssemblyName($f.FullName)
    $asm = $an.FullName
    try {
      $loaded = [System.Reflection.Assembly]::ReflectionOnlyLoadFrom($f.FullName)
      $refs = @($loaded.GetReferencedAssemblies() | ForEach-Object { $_.Name })
    } catch {}
  } catch {}
  [pscustomobject]@{
    path = $f.FullName
    name = $f.Name
    extension = $f.Extension
    bytes = $f.Length
    modified = $f.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')
    product = $f.VersionInfo.ProductName
    file_version = $f.VersionInfo.FileVersion
    company = $f.VersionInfo.CompanyName
    managed = [bool]$asm
    assembly = $asm
    references = $refs
  }
}
$rows | ConvertTo-Json -Depth 5
"""
    data = powershell_json(ps)
    if isinstance(data, dict) and data.get("error") and (TEMP / "quickorganizer_dll_exe_inventory.json").exists():
        return read_json(TEMP / "quickorganizer_dll_exe_inventory.json", [])
    return data if isinstance(data, list) else []


def classify_library(path: str, name: str) -> str:
    lower = (path + " " + name).lower()
    if "quickorganizer.exe.webview2" in lower:
        return "runtime WebView2"
    if name.lower().startswith("system.") or name.lower() in {"netstandard.dll", "microsoft.win32.primitives.dll"}:
        return "framework .NET"
    if "infragistics" in lower:
        return "UI WinForms/Infragistics"
    if "mailbee" in lower:
        return "PEC/email"
    if "signlib" in lower or "system.security.cryptography" in lower:
        return "firma/cifratura"
    if "webview2" in lower or "devtools" in lower:
        return "portali/browser"
    if "google.apis" in lower:
        return "agenda Google"
    if "txtextcontrol" in lower or lower.startswith("tx") or "\\tx" in lower:
        return "editor/documenti"
    if "newtonsoft" in lower or "htmlagilitypack" in lower or "automapper" in lower:
        return "supporto dati/parsing"
    if "dotnettwain" in lower:
        return "scanner/acquisizione"
    return "altro"


def keyword_hits_for_file(path: Path) -> dict[str, int]:
    try:
        data = path.read_bytes()
    except OSError:
        return {}
    if len(data) > 90_000_000:
        return {}
    lower = data.lower()
    hits: dict[str, int] = {}
    for term in KEYWORDS:
        raw = term.lower().encode("utf-8", errors="ignore")
        count = lower.count(raw)
        if count == 0:
            count = lower.count(term.lower().encode("utf-16le", errors="ignore"))
        if count:
            hits[term] = count
    return hits


def collect_resource_inventory() -> dict[str, Any]:
    all_files = [p for p in QUICK_ROOT.rglob("*") if p.is_file()]
    ext_counts_all = Counter((p.suffix.lower() or "(no extension)") for p in all_files)
    files_no_webview = [p for p in all_files if "QuickOrganizer.exe.WebView2" not in str(p)]
    ext_counts_no_webview = Counter((p.suffix.lower() or "(no extension)") for p in files_no_webview)

    dlls = dll_exe_inventory()
    for row in dlls:
        row["category"] = classify_library(row.get("path", ""), row.get("name", ""))
    library_categories = Counter(row.get("category", "altro") for row in dlls if row.get("extension") == ".dll")

    domain_hits = []
    domain_exts = {".dll", ".exe", ".config", ".xml", ".json", ".xslt", ".htm", ".txt", ".ps1"}
    for path in all_files:
        if path.suffix.lower() not in domain_exts:
            continue
        hits = keyword_hits_for_file(path)
        if not hits:
            continue
        domain_hits.append(
            {
                "path": str(path).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "hits": hits,
            }
        )
    domain_hits.sort(key=lambda item: (-sum(item["hits"].values()), item["path"]))

    embedded_resources: list[dict[str, Any]] = []
    csproj_resources: list[str] = []
    if QUICK_CSPROJ.exists():
        text = read_text(QUICK_CSPROJ)
        csproj_resources = sorted(set(re.findall(r'<(?:EmbeddedResource|None|Content)\s+Include="([^"]+)"', text)))
    for path in DECOMP.iterdir() if DECOMP.exists() else []:
        if path.is_file() and not path.name.endswith((".cs", ".csproj", ".config", ".json")):
            embedded_resources.append(
                {
                    "name": path.name,
                    "extension": path.suffix.lower() or "(no extension)",
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    embedded_counts = Counter(item["extension"] for item in embedded_resources)

    cert_files = sorted(list(QUICK_CERT_DIR.glob("*.cer")) if QUICK_CERT_DIR.exists() else [])
    embedded_cert = DECOMP / "QuickOrganizer.ProcessoTelematico.pst.cer"
    cert_targets = cert_files + ([embedded_cert] if embedded_cert.exists() else [])
    cert_ps_rows = []
    if cert_targets:
        target_list = "\n".join(str(p).replace("'", "''") for p in cert_targets)
        ps = f"""
$paths = @'
{target_list}
'@ -split "`n" | Where-Object {{ $_.Trim() }}
$rows = foreach ($p in $paths) {{
  try {{
    $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($p)
    [pscustomobject]@{{
      path = $p
      subject = $cert.Subject
      issuer = $cert.Issuer
      thumbprint = $cert.Thumbprint
      not_before = $cert.NotBefore.ToString('yyyy-MM-dd HH:mm:ss')
      not_after = $cert.NotAfter.ToString('yyyy-MM-dd HH:mm:ss')
    }}
  }} catch {{
    [pscustomobject]@{{ path = $p; error = $_.Exception.Message }}
  }}
}}
$rows | ConvertTo-Json -Depth 4
"""
        parsed = powershell_json(ps)
        if isinstance(parsed, dict):
            cert_ps_rows = [parsed]
        elif isinstance(parsed, list):
            cert_ps_rows = parsed

    return {
        "generated_at": GENERATED_AT,
        "quick_root": str(QUICK_ROOT),
        "file_counts": {
            "total_files": len(all_files),
            "without_webview2": len(files_no_webview),
            "extensions_all": dict(ext_counts_all.most_common()),
            "extensions_without_webview2": dict(ext_counts_no_webview.most_common()),
        },
        "dll_exe_inventory": dlls,
        "library_categories": dict(library_categories),
        "domain_keyword_hits": domain_hits[:120],
        "embedded_resources": {
            "csproj_resource_includes": csproj_resources,
            "extracted_resource_files": embedded_resources,
            "extension_counts": dict(embedded_counts),
        },
        "certificates_seen": cert_ps_rows,
    }


def mdb_summary_for(path: Path) -> dict[str, Any]:
    exe = Path(os.environ.get("WINDIR", "C:/Windows")) / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if not exe.exists():
        exe = Path("powershell")
    ps = f"""
$ErrorActionPreference = 'Stop'
$path = '{str(path).replace("'", "''")}'
$providers = @('Microsoft.ACE.OLEDB.12.0','Microsoft.Jet.OLEDB.4.0')
$conn = $null
$providerUsed = $null
foreach ($provider in $providers) {{
  try {{
    $conn = New-Object System.Data.OleDb.OleDbConnection("Provider=$provider;Data Source=$path;Persist Security Info=False;")
    $conn.Open()
    $providerUsed = $provider
    break
  }} catch {{
    if ($conn) {{ $conn.Dispose() }}
    $conn = $null
  }}
}}
if (-not $conn) {{ throw "Nessun provider OLEDB disponibile" }}
$tables = @()
$schema = $conn.GetSchema('Tables')
foreach ($row in $schema.Rows) {{
  if ($row.TABLE_TYPE -ne 'TABLE') {{ continue }}
  $table = [string]$row.TABLE_NAME
  if ($table.StartsWith('MSys')) {{ continue }}
  $count = $null
  try {{
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = "SELECT COUNT(*) FROM [$table]"
    $count = [int]$cmd.ExecuteScalar()
  }} catch {{}}
  $colsSchema = $conn.GetSchema('Columns', @($null, $null, $table, $null))
  $cols = @()
  foreach ($col in $colsSchema.Rows) {{
    $cols += [string]$col.COLUMN_NAME
  }}
  $tables += [pscustomobject]@{{ name = $table; rows = $count; columns = $cols }}
}}
$conn.Close()
[pscustomobject]@{{ path = $path; provider = $providerUsed; table_count = $tables.Count; tables = $tables }} | ConvertTo-Json -Depth 6
"""
    data = powershell_json(ps, executable=str(exe))
    if isinstance(data, dict):
        return data
    return {"path": str(path), "error": "Formato inatteso da PowerShell"}


def collect_mdb_summary() -> dict[str, Any]:
    summaries = []
    for path in [QUICK_MDB, TEMPLATE_MDB]:
        if path.exists():
            summaries.append(mdb_summary_for(path))
        else:
            summaries.append({"path": str(path), "error": "file non trovato"})
    return {
        "generated_at": GENERATED_AT,
        "privacy": "Sono esportati solo conteggi, nomi tabella e colonne; nessun valore personale o credenziale.",
        "databases": summaries,
        "key_tables": ["PRATICHE", "TESTI", "EMAILS", "AGENDA", "TAVOLA", "Accounts"],
    }


def write_catalog_markdown(catalog: list[dict[str, Any]], macro_counts: Counter) -> Path:
    rows = []
    for item in catalog:
        rows.append(
            (
                item.get("macro", ""),
                item.get("categoria", ""),
                item.get("channel", ""),
                item.get("key", ""),
                item.get("text", ""),
                ", ".join(item.get("datiatto_methods", [])),
            )
        )
    lines = [
        "# Catalogo QuickOrganizer depositi telematici",
        "",
        f"Generato: {GENERATED_AT}.",
        "",
        "Questo file è il catalogo unico estratto da Studio Legale Telematico/QuickOrganizer. I file di settore sotto elencati sono più comodi per la consultazione quotidiana.",
        "",
        "## Conteggi macroaree",
        "",
        md_table([(macro, count) for macro, count in sorted(macro_counts.items())], ["Macroarea", "Tipi deposito"]),
        "",
        "## File di settore",
        "",
    ]
    for macro, filename in SECTOR_FILES.items():
        lines.append(f"- `{filename}` - {macro}.")
    lines.extend(
        [
            "",
            "## Catalogo completo",
            "",
            md_table(rows, ["Macroarea", "Categoria", "Canale", "Chiave schema", "Tipo deposito", "DatiAtto"]),
        ]
    )
    return write_utf8(ART / "catalogo-quickorganizer-depositi.md", "\n".join(lines))


def write_sector_catalogs(catalog: list[dict[str, Any]]) -> list[Path]:
    outputs: list[Path] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in catalog:
        grouped[item.get("macro", "")].append(item)
    for macro, filename in SECTOR_FILES.items():
        entries = grouped.get(macro, [])
        rows = [
            (
                item.get("categoria", ""),
                item.get("channel", ""),
                item.get("key", ""),
                item.get("text", ""),
                ", ".join(item.get("datiatto_methods", [])),
                ", ".join(root.get("type", "") for root in item.get("datiatto_roots", [])),
            )
            for item in entries
        ]
        lines = [
            f"# {macro}",
            "",
            f"Generato: {GENERATED_AT}.",
            "",
            f"Tipi deposito estratti: {len(entries)}.",
            "",
            "## Regola di integrazione IUSENTRA",
            "",
            "Nel flusso React `Prepara deposito`, il menu compatto deve mostrare macroarea, categoria e tipo. La scelta deve salvare la chiave schema, il canale e il metodo DatiAtto associato, non solo una descrizione testuale.",
            "",
            "## Voci",
            "",
            md_table(rows, ["Categoria", "Canale", "Chiave schema", "Tipo deposito", "Metodo DatiAtto", "Root XML"]),
        ]
        outputs.append(write_utf8(ART / filename, "\n".join(lines)))
    return outputs


def write_xsd_markdown(
    catalog: list[dict[str, Any]],
    namespace_manifest: list[dict[str, Any]],
    xml_namespace_counter: Counter,
    root_classes: list[dict[str, Any]],
    refs: dict[str, Any],
    create_methods: list[dict[str, Any]],
    key_to_methods: list[dict[str, Any]],
) -> Path:
    namespace_rows = [
        (namespace, count)
        for namespace, count in sorted(xml_namespace_counter.items(), key=lambda item: (-item[1], item[0]))[:80]
    ]
    method_rows = [
        (
            method["method"],
            method["line_start_estimate"],
            "sì" if method["uses_indice_busta"] else "no",
            "sì" if method["uses_contributo_unificato"] else "no",
            ", ".join(root.get("type", "") for root in method.get("saved_roots", [])),
        )
        for method in create_methods
    ]
    map_rows = [
        (
            item.get("key", ""),
            ", ".join(item.get("methods", [])),
            ", ".join(root.get("type", "") for root in item.get("saved_roots", [])),
        )
        for item in key_to_methods
    ]
    lines = [
        "# XSD e DatiAtto QuickOrganizer",
        "",
        f"Generato: {GENERATED_AT}.",
        "",
        "QuickOrganizer non distribuisce XSD sciolti nella cartella principale: le classi generate dagli XSD ministeriali sono embedded nel codice decompilato dell'EXE. Per IUSENTRA questo conferma che la mappa utile è: chiave deposito -> canale -> metodo `Create_DatiAtto_*` -> root XML -> validazioni richieste.",
        "",
        "## Fonti ufficiali da tenere collegate",
        "",
    ]
    for source in OFFICIAL_SOURCES:
        lines.append(f"- [{source['name']}]({source['url']}) - {source['note']}")
    lines.extend(
        [
            "",
            "## Namespace XML rilevati",
            "",
            md_table(namespace_rows, ["Namespace", "Riferimenti"]),
            "",
            "## Metodi Create_DatiAtto",
            "",
            md_table(method_rows, ["Metodo", "Linea stimata", "IndiceBusta", "Contributo", "Root salvato"]),
            "",
            "## Chiave deposito -> metodo DatiAtto",
            "",
            md_table(map_rows, ["Chiave schema", "Metodo", "Root XML"]),
            "",
            "## Pattern tecnici rilevati nei sorgenti",
            "",
            "- `DatiAtto.xml` viene generato per metodo specializzato e poi firmato.",
            "- `IndiceBusta` compare nelle classi ministeriali SICID/SIECIC/SIGP/UNEP e va confrontato con i file MIME fisici.",
            "- `Atto.enc` nasce dopo costruzione MIME, firma e cifratura CMS AES256.",
            "- Le specifiche ufficiali PST restano la fonte per decidere se uno schema embedded è ancora attuale.",
        ]
    )
    return write_utf8(ART / "xsd-quickorganizer-datiatto.md", "\n".join(lines))


def write_datiatto_generator_files(
    catalog: list[dict[str, Any]],
    create_methods: list[dict[str, Any]],
    key_to_methods: list[dict[str, Any]],
) -> list[Path]:
    outdir = ART / "quickorganizer-datiatto-generatori"
    outputs: list[Path] = []
    key_map = {item["key"]: item for item in key_to_methods}
    method_map = {item["method"]: item for item in create_methods}
    catalog_keys = {item.get("key", "") for item in catalog}
    sector_paths: list[Path] = []

    lines = [
        "# Generatori DatiAtto QuickOrganizer",
        "",
        f"Generato: {GENERATED_AT}.",
        "",
        "Questo indice separa la logica dei generatori dal catalogo visibile. Il JSON completo conserva tutti i campi estratti dal C# decompilato; i file per macroarea servono per lettura rapida.",
        "",
        "## Conteggi",
        "",
        md_table(
            [
                ("Tipi deposito nel catalogo Studio Telematico", len(catalog)),
                ("Case reali letti nello switch `AttoDaInviareKey`", len(key_to_methods)),
                ("Metodi `Create_DatiAtto_*` decompilati", len(create_methods)),
                ("Case non presenti nel catalogo UI estratto", len([item for item in key_to_methods if item["key"] not in catalog_keys])),
            ],
            ["Voce", "Totale"],
        ),
        "",
        "## File per macroarea",
        "",
    ]

    grouped_macro: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in catalog:
        grouped_macro[item.get("macro", "Da classificare")].append(item)

    for macro in sorted(grouped_macro):
        entries = grouped_macro[macro]
        filename = f"{slug_filename(macro)}.md"
        sector_paths.append(outdir / filename)
        lines.append(f"- `{rel(outdir / filename)}` - {macro}.")
        sector_lines = [
            f"# Generatori DatiAtto - {macro}",
            "",
            f"Generato: {GENERATED_AT}.",
            "",
            f"Tipi deposito nel settore: {len(entries)}.",
            "",
            "Ogni riga riporta il metodo esatto chiamato da Studio Telematico, la root XML salvata, i dati richiesti dal metodo e i campi/codici che il menu abilita.",
        ]
        grouped_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in entries:
            grouped_category[item.get("categoria", "Senza categoria")].append(item)
        for category in sorted(grouped_category):
            rows = []
            for item in sorted(grouped_category[category], key=lambda row: row.get("key", "")):
                methods = item.get("datiatto_methods", [])
                roots = [root.get("type", "") for root in item.get("datiatto_roots", [])]
                mapping = key_map.get(item.get("key", ""), {})
                fixed_codes = [
                    f"{code.get('code', '')} {code.get('label', '')}".strip()
                    for code in mapping.get("fixed_object_codes", [])
                ]
                true_flags = [key for key, value in mapping.get("flags", {}).items() if value]
                rows.append(
                    (
                        item.get("key", ""),
                        item.get("text", ""),
                        compact_join(methods, limit=3),
                        compact_join(roots, limit=3),
                        compact_join(item.get("datiatto_required_data", []), limit=8),
                        compact_join(fixed_codes, limit=2),
                        compact_join(true_flags, limit=6),
                    )
                )
            sector_lines.extend(
                [
                    "",
                    f"## {category}",
                    "",
                    md_table(
                        rows,
                        [
                            "Chiave",
                            "Tipo deposito",
                            "Metodo",
                            "Root XML",
                            "Dati richiesti",
                            "Codici oggetto fissi",
                            "Flag attivi",
                        ],
                    ),
                ]
            )
        outputs.append(write_utf8(outdir / filename, "\n".join(sector_lines)))

    uncatalogued = [item for item in key_to_methods if item["key"] not in catalog_keys]
    uncatalogued_rows = [
        (
            item.get("key", ""),
            compact_join(item.get("methods", []), limit=4),
            compact_join([root.get("type", "") for root in item.get("saved_roots", [])], limit=4),
            compact_join(item.get("required_data", []), limit=8),
        )
        for item in uncatalogued
    ]
    uncatalogued_path = outdir / "case-non-presenti-nel-catalogo-ui.md"
    lines.append(f"- `{rel(uncatalogued_path)}` - case dello switch non collegati al catalogo UI estratto.")
    outputs.append(
        write_utf8(
            uncatalogued_path,
            "\n".join(
                [
                    "# Case DatiAtto non presenti nel catalogo UI estratto",
                    "",
                    f"Generato: {GENERATED_AT}.",
                    "",
                    "Queste voci sono presenti nello switch decompilato `AttoDaInviareKey` ma non nel catalogo UI a 270 voci. Non vanno scartate: possono essere alias, varianti legacy o percorsi nascosti da integrare/riconciliare.",
                    "",
                    md_table(uncatalogued_rows, ["Chiave", "Metodo", "Root XML", "Dati richiesti"]),
                ]
            ),
        )
    )

    lines.extend(
        [
            "",
            "## Regola operativa",
            "",
            "- Per implementare un deposito in IUSENTRA non basta la root XML: bisogna usare anche dati richiesti, codici oggetto fissi, flag e controlli abilitati.",
            "- I campi completi e gli assignment C# sono nel JSON `quickorganizer-datiatto-generatori-campo-per-campo.json`.",
        ]
    )
    outputs.insert(0, write_utf8(outdir / "indice.md", "\n".join(lines)))
    return outputs


def write_menu_rules_files(
    catalog: list[dict[str, Any]],
    key_to_methods: list[dict[str, Any]],
) -> list[Path]:
    outdir = ART / "quickorganizer-regole-menu-deposito"
    outputs: list[Path] = []
    key_map = {item["key"]: item for item in key_to_methods}
    grouped_macro: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in catalog:
        grouped_macro[item.get("macro", "Da classificare")].append(item)

    index_lines = [
        "# Regole menu deposito Studio Telematico",
        "",
        f"Generato: {GENERATED_AT}.",
        "",
        "Questi file descrivono cosa Studio Telematico abilita o imposta quando si sceglie un tipo deposito: campi visibili, campi obbligatori, codici oggetto bloccati, combo istanze e flag operativi.",
        "",
    ]

    for macro in sorted(grouped_macro):
        filename = f"{slug_filename(macro)}.md"
        path = outdir / filename
        index_lines.append(f"- `{rel(path)}` - {macro}.")
        rows = []
        for item in sorted(grouped_macro[macro], key=lambda row: (row.get("categoria", ""), row.get("key", ""))):
            mapping = key_map.get(item.get("key", ""), {})
            controls = [
                f"{control.get('control')}: "
                + ", ".join(f"{key}={value}" for key, value in control.items() if key != "control")
                for control in mapping.get("controls", [])
            ]
            fixed_codes = [
                f"{code.get('code', '')} {code.get('label', '')}".strip()
                for code in mapping.get("fixed_object_codes", [])
            ]
            flags = [f"{key}={value}" for key, value in mapping.get("flags", {}).items()]
            rows.append(
                (
                    item.get("categoria", ""),
                    item.get("key", ""),
                    item.get("text", ""),
                    compact_join(flags, limit=8),
                    compact_join(fixed_codes, limit=3),
                    compact_join(mapping.get("combo_sources", []), limit=4),
                    compact_join(controls, limit=6),
                )
            )
        outputs.append(
            write_utf8(
                path,
                "\n".join(
                    [
                        f"# Regole menu deposito - {macro}",
                        "",
                        f"Generato: {GENERATED_AT}.",
                        "",
                        md_table(
                            rows,
                            [
                                "Categoria",
                                "Chiave",
                                "Tipo deposito",
                                "Flag",
                                "Codici oggetto fissi",
                                "Combo/istanze",
                                "Controlli UI",
                            ],
                        ),
                    ]
                ),
            )
        )

    outputs.insert(0, write_utf8(outdir / "indice.md", "\n".join(index_lines)))
    return outputs


def write_busta_contract_files(
    catalog: list[dict[str, Any]],
    create_methods: list[dict[str, Any]],
    key_to_methods: list[dict[str, Any]],
    refs: dict[str, Any],
) -> list[Path]:
    outdir = ART / "quickorganizer-generatore-busta"
    outputs: list[Path] = []
    method_map = {item["method"]: item for item in create_methods}
    key_map = {item["key"]: item for item in key_to_methods}

    rows = []
    for item in catalog:
        mapping = key_map.get(item.get("key", ""), {})
        contracts: list[str] = []
        for method_name in mapping.get("methods", []):
            contracts.extend(method_map.get(method_name, {}).get("busta_contract", []))
        rows.append(
            (
                item.get("macro", ""),
                item.get("key", ""),
                item.get("text", ""),
                compact_join(mapping.get("methods", []), limit=3),
                compact_join([root.get("type", "") for root in mapping.get("saved_roots", [])], limit=3),
                compact_join(_compact_strings(contracts, limit=20), limit=8),
            )
        )

    transport_hits = refs.get("source_hits", {})
    transport_rows = []
    for term in ["Atto.enc", "IndiceBusta", "DatiAtto", "MailBee", "SignLib", "AES256", "CAdES", "PAdES", "getCertificato"]:
        for hit in transport_hits.get(term, [])[:8]:
            transport_rows.append((term, hit.get("file", ""), hit.get("line", ""), hit.get("text", "")))

    index_lines = [
        "# Generatore busta Studio Telematico",
        "",
        f"Generato: {GENERATED_AT}.",
        "",
        "Questo file raccoglie i dati necessari a trasformare la scelta deposito in busta tecnica: `DatiAtto.xml`, `IndiceBusta`, riferimenti agli allegati, firma, `Atto.msg`, `Atto.enc`, PEC e ricevute.",
        "",
        "## Contratto operativo da portare in IUSENTRA",
        "",
        "- Ogni `DatiAtto.xml` generato deve contenere `IndiceBusta.AttoPrincipale.id` coerente con il documento principale.",
        "- Gli allegati fisici devono comparire in `IndiceBusta.Any` con gli stessi ID/nomi poi presenti nel MIME `Atto.msg`.",
        "- Se Studio Telematico crea buste complementari, il `RefId` collega le buste del medesimo deposito.",
        "- Prima dell'invio reale `DatiAtto.xml` va firmato CAdES come `DatiAtto.xml.p7m`.",
        "- `Atto.msg` deve contenere le parti MIME previste: atto principale, allegati, `DatiAtto.xml.p7m`, indice e documenti di accompagnamento.",
        "- `Atto.enc` è il risultato della cifratura CMS/PKCS#7 con certificato pubblico dell'ufficio destinatario; non è un semplice file zip o base64.",
        "- L'invio PEC operativo resta dal PC locale dell'avvocato, con presidio ricevute di accettazione, consegna ed esito controlli automatici.",
        "",
        "## Matrice deposito -> contratto busta",
        "",
        md_table(rows, ["Macroarea", "Chiave", "Tipo deposito", "Metodo", "Root XML", "Contratto busta"]),
        "",
        "## Riferimenti sorgente rilevati",
        "",
        md_table(transport_rows, ["Tema", "File", "Linea", "Estratto"]),
    ]
    outputs.append(write_utf8(outdir / "contratto-generatore-busta.md", "\n".join(index_lines)))
    return outputs


def write_logic_markdown(refs: dict[str, Any], comparison: dict[str, Any]) -> Path:
    lines = [
        "# Logica Studio Legale Telematico",
        "",
        f"Generato: {GENERATED_AT}.",
        "",
        "## Flusso deposito ricostruito",
        "",
        "1. L'albero schema propone macroarea, categoria e tipo deposito.",
        "2. La scelta imposta una chiave tecnica come `Introduttivi_SICID::Citazione` o `Atti_UNEP::Pignoramento`.",
        "3. `QualeTipologiaDeposito` e `FindSchemaXSD` decidono campi, validazioni e generatore `DatiAtto.xml`.",
        "4. La busta viene preparata con atto principale, allegati, `DatiAtto.xml`, indice documenti e riferimenti MIME.",
        "5. I documenti richiesti vengono firmati, `DatiAtto.xml` viene firmato CAdES, il messaggio viene cifrato con il certificato dell'ufficio e nasce `Atto.enc`.",
        "6. L'invio PEC usa MailBee dal PC locale configurato, non un canale server remoto.",
        "",
        "## Regole che conviene portare in IUSENTRA",
        "",
        "- Il selettore deposito non deve essere una lista piatta: deve portare con sé canale, schema, codice oggetto, validazioni e documenti obbligatori.",
        "- Gli introduttivi esecuzioni impostano codici oggetto fissi per pignoramento mobiliare presso debitore, mobiliare presso terzi e immobiliare.",
        "- Cassazione, SIGP e UNEP hanno campi speciali: ruolo difensore, motivi, registro, urgenza, natura atto, date specifiche.",
        "- Gli allegati `EML`, `MSG`, `P7M` e `XML` hanno comportamento firma diverso dai PDF/documenti ordinari.",
        "- I depositi complementari vengono raggruppati e marcati con soggetto PEC dedicato.",
        "",
        "## Riferimenti soggetto PEC/ricevute",
        "",
    ]
    prefixes = refs.get("subject_prefixes", [])
    for prefix in prefixes[:60]:
        lines.append(f"- `{prefix}`")
    lines.extend(
        [
            "",
            "## Differenze note rispetto a IUSENTRA",
            "",
            f"- QuickOrganizer cataloga {comparison['object_compare']['quick_leaf_codes']} codici oggetto foglia; IUSENTRA ne ha {comparison['object_compare']['ius_records']} da catalogo PST/XSD.",
            f"- Codici QuickOrganizer non presenti in IUSENTRA: {', '.join(comparison['object_compare']['missing_in_iusentra']) or 'nessuno'}.",
            "- IUSENTRA deve mantenere la propria fonte ufficiale XSD più ampia e usare QuickOrganizer come confronto comportamentale, non come fonte normativa unica.",
        ]
    )
    return write_utf8(ART / "quickorganizer-logica-studio-telematico.md", "\n".join(lines))


def write_firma_pin_markdown(refs: dict[str, Any]) -> Path:
    lines = [
        "# Firma digitale, PIN e sessioni QuickOrganizer",
        "",
        f"Generato: {GENERATED_AT}.",
        "",
        "## Cosa emerge",
        "",
        "- La sessione firma ruota attorno a `QualifiedCertificate` e a variabili statiche di lavoro come `PCT.QualifiedCertificate` e `PCT.pin`.",
        "- Il PIN risulta usato come dato di sessione/processo per firmare e autenticarsi, non come valore da salvare nel database.",
        "- Il certificato qualificato viene distinto dal certificato di autenticazione web tramite OID/estensioni.",
        "- Le chiamate ai servizi PST/portali usano il certificato web quando richiesto; il deposito usa firma CAdES e cifratura separata.",
        "",
        "## Trasferimento in IUSENTRA",
        "",
        "- Local Signer deve continuare a chiedere il PIN al momento dell'operazione e tenerlo solo in memoria di sessione strettamente necessaria.",
        "- La firma multipla deve firmare più documenti nella stessa operazione, salvare ogni esito e non derivare mai `Firmato` da nome file o testo.",
        "- Per portali/PST va separato il certificato di autenticazione dal certificato di firma e dal certificato pubblico dell'ufficio.",
        "- Ogni errore PIN/certificato deve bloccare il solo passaggio obbligatorio e lasciare audit comprensibile nel fascicolo.",
        "",
        "## Sorgenti decompilati da rileggere",
        "",
        "- `QuickOrganizer/QualifiedCertificate.cs`",
        "- `QuickOrganizer/PCT.cs`",
        "- `FormSentMailBee.cs`",
    ]
    for term in ["QualifiedCertificate", "pin", "CAdES", "PAdES", "pkcs"]:
        hits = refs.get("source_hits", {}).get(term, [])
        if hits:
            lines.extend(["", f"### Hit `{term}`", ""])
            for hit in hits[:8]:
                lines.append(f"- `{hit['file']}:{hit['line']}` - `{hit['text']}`")
    return write_utf8(ART / "quickorganizer-firma-pin-sessioni.md", "\n".join(lines))


def write_pec_notifiche_markdown(refs: dict[str, Any]) -> Path:
    lines = [
        "# PEC, notifiche e ricevute QuickOrganizer",
        "",
        f"Generato: {GENERATED_AT}.",
        "",
        "## Cosa serve a IUSENTRA",
        "",
        "- Presidio PEC deve normalizzare i soggetti di deposito, accettazione, consegna, controlli automatici, esiti cancelleria e copie non crittografate.",
        "- Notifiche L. 53 vanno tenute distinte dai depositi: generano relata, soggetto PEC dedicato, ricevute e collegamento documentale autonomo.",
        "- La ricerca fascicoli di QuickOrganizer usa `EMAILS.NumeroPratica`, `Controllo`, `Subject`, allegati e stato cancellato per separare ricevute, inviate, depositi e notifiche.",
        "- In IUSENTRA questi segnali devono alimentare fascicolo, agenda, scadenziario, notifiche interne e Web Push senza invio PEC server-side.",
        "",
        "## Prefissi oggetto da presidiare",
        "",
    ]
    for prefix in refs.get("subject_prefixes", [])[:90]:
        lines.append(f"- `{prefix}`")
    lines.extend(
        [
            "",
            "## Azioni IUSENTRA",
            "",
            "- Ampliare `pct/pec_legal_workflow.py::normalizza_oggetto_pec` con i prefissi QuickOrganizer utili.",
            "- Indicizzare ogni ricevuta PEC su fascicolo, documento, tipo evento, data italiana `Europe/Rome`, stato e origine.",
            "- Collegare esiti deposito/notifica ad agenda e scadenziario solo dopo classificazione certa del messaggio.",
            "- Conservare la regola già blindata: l'invio operativo PEC legale parte dal PC locale tramite Local Signer/servizio locale.",
        ]
    )
    return write_utf8(ART / "quickorganizer-pec-notifiche-ricevute.md", "\n".join(lines))


def write_portali_markdown(refs: dict[str, Any]) -> Path:
    lines = [
        "# Portali, PolisWeb e download fascicoli QuickOrganizer",
        "",
        f"Generato: {GENERATED_AT}.",
        "",
        "## Componenti rilevati",
        "",
        "- `BrowserForm.cs` usa WebView2, profilo utente locale e gestione eventi browser.",
        "- `WizardImportaPraticheDaPolisWeb.cs` orchestra ricerca, consultazione e download documenti.",
        "- `WebView2.DevTools.Dom.dll` e `Microsoft.Web.WebView2.*` indicano automazione DOM/portale dentro browser embedded.",
        "- La cartella `QuickOrganizer.exe.WebView2` è runtime/cache browser, da non confondere con logica applicativa primaria.",
        "",
        "## URL e portali rilevati nei sorgenti",
        "",
    ]
    for url in refs.get("urls", [])[:80]:
        lines.append(f"- {url}")
    lines.extend(
        [
            "",
            "## Artefatti collegati",
            "",
            "- `quickorganizer-registri-consultazione-fascicoli.md` contiene registri, alias IUSENTRA, ruoli e servizi JPW/URN.",
            "- `quickorganizer-portale-lettura-download-fascicolo.md` contiene menu `Importa Pratiche dal PolisWeb`, `Accesso al PolisWeb...`, download singolo/intero fascicolo e ricerca per anno.",
            "",
            "## Trasferimento in IUSENTRA",
            "",
            "- Tenere portali come connettori governati: autenticazione con certificato, ricerca fascicoli, download documenti, audit e salvataggio in SQL tenant-aware.",
            "- Non mischiare scraping portale con deposito valido: i download alimentano fascicolo e prove, l'invio resta nel flusso deposito/PEC.",
            "- Ogni import deve registrare origine portale, ufficio, RG, ruolo, documento scaricato, hash, data italiana e collegamento a fascicolo.",
        ]
    )
    return write_utf8(ART / "quickorganizer-portali-polisweb-download.md", "\n".join(lines))


def write_registry_download_markdown(registry_catalog: dict[str, Any]) -> Path:
    records = registry_catalog.get("records", [])
    service_counts = registry_catalog.get("service_counts", {})
    service_rows = list(service_counts.items())[:40]
    registry_rows = [
        (
            item.get("service_code_xml", ""),
            item.get("application_code_xml", ""),
            item.get("registry_code_xml", ""),
            item.get("registry_description_xml", ""),
            item.get("office_count", ""),
            item.get("quick_target_path", ""),
            item.get("logical_service_iusentra", ""),
            item.get("urn", ""),
            ", ".join(item.get("allowed_roles", [])),
            item.get("notes", ""),
        )
        for item in records
    ]
    sample_rows = []
    for item in records:
        for office in item.get("sample_offices", [])[:2]:
            sample_rows.append(
                (
                    item.get("registry_code_xml", ""),
                    office.get("codiceUfficio", ""),
                    office.get("descrizione", ""),
                    office.get("tipoUfficio", ""),
                    office.get("pec", ""),
                )
            )
    lines = [
        "# Registri consultazione fascicoli QuickOrganizer",
        "",
        f"Generato: {GENERATED_AT}.",
        "",
        "Questo file risponde al perimetro richiesto: civile ordinario SICID/RGN, lavoro SIL/LAV, volontaria giurisdizione SIVG/VG, minorenni MIN/SIMIN, esecuzioni e concorsuali SIECIC, Giudice di Pace SIGP/GDP, Cassazione civile CASSCI, Cassazione penale CASSPE e registri ulteriori trovati.",
        "",
        "## Sintesi",
        "",
        "- QuickOrganizer legge i registri disponibili da `C:/QuickOrganizer/ListaUfficiGiudiziari.xml` e li incrocia con logica runtime in `Common.cs` e `WizardImportaPraticheDaPolisWeb.cs`.",
        "- Per il civile ordinario QuickOrganizer usa registro `CC`; `RGN/RNG` sono alias/tipo numero ruolo da normalizzare in IUSENTRA.",
        "- Per Giudice di Pace il XML espone `GDP`, mentre alcune parti del codice storico usano `GP`: IUSENTRA deve accettare entrambi.",
        "- Per lavoro, volontaria giurisdizione e minorenni QuickOrganizer passa spesso dal target `JPW_SICID`, ma con URN dedicati `CONS-SIL-BE`, `CONS-SIVG-BE`, `CONS-MIN-BE`.",
        "- `Agrarie` e `Speciali` risultano tipi/filtro locali QuickOrganizer: non ho trovato una combinazione JPW autonoma nel catalogo XML.",
        "",
        "## Conteggio servizi nel catalogo uffici",
        "",
        md_table(service_rows, ["Servizio", "Righe ufficio"]),
        "",
        "## Registri e mapping operativo",
        "",
        md_table(
            registry_rows,
            [
                "Servizio XML",
                "Applicazione",
                "Registro XML",
                "Descrizione",
                "Uffici",
                "Target Quick",
                "Servizio IUSENTRA",
                "URN",
                "Ruoli",
                "Note",
            ],
        ),
        "",
        "## Campione uffici",
        "",
        md_table(sample_rows[:120], ["Registro", "Codice ufficio", "Ufficio", "Tipo", "PEC"]),
        "",
        "## Regole per IUSENTRA",
        "",
        "- La ricerca fascicolo deve salvare sempre registro normalizzato, alias mostrato, servizio JPW, ufficio, ruolo e anno.",
        "- La ricerca per anno non è un filtro testuale: deve diventare parametro governato del servizio o del portale, con `numero=0` quando previsto.",
        "- Per SIECIC non inventare `idRuoloJPW` o `idDfa`: se mancano, bloccare solo quel dettaglio con motivo puntuale.",
        "- Le aree Cassazione civile e penale vanno tenute separate: `CASSCI` e `CASSPE` hanno URL/servizi distinti.",
    ]
    return write_utf8(ART / "quickorganizer-registri-consultazione-fascicoli.md", "\n".join(lines))


def write_portal_download_flow_markdown(download_flow: dict[str, Any]) -> Path:
    menu = download_flow.get("studio_telematico_menu", {})
    commands = menu.get("commands", [])
    command_rows = [
        (
            item.get("caption", ""),
            item.get("key", ""),
            item.get("kind", ""),
            item.get("launcher", ""),
            item.get("behavior", ""),
        )
        for item in commands
    ]
    url_matrix = download_flow.get("portal_url_matrix", {})
    suffix_rows = [
        (item.get("function", ""), item.get("suffix", ""))
        for item in url_matrix.get("function_suffixes", [])
    ]
    registry_rows = [
        (
            item.get("registry", ""),
            item.get("description", ""),
            item.get("area", ""),
            item.get("registroRicerca", item.get("registry", "")),
        )
        for item in url_matrix.get("registry_paths", [])
    ]
    cass_rows = [
        (item.get("registry", ""), item.get("url", ""))
        for item in url_matrix.get("cassazione", [])
    ]
    flow_rows = [
        (item.get("step", ""), item.get("name", ""), item.get("details", ""))
        for item in download_flow.get("fascicolo_flow", [])
    ]
    search_rows = [
        (
            item.get("mode", ""),
            item.get("quick_behavior", ""),
            ", ".join(item.get("methods", [])),
            ", ".join(item.get("payload_fields", [])),
        )
        for item in download_flow.get("search_modes", [])
    ]
    download_rows = [
        (
            item.get("label", ""),
            item.get("duplicato", ""),
            item.get("original", ""),
            item.get("effect", ""),
        )
        for item in download_flow.get("download_options", [])
    ]
    save_rows = [
        (item.get("target", ""), item.get("behavior", ""))
        for item in download_flow.get("browser_download_handler", {}).get("save_targets", [])
    ]
    lines = [
        "# Accesso PolisWeb, lettura fascicolo e download QuickOrganizer",
        "",
        f"Generato: {GENERATED_AT}.",
        "",
        "Questo file separa i due comportamenti che in Studio Telematico convivono nello stesso menu: import/sincronizzazione dati tramite wizard e accesso diretto assistito al portale PST tramite browser WebView2.",
        "",
        "## Menu Studio Telematico",
        "",
        f"Menu principale rilevato: `{menu.get('access_menu_caption', 'Accesso al PolisWeb...')}`.",
        "",
        md_table(command_rows, ["Voce", "Key", "Tipo", "Launcher", "Comportamento"]),
        "",
        "## URL portale PST per accesso diretto",
        "",
        "QuickOrganizer costruisce URL con `registroRicerca`, `ufficioRicerca` e `ruoloRicerca={ruolo}@{ruolo}`. La base è `https://servizipst.giustizia.it/PST/it/`.",
        "",
        md_table(registry_rows, ["Registro", "Descrizione", "Area PST", "registroRicerca"]),
        "",
        "### Suffissi funzione",
        "",
        md_table(suffix_rows, ["Funzione", "Suffisso URL"]),
        "",
        "### Cassazione",
        "",
        md_table(cass_rows, ["Registro", "URL"]),
        "",
        "## Lettura fascicolo dal portale",
        "",
        "- Le voci `Fascicolo d'ufficio`, `Eventi`, `Documenti` e `Notifiche` partono dalla pratica selezionata e chiamano `RecuperaDatiFascicoloUfficio(..., showBrowser:true)`.",
        "- Quando la pagina contiene `_infofascicolo`, `BrowserForm` seleziona la scheda cercando link con `storicofascicolo`, `documentifascicolo` o `comunicazionifascicolo`.",
        "- Questo è accesso portale assistito: richiede sessione PST/certificato dell'utente e va verificato in browser reale prima di copiarlo come flusso automatico.",
        "",
        "## Ricerca fascicolo e ricerca per anno",
        "",
        md_table(search_rows, ["Modo", "Comportamento QuickOrganizer", "Metodi", "Campi payload"]),
        "",
        "## Scarico singolo documento e intero fascicolo",
        "",
        md_table(flow_rows, ["Passo", "Nome", "Dettaglio"]),
        "",
        "Interpretazione: non è emerso un endpoint unico `scarica intero fascicolo`. Studio Telematico scarica l'intero fascicolo come batch di download singoli, iterando documenti e allegati selezionati.",
        "",
        "## Opzioni download servizi",
        "",
        md_table(download_rows, ["Opzione", "Duplicato", "Original", "Effetto"]),
        "",
        "## Download intercettato dal browser",
        "",
        f"- Evento: `{download_flow.get('browser_download_handler', {}).get('webview2_event', '')}`.",
        f"- Estensioni/pattern ammessi: {', '.join(download_flow.get('browser_download_handler', {}).get('accepted_extensions_or_patterns', []))}.",
        f"- Gestione `.p7m`: {download_flow.get('browser_download_handler', {}).get('p7m_handling', '')}",
        "",
        md_table(save_rows, ["Destinazione", "Comportamento"]),
        "",
        "## Regole per IUSENTRA",
        "",
        "- Creare due azioni distinte: `Importa/sincronizza da PolisWeb` e `Accedi al PolisWeb`.",
        "- `Scarica intero fascicolo` deve essere batch governato di documenti singoli, con progress, deduplica per `idCat/IdDocumento/hash` e ripresa su errore.",
        "- Ogni documento deve salvare tenant, fascicolo, ufficio, registro, ruolo, origine portale, id documento, hash, data italiana e stato download.",
        "- Lo scarico via portale non deve diventare prova di deposito o notifica: alimenta fascicolo, agenda, scadenziario e presidio PEC come origine documentale.",
    ]
    return write_utf8(ART / "quickorganizer-portale-lettura-download-fascicolo.md", "\n".join(lines))


def write_certificate_code_markdown(comparison: dict[str, Any]) -> Path:
    cert = comparison["certificate_compare"]
    obj = comparison["object_compare"]
    rows_missing = [
        (
            item.get("codiceUfficio", ""),
            item.get("tipoUfficio", ""),
            item.get("descrizione", ""),
            item.get("cert", ""),
            ", ".join(item.get("servizi", [])),
        )
        for item in cert.get("missing_with_services", [])[:80]
    ]
    rows_diffs = [
        (item["codice"], item["quickorganizer"], item["iusentra"])
        for item in obj.get("label_diffs_sample", [])[:60]
    ]
    lines = [
        "# Confronto certificati uffici e codici oggetto",
        "",
        f"Generato: {GENERATED_AT}.",
        "",
        "## Certificati uffici",
        "",
        f"- QuickOrganizer XML: {comparison['quickorganizer']['cert_names_in_xml']} nomi certificato, {comparison['quickorganizer']['cert_codes_in_xml']} codici certificato.",
        f"- QuickOrganizer file locali `.cer`: {len(comparison['quickorganizer']['local_cer_files'])} ({', '.join(comparison['quickorganizer']['local_cer_files']) or 'nessuno'}).",
        f"- IUSENTRA cache `.cer`: {comparison['iusentra']['cert_files']} file, {comparison['iusentra']['cert_codes']} codici.",
        f"- Codici comuni: {cert['common_by_code']}.",
        f"- Codici QuickOrganizer mancanti in IUSENTRA per confronto grezzo: {cert['missing_by_code']}.",
        f"- Tipologie mancanti nel confronto grezzo: {json.dumps(cert['missing_by_type'], ensure_ascii=False)}.",
        "",
        "Interpretazione: QuickOrganizer non contiene tutti i certificati pubblici degli uffici dentro l'EXE o nella cartella `Certificati`; usa `ListaUfficiGiudiziari.xml`/`QC_Uffici.xml` e scarica il certificato dell'ufficio quando deve cifrare. IUSENTRA, invece, ha una cache PST più ampia e un audit operativo già impostato per codici attivi.",
        "",
        "## Righe mancanti con servizi telematici",
        "",
        md_table(rows_missing, ["Codice ufficio", "Tipo", "Descrizione", "Certificato", "Servizi"]) if rows_missing else "Nessuna riga mancante con servizi telematici nel campione QuickOrganizer.",
        "",
        "## Codici oggetto deposito/pratica",
        "",
        f"- QuickOrganizer foglie con codice: {obj['quick_leaf_codes']}.",
        f"- IUSENTRA catalogo PST/XSD: {obj['ius_records']}.",
        f"- Codici comuni: {obj['common']}.",
        f"- Codici QuickOrganizer non presenti in IUSENTRA: {', '.join(obj['missing_in_iusentra']) or 'nessuno'}.",
        f"- Codici IUSENTRA in più rispetto a QuickOrganizer: {obj['extra_in_iusentra']}.",
        f"- Descrizioni diverse dopo normalizzazione semplice: {obj['label_diffs_count']}.",
        "",
        "## Campione differenze descrizione",
        "",
        md_table(rows_diffs, ["Codice", "QuickOrganizer", "IUSENTRA"]),
        "",
        "## Regola operativa",
        "",
        "Il confronto con QuickOrganizer serve a scoprire comportamenti e lacune, ma IUSENTRA deve restare agganciato al catalogo PST/XSD ufficiale più recente. I sei codici mancanti vanno trattati come watchlist da verificare su XSD/fonti ufficiali prima di inserirli come depositabili.",
    ]
    return write_utf8(ART / "quickorganizer-confronto-certificati-codici.md", "\n".join(lines))


def write_resources_markdown(resources: dict[str, Any]) -> Path:
    categories = resources.get("library_categories", {})
    cat_rows = sorted(categories.items(), key=lambda item: (-item[1], item[0]))
    interesting = [
        row
        for row in resources.get("dll_exe_inventory", [])
        if row.get("category") not in {"framework .NET", "UI WinForms/Infragistics", "runtime WebView2"}
    ]
    lib_rows = [
        (
            row.get("name", ""),
            row.get("category", ""),
            row.get("file_version", ""),
            row.get("company", ""),
            "sì" if row.get("managed") else "no",
            ", ".join(row.get("references", [])[:8]),
        )
        for row in interesting[:120]
    ]
    hit_rows = [
        (
            item.get("path", ""),
            item.get("bytes", ""),
            ", ".join(f"{k}:{v}" for k, v in item.get("hits", {}).items()),
        )
        for item in resources.get("domain_keyword_hits", [])[:80]
    ]
    embedded = resources.get("embedded_resources", {})
    embedded_rows = [
        (item.get("name", ""), item.get("extension", ""), item.get("bytes", ""), item.get("sha256", "")[:16])
        for item in embedded.get("extracted_resource_files", [])[:120]
    ]
    cert_rows = [
        (
            item.get("path", ""),
            item.get("subject", item.get("error", "")),
            item.get("issuer", ""),
            item.get("not_after", ""),
            item.get("thumbprint", ""),
        )
        for item in resources.get("certificates_seen", [])
    ]
    lines = [
        "# DLL, risorse embedded e sottocartelle QuickOrganizer",
        "",
        f"Generato: {GENERATED_AT}.",
        "",
        "## Conteggio file",
        "",
        f"- File totali sotto `C:/QuickOrganizer`: {resources['file_counts']['total_files']}.",
        f"- File senza cache/runtime WebView2: {resources['file_counts']['without_webview2']}.",
        "",
        "## Categorie DLL/EXE",
        "",
        md_table(cat_rows, ["Categoria", "File"]),
        "",
        "## Librerie utili al confronto",
        "",
        md_table(lib_rows, ["File", "Categoria", "Versione", "Società", "Managed", "Riferimenti principali"]),
        "",
        "## Hit tecnici in EXE/DLL/config/XML",
        "",
        md_table(hit_rows, ["File", "Byte", "Keyword rilevate"]),
        "",
        "## Risorse embedded estratte dall'EXE",
        "",
        md_table(embedded_rows, ["Risorsa", "Estensione", "Byte", "SHA256 breve"]),
        "",
        "## Certificati visti su disco/embedded",
        "",
        md_table(cert_rows, ["Path", "Subject/errore", "Issuer", "Scadenza", "Thumbprint"]),
        "",
        "## Lettura tecnica",
        "",
        "- `MailBee.NET.dll` è la libreria operativa per email/PEC.",
        "- `SignLib.dll` e `System.Security.Cryptography.Pkcs.dll` sono segnali chiari per firma/cifratura CMS.",
        "- `Microsoft.Web.WebView2.*` e `WebView2.DevTools.Dom.dll` sono collegati a portali, PolisWeb e automazione browser.",
        "- `TXTextControl` e relativi moduli servono a editor, PDF/RTF/DOC e documenti.",
        "- `Infragistics` governa griglie, tree e UI desktop, utile per replicare un menu deposito compatto in React senza copiare la UI.",
        "- La cartella WebView2 è grande ma per IUSENTRA conta come runtime/cache, non come fonte primaria di regole ministeriali.",
    ]
    return write_utf8(ART / "quickorganizer-risorse-dll-sottocartelle.md", "\n".join(lines))


def write_mdb_markdown(summary: dict[str, Any]) -> Path:
    lines = [
        "# Database QuickOrganizer: fascicoli, PEC, agenda e documenti",
        "",
        f"Generato: {GENERATED_AT}.",
        "",
        "Questo report esporta solo struttura, conteggi e colonne. Non contiene valori personali, password PEC o contenuti dei fascicoli.",
        "",
    ]
    for db in summary.get("databases", []):
        lines.extend(
            [
                f"## {db.get('path', '')}",
                "",
            ]
        )
        if db.get("error"):
            lines.extend([f"Errore lettura: `{db['error']}`", ""])
            continue
        lines.extend(
            [
                f"- Provider: `{db.get('provider', '')}`.",
                f"- Tabelle: {db.get('table_count', 0)}.",
                "",
                "### Conteggi tabelle",
                "",
                md_table(
                    [(table.get("name", ""), table.get("rows", "")) for table in db.get("tables", [])],
                    ["Tabella", "Righe"],
                ),
                "",
                "### Tabelle chiave",
                "",
            ]
        )
        for table_name in summary.get("key_tables", []):
            table = next((item for item in db.get("tables", []) if item.get("name") == table_name), None)
            if not table:
                continue
            lines.extend(
                [
                    f"#### {table_name}",
                    "",
                    f"Righe: {table.get('rows', '')}.",
                    "",
                    "`" + "`, `".join(table.get("columns", [])) + "`",
                    "",
                ]
            )
    lines.extend(
        [
            "## Implicazioni per IUSENTRA",
            "",
            "- Ricerca fascicoli: indicizzare insieme anagrafica fascicolo, RG, oggetto, autorità, parti, documenti, PEC e agenda.",
            "- Download fascicoli: salvare origine portale/PolisWeb, documento, hash, fascicolo, ufficio, RG e data italiana.",
            "- Presidio PEC: collegare messaggio, allegati, ricevute, esiti cancelleria, notifica L. 53 e deposito.",
            "- Agenda/scadenziario/notifiche: usare gli eventi PEC e portale come sorgenti governate, non come testo libero.",
            "- Password/account: non importare credenziali storiche; mantenere il modello IUSENTRA con invio operativo dal PC locale.",
        ]
    )
    return write_utf8(ART / "quickorganizer-database-fascicoli-pec.md", "\n".join(lines))


def write_work_markdown(
    comparison: dict[str, Any],
    resources: dict[str, Any],
    mdb: dict[str, Any],
    registry_catalog: dict[str, Any],
    download_flow: dict[str, Any],
) -> Path:
    registry_records = registry_catalog.get("records", [])
    menu_commands = download_flow.get("studio_telematico_menu", {}).get("commands", [])
    lines = [
        "# Lavoro IUSENTRA da aggiungere dopo analisi QuickOrganizer",
        "",
        f"Generato: {GENERATED_AT}.",
        "",
        "## Obiettivo",
        "",
        "Specializzare IUSENTRA mantenendo blindato ciò che è già stato provato realmente: cache certificati PST, accettazione cancelleria, invio PEC dal PC locale, deposito React e controlli anti-regressione.",
        "",
        "## Deposito telematico React",
        "",
        "- Aggiungere repository catalogo deposito con 270 tipi QuickOrganizer come confronto e con fonte ufficiale PST/XSD come autorità normativa.",
        "- Nel passo `2. Documenti da inviare`, aggiungere menu compatto macroarea/categoria/tipo simile a QuickOrganizer.",
        "- Alla scelta salvare `schema_key`, `channel`, `datiatto_methods`, root XML, codice oggetto proposto, documenti obbligatori e validazioni.",
        "- Rendere visibili i requisiti bloccanti puntuali quando `Invia deposito reale` resta disabilitato.",
        "- Non toccare la prova reale già blindata di accettazione cancelleria se non con test mirati e nuova prova reale.",
        "",
        "## XSD e busta",
        "",
        "- Creare mappa IUSENTRA `schema_key -> generator -> root XML -> IndiceBusta -> document rules`.",
        "- Verificare ogni generatore contro XSD ufficiali PST aggiornati, incluse rettifiche DGSIA e news 2026.",
        "- Controllare `DatiAtto.xml.p7m`, `IndiceBusta.xml`, `IndiceDocumentiDepositati.PDF`, Content-ID MIME e `Atto.enc` CMS AES256.",
        "",
        "## Firma/PIN/Local Signer",
        "",
        "- Allineare firma multipla alla logica sessione: PIN solo in memoria, firma più file, salvataggio esito per documento.",
        "- Separare certificato firma, certificato autenticazione portali e certificato pubblico ufficio.",
        "- Auditare errori PIN/certificato senza fallback silenziosi.",
        "",
        "## PEC, notifiche e ricevute",
        "",
        "- Estendere normalizzazione oggetti PEC con prefissi QuickOrganizer.",
        "- Collegare ricevute ad agenda, scadenziario, notifiche interne e Web Push solo dopo classificazione certa.",
        "- Tenere notifiche L. 53 separate dal deposito PCT, con relata firmata quando richiesta e prova senza invio reale.",
        "",
        "## Ricerca fascicoli e download",
        "",
        "- Migliorare ricerca globale fascicoli con segnali equivalenti a `PRATICHE`, `TESTI`, `EMAILS`, `AGENDA`, `TAVOLA`.",
        "- Indicizzare RG, anno, ufficio, oggetto, parti, documenti, PEC, ricevute, notifiche e scadenze.",
        "- Per portali/PolisWeb salvare origine, hash, ufficio, data italiana, ruolo e fascicolo tenant-aware.",
        f"- Integrare la mappa registri consultazione: {len(registry_records)} combinazioni/alias registrate in `quickorganizer-registri-consultazione-fascicoli.md`.",
        f"- Replicare in React le azioni operative rilevate nel menu `Accesso al PolisWeb...`: {len(menu_commands)} comandi distinti tra wizard, fascicolo d'ufficio, agenda, scadenze, documenti, Cassazione e notifiche.",
        "- Separare `Importa Pratiche dal PolisWeb` da `Accesso al PolisWeb`: il primo sincronizza dati tramite wizard/servizi, il secondo apre il portale PST assistito con WebView2 e intercetta download.",
        "- Aggiungere ricerca fascicolo per anno come parametro governato: quando manca il numero ruolo usare `numero=0` solo sui registri/metodi che lo prevedono.",
        "- Implementare `Scarica intero fascicolo` come batch di scarichi singoli con deduplica `idCat/IdDocumento/hash`, progress, ripresa su errore e salvataggio SQL tenant-aware.",
        "",
        "## Certificati e codici",
        "",
        f"- Audit IUSENTRA certificati: {comparison['iusentra'].get('audit', {}).get('catalogo_pct_operativi', 'n/d')} operativi, {comparison['iusentra'].get('audit', {}).get('scaricati_o_validi', 'n/d')} coperti secondo audit locale.",
        f"- Watchlist codici QuickOrganizer non in IUSENTRA: {', '.join(comparison['object_compare']['missing_in_iusentra']) or 'nessuno'}.",
        "- Non importare certificati storici o sezioni distaccate senza servizi come blocchi globali.",
        "",
        "## Dati/tenant/SQL",
        "",
        "- Ogni nuovo dato va su SQLite e PostgreSQL con JSON solo mirror.",
        "- API JSON e React full devono restare la superficie primaria.",
        "- Ogni import QuickOrganizer deve evitare password/account e dati personali non richiesti.",
        "",
        "## Verifiche obbligatorie future",
        "",
        "- Test mirati su catalogo deposito, mapping schema, PEC workflow, ricerca fascicoli e certificati.",
        "- Prova reale su `127.0.0.1:8080` prima di dichiarare qualunque comportamento utente.",
        "- Browser reale, scroll completo, hover/focus, responsive e testo italiano corretto quando la UI verrà modificata.",
    ]
    return write_utf8(ART / "lavoro-specializzazione-deposito-pec-fascicoli.md", "\n".join(lines))


def write_index_markdown(outputs: list[Path]) -> Path:
    lines = [
        "# Indice artefatti QuickOrganizer",
        "",
        f"Generato: {GENERATED_AT}.",
        "",
        "Questo indice va riletto dopo ogni compattazione prima di proseguire su deposito, PEC, fascicoli, notifiche, portali o certificati.",
        "",
        "## File",
        "",
    ]
    for path in sorted(outputs, key=lambda p: p.name):
        lines.append(f"- `{rel(path)}`")
    lines.extend(
        [
            "",
            "## Regola di manutenzione",
            "",
            "- Se si scoprono nuove azioni, campi, DLL o schemi, aggiornare `scripts/generate_quickorganizer_analysis_artifacts.py` e rigenerare.",
            "- Le decisioni sensibili restano replicate in `artifacts/react-migration/procedura-deposito-telematico.md`.",
            "- Questo set è analisi documentale: la prova utente reale va fatta sulla copia IUSENTRA `127.0.0.1:8080` quando si modifica la UI o il flusso operativo.",
        ]
    )
    return write_utf8(ART / "quickorganizer-indice-artefatti.md", "\n".join(lines))


def write_json_artifacts(
    catalog: list[dict[str, Any]],
    namespace_manifest: list[dict[str, Any]],
    xml_namespace_counter: Counter,
    root_classes: list[dict[str, Any]],
    create_methods: list[dict[str, Any]],
    key_to_methods: list[dict[str, Any]],
    refs: dict[str, Any],
    comparison: dict[str, Any],
    resources: dict[str, Any],
    mdb: dict[str, Any],
    registry_catalog: dict[str, Any],
    download_flow: dict[str, Any],
    macro_counts: Counter,
    category_counts: Counter,
) -> list[Path]:
    catalog_payload = {
        "schema_version": 1,
        "generated_at": GENERATED_AT,
        "source": {
            "application": "QuickOrganizer.exe / Studio Legale Telematico 2026 Rel. 021",
            "database": str(QUICK_MDB),
            "catalog_extraction": str(CATALOG_SRC),
            "decompiled_source": str(DECOMP),
        },
        "official_sources": OFFICIAL_SOURCES,
        "counts": {
            "total_deposit_types": len(catalog),
            "macroareas": dict(sorted(macro_counts.items())),
            "categories": dict(sorted(category_counts.items())),
        },
        "entries": catalog,
    }
    outputs = [
        write_json(ART / "quickorganizer-deposito-catalogo.json", catalog_payload),
        write_json(IUS_DEPOSIT_CATALOG, catalog_payload),
        write_json(
            ART / "quickorganizer-xsd-datiatto-manifest.json",
            {
                "schema_version": 1,
                "generated_at": GENERATED_AT,
                "source": {
                    "decompiled_source": str(DECOMP),
                    "form_deposito": str(FORM),
                    "pct_core": str(PCT),
                    "browser_portali": str(BROWSER),
                    "wizard_polisweb": str(WIZARD),
                },
                "official_sources": OFFICIAL_SOURCES,
                "xml_namespace_count": len(xml_namespace_counter),
                "xml_namespaces": [
                    {"namespace": namespace, "references": count}
                    for namespace, count in sorted(xml_namespace_counter.items())
                ],
                "namespace_groups": namespace_manifest,
                "root_classes": root_classes,
                "create_datiatto_methods": create_methods,
                "atto_key_to_datiatto_methods": key_to_methods,
                **refs,
            },
        ),
        write_json(
            ART / "quickorganizer-datiatto-generatori-campo-per-campo.json",
            {
                "schema_version": 1,
                "generated_at": GENERATED_AT,
                "source": {
                    "application": "QuickOrganizer.exe / Studio Legale Telematico",
                    "decompiled_source": str(DECOMP),
                    "form_deposito": str(FORM),
                },
                "counts": {
                    "create_datiatto_methods": len(create_methods),
                    "atto_key_cases": len(key_to_methods),
                },
                "create_datiatto_methods": create_methods,
                "atto_key_to_datiatto_methods": key_to_methods,
            },
        ),
        write_json(ART / "quickorganizer-confronto-certificati-codici.json", comparison),
        write_json(ART / "quickorganizer-risorse-dll-sottocartelle.json", resources),
        write_json(ART / "quickorganizer-database-fascicoli-pec.json", mdb),
        write_json(ART / "quickorganizer-registri-consultazione-fascicoli.json", registry_catalog),
        write_json(ART / "quickorganizer-portale-lettura-download-fascicolo.json", download_flow),
    ]
    return outputs


def ensure_clean_encoding(paths: list[Path]) -> None:
    bad_markers = ["\u00c3", "\u00c2", "\u00e2", "\ufffd"]
    for path in paths:
        if not path.exists() or path.suffix.lower() in {".json"}:
            data = path.read_text(encoding="utf-8") if path.exists() else ""
        else:
            data = path.read_text(encoding="utf-8")
        bad = [marker for marker in bad_markers if marker in data]
        if bad:
            raise SystemExit(f"Mojibake residue in {path}: {bad}")


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog()
    namespace_manifest, xml_namespace_counter, root_classes = extract_schema_manifest()
    create_methods, key_to_methods, key_method_map = extract_datiatto()
    refs = extract_runtime_refs()

    for item in catalog:
        mapping = key_method_map.get(item["key"])
        item["datiatto_methods"] = mapping["methods"] if mapping else []
        item["datiatto_roots"] = mapping["saved_roots"] if mapping else []
        item["datiatto_required_data"] = mapping["required_data"] if mapping else []
        item["deposit_menu_flags"] = mapping["flags"] if mapping else {}
        item["deposit_fixed_object_codes"] = mapping["fixed_object_codes"] if mapping else []

    macro_counts = Counter(item.get("macro", "") for item in catalog)
    category_counts = Counter(item.get("categoria", "") for item in catalog)

    comparison = compare_certificates_and_codes()
    resources = collect_resource_inventory()
    mdb = collect_mdb_summary()
    registry_catalog = collect_registry_download_catalog()
    download_flow = collect_portal_download_flow()

    outputs = []
    outputs.extend(
        write_json_artifacts(
            catalog,
            namespace_manifest,
            xml_namespace_counter,
            root_classes,
            create_methods,
            key_to_methods,
            refs,
            comparison,
            resources,
            mdb,
            registry_catalog,
            download_flow,
            macro_counts,
            category_counts,
        )
    )
    outputs.append(write_catalog_markdown(catalog, macro_counts))
    outputs.extend(write_sector_catalogs(catalog))
    outputs.append(
        write_xsd_markdown(
            catalog,
            namespace_manifest,
            xml_namespace_counter,
            root_classes,
            refs,
            create_methods,
            key_to_methods,
        )
    )
    outputs.extend(write_datiatto_generator_files(catalog, create_methods, key_to_methods))
    outputs.extend(write_menu_rules_files(catalog, key_to_methods))
    outputs.extend(write_busta_contract_files(catalog, create_methods, key_to_methods, refs))
    outputs.append(write_logic_markdown(refs, comparison))
    outputs.append(write_firma_pin_markdown(refs))
    outputs.append(write_pec_notifiche_markdown(refs))
    outputs.append(write_portali_markdown(refs))
    outputs.append(write_registry_download_markdown(registry_catalog))
    outputs.append(write_portal_download_flow_markdown(download_flow))
    outputs.append(write_certificate_code_markdown(comparison))
    outputs.append(write_resources_markdown(resources))
    outputs.append(write_mdb_markdown(mdb))
    outputs.append(write_work_markdown(comparison, resources, mdb, registry_catalog, download_flow))
    outputs.append(write_index_markdown(outputs))

    ensure_clean_encoding(outputs)
    print(
        json.dumps(
            {
                "catalog_entries": len(catalog),
                "macroareas": len(macro_counts),
                "xml_namespaces": len(xml_namespace_counter),
                "create_datiatto_methods": len(create_methods),
                "key_method_mappings": len(key_to_methods),
                "files_written": [rel(path) for path in outputs],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
