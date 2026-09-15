"""Le prove di notifica lette nel testo: relata, ricevute PEC, attestazione, atto notificato.

Notifica in proprio a mezzo PEC (L. 53/1994 art. 3-bis; art. 147 c.p.c.): la
relata è firmata dall'avvocato e cita la legge; la ricevuta di accettazione e
la ricevuta di avvenuta consegna sono generate dai gestori PEC (D.P.R.
68/2005) con intestazioni fisse; l'attestazione di conformità segue l'art.
16-undecies D.L. 179/2012; la comunicazione di cancelleria arriva ex art. 136
c.p.c. Ogni prova vale per forma: più segnali concordi, più fiducia.
"""

from __future__ import annotations

import re

from pct.registro_letture.fatti_repository import Fatto

# (campo, etichetta, espressioni; ognuna che combacia aggiunge fiducia)
PROVE: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("rac", "Ricevuta di accettazione", (r"ricevuta\s+di\s+accettazione", r"posta\s+certificata:\s*accettazione", r"accettazione:\s", r"il\s+messaggio\s+è\s+stato\s+accettato\s+dal\s+sistema")),
    ("rdac", "Ricevuta di avvenuta consegna", (r"ricevuta\s+di\s+avvenuta\s+consegna", r"posta\s+certificata:\s*consegna", r"avvenuta\s+consegna", r"il\s+messaggio\s+è\s+stato\s+consegnato")),
    ("relata", "Relata di notifica", (r"relata\s+di\s+notifica(?:zione)?", r"relazione\s+di\s+notifica(?:zione)?", r"art(?:icolo|\.)?\s*3[\s-]*bis", r"legge\s*(?:n\.?\s*)?53(?:/|\s+del\s+)(?:19)?94", r"l\.\s*53/(?:19)?94", r"ai\s+sensi\s+della\s+legge\s+21\s+gennaio\s+1994")),
    ("attestazione", "Attestazione di conformità", (r"attestazione\s+di\s+conformit", r"attest[oa]\s+(?:che\s+)?la\s+conformit", r"16[\s-]*(?:undecies|decies)", r"conforme\s+all'originale")),
    ("atto_notificato", "Atto notificato", (r"originale\s+notificato", r"copia\s+notificata", r"atto\s+notificato", r"notificato\s+a\s+mezzo\s+pec")),
    ("comunicazione_cancelleria", "Comunicazione di cancelleria", (r"comunicazione\s+di\s+cancelleria", r"biglietto\s+di\s+cancelleria", r"art(?:icolo|\.)?\s*136\s+c\.?\s*p\.?\s*c", r"si\s+comunica\s+(?:che|il|l')", r"cancelleria\s+(?:civile|del\s+tribunale)")),
    ("deposito_prova", "Deposito della prova di notifica", (r"deposito\s+(?:telematico\s+)?(?:della\s+)?(?:prova|relata)", r"ricevuta\s+di\s+accettazione\s+del\s+deposito", r"esito\s+controlli\s+automatici")),
)
_PROVE_RE = tuple((campo, etichetta, tuple(re.compile(espressione, re.IGNORECASE) for espressione in espressioni)) for campo, etichetta, espressioni in PROVE)
SEGNALI_PER_CERTEZZA = 2


def _brano(testo: str, posizione: int, raggio: int = 90) -> str:
    return " ".join(testo[max(0, posizione - raggio):posizione + raggio].split())


def estrai_prove_notifica(testo: str, *, origine: str, nome: str = "") -> list[Fatto]:
    """Le prove di notifica riconoscibili nel testo (e nel nome del file), una per tipo."""
    testo = str(testo or "")
    testata = " ".join((str(nome or ""), testo[:4000]))
    fatti: list[Fatto] = []
    for campo, etichetta, espressioni in _PROVE_RE:
        segnali: list[str] = []
        prima = -1
        for espressione in espressioni:
            match = espressione.search(testo) or espressione.search(testata)
            if match:
                segnali.append(" ".join(match.group(0).split()))
                if match.string is testo and (prima < 0 or match.start() < prima):
                    prima = match.start()
        if not segnali:
            continue
        posizione = prima if prima >= 0 else 0
        fatti.append(Fatto(
            categoria="prova_notifica", campo=campo, valore=campo, valore_letto=segnali[0][:120], etichetta=etichetta,
            contesto=_brano(testo, posizione) if prima >= 0 else f"Nome del documento: {nome}"[:300], posizione=posizione, origine=origine,
            confidenza=min(1.0, 0.45 + 0.25 * len(segnali)),
            prove=[{"codice": "segnali", "esito": "ok" if len(segnali) >= SEGNALI_PER_CERTEZZA else "attenzione", "dettaglio": "; ".join(segnali[:4])}],
        ))
    return fatti


__all__ = ["PROVE", "SEGNALI_PER_CERTEZZA", "estrai_prove_notifica"]
