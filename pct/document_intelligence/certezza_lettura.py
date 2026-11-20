"""Quando la lettura di un documento è certa e non chiede verifiche all'avvocato (direttiva del 10/11/2026).

Un documento è riconosciuto con certezza se l'avvocato lo ha confermato o corretto, oppure se il catalogo lo ha
identificato dal contenuto (testo estratto e regola di identità con fonte normativa registrata) con affidabilità
pari o superiore alla soglia. Sotto la soglia o con la voce «da rivedere» c'è un dubbio reale e il dato resta da
confermare, con il motivo scritto dal catalogo.

Base: art. 20 CAD (D.Lgs. 82/2005) e art. 3 D.M. 44/2011 sull'integrità del documento informatico; le regole di
identità del catalogo citano la norma che definisce ciascun tipo di atto (pct/document_intelligence/catalog_sources.py).
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

SOGLIA_CERTEZZA = 90
STATI_DECISI_DALL_AVVOCATO = frozenset({"confirmed", "overridden"})


def lettura_certa(stato: Any, affidabilita: Any) -> bool:
    """Vero se la voce del catalogo è decisa dall'avvocato o riconosciuta dal contenuto con affidabilità certa."""
    stato = str(stato or "").strip()
    if stato in STATI_DECISI_DALL_AVVOCATO:
        return True
    if stato != "proposed":
        return False
    try:
        return int(affidabilita or 0) >= SOGLIA_CERTEZZA
    except (TypeError, ValueError):
        return False


STATO_AUTOMATICO = "catalogued"  # proposta certa dal contenuto: catalogata in automatico, nessuna conferma chiesta


def stato_catalogo(stato: Any, affidabilita: Any, *, ha_prova: bool, automatico: bool = False) -> str:
    """Lo stato del catalogo come lo vede l'avvocato, uguale in pannello, quadro e Lettura.

    Una proposta riconosciuta con certezza dal contenuto (``lettura_certa`` e almeno una prova letta) è catalogata
    in automatico; sotto la soglia, o senza prova, resta una proposta da confermare. Confermate, corrette e voci da
    rivedere restano come sono: la regola non tocca mai le decisioni dell'avvocato e non scrive nulla nel catalogo.
    """
    stato = str(stato or "").strip()
    if stato == "proposed" and ha_prova and (automatico or lettura_certa(stato, affidabilita)):
        return STATO_AUTOMATICO
    return stato


def motivo_da_confermare(stato: Any, affidabilita: Any, *, ha_prova: bool) -> str:
    """Perché una proposta chiede ancora la conferma (vuoto se non la chiede)."""
    if str(stato or "").strip() != "proposed":
        return ""
    if not ha_prova:
        return "manca una prova letta dal contenuto"
    try:
        valore = int(affidabilita or 0)
    except (TypeError, ValueError):
        valore = 0
    if valore < SOGLIA_CERTEZZA:
        return f"affidabilità {valore}% sotto la soglia di certezza del {SOGLIA_CERTEZZA}%"
    return ""


def riepilogo_catalogo(stati: Iterable[str | None]) -> dict[str, int]:
    """Un solo calcolo dei conteggi del catalogo, uno stato per documento del fascicolo (None = non ancora letto).

    Documenti = catalogati + da verificare + in attesa; catalogati = automatici + confermati + proposti.
    Le bozze dello studio non sono documenti del fascicolo: chi chiama non le passa.
    """
    elenco = [str(s or "").strip() for s in stati]
    automatici = sum(1 for s in elenco if s == STATO_AUTOMATICO)
    confermati = sum(1 for s in elenco if s in STATI_DECISI_DALL_AVVOCATO)
    proposti = sum(1 for s in elenco if s == "proposed")
    da_verificare = sum(1 for s in elenco if s == "review_required")
    catalogati = automatici + confermati + proposti
    return {"documenti": len(elenco), "catalogati": catalogati, "automatici": automatici, "confermati": confermati,
            "proposti": proposti, "da_verificare": da_verificare, "in_attesa": len(elenco) - catalogati - da_verificare}


__all__ = ["SOGLIA_CERTEZZA", "STATI_DECISI_DALL_AVVOCATO", "STATO_AUTOMATICO", "lettura_certa", "motivo_da_confermare",
           "riepilogo_catalogo", "stato_catalogo"]
