"""Atti delle procedure concorsuali oltre all'apertura e all'ammissione al passivo (D.Lgs. 14/2019)."""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

_CONCORSO = r"\bcurator\w+\b|\bliquidator\w+\b|\bcreditor\w+\b|\bprocedura\b|\bgiudice\s+delegato\b|\bpassivo\b|\bccii\b|\b14/2019\b"


def _atto(id: str, titolo: str, conferma: str, label: str, evidence: str, *, role: str = "atto_principale",
          tipo: TipoDocumento = TipoDocumento.RICORSO):
    return regola(id, titolo, conferma, label, role=role, section="atti", tipo=tipo,
                  fonte="normattiva_codice_crisi_14_2019", deposit_role="atto_principale", evidence=evidence)


REGOLE = (
    _atto(
        "domanda_tardiva_passivo",
        r"domanda\s+(?:tardiva|ultratardiva|supertardiva)\s+di\s+(?:insinuazione|ammissione)(?:\s+al\s+passivo)?(?:\s+.*)?|insinuazione\s+tardiva(?:\s+.*)?",
        r"\btardiv\w+\b|\bcurator\w+\b|\bpassivo\b|\b208\b",
        "Domanda tardiva di ammissione al passivo",
        "titolo della domanda e termine scaduto per l'insinuazione (art. 208 CCII)",
    ),
    _atto(
        "opposizione_stato_passivo",
        r"(?:ricorso\s+in\s+)?opposizione\s+(?:allo\s+)?stato\s+passivo(?:\s+.*)?|impugnazione\s+(?:dei\s+crediti\s+ammessi|dello\s+stato\s+passivo)(?:\s+.*)?",
        r"\bstato\s+passivo\b|\bescluss\w+\b|\bammess\w+\b|\b206\b|\bcurator\w+\b",
        "Opposizione allo stato passivo",
        "titolo del ricorso e credito escluso o ammesso (art. 206 CCII)",
    ),
    _atto(
        "domanda_esdebitazione",
        r"(?:domanda|ricorso|istanza)\s+(?:di|per\s+l.?\s*)\s*esdebitazione(?:\s+.*)?",
        r"\besdebita\w+\b|\bdebit\w+\b|\b2(?:7[89]|8[0-3])\b|\bincapient\w+\b",
        "Domanda di esdebitazione",
        "titolo della domanda e liberazione dai debiti residui (artt. 278-283 CCII)",
    ),
    _atto(
        "concordato_minore",
        r"(?:domanda|ricorso|proposta)\s+di\s+concordato\s+minore(?:\s+.*)?",
        r"\bconcordato\s+minore\b|\bcreditor\w+\b|\bocc\b|\bgestore\b|\b74\b",
        "Domanda di concordato minore",
        "titolo della domanda e proposta ai creditori (art. 74 CCII)",
    ),
    _atto(
        "osservazioni_piano",
        r"osservazioni\s+(?:al|sul)\s+(?:piano|proposta)(?:\s+.*)?|contestazioni\s+(?:al|sul)\s+piano(?:\s+.*)?",
        _CONCORSO + r"|\bocc\b|\bgestore\b|\bpiano\b",
        "Osservazioni al piano",
        "titolo dell'atto e contestazioni dei creditori al piano (artt. 70 e 78 CCII)",
        role="atto_difensivo", tipo=TipoDocumento.MEMORIA,
    ),
    _atto(
        "reclamo_giudice_delegato",
        r"reclamo\s+(?:contro|avverso)\s+(?:il\s+)?(?:provvedimento|decreto)\s+(?:del\s+)?giudice\s+delegato(?:\s+.*)?|reclamo\s+ex\s+art\.?\s*124(?:\s+ccii)?(?:\s+.*)?",
        _CONCORSO + r"|\breclam\w+\b",
        "Reclamo contro un provvedimento del giudice delegato",
        "titolo del reclamo e atto del giudice delegato (art. 124 CCII)",
    ),
    _atto(
        "istanza_rivendica",
        r"(?:istanza|domanda)\s+di\s+(?:rivendica(?:zione)?|restituzione)(?:\s+(?:di\s+beni|ex\s+art\.?\s*210).*)?",
        _CONCORSO + r"|\brivendic\w+\b|\brestituzion\w+\b|\b210\b",
        "Domanda di rivendica o restituzione",
        "titolo della domanda e diritto reale o personale sui beni acquisiti (art. 210 CCII)",
    ),
    _atto(
        "istanza_organi_procedura",
        r"istanza\s+al\s+(?:curatore|liquidatore|commissario(?:\s+giudiziale)?)(?:\s+.*)?|istanza\s+di\s+autorizzazione\s+ad\s+atti\s+del\s+(?:liquidatore|curatore)(?:\s+.*)?",
        _CONCORSO,
        "Istanza agli organi della procedura concorsuale",
        "titolo dell'istanza e poteri del curatore e del giudice delegato (artt. 123 e 128 CCII)",
        role="istanza", tipo=TipoDocumento.MEMORIA,
    ),
)

__all__ = ["REGOLE"]
