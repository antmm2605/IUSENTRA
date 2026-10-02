"""Esito onesto per le domande giuridiche senza fonti pertinenti o bloccate da una guardia.

Quando Lex non ha testo di norma o sentenze pertinenti, o quando la bozza del modello e'
stata fermata dalla guardia anti allucinazione, l'avvocato deve leggere una cosa sola:
le fonti disponibili non bastano, e che cosa manca. Niente "Dato certo", niente percentuale
di attendibilita', niente elenco di fonti interne (template, impostazioni, PEC, catalogo).
"""

from __future__ import annotations

import logging
from typing import Any

from lex.retrieval.filters import TIPI_EVIDENZA_GIURIDICA, WORKFLOW_GIURIDICI

logger = logging.getLogger(__name__)


def _valore(item: Any, nome: str) -> Any:
    return item.get(nome) if isinstance(item, dict) else getattr(item, nome, None)


def evidenze_giuridiche_pertinenti(items: list[Any]) -> list[Any]:
    """Evidenze che sono testo di norma, sentenza, prassi o fonte ufficiale letta, con un estratto."""

    return [
        item
        for item in list(items or [])
        if str(_valore(item, "source_type") or "").strip().lower() in TIPI_EVIDENZA_GIURIDICA
        and str(_valore(item, "content") or _valore(item, "excerpt") or "").strip()
    ]


def e_domanda_giuridica_risposta(request: Any, workflow: str) -> bool:
    if workflow == "giurisprudenza_specifica":
        return False
    if workflow in WORKFLOW_GIURIDICI:
        return True
    if workflow == "question_answering" and not getattr(request, "fascicolo_id", None):
        try:
            from lex.ricerca_giuridica.classificatore import classifica_domanda

            return classifica_domanda(str(getattr(request, "query", "") or "")).giuridica
        except Exception:
            return False
    return False


def diagnosi_archivio_normattiva() -> list[str]:
    """Che cosa manca nell'installazione: archivio Normattiva, indice di ricerca."""

    try:
        from lex.retrieval.official_sources_retriever import official_archive_snapshot

        stato = dict(official_archive_snapshot().get("normattiva") or {})
    except Exception:
        logger.exception("Diagnosi archivio Normattiva non riuscita.")
        return ["Non e' stato possibile verificare lo stato dell'archivio Normattiva."]
    if not stato.get("available") or not int(stato.get("chunks") or 0):
        return [
            "L'archivio Normattiva non e' stato importato in questa installazione: non ho nessun testo di norma da consultare."
        ]
    try:
        import sqlite3

        from lex.ricerca_giuridica.indice_fts import indice_fts_presente

        conn = sqlite3.connect(str(stato.get("path")))
        try:
            if not indice_fts_presente(conn):
                return [
                    "L'archivio Normattiva e' presente ma l'indice di ricerca non e' stato costruito: la ricerca per pertinenza non e' attiva."
                ]
        finally:
            conn.close()
    except Exception:
        pass
    return ["Nell'archivio Normattiva non ho trovato articoli pertinenti alla domanda."]


def costruisci_esito_onesto(
    *, workflow: str, guard_bloccata: bool, pertinenti: list[Any], lacune: list[str] | None = None
) -> tuple[str, list[str]]:
    """Ritorna (testo per l'avvocato, elenco di cio' che manca)."""

    manca: list[str] = []
    if not pertinenti:
        manca.extend(diagnosi_archivio_normattiva())
        if workflow == "giurisprudenza":
            manca.append("Nel corpus di giurisprudenza non ho trovato sentenze pertinenti alla domanda.")
    if guard_bloccata:
        manca.append(
            "La bozza di risposta citava riferimenti normativi o giurisprudenziali che non risultano nelle fonti verificate, "
            "per questo non viene mostrata."
        )
    for lacuna in lacune or []:
        voce = " ".join(str(lacuna or "").split())
        if voce and voce not in manca:
            manca.append(voce)
    righe = ["Le fonti disponibili non bastano per rispondere a questa domanda in modo affidabile."]
    if manca:
        righe.append("")
        righe.append("Cosa manca:")
        righe.extend(f"- {voce}" for voce in manca)
    if pertinenti:
        righe.append("")
        righe.append("Fonti giuridiche pertinenti trovate (non sufficienti per una risposta completa):")
        for item in pertinenti[:3]:
            titolo = str(_valore(item, "title") or "Fonte").strip()
            righe.append(f"- {titolo}")
    righe.append("")
    righe.append("Cosa puoi fare:")
    righe.append("- Importa o aggiorna l'archivio Normattiva e costruisci l'indice di ricerca.")
    righe.append("- Indica l'articolo e il codice di riferimento per una ricerca puntuale.")
    righe.append("- Verifica la questione direttamente su Normattiva o sulle banche dati giuridiche prima di usarla.")
    return "\n".join(righe), manca


__all__ = [
    "costruisci_esito_onesto",
    "diagnosi_archivio_normattiva",
    "e_domanda_giuridica_risposta",
    "evidenze_giuridiche_pertinenti",
]
