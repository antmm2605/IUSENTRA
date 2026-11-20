"""Che cosa decorre dalla notifica della sentenza: termine breve, passaggio in giudicato, art. 14 D.L. 669/1996.

Norme (testi vigenti verificati il 10/11/2026 nell'archivio Normattiva del software e su normattiva.it):

- **termine breve**: art. 325 c.p.c., 30 giorni dalla notificazione per l'appello (60 per la
  cassazione); art. 326 c.p.c., decorre dalla notificazione anche per la parte che notifica; nel rito
  del lavoro l'appello si propone con ricorso depositato entro 30 giorni dalla notificazione (art. 434,
  secondo comma, c.p.c.). La sospensione feriale non si applica alle controversie di lavoro e previdenza
  (art. 3 L. 742/1969, che richiama gli artt. 429 e 459 c.p.c.); negli altri casi si applica (art. 1);
- **passaggio in giudicato**: art. 324 c.p.c., la sentenza non più soggetta ad appello (né agli altri
  mezzi ordinari) passa in giudicato; scaduto il termine breve senza impugnazione, il giorno successivo.
  Resta da verificare in cancelleria che non sia stata proposta impugnazione (art. 124 disp. att. c.p.c.);
- **esecuzione contro la P.A.**: art. 14, comma 1, D.L. 669/1996 (conv. L. 30/1997), le amministrazioni
  dello Stato e gli enti pubblici non economici completano il pagamento delle somme dovute per
  provvedimenti giurisdizionali entro 120 giorni dalla notificazione del titolo esecutivo; prima il
  creditore non può notificare il precetto né procedere ad esecuzione. La sentenza di primo grado è
  esecutiva per legge (art. 282 c.p.c.; nel lavoro art. 431 c.p.c.).

Modulo puro: riceve la data della notifica e i dati della causa, restituisce i calcoli con la norma.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from pct.termini_processuali import ItalianDeadlineCalculator

NORMA_BREVE = "artt. 325 e 326 c.p.c."
NORMA_BREVE_LAVORO = "artt. 325, 326 e 434, secondo comma, c.p.c.; art. 3 L. 742/1969"
NORMA_GIUDICATO = "art. 324 c.p.c."
NORMA_ESECUZIONE_PA = "art. 14, comma 1, D.L. 669/1996 (conv. L. 30/1997)"
GIORNI_ESECUZIONE_PA = 120

# Il dispositivo che condanna a pagare una somma (capitale o spese): c'è un titolo per somme di denaro.
_DISPOSITIVO = re.compile(r"\bP\.?\s*Q\.?\s*M\.?\b|\bper\s+questi\s+motivi\b", re.IGNORECASE)
_CONDANNA_PAGAMENTO = re.compile(
    r"\bcondann\w*\b[^;]{0,400}?\b(?:al\s+pagamento|a\s+pagare|alla\s+rifusione|al\s+rimborso|alla\s+corresponsione)\b",
    re.IGNORECASE | re.DOTALL,
)


def condanna_al_pagamento(testo: str) -> bool:
    """Vero se il dispositivo condanna al pagamento di somme (anche solo delle spese di lite)."""
    testo = str(testo or "")
    inizio = _DISPOSITIVO.search(testo)
    return bool(_CONDANNA_PAGAMENTO.search(testo[inizio.start():] if inizio else testo[-4000:]))


def _giorno(valore: Any) -> date | None:
    try:
        return date.fromisoformat(str(valore or "")[:10])
    except ValueError:
        return None


def _it(giorno: date) -> str:
    return giorno.strftime("%d/%m/%Y")


def termini_dalla_notifica(data_notifica: str, *, lavoro: bool, contro_pa: bool, condanna: bool,
                           oggi: date | None = None, esclusione_feriale: str = "") -> list[dict[str, Any]]:
    """I calcoli che nascono dalla notifica della sentenza, in ordine di data.

    ``esclusione_feriale``: il motivo per cui la materia è esclusa dalla sospensione feriale (art. 3 L. 742/1969 e
    art. 92 R.D. 12/1941, `pct/ragionamento/feriale.py`); il lavoro è sempre escluso.
    """
    base = _giorno(data_notifica)
    if base is None:
        return []
    sospende = not lavoro and not esclusione_feriale
    calcolatore = ItalianDeadlineCalculator()
    breve = calcolatore.calculate(
        base, 30, direction="forward", period_type="days", suspend_august=sospende,
        ferial_suspension_policy="applies" if sospende else "not_applicable",
        reference_law=NORMA_BREVE_LAVORO if lavoro else NORMA_BREVE, template_code="sentenza_notificata:termine_breve",
    )
    scade = _giorno(breve.get("deadline")) or base + timedelta(days=30)
    feriale = ("senza sospensione feriale (controversia di lavoro, art. 3 L. 742/1969)" if lavoro
               else f"senza sospensione feriale ({esclusione_feriale})" if esclusione_feriale
               else "con la sospensione feriale dal 1° al 31 agosto (art. 1 L. 742/1969)")
    calcoli = [{
        **breve,
        "codice": "termine_breve_impugnazione",
        "etichetta": "Termine breve per l'appello",
        "formula": (f"30 giorni dalla notifica della sentenza del {_it(base)}, {feriale}: "
                    f"{'ricorso in appello depositato' if lavoro else 'atto di appello notificato'} entro il {_it(scade)}."),
        "evento_base": "notifica_sentenza",
        "norma": NORMA_BREVE_LAVORO if lavoro else NORMA_BREVE,
    }, {
        "codice": "passaggio_in_giudicato",
        "etichetta": "Passaggio in giudicato",
        "deadline": (scade + timedelta(days=1)).isoformat(),
        "formula": (f"Senza appello entro il {_it(scade)} la sentenza passa in giudicato dal {_it(scade + timedelta(days=1))}: "
                    "verificare in cancelleria che non sia stata impugnata (art. 124 disp. att. c.p.c.)."),
        "evento_base": "termine_breve_impugnazione",
        "norma": NORMA_GIUDICATO,
    }]
    if contro_pa and condanna:
        fine = base + timedelta(days=GIORNI_ESECUZIONE_PA)
        calcoli.append({
            "codice": "esecuzione_pa_120_giorni",
            "etichetta": "Pagamento dell'amministrazione (120 giorni)",
            "deadline": fine.isoformat(),
            "formula": (f"L'amministrazione paga entro 120 giorni dalla notifica del titolo ({_it(base)}), cioè entro il {_it(fine)}; "
                        f"prima il precetto non si notifica: dal {_it(fine + timedelta(days=1))} richiesta di pagamento o precetto."),
            "evento_base": "notifica_sentenza",
            "norma": NORMA_ESECUZIONE_PA,
            "precetto_dal": (fine + timedelta(days=1)).isoformat(),
        })
    if oggi:
        for calcolo in calcoli:
            calcolo["decorso"] = str(calcolo.get("deadline") or "") < oggi.isoformat()
    return calcoli


__all__ = ["GIORNI_ESECUZIONE_PA", "NORMA_BREVE", "NORMA_BREVE_LAVORO", "NORMA_ESECUZIONE_PA", "NORMA_GIUDICATO",
           "condanna_al_pagamento", "termini_dalla_notifica"]
