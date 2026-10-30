"""Istanze del processo civile di cognizione e cautelare (c.p.c.).

Ognuna è un tipo di atto con un fondamento proprio nel codice di rito: senza
queste regole la regola generica le leggeva tutte come «Istanza», e né Lex né
il modello addestrato potevano distinguerle. Vengono prima delle regole
generiche, che restano per le istanze senza un nome codificato.
"""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

_CHIEDE = r"\bchied\w+\b|\bvoglia\b|\bdispor\w+\b|\bconceder\w+\b"


def _istanza(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str = "normattiva_cpc"):
    return regola(
        id, titolo, conferma, label,
        role="istanza", section="atti", tipo=TipoDocumento.MEMORIA,
        fonte=fonte, deposit_role="atto_principale", evidence=evidence,
    )


REGOLE = (
    _istanza(
        "istanza_rinvio_udienza",
        r"istanza\s+di\s+(?:rinvio|differimento)(?:\s+(?:dell.?\s*|della\s+)?udienza)?(?:\s+.*)?",
        r"\budienz\w+\b|\brinvi\w+\b|\bdifferiment\w+\b",
        "Istanza di rinvio dell'udienza",
        "titolo dell'istanza e udienza da differire (art. 175 c.p.c., art. 420-ter c.p.p.)",
    ),
    _istanza(
        "istanza_anticipazione_udienza",
        r"istanza\s+di\s+anticipazione(?:\s+(?:dell.?\s*|della\s+)?udienza)?(?:\s+.*)?",
        r"\budienz\w+\b|\banticipa\w+\b",
        "Istanza di anticipazione dell'udienza",
        "titolo dell'istanza e udienza da anticipare (art. 163-bis, terzo comma, c.p.c.)",
    ),
    _istanza(
        "istanza_provvisoria_esecuzione",
        r"istanza\s+di\s+(?:concessione\s+(?:o\s+revoca\s+)?(?:della\s+)?)?provvisoria\s+esecu(?:zione|torieta|torietà)(?:\s+.*)?",
        r"\bprovvisori\w+\s+esecu\w+\b|\bdecreto\s+ingiuntiv\w+\b|\bsentenz\w+\b|\bgrave\s+pregiudizio\b",
        "Istanza di provvisoria esecuzione",
        "titolo dell'istanza e provvisoria esecuzione del titolo (artt. 648 e 642 c.p.c.)",
    ),
    _istanza(
        "istanza_sospensione_esecutivita",
        r"istanza\s+di\s+sospensione\s+(?:dell.?\s*)?(?:esecutivit[aà]|esecutoriet[aà]|efficacia\s+esecutiva)(?:\s+.*)?",
        r"\bsospension\w+\b|\besecutiv\w+\b|\besecutori\w+\b|\bgravi\s+(?:e\s+fondati\s+)?motivi\b",
        "Istanza di sospensione dell'esecutività",
        "titolo dell'istanza e gravi motivi di sospensione (artt. 283, 351, 373 e 649 c.p.c.)",
    ),
    _istanza(
        "istanza_formula_esecutiva",
        r"istanza\s+(?:di|per\s+la)\s+(?:concessione|apposizione|rilascio)\s+(?:della\s+)?formula\s+esecutiva(?:\s+.*)?|"
        r"istanza\s+di\s+rilascio\s+(?:di\s+)?copia\s+esecutiva(?:\s+.*)?",
        r"\bformula\s+esecutiva\b|\bcopia\s+(?:esecutiva|attestata)\b|\btitolo\s+esecutivo\b|\bdecreto\s+ingiuntivo\b",
        "Istanza di rilascio della formula esecutiva",
        "titolo dell'istanza e spedizione del titolo in forma esecutiva (artt. 475 e 654 c.p.c.)",
    ),
    _istanza(
        "istanza_ctu",
        r"istanza\s+(?:di|per\s+la)\s+(?:nomina\s+(?:del\s+)?)?(?:ctu|c\.t\.u\.|consulen(?:za|te)\s+tecnic[ao](?:\s+d.?\s*ufficio)?)(?:\s+.*)?|"
        r"istanza\s+di\s+sostituzione\s+(?:del\s+)?(?:ctu|c\.t\.u\.|consulente\s+tecnico)(?:\s+.*)?",
        r"\bctu\b|\bconsulen\w+\s+tecnic\w+\b|\bperit\w+\b|\baccertament\w+\b",
        "Istanza di consulenza tecnica d'ufficio",
        "titolo dell'istanza e consulenza tecnica (artt. 61, 191 e 196 c.p.c.)",
    ),
    _istanza(
        "istanza_ordine_esibizione",
        r"istanza\s+(?:di|per)\s+(?:l.?\s*)?ordine\s+di\s+esibizione(?:\s+.*)?|istanza\s+ex\s+art\.?\s*210(?:\s+.*)?",
        r"\besibizion\w+\b|\bdocument\w+\b|\b210\b",
        "Istanza di ordine di esibizione",
        "titolo dell'istanza e documenti da esibire (art. 210 c.p.c.)",
    ),
    _istanza(
        "istanza_distrazione_spese",
        r"istanza\s+di\s+distrazione(?:\s+delle)?\s+spese(?:\s+.*)?",
        r"\bdistrazion\w+\b|\bantistatari\w+\b|\banticipat\w+\b|\b93\b",
        "Istanza di distrazione delle spese",
        "titolo dell'istanza e dichiarazione di anticipo delle spese (art. 93 c.p.c.)",
    ),
    _istanza(
        "istanza_riunione_separazione",
        r"istanza\s+di\s+(?:riunione|separazione)(?:\s+(?:dei\s+)?(?:procedimenti|giudizi|cause))?(?:\s+.*)?",
        r"\briunion\w+\b|\bseparazion\w+\b|\bconness\w+\b|\bprocediment\w+\b|\bcaus\w+\b",
        "Istanza di riunione o separazione dei procedimenti",
        "titolo dell'istanza e connessione delle cause (artt. 273, 274 e 279 c.p.c.)",
    ),
    _istanza(
        "istanza_estinzione",
        r"istanza\s+(?:di|per\s+la\s+dichiarazione\s+di)\s+estinzione(?:\s+(?:del\s+giudizio|del\s+processo|della\s+procedura))?(?:\s+.*)?",
        r"\bestinzion\w+\b|\binattivit\w+\b|\brinunci\w+\b",
        "Istanza di estinzione",
        "titolo dell'istanza e causa di estinzione (artt. 306, 307 e 630 c.p.c.)",
    ),
    _istanza(
        "istanza_integrazione_contraddittorio",
        r"istanza\s+di\s+integrazione\s+del\s+contraddittorio(?:\s+.*)?",
        r"\bcontraddittori\w+\b|\blitisconsor\w+\b|\bparti\b",
        "Istanza di integrazione del contraddittorio",
        "titolo dell'istanza e litisconsorzio necessario (artt. 102 e 331 c.p.c.)",
    ),
    _istanza(
        "istanza_interrogatorio_formale",
        r"istanza\s+di\s+(?:interpello|interrogatorio)\s+formale(?:\s+.*)?",
        r"\binterrogatori\w+\b|\binterpell\w+\b|\bcapitol\w+\b",
        "Istanza di interrogatorio formale",
        "titolo dell'istanza e capitoli dell'interrogatorio (art. 230 c.p.c.)",
    ),
    _istanza(
        "istanza_ordinanza_rilascio",
        r"istanza\s+di\s+ordinanza\s+(?:provvisoria\s+)?di\s+rilascio(?:\s+.*)?",
        r"\brilasci\w+\b|\bimmobil\w+\b|\bsfratt\w+\b|\bconvalid\w+\b",
        "Istanza di ordinanza provvisoria di rilascio",
        "titolo dell'istanza e rilascio dell'immobile (art. 665 c.p.c.)",
    ),
    _istanza(
        "istanza_inaudita_altera_parte",
        r"istanza\s+di\s+provvedimento\s+inaudita\s+altera\s+parte(?:\s+.*)?|istanza\s+(?:di\s+emissione\s+)?inaudita\s+altera\s+parte(?:\s+.*)?",
        r"\binaudita\s+altera\s+parte\b|\burgen\w+\b|\bpregiudizio\b",
        "Istanza di provvedimento inaudita altera parte",
        "titolo dell'istanza e pregiudizio della convocazione (art. 669-sexies, secondo comma, c.p.c.)",
    ),
)

__all__ = ["REGOLE"]
