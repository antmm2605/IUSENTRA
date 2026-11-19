"""Harness di Lex: la domanda dell'avvocato passa sempre dai passi che consultano norme e regole.

1. comprensione — tipo di richiesta (redazione, parere, termine, norma, operativa), atto, racconto di fatti;
2. fatti — date, importi qualificati, parti e ruoli, luoghi, segnali giuridici, solo dal testo;
3. norme — testo vigente dall'archivio Normattiva del software (istantanea + lettura dal vivo);
4. regole — fattispecie e regole processuali deterministiche (valore, giudice, foro, procedibilità, rito, termini);
5. composizione — schema fisso: cosa ho capito, conclusione, come e perché, termini, cosa fare, dubbi, norme, bozza;
6. controllo — ogni affermazione confrontata con le parole della norma; ogni articolo citato deve esistere.

Le domande operative (scadenze, PEC, agenda, clienti dello studio) non passano di qui.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .comprensione import Comprensione, comprendi, e_richiesta_giuridica
from .composizione import componi
from .controllo import EsitoControllo, verifica_analisi, verifica_citazioni
from .fatti import leggi_fatti
from .fattispecie import scegli
from .norme import NORME, testo_norma

__all__ = ["RispostaHarness", "comprendi", "e_richiesta_giuridica", "rispondi"]


@dataclass
class RispostaHarness:
    testo: str
    tipo: str
    regola: str
    affidabilita: float
    fonti: list[dict[str, str]] = field(default_factory=list)
    norme_verificate: list[str] = field(default_factory=list)
    affermazioni_tolte: list[str] = field(default_factory=list)
    citazioni_non_verificate: list[str] = field(default_factory=list)
    bozza: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"answer": self.testo, "kind": self.tipo, "rule": self.regola, "confidence": self.affidabilita,
                "sources": self.fonti, "verified_norms": self.norme_verificate,
                "removed_claims": self.affermazioni_tolte, "unverified_citations": self.citazioni_non_verificate,
                "draft": self.bozza, "deterministic": True}


def _affidabilita(esito: EsitoControllo, punti: int) -> float:
    if punti == 0:
        return 0.3
    base = 0.92 - 0.12 * len(esito.affermazioni_tolte) - 0.08 * len(esito.citazioni_non_verificate)
    return round(max(0.3, min(0.95, base)), 2)


def risposta_norma(domanda: str) -> RispostaHarness | None:
    """Testo di un articolo del catalogo dall'istantanea dell'archivio: risposta immediata, senza ricerche."""
    from lex.testi_ufficiali import riconosci_articolo

    richiesta = riconosci_articolo(domanda)
    if richiesta is None:
        return None
    sigla = {"codice civile": "cc", "codice di procedura civile": "cpc", "codice penale": "cp",
             "codice di procedura penale": "cpp"}.get(richiesta.etichetta_atto)
    if not sigla:
        return None
    chiave = f"{sigla}:{richiesta.chiave}"
    t = testo_norma(chiave)
    if chiave not in NORME or t is None:
        return None
    agg = f" (aggiornamento dell'archivio {t.aggiornamento})" if t.aggiornamento else ""
    testo = "\n".join([f"**{NORME[chiave].citazione} — {NORME[chiave].rubrica}**: testo vigente dall'archivio Normattiva "
                       f"di IUSENTRA{agg}.", "", "> " + " ".join(t.testo.split()), "", f"Fonte ufficiale: {t.url}"])
    return RispostaHarness(testo, "norma", "testo_articolo", 0.95,
                           [{"title": f"Normattiva — {NORME[chiave].citazione}", "url": t.url}], [chiave])


def rispondi(domanda: str, *, oggi: date | None = None, comprensione: Comprensione | None = None) -> RispostaHarness | None:
    c = comprensione or comprendi(domanda)
    if not c.per_harness:
        return None
    if c.tipo == "norma":
        return risposta_norma(domanda)
    f = leggi_fatti(domanda, oggi=oggi)
    regola = scegli(c, f)
    if regola is None:
        return None
    analisi = regola[2](c, f)
    esito = verifica_analisi(analisi)
    testo = componi(c.tipo, analisi, esito, domanda)
    verifica_citazioni(testo, esito)
    if esito.citazioni_non_verificate:
        testo = componi(c.tipo, analisi, esito, domanda)
    fonti = []
    for chiave in esito.norme_verificate:
        t = testo_norma(chiave)
        if t and t.url:
            fonti.append({"title": f"Normattiva — {NORME[chiave].citazione}", "url": t.url})
    return RispostaHarness(testo, c.tipo, analisi.regola, _affidabilita(esito, len(analisi.punti())), fonti,
                           esito.norme_verificate, esito.affermazioni_tolte, esito.citazioni_non_verificate, analisi.bozza)
