"""Ricerca read-only degli uffici giudiziari competenti per Comune.

Il modulo interroga Giustizia Map senza cache e senza scrivere dati runtime:
serve la UI React degli Strumenti Forensi quando l'avvocato deve individuare
Tribunale, Giudice di Pace, Procura, UNEP e uffici distrettuali collegati.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

GIUSTIZIA_MAP_VIEW_URL = "https://www.giustizia.it/giustizia/it/mg_form_view.wp?uid=G_MAP"
GIUSTIZIA_MAP_FORM_URL = "https://www.giustizia.it/giustizia/it/mg_form_submit.page"

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


def _clean_text(value: Any) -> str:
    text = str(value or "").replace("\xa0", " ")
    for source, target in _TEXT_REPLACEMENTS.items():
        text = text.replace(source, target)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _validate_comune(comune: str) -> str:
    normalized = _clean_text(comune)
    if len(normalized) < 2:
        raise ValueError("Inserisci almeno due caratteri del Comune.")
    if len(normalized) > 80 or any(ord(char) < 32 for char in normalized):
        raise ValueError("Il nome del Comune non è valido.")
    return normalized


def _fetch_giustizia_map(comune: str, timeout: float) -> str:
    body = urlencode(
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
        }
    ).encode("utf-8")
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


def _extract_xml(payload: str) -> str:
    raw = (payload or "").strip()
    if raw.startswith("<") and "<ufficio" in raw:
        return raw
    parser = _BloccoXmlParser()
    parser.feed(raw)
    xml_text = _clean_text("".join(parser.parts))
    if xml_text.startswith("<") and "<ufficio" in xml_text:
        return xml_text
    match = re.search(r"(<[^>]*uffici[^>]*>.*?</[^>]*uffici>)", raw, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1)
    raise ValueError("La risposta ministeriale non contiene uffici leggibili.")


def _node_text(node: ElementTree.Element | None) -> str:
    if node is None:
        return ""
    return _clean_text(" ".join(node.itertext()))


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
    if "UNEP PRESSO IL TRIBUNALE" in upper:
        return "unep", "UNEP", 40, True
    if "CORTE DI ASSISE DI APPELLO" in upper:
        return "assise_appello", "Corte di Assise d'Appello", 55, True
    if "CORTE D'APPELLO" in upper or "CORTE DI APPELLO" in upper:
        return "corte_appello", "Corte d'Appello", 50, True
    if "CORTE DI ASSISE" in upper:
        return "assise", "Corte di Assise", 60, True
    if "PROCURA GENERALE" in upper:
        return "procura_generale", "Procura Generale", 70, False
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
        "email": _node_text(node.find("email")),
        "pec": _node_text(node.find("pec")),
        "site": _node_text(node.find("sitoweb")),
        "fiscalCode": _node_text(node.find("codicefiscale")),
        "patrono": _node_text(node.find("patrono")),
        "notes": _node_text(node.find("infoaggiuntive")),
        "assistenzaPct": _children_text(node.find("assistenza_pct")),
        "casellario": _children_text(node.find("casellario")),
    }
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
            "Ricerca eseguita in tempo reale sulla fonte ministeriale, senza salvare copie locali.",
            "I recapiti sono riportati come pubblicati dalla fonte e possono richiedere verifica prima dell'uso.",
        ],
    }
