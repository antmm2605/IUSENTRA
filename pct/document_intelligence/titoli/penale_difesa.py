"""Atti della difesa e della parte civile nel processo penale oltre a quelli di `penale` (c.p.p.)."""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

_PROCESSO = r"\bimputat\w+\b|\bindagat\w+\b|\bprocediment\w+\b|\br\.?\s*g\.?\s*n\.?\s*r\.?\b|\bpubblico\s+ministero\b|\breat\w+\b"


def _atto(id: str, titolo: str, conferma: str, label: str, evidence: str, *, role: str = "istanza",
          tipo: TipoDocumento = TipoDocumento.MEMORIA, section: str = "atti", fonte: str = "normattiva_cpp",
          deposit_role: str = "atto_principale"):
    return regola(id, titolo, conferma, label, role=role, section=section, tipo=tipo, fonte=fonte,
                  deposit_role=deposit_role, evidence=evidence)


REGOLE = (
    _atto(
        "costituzione_parte_civile",
        r"(?:atto\s+di\s+|dichiarazione\s+di\s+)?costituzione\s+(?:di\s+)?parte\s+civile(?:\s+.*)?",
        r"\bparte\s+civile\b|\brisarciment\w+\b|\bdanneggiat\w+\b|\b7[68]\b",
        "Costituzione di parte civile",
        "titolo dell'atto e domanda risarcitoria nel processo penale (artt. 76 e 78 c.p.p.)",
        role="atto_principale",
    ),
    _atto(
        "remissione_querela",
        r"(?:atto\s+di\s+|dichiarazione\s+di\s+)?remissione\s+(?:di|della)\s+querela(?:\s+.*)?|accettazione\s+(?:della\s+)?remissione\s+di\s+querela(?:\s+.*)?",
        r"\bquerel\w+\b|\bremission\w+\b|\bremett\w+\b|\b152\b|\b340\b",
        "Remissione di querela",
        "titolo dell'atto ed estinzione del reato per remissione (art. 152 c.p.; art. 340 c.p.p.)",
    ),
    _atto(
        "istanza_dissequestro",
        r"istanza\s+di\s+(?:dissequestro|restituzione\s+(?:di\s+|dei\s+)?(?:beni|cose)\s+sequestrat[ei])(?:\s+.*)?|richiesta\s+di\s+dissequestro(?:\s+.*)?",
        r"\bsequestr\w+\b|\brestituzion\w+\b|\b26[23]\b",
        "Istanza di dissequestro e restituzione",
        "titolo dell'istanza e cose sequestrate da restituire (artt. 262 e 263 c.p.p.)",
    ),
    _atto(
        "istanza_misura_cautelare",
        r"istanza\s+di\s+(?:revoca|sostituzione|revoca\s+o\s+sostituzione)\s+(?:della\s+|di\s+)?misur[ae]\s+cautelar[ei](?:\s+.*)?",
        r"\bmisur\w+\s+cautelar\w+\b|\besigenze\s+cautelari\b|\b299\b|\bcustodia\b|\barresti\s+domiciliari\b",
        "Istanza di revoca o sostituzione della misura cautelare",
        "titolo dell'istanza ed esigenze cautelari venute meno (art. 299 c.p.p.)",
    ),
    _atto(
        "istanza_legittimo_impedimento",
        r"istanza\s+(?:di\s+rinvio\s+)?(?:per\s+)?legittimo\s+impedimento(?:\s+.*)?|comunicazione\s+di\s+legittimo\s+impedimento(?:\s+.*)?",
        r"\bimpediment\w+\b|\budienz\w+\b|\brinvi\w+\b|\b420-?ter\b",
        "Istanza di rinvio per legittimo impedimento",
        "titolo dell'istanza e impedimento a comparire (art. 420-ter c.p.p.)",
    ),
    _atto(
        "istanza_copie_atti",
        r"(?:istanza|richiesta)\s+(?:di\s+)?(?:rilascio\s+(?:di\s+)?)?copi[ae](?:\s+(?:degli\s+)?atti)?(?:\s+.*)?",
        r"\bcopi\w+\b|\batti\b|\bfascicol\w+\b|\b116\b|\bcancelleri\w+\b|\bsegreteri\w+\b",
        "Istanza di rilascio di copie",
        "titolo dell'istanza e atti del procedimento richiesti (art. 116 c.p.p.; art. 76 disp. att. c.p.c.)",
    ),
    _atto(
        "incidente_probatorio",
        r"(?:istanza|richiesta)\s+(?:di\s+)?incidente\s+probatorio(?:\s+.*)?",
        r"\bincidente\s+probatorio\b|\b39[2-8]\b|\bprova\b|\bassunzion\w+\b",
        "Richiesta di incidente probatorio",
        "titolo della richiesta e prova non rinviabile al dibattimento (artt. 392 e 393 c.p.p.)",
    ),
    _atto(
        "istanza_misure_alternative",
        r"istanza\s+(?:per|di)\s+(?:l.?\s*)?(?:applicazione\s+di\s+)?misure\s+alternative(?:\s+alla\s+detenzione)?(?:\s+.*)?|"
        r"istanza\s+di\s+sospensione\s+dell.?\s*ordine\s+di\s+esecuzione(?:\s+.*)?|istanza\s+di\s+affidamento\s+in\s+prova(?:\s+.*)?",
        r"\bmisur\w+\s+alternativ\w+\b|\baffidamento\s+in\s+prova\b|\bdetenzione\s+domiciliare\b|\bordine\s+di\s+esecuzione\b|\bsorveglianz\w+\b|\b656\b",
        "Istanza di misure alternative alla detenzione",
        "titolo dell'istanza e sospensione dell'ordine di esecuzione (art. 656, quinto comma, c.p.p.)",
    ),
    _atto(
        "eccezioni_preliminari_penali",
        r"(?:memoria\s+(?:con\s+)?)?eccezioni\s+preliminari(?:\s+.*)?|questioni\s+preliminari(?:\s+.*)?",
        _PROCESSO + r"|\bnullit\w+\b|\b491\b",
        "Eccezioni preliminari",
        "titolo dell'atto e questioni preliminari al dibattimento (art. 491 c.p.p.)",
        role="atto_difensivo",
    ),
    _atto(
        "istanza_pubblico_ministero",
        r"istanza\s+al\s+pubblico\s+ministero(?:\s+.*)?|istanza\s+(?:generica\s+)?penale(?:\s+.*)?",
        _PROCESSO,
        "Istanza nel procedimento penale",
        "titolo dell'istanza e facoltà della difesa nel procedimento (art. 121 c.p.p.)",
    ),
)

__all__ = ["REGOLE"]
