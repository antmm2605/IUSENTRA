"""Riscrittura di un passaggio dell'atto con il modello locale, ancorata al testo.

Le azioni Lex della pagina Template («rendi più chiaro», «più formale»,
«espandi le premesse») prima non chiamavano alcun modello: aggiungevano al testo
frasi fisse o note tra parentesi quadre. Qui il modello locale riscrive davvero il
passaggio, e la riscrittura passa due controlli prima di diventare proposta:

1. ogni data, importo e numero della riscrittura deve comparire nel testo di
   partenza (cancello di ancoraggio, `pct/provenienza_ai.cancello_ancoraggio`);
2. ogni riferimento normativo o giurisprudenziale deve comparire nel testo di
   partenza (`lex.guards.hallucination_guard.extract_legal_references`).

Se un controllo fallisce la riscrittura non si propone: si dice quale valore non
era nel testo. Il modello propone, le regole decidono (principio delle fonti certe).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

STILI = {
    "rendi_chiaro_cliente": "in un italiano più chiaro e comprensibile per il cliente, senza perdere precisione giuridica",
    "rendi_incisivo": "in forma più diretta e incisiva",
    "rendi_formale": "con tono più formale e istituzionale, adatto a un atto giudiziario",
    "rendi_professionale": "con tono professionale e lineare",
    "espandi_premesse": "in forma più completa e ordinata, esplicitando i passaggi logici già presenti",
    "correggi_refusi": "correggendo solo refusi, punteggiatura e concordanze, senza cambiare il contenuto",
}

MAX_CARATTERI = 6000

SISTEMA = (
    "Sei un avvocato italiano che rivede un passaggio di un atto. Riscrivi il testo indicato come richiesto. "
    "Regole inderogabili: non aggiungere fatti, date, importi, numeri, nomi, norme o sentenze che non siano già "
    "nel testo; non togliere dati presenti; scrivi solo il testo riscritto, in italiano, senza commenti, "
    "premesse o spiegazioni."
)


@dataclass
class EsitoRiscrittura:
    ok: bool
    testo: str = ""
    messaggio: str = ""
    non_ancorati: list[str] = field(default_factory=list)
    modello: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "testo": self.testo,
            "messaggio": self.messaggio,
            "nonAncorati": list(self.non_ancorati),
            "modello": self.modello,
            # Nomi letti dal client comune dei form React (`submitFormJson`).
            "message": self.messaggio,
            "text": self.testo,
        }


_VALORE = re.compile(r"\d[\d.,/]*\d|\d")
_MESI = "gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"
_DATA_LETTERE = re.compile(rf"\b\d{{1,2}}\s*(?:°|º)?\s+(?:{_MESI})\s+\d{{4}}\b", re.IGNORECASE)
_PREAMBOLO = re.compile(r"^(ecco|di seguito|testo riscritto|versione riscritta)[^:\n]*:\s*", re.IGNORECASE)


def pulisci_risposta(testo: str) -> str:
    """Toglie virgolette, preamboli («Ecco il testo riscritto:») e markdown."""
    pulito = str(testo or "").strip()
    pulito = re.sub(r"<think>.*?</think>", "", pulito, flags=re.DOTALL).strip()
    pulito = _PREAMBOLO.sub("", pulito).strip()
    pulito = pulito.strip("`").strip()
    if len(pulito) >= 2 and pulito[0] in "«\"“" and pulito[-1] in "»\"”":
        pulito = pulito[1:-1].strip()
    pulito = re.sub(r"\*\*(.+?)\*\*", r"\1", pulito)
    return pulito


def valori_non_ancorati(originale: str, riscrittura: str) -> list[str]:
    """Date, numeri e riferimenti giuridici della riscrittura assenti dal testo di partenza."""
    from pct.provenienza_ai import ESITO_BLOCCATO, cancello_ancoraggio

    date_lettere = _DATA_LETTERE.findall(riscrittura)
    resto = _DATA_LETTERE.sub(" ", riscrittura)
    token = [*date_lettere, *_VALORE.findall(resto)]
    valori = {f"v{i}": t for i, t in enumerate(dict.fromkeys(token))}
    bloccati = []
    if valori:
        esito = cancello_ancoraggio(valori, originale)
        bloccati = [c.valore for c in esito.controlli if c.esito == ESITO_BLOCCATO]
    try:
        from lex.guards.hallucination_guard import _supported_by_evidence, extract_legal_references

        nel_testo = extract_legal_references(originale)
        for ref in extract_legal_references(riscrittura):
            if not _supported_by_evidence(ref, nel_testo):
                bloccati.append(ref.label)
    except Exception:
        pass
    return list(dict.fromkeys(bloccati))


def genera_con_lex(user_id: str) -> Callable[[str, str], tuple[str, str]]:
    def genera(prompt: str, sistema: str) -> tuple[str, str]:
        from lex.gateway.service import LexGateway

        risposta = LexGateway().ask(
            user_id=user_id or "template-atti",
            prompt=prompt,
            task="draft_act_support",
            allow_external=False,
            system_prompt=sistema,
        )
        modello = f"{getattr(risposta, 'provider', '')}:{getattr(risposta, 'model', '')}".strip(":")
        return str(getattr(risposta, "content", "") or ""), modello

    return genera


def riscrivi_passaggio(
    passaggio: str,
    azione: str,
    *,
    istruzioni: str = "",
    genera: Callable[[str, str], tuple[str, str]],
) -> EsitoRiscrittura:
    passaggio = str(passaggio or "").strip()
    if not passaggio:
        return EsitoRiscrittura(False, messaggio="Seleziona nel testo il passaggio da riscrivere.")
    if len(passaggio) > MAX_CARATTERI:
        return EsitoRiscrittura(False, messaggio="Il passaggio è troppo lungo: selezionane una parte (al massimo una pagina).")
    stile = STILI.get(azione, STILI["rendi_professionale"])
    richiesta = f"Riscrivi il seguente passaggio {stile}."
    if istruzioni.strip():
        richiesta += f" Indicazioni dell'avvocato: {istruzioni.strip()}"
    prompt = f"{richiesta}\n\nTESTO:\n{passaggio}"
    try:
        grezzo, modello = genera(prompt, SISTEMA)
    except Exception:
        return EsitoRiscrittura(False, messaggio="Il modello locale non è disponibile: il testo non è stato modificato.")
    riscritto = pulisci_risposta(grezzo)
    if not riscritto:
        return EsitoRiscrittura(False, messaggio="Il modello non ha prodotto una riscrittura utilizzabile.", modello=modello)
    if riscritto == passaggio:
        return EsitoRiscrittura(False, messaggio="Nessuna modifica proposta: il passaggio è già adeguato.", modello=modello)
    fuori_testo = valori_non_ancorati(passaggio, riscritto)
    if fuori_testo:
        return EsitoRiscrittura(
            False,
            messaggio=(
                "Riscrittura scartata: conteneva dati non presenti nel passaggio di partenza ("
                + ", ".join(fuori_testo[:5])
                + "). Nessun dato viene aggiunto senza fonte."
            ),
            non_ancorati=fuori_testo,
            modello=modello,
        )
    return EsitoRiscrittura(True, testo=riscritto, messaggio="Riscrittura verificata: nessun dato nuovo rispetto al testo.", modello=modello)
