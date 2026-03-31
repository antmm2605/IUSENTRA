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
from typing import Dict, List, Optional

from pct.tariffario import (
    Fase,
    Grado,
    Materia,
    RisultatoCalcolo,
    calcola_compenso,
)


# ──────────────────────────────────────────────────────────────────────────────
# Macro-aree
# ──────────────────────────────────────────────────────────────────────────────

AREE = [
    "Civile",
    "Lavoro e previdenza",
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

    def to_dict(self) -> dict:
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
        }


# ──────────────────────────────────────────────────────────────────────────────
# Catalogo pratiche
# ──────────────────────────────────────────────────────────────────────────────

_FASI_BASE      = [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA, Fase.DECISIONALE]
_FASI_STUDIO    = [Fase.STUDIO]
_FASI_ESEC      = [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ESECUTIVA]
_FASI_PENALE    = [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA, Fase.DECISIONALE]

CATALOGO: List[TipoPratica] = [

    # ── CIVILE ──────────────────────────────────────────────────────────────

    TipoPratica(
        id="consulenza_civile",
        label="Consulenza / Parere civile",
        area="Civile",
        materia=Materia.STRAGIUD,
        grado_default=Grado.TRIBUNALE,
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
        grado_default=Grado.TRIBUNALE,
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
        base_normativa="Tab. A2 DM 55/2014 × coeff. 1.30 — art. 339 c.p.c.",
    ),
    TipoPratica(
        id="cassazione_civile",
        label="Cassazione civile",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.CASSAZIONE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A2 DM 55/2014 × coeff. 1.60 — art. 360 c.p.c.",
    ),
    TipoPratica(
        id="precetto",
        label="Precetto",
        area="Civile",
        materia=Materia.ESEC_MOB,
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA],
        base_normativa="Tab. A2 DM 55/2014 — fase esecutiva — art. 480 c.p.c.",
    ),
    TipoPratica(
        id="pignoramento",
        label="Pignoramento",
        area="Civile",
        materia=Materia.ESEC_MOB,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_ESEC,
        base_normativa="Tab. A2 DM 55/2014 — fase esecutiva — art. 491 ss. c.p.c.",
    ),
    TipoPratica(
        id="esecuzione_mobiliare",
        label="Esecuzione mobiliare",
        area="Civile",
        materia=Materia.ESEC_MOB,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_ESEC,
        base_normativa="Tab. A2 DM 55/2014 — esecuzione su beni mobili",
    ),
    TipoPratica(
        id="esecuzione_immobiliare",
        label="Esecuzione immobiliare",
        area="Civile",
        materia=Materia.ESEC_IMMO,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_ESEC,
        base_normativa="Tab. A2 DM 55/2014 — esecuzione su beni immobili — art. 555 ss. c.p.c.",
    ),
    TipoPratica(
        id="esecuzione_terzi",
        label="Esecuzione presso terzi (pignoramento c/terzi)",
        area="Civile",
        materia=Materia.ESEC_MOB,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_ESEC,
        base_normativa="Tab. A2 DM 55/2014 — art. 543 c.p.c.",
    ),
    TipoPratica(
        id="opposizione_esecutiva",
        label="Opposizione esecutiva",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 — artt. 615-619 c.p.c.",
    ),
    TipoPratica(
        id="separazione_consensuale",
        label="Separazione consensuale",
        area="Civile",
        materia=Materia.VOLONTARIA,
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A2 DM 55/2014 — art. 158 c.c. / art. 711 c.p.c.",
    ),
    TipoPratica(
        id="separazione_giudiziale",
        label="Separazione giudiziale",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 — art. 151 c.c. / artt. 706 ss. c.p.c.",
    ),
    TipoPratica(
        id="divorzio_congiunto",
        label="Divorzio congiunto",
        area="Civile",
        materia=Materia.VOLONTARIA,
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A2 DM 55/2014 — L. 898/1970 art. 4 co. 16",
    ),
    TipoPratica(
        id="divorzio_giudiziale",
        label="Divorzio giudiziale",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 — L. 898/1970 art. 4",
    ),
    TipoPratica(
        id="procedimenti_famiglia",
        label="Procedimenti di famiglia / minori",
        area="Civile",
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 — D.Lgs. 149/2022 (riforma proc. civ.)",
    ),

    # ── LAVORO E PREVIDENZA ─────────────────────────────────────────────────

    TipoPratica(
        id="controversia_lavoro",
        label="Controversia di lavoro",
        area="Lavoro e previdenza",
        materia=Materia.LAVORO,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A3 DM 55/2014 agg. DM 147/2022 — art. 409 c.p.c.",
    ),
    TipoPratica(
        id="licenziamento",
        label="Licenziamento (impugnazione)",
        area="Lavoro e previdenza",
        materia=Materia.LAVORO,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A3 DM 55/2014 — L. 300/1970 art. 18 / D.Lgs. 23/2015",
    ),
    TipoPratica(
        id="differenze_retributive",
        label="Differenze retributive",
        area="Lavoro e previdenza",
        materia=Materia.LAVORO,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A3 DM 55/2014 — art. 36 Cost.",
    ),
    TipoPratica(
        id="appello_lavoro",
        label="Appello in materia di lavoro",
        area="Lavoro e previdenza",
        materia=Materia.LAVORO,
        grado_default=Grado.CORTE_APPELLO,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A3 DM 55/2014 × coeff. 1.30 — art. 434 c.p.c.",
    ),
    TipoPratica(
        id="previdenza",
        label="Previdenza (INPS / INAIL / fondi)",
        area="Lavoro e previdenza",
        materia=Materia.PREVIDENZA,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A4 DM 55/2014 agg. DM 147/2022 — artt. 442 ss. c.p.c.",
    ),
    TipoPratica(
        id="assistenza_previdenziale",
        label="Assistenza previdenziale / ricorso amministrativo",
        area="Lavoro e previdenza",
        materia=Materia.PREVIDENZA,
        grado_default=Grado.TRIBUNALE,
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
        grado_default=Grado.TRIBUNALE,
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
        grado_default=Grado.TRIBUNALE,
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
        grado_default=Grado.TRIBUNALE,
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
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. penale DM 55/2014 — art. 416 c.p.p.",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="dibattimento_penale",
        label="Dibattimento penale",
        area="Penale",
        materia=Materia.PENALE,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_PENALE,
        base_normativa="Tab. penale DM 55/2014 — artt. 470 ss. c.p.p.",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="impugnazioni_penali",
        label="Impugnazioni penali (appello)",
        area="Penale",
        materia=Materia.PENALE,
        grado_default=Grado.CORTE_APPELLO,
        fasi_default=_FASI_PENALE,
        base_normativa="Tab. penale DM 55/2014 × coeff. 1.30 — artt. 593 ss. c.p.p.",
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
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_PENALE,
        base_normativa="Tab. penale DM 55/2014 — artt. 74-101 c.p.p.",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),

    # ── AMMINISTRATIVO ──────────────────────────────────────────────────────

    TipoPratica(
        id="ricorso_tar",
        label="Ricorso TAR",
        area="Amministrativo",
        materia=Materia.AMMINISTRATIVO,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A21 DM 55/2014 agg. DM 147/2022 — D.Lgs. 104/2010 (Cod. Proc. Amm.)",
    ),
    TipoPratica(
        id="cautelare_sospensiva",
        label="Cautelare / Sospensiva (TAR)",
        area="Amministrativo",
        materia=Materia.AMMINISTRATIVO,
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A21 DM 55/2014 — art. 55 D.Lgs. 104/2010",
    ),
    TipoPratica(
        id="motivi_aggiunti",
        label="Motivi aggiunti",
        area="Amministrativo",
        materia=Materia.AMMINISTRATIVO,
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA],
        base_normativa="Tab. A21 DM 55/2014 — art. 43 D.Lgs. 104/2010",
    ),
    TipoPratica(
        id="appello_cds",
        label="Appello Consiglio di Stato",
        area="Amministrativo",
        materia=Materia.AMMINISTRATIVO,
        grado_default=Grado.CORTE_APPELLO,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A22 DM 55/2014 × coeff. 1.30 — artt. 91 ss. D.Lgs. 104/2010",
    ),
    TipoPratica(
        id="ottemperanza",
        label="Giudizio di ottemperanza",
        area="Amministrativo",
        materia=Materia.AMMINISTRATIVO,
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE],
        base_normativa="Tab. A21 DM 55/2014 — artt. 112 ss. D.Lgs. 104/2010",
    ),

    # ── TRIBUTARIO ──────────────────────────────────────────────────────────

    TipoPratica(
        id="ricorso_tributario",
        label="Ricorso tributario (CGT primo grado)",
        area="Tributario",
        materia=Materia.TRIBUTARIO,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A23 DM 55/2014 agg. DM 147/2022 — D.Lgs. 546/1992",
    ),
    TipoPratica(
        id="appello_tributario",
        label="Appello tributario (CGT secondo grado)",
        area="Tributario",
        materia=Materia.TRIBUTARIO,
        grado_default=Grado.CORTE_APPELLO,
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
        base_normativa="Tab. A23/A24 DM 55/2014 × coeff. 1.60 — art. 62 D.Lgs. 546/1992",
    ),
    TipoPratica(
        id="autotutela",
        label="Autotutela tributaria",
        area="Tributario",
        materia=Materia.STRAGIUD,
        grado_default=Grado.TRIBUNALE,
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
        grado_default=Grado.TRIBUNALE,
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
        grado_default=Grado.TRIBUNALE,
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
        grado_default=Grado.TRIBUNALE,
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
        grado_default=Grado.TRIBUNALE,
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
        grado_default=Grado.TRIBUNALE,
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
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.STUDIO],
        base_normativa="Tab. A25 DM 55/2014 — Prestazioni stragiudiziali",
        richiede_valore=False,
        tipo_compenso_default="Compenso fisso",
    ),
    TipoPratica(
        id="mediazione",
        label="Mediazione (D.Lgs. 28/2010)",
        area="Stragiudiziale",
        materia=Materia.MEDIAZIONE,
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.ATTIVAZIONE, Fase.RIVITALIZZAZIONE, Fase.CONCILIAZIONE],
        base_normativa="Tab. A25 DM 55/2014 agg. DM 147/2022 — D.Lgs. 28/2010",
        richiede_valore=True,
        tipo_compenso_default="Per fasi processuali (D.M. 55/2014)",
    ),
    TipoPratica(
        id="negoziazione_assistita",
        label="Negoziazione assistita (D.L. 132/2014)",
        area="Stragiudiziale",
        materia=Materia.NEGOZIAZIONE_ASSISTITA,
        grado_default=Grado.TRIBUNALE,
        fasi_default=[Fase.ATTIVAZIONE, Fase.NEGOZIAZIONE_TRATTAZIONE, Fase.CONCILIAZIONE],
        base_normativa="Tab. A25 DM 55/2014 agg. DM 147/2022 — D.L. 132/2014 conv. L. 162/2014",
        richiede_valore=True,
        tipo_compenso_default="Per fasi processuali (D.M. 55/2014)",
    ),
    TipoPratica(
        id="transazione",
        label="Transazione / Accordo stragiudiziale",
        area="Stragiudiziale",
        materia=Materia.STRAGIUD,
        grado_default=Grado.TRIBUNALE,
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
        grado_default=Grado.TRIBUNALE,
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
        materia=Materia.CIVILE_COGN,
        grado_default=Grado.TRIBUNALE,
        fasi_default=_FASI_BASE,
        base_normativa="Tab. A2 DM 55/2014 (applicazione analogica) — artt. 806 ss. c.p.c.",
    ),
    TipoPratica(
        id="domiciliazione",
        label="Domiciliazione",
        area="Speciali",
        materia=Materia.STRAGIUD,
        grado_default=Grado.TRIBUNALE,
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
        grado_default=Grado.TRIBUNALE,
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
        {"descrizione": "Marca da bollo ricorso", "importo": 27.0},
        {"descrizione": "Contributo Unificato (indicativo)", "importo": 98.0},
        {"descrizione": "Notifica tramite Ufficiale Giudiziario", "importo": 25.0},
    ],
    "decreto_ingiuntivo": [
        {"descrizione": "Marca da bollo ricorso D.I.", "importo": 27.0},
        {"descrizione": "Contributo Unificato", "importo": 98.0},
        {"descrizione": "Notifica D.I. tramite U.G.", "importo": 25.0},
        {"descrizione": "Diritti U.G. notifica", "importo": 12.0},
    ],
    "opposizione_di": [
        {"descrizione": "Contributo Unificato opposizione", "importo": 196.0},
        {"descrizione": "Notifica atto di citazione", "importo": 25.0},
        {"descrizione": "Marca da bollo", "importo": 27.0},
    ],
    "atto_citazione": [
        {"descrizione": "Contributo Unificato (indicativo)", "importo": 196.0},
        {"descrizione": "Notifica atto citazione tramite U.G.", "importo": 25.0},
        {"descrizione": "Marca da bollo", "importo": 27.0},
    ],
    "comparsa_risposta": [
        {"descrizione": "Marca da bollo comparsa", "importo": 27.0},
        {"descrizione": "Contributo Unificato (se non già versato)", "importo": 196.0},
    ],
    "appello_civile": [
        {"descrizione": "Contributo Unificato appello", "importo": 392.0},
        {"descrizione": "Notifica atto di appello", "importo": 25.0},
        {"descrizione": "Marca da bollo", "importo": 27.0},
    ],
    "cassazione_civile": [
        {"descrizione": "Contributo Unificato Cassazione", "importo": 784.0},
        {"descrizione": "Notifica ricorso Cassazione", "importo": 30.0},
        {"descrizione": "Marca da bollo", "importo": 27.0},
    ],
    "precetto": [
        {"descrizione": "Notifica precetto tramite U.G.", "importo": 25.0},
        {"descrizione": "Diritti U.G. notifica precetto", "importo": 12.0},
        {"descrizione": "Copia autentica titolo esecutivo", "importo": 15.0},
    ],
    "pignoramento": [
        {"descrizione": "Diritti U.G. pignoramento mobiliare", "importo": 50.0},
        {"descrizione": "Iscrizione a ruolo procedura esecutiva", "importo": 43.0},
        {"descrizione": "Marca da bollo", "importo": 27.0},
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
        {"descrizione": "Marca da bollo", "importo": 27.0},
    ],
    "opposizione_esecutiva": [
        {"descrizione": "Contributo Unificato opposizione esec.", "importo": 196.0},
        {"descrizione": "Marca da bollo", "importo": 27.0},
    ],
    "separazione_consensuale": [
        {"descrizione": "Marca da bollo ricorso", "importo": 27.0},
        {"descrizione": "Bollo verbale udienza", "importo": 16.0},
    ],
    "separazione_giudiziale": [
        {"descrizione": "Contributo Unificato", "importo": 196.0},
        {"descrizione": "Marca da bollo", "importo": 27.0},
        {"descrizione": "Notifica atto citazione", "importo": 25.0},
    ],
    "divorzio_congiunto": [
        {"descrizione": "Marca da bollo ricorso", "importo": 27.0},
        {"descrizione": "Bollo verbale udienza", "importo": 16.0},
    ],
    "divorzio_giudiziale": [
        {"descrizione": "Contributo Unificato", "importo": 196.0},
        {"descrizione": "Marca da bollo", "importo": 27.0},
        {"descrizione": "Notifica atto di citazione", "importo": 25.0},
    ],
    "procedimenti_famiglia": [
        {"descrizione": "Marca da bollo ricorso", "importo": 27.0},
        {"descrizione": "Contributo Unificato (se dovuto)", "importo": 98.0},
    ],
    # ── LAVORO ──
    "controversia_lavoro": [
        {"descrizione": "Marca da bollo ricorso lavoro", "importo": 27.0},
        {"descrizione": "Contributo Unificato lavoro", "importo": 18.0},
        {"descrizione": "Notifica (se richiesta)", "importo": 15.0},
    ],
    "licenziamento": [
        {"descrizione": "Marca da bollo ricorso", "importo": 27.0},
        {"descrizione": "Contributo Unificato", "importo": 18.0},
    ],
    "differenze_retributive": [
        {"descrizione": "Marca da bollo", "importo": 27.0},
        {"descrizione": "Contributo Unificato", "importo": 18.0},
        {"descrizione": "Estratti busta paga / documenti", "importo": 20.0},
    ],
    "appello_lavoro": [
        {"descrizione": "Contributo Unificato appello lavoro", "importo": 36.0},
        {"descrizione": "Marca da bollo", "importo": 27.0},
    ],
    "previdenza": [
        {"descrizione": "Marca da bollo ricorso previdenziale", "importo": 27.0},
        {"descrizione": "Contributo Unificato previdenziale", "importo": 9.0},
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
        {"descrizione": "Marca da bollo ricorso", "importo": 27.0},
        {"descrizione": "Notifica ricorso (atti da notificare)", "importo": 30.0},
    ],
    "cautelare_sospensiva": [
        {"descrizione": "Contributo Unificato TAR (+ misura cautelare)", "importo": 650.0},
        {"descrizione": "Marca da bollo", "importo": 27.0},
        {"descrizione": "Notifica motivi aggiunti/cautelare", "importo": 25.0},
    ],
    "motivi_aggiunti": [
        {"descrizione": "Contributo Unificato motivi aggiunti", "importo": 650.0},
        {"descrizione": "Notifica motivi aggiunti", "importo": 25.0},
    ],
    "appello_cds": [
        {"descrizione": "Contributo Unificato CdS", "importo": 1300.0},
        {"descrizione": "Marca da bollo", "importo": 27.0},
        {"descrizione": "Notifica appello", "importo": 30.0},
    ],
    "ottemperanza": [
        {"descrizione": "Contributo Unificato ottemperanza", "importo": 650.0},
        {"descrizione": "Marca da bollo", "importo": 27.0},
    ],
    # ── TRIBUTARIO ──
    "ricorso_tributario": [
        {"descrizione": "Contributo Unificato CGT (base)", "importo": 30.0},
        {"descrizione": "Marca da bollo ricorso", "importo": 27.0},
        {"descrizione": "Notifica ricorso", "importo": 15.0},
    ],
    "appello_tributario": [
        {"descrizione": "Contributo Unificato CGT appello", "importo": 60.0},
        {"descrizione": "Marca da bollo", "importo": 27.0},
    ],
    "cassazione_tributaria": [
        {"descrizione": "Contributo Unificato Cassazione trib.", "importo": 784.0},
        {"descrizione": "Marca da bollo", "importo": 27.0},
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
    return result


# ──────────────────────────────────────────────────────────────────────────────
# RisultatoMotore — risultato completo del calcolo
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RisultatoMotore:
    """Calcolo completo: DM 55/2014 → spese generali → CPA → IVA → esborsi → totale."""

    tipo_pratica: TipoPratica
    calcolo_dm55: RisultatoCalcolo

    # Valori calcolati dal motore
    onorario_base: float        # totale con spese generali (da calcolo_dm55)
    cpa: float                  # Cassa Forense 4% (su onorario_base)
    base_iva: float             # onorario_base + cpa
    iva: float                  # 22% (se applica_iva)
    anticipazioni: float        # esborsi art. 15 (esenti da CPA/IVA)
    totale: float               # totale finale

    applica_cpa: bool = True
    applica_iva: bool = True

    def to_dict(self) -> dict:
        return {
            "tipo_pratica": self.tipo_pratica.to_dict(),
            "calcolo_dm55": self.calcolo_dm55.to_dict(),
            "onorario_base": self.onorario_base,
            "cpa": self.cpa,
            "base_iva": self.base_iva,
            "iva": self.iva,
            "anticipazioni": self.anticipazioni,
            "totale": self.totale,
            "applica_cpa": self.applica_cpa,
            "applica_iva": self.applica_iva,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Funzione principale: motore_calcola
# ──────────────────────────────────────────────────────────────────────────────

def motore_calcola(
    id_pratica: str,
    valore_controversia: float = 0.0,
    grado: Optional[Grado] = None,
    fasi: Optional[List[Fase]] = None,
    bonus_telematico: bool = False,
    includi_spese_generali: bool = True,
    perc_spese_generali: float = 0.15,
    variazioni_fasi: Optional[Dict[str, float]] = None,
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

    calcolo = calcola_compenso(
        materia=tp.materia,
        grado=_grado,
        valore=valore_controversia,
        fasi=_fasi,
        bonus_telematico=bonus_telematico,
        includi_spese_generali=includi_spese_generali,
        perc_spese_generali=perc_spese_generali,
        variazioni_fasi=variazioni_fasi or None,
    )

    onorario_base = calcolo.totale_con_spese if includi_spese_generali else calcolo.totale_base
    cpa = round(onorario_base * 0.04, 2) if applica_cpa else 0.0
    base_iva = round(onorario_base + cpa, 2)
    iva = round(base_iva * 0.22, 2) if applica_iva else 0.0
    totale = round(base_iva + iva + anticipazioni, 2)

    return RisultatoMotore(
        tipo_pratica=tp,
        calcolo_dm55=calcolo,
        onorario_base=onorario_base,
        cpa=cpa,
        base_iva=base_iva,
        iva=iva,
        anticipazioni=anticipazioni,
        totale=totale,
        applica_cpa=applica_cpa,
        applica_iva=applica_iva,
    )
