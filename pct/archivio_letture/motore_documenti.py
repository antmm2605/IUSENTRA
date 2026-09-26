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
from .estrazione_importi import VERSIONE_ESTRAZIONE_IMPORTI, estrai_importi
from .estrazione_istituti import VERSIONE_ESTRAZIONE_ISTITUTI
from .estrazione_notifiche import estrai_prove_notifica
from .estrazione_parti import VERSIONE_ESTRAZIONE_PARTI
from .estrazione_ruolo import estrai_ruoli
from .estrazione_tabelle import VERSIONE_ESTRAZIONE_TABELLE

VERSIONE_MOTORE_DOCUMENTI_V13 = f"2026.09.21.motore-documenti.v13+modalita-note-scritte+ciclo-fermo+fatti-obsoleti+importi:{VERSIONE_ESTRAZIONE_IMPORTI}+istituti:{VERSIONE_ESTRAZIONE_ISTITUTI}+{VERSIONE_FORMULARIO}"
VERSIONE_MOTORE_DOCUMENTI_V14 = f"2026.09.23.motore-documenti.v14+ufficio-rg+modalita-note-scritte+ciclo-fermo+fatti-obsoleti+importi:{VERSIONE_ESTRAZIONE_IMPORTI}+istituti:{VERSIONE_ESTRAZIONE_ISTITUTI}+{VERSIONE_FORMULARIO}"
# v15: le parti dell'epigrafe e il ruolo amministrativo (REG.RIC.). Le versioni
# precedenti non sono compatibili: ogni documento si rilegge una volta per
# alimentare le parti del fascicolo.
VERSIONE_MOTORE_DOCUMENTI_V15 = f"2026.09.26.motore-documenti.v15+parti:{VERSIONE_ESTRAZIONE_PARTI}+ruolo-amministrativo+ufficio-rg+modalita-note-scritte+ciclo-fermo+fatti-obsoleti+importi:{VERSIONE_ESTRAZIONE_IMPORTI}+istituti:{VERSIONE_ESTRAZIONE_ISTITUTI}+{VERSIONE_FORMULARIO}"
# v16: i prospetti a tabella (voci, importi, prova dei conti). Si rilegge una
# volta dal testo già indicizzato: nessuna nuova estrazione dai PDF.
VERSIONE_MOTORE_DOCUMENTI = f"2026.09.26.motore-documenti.v16+tabelle:{VERSIONE_ESTRAZIONE_TABELLE}+parti:{VERSIONE_ESTRAZIONE_PARTI}+ruolo-amministrativo+ufficio-rg+modalita-note-scritte+ciclo-fermo+fatti-obsoleti+importi:{VERSIONE_ESTRAZIONE_IMPORTI}+istituti:{VERSIONE_ESTRAZIONE_ISTITUTI}+{VERSIONE_FORMULARIO}"
VERSIONI_MOTORE_DOCUMENTI_COMPATIBILI = (VERSIONE_MOTORE_DOCUMENTI,)
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
        # I prospetti a tabella: ogni importo resta con la sua voce, e i conti si rifanno.
        from .estrazione_tabelle import fatti_prospetti

        fatti.extend(fatti_prospetti(testo, origine=origine))
    collaudati = collauda_tutti(_senza_doppioni(fatti), contesto)
    from .pertinenza_documentale import applica_pertinenza

    collaudati = applica_pertinenza(collaudati, testo, contesto=contesto, origine=origine)
    if not any(f.campo == "natura_documentale" and f.valore == "precedente_giurisprudenziale" for f in collaudati):
        from .estrazione_economica import estrai_controllo_economico
        from .estrazione_parti import fatti_parti
        collaudati.extend(estrai_controllo_economico(testo, origine=origine, metadata=metadata or {}))
        # Le parti si leggono solo negli atti di questa causa: un precedente
        # allegato porta le parti di un altro processo.
        collaudati.extend(collauda_tutti(fatti_parti(testo, origine=origine, avvocati_studio=list(contesto.avvocati_studio), cliente=contesto.cliente), contesto))
    collaudati.sort(key=lambda fatto: (ORDINE_VERIFICA.get(fatto.verifica, 9), fatto.posizione))
    return collaudati


__all__ = ["FATTI_MASSIMI", "VERSIONE_MOTORE_DOCUMENTI", "VERSIONI_MOTORE_DOCUMENTI_COMPATIBILI", "leggi_testo"]
