"""Modelli dei termini del processo amministrativo, tributario e penale (motore unico dei termini).

Un solo motore per scadenziario, modello della causa e harness di Lex: i modelli si aggiungono ai
``DEFAULT_TEMPLATES`` di ``pct/termini_processuali.py`` e si calcolano con ``ItalianDeadlineCalculator``.
Testi letti il 19-20/11/2026 nell'archivio Normattiva del software (stato «VIGENTE»):

- c.p.a., D.Lgs. 104/2010, all. 1: art. 29 (annullamento, «termine di decadenza di sessanta giorni»); art. 43 (motivi
  aggiunti: «si applica la disciplina prevista per il ricorso, ivi compresa quella relativa ai termini»); art. 45
  (deposito «nel termine perentorio di trenta giorni» dall'ultima notificazione perfezionata); art. 46 (costituzione
  delle parti intimate entro sessanta giorni dal perfezionamento della notificazione); art. 92 (impugnazioni: sessanta
  giorni dalla notificazione della sentenza, sei mesi dalla pubblicazione senza notificazione); art. 120, comma 2
  (appalti: ricorso e motivi aggiunti «nel termine di trenta giorni»); art. 54, commi 2-3 (sospensione dal 1° al 31
  agosto, esclusa per il procedimento cautelare);
- D.Lgs. 546/1992 (vigente fino al 31/12/2026, poi D.Lgs. 175/2024): art. 21 (ricorso entro sessanta giorni dalla
  notificazione dell'atto, a pena di inammissibilità); art. 22 (costituzione del ricorrente entro trenta giorni dalla
  proposizione del ricorso); art. 51 (impugnazione entro sessanta giorni dalla notificazione della sentenza);
  art. 38, comma 3 (senza notificazione: art. 327 c.p.c., sei mesi); D.Lgs. 218/1997, art. 6, commi 2, 2-bis e 3
  (istanza di accertamento con adesione: termine per impugnare sospeso per novanta giorni; trenta giorni se l'istanza
  segue la notifica di un atto preceduto dallo schema in contraddittorio preventivo); sospensione feriale: art. 1
  L. 742/1969 (giurisdizioni ordinarie e amministrative);
- c.p.p. (D.P.R. 447/1988): art. 461 (opposizione al decreto penale entro quindici giorni dalla notificazione);
  art. 585 (impugnazione: 15, 30 o 45 giorni secondo l'art. 544; più quindici per il difensore dell'imputato giudicato
  in assenza, comma 1-bis); art. 408, commi 3 e 3-bis (opposizione alla richiesta di archiviazione entro venti giorni,
  trenta per i delitti con violenza alla persona e per l'art. 624-bis c.p.), art. 410; art. 172 (niente proroga del
  sabato); c.p. art. 124 (querela entro tre mesi dalla notizia del fatto: termine sostanziale); L. 742/1969, art. 2
  (in materia penale la sospensione non opera per gli imputati in custodia cautelare se essi o i difensori vi
  rinunciano, né per le indagini sui reati di criminalità organizzata, né quando il giudice dichiara l'urgenza).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pct.termini_processuali import DeadlineTemplate

_PRUDENZA_FERIALE = "dubbio_feriale"

TEMPLATES_RITI: tuple[DeadlineTemplate, ...] = (
    # --- processo amministrativo (c.p.a.) ---
    DeadlineTemplate(code="AMM_RICORSO_29", name="Ricorso al TAR per l'annullamento", matter_type="admin", base_value=60,
                     reference_law="Art. 29 c.p.a.; art. 41 c.p.a.; art. 54, comma 2, c.p.a.",
                     metadata={"source_event": "notifica_o_piena_conoscenza_atto"}),
    DeadlineTemplate(code="AMM_APPALTI_120", name="Ricorso al TAR in materia di appalti", matter_type="admin", base_value=30,
                     reference_law="Art. 120, comma 2, c.p.a.; art. 54, comma 2, c.p.a.",
                     metadata={"source_event": "comunicazione_aggiudicazione"}),
    DeadlineTemplate(code="AMM_MOTIVI_AGGIUNTI_43", name="Motivi aggiunti", matter_type="admin", base_value=60,
                     reference_law="Art. 43, comma 1, c.p.a. (termini del ricorso, art. 29); trenta giorni negli appalti (art. 120, comma 2)",
                     metadata={"source_event": "conoscenza_nuovo_atto"}),
    DeadlineTemplate(code="AMM_DEPOSITO_45", name="Deposito del ricorso notificato", matter_type="admin", base_value=30,
                     reference_law="Art. 45, comma 1, c.p.a. (perentorio)", metadata={"source_event": "ultima_notifica_perfezionata"}),
    DeadlineTemplate(code="AMM_COSTITUZIONE_46", name="Costituzione delle parti intimate", matter_type="admin", base_value=60,
                     reference_law="Art. 46, comma 1, c.p.a.", metadata={"source_event": "notifica_ricorso"}),
    DeadlineTemplate(code="AMM_APPELLO_92", name="Appello al Consiglio di Stato (sentenza notificata)", matter_type="admin",
                     base_value=60, reference_law="Art. 92, comma 1, c.p.a. (perentorio)",
                     metadata={"source_event": "notifica_sentenza"}),
    DeadlineTemplate(code="AMM_APPELLO_LUNGO_92", name="Appello al Consiglio di Stato (sentenza non notificata)",
                     matter_type="admin", base_value=6, period_type="months", reference_law="Art. 92, comma 3, c.p.a.",
                     metadata={"source_event": "pubblicazione_sentenza"}),
    DeadlineTemplate(code="AMM_CAUTELARE_54", name="Termine nel procedimento cautelare amministrativo", matter_type="admin",
                     base_value=30, suspend_august=False, ferial_suspension_policy="not_applicable",
                     reference_law="Art. 54, comma 3, c.p.a. (sospensione feriale esclusa nel procedimento cautelare)",
                     metadata={"source_event": "provvedimento_cautelare", "manual": True}),
    # --- processo tributario (D.Lgs. 546/1992) ---
    DeadlineTemplate(code="TRIB_RICORSO_21", name="Ricorso tributario", matter_type="tax", base_value=60,
                     reference_law="Art. 21, comma 1, d.lgs. 546/1992; art. 1 l. 742/1969",
                     metadata={"source_event": "notifica_atto_impositivo"}),
    DeadlineTemplate(code="TRIB_COSTITUZIONE_22", name="Costituzione del ricorrente", matter_type="tax", base_value=30,
                     reference_law="Art. 22, comma 1, d.lgs. 546/1992 (a pena di inammissibilità)",
                     metadata={"source_event": "proposizione_ricorso"}),
    DeadlineTemplate(code="TRIB_APPELLO_51", name="Appello tributario (sentenza notificata)", matter_type="tax", base_value=60,
                     reference_law="Art. 51, comma 1, d.lgs. 546/1992", metadata={"source_event": "notifica_sentenza"}),
    DeadlineTemplate(code="TRIB_APPELLO_LUNGO_38", name="Appello tributario (sentenza non notificata)", matter_type="tax",
                     base_value=6, period_type="months",
                     reference_law="Art. 38, comma 3, d.lgs. 546/1992; art. 327, comma 1, c.p.c.",
                     metadata={"source_event": "deposito_sentenza"}),
    # --- processo penale (c.p.p.) e querela (c.p.) ---
    DeadlineTemplate(code="PEN_OPPOSIZIONE_DECRETO_461", name="Opposizione al decreto penale di condanna", matter_type="penal",
                     base_value=15, reference_law="Art. 461, comma 1, c.p.p.; art. 172 c.p.p.; art. 1 l. 742/1969",
                     metadata={"source_event": "notifica_decreto_penale"}),
    DeadlineTemplate(code="PEN_IMPUGNAZIONE_585_15", name="Impugnazione (camera di consiglio o motivazione contestuale)",
                     matter_type="penal", base_value=15, reference_law="Art. 585, comma 1, lett. a), c.p.p.",
                     metadata={"source_event": "deposito_o_lettura"}),
    DeadlineTemplate(code="PEN_IMPUGNAZIONE_585_30", name="Impugnazione (motivazione entro quindici giorni)",
                     matter_type="penal", base_value=30, reference_law="Art. 585, comma 1, lett. b), c.p.p.; art. 544, comma 2",
                     metadata={"source_event": "scadenza_deposito_motivazione"}),
    DeadlineTemplate(code="PEN_IMPUGNAZIONE_585_45", name="Impugnazione (motivazione con termine più lungo)",
                     matter_type="penal", base_value=45, reference_law="Art. 585, comma 1, lett. c), c.p.p.; art. 544, comma 3",
                     metadata={"source_event": "scadenza_deposito_motivazione"}),
    DeadlineTemplate(code="PEN_OPPOSIZIONE_ARCHIVIAZIONE_408", name="Opposizione alla richiesta di archiviazione",
                     matter_type="penal", base_value=20, reference_law="Art. 408, comma 3, c.p.p.; art. 410 c.p.p.",
                     metadata={"source_event": "notifica_avviso_archiviazione"}),
    DeadlineTemplate(code="PEN_OPPOSIZIONE_ARCHIVIAZIONE_408_VIOLENZA", name="Opposizione all'archiviazione (violenza alla persona)",
                     matter_type="penal", base_value=30, reference_law="Art. 408, comma 3-bis, c.p.p.",
                     metadata={"source_event": "notifica_avviso_archiviazione"}),
    DeadlineTemplate(code="PEN_QUERELA_124", name="Termine per la querela", matter_type="penal", base_value=3,
                     period_type="months", suspend_august=False, ferial_suspension_policy="not_applicable",
                     extend_saturday=False, reference_law="Art. 124 c.p. (termine sostanziale: niente sospensione feriale)",
                     metadata={"source_event": "notizia_del_fatto"}),
    # --- esecuzione e materie civili con regola feriale propria ---
    DeadlineTemplate(code="CIV_IMPUGNAZIONE_DELIBERA_1137", name="Impugnazione della delibera condominiale", base_value=30,
                     suspend_august=True, extend_saturday=False,
                     reference_law="Art. 1137 c.c.; art. 1 l. 742/1969 come inciso da Corte cost. 49/1990",
                     metadata={"source_event": "deliberazione_o_comunicazione"}),
    DeadlineTemplate(code="CIV_MERITO_669_OCTIES", name="Inizio del giudizio di merito dopo la misura cautelare",
                     base_value=60, suspend_august=False, ferial_suspension_policy="manual_review",
                     reference_law="Art. 669-octies c.p.c.",
                     metadata={"source_event": "pronuncia_o_comunicazione_ordinanza", _PRUDENZA_FERIALE: True}),
)


def attraversa_agosto(dal: date, al: date) -> bool:
    return any(date(anno, 8, 1) <= al and date(anno, 8, 31) >= dal for anno in range(dal.year, al.year + 1))


def dubbio_feriale(template: DeadlineTemplate, dal: date, scadenza: date) -> str:
    """Il dubbio dichiarato quando la sospensione feriale è controversa e il termine attraversa agosto."""
    if not (template.metadata or {}).get(_PRUDENZA_FERIALE) or not attraversa_agosto(dal, scadenza):
        return ""
    return (f"Sospensione feriale controversa per {template.reference_law}: la data proposta è quella senza sospensione, "
            "la più prudente; con la sospensione il termine scadrebbe più tardi.")


def ricorso_tributario(notifica: date, *, istanza_adesione: date | None = None, dopo_schema: bool = False) -> dict[str, Any]:
    """Termine del ricorso tributario (art. 21 d.lgs. 546/1992) con l'eventuale istanza di accertamento con adesione.

    L'istanza sospende il termine per impugnare per novanta giorni (art. 6, comma 3, d.lgs. 218/1997); trenta se
    l'istanza segue la notifica di un atto preceduto dallo schema in contraddittorio preventivo (art. 6, comma 2-bis,
    ultimo periodo). La sospensione dell'adesione si somma a quella feriale (art. 1 l. 742/1969).
    """
    from pct.termini_processuali import ItalianDeadlineCalculator

    calcolatore = ItalianDeadlineCalculator()
    modello = next(t for t in TEMPLATES_RITI if t.code == "TRIB_RICORSO_21")
    if istanza_adesione is None:
        esito = calcolatore.calculate_template(notifica, modello)
        return {"scadenza": esito["deadline"], "sospensione_adesione": 0, "norma": modello.reference_law}
    giorni = 30 if dopo_schema else 90
    # Il termine resta sospeso per «giorni» dalla presentazione dell'istanza: il periodo utile diventa 60 + giorni,
    # contati con la sospensione feriale e la proroga del giorno festivo (art. 155 c.p.c.).
    from dataclasses import replace

    finale = date.fromisoformat(calcolatore.calculate_template(notifica, replace(modello, base_value=60 + giorni))["deadline"])
    return {"scadenza": finale.isoformat(), "sospensione_adesione": giorni,
            "norma": modello.reference_law + f"; art. 6, comma {'2-bis' if dopo_schema else '3'}, d.lgs. 218/1997"}


__all__ = ["TEMPLATES_RITI", "attraversa_agosto", "dubbio_feriale", "ricorso_tributario"]
