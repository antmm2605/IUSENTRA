"""Risoluzione alternativa delle controversie: mediazione, negoziazione assistita e arbitrato.

Fonti: D.Lgs. 28/2010 (mediazione), D.L. 132/2014 (negoziazione assistita),
c.p.c. artt. 806-840 (arbitrato). L'istanza e la proposta del mediatore
restano in `civile`.
"""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

_MEDIAZIONE = r"\bmediazion\w+\b|\bmediator\w+\b|\borganismo\b|\b28/2010\b"
_NEGOZIAZIONE = r"\bnegoziazione\s+assistita\b|\b132/2014\b|\bconvenzione\s+di\s+negoziazione\b"
_ARBITRATO = r"\barbitr\w+\b|\bcollegio\s+arbitrale\b|\blodo\b|\b8(?:0[6-9]|1\d)\b"


def _atto(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str,
          role: str = "atto_adr", section: str = "allegati", tipo: TipoDocumento = TipoDocumento.ALLEGATO,
          deposit_role: str = "allegato", deposit_candidate: bool = True):
    return regola(id, titolo, conferma, label, role=role, section=section, tipo=tipo, fonte=fonte,
                  deposit_role=deposit_role, deposit_candidate=deposit_candidate, evidence=evidence)


REGOLE = (
    _atto(
        "invito_negoziazione_assistita",
        r"invito\s+(?:a\s+(?:stipulare\s+(?:una\s+)?convenzione\s+di\s+)?|alla\s+)negoziazione\s+assistita(?:\s+.*)?",
        _NEGOZIAZIONE + r"|\bconvenzion\w+\b|\btrenta\s+giorni\b",
        "Invito a negoziazione assistita",
        "titolo dell'invito e convenzione proposta all'altra parte (art. 4 D.L. 132/2014)",
        fonte="normattiva_dl_132_2014_negoziazione", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
    ),
    _atto(
        "risposta_negoziazione_assistita",
        r"(?:diniego|rifiuto|adesione|risposta)\s+(?:all.?\s*invito\s+)?(?:a|alla)\s+negoziazione(?:\s+assistita)?(?:\s+.*)?",
        _NEGOZIAZIONE + r"|\binvit\w+\b|\baderi\w+\b|\brifiut\w+\b",
        "Risposta all'invito a negoziazione assistita",
        "titolo della risposta e adesione o rifiuto dell'invito (art. 4 D.L. 132/2014)",
        fonte="normattiva_dl_132_2014_negoziazione", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
    ),
    _atto(
        "invito_mediazione",
        r"invito\s+(?:a|alla)\s+mediazione(?:\s+.*)?|comunicazione\s+(?:di\s+avvio|della\s+domanda)\s+di\s+mediazione(?:\s+.*)?",
        _MEDIAZIONE + r"|\bincontr\w+\b",
        "Invito alla mediazione",
        "titolo dell'invito e procedimento di mediazione (artt. 4 e 8 D.Lgs. 28/2010)",
        fonte="normattiva_d_lgs_28_2010_mediazione", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
    ),
    _atto(
        "adesione_mediazione",
        r"(?:modulo\s+di\s+)?adesione\s+(?:alla\s+)?(?:procedura\s+di\s+)?mediazione(?:\s+.*)?|(?:istanza|domanda)\s+di\s+adesione(?:\s+alla\s+mediazione)?(?:\s+.*)?",
        _MEDIAZIONE + r"|\bparte\s+(?:invitata|chiamata)\b|\baderi\w+\b",
        "Adesione alla mediazione",
        "titolo dell'atto e partecipazione della parte chiamata (art. 8 D.Lgs. 28/2010)",
        fonte="normattiva_d_lgs_28_2010_mediazione",
    ),
    _atto(
        "verbale_mediazione",
        r"verbale\s+(?:di\s+(?:accordo|mancato\s+accordo|conciliazione|mancata\s+conciliazione|primo\s+incontro)(?:\s+.*)?|negativo\s+di\s+mediazione(?:\s+.*)?)|"
        r"verbale\s+(?:conclusivo\s+)?(?:del\s+procedimento\s+)?di\s+mediazione(?:\s+.*)?",
        _MEDIAZIONE + r"|\bincontr\w+\b|\bparti\b",
        "Verbale di mediazione",
        "titolo del verbale ed esito dell'incontro di mediazione (artt. 11 e 12 D.Lgs. 28/2010)",
        fonte="normattiva_d_lgs_28_2010_art_11_proposta", role="verbale_adr",
        deposit_role="fuori_busta", deposit_candidate=False,
    ),
    _atto(
        "clausola_compromissoria",
        r"clausola\s+(?:compromissoria|arbitrale)(?:\s+.*)?|compromesso(?:\s+arbitrale)?(?:\s+.*)?|convenzione\s+(?:di\s+)?arbitr(?:ato|ale)(?:\s+.*)?",
        _ARBITRATO,
        "Clausola compromissoria o compromesso",
        "titolo dell'atto e devoluzione della lite ad arbitri (artt. 807 e 808 c.p.c.)",
        fonte="normattiva_cpc", role="contratto", section="contratti", tipo=TipoDocumento.CONTRATTO,
    ),
    _atto(
        "domanda_arbitrato",
        r"(?:domanda|atto\s+introduttivo|atto\s+di\s+accesso)\s+(?:di|all.?\s*)\s*arbitrato(?:\s+.*)?|domanda\s+di\s+arbitrato(?:\s+.*)?",
        _ARBITRATO + r"|\bconvenuto\b|\bdomand\w+\b",
        "Domanda di arbitrato",
        "titolo della domanda e nomina degli arbitri (artt. 806, 810 e 816-bis c.p.c.)",
        fonte="normattiva_cpc", role="atto_principale", section="atti", tipo=TipoDocumento.CITAZIONE,
        deposit_role="atto_principale",
    ),
    _atto(
        "nomina_arbitro",
        r"(?:atto\s+di\s+)?nomina\s+(?:dell.?\s*|del\s+)?arbitr[oi](?:\s+.*)?|accettazione\s+(?:della\s+nomina\s+)?(?:dell.?\s*)?arbitr[oi](?:\s+.*)?",
        _ARBITRATO,
        "Nomina dell'arbitro",
        "titolo dell'atto e nomina o accettazione dell'arbitro (artt. 810 e 813 c.p.c.)",
        fonte="normattiva_cpc", role="atto_adr",
    ),
    _atto(
        "memoria_arbitrale",
        r"(?:memoria|comparsa)\s+(?:nel\s+procedimento\s+)?arbitrale(?:\s+.*)?|(?:memoria|comparsa)\s+(?:di\s+risposta\s+)?nel\s+procedimento\s+arbitrale(?:\s+.*)?",
        _ARBITRATO,
        "Memoria nel procedimento arbitrale",
        "titolo della memoria e svolgimento del procedimento arbitrale (art. 816-bis c.p.c.)",
        fonte="normattiva_cpc", role="atto_difensivo", section="atti", tipo=TipoDocumento.MEMORIA,
        deposit_role="atto_principale",
    ),
)

__all__ = ["REGOLE"]
