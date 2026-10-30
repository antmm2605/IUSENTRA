"""Atti e istanze del processo di esecuzione oltre a precetto, pignoramento e vendita (c.p.c., libro III)."""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

_ESECUZIONE = r"\besecuz\w+\b|\bpignora\w+\b|\bprocedura\s+esecutiva\b|\bgiudice\s+dell.?\s*esecuzione\b|\bcreditor\w+\b"


def _atto(id: str, titolo: str, conferma: str, label: str, evidence: str, *, role: str = "istanza",
          section: str = "atti", tipo: TipoDocumento = TipoDocumento.MEMORIA, deposit_role: str = "atto_principale",
          deposit_candidate: bool = True, fonte: str = "normattiva_cpc"):
    return regola(id, titolo, conferma, label, role=role, section=section, tipo=tipo, fonte=fonte,
                  deposit_role=deposit_role, deposit_candidate=deposit_candidate, evidence=evidence)


REGOLE = (
    _atto(
        "dichiarazione_terzo_pignorato",
        r"dichiarazione\s+(?:del\s+terzo(?:\s+pignorato)?|ex\s+art\.?\s*547(?:\s+c\.?\s*p\.?\s*c\.?)?|ai\s+sensi\s+dell.?\s*art\.?\s*547.*)(?:\s+.*)?|"
        r"dichiarazione\s+(?:ex\s+)?(?:art\.?\s*)?553\s+c\.?\s*p\.?\s*c\.?(?:\s+.*)?",
        r"\bterzo\b|\bpignorat\w+\b|\bdebitor\w+\b|\bsomme\b|\b547\b",
        "Dichiarazione del terzo pignorato",
        "titolo della dichiarazione e somme dovute al debitore (art. 547 c.p.c.)",
        role="atto_esecutivo", section="allegati", tipo=TipoDocumento.ALLEGATO, deposit_role="allegato",
    ),
    _atto(
        "contestazione_dichiarazione_terzo",
        r"contestazione\s+della\s+dichiarazione\s+del\s+terzo(?:\s+.*)?|istanza\s+di\s+accertamento\s+dell.?\s*obbligo\s+del\s+terzo(?:\s+.*)?",
        r"\bterzo\b|\bdichiarazion\w+\b|\b549\b",
        "Contestazione della dichiarazione del terzo",
        "titolo dell'atto e accertamento dell'obbligo del terzo (art. 549 c.p.c.)",
    ),
    _atto(
        "precisazione_credito",
        r"(?:nota\s+di\s+)?precisazione\s+(?:del\s+)?credit[oi](?:\s+.*)?|aggiornamento\s+del\s+conteggio\s+del\s+credito(?:\s+.*)?",
        r"\bcredit\w+\b|\binteress\w+\b|\bspese\b|\bcapitale\b",
        "Precisazione del credito",
        "titolo della nota e credito per cui si procede (artt. 566 e 596 c.p.c.)",
    ),
    _atto(
        "osservazioni_progetto_distribuzione",
        r"osservazioni\s+(?:al\s+)?(?:progetto\s+di\s+(?:distribuzione|riparto)|piano\s+di\s+riparto)(?:\s+.*)?|contestazioni\s+al\s+progetto\s+di\s+distribuzione(?:\s+.*)?",
        r"\bdistribuzion\w+\b|\bripart\w+\b|\bcreditor\w+\b|\bgraduazion\w+\b",
        "Osservazioni al progetto di distribuzione",
        "titolo dell'atto e contestazione del riparto (artt. 512 e 598 c.p.c.)",
    ),
    _atto(
        "reclamo_giudice_esecuzione",
        r"reclamo\s+(?:contro|avverso)\s+(?:il\s+)?(?:provvedimento|atti)\s+(?:del\s+)?(?:g\.?\s*e\.?|giudice\s+dell.?\s*esecuzione|professionista\s+delegato)(?:\s+.*)?|"
        r"reclamo\s+ex\s+art\.?\s*(?:591-?ter|630)(?:\s+.*)?",
        _ESECUZIONE + r"|\bdelegat\w+\b",
        "Reclamo contro un provvedimento dell'esecuzione",
        "titolo del reclamo e atto del giudice o del delegato (artt. 591-ter e 630 c.p.c.)",
    ),
    _atto(
        "rinuncia_atti_esecutivi",
        r"rinuncia\s+agli\s+atti\s+(?:esecutivi|della\s+procedura\s+esecutiva|dell.?\s*esecuzione)(?:\s+.*)?",
        _ESECUZIONE,
        "Rinuncia agli atti esecutivi",
        "titolo della rinuncia ed estinzione dell'esecuzione (art. 629 c.p.c.)",
    ),
    _atto(
        "opposizione_terzo_esecuzione",
        r"opposizione\s+di\s+terzo\s+all.?\s*esecuzione(?:\s+.*)?|opposizione\s+(?:di\s+terzo\s+)?ex\s+art\.?\s*619(?:\s+.*)?",
        r"\bterzo\b|\bpropriet\w+\b|\bpignorat\w+\b|\bben[ei]\b",
        "Opposizione di terzo all'esecuzione",
        "titolo dell'opposizione e diritto del terzo sui beni pignorati (art. 619 c.p.c.)",
        role="atto_principale", tipo=TipoDocumento.RICORSO,
    ),
    _atto(
        "istanza_ricerca_beni",
        r"istanza\s+(?:di|per\s+la)\s+ricerca\s+(?:telematica\s+)?dei\s+beni(?:\s+(?:da\s+pignorare|con\s+modalit[aà]\s+telematiche))?(?:\s+.*)?|istanza\s+ex\s+art\.?\s*492-?bis(?:\s+.*)?",
        r"\bricerc\w+\b|\banagrafe\s+tributaria\b|\bbanche\s+dati\b|\b492-?bis\b|\bpignora\w+\b",
        "Istanza di ricerca telematica dei beni",
        "titolo dell'istanza e ricerca dei beni da pignorare (art. 492-bis c.p.c.)",
    ),
    _atto(
        "istanza_conversione_pignoramento",
        r"istanza\s+di\s+conversione\s+del\s+pignoramento(?:\s+.*)?",
        r"\bconversion\w+\b|\bsomm\w+\b|\bpignora\w+\b|\b495\b",
        "Istanza di conversione del pignoramento",
        "titolo dell'istanza e somma sostitutiva dei beni pignorati (art. 495 c.p.c.)",
    ),
    _atto(
        "istanza_riduzione_pignoramento",
        r"istanza\s+di\s+riduzione\s+del\s+pignoramento(?:\s+.*)?",
        r"\briduzion\w+\b|\bpignora\w+\b|\bvalore\b|\b496\b",
        "Istanza di riduzione del pignoramento",
        "titolo dell'istanza e valore dei beni eccedente il credito (art. 496 c.p.c.)",
    ),
    _atto(
        "istanza_assegnazione",
        r"istanza\s+di\s+assegnazione(?:\s+(?:delle\s+)?(?:somme|crediti|del\s+bene))?(?:\s+.*)?",
        r"\bassegna\w+\b|\bpignora\w+\b|\bterzo\b|\bcredit\w+\b",
        "Istanza di assegnazione",
        "titolo dell'istanza e assegnazione di somme o beni pignorati (artt. 552, 553 e 589 c.p.c.)",
    ),
    _atto(
        "istanza_custode",
        r"istanza\s+di\s+(?:nomina|sostituzione|revoca)\s+del\s+custode(?:\s+.*)?",
        r"\bcustod\w+\b|\bimmobil\w+\b|\bpignora\w+\b",
        "Istanza relativa al custode dei beni pignorati",
        "titolo dell'istanza e custodia dei beni pignorati (artt. 559 e 560 c.p.c.)",
    ),
    _atto(
        "istanza_liberazione_immobile",
        r"istanza\s+(?:di|per\s+la)\s+liberazione\s+dell.?\s*immobile(?:\s+.*)?|istanza\s+(?:di\s+emissione\s+)?dell.?\s*ordine\s+di\s+liberazione(?:\s+.*)?",
        r"\bliberazion\w+\b|\bimmobil\w+\b|\bcustod\w+\b|\baggiudicat\w+\b",
        "Istanza di liberazione dell'immobile",
        "titolo dell'istanza e ordine di liberazione (art. 560 c.p.c.)",
    ),
    _atto(
        "istanza_sospensione_esecuzione",
        r"istanza\s+di\s+sospensione\s+(?:dell.?\s*esecuzione|della\s+procedura\s+esecutiva)(?!\s+dell.?\s*atto)(?:\s+.*)?",
        _ESECUZIONE + r"|\bsospension\w+\b",
        "Istanza di sospensione dell'esecuzione",
        "titolo dell'istanza e gravi motivi di sospensione (artt. 624 e 624-bis c.p.c.)",
    ),
)

__all__ = ["REGOLE"]
