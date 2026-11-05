"""Presso chi e come si notifica, secondo chi è il destinatario.

* amministrazione dello Stato → Avvocatura dello Stato del distretto (art. 11 R.D. 1611/1933, art. 144 c.p.c.);
  nel pubblico impiego di primo grado il ricorso si notifica all'amministrazione (art. 415, settimo comma, c.p.c.);
* altra pubblica amministrazione → indirizzo PEC del registro delle pubbliche amministrazioni (art. 16-ter D.L. 179/2012);
* impugnazione → procuratore costituito o indirizzo indicato nella notifica della sentenza (art. 330 c.p.c.);
* chiunque altro → PEC risultante dai pubblici elenchi (art. 3-bis L. 53/1994; art. 16-ter D.L. 179/2012);
  senza PEC nei pubblici elenchi → ufficiale giudiziario (art. 137 c.p.c.).
"""

from __future__ import annotations

import re

_STATO = re.compile(r"\b(?:minister[oi]|presidenza\s+del\s+consiglio|amministrazione\s+dello\s+stato|avvocatura\s+dello\s+stato)\b", re.I)
_PA = re.compile(r"\b(?:comune|regione|provincia|citt[aà]\s+metropolitana|azienda\s+sanitaria|a\.?s\.?l\b|a\.?s\.?p\b|"
                 r"inps|inail|agenzia\s+delle\s+entrate|universit[aà]|istituto\s+(?:comprensivo|scolastico)|"
                 r"ufficio\s+scolastico|camera\s+di\s+commercio|ente\s+pubblico)\b", re.I)


def come_notificare(controparte: str, *, materia: str = "", impugnazione: bool = False) -> list[dict[str, object]]:
    """Le indicazioni, dalla più specifica, ognuna con le sue norme; mai un indirizzo inventato."""
    nome = str(controparte or "").strip()
    passi: list[dict[str, object]] = []
    if impugnazione:
        passi.append({"testo": "Notificare presso il procuratore costituito nel grado precedente o all'indirizzo indicato nella "
                               "notifica della sentenza.", "norme": ["cpc_330", "cpc_170"]})
    if nome and _STATO.search(nome):
        if materia == "lavoro" and not impugnazione:
            passi.append({"testo": f"{nome}: nel pubblico impiego il ricorso si notifica direttamente all'amministrazione; per la "
                                   "difesa delle amministrazioni statali si osservano le norme sull'Avvocatura dello Stato.",
                          "norme": ["cpc_415", "cpc_144", "rd1611_art11"]})
        else:
            passi.append({"testo": f"{nome}: notificare presso l'Avvocatura dello Stato del distretto dell'ufficio giudiziario, "
                                   "a pena di nullità.", "norme": ["rd1611_art11", "cpc_144"]})
        passi.append({"testo": "Indirizzo PEC dal registro delle pubbliche amministrazioni.", "norme": ["dl179_art16ter"]})
    elif nome and _PA.search(nome):
        passi.append({"testo": f"{nome}: indirizzo PEC dal registro delle pubbliche amministrazioni.", "norme": ["dl179_art16ter", "l53_art3bis"]})
    else:
        chi = nome or "Il destinatario"
        passi.append({"testo": f"{chi}: notifica a mezzo PEC all'indirizzo risultante dai pubblici elenchi (INI-PEC, registro delle "
                               "imprese, ReGIndE).", "norme": ["l53_art3bis", "dl179_art16ter"]})
    passi.append({"testo": "Senza un indirizzo PEC nei pubblici elenchi: notifica a mezzo dell'ufficiale giudiziario.", "norme": ["cpc_137"]})
    return passi


__all__ = ["come_notificare"]
