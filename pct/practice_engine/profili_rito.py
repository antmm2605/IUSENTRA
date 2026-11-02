"""Profili di rito: il procedimento giudiziale quando la pratica specifica non è nel catalogo.

Il catalogo operativo (`pct/legal_platform_seed.py`) descrive pratiche
specifiche (licenziamento, retribuzione, gara d'appalto…). Un fascicolo
giudiziale ben identificato — ufficio, sezione, registro, atto introduttivo —
ha però sempre un rito, anche quando l'oggetto della lite non coincide con una
pratica del catalogo. Questi profili descrivono il rito, con la norma che lo
disciplina, e non aggiungono requisiti che la norma non preveda.

Basi normative:

- rito del lavoro e della previdenza: artt. 409, 413, 414, 415, 442 c.p.c.;
- processo ordinario di cognizione: artt. 163, 163-bis, 165, 168 c.p.c.
  (testo del D.Lgs. 149/2022);
- procedimento semplificato di cognizione: artt. 281-decies, 281-undecies c.p.c.;
- procedimento in materia di persone, minorenni e famiglie: artt. 473-bis,
  473-bis.11, 473-bis.12 c.p.c.;
- ricorso al TAR: artt. 40, 41, 45 c.p.a. (D.Lgs. 104/2010) e deposito
  telematico PAT (D.P.C.M. 16 febbraio 2016, n. 40);
- per tutti: procura alle liti (art. 83 c.p.c.; art. 24 c.p.a.) e contributo
  unificato quando dovuto (art. 9 e art. 13 D.P.R. 115/2002).
"""

from __future__ import annotations

from dataclasses import replace

from pct.legal_platform_catalog import LegalOperationalProcedure

from .models import PracticeProfile

RITO_LAVORO = "PROC_RITO_LAVORO_001"
RITO_ORDINARIO = "PROC_RITO_ORDINARIO_001"
RITO_SEMPLIFICATO = "PROC_RITO_SEMPLIFICATO_001"
RITO_FAMIGLIA = "PROC_RITO_FAMIGLIA_001"
RITO_TAR = "PROC_RITO_TAR_001"

_VERIFICA_DATI = "Verifica dati cliente e parti"
_CODICE_OGGETTO = "Codice oggetto PST ufficiale"
_CLASSIFICAZIONE = "Classificazione atto principale e allegati"
_FIRMA_BUSTA = "Firma digitale e busta ministeriale"


def _documento(label: str, *, required: bool = True, message: str = "") -> dict[str, object]:
    return {"label": label, "required": required, "blocking": required, "message": message}


def _contributo(norma: str) -> dict[str, object]:
    return _documento(
        "Contributo unificato quando dovuto",
        required=False,
        message=f"Il contributo unificato si versa nella misura e nei casi di esenzione previsti ({norma}).",
    )


def _procedura(
    code: str,
    name: str,
    *,
    area: str,
    fascicolo_type: str,
    channel: str,
    registry: str,
    workflow: str,
    documenti: tuple[dict[str, object], ...],
    checklist: tuple[str, ...],
    template_labels: tuple[str, ...],
) -> LegalOperationalProcedure:
    return LegalOperationalProcedure(
        code=code,
        name=name,
        source_wave="profili_rito",
        area_label=area,
        subbranch_code=code,
        coverage_mode="RITO",
        operational_priority=50,
        channel_code=channel,
        registry_code=registry,
        workflow_code=workflow,
        complexity_level="STANDARD",
        estimated_duration_days=0,
        requires_human_review=True,
        requires_hearing=True,
        requires_registry_enrollment=True,
        allows_settlement=True,
        fascicolo_type=fascicolo_type,
        required_documents=documenti,  # type: ignore[arg-type]  # requisiti con obbligatorietà dichiarata
        checklist=checklist,
        template_labels=template_labels,
    )


def _profilo(procedura: LegalOperationalProcedure, fonte: str) -> PracticeProfile:
    from .profiles import build_profile_from_procedure

    return replace(build_profile_from_procedure(procedura), source=fonte)


def profili_di_rito() -> list[PracticeProfile]:
    """I profili di rito, ciascuno con la norma che lo disciplina come fonte."""
    procura = _documento("Procura alle liti (art. 83 c.p.c.)")
    return [
        _profilo(_procedura(
            RITO_LAVORO, "Controversia di lavoro e previdenza (rito del lavoro)",
            area="Lavoro e previdenza", fascicolo_type="LAVORO", channel="PCT_LAVORO", registry="SICID",
            workflow="WF_RITO_LAVORO",
            documenti=(
                _documento("Ricorso (art. 414 c.p.c.)"),
                procura,
                _documento("Documenti offerti in comunicazione (art. 414, n. 5, c.p.c.)", required=False),
                _contributo("artt. 9 e 13, comma 3, D.P.R. 115/2002"),
            ),
            checklist=(_VERIFICA_DATI, _CODICE_OGGETTO, _CLASSIFICAZIONE, _FIRMA_BUSTA),
            template_labels=("Ricorso ex art. 414 c.p.c.", "Memoria difensiva ex art. 416 c.p.c."),
        ), "artt. 409, 413, 414, 415, 442 c.p.c."),
        _profilo(_procedura(
            RITO_ORDINARIO, "Processo ordinario di cognizione",
            area="Civile", fascicolo_type="CIVILE", channel="PCT_CIVILE", registry="SICID",
            workflow="WF_RITO_ORDINARIO",
            documenti=(
                _documento("Atto di citazione notificato (artt. 163 e 165 c.p.c.)"),
                procura,
                _contributo("art. 13 D.P.R. 115/2002"),
            ),
            checklist=(_VERIFICA_DATI, _CODICE_OGGETTO, _CLASSIFICAZIONE, _FIRMA_BUSTA),
            template_labels=("Atto di citazione", "Comparsa di costituzione e risposta"),
        ), "artt. 163, 163-bis, 165, 168 c.p.c."),
        _profilo(_procedura(
            RITO_SEMPLIFICATO, "Procedimento semplificato di cognizione",
            area="Civile", fascicolo_type="CIVILE", channel="PCT_CIVILE", registry="SICID",
            workflow="WF_RITO_SEMPLIFICATO",
            documenti=(
                _documento("Ricorso (art. 281-undecies c.p.c.)"),
                procura,
                _contributo("art. 13 D.P.R. 115/2002"),
            ),
            checklist=(_VERIFICA_DATI, _CODICE_OGGETTO, _CLASSIFICAZIONE, _FIRMA_BUSTA),
            template_labels=("Ricorso ex art. 281-undecies c.p.c.",),
        ), "artt. 281-decies, 281-undecies c.p.c."),
        _profilo(_procedura(
            RITO_FAMIGLIA, "Procedimento in materia di persone, minorenni e famiglie",
            area="Famiglia", fascicolo_type="FAMIGLIA", channel="PCT_CIVILE", registry="SICID",
            workflow="WF_RITO_FAMIGLIA",
            documenti=(
                _documento("Ricorso (art. 473-bis.12 c.p.c.)"),
                procura,
                _documento(
                    "Documentazione economica (art. 473-bis.12, terzo comma, c.p.c.)",
                    required=False,
                    message="Necessaria quando sono proposte domande di contributo economico o vi sono figli minori.",
                ),
                _contributo("art. 13 D.P.R. 115/2002"),
            ),
            checklist=(_VERIFICA_DATI, _CODICE_OGGETTO, _CLASSIFICAZIONE, _FIRMA_BUSTA),
            template_labels=("Ricorso ex art. 473-bis.12 c.p.c.",),
        ), "artt. 473-bis, 473-bis.11, 473-bis.12 c.p.c."),
        _profilo(_procedura(
            RITO_TAR, "Ricorso al TAR (processo amministrativo)",
            area="Amministrativo", fascicolo_type="AMMINISTRATIVO", channel="PAT_AMMINISTRATIVO",
            registry="PAT_AMMINISTRATIVO", workflow="WF_RITO_TAR",
            documenti=(
                _documento("Ricorso notificato (artt. 40 e 41 c.p.a.)"),
                _documento("Procura alle liti (art. 24 c.p.a.)"),
                _documento("Provvedimento impugnato (art. 40 c.p.a.)"),
                _contributo("art. 13, comma 6-bis, D.P.R. 115/2002"),
            ),
            checklist=(_VERIFICA_DATI, _CLASSIFICAZIONE, _FIRMA_BUSTA),
            template_labels=("Ricorso al TAR",),
        ), "artt. 40, 41, 45 c.p.a.; D.P.C.M. 40/2016"),
    ]


__all__ = [
    "RITO_FAMIGLIA", "RITO_LAVORO", "RITO_ORDINARIO", "RITO_SEMPLIFICATO", "RITO_TAR", "profili_di_rito",
]
