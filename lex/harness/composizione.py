"""Passo 5 dell'harness: la risposta con lo schema fisso dell'avvocato.

Cosa ho capito · Conclusione · Come e perché (norme, competenza, procedibilità, rito) · Termini · Cosa fare ·
Dubbi e dati da completare · Norme applicate · Bozza (solo per le redazioni).
Il testo è composto dal codice con le affermazioni verificate: nessun modello linguistico aggiunge norme o fatti.
"""
from __future__ import annotations

from .controllo import EsitoControllo
from .modello import Analisi, Punto
from .norme import NORME, testo_norma


def _riga(p: Punto) -> str:
    citate = []
    for r in p.rif:
        n = NORME[r.chiave].citazione
        parti = n.split(" ", 2)
        if r.comma and len(parti) == 3:
            n = f"{parti[0]} {parti[1]}, comma {r.comma}, {parti[2]}"
        if n not in citate:
            citate.append(n)
    return f"- {p.testo}" + (f" ({'; '.join(citate)})" if citate else "")


def componi(domanda_tipo: str, a: Analisi, esito: EsitoControllo, domanda: str = "") -> str:
    righe: list[str] = []
    righe.append("**Cosa ho capito**")
    righe += [f"- {x}" for x in a.capito] or [f"- Domanda: «{' '.join(domanda.split())[:300]}»"]
    if a.conclusione:
        righe += ["", "**Conclusione**"] + [_riga(p) for p in a.conclusione]
    come = [("Inquadramento", a.inquadramento), ("Competenza e valore della causa", a.competenza),
            ("Condizioni di procedibilità", a.procedibilita), ("Rito", a.rito)]
    if any(lista for _, lista in come):
        righe += ["", "**Come e perché**"]
        for titolo, lista in come:
            if lista:
                righe.append(f"*{titolo}*")
                righe += [_riga(p) for p in lista]
    if a.termini:
        righe += ["", "**Termini**"] + [_riga(p) for p in a.termini]
    if a.cosa_fare:
        righe += ["", "**Cosa fare**"] + [f"{n}. {x}" for n, x in enumerate(a.cosa_fare, 1)]
    if a.dubbi:
        righe += ["", "**Dubbi e dati da completare**"] + [f"- {x}" for x in a.dubbi]
    if esito.norme_verificate:
        righe += ["", "**Norme applicate** (testo vigente letto dall'archivio Normattiva di IUSENTRA; ogni affermazione è "
                      "stata confrontata con le parole della norma)"]
        for chiave in esito.norme_verificate:
            t = testo_norma(chiave)
            n = NORME[chiave]
            agg = f", aggiornamento dell'archivio {t.aggiornamento}" if t and t.aggiornamento else ""
            righe.append(f"- {n.citazione} — {n.rubrica}{agg}" + (f": {t.url}" if t and t.url else ""))
    if a.bozza:
        righe += ["", "**Bozza dell'atto** (dal modello del catalogo" + (f" {a.modello}" if a.modello else "") +
                  "; i dati mancanti sono segnati «[da completare]»)", "",
                  # una riga vuota fra le righe: la chat rende il testo come markdown e unirebbe le righe semplici
                  "\n\n".join(r for r in a.bozza.splitlines() if r.strip())]
    if esito.citazioni_non_verificate:
        righe += ["", "Attenzione: questi riferimenti non sono stati verificati sull'archivio e vanno controllati prima "
                      "dell'uso: " + ", ".join(esito.citazioni_non_verificate) + "."]
    righe += ["", "_Risposta costruita passo per passo dall'harness di Lex (comprensione, fatti, norme vigenti, regole, "
                  "controlli). È un supporto all'avvocato: nessun atto è stato salvato, firmato, notificato o depositato._"]
    return "\n".join(righe)
