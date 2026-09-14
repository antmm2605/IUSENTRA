"""Sinistri, responsabilità civile e documentazione medica."""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

REGOLE = (
    regola(
        "constatazione_amichevole",
        r"constatazione\s+amichevole(?:\s+.*)?|modulo\s+(?:cai|cid)(?:\s+.*)?|denuncia\s+di\s+sinistro(?:\s+.*)?",
        r"\bveicol\w+\b|\bsinistro\b|\btarga\b|\bassicura\w+\b|\bconducent\w+\b",
        "Constatazione amichevole di incidente",
        role="documento_sinistro", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_codice_assicurazioni_209_2005",
        evidence="titolo del modulo e dati del sinistro (art. 143 D.Lgs. 209/2005)",
    ),
    regola(
        "richiesta_risarcimento",
        r"richiesta\s+(?:di\s+)?risarcimento(?:\s+(?:dei\s+)?danni)?(?:\s+.*)?|richiesta\s+danni(?:\s+.*)?",
        r"\bsinistro\b|\brisarc\w+\b|\bdann\w+\b|\bassicura\w+\b|\bresponsabil\w+\b",
        "Richiesta di risarcimento",
        role="corrispondenza_stragiudiziale", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="normattiva_codice_assicurazioni_209_2005", deposit_role="allegato",
        evidence="titolo della richiesta e sinistro denunciato (art. 148 D.Lgs. 209/2005)",
    ),
    regola(
        "referto_medico",
        r"referto(?:\s+(?:medico|di\s+pronto\s+soccorso|radiologico))?(?:\s+.*)?|certificato\s+medico(?:\s+.*)?|verbale\s+di\s+pronto\s+soccorso(?:\s+.*)?|lettera\s+di\s+dimissione(?:\s+.*)?|cartella\s+clinica(?:\s+.*)?",
        r"\bdiagnos\w+\b|\bprognos\w+\b|\bpazient\w+\b|\blesion\w+\b|\bgiorni\b|\bmedic\w+\b",
        "Documentazione medica",
        role="documento_medico", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_codice_assicurazioni_209_2005",
        evidence="titolo del documento sanitario e diagnosi",
    ),
    regola(
        "relazione_medico_legale",
        r"(?:relazione|perizia|consulenza)\s+medico[\s-]*legale(?:\s+.*)?",
        r"\binvalidit\w+\b|\blesion\w+\b|\bdanno\s+biologico\b|\bmenomazion\w+\b|\bpostum\w+\b",
        "Relazione medico-legale",
        role="perizia_di_parte", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_cpc_consulenza_tecnica",
        evidence="titolo della relazione e valutazione del danno alla persona",
    ),
    regola(
        "rapporto_incidente",
        r"rapporto\s+di\s+incidente(?:\s+stradale)?(?:\s+.*)?|verbale\s+di\s+rilievo(?:\s+.*)?|rilievi\s+(?:del|di)\s+(?:sinistro|incidente)(?:\s+.*)?",
        r"\bveicol\w+\b|\bconducent\w+\b|\bpolizia\b|\bcarabinieri\b|\bsinistro\b",
        "Rapporto di incidente stradale",
        role="verbale_ufficio", section="allegati", tipo=TipoDocumento.VERBALE,
        fonte="normattiva_codice_strada_285_1992",
        evidence="titolo del rapporto e rilievi dell'autorità",
    ),
    regola(
        "preventivo_riparazione",
        r"preventivo(?:\s+di\s+(?:riparazione|spesa))?(?:\s+.*)?",
        r"\briparazion\w+\b|\bcarrozzeria\b|\bricambi\b|\bmanodopera\b|\bveicol\w+\b",
        "Preventivo di riparazione",
        role="documento_economico", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_codice_assicurazioni_209_2005",
        evidence="titolo del preventivo e voci di riparazione",
    ),
)

__all__ = ["REGOLE"]
