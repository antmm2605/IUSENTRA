"""Regole generiche: si applicano solo quando nessuna area ha riconosciuto l'atto."""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

REGOLE = (
    regola(
        "ricorso",
        r"ricorso(?:\s+.*)?",
        r"\bricorrente\b|\bchiede\b|\bespone\b|\bpremesso\b",
        "Ricorso introduttivo",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO,
        fonte="normattiva_cpc", deposit_role="atto_principale",
        evidence="titolo del ricorso e formula della domanda (artt. 125 e 281-undecies c.p.c.)",
    ),
    regola(
        "memoria",
        r"memori[ae](?:\s+.*)?",
        r"\btribunale\b|\bgiudice\b|\bcorte\b|\br\.?\s*g\.?\b",
        "Memoria difensiva",
        role="atto_difensivo", section="atti", tipo=TipoDocumento.MEMORIA,
        fonte="normattiva_cpc", deposit_role="atto_principale",
        evidence="titolo della memoria e riferimenti al giudizio",
    ),
    regola(
        "istanza",
        r"istanza\s+(?:di|per|ex|al|ai\s+sensi)\b.*",
        r"\bchiede\b|\bsi\s+chiede\b|\bistante\b|\bvoglia\b",
        "Istanza",
        role="istanza", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        fonte="normattiva_cpc", deposit_role="atto_principale",
        evidence="titolo dell'istanza e richiesta al giudice",
    ),
    regola(
        "contratto",
        r"contratto\s+(?:di\s+)?\w+(?:\s+.*)?|scrittura\s+privata(?:\s+.*)?|accordo(?:\s+.*)?|transazione(?:\s+.*)?",
        r"\bsi\s+convien\w*\b|\bstipul\w*\b|\ble\s+parti\b|\bsi\s+obblig\w+\b|\bcorrispettiv\w*\b|\bsottoscri\w+\b",
        "Contratto",
        role="contratto", section="contratti", tipo=TipoDocumento.CONTRATTO,
        fonte="normattiva_cc_contratto",
        evidence="titolo del contratto e accordo delle parti (art. 1321 c.c.)",
    ),
    regola(
        "diffida",
        r"(?:oggetto\s*:\s*)?(?:lettera\s+di\s+)?diffida(?:\s+.*)?|(?:oggetto\s*:\s*)?(?:atto\s+di\s+)?(?:costituzione|messa)\s+in\s+mora(?:\s+.*)?|(?:oggetto\s*:\s*)?sollecito\s+di\s+pagamento(?:\s+.*)?",
        r"\bdiffid\w+\b|\bin\s+mora\b|\bentro\b.{0,60}\bgiorni\b|\bpagament\w+\b",
        "Lettera di diffida e messa in mora",
        role="corrispondenza_stragiudiziale", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="cc_art_1219_mora",
        evidence="titolo della lettera e intimazione ad adempiere (art. 1219 c.c.)",
    ),
    regola(
        "lettera",
        r"oggetto\s*:\s*.+",
        r"\b(?:gentile|gent\.m[oa]|egregi[oa]|spett\.?le|spettabile)\b|\b(?:distinti|cordiali)\s+saluti\b",
        "Lettera",
        role="corrispondenza", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="catalog_agid_metadati", deposit_role="allegato",
        evidence="oggetto della lettera e formule di apertura o chiusura",
    ),
)

__all__ = ["REGOLE"]
