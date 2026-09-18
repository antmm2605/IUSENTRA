"""Il motore documenti: da un testo ai fatti collaudati.

Non apre file e non sa nulla di Flask: riceve il testo (nativo, OCR o
dell'indice documentale), il nome del documento, l'origine e il contesto del
fascicolo; restituisce i fatti già collaudati, senza doppioni, i più solidi
per primi. La versione cambia quando cambiano le regole di estrazione o di
collaudo: il registro rimette allora da leggere tutto per questo motore.
"""

from __future__ import annotations

from typing import Iterable

from legal_ocr.formulario import VERSIONE_FORMULARIO
from pct.registro_letture.fatti_repository import Fatto

from .collaudo import Contesto, collauda_tutti
from .estrazione_date import estrai_date
from .estrazione_importi import VERSIONE_ESTRAZIONE_IMPORTI
from .estrazione_importi import VERSIONE_ESTRAZIONE_IMPORTI, estrai_importi
from .estrazione_istituti import VERSIONE_ESTRAZIONE_ISTITUTI
from .estrazione_notifiche import estrai_prove_notifica
from .estrazione_ruolo import estrai_ruoli

VERSIONE_MOTORE_DOCUMENTI = f"2026.09.18.motore-documenti.v12+ciclo-fermo+fatti-obsoleti+importi:{VERSIONE_ESTRAZIONE_IMPORTI}+istituti:{VERSIONE_ESTRAZIONE_ISTITUTI}+{VERSIONE_FORMULARIO}"
VERSIONI_MOTORE_DOCUMENTI_COMPATIBILI = (
    VERSIONE_MOTORE_DOCUMENTI,
    f"2026.09.18.motore-documenti.v10+fatti-obsoleti+importi:{VERSIONE_ESTRAZIONE_IMPORTI}+{VERSIONE_FORMULARIO}",
    f"2026.09.16.motore-documenti.v7+{VERSIONE_FORMULARIO}",
)
FATTI_MASSIMI = 80
ORDINE_VERIFICA = {"verificata": 0, "corretta": 0, "plausibile": 1, "respinta": 2, "ignorata": 3}


def _senza_doppioni(fatti: Iterable[Fatto]) -> list[Fatto]:
    visti: set[str] = set()
    esito: list[Fatto] = []
    for fatto in fatti:
        if fatto.chiave in visti:
            continue
        visti.add(fatto.chiave)
        esito.append(fatto)
    return esito


def leggi_testo(
    testo: str, *, origine: str, contesto: Contesto, nome: str = "",
    con_ruoli: bool = True, con_notifiche: bool = True, con_importi: bool = True,
    metadata: dict[str, object] | None = None,
) -> list[Fatto]:
    """I fatti del testo, collaudati: date ancorate, prove di notifica, ruoli, importi."""
    testo = str(testo or "")
    if not testo.strip():
        return []
    from .estrazione_domanda import estrai_domanda
    from .estrazione_istituti import qualifica_istituti
    # La data non basta: «termine del 10/09/2026» non dice all'avvocato che cosa
    # deve fare. Qui la data prende il nome del suo istituto — deposito di note
    # ex art. 127-ter c.p.c. — e da quello nascono i termini che il decreto
    # impone senza scriverne la data.
    fatti: list[Fatto] = qualifica_istituti(estrai_date(testo, origine=origine), testo, origine=origine)
    fatti.extend(estrai_domanda(testo, origine=origine, contesto=contesto))
    if con_notifiche:
        fatti.extend(estrai_prove_notifica(testo, origine=origine, nome=nome))
    if con_ruoli:
        fatti.extend(estrai_ruoli(testo, origine=origine))
    if con_importi:
        # Gli importi economici (contributo unificato, compenso liquidato, spese)
        # si leggono qui una volta sola: il presidio economico li consulta.
        fatti.extend(estrai_importi(testo, metadata={**(metadata or {}), "filename": nome}, origine=origine))
    collaudati = collauda_tutti(_senza_doppioni(fatti), contesto)
    from .pertinenza_documentale import applica_pertinenza

    collaudati = applica_pertinenza(collaudati, testo, contesto=contesto, origine=origine)
    if not any(f.campo == "natura_documentale" and f.valore == "precedente_giurisprudenziale" for f in collaudati):
        from .estrazione_economica import estrai_controllo_economico
        collaudati.extend(estrai_controllo_economico(testo, origine=origine, metadata=metadata or {}))
    collaudati.sort(key=lambda fatto: (ORDINE_VERIFICA.get(fatto.verifica, 9), fatto.posizione))
    return collaudati


__all__ = ["FATTI_MASSIMI", "VERSIONE_MOTORE_DOCUMENTI", "VERSIONI_MOTORE_DOCUMENTI_COMPATIBILI", "leggi_testo"]
