"""Ricerca read-only degli uffici giudiziari competenti per Comune.

Il modulo usa la banca dati locale generata da fonti pubbliche ministeriali e,
se un Comune non è ancora presente nel DB, può interrogare Giustizia Map in
tempo reale. Serve le superfici React quando l'avvocato deve individuare PEC di
Tribunale, Giudice di Pace, Procura, UNEP e uffici distrettuali collegati.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
from datetime import datetime, timezone
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

GIUSTIZIA_MAP_VIEW_URL = "https://www.giustizia.it/giustizia/it/mg_form_view.wp?uid=G_MAP"
GIUSTIZIA_MAP_FORM_URL = "https://www.giustizia.it/giustizia/it/mg_form_submit.page"
UFFICI_MINISTERO_DATA = Path(__file__).resolve().parent / "data" / "uffici_ministero.json"
UFFICI_GIUDIZIARI_COMUNI_DB = Path(__file__).resolve().parent / "data" / "uffici_giudiziari_comuni.sqlite"
PEC_TERRITORIO_DATA = Path(__file__).resolve().parent / "data" / "pec_territorio.json"

FetchGiustiziaMap = Callable[[str, float], str]

_TEXT_REPLACEMENTS = {
    chr(0x0101): chr(0x00E0),
    chr(0x0100): chr(0x00C0),
    chr(0x0113): chr(0x00E8),
    chr(0x0112): chr(0x00C8),
    chr(0x0117): chr(0x00EC),
    chr(0x0116): chr(0x00CC),
    chr(0x014D): chr(0x00F2),
    chr(0x014C): chr(0x00D2),
    chr(0x016B): chr(0x00F9),
    chr(0x016A): chr(0x00D9),
    "牋": " ",
}


class _BloccoXmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capture_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._capture_depth:
            self._capture_depth += 1
            return
        attr_map = {name.lower(): value or "" for name, value in attrs}
        if tag.lower() == "span" and attr_map.get("id") == "blocco_xml":
            self._capture_depth = 1

    def handle_endtag(self, tag: str) -> None:
        if self._capture_depth:
            self._capture_depth = max(0, self._capture_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._capture_depth:
            self.parts.append(data)


class _ComuneSelectParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capture = False
        self._current_value = ""
        self._current_text: list[str] = []
        self.options: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "option":
            return
        attr_map = {name.lower(): value or "" for name, value in attrs}
        value = attr_map.get("value", "").strip()
        if "#" not in value:
            return
        self._capture = True
        self._current_value = value
        self._current_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "option" or not self._capture:
            return
        self.options.append((self._current_value, _clean_text("".join(self._current_text))))
        self._capture = False
        self._current_value = ""
        self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._current_text.append(data)


def _clean_text(value: Any) -> str:
    text = html.unescape(str(value or "")).replace("\xa0", " ")
    for source, target in _TEXT_REPLACEMENTS.items():
        text = text.replace(source, target)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _comparable(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean_text(value).casefold())


def _validate_comune(comune: str) -> str:
    normalized = _clean_text(comune)
    if len(normalized) < 2:
        raise ValueError("Inserisci almeno due caratteri del Comune.")
    if len(normalized) > 80 or any(ord(char) < 32 for char in normalized):
        raise ValueError("Il nome del Comune non è valido.")
    return normalized


def _post_giustizia_map(fields: dict[str, str], timeout: float) -> str:
    body = urlencode(fields).encode("utf-8")
    request = Request(
        GIUSTIZIA_MAP_FORM_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": "IUSENTRA uffici competenti/1.0",
        },
    )
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - fonte ministeriale esplicita.
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _find_comune_option(payload: str, comune: str, sigla_provincia: str = "") -> str:
    parser = _ComuneSelectParser()
    parser.feed(payload or "")
    if not parser.options:
        return ""
    wanted = _comparable(comune)
    wanted_provincia = _clean_text(sigla_provincia).upper()
    exact: list[tuple[str, str]] = []
    exact_province: list[tuple[str, str]] = []
    partial: list[tuple[str, str]] = []
    partial_province: list[tuple[str, str]] = []
    for value, label in parser.options:
        option_name = value.split("#", 1)[1] if "#" in value else label
        label_name = re.sub(r"\s*\([A-Z]{2}\)\s*$", "", _clean_text(label))
        comparable = _comparable(option_name or label_name)
        province_match = not wanted_provincia or re.search(rf"\({re.escape(wanted_provincia)}\)\s*$", label)
        if comparable == wanted:
            exact.append((value, label))
            if province_match:
                exact_province.append((value, label))
        elif comparable.startswith(wanted) or wanted.startswith(comparable):
            partial.append((value, label))
            if province_match:
                partial_province.append((value, label))
    if exact_province:
        return exact_province[0][0]
    if exact:
        return exact[0][0]
    if len(parser.options) == 1:
        return parser.options[0][0]
    if partial_province:
        return partial_province[0][0]
    if partial:
        return partial[0][0]
    return ""


def _fetch_giustizia_map(comune: str, timeout: float) -> str:
    if "#" in comune:
        return _post_giustizia_map(
            {
                "uid": "G_MAP",
                "_pagina_": "3",
                "comune": comune,
                "_xml_": "xml",
                "Submit": "cerca",
            },
            timeout,
        )
    first = _post_giustizia_map(
        {
            "uid": "G_MAP",
            "_pagina_": "2",
            "cerca_comune": comune,
            "tipo_ufficio": "",
            "lista_regioni": "",
            "lista_prov": "",
            "ricerca_libera": "",
            "_xml_": "xml",
            "Submit": "cerca",
        },
        timeout,
    )
    try:
        _extract_xml(first)
        return first
    except ValueError:
        selected = _find_comune_option(first, comune)
        if not selected:
            return first
    return _post_giustizia_map(
        {
            "uid": "G_MAP",
            "_pagina_": "3",
            "comune": selected,
            "_xml_": "xml",
            "Submit": "cerca",
        },
        timeout,
    )


def _extract_xml(payload: str) -> str:
    raw = (payload or "").strip()
    if raw.startswith("<") and "<ufficio" in raw:
        return raw
    parser = _BloccoXmlParser()
    parser.feed(raw)
    xml_text = _clean_text("".join(parser.parts))
    if "<ufficio" in xml_text:
        starts = [pos for pos in (xml_text.find("<?xml"), xml_text.find("<root"), xml_text.find("<uffici"), xml_text.find("<ufficio")) if pos >= 0]
        start = min(starts) if starts else 0
        end = len(xml_text)
        for close_tag in ("</root>", "</uffici>"):
            close_pos = xml_text.rfind(close_tag)
            if close_pos >= 0:
                end = close_pos + len(close_tag)
                break
        return xml_text[start:end]
    match = re.search(r"(<[^>]*uffici[^>]*>.*?</[^>]*uffici>)", raw, re.IGNORECASE | re.DOTALL)
    if match:
        return _clean_text(match.group(1))
    raise ValueError("La risposta ministeriale non contiene uffici leggibili.")


def _node_text(node: ElementTree.Element | None) -> str:
    if node is None:
        return ""
    return _clean_text(" ".join(node.itertext()))


def _extract_pec_addresses(value: str) -> str:
    addresses = re.findall(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", str(value or ""), flags=re.I)
    pec_addresses: list[str] = []
    seen: set[str] = set()
    for address in addresses:
        clean = address.strip(" .;,").lower()
        domain = clean.rsplit("@", 1)[-1]
        if not clean or ("pec" not in domain and "cert" not in domain):
            continue
        if clean not in seen:
            seen.add(clean)
            pec_addresses.append(clean)
    return ", ".join(pec_addresses)


@lru_cache(maxsize=1)
def _load_uffici_ministero() -> tuple[dict[str, Any], ...]:
    try:
        data = json.loads(UFFICI_MINISTERO_DATA.read_text(encoding="utf-8"))
    except Exception:
        return ()
    offices = data.get("uffici") if isinstance(data, dict) else {}
    if not isinstance(offices, dict):
        return ()
    rows: list[dict[str, Any]] = []
    for codice_gl, raw in offices.items():
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        row["codice_gl"] = str(row.get("codice_gl") or codice_gl)
        row["kind"] = _ministero_kind(row)
        rows.append(row)
    return tuple(rows)


def _ministero_kind(row: dict[str, Any]) -> str:
    text = _clean_text(
        " ".join(
            [
                str(row.get("tipo_ministero_descrizione") or ""),
                str(row.get("descrizione_ministero") or ""),
            ]
        )
    ).upper()
    if "GIUDICE DI PACE" in text:
        return "giudice_pace"
    if "PROCURA" in text and "MINORENNI" in text:
        return "procura_minorenni"
    if "TRIBUNALE" in text and "MINORENNI" in text:
        return "tribunale_minorenni"
    if "PROCURA GENERALE" in text:
        return "procura_generale"
    if "PROCURA" in text:
        return "procura"
    if "CORTE" in text and "APPELLO" in text:
        return "corte_appello"
    if "TRIBUNALE" in text:
        return "tribunale"
    return ""


def _ministero_match(office: dict[str, Any], city: str) -> dict[str, Any] | None:
    kind = str(office.get("kind") or "")
    if not kind:
        return None
    city_key = _comparable(city)
    name_key = _comparable(str(office.get("name") or ""))
    candidates: list[dict[str, Any]] = []
    for row in _load_uffici_ministero():
        if row.get("kind") != kind:
            continue
        row_city = _comparable(str(row.get("comune_ministero") or ""))
        row_name = _comparable(str(row.get("descrizione_ministero") or ""))
        if city_key and row_city == city_key:
            candidates.append(row)
        elif name_key and row_name and (row_name in name_key or name_key in row_name):
            candidates.append(row)
    if not candidates:
        return None
    with_pec = [row for row in candidates if _extract_pec_addresses(str(row.get("pec_ministero") or ""))]
    return (with_pec or candidates)[0]


@lru_cache(maxsize=1)
def _load_pec_territorio() -> tuple[dict[str, str], ...]:
    try:
        data = json.loads(PEC_TERRITORIO_DATA.read_text(encoding="utf-8"))
    except Exception:
        return ()
    entries = data.get("entries") if isinstance(data, dict) else []
    if not isinstance(entries, list):
        return ()
    result: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        email = _extract_pec_addresses(str(entry.get("email") or ""))
        if not email:
            continue
        result.append(
            {
                "pec": email,
                "kind": str(entry.get("kind") or ""),
                "cityKey": str(entry.get("cityKey") or ""),
                "label": str(entry.get("label") or ""),
            }
        )
    return tuple(result)


def _pec_territorio_match(office: dict[str, Any]) -> dict[str, str] | None:
    kind = str(office.get("kind") or "")
    city_key = _comparable(str(office.get("city") or ""))
    if not kind or not city_key:
        return None
    candidates = [
        entry
        for entry in _load_pec_territorio()
        if entry.get("kind") == kind and entry.get("cityKey") == city_key
    ]
    if kind == "procura_generale" and not candidates:
        candidates = [
            entry
            for entry in _load_pec_territorio()
            if entry.get("kind") == "procura_generale" and city_key in str(entry.get("cityKey") or "")
        ]
    if kind == "assise_appello" and not candidates:
        candidates = [
            entry
            for entry in _load_pec_territorio()
            if entry.get("kind") in {"assise_appello", "corte_appello"} and entry.get("cityKey") == city_key
        ]
    if kind == "assise" and not candidates:
        candidates = [
            entry
            for entry in _load_pec_territorio()
            if entry.get("kind") in {"assise", "tribunale"} and entry.get("cityKey") == city_key
        ]
    if not candidates:
        return None
    preferred = sorted(
        candidates,
        key=lambda entry: (
            0 if str(entry.get("pec") or "").startswith(("prot.", "dirigente.", "presidente.")) else 1,
            str(entry.get("pec") or ""),
        ),
    )
    return preferred[0]


def _children_text(node: ElementTree.Element | None) -> dict[str, str]:
    if node is None:
        return {}
    values: dict[str, str] = {}
    for child in list(node):
        text = _node_text(child)
        if text:
            values[child.tag.lower()] = text
    return values


def _office_kind(name: str) -> tuple[str, str, int, bool]:
    upper = name.upper()
    if "GIUDICE DI PACE" in upper:
        return "giudice_pace", "Giudice di Pace", 10, True
    if "PROCURA DELLA REPUBBLICA PRESSO IL TRIBUNALE PER I MINORENNI" in upper:
        return "procura_minorenni", "Procura presso Tribunale per i minorenni", 61, True
    if "TRIBUNALE PER I MINORENNI" in upper:
        return "tribunale_minorenni", "Tribunale per i minorenni", 62, True
    if upper.startswith("TRIBUNALE DI ") and not any(
        marker in upper for marker in ("SUPERIORE", "REGIONALE", "SORVEGLIANZA")
    ):
        return "tribunale", "Tribunale", 20, True
    if "PROCURA DELLA REPUBBLICA PRESSO IL TRIBUNALE" in upper:
        return "procura", "Procura", 30, True
    if "UNEP PRESSO IL TRIBUNALE" in upper or "U.N.E.P. PRESSO IL TRIBUNALE" in upper:
        return "unep", "UNEP", 40, True
    if (
        "CORTE DI ASSISE DI APPELLO" in upper
        or "CORTE DI ASSISE D'APPELLO" in upper
        or "CORTE D'ASSISE D'APPELLO" in upper
    ):
        return "assise_appello", "Corte di Assise d'Appello", 55, True
    if "PROCURA GENERALE" in upper and "CASSAZIONE" in upper:
        return "speciale", "Ufficio nazionale o speciale", 90, False
    if "PROCURA GENERALE" in upper:
        return "procura_generale", "Procura Generale", 70, False
    if "CORTE D'APPELLO" in upper or "CORTE DI APPELLO" in upper:
        return "corte_appello", "Corte d'Appello", 50, True
    if "CORTE DI ASSISE" in upper:
        return "assise", "Corte di Assise", 60, True
    if "SORVEGLIANZA" in upper:
        return "sorveglianza", "Sorveglianza", 75, False
    if "CORTE SUPREMA" in upper or "DIREZIONE NAZIONALE" in upper or "ACQUE PUBBLICHE" in upper:
        return "speciale", "Ufficio nazionale o speciale", 90, False
    return "altro", "Ufficio giudiziario", 80, False


def _action(label: str, href: str, tone: str = "primary") -> dict[str, str]:
    return {"label": label, "href": href, "method": "GET", "tone": tone}


def _href(path: str, **query: str) -> str:
    clean = {key: value for key, value in query.items() if value}
    return path if not clean else f"{path}?{urlencode(clean)}"


def _office_actions(office: dict[str, Any], comune: str) -> list[dict[str, str]]:
    name = str(office.get("name") or "")
    kind = str(office.get("kind") or "")
    actions = [
        _action(
            "Usa nel fascicolo",
            _href("/fascicoli/nuovo", ufficio_competente=name, comune_competenza=comune),
        )
    ]
    if kind == "unep":
        actions.append(
            _action(
                "Prepara notifica",
                _href("/notifiche-legali", ufficio_notifica=name, comune_competenza=comune),
                "success",
            )
        )
    if kind in {"tribunale", "giudice_pace", "corte_appello", "assise", "assise_appello"}:
        actions.append(
            _action(
                "Controlla deposito",
                _href("/deposito/checklist", ufficio=name, comune_competenza=comune),
                "warning",
            )
        )
    return actions


def _office_id(name: str, address: str, city: str) -> str:
    digest = hashlib.sha1(f"{name}|{address}|{city}".encode("utf-8")).hexdigest()[:12]
    return f"ufficio-{digest}"


def _office_from_node(node: ElementTree.Element, comune: str) -> dict[str, Any]:
    name = _clean_text(node.attrib.get("nomeufficio")) or _node_text(node.find("nome")) or _node_text(node.find("ufficio"))
    address = _node_text(node.find("indirizzo"))
    city = _node_text(node.find("comune"))
    email = _node_text(node.find("email"))
    pec = _extract_pec_addresses(" ".join([_node_text(node.find("pec")), email]))
    kind, type_label, priority, primary = _office_kind(name)
    office: dict[str, Any] = {
        "id": _office_id(name, address, city),
        "name": name,
        "kind": kind,
        "typeLabel": type_label,
        "priority": priority,
        "primary": primary,
        "address": address,
        "city": city,
        "cap": _node_text(node.find("cap")),
        "istatCode": _node_text(node.find("codiceistat")),
        "phone": _node_text(node.find("telefono")),
        "fax": _node_text(node.find("fax")),
        "email": email,
        "pec": pec,
        "site": _node_text(node.find("sitoweb")),
        "fiscalCode": _node_text(node.find("codicefiscale")),
        "patrono": _node_text(node.find("patrono")),
        "notes": _node_text(node.find("infoaggiuntive")),
        "assistenzaPct": _children_text(node.find("assistenza_pct")),
        "casellario": _children_text(node.find("casellario")),
    }
    ministero = _ministero_match(office, city)
    if ministero:
        if not office["pec"]:
            office["pec"] = _extract_pec_addresses(str(ministero.get("pec_ministero") or ""))
        office["codiceMinistero"] = str(ministero.get("codice_ministero") or "")
        office["codiceGiustiziaLocale"] = str(ministero.get("codice_gl") or "")
    if not office["pec"]:
        pec_territorio = _pec_territorio_match(office)
        if pec_territorio:
            office["pec"] = pec_territorio["pec"]
            office["pecSource"] = "Ministero della Giustizia - Posta certificata strutture territoriali"
    office["actions"] = _office_actions(office, comune)
    return office


def _parse_offices(xml_text: str, comune: str) -> list[dict[str, Any]]:
    root = ElementTree.fromstring(xml_text)
    offices = [
        _office_from_node(node, comune)
        for node in root.iter()
        if node.tag.lower() == "ufficio"
    ]
    return sorted(offices, key=lambda office: (int(office.get("priority") or 99), str(office.get("name") or "")))


def _filter_offices(
    offices: Iterable[dict[str, Any]],
    includi_speciali: bool,
    *,
    tipi_ufficio: Iterable[str] | None = None,
    solo_pec: bool = False,
) -> list[dict[str, Any]]:
    allowed_kinds = {str(kind).strip() for kind in (tipi_ufficio or []) if str(kind).strip()}
    filtered = list(offices)
    if includi_speciali:
        visible = filtered
    else:
        visible = [office for office in filtered if office.get("primary") is True]
    if allowed_kinds:
        visible = [office for office in visible if str(office.get("kind") or "") in allowed_kinds]
    if solo_pec:
        visible = [office for office in visible if str(office.get("pec") or "").strip()]
    return visible


def _comune_record_from_query(comune: str):
    try:
        from pct.territorio_italia import get_comune
    except Exception:
        return None
    raw = _clean_text(comune)
    if "#" in raw:
        prefix, name = raw.split("#", 1)
        codice_istat = prefix[-6:] if len(prefix) >= 6 else ""
        return get_comune(codice_istat=codice_istat, nome=name)
    return get_comune(nome=raw)


def _ricerca_uffici_da_db(
    comune: str,
    *,
    includi_speciali: bool,
    tipi_ufficio: Iterable[str] | None,
    solo_pec: bool,
) -> dict[str, Any] | None:
    record = _comune_record_from_query(comune)
    if record is None or not UFFICI_GIUDIZIARI_COMUNI_DB.exists():
        return None
    conn = None
    try:
        conn = sqlite3.connect(UFFICI_GIUDIZIARI_COMUNI_DB)
        conn.row_factory = sqlite3.Row
        status = conn.execute(
            "SELECT ok, total_official FROM comuni_status WHERE codice_istat = ?",
            (record.codice_istat,),
        ).fetchone()
        if status is None or int(status["ok"] or 0) != 1:
            return None
        columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(office_associations)").fetchall()}
        if "office_json" in columns:
            rows = conn.execute(
                """
                SELECT office_json, '' AS derived_from, '' AS association_source
                FROM office_associations
                WHERE comune_istat = ?
                ORDER BY kind, name
                """,
                (record.codice_istat,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT o.office_json,
                       a.derived_from,
                       a.association_source
                FROM office_associations a
                JOIN offices o ON o.office_id = a.office_id
                WHERE a.comune_istat = ?
                ORDER BY o.kind, o.name
                """,
                (record.codice_istat,),
            ).fetchall()
    except Exception:
        return None
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass
    offices_all: list[dict[str, Any]] = []
    for row in rows:
        office = json.loads(row["office_json"])
        derived_from = []
        try:
            derived_from = json.loads(row["derived_from"] or "[]")
        except Exception:
            derived_from = []
        if derived_from:
            office["derivedFromComuni"] = derived_from
        if row["association_source"]:
            office["associationSource"] = str(row["association_source"])
        office["associationComuneIstat"] = record.codice_istat
        office["associationComune"] = record.label
        office["actions"] = _office_actions(office, record.label)
        offices_all.append(office)
    offices_all = sorted(offices_all, key=lambda office: (int(office.get("priority") or 99), str(office.get("name") or "")))
    offices = _filter_offices(
        offices_all,
        includi_speciali,
        tipi_ufficio=tipi_ufficio,
        solo_pec=solo_pec,
    )
    warnings: list[str] = [
        "Verifica materia, rito, valore, foro applicabile e norme speciali prima di usare il risultato in un atto."
    ]
    has_derived_associations = any(office.get("derivedFromComuni") for office in offices_all)
    if has_derived_associations:
        warnings.append(
            "Per questo Comune di nuova istituzione la fonte ministeriale non espone ancora il nome corrente: "
            "gli uffici sono stati ricavati interrogando i Comuni predecessori documentati."
        )
    if offices_all and not offices:
        warnings.append("La banca dati locale contiene uffici per il Comune, ma nessuno risponde ai filtri selezionati.")
    return {
        "comune": record.label,
        "comuneRecord": record.to_dict(),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "title": "Banca dati locale da Ministero della Giustizia - Giustizia Map",
            "url": GIUSTIZIA_MAP_VIEW_URL,
        },
        "totalOfficial": int(status["total_official"] or len(offices_all)),
        "totalVisible": len(offices),
        "primaryCount": sum(1 for office in offices_all if office.get("primary") is True),
        "offices": offices,
        "warnings": warnings,
        "notes": [
            "Ricerca eseguita sulla banca dati locale costruita da Giustizia Map.",
            "I recapiti PEC sono normalizzati e integrati, quando necessario, con il catalogo ministeriale locale.",
            *(
                ["Le associazioni derivate mantengono evidenza dei Comuni predecessori usati per l'interrogazione."]
                if has_derived_associations
                else []
            ),
        ],
    }


def ricerca_uffici_competenti(
    comune: str,
    *,
    includi_speciali: bool = False,
    tipi_ufficio: Iterable[str] | None = None,
    solo_pec: bool = False,
    timeout: float = 8.0,
    fetcher: FetchGiustiziaMap | None = None,
) -> dict[str, Any]:
    """Restituisce gli uffici competenti dal servizio ministeriale, senza cache."""

    comune_normalizzato = _validate_comune(comune)
    if fetcher is None:
        cached = _ricerca_uffici_da_db(
            comune_normalizzato,
            includi_speciali=includi_speciali,
            tipi_ufficio=tipi_ufficio,
            solo_pec=solo_pec,
        )
        if cached is not None:
            return cached
    html = fetcher(comune_normalizzato, timeout) if fetcher else _fetch_giustizia_map(comune_normalizzato, timeout)
    offices_all = _parse_offices(_extract_xml(html), comune_normalizzato)
    offices = _filter_offices(
        offices_all,
        includi_speciali,
        tipi_ufficio=tipi_ufficio,
        solo_pec=solo_pec,
    )
    warnings: list[str] = [
        "Verifica materia, rito, valore, foro applicabile e norme speciali prima di usare il risultato in un atto."
    ]
    if offices_all and not offices:
        warnings.append("La ricerca ha trovato solo uffici generali o speciali: attiva la visualizzazione completa.")
    elif len(offices) < len(offices_all):
        warnings.append("Gli uffici nazionali e speciali sono nascosti per rendere la lista più operativa.")

    return {
        "comune": comune_normalizzato,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "title": "Ministero della Giustizia - Giustizia Map",
            "url": GIUSTIZIA_MAP_VIEW_URL,
        },
        "totalOfficial": len(offices_all),
        "totalVisible": len(offices),
        "primaryCount": sum(1 for office in offices_all if office.get("primary") is True),
        "offices": offices,
        "warnings": warnings,
        "notes": [
            "Ricerca eseguita in tempo reale sulla fonte ministeriale.",
            "I recapiti PEC sono normalizzati e integrati, quando necessario, con il catalogo ministeriale locale.",
        ],
    }
