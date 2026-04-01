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


# ================================================================ Categorie

CATEGORIE = [
    "Atti giudiziari",
    "Incarichi professionali",
    "Stragiudiziale",
    "Contratti",
    "GDPR / Privacy",
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
    note:        str = ""
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

BUILTIN_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "builtin-procura-liti",
        "titolo": "Procura alle liti",
        "categoria": "Atti giudiziari",
        "builtin": True,
        "note": "Procura speciale per la rappresentanza in giudizio. Da firmare e autenticare.",
        "corpo": """PROCURA SPECIALE ALLE LITI

Il/La sottoscritto/a {{ cliente.nome_completo }},
{% if cliente.codice_fiscale %}C.F. {{ cliente.codice_fiscale }},{% endif %}
{% if cliente.data_nascita %}nato/a il {{ cliente.data_nascita }}{% if cliente.luogo_nascita %} a {{ cliente.luogo_nascita }}{% endif %},{% endif %}
residente in {{ cliente.indirizzo or '___________________' }},

DELEGA E CONFERISCE

procura speciale all'Avv. {{ avvocato_nome }} con studio in {{ studio_indirizzo }}, affinché lo/la rappresenti e difenda
{% if fascicolo %}
nel procedimento relativo a: {{ fascicolo.titolo }}
{% if fascicolo.numero_rg %}N. RG {{ fascicolo.numero_rg }}{% endif %}
{% if fascicolo.tribunale %}innanzi al {{ fascicolo.tribunale }}{% endif %}
{% else %}
nel procedimento di: ___________________
{% endif %}
con ogni più ampia facoltà di legge, ivi compresa quella di designare altri difensori, chiamare terzi in causa, proporre domande riconvenzionali, transigere e conciliare, riscuotere somme, rilasciare quietanze e fare tutto quanto necessario per la tutela dei propri interessi.

Luogo e data: ___________________, {{ data_oggi }}

Firma del mandante: ___________________


L'Avv. {{ avvocato_nome }} autentica la firma del/della mandante.

___________________, {{ data_oggi }}
Avv. {{ avvocato_nome }}
""",
    },
    {
        "id": "builtin-lettera-incarico",
        "titolo": "Lettera di incarico professionale",
        "categoria": "Incarichi professionali",
        "builtin": True,
        "note": "Lettera di conferimento incarico professionale con descrizione dell'oggetto.",
        "corpo": """{{ studio_nome }}
{{ studio_indirizzo }}

{{ data_oggi }}

Spettabile
{{ cliente.nome_completo }}
{{ cliente.indirizzo or '' }}


Oggetto: Conferimento incarico professionale{% if fascicolo %} — {{ fascicolo.titolo }}{% endif %}

Gentile {{ 'Sig.' if cliente.tipo and cliente.tipo.value == 'PF' else 'Spettabile' }} {{ cliente.nome_completo }},

a seguito del colloquio intercorso, Le confermiamo formalmente l'accettazione dell'incarico professionale relativo a:

{% if fascicolo %}
PRATICA: {{ fascicolo.titolo }}
{% if fascicolo.tipo %}Tipo procedimento: {{ fascicolo.tipo.value }}{% endif %}
{% if fascicolo.numero_rg %}N. RG: {{ fascicolo.numero_rg }}{% endif %}
{% if fascicolo.tribunale %}Autorità giudiziaria: {{ fascicolo.tribunale }}{% endif %}
{% else %}
OGGETTO: ___________________
{% endif %}

OGGETTO DELL'INCARICO
Il presente studio si impegna a fornire assistenza e consulenza legale in merito alla questione sopra indicata, con ogni opportuna attività stragiudiziale e giudiziale a tutela dei Suoi interessi.

COMPENSO PROFESSIONALE
Il compenso per la presente attività professionale sarà determinato ai sensi dei parametri forensi (D.M. 55/2014 e successive modificazioni), in relazione all'attività effettivamente svolta. Sarà nostra cura informarLa preventivamente in caso di variazioni significative.

RISERVATEZZA
Tutto quanto comunicato dal Cliente allo Studio è coperto dal segreto professionale ai sensi delle norme deontologiche forensi.

Confidando nella Sua fiducia, restiamo a Sua disposizione per qualsiasi chiarimento.

Cordiali saluti,
{{ avvocato_nome }}
{{ studio_nome }}

---
Per accettazione:
{{ cliente.nome_completo }}: ___________________   Data: ___________________
""",
    },
    {
        "id": "builtin-diffida",
        "titolo": "Diffida stragiudiziale",
        "categoria": "Stragiudiziale",
        "builtin": True,
        "note": "Diffida formale all'adempimento prima dell'azione giudiziale.",
        "corpo": """{{ studio_nome }}
{{ studio_indirizzo }}

RACCOMANDATA A.R. / PEC

{{ data_oggi }}

Spettabile
{{ destinatario_nome or '___________________' }}
{{ destinatario_indirizzo or '___________________' }}

OGGETTO: DIFFIDA E MESSA IN MORA

Egr. Sig./Spett.le {{ destinatario_nome or '___________________' }},

il/la sottoscritto/a Avv. {{ avvocato_nome }}, in nome e per conto del/della proprio/a assistito/a {{ cliente.nome_completo }}{% if cliente.codice_fiscale %} (C.F. {{ cliente.codice_fiscale }}){% endif %},

INTIMA E DIFFIDA

codesta Spettabile {{ destinatario_nome or 'parte' }} ad adempiere, entro e non oltre {{ termine_giorni|default(15) }} ({{ termine_giorni|default(15) }}) giorni dal ricevimento della presente, al seguente obbligo:

{{ oggetto_diffida or '___________________\n___________________\n___________________' }}

In caso di inottemperanza entro il predetto termine, il/la sottoscritto/a procuratore si vedrà costretto/a ad adire le competenti Autorità Giudiziarie per la tutela dei diritti del proprio assistito/a, con aggravio delle spese legali a Vostro carico ai sensi dell'art. 96 c.p.c.

Si riserva ogni azione e diritto.

Con osservanza,
Avv. {{ avvocato_nome }}
{{ studio_nome }}
""",
    },
    {
        "id": "builtin-messa-in-mora",
        "titolo": "Atto di messa in mora",
        "categoria": "Stragiudiziale",
        "builtin": True,
        "note": "Costituzione in mora del debitore ex art. 1219 c.c.",
        "corpo": """{{ studio_nome }}
{{ studio_indirizzo }}

RACCOMANDATA A.R. / PEC

{{ data_oggi }}

Spettabile
{{ destinatario_nome or '___________________' }}
{{ destinatario_indirizzo or '___________________' }}

OGGETTO: COSTITUZIONE IN MORA — art. 1219 c.c.

Egr. Sig./Spett.le {{ destinatario_nome or '___________________' }},

il/la sottoscritto/a Avv. {{ avvocato_nome }}, in qualità di procuratore di {{ cliente.nome_completo }},

COSTITUISCE FORMALMENTE IN MORA

codesta parte ai sensi e per gli effetti dell'art. 1219 del Codice Civile, intimando il pagamento della somma di € {{ importo_dovuto or '___________________' }} oltre interessi legali maturati e maturandi, dovuta a titolo di {{ titolo_credito or '___________________' }}.

Si diffida pertanto al pagamento integrale dell'importo sopra indicato entro {{ termine_giorni|default(15) }} ({{ termine_giorni|default(15) }}) giorni dalla data di ricevimento della presente, mediante bonifico bancario alle seguenti coordinate:
IBAN: {{ studio_iban or '___________________' }}

Decorso inutilmente il termine, si procederà senza ulteriore preavviso nelle competenti sedi giudiziarie, con condanna alle spese di lite.

Avv. {{ avvocato_nome }}
{{ studio_nome }}
""",
    },
    {
        "id": "builtin-nda",
        "titolo": "Accordo di riservatezza (NDA)",
        "categoria": "Contratti",
        "builtin": True,
        "note": "Non-disclosure agreement tra studio e cliente o tra parti.",
        "corpo": """ACCORDO DI RISERVATEZZA
(Non Disclosure Agreement)

Tra:
{{ studio_nome }}, con sede in {{ studio_indirizzo }},
di seguito denominato "Studio"

e

{{ cliente.nome_completo }}{% if cliente.codice_fiscale %}, C.F. {{ cliente.codice_fiscale }}{% endif %},
residente/con sede in {{ cliente.indirizzo or '___________________' }},
di seguito denominato "Controparte"

PREMESSO CHE le parti intendono avviare/proseguire una collaborazione professionale nell'ambito della quale potranno essere condivise informazioni riservate;

LE PARTI CONVENGONO QUANTO SEGUE:

Art. 1 – Definizione di Informazione Riservata
Per "Informazione Riservata" si intende qualsiasi dato, documento, notizia di carattere tecnico, commerciale, strategico, giuridico o di altra natura, comunque acquisita nell'ambito del rapporto professionale.

Art. 2 – Obbligo di riservatezza
Le parti si impegnano a mantenere strettamente riservate le Informazioni Riservate ricevute e a non divulgarle a terzi senza il preventivo consenso scritto della parte che le ha fornite.

Art. 3 – Eccezioni
L'obbligo di riservatezza non si applica alle informazioni che: (i) siano già di pubblico dominio; (ii) siano state acquisite legittimamente da terzi; (iii) debbano essere divulgate per obbligo di legge.

Art. 4 – Durata
Il presente accordo ha durata di {{ durata_anni|default(5) }} anni dalla data di sottoscrizione.

Art. 5 – Legge applicabile
Il presente accordo è regolato dalla legge italiana. Per qualsiasi controversia sarà competente il Tribunale di {{ tribunale_competente or '___________________' }}.

{{ data_oggi }}

Per lo Studio:                          Per la Controparte:
{{ avvocato_nome }}                     {{ cliente.nome_completo }}
___________________                     ___________________
""",
    },
]


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
        return sorted(self._templates.values(), key=lambda t: (t.categoria, t.titolo))

    def get(self, id_template: str) -> Optional[TemplateAtto]:
        return self._templates.get(id_template)

    def crea(self, titolo: str, categoria: str, corpo: str, note: str = "") -> TemplateAtto:
        t = TemplateAtto(
            id=str(uuid.uuid4()),
            titolo=titolo,
            categoria=categoria,
            corpo=corpo,
            note=note,
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
