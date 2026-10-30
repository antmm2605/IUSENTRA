"""Atti del processo civile di cognizione e delle impugnazioni oltre a quelli di `civile` (c.p.c., libri I e II).

Vengono prima di `civile` perché alcuni titoli contengono parole che le sue
regole leggerebbero in modo generico (il controricorso non è un ricorso per
cassazione; le note d'udienza non sono una memoria).
"""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

_CAUSA = r"\bcaus\w+\b|\bgiudizi\w+\b|\bgiudice\b|\budienz\w+\b|\bprocediment\w+\b"


def _atto(id: str, titolo: str, conferma: str, label: str, evidence: str, *, role: str = "atto_difensivo",
          tipo: TipoDocumento = TipoDocumento.MEMORIA, section: str = "atti", deposit_role: str = "atto_principale",
          fonte: str = "normattiva_cpc"):
    return regola(id, titolo, conferma, label, role=role, section=section, tipo=tipo, fonte=fonte,
                  deposit_role=deposit_role, evidence=evidence)


REGOLE = (
    _atto(
        "controricorso",
        r"controricorso(?:\s+.*)?",
        r"\bcassazion\w+\b|\bricorrent\w+\b|\b370\b|\bmotiv\w+\b",
        "Controricorso",
        "titolo dell'atto e difesa contro il ricorso per cassazione (art. 370 c.p.c.)",
        tipo=TipoDocumento.COMPARSA,
    ),
    _atto(
        "regolamento_competenza_giurisdizione",
        r"(?:istanza\s+di\s+|ricorso\s+per\s+)?regolamento\s+(?:necessario\s+|facoltativo\s+|preventivo\s+)?di\s+(?:competenza|giurisdizione)(?:\s+.*)?",
        r"\bcompetenz\w+\b|\bgiurisdizion\w+\b|\bcassazion\w+\b|\b4[1-7]\b",
        "Ricorso per regolamento di competenza o di giurisdizione",
        "titolo del ricorso e questione di competenza o giurisdizione (artt. 41 e 42 c.p.c.)",
        role="atto_principale", tipo=TipoDocumento.RICORSO,
    ),
    _atto(
        "revocazione",
        r"(?:atto\s+di\s+citazione\s+per\s+|ricorso\s+per\s+)?revocazione(?:\s+.*)?",
        r"\brevocazion\w+\b|\b39[5-8]\b|\bsentenz\w+\b|\berror\w+\s+di\s+fatto\b|\bdol\w+\b",
        "Impugnazione per revocazione",
        "titolo dell'atto e motivi di revocazione (artt. 395 e 398 c.p.c.)",
        role="atto_principale", tipo=TipoDocumento.CITAZIONE,
    ),
    _atto(
        "opposizione_terzo_sentenza",
        r"(?:atto\s+di\s+)?opposizione\s+(?:di\s+terzo|ordinaria\s+di\s+terzo|revocatoria\s+di\s+terzo)(?:\s+(?:avverso|contro|alla)\s+.*)?|opposizione\s+di\s+terzo\s+ex\s+art\.?\s*404(?:\s+.*)?",
        r"\bterzo\b|\bsentenz\w+\b|\b404\b|\bpregiudic\w+\b",
        "Opposizione di terzo alla sentenza",
        "titolo dell'atto e pregiudizio del terzo (art. 404 c.p.c.)",
        role="atto_principale", tipo=TipoDocumento.CITAZIONE,
    ),
    _atto(
        "ricorso_legge_pinto",
        r"ricorso\s+(?:ex\s+)?(?:legge|l\.)\s*pinto(?:\s+.*)?|ricorso\s+per\s+(?:l.?\s*)?equa\s+riparazione(?:\s+.*)?|ricorso\s+ex\s+(?:art\.?\s*3\s+)?(?:l\.?|legge)\s*(?:n\.?\s*)?89/2001(?:\s+.*)?",
        r"\bequa\s+riparazion\w+\b|\bragionevole\s+durata\b|\b89/2001\b|\bpinto\b",
        "Ricorso per equa riparazione (legge Pinto)",
        "titolo del ricorso e irragionevole durata del processo (L. 89/2001, art. 3)",
        role="atto_principale", tipo=TipoDocumento.RICORSO, fonte="normattiva_legge_89_2001_pinto",
    ),
    _atto(
        "riassunzione_giudizio",
        r"(?:atto\s+di\s+|ricorso\s+per\s+(?:la\s+)?|comparsa\s+(?:di\s+)?)?riassunzione(?:\s+del\s+(?:giudizio|processo))?(?:\s+.*)?",
        r"\briassun\w+\b|\binterruzion\w+\b|\bsospension\w+\b|\b30[23]\b|\b297\b|\bincompetenz\w+\b",
        "Atto di riassunzione del giudizio",
        "titolo dell'atto e ripresa del processo interrotto o sospeso (artt. 297, 302 e 303 c.p.c.)",
        role="atto_principale", tipo=TipoDocumento.CITAZIONE,
    ),
    _atto(
        "rinuncia_atti_giudizio",
        r"(?:atto\s+di\s+|dichiarazione\s+di\s+)?rinuncia\s+agli\s+atti(?:\s+del\s+giudizio)?(?:\s+.*)?|accettazione\s+(?:della\s+)?rinuncia(?:\s+agli\s+atti)?(?:\s+.*)?",
        r"\brinunci\w+\b|\baccett\w+\b|\b306\b|\bestinzion\w+\b",
        "Rinuncia agli atti del giudizio",
        "titolo dell'atto e rinuncia accettata dalle parti costituite (art. 306 c.p.c.)",
    ),
    _atto(
        "capitoli_prova",
        r"capitoli\s+di\s+prova(?:\s+testimoniale)?(?:\s+.*)?|deduzioni\s+istruttorie(?:\s+.*)?|articolazione\s+(?:dei\s+mezzi\s+)?di\s+prova(?:\s+.*)?",
        r"\bvero\s+che\b|\btest[ei]\b|\bcapitol\w+\b|\bprova\b|\bammission\w+\b",
        "Capitoli di prova e deduzioni istruttorie",
        "titolo dell'atto e mezzi di prova dedotti (artt. 244 e 183 c.p.c.)",
    ),
    _atto(
        "osservazioni_ctu",
        r"(?:osservazioni|note\s+critiche|note\s+tecniche|controdeduzioni)\s+(?:alla\s+)?(?:bozza\s+di\s+)?(?:ctu|c\.t\.u\.|consulenza\s+tecnica(?:\s+d.?\s*ufficio)?|relazione\s+(?:del\s+)?ctu)(?:\s+.*)?",
        r"\bctu\b|\bconsulen\w+\b|\bperit\w+\b|\brelazion\w+\b",
        "Osservazioni alla consulenza tecnica d'ufficio",
        "titolo dell'atto e rilievi alla relazione del consulente (art. 195, terzo comma, c.p.c.)",
        fonte="normattiva_cpc_consulenza_tecnica",
    ),
    _atto(
        "note_udienza",
        r"note\s+(?:d.?\s*|di\s+)udienza(?:\s+.*)?|note\s+(?:autorizzate|difensive\s+d.?\s*udienza)(?:\s+.*)?",
        _CAUSA,
        "Note d'udienza",
        "titolo delle note e udienza di riferimento (art. 183 c.p.c.; art. 121 c.p.p.)",
    ),
    _atto(
        "note_conclusive",
        r"note\s+(?:conclusive|conclusionali|di\s+discussione)(?:\s+.*)?|nota\s+conclusiva(?:\s+.*)?|memoria\s+di\s+replica(?:\s+.*)?|note\s+di\s+replica(?:\s+.*)?|replica(?:\s+amministrativa)?(?:\s+.*)?",
        _CAUSA + r"|\bconclusion\w+\b|\breplic\w+\b",
        "Note conclusive e di replica",
        "titolo delle note e decisione della causa (artt. 189, 190 e 281-quinquies c.p.c.; art. 73 c.p.a.)",
    ),
    _atto(
        "istanza_cautelare_possessoria",
        r"(?:ricorso\s+(?:per|di)\s+|azione\s+di\s+)(?:reintegra(?:zione)?|manutenzione)(?:\s+nel\s+possesso)?(?:\s+.*)?|ricorso\s+possessorio(?:\s+.*)?",
        r"\bpossess\w+\b|\bspoli\w+\b|\bturbativ\w+\b|\b1168\b|\b1170\b|\b703\b",
        "Ricorso possessorio",
        "titolo del ricorso e tutela del possesso (artt. 1168 e 1170 c.c.; art. 703 c.p.c.)",
        role="atto_principale", tipo=TipoDocumento.RICORSO, fonte="cpc_procedimenti_possessori",
    ),
    _atto(
        "denuncia_nuova_opera",
        r"(?:ricorso\s+per\s+)?denuncia\s+di\s+(?:nuova\s+opera|danno\s+temuto)(?:\s+.*)?",
        r"\bopera\b|\bdanno\s+temuto\b|\b117[12]\b|\b688\b|\bpericolo\b",
        "Denuncia di nuova opera o di danno temuto",
        "titolo del ricorso e pericolo per il bene (artt. 1171 e 1172 c.c.; art. 688 c.p.c.)",
        role="atto_principale", tipo=TipoDocumento.RICORSO, fonte="cpc_procedimenti_possessori",
    ),
    _atto(
        "ricorso_inibitorio_urgente",
        r"ricorso\s+inibitorio(?:\s+urgente)?(?:\s+.*)?|inibitoria\s+(?:commerciale\s+)?urgente(?:\s+.*)?|atto\s+cautelare\s+inibitorio(?:\s+.*)?",
        r"\binibitori\w+\b|\burgen\w+\b|\bpericulum\b|\bfumus\b|\bcessazion\w+\b",
        "Ricorso cautelare inibitorio",
        "titolo del ricorso e inibitoria in via d'urgenza (art. 700 c.p.c.; art. 131 D.Lgs. 30/2005)",
        role="atto_principale", tipo=TipoDocumento.RICORSO, fonte="cpc_procedimenti_cautelari_uniformi",
    ),
)

__all__ = ["REGOLE"]
