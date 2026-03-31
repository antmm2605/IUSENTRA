"""
pct/wizard_pro.py — Wizard Pro: gestione guidata dell'udienza in presenza.

5 step:
  1. Briefing       — riepilogo fascicolo + appuntamento
  2. Documenti      — checklist documenti da portare
  3. Preparazione   — note, argomenti, richieste al giudice, eccezioni
  4. Pre-partenza   — checklist finale prima di uscire dallo studio
  5. Esito          — resoconto post-udienza e aggiornamento fascicolo
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List


# ─────────────────────────────────────────────────── COSTANTI

STEP_LABELS = {
    1: "Briefing",
    2: "Documenti",
    3: "Preparazione",
    4: "Pre-partenza",
    5: "Esito",
}

STEP_ICONS = {
    1: "bi-search",
    2: "bi-clipboard-check",
    3: "bi-pencil-square",
    4: "bi-suitcase-lg",
    5: "bi-balance-scale",
}

ESITI = [
    ("favorevole",  "Favorevole"),
    ("parziale",    "Parzialmente favorevole"),
    ("sfavorevole", "Sfavorevole"),
    ("rinvio",      "Rinvio"),
    ("sospeso",     "Sospeso"),
]

COLORI_ESITO = {
    "favorevole":  "success",
    "parziale":    "warning",
    "sfavorevole": "danger",
    "rinvio":      "info",
    "sospeso":     "secondary",
}

ICONE_ESITO = {
    "favorevole":  "bi-hand-thumbs-up-fill",
    "parziale":    "bi-dash-circle-fill",
    "sfavorevole": "bi-hand-thumbs-down-fill",
    "rinvio":      "bi-arrow-repeat",
    "sospeso":     "bi-pause-circle-fill",
}


# ─────────────────────────────────────────────────── DOCUMENTO CHECKLIST

@dataclass
class DocumentoChecklist:
    id_documento: str     # "" se virtuale (non collegato a doc nel fascicolo)
    label: str            # nome/descrizione da mostrare
    tipo: str             # es. "ATTO_GIUDIZIARIO"
    obbligatorio: bool
    stato: str            # da_portare | pronto | non_necessario
    note: str = ""
    nome_file: str = ""
    firmato: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "DocumentoChecklist":
        return cls(
            id_documento=d.get("id_documento", ""),
            label=d.get("label", ""),
            tipo=d.get("tipo", ""),
            obbligatorio=d.get("obbligatorio", True),
            stato=d.get("stato", "da_portare"),
            note=d.get("note", ""),
            nome_file=d.get("nome_file", ""),
            firmato=d.get("firmato", False),
        )

    def to_dict(self) -> dict:
        return asdict(self)


# ─────────────────────────────────────────────────── SESSIONE WIZARD PRO

@dataclass
class SessioneWizardPro:
    id: str
    id_fascicolo: str
    id_appuntamento: str        # "" se non collegato ad un appuntamento agenda
    titolo: str                 # es. "Udienza RG 1234/2024 – Rossi c/ Bianchi"
    stato: str                  # in_corso | completato | archiviato
    step_corrente: int          # 1-5

    # ── Step 1 — Briefing ──────────────────────────────────────────────
    step1_note: str = ""
    step1_confermato: bool = False

    # ── Step 2 — Documenti ─────────────────────────────────────────────
    checklist_documenti: List[dict] = field(default_factory=list)
    step2_confermato: bool = False

    # ── Step 3 — Preparazione ──────────────────────────────────────────
    note_preparazione: str = ""
    argomenti_principali: str = ""
    richieste_giudice: str = ""
    eccezioni_da_sollevare: str = ""
    step3_confermato: bool = False

    # ── Step 4 — Pre-partenza ──────────────────────────────────────────
    precheck_firma_ok: bool = False
    precheck_docs_pronti: bool = False
    precheck_cliente_notificato: bool = False
    precheck_trasporto_ok: bool = False
    precheck_note: str = ""
    step4_confermato: bool = False

    # ── Step 5 — Esito ─────────────────────────────────────────────────
    esito: str = ""                  # favorevole | parziale | sfavorevole | rinvio | sospeso
    esito_rinvio_data: str = ""
    esito_note_verbale: str = ""
    esito_azioni: str = ""
    esito_aggiorna_fascicolo: bool = True
    step5_confermato: bool = False

    # ── Metadata ───────────────────────────────────────────────────────
    avvocato: str = ""
    creato_il: str = ""
    modificato_il: str = ""
    completato_il: str = ""

    # ── Costruttore convenience ────────────────────────────────────────
    @classmethod
    def nuova(
        cls,
        id_fascicolo: str,
        titolo: str,
        id_appuntamento: str = "",
        avvocato: str = "",
    ) -> "SessioneWizardPro":
        now = datetime.now().isoformat()
        return cls(
            id=str(uuid.uuid4()),
            id_fascicolo=id_fascicolo,
            id_appuntamento=id_appuntamento,
            titolo=titolo,
            stato="in_corso",
            step_corrente=1,
            avvocato=avvocato,
            creato_il=now,
            modificato_il=now,
        )

    @classmethod
    def from_dict(cls, d: dict) -> "SessioneWizardPro":
        return cls(
            id=d.get("id", ""),
            id_fascicolo=d.get("id_fascicolo", ""),
            id_appuntamento=d.get("id_appuntamento", ""),
            titolo=d.get("titolo", ""),
            stato=d.get("stato", "in_corso"),
            step_corrente=d.get("step_corrente", 1),
            step1_note=d.get("step1_note", ""),
            step1_confermato=d.get("step1_confermato", False),
            checklist_documenti=d.get("checklist_documenti", []),
            step2_confermato=d.get("step2_confermato", False),
            note_preparazione=d.get("note_preparazione", ""),
            argomenti_principali=d.get("argomenti_principali", ""),
            richieste_giudice=d.get("richieste_giudice", ""),
            eccezioni_da_sollevare=d.get("eccezioni_da_sollevare", ""),
            step3_confermato=d.get("step3_confermato", False),
            precheck_firma_ok=d.get("precheck_firma_ok", False),
            precheck_docs_pronti=d.get("precheck_docs_pronti", False),
            precheck_cliente_notificato=d.get("precheck_cliente_notificato", False),
            precheck_trasporto_ok=d.get("precheck_trasporto_ok", False),
            precheck_note=d.get("precheck_note", ""),
            step4_confermato=d.get("step4_confermato", False),
            esito=d.get("esito", ""),
            esito_rinvio_data=d.get("esito_rinvio_data", ""),
            esito_note_verbale=d.get("esito_note_verbale", ""),
            esito_azioni=d.get("esito_azioni", ""),
            esito_aggiorna_fascicolo=d.get("esito_aggiorna_fascicolo", True),
            step5_confermato=d.get("step5_confermato", False),
            avvocato=d.get("avvocato", ""),
            creato_il=d.get("creato_il", ""),
            modificato_il=d.get("modificato_il", ""),
            completato_il=d.get("completato_il", ""),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    # ── Proprietà calcolate ────────────────────────────────────────────

    @property
    def percentuale_completamento(self) -> int:
        confermati = sum([
            self.step1_confermato,
            self.step2_confermato,
            self.step3_confermato,
            self.step4_confermato,
            self.step5_confermato,
        ])
        return confermati * 20  # 5 step × 20% = 100%

    @property
    def label_esito(self) -> str:
        return dict(ESITI).get(self.esito, self.esito or "—")

    @property
    def colore_esito(self) -> str:
        return COLORI_ESITO.get(self.esito, "secondary")

    @property
    def icona_esito(self) -> str:
        return ICONE_ESITO.get(self.esito, "bi-question-circle")

    @property
    def docs_checklist(self) -> List[DocumentoChecklist]:
        return [DocumentoChecklist.from_dict(d) for d in self.checklist_documenti]

    @property
    def docs_pronti(self) -> int:
        return sum(1 for d in self.docs_checklist if d.stato == "pronto")

    @property
    def docs_totali(self) -> int:
        return sum(1 for d in self.docs_checklist if d.stato != "non_necessario")

    @property
    def precheck_completato(self) -> bool:
        return all([
            self.precheck_firma_ok,
            self.precheck_docs_pronti,
            self.precheck_cliente_notificato,
            self.precheck_trasporto_ok,
        ])

    @property
    def precheck_n_ok(self) -> int:
        return sum([
            self.precheck_firma_ok,
            self.precheck_docs_pronti,
            self.precheck_cliente_notificato,
            self.precheck_trasporto_ok,
        ])


# ─────────────────────────────────────────────────── GESTORE PERSISTENZA

class GestioneWizardPro:
    """CRUD per le sessioni Wizard Pro (JSON file)."""

    def __init__(self, db_path: str):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _carica_tutto(self) -> list:
        if not self._path.exists():
            return []
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _salva_tutto(self, sessioni: list) -> None:
        self._path.write_text(
            json.dumps(sessioni, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def lista(self) -> List[SessioneWizardPro]:
        return [SessioneWizardPro.from_dict(d) for d in self._carica_tutto()]

    def lista_per_fascicolo(self, id_fascicolo: str) -> List[SessioneWizardPro]:
        return [s for s in self.lista() if s.id_fascicolo == id_fascicolo]

    def carica(self, id_sessione: str) -> Optional[SessioneWizardPro]:
        for d in self._carica_tutto():
            if d.get("id") == id_sessione:
                return SessioneWizardPro.from_dict(d)
        return None

    def salva(self, sessione: SessioneWizardPro) -> None:
        sessione.modificato_il = datetime.now().isoformat()
        tutti = self._carica_tutto()
        for i, d in enumerate(tutti):
            if d.get("id") == sessione.id:
                tutti[i] = sessione.to_dict()
                self._salva_tutto(tutti)
                return
        tutti.append(sessione.to_dict())
        self._salva_tutto(tutti)

    def elimina(self, id_sessione: str) -> bool:
        tutti = self._carica_tutto()
        nuovi = [d for d in tutti if d.get("id") != id_sessione]
        if len(nuovi) < len(tutti):
            self._salva_tutto(nuovi)
            return True
        return False
