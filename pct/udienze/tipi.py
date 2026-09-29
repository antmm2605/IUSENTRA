"""Tipi di udienza civile e verifiche da fare prima, ciascuna legata alla sua norma.

Le norme citate sono quelle del registro verificato ``pct/procedura_fasi/fonti.py`` (testo
vigente su Normattiva, con estratto): la verifica mostra all'avvocato l'estratto e il link.
Le verifiche senza norma sono puramente operative e lo dicono (``fonte`` vuota).
"""

from __future__ import annotations

from typing import Any

from pct.procedura_fasi.fonti import FONTI

TIPI: dict[str, dict[str, Any]] = {
    "prima_comparizione": {
        "etichetta": "Prima comparizione e trattazione (art. 183 c.p.c.)",
        "verifiche": [
            ("comparizione_cliente", "Il cliente sa che deve comparire personalmente e ha confermato la presenza", "cpc_183"),
            ("memorie_171ter", "Memorie integrative depositate nei termini (40, 20 e 10 giorni prima dell'udienza)", "cpc_171ter"),
            ("giustificato_motivo", "Se il cliente non può venire: giustificato motivo documentato da produrre in udienza", "cpc_183"),
        ],
    },
    "istruttoria": {
        "etichetta": "Udienza istruttoria (assunzione delle prove)",
        "verifiche": [
            ("testimoni", "Testimoni ammessi intimati e reperibili; capitoli di prova pronti", ""),
            ("originali", "Documenti in originale da esibire, se richiesti", ""),
        ],
    },
    "precisazione_conclusioni": {
        "etichetta": "Rimessione in decisione (art. 189 c.p.c.)",
        "verifiche": [
            ("note_conclusioni", "Note di precisazione delle conclusioni depositate nel termine assegnato", "cpc_189"),
            ("calendario_scritti", "Termini per comparse conclusionali e memorie di replica annotati nello scadenziario", "cpc_189"),
        ],
    },
    "cartolare": {
        "etichetta": "Udienza sostituita da note scritte (art. 127-ter c.p.c.)",
        "verifiche": [
            ("note_scritte", "Note scritte depositate entro il termine assegnato: la scadenza vale come data d'udienza", "cpc_127ter"),
        ],
        "senza_presenza": True,
    },
    "altra": {
        "etichetta": "Altra udienza (discussione, comparizione, rinvio)",
        "verifiche": [],
    },
}

AVVISO_ASSENZA = ("cpc_309", "Se nessuna parte compare, il giudice fissa una nuova udienza; se nessuno compare nemmeno a quella, "
                  "la causa è cancellata dal ruolo e il processo si estingue.")


def fonte(chiave: str) -> dict[str, str]:
    voce = FONTI.get(chiave) or {}
    return {"norma": str(voce.get("norma") or ""), "estratto": str(voce.get("estratto") or ""), "url": str(voce.get("url") or "")} if voce else {}


def catalogo() -> list[dict[str, Any]]:
    return [{"value": chiave, "label": tipo["etichetta"], "senzaPresenza": bool(tipo.get("senza_presenza"))} for chiave, tipo in TIPI.items()]


def verifiche(tipo: str, fatte: dict[str, bool]) -> list[dict[str, Any]]:
    return [{"id": chiave, "testo": testo, "fatta": bool(fatte.get(chiave)), "fonte": fonte(norma) if norma else {}}
            for chiave, testo, norma in TIPI.get(tipo, {}).get("verifiche", [])]


__all__ = ["AVVISO_ASSENZA", "TIPI", "catalogo", "fonte", "verifiche"]
