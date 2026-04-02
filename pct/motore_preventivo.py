"""
pct/motore_preventivo.py — Motore Preventivo Forense.

Catalogo completo delle tipologie di pratica → mappa alle tabelle DM 55/2014
aggiornate con DM 147/2022 → calcolo completo della parcella:
  onorario base → spese generali → CPA → IVA → esborsi → totale

Normativa di riferimento:
  - D.M. 55/2014 (tabelle parametri forensi)
  - D.M. 147/2022 (aggiornamento tabelle)
  - L. 247/2012 art. 13 (obbligo informativa preventiva)
  - D.P.R. 633/72 art. 15 (anticipazioni esenti IVA)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pct.tariffario import (
    Fase,
    Grado,
    LivelloCompenso,
    Materia,
    RisultatoCalcolo,
    calcola_compenso,
    livello_compenso_da_complessita,
)
from pct.tariffario_catalogo import default_rule_for_practice, rule_lookup, rules_for_practice


# ──────────────────────────────────────────────────────────────────────────────
# Macro-aree
# ──────────────────────────────────────────────────────────────────────────────

AREE = [
    "Civile",
    "Penale",
    "Amministrativo",
    "Tributario",
    "Stragiudiziale",
    "Speciali",
]

# ──────────────────────────────────────────────────────────────────────────────
# TipoPratica
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TipoPratica:
    """Descrizione di una tipologia di pratica con mapping tabellare."""
    id: str                             # slug univoco
    label: str                          # nome visualizzato
    area: str                           # macro-area
    materia: Materia                    # tabella DM 55/2014
    grado_default: Grado                # grado tipico suggerito
    fasi_default: List[Fase]            # fasi processuali tipiche
    base_normativa: str                 # riferimento normativo sintetico
    richiede_valore: bool = True        # False → compenso orario/forfettario
    tipo_compenso_default: str = "Per fasi processuali (D.M. 55/2014)"
    valore_suggerito: float = 0.0       # suggerimento valore controversia

    # Esborsi tipici per la tipologia (importi orientativi Art. 15 DPR 633/72)
    esborsi_tipici: List[Dict] = field(default_factory=list)
    motore_label: str = ""
    redattore_label: str = ""
    summary: str = ""
    when_to_use: str = ""
    oggetto_template: str = ""
    note_template: str = ""
    checklist_iniziale: List[str] = field(default_factory=list)
    normative_references: List[Dict[str, str]] = field(default_factory=list)
    accessori_calcolo: List[Dict[str, Any]] = field(default_factory=list)
    variation_policy: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        regole = rules_for_practice(self.id)
        regola_default = default_rule_for_practice(self.id)
        gradi_consentiti = []
        for regola in regole:
            for grado in regola.get("allowed_grade_input_values", []) or []:
                if grado not in gradi_consentiti:
                    gradi_consentiti.append(grado)
        if not gradi_consentiti:
            gradi_consentiti = [self.grado_default.value]
        return {
            "id": self.id,
            "label": self.label,
            "area": self.area,
            "materia": self.materia.value,
            "grado_default": self.grado_default.value,
            "fasi_default": [f.value for f in self.fasi_default],
            "base_normativa": self.base_normativa,
            "richiede_valore": self.richiede_valore,
            "tipo_compenso_default": self.tipo_compenso_default,
            "valore_suggerito": self.valore_suggerito,
            "esborsi_tipici": self.esborsi_tipici,
            "motore_label": self.motore_label,
            "redattore_label": self.redattore_label,
            "summary": self.summary,
            "when_to_use": self.when_to_use,
            "oggetto_template": self.oggetto_template,
            "note_template": self.note_template,
            "checklist_iniziale": self.checklist_iniziale,
            "normative_references": self.normative_references,
            "accessori_calcolo": self.accessori_calcolo,
            "variation_policy": self.variation_policy,
            "fasi_default_keys": [_fase_key(f) for f in self.fasi_default],
            "gradi_consentiti": gradi_consentiti,
            "regola_tariffaria_default": regola_default.get("rule_code", "") if regola_default else "",
            "regole_tariffarie": regole,
        }


def _adr_variation_policy(kind: str) -> Dict[str, Any]:
    phase_keys = ["attivazione", "rivitalizzazione", "conciliazione"]
    agreement_phase_keys = ["attivazione", "rivitalizzazione"]
    if kind == "negoziazione":
        phase_keys = ["attivazione", "negoziazione", "conciliazione"]
        agreement_phase_keys = ["attivazione", "negoziazione"]
    return {
        "kind": "adr_pm50_con_accordo",
        "range_pct": {"min": -50, "max": 50, "default": 0},
        "phase_controls": [
            {
                "key": key,
                "label": {
                    "attivazione": "Fase di attivazione",
                    "rivitalizzazione": "Fase di rivitalizzazione",
                    "negoziazione": "Fase di negoziazione",
                    "conciliazione": "Fase di conciliazione",
                }.get(key, key),
            }
            for key in phase_keys
        ],
        "agreement_bonus": {
            "enabled": True,
            "pct": 30,
            "phase_keys": agreement_phase_keys,
            "description": (
                "Se la procedura si conclude con accordo, i compensi delle fasi di attivazione "
                "e negoziazione/rivitalizzazione sono aumentati del 30%, ferma la fase di conciliazione."
            ),
        },
        "references": [
            "Art. 2 D.M. 55/2014: spese generali 15% sul compenso.",
            "Art. 19 D.M. 55/2014: variazione per fase entro il +/-50%.",
            "Art. 20, comma 1-bis, D.M. 55/2014: +30% sulle fasi iniziali ADR se si raggiunge l'accordo.",
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Catalogo pratiche
# ──────────────────────────────────────────────────────────────────────────────

_FASI_BASE      = [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA, Fase.DECISIONALE]
_FASI_STUDIO    = [Fase.STUDIO]
_FASI_ESEC      = [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ESECUTIVA]
_FASI_ESEC_MOB  = [Fase.STUDIO, Fase.ESECUTIVA]
_FASI_ESEC_INT  = [Fase.INTRODUTTIVA, Fase.ESECUTIVA]
_FASI_PENALE    = [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA, Fase.DECISIONALE]

CATALOGO: List[TipoPratica] = [

    # ── CIVILE ──────────────────────────────────────────────────────────────

    TipoPratica(
        id="consulenza_civile",
        label="Consulenza / Parere civile",
        area="Civile",
        materia=Materia.STRAGIUD,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO],
        base_normativa="Tab. A25 DM 55/2014 agg. DM 147/2022 — Prestazioni stragiudiziali",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="diffida",
        label="Diffida / Lettera legale",
        area="Civile",
        materia=Materia.STRAGIUD,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA],
        base_normativa="Tab. A25 DM 55/2014 agg. DM 147/2022 — Prestazioni stragiudiziali",
        richiede_valore=True,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="recupero_crediti",
        label="Recupero crediti",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 agg. DM 147/2022 — Giudizi civili ordinari",
    ),
    TipoPratica(
        id="decreto_ingiuntivo",
        label="Decreto ingiuntivo",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A2 DM 55/2014 agg. DM 147/2022 — art. 633 c.p.c.",
    ),
    TipoPratica(
        id="opposizione_di",
        label="Opposizione a decreto ingiuntivo",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 agg. DM 147/2022 — art. 645 c.p.c.",
    ),
    TipoPratica(
        id="atto_citazione",
        label="Atto di citazione",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 agg. DM 147/2022 — art. 163 c.p.c.",
    ),
    TipoPratica(
        id="comparsa_risposta",
        label="Comparsa di costituzione e risposta",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 agg. DM 147/2022 — art. 167 c.p.c.",
    ),
    TipoPratica(
        id="appello_civile",
        label="Appello civile",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.CORTE_APPELLO,
        fasi_default=_FASI_BASE,
        base_normativa="Art. 341 c.p.c. — Tab. A2 se l'appello e devoluto al Tribunale; Tab. A12 se l'appello e devoluto alla Corte d'Appello.",
    ),
    TipoPratica(
        id="cassazione_civile",
        label="Cassazione civile",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.CASSAZIONE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A13 DM 55/2014 agg. DM 147/2022 — art. 360 c.p.c.",
    ),
    TipoPratica(
        id="precetto",
        label="Precetto",
        area="Civile",
        materia=Materia.ESEC_MOB,
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA],
        base_normativa="Tab. A6 DM 55/2014 agg. DM 147/2022 — art. 480 c.p.c.",
    ),
    TipoPratica(
        id="pignoramento",
        label="Pignoramento mobiliare",
        area="Civile",
        materia=Materia.ESEC_MOB,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_ESEC_MOB,
        base_normativa="Tab. A16 DM 55/2014 agg. DM 147/2022 — procedure esecutive mobiliari",
    ),
    TipoPratica(
        id="esecuzione_mobiliare",
        label="Esecuzione mobiliare",
        area="Civile",
        materia=Materia.ESEC_MOB,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_ESEC_MOB,
        base_normativa="Tab. A16 DM 55/2014 agg. DM 147/2022 — esecuzione su beni mobili",
    ),
    TipoPratica(
        id="esecuzione_immobiliare",
        label="Esecuzione immobiliare",
        area="Civile",
        materia=Materia.ESEC_IMMO,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_ESEC_INT,
        base_normativa="Tab. A18 DM 55/2014 agg. DM 147/2022 — esecuzione su beni immobili — art. 555 ss. c.p.c.",
    ),
    TipoPratica(
        id="esecuzione_terzi",
        label="Esecuzione presso terzi (pignoramento c/terzi)",
        area="Civile",
        materia=Materia.ESEC_MOB,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_ESEC_INT,
        base_normativa="Tab. A17 DM 55/2014 agg. DM 147/2022 — pignoramento presso terzi — art. 543 c.p.c.",
    ),
    TipoPratica(
        id="opposizione_esecutiva",
        label="Opposizione all'esecuzione",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 — artt. 615 e 619 c.p.c.",
    ),
    TipoPratica(
        id="opposizione_atti_esecutivi",
        label="Opposizione agli atti esecutivi",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 — art. 617 c.p.c.",
    ),
    TipoPratica(
        id="separazione_consensuale",
        label="Separazione consensuale",
        area="Civile",
        materia=Materia.VOLONTARIA,
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A7 DM 55/2014 agg. DM 147/2022 — art. 473-bis.51 c.p.c. / art. 158 c.c.",
    ),
    TipoPratica(
        id="separazione_giudiziale",
        label="Separazione giudiziale",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 agg. DM 147/2022 — art. 473-bis.47 c.p.c. / art. 151 c.c.",
    ),
    TipoPratica(
        id="divorzio_congiunto",
        label="Divorzio congiunto",
        area="Civile",
        materia=Materia.VOLONTARIA,
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A7 DM 55/2014 agg. DM 147/2022 — art. 473-bis.51 c.p.c. / L. 898/1970 art. 4",
    ),
    TipoPratica(
        id="divorzio_giudiziale",
        label="Divorzio giudiziale",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 agg. DM 147/2022 — art. 473-bis.47 c.p.c. / L. 898/1970 art. 4",
    ),
    TipoPratica(
        id="procedimenti_famiglia",
        label="Procedimento camerale di famiglia",
        area="Civile",
        materia=Materia.VOLONTARIA,
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A7 DM 55/2014 agg. DM 147/2022 — procedimenti camerali familiari ex artt. 473-bis ss. c.p.c.",
    ),
    TipoPratica(
        id="procedimenti_minori",
        label="Procedimenti relativi ai minori",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 agg. DM 147/2022 — artt. 473-bis ss. c.p.c. / procedimenti relativi ai minori",
    ),
    TipoPratica(
        id="modifica_condizioni_famiglia",
        label="Modifica condizioni separazione / divorzio",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 agg. DM 147/2022 — art. 473-bis.29 c.p.c.",
    ),
    TipoPratica(
        id="responsabilita_genitoriale",
        label="Responsabilita genitoriale e affidamento",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 agg. DM 147/2022 — artt. 337-bis ss. c.c. / artt. 473-bis ss. c.p.c.",
    ),
    TipoPratica(
        id="reclamo_famiglia_minori",
        label="Reclamo famiglia / minori",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.CORTE_APPELLO,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A12 DM 55/2014 agg. DM 147/2022 — art. 473-bis.24 c.p.c.",
    ),
    TipoPratica(
        id="appello_famiglia_minori",
        label="Appello famiglia / minori",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.CORTE_APPELLO,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A12 DM 55/2014 agg. DM 147/2022 — art. 473-bis.30 c.p.c.",
    ),
    TipoPratica(
        id="amministrazione_sostegno",
        label="Amministrazione di sostegno",
        area="Civile",
        materia=Materia.VOLONTARIA,
        grado_default=Grado.GIUDICE_TUTELARE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A7 DM 55/2014 agg. DM 147/2022 — artt. 473-bis.52 ss. c.p.c. / artt. 404 ss. c.c.",
    ),
    TipoPratica(
        id="nomina_amministratore_sostegno",
        label="Nomina amministratore di sostegno",
        area="Civile",
        materia=Materia.VOLONTARIA,
        grado_default=Grado.GIUDICE_TUTELARE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A7 DM 55/2014 agg. DM 147/2022 — artt. 473-bis.52 ss. c.p.c. / artt. 404 e 405 c.c.",
    ),
    TipoPratica(
        id="modifica_revoca_ads",
        label="Modifica / revoca amministrazione di sostegno",
        area="Civile",
        materia=Materia.VOLONTARIA,
        grado_default=Grado.GIUDICE_TUTELARE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A7 DM 55/2014 agg. DM 147/2022 — artt. 473-bis.52 ss. c.p.c. / art. 413 c.c.",
    ),
    TipoPratica(
        id="tutela_curatela",
        label="Tutela / curatela ordinaria",
        area="Civile",
        materia=Materia.VOLONTARIA,
        grado_default=Grado.GIUDICE_TUTELARE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A7 DM 55/2014 agg. DM 147/2022 — artt. 473-bis.64 ss. c.p.c. / artt. 343 ss. c.c.",
    ),
    TipoPratica(
        id="reclamo_giudice_tutelare",
        label="Reclamo avverso decreto del giudice tutelare",
        area="Civile",
        materia=Materia.VOLONTARIA,
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A7 DM 55/2014 agg. DM 147/2022 — art. 739 c.p.c.",
    ),
    TipoPratica(
        id="sfratto_morosita",
        label="Sfratto per morosita / convalida",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A5 DM 55/2014 agg. DM 147/2022 — artt. 657 ss. c.p.c.",
    ),
    TipoPratica(
        id="risarcimento_danni",
        label="Risarcimento danni",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 — artt. 2043 e 2054 c.c.",
    ),

    # ── CIVILE (comprende lavoro e previdenza) ─────────────────────────────

    TipoPratica(
        id="controversia_lavoro",
        label="Controversia di lavoro",
        area="Civile",
        materia=Materia.LAVORO,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A3 DM 55/2014 agg. DM 147/2022 — art. 409 c.p.c.",
    ),
    TipoPratica(
        id="licenziamento",
        label="Licenziamento (impugnazione)",
        area="Civile",
        materia=Materia.LAVORO,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A3 DM 55/2014 — L. 300/1970 art. 18 / D.Lgs. 23/2015",
    ),
    TipoPratica(
        id="differenze_retributive",
        label="Differenze retributive",
        area="Civile",
        materia=Materia.LAVORO,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A3 DM 55/2014 — art. 36 Cost.",
    ),
    TipoPratica(
        id="appello_lavoro",
        label="Appello in materia di lavoro",
        area="Civile",
        materia=Materia.LAVORO,
        grado_default=Grado.CORTE_APPELLO,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A12 DM 55/2014 agg. DM 147/2022 — art. 434 c.p.c.",
    ),
    TipoPratica(
        id="cassazione_lavoro",
        label="Cassazione in materia di lavoro",
        area="Civile",
        materia=Materia.LAVORO,
        grado_default=Grado.CASSAZIONE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A13 DM 55/2014 agg. DM 147/2022 — giudizio di legittimita in materia di lavoro.",
    ),
    TipoPratica(
        id="previdenza",
        label="Previdenza (INPS / INAIL / fondi)",
        area="Civile",
        materia=Materia.PREVIDENZA,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A4 DM 55/2014 agg. DM 147/2022 — artt. 442 ss. c.p.c.",
    ),
    TipoPratica(
        id="appello_previdenza",
        label="Appello previdenziale / assistenziale",
        area="Civile",
        materia=Materia.PREVIDENZA,
        grado_default=Grado.CORTE_APPELLO,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A12 DM 55/2014 agg. DM 147/2022 — giudizio di appello in materia previdenziale e assistenziale.",
    ),
    TipoPratica(
        id="cassazione_previdenza",
        label="Cassazione previdenziale / assistenziale",
        area="Civile",
        materia=Materia.PREVIDENZA,
        grado_default=Grado.CASSAZIONE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A13 DM 55/2014 agg. DM 147/2022 — giudizio di legittimita in materia previdenziale e assistenziale.",
    ),
    TipoPratica(
        id="assistenza_previdenziale",
        label="Assistenza previdenziale / ricorso amministrativo",
        area="Civile",
        materia=Materia.PREVIDENZA,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A4 DM 55/2014 — ricorso amm.vo INPS/INAIL",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),

    # ── PENALE ──────────────────────────────────────────────────────────────

    TipoPratica(
        id="consulenza_penale",
        label="Consulenza / Parere penale",
        area="Penale",
        materia=Materia.STRAGIUD,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO],
        base_normativa="Tab. A25 DM 55/2014 — Prestazioni stragiudiziali",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="denuncia_querela",
        label="Denuncia / Querela",
        area="Penale",
        materia=Materia.STRAGIUD,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA],
        base_normativa="Tab. A25 DM 55/2014 — Prestazioni stragiudiziali",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="indagini_preliminari",
        label="Assistenza in indagini preliminari",
        area="Penale",
        materia=Materia.PENALE,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA],
        base_normativa="Tab. penale DM 55/2014 — art. 61 c.p.p. / fase investigativa",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="udienza_preliminare",
        label="Udienza preliminare",
        area="Penale",
        materia=Materia.PENALE,
        grado_default=Grado.GIP_GUP,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A15 DM 55/2014 agg. DM 147/2022 — colonna GIP/GUP — art. 416 c.p.p.",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="dibattimento_penale",
        label="Dibattimento penale",
        area="Penale",
        materia=Materia.PENALE,
        grado_default=Grado.TRIBUNALE_MONOCRATICO,
        fasi_default=_FASI_PENALE,
        base_normativa="Tab. A15 DM 55/2014 agg. DM 147/2022 — colonne monocratico/collegiale/assise — artt. 470 ss. c.p.p.",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="impugnazioni_penali",
        label="Impugnazioni penali (appello)",
        area="Penale",
        materia=Materia.PENALE,
        grado_default=Grado.CORTE_APPELLO_PENALE,
        fasi_default=_FASI_PENALE,
        base_normativa="Tab. A15 DM 55/2014 agg. DM 147/2022 — colonne appello/sorveglianza/assise appello — artt. 593 ss. c.p.p.",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="cassazione_penale",
        label="Ricorso per Cassazione penale",
        area="Penale",
        materia=Materia.PENALE,
        grado_default=Grado.CASSAZIONE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. penale DM 55/2014 × coeff. 1.60 — art. 606 c.p.p.",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="parte_civile",
        label="Costituzione parte civile",
        area="Penale",
        materia=Materia.PENALE,
        grado_default=Grado.TRIBUNALE_MONOCRATICO,
        fasi_default=_FASI_PENALE,
        base_normativa="Tab. A15 DM 55/2014 agg. DM 147/2022 — colonna del rito penale applicabile — artt. 74-101 c.p.p.",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),

    # ── AMMINISTRATIVO ──────────────────────────────────────────────────────

    TipoPratica(
        id="ricorso_tar",
        label="Ricorso TAR",
        area="Amministrativo",
        materia=Materia.AMMINISTRATIVO,
        grado_default=Grado.TAR,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A21 DM 55/2014 agg. DM 147/2022 — D.Lgs. 104/2010 (Cod. Proc. Amm.)",
    ),
    TipoPratica(
        id="cautelare_sospensiva",
        label="Cautelare / Sospensiva (TAR)",
        area="Amministrativo",
        materia=Materia.AMMINISTRATIVO,
        grado_default=Grado.TAR,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A21 DM 55/2014 — art. 55 D.Lgs. 104/2010",
    ),
    TipoPratica(
        id="motivi_aggiunti",
        label="Motivi aggiunti",
        area="Amministrativo",
        materia=Materia.AMMINISTRATIVO,
        grado_default=Grado.TAR,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA],
        base_normativa="Tab. A21 DM 55/2014 — art. 43 D.Lgs. 104/2010",
    ),
    TipoPratica(
        id="appello_cds",
        label="Appello Consiglio di Stato",
        area="Amministrativo",
        materia=Materia.AMMINISTRATIVO,
        grado_default=Grado.CONSIGLIO_DI_STATO,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A22 DM 55/2014 × coeff. 1.30 — artt. 91 ss. D.Lgs. 104/2010",
    ),
    TipoPratica(
        id="ottemperanza",
        label="Giudizio di ottemperanza",
        area="Amministrativo",
        materia=Materia.AMMINISTRATIVO,
        grado_default=Grado.TAR,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A21 DM 55/2014 — artt. 112 ss. D.Lgs. 104/2010",
    ),

    # ── TRIBUTARIO ──────────────────────────────────────────────────────────

    TipoPratica(
        id="ricorso_tributario",
        label="Ricorso tributario (CGT primo grado)",
        area="Tributario",
        materia=Materia.TRIBUTARIO,
        grado_default=Grado.CGT_PRIMO_GRADO,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A23 DM 55/2014 agg. DM 147/2022 — D.Lgs. 546/1992",
    ),
    TipoPratica(
        id="appello_tributario",
        label="Appello tributario (CGT secondo grado)",
        area="Tributario",
        materia=Materia.TRIBUTARIO,
        grado_default=Grado.CGT_SECONDO_GRADO,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A24 DM 55/2014 — art. 52 D.Lgs. 546/1992",
    ),
    TipoPratica(
        id="cassazione_tributaria",
        label="Cassazione tributaria",
        area="Tributario",
        materia=Materia.TRIBUTARIO,
        grado_default=Grado.CASSAZIONE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A13 DM 55/2014 agg. DM 147/2022 — art. 62 D.Lgs. 546/1992",
    ),
    TipoPratica(
        id="autotutela",
        label="Autotutela tributaria",
        area="Tributario",
        materia=Materia.STRAGIUD,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA],
        base_normativa="Tab. A25 DM 55/2014 — D.Lgs. 219/2023 (riforma autotutela)",
        richiede_valore=True,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="accertamento_adesione",
        label="Accertamento con adesione",
        area="Tributario",
        materia=Materia.STRAGIUD,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A25 DM 55/2014 — D.Lgs. 218/1997",
        richiede_valore=True,
        tipo_compenso_default="Compenso fisso",
    ),

    # ── STRAGIUDIZIALE ──────────────────────────────────────────────────────

    TipoPratica(
        id="parere",
        label="Parere legale",
        area="Stragiudiziale",
        materia=Materia.STRAGIUD,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO],
        base_normativa="Tab. A25 DM 55/2014 — Prestazioni stragiudiziali",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="consulenza",
        label="Consulenza legale",
        area="Stragiudiziale",
        materia=Materia.STRAGIUD,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA],
        base_normativa="Tab. A25 DM 55/2014 — Prestazioni stragiudiziali",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="assistenza_trattativa",
        label="Assistenza in trattativa",
        area="Stragiudiziale",
        materia=Materia.STRAGIUD,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA],
        base_normativa="Tab. A25 DM 55/2014 — Prestazioni stragiudiziali",
        richiede_valore=True,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="redazione_contratto",
        label="Redazione contratto",
        area="Stragiudiziale",
        materia=Materia.STRAGIUD,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA],
        base_normativa="Tab. A25 DM 55/2014 — Prestazioni stragiudiziali",
        richiede_valore=True,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="revisione_contratto",
        label="Revisione / Due diligence contrattuale",
        area="Stragiudiziale",
        materia=Materia.STRAGIUD,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO],
        base_normativa="Tab. A25 DM 55/2014 — Prestazioni stragiudiziali",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="sinistro_stradale_stragiudiziale",
        label="Sinistro stradale / richiesta risarcitoria stragiudiziale",
        area="Stragiudiziale",
        materia=Materia.STRAGIUD,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA],
        base_normativa="Tab. A25 DM 55/2014 — artt. 145, 148 e 149 D.Lgs. 209/2005",
        richiede_valore=True,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="mediazione",
        label="Mediazione (D.Lgs. 28/2010)",
        area="Stragiudiziale",
        materia=Materia.MEDIAZIONE,
        grado_default=Grado.PROCEDURA_ADR,
        fasi_default=[Fase.ATTIVAZIONE, Fase.RIVITALIZZAZIONE, Fase.CONCILIAZIONE],
        base_normativa="Tab. A27 DM 55/2014 agg. DM 147/2022 — D.Lgs. 28/2010",
        richiede_valore=True,
        tipo_compenso_default="Per fasi processuali (D.M. 55/2014)",
        variation_policy=_adr_variation_policy("mediazione"),
    ),
    TipoPratica(
        id="negoziazione_assistita",
        label="Negoziazione assistita (D.L. 132/2014)",
        area="Stragiudiziale",
        materia=Materia.NEGOZIAZIONE_ASSISTITA,
        grado_default=Grado.PROCEDURA_ADR,
        fasi_default=[Fase.ATTIVAZIONE, Fase.NEGOZIAZIONE_TRATTAZIONE, Fase.CONCILIAZIONE],
        base_normativa="Tab. A27 DM 55/2014 agg. DM 147/2022 — D.L. 132/2014 conv. L. 162/2014",
        richiede_valore=True,
        tipo_compenso_default="Per fasi processuali (D.M. 55/2014)",
        variation_policy=_adr_variation_policy("negoziazione"),
    ),
    TipoPratica(
        id="transazione",
        label="Transazione / Accordo stragiudiziale",
        area="Stragiudiziale",
        materia=Materia.STRAGIUD,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A25 DM 55/2014 — art. 1965 c.c.",
        richiede_valore=True,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="recupero_crediti_stragiud",
        label="Recupero crediti stragiudiziale",
        area="Stragiudiziale",
        materia=Materia.STRAGIUD,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA],
        base_normativa="Tab. A25 DM 55/2014 — Prestazioni stragiudiziali",
        richiede_valore=True,
        tipo_compenso_default="Compenso fisso",
    ),

    # ── SPECIALI ────────────────────────────────────────────────────────────

    TipoPratica(
        id="arbitrato",
        label="Arbitrato",
        area="Speciali",
        materia=Materia.ARBITRATO,
        grado_default=Grado.PROCEDURA_ADR,
        fasi_default=[Fase.STUDIO],
        base_normativa="Tab. A26 DM 55/2014 agg. DM 147/2022 — artt. 806 ss. c.p.c.",
    ),
    TipoPratica(
        id="domiciliazione",
        label="Domiciliazione",
        area="Speciali",
        materia=Materia.STRAGIUD,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO],
        base_normativa="Tab. A25 DM 55/2014 — Prestazioni stragiudiziali / domiciliazione",
        richiede_valore=False,
        tipo_compenso_default="Compenso orario",
    ),
    TipoPratica(
        id="attivita_tempo",
        label="Attività a tempo (compenso orario)",
        area="Speciali",
        materia=Materia.STRAGIUD,
        grado_default=Grado.FUORI_GIUDIZIO,
        fasi_default=[Fase.STUDIO],
        base_normativa="L. 247/2012 art. 13 co. 2 — compenso orario libero accordo",
        richiede_valore=False,
        tipo_compenso_default="Compenso orario",
    ),
    TipoPratica(
        id="procedure_particolari",
        label="Procedure particolari / varie",
        area="Speciali",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 (applicazione per analogia)",
    ),
]

CATALOGO.extend(
    [
        TipoPratica(
            id="istruzione_preventiva",
            label="Istruzione preventiva / ATP",
            area="Civile",
            materia=Materia.CIVILE_COGN,
            grado_default=Grado.GIUDICE_COMPETENTE,
            fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA],
            base_normativa="Tab. A9 DM 55/2014 agg. DM 147/2022 - artt. 692 ss. c.p.c.",
        ),
        TipoPratica(
            id="cautelare_civile",
            label="Procedimento cautelare civile",
            area="Civile",
            materia=Materia.CIVILE_COGN,
            grado_default=Grado.GIUDICE_COMPETENTE,
            fasi_default=_FASI_BASE,
            base_normativa="Tab. A10 DM 55/2014 agg. DM 147/2022 - artt. 669-bis ss. c.p.c.",
        ),
        TipoPratica(
            id="giudice_pace_penale",
            label="Giudizio penale davanti al Giudice di Pace",
            area="Penale",
            materia=Materia.PENALE,
            grado_default=Grado.GIUDICE_DI_PACE,
            fasi_default=_FASI_PENALE,
            base_normativa="Tab. A15 DM 55/2014 agg. DM 147/2022 - colonna Giudice di Pace penale.",
            richiede_valore=False,
            tipo_compenso_default="Compenso fisso",
        ),
        TipoPratica(
            id="indagini_difensive",
            label="Indagini difensive",
            area="Penale",
            materia=Materia.PENALE,
            grado_default=Grado.FUORI_GIUDIZIO,
            fasi_default=[Fase.STUDIO, Fase.ISTRUTTORIA],
            base_normativa="Tab. A15 DM 55/2014 agg. DM 147/2022 - indagini difensive - artt. 391-bis ss. c.p.p.",
            richiede_valore=False,
            tipo_compenso_default="Compenso fisso",
        ),
        TipoPratica(
            id="convalida_arresto",
            label="Convalida arresto / fermo",
            area="Penale",
            materia=Materia.PENALE,
            grado_default=Grado.GIP_GUP,
            fasi_default=[Fase.STUDIO, Fase.ISTRUTTORIA, Fase.DECISIONALE],
            base_normativa="Tab. A15 DM 55/2014 agg. DM 147/2022 - convalida dell'arresto - artt. 390 ss. c.p.p.",
            richiede_valore=False,
            tipo_compenso_default="Compenso fisso",
        ),
        TipoPratica(
            id="misure_cautelari_penali",
            label="Misure cautelari penali",
            area="Penale",
            materia=Materia.PENALE,
            grado_default=Grado.GIP_GUP,
            fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
            base_normativa="Tab. A15 DM 55/2014 agg. DM 147/2022 - cautelari personali e reali - artt. 272 ss. e 321 ss. c.p.p.",
            richiede_valore=False,
            tipo_compenso_default="Compenso fisso",
        ),
        TipoPratica(
            id="sorveglianza_penale",
            label="Sorveglianza penale",
            area="Penale",
            materia=Materia.PENALE,
            grado_default=Grado.TRIBUNALE_SORVEGLIANZA,
            fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
            base_normativa="Tab. A15 DM 55/2014 agg. DM 147/2022 - tribunale e magistrato di sorveglianza.",
            richiede_valore=False,
            tipo_compenso_default="Compenso fisso",
        ),
        TipoPratica(
            id="giudizio_corte_conti",
            label="Giudizio innanzi alla Corte dei Conti",
            area="Speciali",
            materia=Materia.CONTABILE,
            grado_default=Grado.CORTE_DEI_CONTI,
            fasi_default=_FASI_BASE,
            base_normativa="Tab. A11 DM 55/2014 agg. DM 147/2022 - giudizi innanzi alla Corte dei Conti.",
        ),
        TipoPratica(
            id="giurisdizioni_superiori",
            label="Giurisdizioni superiori / europee",
            area="Speciali",
            materia=Materia.GIURISDIZIONI_SUPERIORI,
            grado_default=Grado.CORTE_COSTITUZIONALE,
            fasi_default=_FASI_BASE,
            base_normativa="Tab. A14 DM 55/2014 agg. DM 147/2022 - giurisdizioni costituzionali e sovranazionali.",
        ),
        TipoPratica(
            id="iscrizione_ipotecaria_tavolare",
            label="Iscrizione ipotecaria / affari tavolari",
            area="Speciali",
            materia=Materia.AFFARI_IPOTECARI,
            grado_default=Grado.CONSERVATORIA_TAVOLARE,
            fasi_default=[Fase.STUDIO],
            base_normativa="Tab. A19 DM 55/2014 agg. DM 147/2022 - iscrizione ipotecaria / affari tavolari.",
        ),
        TipoPratica(
            id="apertura_liquidazione_giudiziale",
            label="Apertura liquidazione giudiziale",
            area="Speciali",
            materia=Materia.CRISI_IMPRESA,
            grado_default=Grado.TRIBUNALE_CONCORSUALE,
            fasi_default=[Fase.STUDIO],
            base_normativa="Tab. A20 DM 55/2014 agg. DM 147/2022 - procedimenti di apertura concorsuale oggi coordinati con la liquidazione giudiziale.",
        ),
        TipoPratica(
            id="accertamento_passivo",
            label="Accertamento del passivo",
            area="Speciali",
            materia=Materia.CRISI_IMPRESA,
            grado_default=Grado.TRIBUNALE_CONCORSUALE,
            fasi_default=_FASI_BASE,
            base_normativa="Tab. A20-bis DM 55/2014 agg. DM 147/2022 - accertamento del passivo nel fallimento e nella liquidazione giudiziale.",
        ),
    ]
)

# Indice rapido id → TipoPratica
_IDX: Dict[str, TipoPratica] = {tp.id: tp for tp in CATALOGO}


# ──────────────────────────────────────────────────────────────────────────────
# Esborsi tipici per tipologia (importi orientativi — Art. 15 DPR 633/72)
# ──────────────────────────────────────────────────────────────────────────────

_ESBORSI_TIPICI: Dict[str, List[Dict]] = {
    # ── CIVILE ──
    "consulenza_civile": [
        {"descrizione": "Ricerca giurisprudenziale / banche dati", "importo": 30.0},
    ],
    "diffida": [
        {"descrizione": "Raccomandata A/R o notifica", "importo": 10.0},
        {"descrizione": "PEC (se invio telematico)", "importo": 5.0},
    ],
    "recupero_crediti": [
        {"descrizione": "Diritti di segreteria ricorso", "importo": 27.0},
        {"descrizione": "Contributo Unificato (indicativo)", "importo": 98.0},
        {"descrizione": "Notifica tramite Ufficiale Giudiziario", "importo": 25.0},
    ],
    "decreto_ingiuntivo": [
        {"descrizione": "Diritti di segreteria ricorso D.I.", "importo": 27.0},
        {"descrizione": "Contributo Unificato", "importo": 98.0},
        {"descrizione": "Notifica D.I. tramite U.G.", "importo": 25.0},
        {"descrizione": "Diritti U.G. notifica", "importo": 12.0},
    ],
    "opposizione_di": [
        {"descrizione": "Contributo Unificato opposizione", "importo": 196.0},
        {"descrizione": "Notifica atto di citazione", "importo": 25.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
    ],
    "atto_citazione": [
        {"descrizione": "Contributo Unificato (indicativo)", "importo": 196.0},
        {"descrizione": "Notifica atto citazione tramite U.G.", "importo": 25.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
    ],
    "comparsa_risposta": [
        {"descrizione": "Diritti di segreteria comparsa", "importo": 27.0},
        {"descrizione": "Contributo Unificato (se non già versato)", "importo": 196.0},
    ],
    "appello_civile": [
        {"descrizione": "Contributo Unificato appello", "importo": 392.0},
        {"descrizione": "Notifica atto di appello", "importo": 25.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
    ],
    "cassazione_civile": [
        {"descrizione": "Contributo Unificato Cassazione", "importo": 784.0},
        {"descrizione": "Notifica ricorso Cassazione", "importo": 30.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
    ],
    "precetto": [
        {"descrizione": "Notifica precetto tramite U.G.", "importo": 25.0},
        {"descrizione": "Diritti U.G. notifica precetto", "importo": 12.0},
        {"descrizione": "Copia autentica titolo esecutivo", "importo": 15.0},
    ],
    "pignoramento": [
        {"descrizione": "Diritti U.G. pignoramento mobiliare", "importo": 50.0},
        {"descrizione": "Iscrizione a ruolo procedura esecutiva", "importo": 43.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
    ],
    "esecuzione_mobiliare": [
        {"descrizione": "Diritti U.G.", "importo": 50.0},
        {"descrizione": "Iscrizione a ruolo", "importo": 43.0},
        {"descrizione": "Perizia beni mobili (CTP)", "importo": 150.0},
    ],
    "esecuzione_immobiliare": [
        {"descrizione": "Iscrizione a ruolo esecuzione immobiliare", "importo": 278.0},
        {"descrizione": "Perizia estimativa CTU immobile", "importo": 500.0},
        {"descrizione": "Estratti catastali / visure ipotecarie", "importo": 30.0},
        {"descrizione": "Notifiche U.G.", "importo": 25.0},
    ],
    "esecuzione_terzi": [
        {"descrizione": "Iscrizione a ruolo pignoramento c/terzi", "importo": 43.0},
        {"descrizione": "Notifica U.G.", "importo": 25.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
    ],
    "opposizione_esecutiva": [
        {"descrizione": "Contributo Unificato opposizione esec.", "importo": 196.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
    ],
    "opposizione_atti_esecutivi": [
        {"descrizione": "Contributo Unificato opposizione atti esecutivi", "importo": 196.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
        {"descrizione": "Notifica ricorso / citazione", "importo": 25.0},
    ],
    "separazione_consensuale": [
        {"descrizione": "Diritti di segreteria ricorso", "importo": 27.0},
        {"descrizione": "Bollo verbale udienza", "importo": 16.0},
    ],
    "separazione_giudiziale": [
        {"descrizione": "Contributo Unificato", "importo": 196.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
        {"descrizione": "Notifica atto citazione", "importo": 25.0},
    ],
    "divorzio_congiunto": [
        {"descrizione": "Diritti di segreteria ricorso", "importo": 27.0},
        {"descrizione": "Bollo verbale udienza", "importo": 16.0},
    ],
    "divorzio_giudiziale": [
        {"descrizione": "Contributo Unificato", "importo": 196.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
        {"descrizione": "Notifica atto di citazione", "importo": 25.0},
    ],
    "procedimenti_famiglia": [
        {"descrizione": "Diritti di segreteria ricorso camerale", "importo": 27.0},
        {"descrizione": "Contributo Unificato (se dovuto)", "importo": 98.0},
    ],
    "procedimenti_minori": [
        {"descrizione": "Diritti di segreteria ricorso", "importo": 27.0},
        {"descrizione": "Contributo Unificato (se dovuto)", "importo": 98.0},
    ],
    "modifica_condizioni_famiglia": [
        {"descrizione": "Diritti di segreteria ricorso", "importo": 27.0},
        {"descrizione": "Contributo Unificato (se dovuto)", "importo": 98.0},
        {"descrizione": "Notifica ricorso / decreto", "importo": 25.0},
    ],
    "responsabilita_genitoriale": [
        {"descrizione": "Diritti di segreteria ricorso", "importo": 27.0},
        {"descrizione": "Contributo Unificato (se dovuto)", "importo": 98.0},
        {"descrizione": "Notifica ricorso / provvedimento", "importo": 25.0},
    ],
    "reclamo_famiglia_minori": [
        {"descrizione": "Diritti di segreteria reclamo", "importo": 27.0},
        {"descrizione": "Contributo Unificato (se dovuto)", "importo": 98.0},
        {"descrizione": "Notifica reclamo", "importo": 25.0},
    ],
    "appello_famiglia_minori": [
        {"descrizione": "Contributo Unificato appello (se dovuto)", "importo": 392.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
        {"descrizione": "Notifica atto di appello", "importo": 25.0},
    ],
    "amministrazione_sostegno": [
        {"descrizione": "Diritti di segreteria ricorso al giudice tutelare", "importo": 27.0},
        {"descrizione": "Certificazioni e visure sanitarie / anagrafiche", "importo": 25.0},
    ],
    "nomina_amministratore_sostegno": [
        {"descrizione": "Diritti di segreteria ricorso al giudice tutelare", "importo": 27.0},
        {"descrizione": "Certificazioni mediche e documentazione anagrafica", "importo": 25.0},
        {"descrizione": "Visure patrimoniali essenziali", "importo": 20.0},
    ],
    "modifica_revoca_ads": [
        {"descrizione": "Diritti di segreteria istanza", "importo": 27.0},
        {"descrizione": "Aggiornamento certificazioni / relazioni", "importo": 25.0},
    ],
    "tutela_curatela": [
        {"descrizione": "Diritti di segreteria ricorso", "importo": 27.0},
        {"descrizione": "Certificati stato civile / anagrafici", "importo": 20.0},
        {"descrizione": "Visure patrimoniali iniziali", "importo": 20.0},
    ],
    "reclamo_giudice_tutelare": [
        {"descrizione": "Diritti di segreteria reclamo", "importo": 27.0},
        {"descrizione": "Notifica reclamo (se richiesta)", "importo": 25.0},
        {"descrizione": "Copie autentiche del decreto reclamato", "importo": 15.0},
    ],
    "sfratto_morosita": [
        {"descrizione": "Contributo Unificato (indicativo)", "importo": 103.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
        {"descrizione": "Notifica intimazione / citazione", "importo": 25.0},
    ],
    "risarcimento_danni": [
        {"descrizione": "Contributo Unificato (indicativo)", "importo": 196.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
        {"descrizione": "Notifica atto introduttivo", "importo": 25.0},
        {"descrizione": "Perizia di parte / relazione tecnica (indicativa)", "importo": 250.0},
    ],
    # ── LAVORO ──
    "controversia_lavoro": [
        {"descrizione": "Diritti di segreteria ricorso lavoro", "importo": 27.0},
        {"descrizione": "Contributo Unificato lavoro", "importo": 18.0},
        {"descrizione": "Notifica (se richiesta)", "importo": 15.0},
    ],
    "licenziamento": [
        {"descrizione": "Diritti di segreteria ricorso", "importo": 27.0},
        {"descrizione": "Contributo Unificato", "importo": 18.0},
    ],
    "differenze_retributive": [
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
        {"descrizione": "Contributo Unificato", "importo": 18.0},
        {"descrizione": "Estratti busta paga / documenti", "importo": 20.0},
    ],
    "appello_lavoro": [
        {"descrizione": "Contributo Unificato appello lavoro", "importo": 36.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
    ],
    "cassazione_lavoro": [
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
        {"descrizione": "Notifica ricorso per Cassazione", "importo": 30.0},
    ],
    "previdenza": [
        {"descrizione": "Diritti di segreteria ricorso previdenziale", "importo": 27.0},
        {"descrizione": "Contributo Unificato previdenziale", "importo": 9.0},
    ],
    "appello_previdenza": [
        {"descrizione": "Diritti di segreteria appello previdenziale", "importo": 27.0},
    ],
    "cassazione_previdenza": [
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
        {"descrizione": "Notifica ricorso per Cassazione", "importo": 30.0},
    ],
    "assistenza_previdenziale": [
        {"descrizione": "Spedizione raccomandata / PEC", "importo": 10.0},
        {"descrizione": "Bollo istanza amministrativa", "importo": 16.0},
    ],
    # ── PENALE ──
    "consulenza_penale": [
        {"descrizione": "Accesso atti / copie fascicolo", "importo": 30.0},
    ],
    "denuncia_querela": [
        {"descrizione": "Bollo querela (se dovuto)", "importo": 16.0},
        {"descrizione": "Raccomandata / notifica", "importo": 10.0},
    ],
    "indagini_preliminari": [
        {"descrizione": "Accesso atti RGNR", "importo": 20.0},
        {"descrizione": "Copie atti procedimento", "importo": 30.0},
    ],
    "udienza_preliminare": [
        {"descrizione": "Copie atti udienza", "importo": 20.0},
    ],
    "dibattimento_penale": [
        {"descrizione": "Copie fascicolo dibattimentale", "importo": 50.0},
        {"descrizione": "CTP (consulente tecnico di parte)", "importo": 300.0},
        {"descrizione": "Accesso atti", "importo": 20.0},
    ],
    "impugnazioni_penali": [
        {"descrizione": "Estratto sentenza", "importo": 20.0},
        {"descrizione": "Copie atti per appello", "importo": 30.0},
    ],
    "cassazione_penale": [
        {"descrizione": "Estratto sentenza appellata", "importo": 20.0},
        {"descrizione": "Copie atti per Cassazione", "importo": 40.0},
    ],
    "parte_civile": [
        {"descrizione": "Costituzione parte civile (deposito)", "importo": 15.0},
        {"descrizione": "Copie atti dibattimento", "importo": 30.0},
    ],
    # ── AMMINISTRATIVO ──
    "ricorso_tar": [
        {"descrizione": "Contributo Unificato TAR (base)", "importo": 650.0},
        {"descrizione": "Diritti di segreteria ricorso", "importo": 27.0},
        {"descrizione": "Notifica ricorso (atti da notificare)", "importo": 30.0},
    ],
    "cautelare_sospensiva": [
        {"descrizione": "Contributo Unificato TAR (+ misura cautelare)", "importo": 650.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
        {"descrizione": "Notifica motivi aggiunti/cautelare", "importo": 25.0},
    ],
    "motivi_aggiunti": [
        {"descrizione": "Contributo Unificato motivi aggiunti", "importo": 650.0},
        {"descrizione": "Notifica motivi aggiunti", "importo": 25.0},
    ],
    "appello_cds": [
        {"descrizione": "Contributo Unificato CdS", "importo": 1300.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
        {"descrizione": "Notifica appello", "importo": 30.0},
    ],
    "ottemperanza": [
        {"descrizione": "Contributo Unificato ottemperanza", "importo": 650.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
    ],
    # ── TRIBUTARIO ──
    "ricorso_tributario": [
        {"descrizione": "Contributo Unificato CGT (base)", "importo": 30.0},
        {"descrizione": "Diritti di segreteria ricorso", "importo": 27.0},
        {"descrizione": "Notifica ricorso", "importo": 15.0},
    ],
    "appello_tributario": [
        {"descrizione": "Contributo Unificato CGT appello", "importo": 60.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
    ],
    "cassazione_tributaria": [
        {"descrizione": "Contributo Unificato Cassazione trib.", "importo": 784.0},
        {"descrizione": "Diritti di segreteria", "importo": 27.0},
    ],
    "autotutela": [
        {"descrizione": "Raccomandata / PEC istanza", "importo": 10.0},
        {"descrizione": "Bollo istanza (se dovuto)", "importo": 16.0},
    ],
    "accertamento_adesione": [
        {"descrizione": "Raccomandata / PEC domanda adesione", "importo": 10.0},
        {"descrizione": "Bollo richiesta accertamento adesione", "importo": 16.0},
    ],
    # ── STRAGIUDIZIALE ──
    "sinistro_stradale_stragiudiziale": [
        {"descrizione": "Visura PRA / documenti veicolo", "importo": 15.0},
        {"descrizione": "PEC / raccomandate alla compagnia", "importo": 15.0},
        {"descrizione": "Perizia medico-legale o tecnica (indicativa)", "importo": 180.0},
    ],
    "mediazione": [
        {"descrizione": "Indennità organismo di mediazione (indicativa)", "importo": 100.0},
        {"descrizione": "Spese postali / PEC organismo", "importo": 15.0},
    ],
    "negoziazione_assistita": [
        {"descrizione": "Spese notarili accordo (se richiesto)", "importo": 50.0},
        {"descrizione": "Raccomandate / PEC", "importo": 15.0},
    ],
    "transazione": [
        {"descrizione": "Bollo atto transazione (€ 16 ogni 4 facciate)", "importo": 32.0},
        {"descrizione": "Raccomandata / PEC", "importo": 10.0},
    ],
    "recupero_crediti_stragiud": [
        {"descrizione": "Raccomandate A/R diffida", "importo": 10.0},
        {"descrizione": "PEC diffida", "importo": 5.0},
    ],
    # ── SPECIALI ──
    "arbitrato": [
        {"descrizione": "Diritti Camera Arbitrale (indicativo)", "importo": 250.0},
        {"descrizione": "Compenso arbitri (anticipo)", "importo": 500.0},
        {"descrizione": "Spese di segreteria", "importo": 50.0},
    ],
}

_ESBORSI_TIPICI.update(
    {
        "istruzione_preventiva": [
            {"descrizione": "Contributo unificato (se dovuto)", "importo": 147.0},
            {"descrizione": "Diritti di segreteria", "importo": 27.0},
        ],
        "cautelare_civile": [
            {"descrizione": "Contributo unificato cautelare (indicativo)", "importo": 147.0},
            {"descrizione": "Diritti di segreteria", "importo": 27.0},
            {"descrizione": "Notifica ricorso / decreto", "importo": 25.0},
        ],
        "giudice_pace_penale": [
            {"descrizione": "Copie atti procedimento", "importo": 20.0},
        ],
        "indagini_difensive": [
            {"descrizione": "Investigazioni difensive / acquisizione documenti", "importo": 80.0},
        ],
        "convalida_arresto": [
            {"descrizione": "Accesso atti / copie urgenti", "importo": 20.0},
        ],
        "misure_cautelari_penali": [
            {"descrizione": "Copie atti cautelari", "importo": 20.0},
            {"descrizione": "Notifiche / accessi urgenti", "importo": 15.0},
        ],
        "sorveglianza_penale": [
            {"descrizione": "Copie atti esecutivi penali", "importo": 20.0},
        ],
        "giudizio_corte_conti": [
            {"descrizione": "Contributo unificato contabile (se dovuto)", "importo": 259.0},
            {"descrizione": "Diritti di segreteria", "importo": 27.0},
        ],
        "giurisdizioni_superiori": [
            {"descrizione": "Diritti di cancelleria / traduzioni", "importo": 60.0},
        ],
        "iscrizione_ipotecaria_tavolare": [
            {"descrizione": "Tassa ipotecaria / diritti conservatoria", "importo": 35.0},
            {"descrizione": "Visure e formalita", "importo": 30.0},
        ],
        "apertura_liquidazione_giudiziale": [
            {"descrizione": "Diritti di segreteria", "importo": 27.0},
            {"descrizione": "Contributo unificato concorsuale (indicativo)", "importo": 518.0},
        ],
        "accertamento_passivo": [
            {"descrizione": "Contributo unificato opposizione stato passivo (indicativo)", "importo": 518.0},
            {"descrizione": "Diritti di segreteria", "importo": 27.0},
        ],
    }
)


_URL_LEGGE_FORENSE = "https://www.gazzettaufficiale.it/eli/id/2013/01/18/13G00018/sg"
_URL_DM55 = (
    "https://www.normattiva.it/atto/caricaDettaglioAtto?"
    "atto.codiceRedazionale=14G00067&atto.dataPubblicazioneGazzetta=2014-04-02"
    "&bloccoAggiornamentoBreadCrumb=true&classica=true&dataVigenza=11%2F03%2F2026"
)
_URL_DM147 = (
    "https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?"
    "atto.codiceRedazionale=22G00157&atto.dataPubblicazioneGazzetta=2022-10-08"
    "&atto.tipoProvvedimento=DECRETO"
)
_URL_EQUO_COMPENSO = (
    "https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?"
    "atto.codiceRedazionale=23G00051&atto.dataPubblicazioneGazzetta=2023-05-05"
    "&atto.tipoProvvedimento=LEGGE"
)
_URL_DPR633 = "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.del.presidente.della.repubblica%3A1972-10-26%3B633"
_URL_CPC = "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Aregio.decreto%3A1940-10-28%3B1443"
_URL_CC = "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Aregio.decreto%3A1942-03-16%3B262"
_URL_DLGS149 = "https://www.normattiva.it/eli/id/2022/10/17/22G00158/CONSOLIDATED/"
_URL_CPP = (
    "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.del.presidente.della.repubblica"
    "%3A1988-09-22%3B447"
)
_URL_CPA = "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legislativo%3A2010-07-02%3B104"
_URL_TRIBUTARIO = "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legislativo%3A1992-12-31%3B546"
_URL_CODICE_GIUSTIZIA_CONTABILE = "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=16G00187&atto.dataPubblicazioneGazzetta=2016-09-07&qId=&tipoDettaglio=multivigenza"
_URL_CODICE_CRISE_IMPRESA = "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legislativo%3A2019%3B14="
_URL_ORDINAMENTO_PENITENZIARIO = "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Alegge%3A1975-07-26%3B354"
_URL_MEDIAZIONE = "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legislativo%3A2010-03-04%3B28"
_URL_REGISTRO_MEDIAZIONE_INFO = "https://www.giustizia.it/giustizia/it/mg_3_4_15.page"
_URL_NEGOZIAZIONE = "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legge%3A2014-09-12%3B132"
_URL_DM150_MEDIAZIONE = (
    "https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?"
    "atto.codiceRedazionale=23G00162&atto.dataPubblicazioneGazzetta=2023-10-31"
    "&atto.tipoProvvedimento=DECRETO"
)
_URL_CODICE_ASSICURAZIONI = (
    "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legislativo%3A2005-09-07%3B209"
)

_RIF_MEDIAZIONE_LOCAZIONE = [
    {
        "title": "D.Lgs. 4 marzo 2010, n. 28",
        "article": "art. 5, comma 1 — locazione",
        "description": "Nelle controversie in materia di locazione la mediazione costituisce condizione di procedibilita della domanda giudiziale.",
        "url": _URL_MEDIAZIONE,
    },
    {
        "title": "D.M. 24 ottobre 2023, n. 150",
        "article": "spese e indennita di mediazione",
        "description": "Disciplina delle spese, indennita e maggiorazioni applicabili nella procedura di mediazione dopo la riforma Cartabia.",
        "url": _URL_DM150_MEDIAZIONE,
    },
    {
        "title": "Ministero della Giustizia",
        "article": "registro organismi di mediazione",
        "description": "Scheda ministeriale per verificare il registro ufficiale degli organismi di mediazione e le modalita tecniche di consultazione del portale dedicato.",
        "url": _URL_REGISTRO_MEDIAZIONE_INFO,
    },
]

_RIF_MEDIAZIONE_GENERALE = [
    {
        "title": "D.Lgs. 4 marzo 2010, n. 28",
        "article": "art. 5 e procedimento di mediazione",
        "description": "Disciplina della mediazione civile e commerciale e delle ipotesi in cui la procedura puo rilevare come condizione di procedibilita o come scelta strategica preventiva.",
        "url": _URL_MEDIAZIONE,
    },
    {
        "title": "D.M. 24 ottobre 2023, n. 150",
        "article": "spese e indennita di mediazione",
        "description": "Regolamento vigente su spese, indennita e maggiorazioni applicabili agli organismi di mediazione.",
        "url": _URL_DM150_MEDIAZIONE,
    },
    {
        "title": "Ministero della Giustizia",
        "article": "registro organismi di mediazione",
        "description": "Registro ufficiale e scheda ministeriale per verificare organismi iscritti e operativita del portale dedicato.",
        "url": _URL_REGISTRO_MEDIAZIONE_INFO,
    },
]

_RIFERIMENTI_BASE: List[Dict[str, str]] = [
    {
        "title": "L. 31 dicembre 2012, n. 247",
        "article": "art. 13",
        "description": "Conferimento dell'incarico, obbligo di informativa sul compenso e pattuizione con il cliente.",
        "url": _URL_LEGGE_FORENSE,
    },
    {
        "title": "D.M. 10 marzo 2014, n. 55",
        "article": "parametri forensi",
        "description": "Parametri di riferimento per la liquidazione dei compensi professionali forensi.",
        "url": _URL_DM55,
    },
    {
        "title": "D.M. 13 agosto 2022, n. 147",
        "article": "aggiornamento tabelle",
        "description": "Aggiornamento dei parametri forensi e delle tabelle applicative.",
        "url": _URL_DM147,
    },
    {
        "title": "L. 21 aprile 2023, n. 49",
        "article": "equo compenso",
        "description": "Presidio sull'equo compenso nei rapporti con clienti qualificati e grandi committenti.",
        "url": _URL_EQUO_COMPENSO,
    },
    {
        "title": "D.P.R. 26 ottobre 1972, n. 633",
        "article": "art. 15",
        "description": "Disciplina delle anticipazioni e delle spese vive non imponibili IVA quando riaddebitate al cliente.",
        "url": _URL_DPR633,
    },
]

_RIFERIMENTI_AREA: Dict[str, Dict[str, str]] = {
    "Civile": {
        "title": "Codice di procedura civile",
        "description": "Riferimento processuale della tipologia selezionata in ambito civile.",
        "url": _URL_CPC,
    },
    "Lavoro e previdenza": {
        "title": "Codice di procedura civile",
        "description": "Riferimento processuale del rito lavoro e previdenza.",
        "url": _URL_CPC,
    },
    "Penale": {
        "title": "Codice di procedura penale",
        "description": "Riferimento processuale della tipologia selezionata in ambito penale.",
        "url": _URL_CPP,
    },
    "Amministrativo": {
        "title": "Codice del processo amministrativo",
        "description": "Riferimento processuale della tipologia selezionata in ambito amministrativo.",
        "url": _URL_CPA,
    },
    "Tributario": {
        "title": "D.Lgs. 31 dicembre 1992, n. 546",
        "description": "Riferimento processuale del contenzioso tributario.",
        "url": _URL_TRIBUTARIO,
    },
    "Stragiudiziale": {
        "title": "Prestazioni stragiudiziali",
        "description": "Prestazioni stragiudiziali e strumenti ADR richiamati per la tipologia selezionata.",
        "url": _URL_MEDIAZIONE,
    },
    "Speciali": {
        "title": "Accordo professionale e criteri analogici",
        "description": "Prestazioni speciali o atipiche con compenso pattizio o applicazione analogica dei parametri.",
        "url": _URL_LEGGE_FORENSE,
    },
}

_MOTORE_PER_AREA = {
    "Civile": "Motore parametrico giudiziale civile",
    "Lavoro e previdenza": "Motore parametrico lavoro e previdenza",
    "Penale": "Motore parametrico penale",
    "Amministrativo": "Motore parametrico amministrativo",
    "Tributario": "Motore parametrico tributario",
    "Stragiudiziale": "Motore preventivo stragiudiziale / ADR",
    "Speciali": "Motore preventivo speciale e pattizio",
}

_REDATTORE_PER_AREA = {
    "Civile": "Redattore preventivo giudiziale civile",
    "Lavoro e previdenza": "Redattore preventivo rito lavoro",
    "Penale": "Redattore preventivo penale",
    "Amministrativo": "Redattore preventivo amministrativo",
    "Tributario": "Redattore preventivo tributario",
    "Stragiudiziale": "Redattore preventivo stragiudiziale",
    "Speciali": "Redattore preventivo personalizzato",
}

_SUMMARY_OVERRIDES = {
    "atto_citazione": "Preventivo per avviare un giudizio ordinario di cognizione con atto di citazione e gestione delle relative fasi.",
    "decreto_ingiuntivo": "Preventivo per il recupero monitorio del credito fondato su prova scritta, con stima delle fasi essenziali del procedimento.",
    "diffida": "Preventivo per attività stragiudiziale di diffida o messa in mora, con impostazione pronta per invio PEC o raccomandata.",
    "appello_civile": "Preventivo per impugnazione civile in secondo grado, con scelta guidata della regola tariffaria in base al giudice che ha emesso la sentenza impugnata.",
    "separazione_consensuale": "Preventivo per procedimento congiunto di separazione personale, con logica tariffaria di volontaria giurisdizione e domanda congiunta.",
    "divorzio_congiunto": "Preventivo per domanda congiunta di scioglimento o cessazione degli effetti civili del matrimonio, con compenso unico tabellare di volontaria giurisdizione.",
    "procedimenti_famiglia": "Preventivo per procedimenti camerali di famiglia, da usare quando il rito resta non contenzioso o comunque camerale.",
    "procedimenti_minori": "Preventivo per procedimenti relativi ai minori con struttura piu prudente sul rito contenzioso davanti al tribunale competente.",
    "modifica_condizioni_famiglia": "Preventivo per revisione o modifica delle condizioni gia fissate in materia familiare, con focus su ricorso e provvedimenti successivi.",
    "responsabilita_genitoriale": "Preventivo per controversie su affidamento, collocamento, mantenimento e responsabilita genitoriale, separato dal contenitore generico famiglia.",
    "reclamo_famiglia_minori": "Preventivo per reclamo sui provvedimenti temporanei e urgenti in materia di persone, minorenni e famiglie, con profilo da impugnazione davanti alla Corte d'Appello.",
    "appello_famiglia_minori": "Preventivo per appello in materia famiglia o minori contro la sentenza resa dal tribunale competente.",
    "amministrazione_sostegno": "Preventivo per ricorso e gestione del procedimento di amministrazione di sostegno davanti al giudice tutelare con regola di volontaria giurisdizione.",
    "nomina_amministratore_sostegno": "Preventivo per la sola fase di apertura e nomina dell'amministratore di sostegno, con documentazione sanitaria e patrimoniale essenziale.",
    "modifica_revoca_ads": "Preventivo per modifica dei poteri, sostituzione o revoca dell'amministratore di sostegno gia nominato.",
    "tutela_curatela": "Preventivo per procedimenti ordinari di tutela o curatela, separati dall'amministrazione di sostegno per non confondere presupposti e documentazione.",
    "reclamo_giudice_tutelare": "Preventivo per impugnare in via di reclamo un decreto del giudice tutelare davanti al tribunale competente.",
    "cassazione_lavoro": "Preventivo per ricorso di legittimita in materia di lavoro, separato dal secondo grado per mantenere regola tariffaria e grado coerenti.",
    "mediazione": "Preventivo per assistenza in procedura di mediazione civile e commerciale con valorizzazione delle fasi ADR.",
    "negoziazione_assistita": "Preventivo per assistenza nella convenzione di negoziazione assistita e nelle fasi di trattativa e definizione.",
    "appello_previdenza": "Preventivo per impugnazione previdenziale o assistenziale in secondo grado, con focus sulle fasi del giudizio davanti alla Corte d'Appello.",
    "cassazione_previdenza": "Preventivo per ricorso di legittimita in materia previdenziale e assistenziale, separato dal primo e dal secondo grado.",
    "opposizione_esecutiva": "Preventivo per opposizione all'esecuzione, distinto dall'opposizione agli atti esecutivi per non mescolare rimedi diversi nella stessa scheda.",
    "opposizione_atti_esecutivi": "Preventivo per opposizione agli atti esecutivi, dedicato ai vizi formali del titolo, del precetto o dei singoli atti dell'esecuzione.",
    "sfratto_morosita": "Preventivo per intimazione di sfratto per morosita e convalida, con focus sulle attivita urgenti introduttive.",
    "risarcimento_danni": "Preventivo per azione risarcitoria civile con stima di istruttoria, prova tecnica e fase decisionale.",
    "sinistro_stradale_stragiudiziale": "Preventivo per richiesta risarcitoria stragiudiziale verso compagnia o responsabile prima dell'eventuale giudizio.",
    "ricorso_tar": "Preventivo per tutela davanti al TAR con struttura pensata per ricorso, cautelare e fase di merito.",
    "ricorso_tributario": "Preventivo per contenzioso tributario con articolazione per ricorso, istanza cautelare e fasi successive.",
}

_WHEN_TO_USE_OVERRIDES = {
    "atto_citazione": "Usalo quando la tutela passa dal rito ordinario e vuoi impostare sin da subito attività introduttiva, istruttoria e decisionale.",
    "decreto_ingiuntivo": "Usalo quando il credito è documentato e il cliente vuole una prima azione monitoria con tempi e costi prevedibili.",
    "diffida": "Usalo nella fase di onboarding cliente quando prima della lite è opportuno tentare una richiesta formale ben tracciata.",
    "appello_civile": "Usalo quando devi impugnare una sentenza civile e vuoi scegliere subito se l'appello va al Tribunale o alla Corte d'Appello in base al giudice che ha pronunciato la decisione.",
    "separazione_consensuale": "Usalo quando i coniugi hanno gia raggiunto un accordo e vuoi preimpostare un ricorso congiunto con logica camerale.",
    "divorzio_congiunto": "Usalo quando la crisi familiare e gia definita in forma condivisa e vuoi stimare subito il compenso unico della domanda congiunta.",
    "procedimenti_famiglia": "Usalo per procedimenti camerali familiari o per richieste non pienamente contenziose che non vuoi mescolare ai giudizi di separazione o divorzio.",
    "procedimenti_minori": "Usalo quando il focus principale riguarda provvedimenti sui minori e preferisci una stima piu cauta sul rito davanti al tribunale competente.",
    "modifica_condizioni_famiglia": "Usalo quando devi chiedere la revisione di affidamento, mantenimento o altri provvedimenti gia emessi nella crisi familiare.",
    "responsabilita_genitoriale": "Usalo quando la pratica riguarda in via principale affidamento, mantenimento, collocamento o esercizio della responsabilita genitoriale.",
    "reclamo_famiglia_minori": "Usalo quando devi impugnare in via di reclamo i provvedimenti temporanei e urgenti resi nel rito famiglia e minori.",
    "appello_famiglia_minori": "Usalo quando devi proporre appello contro una sentenza del tribunale in materia di persone, minorenni e famiglie.",
    "amministrazione_sostegno": "Usalo quando l'intervento richiesto riguarda la nomina, la modifica o la gestione dell'amministratore di sostegno davanti al giudice tutelare.",
    "nomina_amministratore_sostegno": "Usalo quando la pratica riguarda l'apertura iniziale dell'amministrazione di sostegno e vuoi isolare costi e documenti della sola nomina.",
    "modifica_revoca_ads": "Usalo quando esiste gia un'amministrazione di sostegno e devi chiedere variazioni dei poteri, sostituzione o cessazione della misura.",
    "tutela_curatela": "Usalo quando il caso ricade su tutela o curatela ordinaria e non vuoi confonderlo con l'amministrazione di sostegno.",
    "reclamo_giudice_tutelare": "Usalo quando devi contestare un decreto del giudice tutelare e vuoi una scheda dedicata al reclamo davanti al tribunale.",
    "cassazione_lavoro": "Usalo quando il contenzioso di lavoro e gia arrivato alla fase di legittimita e non vuoi mescolare il ricorso per Cassazione con il giudizio di appello.",
    "mediazione": "Usalo quando la materia impone o rende utile un tentativo ADR prima del giudizio o in corso di causa.",
    "negoziazione_assistita": "Usalo quando la controversia richiede o consiglia una negoziazione assistita prima dell'azione giudiziale.",
    "appello_previdenza": "Usalo quando devi impugnare una decisione previdenziale o assistenziale nel giudizio di secondo grado davanti alla Corte d'Appello.",
    "cassazione_previdenza": "Usalo quando la pratica previdenziale o assistenziale e arrivata al giudizio di legittimita e vuoi un preventivo dedicato alla sola Cassazione.",
    "opposizione_esecutiva": "Usalo quando devi contestare il diritto di procedere ad esecuzione forzata o la pignorabilita dei beni, senza confonderlo con i vizi formali degli atti esecutivi.",
    "opposizione_atti_esecutivi": "Usalo quando devi contestare la regolarita formale del titolo, del precetto o dei singoli atti dell'esecuzione, con rimedio distinto dall'opposizione all'esecuzione.",
    "sfratto_morosita": "Usalo quando il locatore deve attivare rapidamente la tutela per morosita e vuoi stimare con chiarezza fase introduttiva e possibili sviluppi.",
    "risarcimento_danni": "Usalo quando il cliente chiede ristoro economico e la pratica richiede di stimare bene istruttoria, spese vive e possibili consulenze.",
    "sinistro_stradale_stragiudiziale": "Usalo quando vuoi costruire un preventivo per la fase di messa in mora, raccolta documenti e trattativa assicurativa prima della causa.",
}

_ACCESSORI_CALCOLO: Dict[str, List[Dict[str, Any]]] = {
    "sfratto_morosita": [
        {
            "id": "mediazione_locazione",
            "tipo_pratica_id": "mediazione",
            "label": "Aggiungi mediazione civile (locazione)",
            "description": "In materia di locazione la mediazione e condizione di procedibilita ai sensi dell'art. 5, comma 1, D.Lgs. 28/2010.",
            "default_checked": True,
            "row_label": "Compenso professionale per mediazione civile collegata alla controversia locatizia",
            "fasi_default_keys": ["attivazione", "rivitalizzazione", "conciliazione"],
            "normative_references": _RIF_MEDIAZIONE_LOCAZIONE,
        }
    ]
}


def _accessori_generici_per(tp: TipoPratica) -> List[Dict[str, Any]]:
    if tp.id in {"mediazione", "negoziazione_assistita"}:
        return []
    if tp.area not in {"Civile", "Stragiudiziale"}:
        return []
    return [
        {
            "id": "mediazione_generale",
            "tipo_pratica_id": "mediazione",
            "label": "Aggiungi mediazione civile / commerciale",
            "description": (
                "Attiva il calcolo della mediazione come integrazione opzionale quando la materia lo richiede "
                "o quando vuoi includerla nel preventivo gia in fase iniziale."
            ),
            "default_checked": False,
            "row_label": "Compenso professionale per mediazione civile collegata",
            "fasi_default_keys": ["attivazione", "rivitalizzazione", "conciliazione"],
            "normative_references": _RIF_MEDIAZIONE_GENERALE,
        }
    ]


def _accessori_calcolo_for(tp: TipoPratica) -> List[Dict[str, Any]]:
    rows = [
        {
            **{k: v for k, v in item.items() if k != "normative_references"},
            "normative_references": [dict(ref) for ref in item.get("normative_references", [])],
        }
        for item in _ACCESSORI_CALCOLO.get(tp.id, [])
    ]
    has_mediazione = any(item.get("tipo_pratica_id") == "mediazione" for item in rows)
    if not has_mediazione:
        rows.extend(_accessori_generici_per(tp))
    return rows


def _fase_key(fase: Fase) -> str:
    mapping = {
        Fase.STUDIO: "studio",
        Fase.INTRODUTTIVA: "introduttiva",
        Fase.ISTRUTTORIA: "istruttoria",
        Fase.DECISIONALE: "decisionale",
        Fase.ESECUTIVA: "esecutiva",
        Fase.ATTIVAZIONE: "attivazione",
        Fase.RIVITALIZZAZIONE: "rivitalizzazione",
        Fase.NEGOZIAZIONE_TRATTAZIONE: "negoziazione",
        Fase.CONCILIAZIONE: "conciliazione",
    }
    return mapping[fase]


def _descrivi_fase(fase: Fase) -> str:
    mapping = {
        Fase.STUDIO: "analisi iniziale della pratica e della documentazione",
        Fase.INTRODUTTIVA: "impostazione strategica e redazione dell'atto iniziale",
        Fase.ISTRUTTORIA: "gestione istruttoria, udienze e mezzi di prova",
        Fase.DECISIONALE: "conclusioni, note finali e decisione",
        Fase.ESECUTIVA: "attività esecutiva e recupero coattivo",
        Fase.ATTIVAZIONE: "avvio della procedura ADR o stragiudiziale",
        Fase.RIVITALIZZAZIONE: "interlocuzione con organismo e parti",
        Fase.NEGOZIAZIONE_TRATTAZIONE: "trattativa assistita e verbalizzazione delle posizioni",
        Fase.CONCILIAZIONE: "definizione dell'accordo e chiusura della procedura",
    }
    return mapping[fase]


def _summary_for(tp: TipoPratica) -> str:
    if tp.id in _SUMMARY_OVERRIDES:
        return _SUMMARY_OVERRIDES[tp.id]
    area = tp.area.lower()
    if tp.area == "Stragiudiziale":
        return f"Preventivo per {tp.label.lower()}, con impostazione immediata di attivita, tempi e spese vive tipiche."
    if tp.area == "Penale":
        return f"Preventivo per {tp.label.lower()} in ambito penale, con compenso strutturato sulle fasi difensive effettivamente prevedibili."
    return f"Preventivo per {tp.label.lower()} in area {area}, con compenso guidato dai parametri forensi e dalle fasi standard della pratica."


def _when_to_use_for(tp: TipoPratica) -> str:
    if tp.id in _WHEN_TO_USE_OVERRIDES:
        return _WHEN_TO_USE_OVERRIDES[tp.id]
    if tp.richiede_valore:
        return "Usalo quando vuoi partire da una tipologia gia riconoscibile, stimando il compenso in base a valore, fase e complessita dell'incarico."
    return "Usalo quando il compenso dipende soprattutto da attivita, presidio professionale e complessita, piu che da un valore di lite."


def _oggetto_template_for(tp: TipoPratica) -> str:
    return f"Preventivo professionale per {tp.label.lower()}"


def _note_template_for(tp: TipoPratica) -> str:
    lines = [
        f"Il presente preventivo riguarda l'attivita di {tp.label.lower()} e viene predisposto sulla base dei parametri forensi applicabili.",
        "L'importo potra essere aggiornato in caso di estensione dell'incarico, attivita ulteriori non preventivabili o mutamenti del valore/complessita della pratica.",
        "Restano esclusi contributo unificato, notifiche, bolli, trasferte, ausiliari e ulteriori spese vive non comprese nelle voci esposte, salvo diverso accordo scritto.",
    ]
    if tp.area == "Stragiudiziale":
        lines.append("Le attivita di trattativa o ADR ulteriori rispetto a quelle stimate formeranno oggetto di integrazione del preventivo.")
    if tp.area == "Penale":
        lines.append("Il compenso potra richiedere adeguamento in caso di udienze ulteriori, impugnazioni, incidenti o attivita investigative aggiuntive.")
    lines.append("Informativa resa ai sensi dell'art. 13 L. 247/2012 e dei parametri forensi vigenti.")
    return "\n".join(lines)


def _checklist_for(tp: TipoPratica) -> List[str]:
    checklist = [
        "confermare cliente, controparte e obiettivo dell'incarico",
        "verificare documenti disponibili e urgenze operative",
    ]
    if tp.richiede_valore:
        checklist.append("stimare correttamente il valore economico della pratica")
    for fase in tp.fasi_default[:4]:
        checklist.append(_descrivi_fase(fase))
    if tp.area == "Stragiudiziale":
        checklist.append("definire se inserire fase di mediazione o negoziazione assistita")
    if tp.id == "sfratto_morosita":
        checklist.append("verificare subito la mediazione civile obbligatoria in materia di locazione")
    return checklist


def _normative_references_for(tp: TipoPratica) -> List[Dict[str, str]]:
    refs = [dict(item) for item in _RIFERIMENTI_BASE]
    if tp.materia in {Materia.LAVORO, Materia.PREVIDENZA}:
        area_ref = _RIFERIMENTI_AREA.get("Lavoro e previdenza")
    else:
        area_ref = _RIFERIMENTI_AREA.get(tp.area)
    if area_ref:
        refs.append(
            {
                "title": area_ref["title"],
                "article": tp.base_normativa,
                "description": area_ref["description"],
                "url": area_ref["url"],
            }
        )
    if tp.id == "mediazione":
        refs.append(
            {
                "title": "D.Lgs. 4 marzo 2010, n. 28",
                "article": "mediazione civile e commerciale",
                "description": "Disciplina del procedimento di mediazione e dei casi di procedibilita.",
                "url": _URL_MEDIAZIONE,
            }
        )
        refs.append(
            {
                "title": "D.M. 24 ottobre 2023, n. 150",
                "article": "spese e indennita di mediazione",
                "description": "Criteri di iscrizione, indennita e spese degli organismi di mediazione dopo la riforma Cartabia.",
                "url": _URL_DM150_MEDIAZIONE,
            }
        )
        refs.append(
            {
                "title": "D.M. 10 marzo 2014, n. 55",
                "article": "artt. 2, 19 e 20, comma 1-bis",
                "description": "Spese generali al 15%, variazione per fase entro il +/-50% e maggiorazione del 30% sulle fasi iniziali ADR in caso di accordo.",
                "url": _URL_DM55,
            }
        )
        refs.append(
            {
                "title": "Ministero della Giustizia",
                "article": "registro organismi di mediazione",
                "description": (
                    "La scheda ministeriale del registro, aggiornata al 4 marzo 2026, rinvia al portale "
                    "ufficiale degli organismi di mediazione e segnala l'uso di Microsoft Edge in "
                    "modalita compatibilita con Internet Explorer per la consultazione."
                ),
                "url": _URL_REGISTRO_MEDIAZIONE_INFO,
            }
        )
    if tp.id == "negoziazione_assistita":
        refs.append(
            {
                "title": "D.L. 12 settembre 2014, n. 132",
                "article": "negoziazione assistita",
                "description": "Disciplina della convenzione di negoziazione assistita e dei casi di obbligatorieta.",
                "url": _URL_NEGOZIAZIONE,
            }
        )
        refs.append(
            {
                "title": "D.M. 10 marzo 2014, n. 55",
                "article": "artt. 2, 19 e 20, comma 1-bis",
                "description": "Spese generali al 15%, variazione per fase entro il +/-50% e maggiorazione del 30% sulle fasi iniziali ADR in caso di accordo.",
                "url": _URL_DM55,
            }
        )
    if tp.id == "sinistro_stradale_stragiudiziale":
        refs.append(
            {
                "title": "D.Lgs. 7 settembre 2005, n. 209",
                "article": "artt. 145, 148 e 149",
                "description": "Procedura risarcitoria RCA, richiesta danni e indennizzo diretto in fase stragiudiziale.",
                "url": _URL_CODICE_ASSICURAZIONI,
            }
        )
    if tp.id == "sfratto_morosita":
        refs.append(
            {
                "title": "Codice di procedura civile",
                "article": "artt. 657 e seguenti",
                "description": "Intimazione di sfratto per morosita e citazione per la convalida.",
                "url": _URL_CPC,
            }
        )
        refs.extend([dict(item) for item in _RIF_MEDIAZIONE_LOCAZIONE])
    if tp.id == "risarcimento_danni":
        refs.append(
            {
                "title": "Codice civile",
                "article": "artt. 2043 e 2054",
                "description": "Responsabilita aquiliana e responsabilita da circolazione dei veicoli.",
                "url": _URL_CC,
            }
        )
    if tp.id == "istruzione_preventiva":
        refs.append(
            {
                "title": "Codice di procedura civile",
                "article": "artt. 692 e seguenti",
                "description": "Procedimenti di istruzione preventiva, accertamento tecnico preventivo e anticipazione della prova.",
                "url": _URL_CPC,
            }
        )
    if tp.id == "cautelare_civile":
        refs.append(
            {
                "title": "Codice di procedura civile",
                "article": "artt. 669-bis e seguenti",
                "description": "Disciplina uniforme dei procedimenti cautelari civili e delle misure urgenti.",
                "url": _URL_CPC,
            }
        )
    if tp.id in {
        "separazione_consensuale",
        "separazione_giudiziale",
        "divorzio_congiunto",
        "divorzio_giudiziale",
        "procedimenti_famiglia",
        "procedimenti_minori",
        "modifica_condizioni_famiglia",
        "responsabilita_genitoriale",
        "reclamo_famiglia_minori",
        "appello_famiglia_minori",
        "amministrazione_sostegno",
        "nomina_amministratore_sostegno",
        "modifica_revoca_ads",
        "tutela_curatela",
    }:
        refs.append(
            {
                "title": "D.Lgs. 10 ottobre 2022, n. 149",
                "article": "Titolo IV-bis c.p.c. — persone, minorenni e famiglie",
                "description": "Riforma Cartabia del rito famiglia e minori, con introduzione degli articoli 473-bis e seguenti del codice di procedura civile.",
                "url": _URL_DLGS149,
            }
        )
    if tp.id in {"separazione_consensuale", "divorzio_congiunto"}:
        refs.append(
            {
                "title": "Codice di procedura civile",
                "article": "art. 473-bis.51",
                "description": "Disciplina del procedimento su domanda congiunta per i procedimenti in materia di persone, minorenni e famiglie.",
                "url": _URL_CPC,
            }
        )
    if tp.id in {"separazione_giudiziale", "divorzio_giudiziale"}:
        refs.append(
            {
                "title": "Codice di procedura civile",
                "article": "art. 473-bis.47",
                "description": "Base processuale del ricorso giudiziale nelle controversie familiari di crisi della coppia.",
                "url": _URL_CPC,
            }
        )
    if tp.id == "procedimenti_minori":
        refs.append(
            {
                "title": "Codice di procedura civile",
                "article": "art. 473-bis",
                "description": "Il titolo IV-bis si applica ai procedimenti relativi allo stato delle persone, ai minorenni e alle famiglie attribuiti al giudice competente.",
                "url": _URL_CPC,
            }
        )
    if tp.id == "modifica_condizioni_famiglia":
        refs.append(
            {
                "title": "Codice di procedura civile",
                "article": "art. 473-bis.29",
                "description": "Domande di modifica o revisione dei provvedimenti in materia di affidamento, mantenimento e responsabilita genitoriale.",
                "url": _URL_CPC,
            }
        )
    if tp.id == "responsabilita_genitoriale":
        refs.append(
            {
                "title": "Codice civile",
                "article": "artt. 337-bis e seguenti",
                "description": "Disciplina sostanziale dell'affidamento e dell'esercizio della responsabilita genitoriale nei rapporti con i figli.",
                "url": _URL_CC,
            }
        )
        refs.append(
            {
                "title": "Codice di procedura civile",
                "article": "artt. 473-bis e seguenti",
                "description": "Rito unitario delle controversie in materia di persone, minorenni e famiglie davanti al tribunale competente.",
                "url": _URL_CPC,
            }
        )
    if tp.id == "reclamo_famiglia_minori":
        refs.append(
            {
                "title": "Codice di procedura civile",
                "article": "art. 473-bis.24",
                "description": "Reclamo avverso i provvedimenti temporanei e urgenti nel rito persone, minorenni e famiglie.",
                "url": _URL_CPC,
            }
        )
    if tp.id == "appello_famiglia_minori":
        refs.append(
            {
                "title": "Codice di procedura civile",
                "article": "art. 473-bis.30",
                "description": "Appello avverso la sentenza pronunciata dal tribunale nei procedimenti di persone, minorenni e famiglie.",
                "url": _URL_CPC,
            }
        )
    if tp.id == "amministrazione_sostegno":
        refs.append(
            {
                "title": "Codice civile",
                "article": "art. 404",
                "description": "Presupposti e finalita dell'amministrazione di sostegno a tutela della persona fragile.",
                "url": _URL_CC,
            }
        )
        refs.append(
            {
                "title": "Codice di procedura civile",
                "article": "art. 720-bis",
                "description": "Procedimento davanti al giudice tutelare per l'amministrazione di sostegno e i relativi provvedimenti.",
                "url": _URL_CPC,
            }
        )
        refs.append(
            {
                "title": "Codice di procedura civile",
                "article": "artt. 473-bis.52 e seguenti",
                "description": "Sezione dedicata ai procedimenti di interdizione, inabilitazione e nomina di amministratore di sostegno nel rito vigente.",
                "url": _URL_CPC,
            }
        )
    if tp.id == "nomina_amministratore_sostegno":
        refs.append(
            {
                "title": "Codice civile",
                "article": "artt. 404 e 405",
                "description": "Presupposti della misura e decreto di nomina dell'amministratore di sostegno.",
                "url": _URL_CC,
            }
        )
        refs.append(
            {
                "title": "Codice di procedura civile",
                "article": "artt. 473-bis.52 e seguenti",
                "description": "Procedimento vigente per interdizione, inabilitazione e nomina dell'amministratore di sostegno.",
                "url": _URL_CPC,
            }
        )
    if tp.id == "giudice_pace_penale":
        refs.append(
            {
                "title": "D.Lgs. 28 agosto 2000, n. 274",
                "article": "procedimento penale davanti al Giudice di Pace",
                "description": "Disciplina speciale dei procedimenti penali attribuiti al Giudice di Pace.",
                "url": "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legislativo%3A2000-08-28%3B274",
            }
        )
    if tp.id == "indagini_difensive":
        refs.append(
            {
                "title": "Codice di procedura penale",
                "article": "artt. 391-bis e seguenti",
                "description": "Attivita investigative difensive del difensore nella fase preliminare e nel corso del procedimento.",
                "url": _URL_CPP,
            }
        )
    if tp.id == "convalida_arresto":
        refs.append(
            {
                "title": "Codice di procedura penale",
                "article": "artt. 390 e 391",
                "description": "Richiesta e udienza di convalida dell'arresto o del fermo davanti al giudice competente.",
                "url": _URL_CPP,
            }
        )
    if tp.id == "misure_cautelari_penali":
        refs.append(
            {
                "title": "Codice di procedura penale",
                "article": "artt. 272 e seguenti, artt. 321 e seguenti",
                "description": "Misure cautelari personali e reali nel procedimento penale.",
                "url": _URL_CPP,
            }
        )
    if tp.id == "sorveglianza_penale":
        refs.append(
            {
                "title": "L. 26 luglio 1975, n. 354",
                "article": "ordinamento penitenziario",
                "description": "Base normativa dei procedimenti davanti al Tribunale e al Magistrato di Sorveglianza.",
                "url": _URL_ORDINAMENTO_PENITENZIARIO,
            }
        )
    if tp.id == "giudizio_corte_conti":
        refs.append(
            {
                "title": "D.Lgs. 26 agosto 2016, n. 174",
                "article": "Codice di giustizia contabile",
                "description": "Rito e competenza dei giudizi davanti alla Corte dei Conti.",
                "url": _URL_CODICE_GIUSTIZIA_CONTABILE,
            }
        )
    if tp.id == "iscrizione_ipotecaria_tavolare":
        refs.append(
            {
                "title": "Codice civile",
                "article": "artt. 2808 e seguenti",
                "description": "Disciplina sostanziale dell'ipoteca e delle formalita di iscrizione.",
                "url": _URL_CC,
            }
        )
    if tp.id in {"apertura_liquidazione_giudiziale", "accertamento_passivo"}:
        refs.append(
            {
                "title": "D.Lgs. 12 gennaio 2019, n. 14",
                "article": "Codice della crisi d'impresa e dell'insolvenza",
                "description": "Disciplina vigente della liquidazione giudiziale e dell'accertamento del passivo.",
                "url": _URL_CODICE_CRISE_IMPRESA,
            }
        )
    if tp.id == "modifica_revoca_ads":
        refs.append(
            {
                "title": "Codice civile",
                "article": "art. 413",
                "description": "Revoca e modifica dell'amministrazione di sostegno e dei relativi provvedimenti.",
                "url": _URL_CC,
            }
        )
        refs.append(
            {
                "title": "Codice di procedura civile",
                "article": "artt. 473-bis.52 e seguenti",
                "description": "Quadro processuale vigente per le istanze che incidono sulla misura di amministrazione di sostegno.",
                "url": _URL_CPC,
            }
        )
    if tp.id == "tutela_curatela":
        refs.append(
            {
                "title": "Codice civile",
                "article": "artt. 343 e seguenti",
                "description": "Disciplina di apertura e gestione della tutela e della curatela ordinaria.",
                "url": _URL_CC,
            }
        )
        refs.append(
            {
                "title": "Codice di procedura civile",
                "article": "artt. 473-bis.64 e seguenti",
                "description": "Disposizioni processuali relative a minori, interdetti e inabilitati nel rito vigente.",
                "url": _URL_CPC,
            }
        )
    if tp.id == "reclamo_giudice_tutelare":
        refs.append(
            {
                "title": "Codice di procedura civile",
                "article": "art. 739",
                "description": "Reclamo contro i decreti pronunciati in camera di consiglio, rilevante per i provvedimenti del giudice tutelare.",
                "url": _URL_CPC,
            }
        )
    return refs


def _arricchisci_catalogo() -> None:
    for tp in CATALOGO:
        tp.esborsi_tipici = [dict(item) for item in _ESBORSI_TIPICI.get(tp.id, [])]
        if tp.materia in {Materia.LAVORO, Materia.PREVIDENZA}:
            tp.motore_label = tp.motore_label or _MOTORE_PER_AREA.get("Lavoro e previdenza", "Motore preventivo forense")
            tp.redattore_label = tp.redattore_label or _REDATTORE_PER_AREA.get("Lavoro e previdenza", "Redattore preventivo professionale")
        else:
            tp.motore_label = tp.motore_label or _MOTORE_PER_AREA.get(tp.area, "Motore preventivo forense")
            tp.redattore_label = tp.redattore_label or _REDATTORE_PER_AREA.get(tp.area, "Redattore preventivo professionale")
        tp.summary = tp.summary or _summary_for(tp)
        tp.when_to_use = tp.when_to_use or _when_to_use_for(tp)
        tp.oggetto_template = tp.oggetto_template or _oggetto_template_for(tp)
        tp.note_template = tp.note_template or _note_template_for(tp)
        tp.checklist_iniziale = tp.checklist_iniziale or _checklist_for(tp)
        tp.normative_references = tp.normative_references or _normative_references_for(tp)
        tp.accessori_calcolo = _accessori_calcolo_for(tp)


_arricchisci_catalogo()


def get_tipo_pratica(id_pratica: str) -> Optional[TipoPratica]:
    return _IDX.get(id_pratica)


def get_esborsi_tipici(id_pratica: str) -> List[Dict]:
    """Restituisce la lista di esborsi tipici per la tipologia di pratica."""
    return _ESBORSI_TIPICI.get(id_pratica, [])


def catalogo_per_area() -> Dict[str, List[TipoPratica]]:
    """Restituisce il catalogo raggruppato per area."""
    result: Dict[str, List[TipoPratica]] = {a: [] for a in AREE}
    for tp in CATALOGO:
        result.setdefault(tp.area, []).append(tp)
    for area in result:
        result[area] = sorted(result[area], key=lambda item: item.label)
    return result


def catalogo_wizard() -> Dict[str, List[dict]]:
    """Catalogo serializzabile e pronto per il wizard frontend."""
    return {
        area: [tp.to_dict() for tp in items]
        for area, items in catalogo_per_area().items()
        if items
    }


def redattore_preventivo_iniziale(id_pratica: str) -> dict:
    """Restituisce la scheda professionale della tipologia per il wizard preventivi."""
    tp = get_tipo_pratica(id_pratica)
    if tp is None:
        raise ValueError(f"Tipologia pratica non trovata: {id_pratica!r}")
    return tp.to_dict()


def catalogo_riferimenti_normativi() -> List[Dict[str, Any]]:
    """Catalogo deduplicato dei riferimenti normativi ufficiali usati dal motore preventivi.

    Ogni riferimento conserva la provenienza funzionale:
    - aree in cui compare
    - tipologie pratica collegate
    - motori/redattori che lo espongono nel wizard
    """
    catalogo: Dict[tuple[str, str, str], Dict[str, Any]] = {}
    for tp in CATALOGO:
        for ref in tp.normative_references:
            key = (
                (ref.get("title") or "").strip(),
                (ref.get("article") or "").strip(),
                (ref.get("url") or "").strip(),
            )
            if not any(key):
                continue
            entry = catalogo.setdefault(
                key,
                {
                    "title": key[0],
                    "article": key[1],
                    "description": (ref.get("description") or "").strip(),
                    "url": key[2],
                    "areas": [],
                    "tipologie_ids": [],
                    "tipologie_labels": [],
                    "motori": [],
                    "redattori": [],
                },
            )
            if tp.area not in entry["areas"]:
                entry["areas"].append(tp.area)
            if tp.id not in entry["tipologie_ids"]:
                entry["tipologie_ids"].append(tp.id)
            if tp.label not in entry["tipologie_labels"]:
                entry["tipologie_labels"].append(tp.label)
            if tp.motore_label and tp.motore_label not in entry["motori"]:
                entry["motori"].append(tp.motore_label)
            if tp.redattore_label and tp.redattore_label not in entry["redattori"]:
                entry["redattori"].append(tp.redattore_label)

    rows = list(catalogo.values())
    rows.sort(key=lambda item: (item["title"], item["article"], item["url"]))
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# RisultatoMotore — risultato completo del calcolo
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RisultatoMotore:
    """Calcolo completo: DM 55/2014 → spese generali → CPA → IVA → esborsi → totale."""

    tipo_pratica: TipoPratica
    calcolo_dm55: RisultatoCalcolo

    # Valori calcolati dal motore
    onorario_base: float        # compat: coincide con il livello selezionato
    onorario_selezionato: float
    cpa: float                  # Cassa Forense 4% (su onorario_base)
    base_iva: float             # onorario_base + cpa
    iva: float                  # 22% (se applica_iva)
    anticipazioni: float        # esborsi art. 15 (esenti da CPA/IVA)
    totale: float               # totale finale

    applica_cpa: bool = True
    applica_iva: bool = True
    livello_compenso: str = LivelloCompenso.BASE.value

    def to_dict(self) -> dict:
        return {
            "tipo_pratica": self.tipo_pratica.to_dict(),
            "calcolo_dm55": self.calcolo_dm55.to_dict(),
            "onorario_base": self.onorario_base,
            "onorario_selezionato": self.onorario_selezionato,
            "cpa": self.cpa,
            "base_iva": self.base_iva,
            "iva": self.iva,
            "anticipazioni": self.anticipazioni,
            "totale": self.totale,
            "applica_cpa": self.applica_cpa,
            "applica_iva": self.applica_iva,
            "livello_compenso": self.livello_compenso,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Funzione principale: motore_calcola
# ──────────────────────────────────────────────────────────────────────────────

def motore_calcola(
    id_pratica: str,
    valore_controversia: float = 0.0,
    grado: Optional[Grado] = None,
    regola_tariffaria: str = "",
    fasi: Optional[List[Fase]] = None,
    livello_compenso: LivelloCompenso | str | None = None,
    complessita: str = "",
    bonus_telematico: bool = False,
    includi_spese_generali: bool = True,
    perc_spese_generali: float = 0.15,
    variazioni_fasi: Optional[Dict[str, float]] = None,
    maggiorazioni_fasi: Optional[Dict[str, float]] = None,
    applica_cpa: bool = True,
    applica_iva: bool = True,
    anticipazioni: float = 0.0,
) -> RisultatoMotore:
    """Calcola il compenso completo per la tipologia di pratica indicata.

    Args:
        id_pratica: identificatore nel CATALOGO
        valore_controversia: valore in €
        grado: override grado (default: grado_default del tipo pratica)
        fasi: override fasi (default: fasi_default del tipo pratica)
        livello_compenso: minimo / base / massimo da usare come livello operativo
        complessita: bassa / media / alta per pratiche a valore indeterminabile
        bonus_telematico: +30% per deposito con ricerca testuale
        includi_spese_generali: applica spese generali art. 2 DM 55/2014
        perc_spese_generali: percentuale (default 15%)
        variazioni_fasi: dict fase_label → moltiplicatore [0.50–1.50]
        applica_cpa: applica Cassa Forense 4%
        applica_iva: applica IVA 22%
        anticipazioni: esborsi art. 15 (esenti da CPA/IVA)
    """
    tp = _IDX.get(id_pratica)
    if tp is None:
        raise ValueError(f"Tipologia pratica non trovata: {id_pratica!r}")

    _grado = grado if grado is not None else tp.grado_default
    _fasi  = fasi  if fasi  is not None else tp.fasi_default
    regola_attiva = rule_lookup(regola_tariffaria) if regola_tariffaria else None
    if not regola_attiva:
        regola_attiva = default_rule_for_practice(id_pratica)
    profile_code = str((regola_attiva or {}).get("profile_code", "") or "")

    calcolo = calcola_compenso(
        materia=tp.materia,
        grado=_grado,
        valore=valore_controversia,
        fasi=_fasi,
        profile_code=profile_code,
        bonus_telematico=bonus_telematico,
        includi_spese_generali=includi_spese_generali,
        perc_spese_generali=perc_spese_generali,
        variazioni_fasi=variazioni_fasi or None,
        maggiorazioni_fasi=maggiorazioni_fasi or None,
        complessita=complessita,
    )

    if livello_compenso in (None, ""):
        livello = livello_compenso_da_complessita(complessita)
    elif isinstance(livello_compenso, LivelloCompenso):
        livello = livello_compenso
    else:
        livello = LivelloCompenso(str(livello_compenso or LivelloCompenso.BASE.value))
    onorario_base = calcolo.totale_compenso_livello(livello)
    cpa = round(onorario_base * 0.04, 2) if applica_cpa else 0.0
    base_iva = round(onorario_base + cpa, 2)
    iva = round(base_iva * 0.22, 2) if applica_iva else 0.0
    totale = round(base_iva + iva + anticipazioni, 2)

    return RisultatoMotore(
        tipo_pratica=tp,
        calcolo_dm55=calcolo,
        onorario_base=onorario_base,
        onorario_selezionato=onorario_base,
        cpa=cpa,
        base_iva=base_iva,
        iva=iva,
        anticipazioni=anticipazioni,
        totale=totale,
        applica_cpa=applica_cpa,
        applica_iva=applica_iva,
        livello_compenso=livello.value,
    )
