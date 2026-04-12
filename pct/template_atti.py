"""
pct/template_atti.py — Generatore di atti legali da template.

Permette all'avvocato di:
  - Gestire template riutilizzabili (Jinja2) per atti comuni
  - Generare documenti precompilati dai dati fascicolo/cliente
  - Esportare in PDF via ReportLab

Template built-in inclusi:
  - Procura alle liti
  - Lettera di incarico professionale
  - Diffida stragiudiziale
  - Atto di messa in mora
  - Accordo di riservatezza (NDA)
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pct.template_atti_catalogo import build_builtin_templates


# ================================================================ Categorie

CATEGORIE = [
    "Procure, nomine e deleghe",
    "Civile ordinario",
    "Monitorio e cautelare",
    "Impugnazioni civili",
    "Esecuzioni",
    "Famiglia e volontaria giurisdizione",
    "Lavoro e previdenza",
    "Penale",
    "Amministrativo",
    "Tributario",
    "UNEP e notificazioni",
    "Stragiudiziale collegato",
    "Altro",
]

EDITOR_FONT_CATALOG: Dict[str, Dict[str, str]] = {
    "source_serif": {
        "label": "Source Serif 4",
        "css_stack": "'Source Serif 4', Georgia, 'Times New Roman', serif",
        "pdf_family": "times",
        "tone": "serif",
    },
    "libre_baskerville": {
        "label": "Libre Baskerville",
        "css_stack": "'Libre Baskerville', Georgia, 'Times New Roman', serif",
        "pdf_family": "times",
        "tone": "serif",
    },
    "spectral": {
        "label": "Spectral",
        "css_stack": "'Spectral', Georgia, 'Times New Roman', serif",
        "pdf_family": "times",
        "tone": "serif",
    },
    "crimson_text": {
        "label": "Crimson Text",
        "css_stack": "'Crimson Text', Georgia, 'Times New Roman', serif",
        "pdf_family": "times",
        "tone": "serif",
    },
    "inter": {
        "label": "Inter",
        "css_stack": "'Inter', Arial, Helvetica, sans-serif",
        "pdf_family": "helvetica",
        "tone": "sans",
    },
    "manrope": {
        "label": "Manrope",
        "css_stack": "'Manrope', Arial, Helvetica, sans-serif",
        "pdf_family": "helvetica",
        "tone": "sans",
    },
    "ibm_plex_mono": {
        "label": "IBM Plex Mono",
        "css_stack": "'IBM Plex Mono', 'Courier New', monospace",
        "pdf_family": "courier",
        "tone": "mono",
    },
}

DEFAULT_EDITOR_LAYOUT: Dict[str, Any] = {
    "font_family": "source_serif",
    "font_size_pt": 12,
    "line_height": 1.9,
    "text_align": "justify",
    "margin_top_mm": 25,
    "margin_right_mm": 22,
    "margin_bottom_mm": 25,
    "margin_left_mm": 32,
    "paragraph_spacing_pt": 8,
}


def catalogo_font_editor() -> list[dict[str, str]]:
    return [{"key": key, **meta} for key, meta in EDITOR_FONT_CATALOG.items()]


def font_editor(key: str) -> dict[str, str]:
    return EDITOR_FONT_CATALOG.get(key, EDITOR_FONT_CATALOG[DEFAULT_EDITOR_LAYOUT["font_family"]])


def _clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        coerced = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, coerced))


def _clamp_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        coerced = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, coerced))


def normalizza_editor_layout(layout: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    raw = layout or {}
    font_key = raw.get("font_family", DEFAULT_EDITOR_LAYOUT["font_family"])
    if font_key not in EDITOR_FONT_CATALOG:
        font_key = DEFAULT_EDITOR_LAYOUT["font_family"]
    text_align = str(raw.get("text_align", DEFAULT_EDITOR_LAYOUT["text_align"]) or "").lower()
    if text_align not in {"justify", "left", "center", "right"}:
        text_align = DEFAULT_EDITOR_LAYOUT["text_align"]
    return {
        "font_family": font_key,
        "font_size_pt": _clamp_int(raw.get("font_size_pt"), DEFAULT_EDITOR_LAYOUT["font_size_pt"], 9, 18),
        "line_height": round(
            _clamp_float(raw.get("line_height"), DEFAULT_EDITOR_LAYOUT["line_height"], 1.2, 2.6),
            2,
        ),
        "text_align": text_align,
        "margin_top_mm": _clamp_int(raw.get("margin_top_mm"), DEFAULT_EDITOR_LAYOUT["margin_top_mm"], 10, 45),
        "margin_right_mm": _clamp_int(raw.get("margin_right_mm"), DEFAULT_EDITOR_LAYOUT["margin_right_mm"], 10, 40),
        "margin_bottom_mm": _clamp_int(raw.get("margin_bottom_mm"), DEFAULT_EDITOR_LAYOUT["margin_bottom_mm"], 10, 45),
        "margin_left_mm": _clamp_int(raw.get("margin_left_mm"), DEFAULT_EDITOR_LAYOUT["margin_left_mm"], 15, 50),
        "paragraph_spacing_pt": _clamp_int(
            raw.get("paragraph_spacing_pt"),
            DEFAULT_EDITOR_LAYOUT["paragraph_spacing_pt"],
            0,
            18,
        ),
    }


def percorso_preferenze_editor(db_path: str) -> str:
    base = Path(db_path).resolve().parent
    return str(base / "editor_layout.json")

# ================================================================ Modello

@dataclass
class TemplateAtto:
    id:          str
    titolo:      str
    categoria:   str
    corpo:       str       # testo Jinja2 con variabili {{ }}
    codice:      str = ""
    note:        str = ""
    descrizione: str = ""
    area:        str = ""
    branca:      str = ""
    sottobranca: str = ""
    microtema:   str = ""
    fase:        str = ""
    rito:        str = ""
    grado:       str = ""
    canale_telematico: str = "Misto"
    profilo_deposito: str = ""
    collezione:  str = ""
    allegati_obbligatori: List[str] = field(default_factory=list)
    controlli_conformita: List[str] = field(default_factory=list)
    parole_chiave: List[str] = field(default_factory=list)
    campi_guidati: List[Dict[str, Any]] = field(default_factory=list)
    varianti: List[str] = field(default_factory=list)
    link_compilatore_code: str = ""
    ordine: int = 9999
    builtin:     bool = False
    creato_il:   str = field(default_factory=lambda: datetime.now().isoformat())
    modificato_il: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "TemplateAtto":
        campi = set(TemplateAtto.__dataclass_fields__)
        return TemplateAtto(**{k: v for k, v in d.items() if k in campi})


# ================================================================ Template built-in

BUILTIN_TEMPLATES: List[Dict[str, Any]] = build_builtin_templates()


# ================================================================ Gestore

class GestioneTemplateAtti:

    def __init__(self, db_path: str = "./template_atti/templates.json"):
        self.db_path = db_path
        self._templates: Dict[str, TemplateAtto] = {}
        self._carica()
        self._inserisci_builtin()

    def _carica(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, encoding="utf-8") as f:
                raw = json.load(f)
            self._templates = {k: TemplateAtto.from_dict(v) for k, v in raw.items()}

    def _salva(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        # Salva solo i template custom (non builtin) — i builtin si ricaricano sempre fresh
        da_salvare = {k: v.to_dict() for k, v in self._templates.items() if not v.builtin}
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(da_salvare, f, ensure_ascii=False, indent=2)

    def _inserisci_builtin(self):
        for t in BUILTIN_TEMPLATES:
            if t["id"] not in self._templates:
                self._templates[t["id"]] = TemplateAtto.from_dict(t)

    # ---- CRUD

    def tutti(self) -> List[TemplateAtto]:
        return sorted(
            self._templates.values(),
            key=lambda t: (
                0 if t.builtin else 1,
                t.area or "",
                t.collezione or "",
                t.ordine,
                t.titolo.lower(),
            ),
        )

    def get(self, id_template: str) -> Optional[TemplateAtto]:
        return self._templates.get(id_template)

    def crea(self, titolo: str, categoria: str, corpo: str, note: str = "", **metadata) -> TemplateAtto:
        t = TemplateAtto(
            id=str(uuid.uuid4()),
            titolo=titolo,
            categoria=categoria,
            corpo=corpo,
            codice=metadata.get("codice", ""),
            note=note,
            descrizione=metadata.get("descrizione", ""),
            area=metadata.get("area", ""),
            branca=metadata.get("branca", ""),
            sottobranca=metadata.get("sottobranca", ""),
            microtema=metadata.get("microtema", ""),
            fase=metadata.get("fase", ""),
            rito=metadata.get("rito", ""),
            grado=metadata.get("grado", ""),
            canale_telematico=metadata.get("canale_telematico", "Misto"),
            profilo_deposito=metadata.get("profilo_deposito", ""),
            collezione=metadata.get("collezione", ""),
            allegati_obbligatori=list(metadata.get("allegati_obbligatori", []) or []),
            controlli_conformita=list(metadata.get("controlli_conformita", []) or []),
            parole_chiave=list(metadata.get("parole_chiave", []) or []),
            campi_guidati=list(metadata.get("campi_guidati", []) or []),
            varianti=list(metadata.get("varianti", []) or []),
            link_compilatore_code=metadata.get("link_compilatore_code", ""),
            ordine=int(metadata.get("ordine", 9999) or 9999),
            builtin=False,
        )
        self._templates[t.id] = t
        self._salva()
        return t

    def aggiorna(self, id_template: str, **kwargs) -> TemplateAtto:
        t = self._templates[id_template]
        if t.builtin:
            raise ValueError("I template built-in non possono essere modificati.")
        for k, v in kwargs.items():
            if hasattr(t, k):
                setattr(t, k, v)
        t.modificato_il = datetime.now().isoformat()
        self._salva()
        return t

    def elimina(self, id_template: str):
        t = self._templates.get(id_template)
        if t and t.builtin:
            raise ValueError("I template built-in non possono essere eliminati.")
        self._templates.pop(id_template, None)
        self._salva()

    # ---- Rendering

    def renderizza(self, id_template: str, variabili: Dict[str, Any]) -> str:
        """Renderizza il template con le variabili fornite via Jinja2."""
        from jinja2 import Environment, Undefined
        t = self._templates.get(id_template)
        if not t:
            raise ValueError(f"Template '{id_template}' non trovato.")
        env = Environment(undefined=Undefined)
        tmpl = env.from_string(t.corpo)
        return tmpl.render(**variabili)


class GestionePreferenzeTemplateAtti:

    def __init__(self, prefs_path: str = "./template_atti/editor_layout.json"):
        self.prefs_path = prefs_path

    def carica(self) -> Dict[str, Any]:
        if os.path.exists(self.prefs_path):
            try:
                with open(self.prefs_path, encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict) and "editor_layout" in raw:
                    raw = raw["editor_layout"]
                return normalizza_editor_layout(raw)
            except Exception:
                pass
        return normalizza_editor_layout(DEFAULT_EDITOR_LAYOUT)

    def salva(self, layout: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        normalizzato = normalizza_editor_layout(layout)
        os.makedirs(os.path.dirname(self.prefs_path) or ".", exist_ok=True)
        payload = {
            "editor_layout": normalizzato,
            "updated_at": datetime.now().isoformat(),
        }
        with open(self.prefs_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return normalizzato

    def reset(self) -> Dict[str, Any]:
        return self.salva(DEFAULT_EDITOR_LAYOUT)


def acquisisci_da_scanner_windows(timeout: int = 120) -> Dict[str, Any]:
    """
    Tenta una scansione desktop tramite WIA su Windows.

    Restituisce un data URL PNG pronto per l'inserimento nell'editor.
    """
    if os.name != "nt":
        raise RuntimeError("Scanner desktop diretto disponibile solo su installazioni Windows locali.")

    temp_dir = Path(tempfile.mkdtemp(prefix="hacs-scan-"))
    bmp_path = temp_dir / "scan.bmp"
    jpg_path = temp_dir / "scan.jpg"
    ps_script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$dialog = New-Object -ComObject WIA.CommonDialog
$image = $dialog.ShowAcquireImage()
if ($null -eq $image) {{
  throw 'Acquisizione annullata o scanner non disponibile.'
}}
$bmp = '{str(bmp_path).replace("'", "''")}'
$jpg = '{str(jpg_path).replace("'", "''")}'
$image.SaveFile($bmp)
$bitmap = [System.Drawing.Image]::FromFile($bmp)
try {{
  $bitmap.Save($jpg, [System.Drawing.Imaging.ImageFormat]::Jpeg)
}} finally {{
  $bitmap.Dispose()
}}
Remove-Item -LiteralPath $bmp -Force -ErrorAction SilentlyContinue
Write-Output $jpg
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("PowerShell non disponibile: impossibile usare lo scanner desktop.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Timeout durante l'acquisizione scanner desktop.") from exc

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(stderr or "Scanner desktop non disponibile o acquisizione annullata.")

    if not jpg_path.exists():
        raise RuntimeError("Nessuna immagine acquisita dallo scanner desktop.")

    data = jpg_path.read_bytes()
    data_url = "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")
    return {
        "filename": jpg_path.name,
        "mime_type": "image/jpeg",
        "bytes": len(data),
        "data_url": data_url,
    }
