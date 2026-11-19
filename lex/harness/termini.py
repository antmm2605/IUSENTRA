"""Calcolo delle date con il motore dei termini di IUSENTRA (pct/termini_processuali.py).

Termini processuali: si esclude il giorno iniziale, si sospende dal 1° al 31 agosto quando la legge lo prevede
(art. 1 l. 742/1969) e la scadenza di sabato o festiva è prorogata al primo giorno non festivo (art. 155, commi 4 e 5,
c.p.c.). Termini sostanziali (decadenze, prescrizioni, termini di pagamento): niente sospensione feriale e niente
proroga del sabato, che vale solo per gli atti processuali; resta la proroga del giorno festivo (art. 2963, comma 3, c.c.).
"""
from __future__ import annotations

from datetime import date


def _calcola(dal: date, quanti: int, tipo: str, sospensione_feriale: bool, sostanziale: bool) -> date:
    from pct.termini_processuali import ItalianDeadlineCalculator

    esito = ItalianDeadlineCalculator().calculate(dal, quanti, period_type=tipo, suspend_august=sospensione_feriale,
                                                  extend_saturday=not sostanziale, template_code="LEX_HARNESS",
                                                  reference_law="")
    return date.fromisoformat(esito["deadline"])


def termine_giorni(dal: date, giorni: int, *, sospensione_feriale: bool = True, sostanziale: bool = False) -> date:
    return _calcola(dal, giorni, "days", sospensione_feriale and not sostanziale, sostanziale)


def termine_mesi(dal: date, mesi: int, *, sospensione_feriale: bool = True, sostanziale: bool = False) -> date:
    return _calcola(dal, mesi, "months", sospensione_feriale and not sostanziale, sostanziale)


def termine_anni(dal: date, anni: int, *, sostanziale: bool = True) -> date:
    return _calcola(dal, anni * 12, "months", False, sostanziale)


_GIORNI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")


def data_breve(d: date) -> str:
    return f"{_GIORNI[d.weekday()]} {d.strftime('%d/%m/%Y')}"


# ------------------------------------------------------------------ modelli dei termini processuali
# Ogni termine processuale passa da un modello con la sua norma: quelli collaudati del motore (DEFAULT_TEMPLATES) e,
# per i termini che il motore non ha, i modelli qui sotto. La sospensione feriale non si decide nelle regole.
# Fonti della sospensione: art. 1 l. 742/1969 (sospensione dal 1° al 31 agosto per le giurisdizioni ordinarie e
# amministrative) e art. 3 l. 742/1969 (esclusi i procedimenti dell'art. 92 ord. giud. e le controversie di lavoro).
def _modelli_harness():
    from pct.termini_processuali import DeadlineTemplate

    return {m.code: m for m in (
        DeadlineTemplate(code="LEX_LAV_APPELLO_434", name="Appello nel rito del lavoro", base_value=30, matter_type="labor",
                         suspend_august=False, ferial_suspension_policy="not_applicable",
                         reference_law="Art. 434, comma 2, c.p.c.; art. 3 l. 742/1969"),
        DeadlineTemplate(code="LEX_TRIB_RICORSO_21", name="Ricorso tributario", base_value=60,
                         reference_law="Art. 21 d.lgs. 546/1992; art. 1 l. 742/1969"),
        DeadlineTemplate(code="LEX_TRIB_COSTITUZIONE_22", name="Costituzione del ricorrente nel processo tributario",
                         base_value=30, reference_law="Art. 22 d.lgs. 546/1992; art. 1 l. 742/1969"),
        DeadlineTemplate(code="LEX_AMM_RICORSO_29", name="Ricorso al TAR per l'annullamento", base_value=60,
                         reference_law="Art. 29 e art. 41 c.p.a.; art. 1 l. 742/1969"),
        DeadlineTemplate(code="LEX_CAU_ESECUZIONE_675", name="Esecuzione del sequestro", base_value=30,
                         suspend_august=False, ferial_suspension_policy="not_applicable",
                         reference_law="Art. 675 c.p.c.; art. 3 l. 742/1969 e art. 92 ord. giud. (procedimenti cautelari)"),
        DeadlineTemplate(code="LEX_PEN_QUERELA_124", name="Termine per la querela", base_value=3, period_type="months",
                         matter_type="penal", suspend_august=False, ferial_suspension_policy="not_applicable",
                         reference_law="Art. 124 c.p.; computo ex art. 14 c.p. (sostanziale)"),
        # Art. 92 ord. giud. («opposizione all'esecuzione») letto dalla Cassazione anche per gli artt. 617 e 619 c.p.c.
        # (Cass. ord. 21568/2017; Cass. 9998/2010): niente sospensione feriale. Il modello ESE_OPPOSIZIONE_ATTI_617 del
        # motore la applica: discordanza segnalata, l'harness usa questo.
        DeadlineTemplate(code="LEX_ESE_OPPOSIZIONE_ATTI_617", name="Opposizione agli atti esecutivi", base_value=20,
                         suspend_august=False, ferial_suspension_policy="not_applicable",
                         reference_law="Art. 617 c.p.c.; art. 92 ord. giud. (Cass. ord. 21568/2017)"),
        # Art. 1137 c.c.: termine sostanziale a rilevanza processuale; la sospensione feriale si applica per Corte cost.
        # 49/1990 (illegittimità dell'art. 1 l. 742/1969 nella parte in cui non la estendeva a questo termine).
        DeadlineTemplate(code="LEX_CONDOMINIO_1137", name="Impugnazione della delibera condominiale", base_value=30,
                         suspend_august=True, extend_saturday=False,
                         reference_law="Art. 1137 c.c.; art. 1 l. 742/1969 come inciso da Corte cost. 49/1990"),
        DeadlineTemplate(code="LEX_CAU_MERITO_669OCTIES", name="Inizio del giudizio di merito dopo la misura cautelare",
                         base_value=60, suspend_august=False, ferial_suspension_policy="da_verificare",
                         reference_law="Art. 669-octies c.p.c."),
    )}


def termine(codice: str, dal: date) -> date:
    """Scadenza con il modello indicato (motore dei termini di IUSENTRA)."""
    from pct.termini_processuali import DEFAULT_TEMPLATES, ItalianDeadlineCalculator

    modello = _modelli_harness().get(codice) or next(t for t in DEFAULT_TEMPLATES if t.code == codice)
    return date.fromisoformat(ItalianDeadlineCalculator().calculate_template(dal, modello)["deadline"])


def tocca_agosto(dal: date, al: date) -> bool:
    return any(date(a, 8, 1) <= al and date(a, 8, 31) >= dal for a in range(dal.year, al.year + 1))
