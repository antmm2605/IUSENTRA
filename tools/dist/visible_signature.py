from __future__ import annotations

import base64
import io
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - fallback difensivo
    ZoneInfo = None  # type: ignore[assignment]

CM_TO_PT = 28.35
MM_TO_PT = 72.0 / 25.4
VISIBLE_SIGNATURE_LATERAL_RIGHT_MARGIN_MM = 3.0
VISIBLE_SIGNATURE_LATERAL_RIGHT_MARGIN_PT = VISIBLE_SIGNATURE_LATERAL_RIGHT_MARGIN_MM * MM_TO_PT
VISIBLE_SIGNATURE_LATERAL_SEAL_RIGHT_MARGIN_MM = 1.0
VISIBLE_SIGNATURE_LATERAL_SEAL_RIGHT_MARGIN_PT = VISIBLE_SIGNATURE_LATERAL_SEAL_RIGHT_MARGIN_MM * MM_TO_PT
VISIBLE_SIGNATURE_LATERAL_SEAL_BOTTOM_MARGIN_MM = 1.0
VISIBLE_SIGNATURE_LATERAL_SEAL_BOTTOM_MARGIN_PT = VISIBLE_SIGNATURE_LATERAL_SEAL_BOTTOM_MARGIN_MM * MM_TO_PT
VISIBLE_SIGNATURE_LATERAL_SEAL_TEXT_GAP_MM = 2.0
VISIBLE_SIGNATURE_LATERAL_SEAL_TEXT_GAP_PT = VISIBLE_SIGNATURE_LATERAL_SEAL_TEXT_GAP_MM * MM_TO_PT
VISIBLE_SIGNATURE_LATERAL_TEXT_INSET_PT = 0.0
VISIBLE_SIGNATURE_LATERAL_FONT_SIZE_PT = 8.0
VISIBLE_SIGNATURE_COCCARDA_HEIGHT_PT = 24.0
VISIBLE_SIGNATURE_COCCARDA_WIDTH_PT = VISIBLE_SIGNATURE_COCCARDA_HEIGHT_PT * (43.0 / 45.0)
VISIBLE_SIGNATURE_COCCARDA_HALF_WIDTH_PT = VISIBLE_SIGNATURE_COCCARDA_WIDTH_PT / 2.0
VISIBLE_SIGNATURE_MODE_LATERALE = "laterale"
VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA = "basso_sinistra"
VISIBLE_SIGNATURE_MODE_BASSO_DESTRA = "basso_destra"
VISIBLE_SIGNATURE_MODES = {
    VISIBLE_SIGNATURE_MODE_LATERALE,
    VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA,
    VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
}
VISIBLE_SIGNATURE_DATETIME_MODE_DATE_TIME = "data_ora"
VISIBLE_SIGNATURE_DATETIME_MODE_DATE = "solo_data"
VISIBLE_SIGNATURE_DATETIME_MODE_NONE = "nessuna"
VISIBLE_SIGNATURE_DATETIME_MODES = {
    VISIBLE_SIGNATURE_DATETIME_MODE_DATE_TIME,
    VISIBLE_SIGNATURE_DATETIME_MODE_DATE,
    VISIBLE_SIGNATURE_DATETIME_MODE_NONE,
}
VISIBLE_SIGNATURE_PREFIX = "Firmato digitalmente da"
VISIBLE_SIGNATURE_DATE_LABEL = "Data e ora firma:"
VISIBLE_SIGNATURE_METADATA_KEY = "/HACSSignatureStamp"
VISIBLE_SIGNATURE_FONT_REGULAR_NAME = "IUSENTRAVisibleSignature"
VISIBLE_SIGNATURE_FONT_BOLD_NAME = "IUSENTRAVisibleSignatureBold"
VISIBLE_SIGNATURE_COCCARDA_PNG_B64 = (
    "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"
    "B08rc+8PRMUAAAAASUVORK5CYII="
)
ITALY_TIMEZONE = ZoneInfo("Europe/Rome") if ZoneInfo else None


@lru_cache(maxsize=1)
def _register_visible_signature_fonts() -> tuple[str, str]:
    """Registra i TTF incorporabili distribuiti con ReportLab.

    I font PDF Base 14 (per esempio Helvetica) non vengono incorporati nel
    documento e possono rendere non conforme un PDF/A originariamente valido.
    Bitstream Vera è già parte della dipendenza ReportLab installata dal
    Local Signer e rende il timbro deterministico su Windows e Linux.
    """

    try:
        import reportlab
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception as exc:  # pragma: no cover - dipendenza obbligatoria
        raise RuntimeError(
            "Impossibile caricare il font incorporabile della firma visibile. "
            "La firma è stata interrotta per preservare la conformità PDF/A."
        ) from exc

    package_file = getattr(reportlab, "__file__", None)
    if not package_file:
        raise RuntimeError(
            "Il percorso dei font ReportLab non è disponibile. La firma è "
            "stata interrotta per preservare la conformità PDF/A."
        )

    fonts_dir = Path(package_file).resolve().parent / "fonts"
    fonts = (
        (VISIBLE_SIGNATURE_FONT_REGULAR_NAME, fonts_dir / "Vera.ttf"),
        (VISIBLE_SIGNATURE_FONT_BOLD_NAME, fonts_dir / "VeraBd.ttf"),
    )
    missing = [font_path.name for _font_name, font_path in fonts if not font_path.is_file()]
    if missing:
        raise RuntimeError(
            "Font incorporabili mancanti nel runtime ReportLab: "
            f"{', '.join(missing)}. La firma è stata interrotta per preservare "
            "la conformità PDF/A."
        )

    registered = set(pdfmetrics.getRegisteredFontNames())
    for font_name, font_path in fonts:
        if font_name not in registered:
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    return VISIBLE_SIGNATURE_FONT_REGULAR_NAME, VISIBLE_SIGNATURE_FONT_BOLD_NAME


def normalize_visible_signature_mode(value: Any) -> str:
    mode = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        VISIBLE_SIGNATURE_MODE_LATERALE: {
            "laterale",
            "side",
            "verticale",
            "margine",
            "margine_destro",
            "laterale_dx",
        },
        VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA: {
            "basso_sinistra",
            "bottom_left",
            "left",
            "sinistra",
            "sx",
            "basso_sx",
        },
        VISIBLE_SIGNATURE_MODE_BASSO_DESTRA: {
            "basso_destra",
            "bottom_right",
            "right",
            "destra",
            "dx",
            "basso_dx",
        },
    }
    for normalized, values in aliases.items():
        if mode in values:
            return normalized
    return VISIBLE_SIGNATURE_MODE_LATERALE


def normalize_visible_signature_datetime_mode(value: Any) -> str:
    mode = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        VISIBLE_SIGNATURE_DATETIME_MODE_DATE_TIME: {
            "",
            "data_ora",
            "data_e_ora",
            "date_time",
            "datetime",
            "ora",
            "orario",
            "time",
            "full",
        },
        VISIBLE_SIGNATURE_DATETIME_MODE_DATE: {
            "solo_data",
            "data",
            "date",
            "giorno",
        },
        VISIBLE_SIGNATURE_DATETIME_MODE_NONE: {
            "nessuna",
            "nessuno",
            "no",
            "none",
            "off",
            "senza_data",
        },
    }
    for normalized, values in aliases.items():
        if mode in values:
            return normalized
    return VISIBLE_SIGNATURE_DATETIME_MODE_DATE_TIME


def compute_visible_signature_layout(
    *,
    width: float,
    height: float,
    mode: str,
    margin: float = CM_TO_PT,
) -> dict[str, float | str | int]:
    """Calcola coordinate sicure per la firma visibile su pagine di qualsiasi formato."""
    page_width = max(float(width or 0), 1.0)
    page_height = max(float(height or 0), 1.0)
    shortest_side = max(min(page_width, page_height), 1.0)
    safe_margin = min(max(float(margin or CM_TO_PT), 12.0), max(shortest_side / 4, 12.0))
    resolved_mode = normalize_visible_signature_mode(mode)
    available_width = max(page_width - (safe_margin * 2), 1.0)
    available_height = max(page_height - (safe_margin * 2), 1.0)

    if resolved_mode in {VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA, VISIBLE_SIGNATURE_MODE_BASSO_DESTRA}:
        box_width = min(440.0, available_width)
        box_height = min(102.0, available_height)
        x = safe_margin
        if resolved_mode == VISIBLE_SIGNATURE_MODE_BASSO_DESTRA:
            x = max(safe_margin, page_width - box_width - safe_margin)
        y = safe_margin
        return {
            "x": x,
            "y": y,
            "box_width": box_width,
            "box_height": box_height,
            "align": "left" if resolved_mode == VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA else "right",
            "rotation": 0,
            "mode": resolved_mode,
        }

    side_width = min(max(CM_TO_PT * 1.85, min(42.0, available_width)), available_width)
    side_margin = min(safe_margin, VISIBLE_SIGNATURE_LATERAL_RIGHT_MARGIN_PT)
    side_height = page_height
    return {
        "x": max(0.0, page_width - side_width - side_margin),
        "y": 0.0,
        "box_width": side_width,
        "box_height": side_height,
        "align": "left",
        "rotation": 90,
        "mode": VISIBLE_SIGNATURE_MODE_LATERALE,
    }


def _normalize_visible_signature_place(value: str = "") -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    normalized = re.sub(r"\([^)]*\)", "", raw)
    normalized = re.sub(r"\b\d{5}\b", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" ,;-")
    if not normalized:
        return ""

    if normalized.upper() == normalized:
        normalized = normalized.title()

    return normalized[:48]


def resolve_visible_signature_place(*, city: str = "", province: str = "", address: str = "") -> str:
    city_value = _normalize_visible_signature_place(city)
    if city_value:
        return city_value

    address_value = str(address or "").strip()
    if not address_value:
        return ""

    parts = [part.strip() for part in re.split(r"[;,|-]", address_value) if part.strip()]
    if not parts:
        return ""

    candidate = re.sub(r"^\d{5}\s+", "", parts[-1]).strip()
    candidate = _normalize_visible_signature_place(candidate)
    if candidate:
        return candidate

    province_value = _normalize_visible_signature_place(province)
    if province_value:
        return province_value
    return ""


def format_visible_signature_datetime(
    value: Any,
    *,
    datetime_mode: str = VISIBLE_SIGNATURE_DATETIME_MODE_DATE_TIME,
) -> str:
    resolved_mode = normalize_visible_signature_datetime_mode(datetime_mode)
    if resolved_mode == VISIBLE_SIGNATURE_DATETIME_MODE_NONE:
        return ""

    if value is None:
        return ""

    if isinstance(value, datetime):
        dt = value
        has_time = True
    else:
        raw = str(value or "").strip()
        if not raw:
            return ""
        has_time = any(token in raw for token in ("T", ":", " "))
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            dt = None
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(raw, fmt)
                    has_time = fmt != "%Y-%m-%d"
                    break
                except Exception:
                    dt = None
            if dt is None:
                return ""

    try:
        if getattr(dt, "tzinfo", None) is not None:
            if ITALY_TIMEZONE is not None:
                dt = dt.astimezone(ITALY_TIMEZONE)
            else:
                dt = dt.astimezone()
    except Exception:
        pass

    if has_time and resolved_mode == VISIBLE_SIGNATURE_DATETIME_MODE_DATE_TIME:
        return dt.strftime("%d/%m/%Y alle ore %H:%M")
    return dt.strftime("%d/%m/%Y")


def build_visible_signature_text(
    *,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
    issuer: str = "",
    serial: str = "",
    datetime_mode: str = VISIBLE_SIGNATURE_DATETIME_MODE_DATE_TIME,
) -> str:
    signer_name = str(intestatario or "").strip()
    signature_time = format_visible_signature_datetime(
        data_firma,
        datetime_mode=datetime_mode,
    )
    signature_place = str(luogo or "").strip()
    issuer_value = str(issuer or "").strip()
    serial_value = str(serial or "").strip()

    lines: list[str] = [VISIBLE_SIGNATURE_PREFIX]
    if signer_name:
        lines.append(signer_name)
    if signature_time:
        lines.append(f"{VISIBLE_SIGNATURE_DATE_LABEL} {signature_time}")
    if signature_place:
        lines.append(f"Luogo firma: {signature_place}")
    if issuer_value:
        lines.append(f"Emesso Da: {issuer_value}")
    if serial_value:
        lines.append(f"Serial#: {serial_value}")
    return "\n".join(line for line in lines if line.strip())


def _normalize_visible_signature_name(
    intestatario: str = "",
    *,
    uppercase: bool = False,
    force_avv_prefix: bool = False,
) -> str:
    value = str(intestatario or "").strip()
    if not value:
        return ""

    normalized = value.upper()
    if force_avv_prefix and not normalized.startswith(("AVV.", "AVV ", "AVVOCATO ", "AVVOCATA ")):
        value = f"Avv. {value}"

    return value.upper() if uppercase else value


def has_visible_signature_stamp(pdf_data: bytes) -> bool:
    if not pdf_data.startswith(b"%PDF"):
        return False
    try:
        return (
            VISIBLE_SIGNATURE_METADATA_KEY.encode("ascii") in pdf_data
            or (
                VISIBLE_SIGNATURE_PREFIX.encode("utf-8") in pdf_data
                and VISIBLE_SIGNATURE_DATE_LABEL.encode("utf-8") in pdf_data
            )
        )
    except Exception:
        return False



def has_pdf_signature(pdf_data: bytes) -> bool:
    """Rileva una firma PAdES senza rischiare di riscriverne una non leggibile.

    Un errore del parser non equivale a un PDF senza firma. In quel caso la
    firma viene interrotta: il chiamante non deve mai passare il documento a
    ``PdfWriter`` e invalidare una revisione PAdES preesistente.
    """
    if not pdf_data.lstrip().startswith(b"%PDF"):
        return False
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_data), strict=False)
        for field in (reader.get_fields() or {}).values():
            try:
                current = field.get_object()
            except Exception:
                current = field
            if str(current.get("/FT") or "") == "/Sig" and current.get("/V") is not None:
                return True
        for page in reader.pages:
            for annotation_ref in page.get("/Annots", []):
                try:
                    annotation = annotation_ref.get_object()
                except Exception:
                    annotation = annotation_ref
                if (
                    str(annotation.get("/FT") or "") == "/Sig"
                    and annotation.get("/V") is not None
                ):
                    return True
    except Exception as exc:
        if re.search(rb"/ByteRange\s*\[", pdf_data) and re.search(
            rb"/(?:SubFilter\s*/ETSI\.CAdES\.detached|Type\s*/Sig)", pdf_data
        ):
            return True
        raise RuntimeError(
            "Impossibile verificare in sicurezza se il PDF contiene già una firma "
            "digitale. La firma non è stata eseguita per preservare il documento."
        ) from exc
    if re.search(rb"/ByteRange\s*\[", pdf_data) and re.search(
        rb"/(?:SubFilter\s*/ETSI\.CAdES\.detached|Type\s*/Sig)", pdf_data
    ):
        return True
    return False

# ---------------------------------------------------------------------------
# Firme già presenti e posizionamento automatico del timbro
# ---------------------------------------------------------------------------
#
# Un atto può arrivare già firmato (copia dal portale con i timbri del
# Ministero, atto firmato da un collega, cofirma). Prima di timbrare:
# - se la stessa firma (stesso certificato, o stesso titolare quando il
#   seriale manca) è già visibile, il timbro non si ripete;
# - se c'è la firma di un altro titolare, il nuovo timbro va in una zona
#   libera: margine destro, margine sinistro, in basso o in alto
#   nell'ultima pagina, senza sovrapporsi a testo o timbri esistenti.
# Base: art. 20 e 24 CAD (D.Lgs. 82/2005) e Regolamento eIDAS: la firma non
# deve alterare il contenuto leggibile del documento né quello di altre firme.

VISIBLE_SIGNATURE_ZONE_DESTRA = "destra"
VISIBLE_SIGNATURE_ZONE_SINISTRA = "sinistra"
VISIBLE_SIGNATURE_ZONE_BASSO = "basso"
VISIBLE_SIGNATURE_ZONE_ALTO = "alto"
VISIBLE_SIGNATURE_BAND_EDGE_PT = 42.0
VISIBLE_SIGNATURE_BAND_HEIGHT_PT = 30.0
VISIBLE_SIGNATURE_BAND_MIN_WIDTH_PT = 180.0
_TIMBRO_BLOCK_SEPARATOR = "\n---\n"
_PREFISSI_NOME = ("AVVOCATO ", "AVVOCATA ", "AVV. ", "AVV ", "DOTT.SSA ", "DOTT. ", "DOTT ", "PROF. ")


class FirmaGiaPresente(RuntimeError):
    """Il documento reca già la firma digitale dello stesso titolare: non si firma di nuovo."""

    def __init__(self, messaggio: str, *, firmatario: str = "") -> None:
        super().__init__(messaggio)
        self.firmatario = firmatario


def _nome_da_soggetto(value: Any) -> str:
    text = str(value or "").strip()
    match = re.search(r"(?:^|[,/])\s*CN\s*=\s*([^,/]+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else text


def _chiave_nome(value: Any) -> frozenset[str]:
    text = _nome_da_soggetto(value).upper().replace(" ", " ")
    changed = True
    while changed:
        changed = False
        for prefix in _PREFISSI_NOME:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                changed = True
    parole = re.findall(r"[A-ZÀ-Ý']{2,}", text)
    return frozenset(parole)


def _chiave_seriale(value: Any) -> str:
    text = re.sub(r"[^0-9A-Fa-f]", "", str(value or "")).upper().lstrip("0")
    return text


def stesso_firmatario(
    esistente: dict[str, Any],
    *,
    intestatario: str = "",
    serial: str = "",
) -> bool:
    """Stesso certificato se entrambi i seriali sono noti; altrimenti stesso titolare."""

    seriale_esistente = _chiave_seriale(esistente.get("seriale"))
    seriale_nuovo = _chiave_seriale(serial)
    if seriale_esistente and seriale_nuovo and len(seriale_nuovo) <= 40:
        return seriale_esistente == seriale_nuovo
    nome_esistente = _chiave_nome(esistente.get("firmatario"))
    nome_nuovo = _chiave_nome(intestatario)
    return bool(nome_esistente) and nome_esistente == nome_nuovo


def _parse_timbro(testo: str) -> dict[str, str] | None:
    match = re.search(r"Firmato\s+Da:\s*", str(testo or ""), re.IGNORECASE)
    if not match:
        return None
    resto = testo[match.end():]
    nome = re.split(
        r"\s*,?\s*(?:Emesso\s+Da:|Serial#:|Data e ora firma:|Luogo firma:|\bin data\b|Luogo:)",
        resto,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" ,;")
    emittente = re.search(r"Emesso\s+Da:\s*(.+?)\s*,?\s*(?:Serial#:|$)", resto, re.IGNORECASE)
    seriale = re.search(r"Serial#:\s*([0-9A-Fa-f:]+)", resto, re.IGNORECASE)
    if not nome:
        return None
    return {
        "firmatario": nome,
        "emittente": emittente.group(1).strip(" ,") if emittente else "",
        "seriale": seriale.group(1) if seriale else "",
    }


def _timbri_da_metadati(valore: str) -> list[dict[str, str]]:
    timbri: list[dict[str, str]] = []
    for blocco in str(valore or "").split(_TIMBRO_BLOCK_SEPARATOR):
        righe = [riga.strip() for riga in blocco.splitlines() if riga.strip()]
        if not righe or righe[0] != VISIBLE_SIGNATURE_PREFIX or len(righe) < 2:
            continue
        timbro = {"firmatario": righe[1], "emittente": "", "seriale": "", "zona": ""}
        for riga in righe[2:]:
            if riga.startswith("Emesso Da:"):
                timbro["emittente"] = riga.split(":", 1)[1].strip()
            elif riga.startswith("Serial#:"):
                timbro["seriale"] = riga.split(":", 1)[1].strip()
            elif riga.startswith("Modalita firma visibile:"):
                timbro["zona"] = riga.split(":", 1)[1].strip()
        timbri.append(timbro)
    return timbri


def _larghezza_testo(testo: str, dimensione: float) -> float:
    try:
        from reportlab.pdfbase.pdfmetrics import stringWidth

        return float(stringWidth(testo, "Helvetica", dimensione))
    except Exception:
        return len(testo) * dimensione * 0.5


def _frammenti_pagina(page, origin_x: float, origin_y: float) -> list[dict[str, Any]]:
    frammenti: list[dict[str, Any]] = []

    def visitor(text, cm, tm, _font_dict, font_size):
        testo = str(text or "")
        if not testo.strip():
            return
        a, b, _c, _d, e, f = [float(v) for v in tm]
        m_a, m_b, m_c, m_d, m_e, m_f = [float(v) for v in cm]
        x = e * m_a + f * m_c + m_e - origin_x
        y = e * m_b + f * m_d + m_f - origin_y
        dir_x = a * m_a + b * m_c
        dir_y = a * m_b + b * m_d
        scala = max((dir_x ** 2 + dir_y ** 2) ** 0.5, 0.01)
        dimensione = max(float(font_size or 0) * scala, 4.0)
        lunghezza = _larghezza_testo(testo.strip(), dimensione)
        if abs(dir_y) > abs(dir_x):
            if dir_y > 0:
                box = (x - dimensione, y, x + dimensione * 0.3, y + lunghezza)
            else:
                box = (x - dimensione * 0.3, y - lunghezza, x + dimensione, y)
            verticale = True
        else:
            if dir_x >= 0:
                box = (x, y - dimensione * 0.3, x + lunghezza, y + dimensione)
            else:
                box = (x - lunghezza, y - dimensione, x, y + dimensione * 0.3)
            verticale = False
        frammenti.append({"testo": testo.strip(), "box": box, "verticale": verticale})

    page.extract_text(visitor_text=visitor)
    for riferimento in page.get("/Annots", []) or []:
        try:
            annotazione = riferimento.get_object()
            if str(annotazione.get("/Subtype") or "") != "/Widget":
                continue
            rect = [float(v) for v in annotazione.get("/Rect") or []]
        except Exception:
            continue
        if len(rect) == 4 and abs(rect[2] - rect[0]) > 1 and abs(rect[3] - rect[1]) > 1:
            x0, x1 = sorted((rect[0] - origin_x, rect[2] - origin_x))
            y0, y1 = sorted((rect[1] - origin_y, rect[3] - origin_y))
            frammenti.append({"testo": "", "box": (x0, y0, x1, y1), "verticale": False})
    return frammenti


def _zona_frammento(box: tuple[float, float, float, float], verticale: bool, width: float, height: float) -> str:
    x0, y0, x1, y1 = box
    if verticale and x1 <= width * 0.12:
        return VISIBLE_SIGNATURE_ZONE_SINISTRA
    if verticale and x0 >= width * 0.88:
        return VISIBLE_SIGNATURE_ZONE_DESTRA
    if y1 <= height * 0.1:
        return VISIBLE_SIGNATURE_ZONE_BASSO
    if y0 >= height * 0.9:
        return VISIBLE_SIGNATURE_ZONE_ALTO
    return "corpo"


def analizza_firme_visibili(pdf_data: bytes) -> dict[str, Any]:
    """Timbri di firma già visibili (testo «Firmato Da: … Emesso Da: … Serial#: …») e ingombri delle pagine."""

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_data), strict=False)
    pagine: list[dict[str, Any]] = []
    timbri: list[dict[str, str]] = []
    for indice, page in enumerate(reader.pages):
        box = getattr(page, "cropbox", None) or page.mediabox
        width, height = float(box.width), float(box.height)
        frammenti = _frammenti_pagina(page, float(box.left), float(box.bottom))
        for frammento in frammenti:
            timbro = _parse_timbro(frammento["testo"])
            if timbro:
                timbro["zona"] = _zona_frammento(frammento["box"], frammento["verticale"], width, height)
                timbro["pagina"] = str(indice + 1)
                if not any(
                    t["firmatario"] == timbro["firmatario"] and t["zona"] == timbro["zona"] for t in timbri
                ):
                    timbri.append(timbro)
        pagine.append({"width": width, "height": height, "frammenti": frammenti})
    try:
        metadati = str((reader.metadata or {}).get(VISIBLE_SIGNATURE_METADATA_KEY) or "")
    except Exception:
        metadati = ""
    return {
        "pagine": pagine,
        "timbri": timbri,
        "timbri_metadati": _timbri_da_metadati(metadati),
        "metadati": metadati,
    }


def timbro_firmatario_presente(
    pdf_data: bytes,
    *,
    intestatario: str = "",
    serial: str = "",
    analisi: dict[str, Any] | None = None,
) -> dict[str, str] | None:
    """Timbro visibile dello stesso firmatario già presente nel PDF, se c'è."""

    if not pdf_data.lstrip().startswith(b"%PDF"):
        return None
    try:
        dati = analisi or analizza_firme_visibili(pdf_data)
    except Exception:
        return None
    for timbro in [*dati["timbri"], *dati["timbri_metadati"]]:
        if stesso_firmatario(timbro, intestatario=intestatario, serial=serial):
            return timbro
    return None


def _si_sovrappone(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _intervallo_libero(frammenti: list[dict[str, Any]], y0: float, y1: float, x_min: float, x_max: float) -> tuple[float, float]:
    occupati = sorted(
        (max(f["box"][0], x_min), min(f["box"][2], x_max))
        for f in frammenti
        if f["box"][1] < y1 and y0 < f["box"][3] and f["box"][2] > x_min and f["box"][0] < x_max
    )
    migliore = (0.0, 0.0)
    cursore = x_min
    for inizio, fine in occupati:
        if inizio - cursore > migliore[1] - migliore[0]:
            migliore = (cursore, inizio)
        cursore = max(cursore, fine)
    if x_max - cursore > migliore[1] - migliore[0]:
        migliore = (cursore, x_max)
    return migliore


def _rettangolo_laterale(zona: str, width: float, height: float, lunghezza_testo: float) -> tuple[float, float, float, float]:
    fine = min(height, VISIBLE_SIGNATURE_COCCARDA_HEIGHT_PT + VISIBLE_SIGNATURE_LATERAL_SEAL_TEXT_GAP_PT + lunghezza_testo + 12.0)
    if zona == VISIBLE_SIGNATURE_ZONE_SINISTRA:
        return (0.0, 0.0, 22.0, fine)
    return (width - 22.0, 0.0, width, fine)


def scegli_zona_firma(
    analisi: dict[str, Any],
    *,
    lunghezza_testo_laterale: float,
    larghezza_fascia: float,
    preferita: str = VISIBLE_SIGNATURE_ZONE_DESTRA,
) -> dict[str, Any]:
    """Prima zona libera fra margine destro, sinistro, basso e alto dell'ultima pagina."""

    pagine = analisi["pagine"]
    ordine = [VISIBLE_SIGNATURE_ZONE_DESTRA, VISIBLE_SIGNATURE_ZONE_SINISTRA, VISIBLE_SIGNATURE_ZONE_BASSO, VISIBLE_SIGNATURE_ZONE_ALTO]
    if preferita in ordine:
        ordine.remove(preferita)
        ordine.insert(0, preferita)
    ultima = pagine[-1]
    migliore_fascia: dict[str, Any] | None = None
    for zona in ordine:
        if zona in {VISIBLE_SIGNATURE_ZONE_DESTRA, VISIBLE_SIGNATURE_ZONE_SINISTRA}:
            if all(
                not any(
                    _si_sovrappone(f["box"], _rettangolo_laterale(zona, p["width"], p["height"], lunghezza_testo_laterale))
                    for f in p["frammenti"]
                )
                for p in pagine
            ):
                return {"zona": zona, "pagine": "tutte"}
            continue
        width, height = ultima["width"], ultima["height"]
        if zona == VISIBLE_SIGNATURE_ZONE_BASSO:
            y0, y1 = 4.0, 4.0 + VISIBLE_SIGNATURE_BAND_HEIGHT_PT
        else:
            y0, y1 = height - 4.0 - VISIBLE_SIGNATURE_BAND_HEIGHT_PT, height - 4.0
        x0, x1 = _intervallo_libero(
            ultima["frammenti"], y0, y1, VISIBLE_SIGNATURE_BAND_EDGE_PT, width - VISIBLE_SIGNATURE_BAND_EDGE_PT
        )
        candidato = {"zona": zona, "pagine": "ultima", "x0": x0, "x1": x1, "y0": y0, "y1": y1}
        if x1 - x0 >= min(larghezza_fascia, width - 2 * VISIBLE_SIGNATURE_BAND_EDGE_PT):
            return candidato
        if migliore_fascia is None or (x1 - x0) > (migliore_fascia["x1"] - migliore_fascia["x0"]):
            migliore_fascia = candidato
    # Nessuna zona completamente libera: la fascia con più spazio, con il testo ridotto.
    return migliore_fascia or {"zona": VISIBLE_SIGNATURE_ZONE_BASSO, "pagine": "ultima", "x0": VISIBLE_SIGNATURE_BAND_EDGE_PT,
                               "x1": ultima["width"] - VISIBLE_SIGNATURE_BAND_EDGE_PT, "y0": 4.0, "y1": 4.0 + VISIBLE_SIGNATURE_BAND_HEIGHT_PT}


def _righe_fascia(
    *,
    intestatario: str,
    data_firma: Any,
    luogo: str,
    issuer: str,
    serial: str,
    datetime_mode: str,
) -> list[str]:
    nome = _normalize_visible_signature_name(intestatario, uppercase=True, force_avv_prefix=True)
    prima = " ".join(
        parte for parte in (
            f"Firmato Da: {nome}" if nome else "Firmato Da:",
            f"Emesso Da: {issuer}" if issuer else "",
            f"Serial#: {serial}" if serial else "",
        ) if parte
    )
    data = format_visible_signature_datetime(data_firma, datetime_mode=datetime_mode)
    seconda = ", ".join(
        parte for parte in (
            f"Luogo firma: {str(luogo).upper()}" if luogo else "",
            f"Data e ora firma: {data}" if data else "",
        ) if parte
    )
    return [riga for riga in (prima, seconda) if riga]


def _draw_visible_signature_band(overlay, *, posizione: dict[str, Any], righe: list[str], color) -> None:
    font_name, _bold = _register_visible_signature_fonts()
    x0, x1 = float(posizione["x0"]), float(posizione["x1"])
    y0, y1 = float(posizione["y0"]), float(posizione["y1"])
    testo_x = x0 + VISIBLE_SIGNATURE_COCCARDA_WIDTH_PT + 4.0
    disponibile = max(x1 - testo_x, 40.0)
    dimensione = 7.0
    while dimensione > 5.0 and max(overlay.stringWidth(r, font_name, dimensione) for r in righe) > disponibile:
        dimensione -= 0.25
    righe = [_fit_text_for_width(overlay, r, font_name, dimensione, disponibile) for r in righe]
    interlinea = dimensione + 2.0
    base = y0 + (y1 - y0 + interlinea * (len(righe) - 1)) / 2.0 - dimensione * 0.35
    overlay.saveState()
    overlay.setFillColor(color)
    overlay.setFont(font_name, dimensione)
    for indice, riga in enumerate(righe):
        overlay.drawString(testo_x, base - indice * interlinea, riga)
    overlay.restoreState()
    _draw_visible_signature_seal(
        overlay,
        anchor_x=x0 + VISIBLE_SIGNATURE_COCCARDA_HALF_WIDTH_PT,
        anchor_y=(y0 + y1) / 2.0,
        scale=min(1.0, (y1 - y0) / VISIBLE_SIGNATURE_COCCARDA_HEIGHT_PT),
    )


def _draw_visible_signature_side_mark_left(overlay, *, height: float, color, side_text: str) -> None:
    font_name, _bold = _register_visible_signature_fonts()
    font_size = VISIBLE_SIGNATURE_LATERAL_FONT_SIZE_PT
    seal_anchor_x = VISIBLE_SIGNATURE_LATERAL_SEAL_RIGHT_MARGIN_PT + VISIBLE_SIGNATURE_COCCARDA_HALF_WIDTH_PT
    seal_anchor_y = VISIBLE_SIGNATURE_LATERAL_SEAL_BOTTOM_MARGIN_PT + VISIBLE_SIGNATURE_COCCARDA_HEIGHT_PT / 2.0
    text_start_y = seal_anchor_y + VISIBLE_SIGNATURE_COCCARDA_HEIGHT_PT / 2.0 + VISIBLE_SIGNATURE_LATERAL_SEAL_TEXT_GAP_PT
    text_length = max(height - text_start_y - VISIBLE_SIGNATURE_LATERAL_RIGHT_MARGIN_PT, 40.0)
    side_text = _fit_text_for_width(overlay, side_text, font_name, font_size, text_length)
    overlay.saveState()
    overlay.setFillColor(color)
    overlay.setFont(font_name, font_size)
    overlay.translate(VISIBLE_SIGNATURE_LATERAL_RIGHT_MARGIN_PT + font_size * 0.75, text_start_y)
    overlay.rotate(90)
    overlay.drawString(0, 0, side_text)
    overlay.restoreState()
    _draw_visible_signature_seal(overlay, anchor_x=seal_anchor_x, anchor_y=seal_anchor_y)


def _apply_visible_signature_stamp_positioned(
    pdf_data: bytes,
    *,
    analisi: dict[str, Any],
    preferita: str,
    intestatario: str,
    data_firma: Any,
    luogo: str,
    issuer: str,
    serial: str,
    datetime_mode: str,
) -> bytes:
    """Aggiunge il timbro di un nuovo firmatario nella prima zona libera del documento."""

    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.colors import Color
    from reportlab.pdfgen import canvas

    regular_font_name, _bold_font_name = _register_visible_signature_fonts()
    side_text = _build_visible_signature_side_text(
        intestatario=intestatario, data_firma=data_firma, luogo=luogo,
        issuer=issuer, serial=serial, datetime_mode=datetime_mode,
    )
    righe = _righe_fascia(
        intestatario=intestatario, data_firma=data_firma, luogo=luogo,
        issuer=issuer, serial=serial, datetime_mode=datetime_mode,
    )
    larghezza_fascia = VISIBLE_SIGNATURE_COCCARDA_WIDTH_PT + 6.0 + max(_larghezza_testo(r, 6.0) for r in righe)
    posizione = scegli_zona_firma(
        analisi,
        lunghezza_testo_laterale=_larghezza_testo(side_text, VISIBLE_SIGNATURE_LATERAL_FONT_SIZE_PT),
        larghezza_fascia=max(larghezza_fascia, VISIBLE_SIGNATURE_BAND_MIN_WIDTH_PT),
        preferita=preferita,
    )
    writer = PdfWriter(clone_from=io.BytesIO(pdf_data))
    page_count = len(writer.pages)
    indici = range(page_count) if posizione["pagine"] == "tutte" else [page_count - 1]
    muted = Color(0.23, 0.23, 0.23)
    for index in indici:
        page = writer.pages[index]
        page_box = getattr(page, "cropbox", None) or page.mediabox
        width, height = float(page_box.width), float(page_box.height)
        overlay_buffer = io.BytesIO()
        overlay = canvas.Canvas(overlay_buffer, pagesize=(width, height), initialFontName=regular_font_name,
                                initialFontSize=VISIBLE_SIGNATURE_LATERAL_FONT_SIZE_PT)
        if posizione["zona"] == VISIBLE_SIGNATURE_ZONE_DESTRA:
            _draw_visible_signature_side_mark(
                overlay, width=width, height=height, color=muted,
                layout=compute_visible_signature_layout(width=width, height=height, mode=VISIBLE_SIGNATURE_MODE_LATERALE),
                intestatario=intestatario, data_firma=data_firma, luogo=luogo,
                issuer=issuer, serial=serial, datetime_mode=datetime_mode,
            )
        elif posizione["zona"] == VISIBLE_SIGNATURE_ZONE_SINISTRA:
            _draw_visible_signature_side_mark_left(overlay, height=height, color=muted, side_text=side_text)
        else:
            _draw_visible_signature_band(overlay, posizione=posizione, righe=righe, color=muted)
        overlay.save()
        overlay_buffer.seek(0)
        page.merge_translated_page(PdfReader(overlay_buffer).pages[0], float(page_box.left), float(page_box.bottom))
    reader = PdfReader(io.BytesIO(pdf_data))
    try:
        metadata = {key: str(value) for key, value in (reader.metadata or {}).items() if key and value is not None}
    except Exception:
        metadata = {}
    stamp_text = build_visible_signature_text(
        intestatario=intestatario, data_firma=data_firma, luogo=luogo,
        issuer=issuer, serial=serial, datetime_mode=datetime_mode,
    )
    blocco = f"{stamp_text}\nModalita firma visibile: {posizione['zona']}\nPagine timbrate: {len(list(indici))}"
    precedente = metadata.get(VISIBLE_SIGNATURE_METADATA_KEY, "")
    metadata[VISIBLE_SIGNATURE_METADATA_KEY] = f"{precedente}{_TIMBRO_BLOCK_SEPARATOR}{blocco}" if precedente else blocco
    writer.add_metadata(metadata)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _cert_info(cert) -> dict[str, str]:
    try:
        soggetto = cert.subject.native
        emittente = cert.issuer.native
        return {
            "firmatario": str(soggetto.get("common_name") or ""),
            "emittente": str(emittente.get("common_name") or ""),
            "seriale": format(int(cert.serial_number), "X"),
        }
    except Exception:
        return {}


def _firmatari_cms(dati: bytes) -> tuple[list[dict[str, str]], bytes | None]:
    from asn1crypto import cms

    info = cms.ContentInfo.load(dati)
    if info["content_type"].native != "signed_data":
        return [], None
    signed = info["content"]
    certificati = [c.chosen for c in (signed["certificates"] or []) if c.name == "certificate"]
    firmatari: list[dict[str, str]] = []
    for signer in signed["signer_infos"]:
        sid = signer["sid"]
        cert = None
        if sid.name == "issuer_and_serial_number":
            seriale = sid.chosen["serial_number"].native
            cert = next((c for c in certificati if c.serial_number == seriale), None)
        elif certificati:
            cert = certificati[0]
        dati_cert = _cert_info(cert) if cert is not None else {}
        if dati_cert:
            firmatari.append(dati_cert)
    contenuto = signed["encap_content_info"]["content"].native
    if isinstance(contenuto, str):
        contenuto = contenuto.encode("latin-1")
    return firmatari, contenuto if isinstance(contenuto, bytes) else None


def firme_digitali_presenti(documento: bytes) -> list[dict[str, str]]:
    """Titolari delle firme digitali già apposte (buste CAdES .p7m e firme PAdES nel PDF)."""

    firme: list[dict[str, str]] = []
    dati: bytes | None = documento
    for _livello in range(3):
        if not dati or dati.lstrip().startswith(b"%PDF"):
            break
        try:
            firmatari, dati = _firmatari_cms(dati)
        except Exception:
            dati = None
            break
        firme.extend(firmatari)
    if dati and dati.lstrip().startswith(b"%PDF"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(dati), strict=False)
            for campo in (reader.get_fields() or {}).values():
                valore = campo.get("/V") if hasattr(campo, "get") else None
                valore = valore.get_object() if hasattr(valore, "get_object") else valore
                contenuto = valore.get("/Contents") if hasattr(valore, "get") else None
                if contenuto:
                    firmatari, _ = _firmatari_cms(bytes(contenuto))
                    firme.extend(firmatari)
        except Exception:
            pass
    return firme


def contenuto_pdf(documento: bytes) -> bytes | None:
    dati: bytes | None = documento
    for _livello in range(3):
        if not dati or dati.lstrip().startswith(b"%PDF"):
            return dati or None
        try:
            _firmatari, dati = _firmatari_cms(dati)
        except Exception:
            return None
    return None


def verifica_firma_gia_presente(documento: bytes, *, intestatario: str = "", serial: str = "") -> None:
    """Ferma una nuova firma se lo stesso certificato ha già firmato il documento."""

    for firma in firme_digitali_presenti(documento):
        if not stesso_firmatario(firma, intestatario=intestatario, serial=serial):
            continue
        pdf = contenuto_pdf(documento)
        visibile = bool(pdf and timbro_firmatario_presente(pdf, intestatario=firma["firmatario"], serial=firma["seriale"]))
        nome = firma.get("firmatario") or _nome_da_soggetto(intestatario)
        raise FirmaGiaPresente(
            f"Il documento è già firmato da {nome} con lo stesso dispositivo"
            + (" e la firma è già visibile sul documento" if visibile else "")
            + ": non viene firmato di nuovo.",
            firmatario=nome,
        )


def ha_timbro_visibile(pdf_data: bytes, *, intestatario: str = "", serial: str = "") -> bool:
    """Timbro IUSENTRA oppure timbro dello stesso firmatario già presente (per esempio copia dal portale)."""

    if has_visible_signature_stamp(pdf_data):
        return True
    return timbro_firmatario_presente(pdf_data, intestatario=intestatario, serial=serial) is not None


def riquadro_firma_pades(pdf_data: bytes, *, altezza: float = 45.0) -> tuple[int, int, int, int]:
    """Riquadro dell'aspetto PAdES sull'ultima pagina, in una fascia libera da testo e timbri."""

    larghezza = 595.0
    try:
        analisi = analizza_firme_visibili(pdf_data)
        ultima = analisi["pagine"][-1]
        larghezza, alta = ultima["width"], ultima["height"]
        for y0, y1 in ((6.0, 6.0 + altezza), (alta - 6.0 - altezza, alta - 6.0)):
            x0, x1 = _intervallo_libero(
                ultima["frammenti"], y0, y1, VISIBLE_SIGNATURE_BAND_EDGE_PT, larghezza - VISIBLE_SIGNATURE_BAND_EDGE_PT
            )
            if x1 - x0 >= 200.0:
                return (int(x0), int(y0), int(x1), int(y1))
    except Exception:
        pass
    return (20, 10, max(40, int(larghezza) - 20), 55)


def apply_visible_signature_stamp(
    pdf_data: bytes,
    *,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
    issuer: str = "",
    serial: str = "",
    mode: str = VISIBLE_SIGNATURE_MODE_LATERALE,
    datetime_mode: str = VISIBLE_SIGNATURE_DATETIME_MODE_DATE_TIME,
) -> bytes:
    if not pdf_data.startswith(b"%PDF"):
        return pdf_data

    try:
        analisi: dict[str, Any] | None = analizza_firme_visibili(pdf_data)
    except Exception:
        analisi = None
    if analisi is None:
        if has_visible_signature_stamp(pdf_data):
            return pdf_data
    else:
        if timbro_firmatario_presente(pdf_data, intestatario=intestatario, serial=serial, analisi=analisi):
            # La firma dello stesso titolare è già visibile: il timbro non si ripete.
            return pdf_data
        if analisi["timbri"] or analisi["timbri_metadati"] or has_visible_signature_stamp(pdf_data):
            preferita = VISIBLE_SIGNATURE_ZONE_DESTRA
            if normalize_visible_signature_mode(mode) != VISIBLE_SIGNATURE_MODE_LATERALE:
                preferita = VISIBLE_SIGNATURE_ZONE_BASSO
            try:
                return _apply_visible_signature_stamp_positioned(
                    pdf_data, analisi=analisi, preferita=preferita, intestatario=intestatario,
                    data_firma=data_firma, luogo=luogo, issuer=issuer, serial=serial,
                    datetime_mode=datetime_mode,
                )
            except Exception as exc:
                raise RuntimeError(
                    "Impossibile collocare il timbro di firma accanto alle firme già presenti. "
                    "La firma è stata interrotta per non sovrapporre i timbri."
                ) from exc

    stamp_text = build_visible_signature_text(
        intestatario=intestatario,
        data_firma=data_firma,
        luogo=luogo,
        issuer=issuer,
        serial=serial,
        datetime_mode=datetime_mode,
    )
    resolved_mode = normalize_visible_signature_mode(mode)
    if not stamp_text:
        return pdf_data

    try:
        from pypdf import PdfReader, PdfWriter
        from reportlab.lib.colors import Color
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise RuntimeError(
            "Impossibile preparare il timbro di firma visibile conforme a PDF/A. "
            "La firma non è stata eseguita."
        ) from exc

    try:
        regular_font_name, _bold_font_name = _register_visible_signature_fonts()
        reader = PdfReader(io.BytesIO(pdf_data))
        writer = PdfWriter(clone_from=io.BytesIO(pdf_data))
        page_count = len(reader.pages)
        if page_count == 0:
            return pdf_data

        signer_name = str(intestatario or "").strip()
        signature_place = str(luogo or "").strip()

        for index in range(page_count):
            page = writer.pages[index]
            page_box = getattr(page, "cropbox", None) or page.mediabox
            width = float(page_box.width)
            height = float(page_box.height)
            layout = compute_visible_signature_layout(
                width=width,
                height=height,
                mode=resolved_mode,
            )

            overlay_buffer = io.BytesIO()
            overlay = canvas.Canvas(
                overlay_buffer,
                pagesize=(width, height),
                initialFontName=regular_font_name,
                initialFontSize=VISIBLE_SIGNATURE_LATERAL_FONT_SIZE_PT,
            )

            muted = Color(0.23, 0.23, 0.23)
            if resolved_mode in {VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA, VISIBLE_SIGNATURE_MODE_BASSO_DESTRA}:
                _draw_visible_signature_bottom_text(
                    overlay,
                    width=width,
                    height=height,
                    layout=layout,
                    color=muted,
                    intestatario=signer_name,
                    data_firma=data_firma,
                    luogo=signature_place,
                    datetime_mode=datetime_mode,
                )
            else:
                _draw_visible_signature_side_mark(
                    overlay,
                    width=width,
                    height=height,
                    layout=layout,
                    color=muted,
                    intestatario=signer_name,
                    data_firma=data_firma,
                    luogo=signature_place,
                    issuer=issuer,
                    serial=serial,
                    datetime_mode=datetime_mode,
                )

            overlay.save()
            overlay_buffer.seek(0)
            overlay_page = PdfReader(overlay_buffer).pages[0]
            page.merge_page(overlay_page)

        metadata = {}
        try:
            existing_metadata = reader.metadata or {}
            metadata = {
                key: str(value)
                for key, value in existing_metadata.items()
                if key and value is not None
            }
        except Exception:
            metadata = {}
        metadata[VISIBLE_SIGNATURE_METADATA_KEY] = (
            f"{stamp_text}\nModalita firma visibile: {resolved_mode}\nPagine timbrate: {page_count}"
        )
        writer.add_metadata(metadata)

        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        return output_buffer.getvalue()
    except Exception as exc:
        raise RuntimeError(
            "Impossibile applicare il timbro di firma visibile con font "
            "incorporato. La firma è stata interrotta per preservare la "
            "conformità PDF/A."
        ) from exc


def prepare_document_for_signature(
    document_data: bytes,
    *,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
    issuer: str = "",
    serial: str = "",
    mode: str = VISIBLE_SIGNATURE_MODE_LATERALE,
    datetime_mode: str = VISIBLE_SIGNATURE_DATETIME_MODE_DATE_TIME,
) -> bytes:
    if not document_data.startswith(b"%PDF"):
        return document_data
    return apply_visible_signature_stamp(
        document_data,
        intestatario=intestatario,
        data_firma=data_firma,
        luogo=luogo,
        issuer=issuer,
        serial=serial,
        mode=mode,
        datetime_mode=datetime_mode,
    )


def apply_visible_signature_stamp_from_firme(
    pdf_data: bytes,
    firme: list[dict] | None,
    *,
    city: str = "",
    address: str = "",
    mode: str = VISIBLE_SIGNATURE_MODE_LATERALE,
    datetime_mode: str = VISIBLE_SIGNATURE_DATETIME_MODE_DATE_TIME,
) -> bytes:
    if not firme:
        return pdf_data

    signature = (firme or [{}])[0] or {}
    return apply_visible_signature_stamp(
        pdf_data,
        intestatario=str(signature.get("intestatario") or signature.get("cn") or "").strip(),
        data_firma=signature.get("data_firma"),
        luogo=resolve_visible_signature_place(city=city, address=address),
        issuer=str(signature.get("emittente_cn") or signature.get("emittente") or "").strip(),
        serial=str(signature.get("seriale") or "").strip(),
        mode=mode,
        datetime_mode=datetime_mode,
    )


def _build_visible_signature_location_line(
    *,
    luogo: str = "",
    data_firma: Any = None,
    datetime_mode: str = VISIBLE_SIGNATURE_DATETIME_MODE_DATE_TIME,
) -> str:
    luogo_value = str(luogo or "").strip()
    data_value = format_visible_signature_datetime(data_firma, datetime_mode=datetime_mode)
    if luogo_value and data_value:
        return f"{luogo_value} {data_value}"
    return luogo_value or data_value


def _build_visible_signature_side_text(
    *,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
    issuer: str = "",
    serial: str = "",
    datetime_mode: str = VISIBLE_SIGNATURE_DATETIME_MODE_DATE_TIME,
) -> str:
    segments: list[str] = []
    signer_name = _normalize_visible_signature_name(
        intestatario,
        uppercase=True,
        force_avv_prefix=True,
    )
    date_value = format_visible_signature_datetime(data_firma, datetime_mode=datetime_mode)
    place_value = str(luogo or "").strip()

    issuer_value = str(issuer or "").strip()
    serial_value = str(serial or "").strip()

    if signer_name:
        segments.append(f"Firmato Da: {signer_name}")
    if date_value:
        segments.append(f"Data e ora firma: {date_value}")
    if place_value:
        segments.append(f"Luogo firma: {place_value.upper()}")
    if issuer_value:
        segments.append(f"Emesso Da: {issuer_value}")
    if serial_value:
        segments.append(f"Serial#: {serial_value}")
    return ", ".join(segment for segment in segments if segment.strip())


def _build_visible_signature_bottom_lines(
    *,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
    datetime_mode: str = VISIBLE_SIGNATURE_DATETIME_MODE_DATE_TIME,
) -> tuple[str, str]:
    signer_name = _normalize_visible_signature_name(
        intestatario,
        uppercase=True,
        force_avv_prefix=True,
    )
    place_value = str(luogo or "").strip()
    date_value = format_visible_signature_datetime(data_firma, datetime_mode=datetime_mode)
    if date_value:
        date_value = date_value.replace(" alle ore ", " ore ")

    first_line = "Per autentica e sottoscrizione"

    second_line = "Firmato Da:"
    if signer_name:
        second_line = f"{second_line} {signer_name}"
    if date_value:
        second_line = f"{second_line} in data {date_value}"
    if place_value:
        second_line = f"{second_line} Luogo: {place_value}"
    return first_line, second_line


def _fit_text_for_width(overlay, text: str, font_name: str, font_size: float, max_width: float) -> str:
    value = str(text or "")
    if not value:
        return ""
    try:
        if overlay.stringWidth(value, font_name, font_size) <= max_width:
            return value
        suffix = "..."
        while value and overlay.stringWidth(value + suffix, font_name, font_size) > max_width:
            value = value[:-1]
        return (value.rstrip() + suffix) if value else suffix
    except Exception:
        max_chars = max(int(max_width / max(font_size * 0.55, 1)), 8)
        return value if len(value) <= max_chars else value[: max_chars - 3].rstrip() + "..."


def _draw_visible_signature_side_mark(
    overlay,
    *,
    width: float,
    height: float,
    color,
    layout: dict[str, float | str | int] | None = None,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
    issuer: str = "",
    serial: str = "",
    datetime_mode: str = VISIBLE_SIGNATURE_DATETIME_MODE_DATE_TIME,
) -> None:
    side_text = _build_visible_signature_side_text(
        intestatario=intestatario,
        data_firma=data_firma,
        luogo=luogo,
        issuer=issuer,
        serial=serial,
        datetime_mode=datetime_mode,
    )
    layout = layout or compute_visible_signature_layout(
        width=width,
        height=height,
        mode=VISIBLE_SIGNATURE_MODE_LATERALE,
    )
    text_right_edge = min(
        max(float(layout["x"]) + float(layout["box_width"]), CM_TO_PT),
        max(width - VISIBLE_SIGNATURE_LATERAL_RIGHT_MARGIN_PT, CM_TO_PT),
    )
    seal_anchor_x = min(
        max(width - VISIBLE_SIGNATURE_LATERAL_SEAL_RIGHT_MARGIN_PT - VISIBLE_SIGNATURE_COCCARDA_HALF_WIDTH_PT, 16.0),
        max(width - VISIBLE_SIGNATURE_COCCARDA_HALF_WIDTH_PT, 16.0),
    )
    seal_anchor_y = min(
        max(
            VISIBLE_SIGNATURE_LATERAL_SEAL_BOTTOM_MARGIN_PT + (VISIBLE_SIGNATURE_COCCARDA_HEIGHT_PT / 2.0),
            VISIBLE_SIGNATURE_COCCARDA_HEIGHT_PT / 2.0,
        ),
        max(height - (VISIBLE_SIGNATURE_COCCARDA_HEIGHT_PT / 2.0), VISIBLE_SIGNATURE_COCCARDA_HEIGHT_PT / 2.0),
    )
    text_start_y = min(
        max(
            seal_anchor_y
            + (VISIBLE_SIGNATURE_COCCARDA_HEIGHT_PT / 2.0)
            + VISIBLE_SIGNATURE_LATERAL_SEAL_TEXT_GAP_PT,
            0.0,
        ),
        max(height - 10.0, 0.0),
    )
    text_length = max(height - text_start_y - VISIBLE_SIGNATURE_LATERAL_RIGHT_MARGIN_PT, 40.0)
    font_name, _bold_font_name = _register_visible_signature_fonts()
    font_size = VISIBLE_SIGNATURE_LATERAL_FONT_SIZE_PT
    side_text = _fit_text_for_width(overlay, side_text, font_name, font_size, text_length)

    overlay.setFillColor(color)
    overlay.setFont(font_name, font_size)
    overlay.saveState()
    translate_x = max(text_right_edge - VISIBLE_SIGNATURE_LATERAL_TEXT_INSET_PT, CM_TO_PT)
    translate_y = text_start_y
    overlay.translate(translate_x, translate_y)
    overlay.rotate(90)
    overlay.drawString(0, 0, side_text)
    overlay.restoreState()
    _draw_visible_signature_seal(
        overlay,
        anchor_x=seal_anchor_x,
        anchor_y=seal_anchor_y,
    )


def _clear_visible_signature_zones(
    overlay,
    *,
    width: float,
    height: float,
    mode: str = VISIBLE_SIGNATURE_MODE_LATERALE,
    layout: dict[str, float | str | int] | None = None,
) -> None:
    try:
        from reportlab.lib.colors import Color
    except Exception:
        return

    white = Color(1, 1, 1)
    layout = layout or compute_visible_signature_layout(width=width, height=height, mode=mode)
    pad = 8.0
    block_x = max(float(layout["x"]) - pad, 0.0)
    block_y = max(float(layout["y"]) - pad, 0.0)
    block_width = min(float(layout["box_width"]) + pad * 2, max(width - block_x, 0.0))
    block_height = min(float(layout["box_height"]) + pad * 2, max(height - block_y, 0.0))

    overlay.saveState()
    overlay.setFillColor(white)
    overlay.setStrokeColor(white)
    overlay.rect(
        block_x,
        block_y,
        block_width,
        block_height,
        stroke=0,
        fill=1,
    )
    overlay.restoreState()


def _draw_visible_signature_bottom_text(
    overlay,
    *,
    width: float,
    height: float,
    color,
    layout: dict[str, float | str | int] | None = None,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
    datetime_mode: str = VISIBLE_SIGNATURE_DATETIME_MODE_DATE_TIME,
) -> None:
    layout = layout or compute_visible_signature_layout(
        width=width,
        height=height,
        mode=VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
    )
    align = str(layout.get("align") or "right")
    font_name, _bold_font_name = _register_visible_signature_fonts()
    font_size = 11
    line_one, line_two = _build_visible_signature_bottom_lines(
        intestatario=intestatario,
        data_firma=data_firma,
        luogo=luogo,
        datetime_mode=datetime_mode,
    )
    max_text_width = max(float(layout["box_width"]) - 58.0, 80.0)
    while font_size > 8 and max(
        overlay.stringWidth(line_one, font_name, font_size),
        overlay.stringWidth(line_two, font_name, font_size) if line_two else 0,
    ) > max_text_width:
        font_size -= 0.5
    line_one = _fit_text_for_width(overlay, line_one, font_name, font_size, max_text_width)
    line_two = _fit_text_for_width(overlay, line_two, font_name, font_size, max_text_width)

    overlay.saveState()
    overlay.setFillColor(color)
    overlay.setFont(font_name, font_size)
    baseline_y = float(layout["y"]) + 14.0
    x_left = float(layout["x"]) + 48.0
    x_right = min(float(layout["x"]) + float(layout["box_width"]), width - CM_TO_PT)
    if align == "left":
        if line_two:
            overlay.drawString(x_left, baseline_y + 14, line_one)
            overlay.drawString(x_left, baseline_y, line_two)
        else:
            overlay.drawString(x_left, baseline_y + 7, line_one)
    else:
        if line_two:
            overlay.drawRightString(x_right, baseline_y + 14, line_one)
            overlay.drawRightString(x_right, baseline_y, line_two)
        else:
            overlay.drawRightString(x_right, baseline_y + 7, line_one)
    overlay.restoreState()

    line_one_width = overlay.stringWidth(line_one, font_name, font_size)
    line_two_width = overlay.stringWidth(line_two, font_name, font_size) if line_two else 0
    text_width = max(line_one_width, line_two_width)
    if align == "left":
        seal_anchor_x = max(float(layout["x"]) + 18.0, 18.0)
    else:
        seal_anchor_x = max(x_right - text_width - 28.0, float(layout["x"]) + 18.0)
    seal_anchor_x = min(seal_anchor_x, max(width - 16.0, 16.0))
    seal_anchor_y = min(max(float(layout["y"]) + 17.0, 17.0), max(height - 17.0, 17.0))
    _draw_visible_signature_seal(
        overlay,
        anchor_x=seal_anchor_x,
        anchor_y=seal_anchor_y,
        scale=1.05,
    )


def _draw_visible_signature_bottom_right_text(
    overlay,
    *,
    width: float,
    height: float,
    color,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
) -> None:
    """Wrapper retrocompatibile per test e chiamanti legacy."""
    return _draw_visible_signature_bottom_text(
        overlay,
        width=width,
        height=height,
        layout=compute_visible_signature_layout(
            width=width,
            height=height,
            mode=VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
        ),
        color=color,
        intestatario=intestatario,
        data_firma=data_firma,
        luogo=luogo,
    )


def _draw_visible_signature_bottom_left_text(
    overlay,
    *,
    width: float,
    height: float,
    color,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
) -> None:
    """Wrapper retrocompatibile per test e chiamanti legacy."""
    return _draw_visible_signature_bottom_text(
        overlay,
        width=width,
        height=height,
        layout=compute_visible_signature_layout(
            width=width,
            height=height,
            mode=VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA,
        ),
        color=color,
        intestatario=intestatario,
        data_firma=data_firma,
        luogo=luogo,
    )


def _draw_visible_signature_coccarda_image(
    overlay,
    *,
    anchor_x: float,
    anchor_y: float,
    scale: float = 1.0,
) -> bool:
    try:
        from reportlab.lib.utils import ImageReader
    except Exception:
        return False

    try:
        image_bytes = base64.b64decode(VISIBLE_SIGNATURE_COCCARDA_PNG_B64)
        image = ImageReader(io.BytesIO(image_bytes))
        original_width, original_height = image.getSize()
        target_height = VISIBLE_SIGNATURE_COCCARDA_HEIGHT_PT * max(float(scale or 1.0), 0.5)
        target_width = target_height * (float(original_width) / max(float(original_height), 1.0))
        overlay.drawImage(
            image,
            float(anchor_x) - target_width / 2,
            float(anchor_y) - target_height / 2,
            width=target_width,
            height=target_height,
            preserveAspectRatio=True,
            mask="auto",
        )
        return True
    except Exception:
        return False


def _draw_visible_signature_seal(
    overlay,
    *,
    anchor_x: float,
    anchor_y: float,
    scale: float = 1.0,
) -> None:
    if _draw_visible_signature_coccarda_image(
        overlay,
        anchor_x=anchor_x,
        anchor_y=anchor_y,
        scale=scale,
    ):
        return

    try:
        from reportlab.lib.colors import Color
    except Exception:
        return

    center_x = anchor_x
    center_y = anchor_y
    radius = 7.5 * scale
    silver_dark = Color(0.56, 0.58, 0.63)
    silver_light = Color(0.90, 0.91, 0.93)
    ribbon_gray = Color(0.74, 0.75, 0.79)
    green = Color(0.11, 0.57, 0.24)
    white = Color(0.98, 0.98, 0.98)
    red = Color(0.78, 0.16, 0.18)
    gold = Color(0.84, 0.70, 0.29)

    overlay.saveState()

    left_tail = overlay.beginPath()
    left_tail.moveTo(center_x - 1.4 * scale, center_y - 4.6 * scale)
    left_tail.lineTo(center_x - 5.7 * scale, center_y - 12.5 * scale)
    left_tail.lineTo(center_x - 0.5 * scale, center_y - 9.7 * scale)
    left_tail.close()
    overlay.setFillColor(ribbon_gray)
    overlay.setStrokeColor(ribbon_gray)
    overlay.drawPath(left_tail, fill=1, stroke=0)

    right_tail = overlay.beginPath()
    right_tail.moveTo(center_x + 1.4 * scale, center_y - 4.6 * scale)
    right_tail.lineTo(center_x + 5.7 * scale, center_y - 12.5 * scale)
    right_tail.lineTo(center_x + 0.5 * scale, center_y - 9.7 * scale)
    right_tail.close()
    overlay.drawPath(right_tail, fill=1, stroke=0)

    overlay.setStrokeColor(silver_dark)
    overlay.setFillColor(silver_light)
    overlay.circle(center_x, center_y, radius, stroke=1, fill=1)
    overlay.setFillColor(green)
    overlay.circle(center_x, center_y, radius * 0.68, stroke=0, fill=1)
    overlay.setFillColor(white)
    overlay.circle(center_x, center_y, radius * 0.45, stroke=0, fill=1)
    overlay.setFillColor(red)
    overlay.circle(center_x, center_y, radius * 0.26, stroke=0, fill=1)
    overlay.setFillColor(gold)
    overlay.circle(center_x, center_y, radius * 0.08, stroke=0, fill=1)

    overlay.setStrokeColor(silver_dark)
    overlay.setLineWidth(0.55 * scale)
    overlay.circle(center_x, center_y, radius * 0.88, stroke=1, fill=0)
    overlay.circle(center_x, center_y, radius * 0.56, stroke=1, fill=0)
    overlay.restoreState()


def next_pdf_signature_field_name(reader) -> str:
    """Choose a fresh field without renaming or clearing any existing field."""
    occupied = set((reader.get_fields() or {}).keys())
    index = 1
    while any(
        name == f"Signature{index}" or name.startswith(f"Signature{index}.")
        for name in occupied
    ):
        index += 1
    return f"Signature{index}"
