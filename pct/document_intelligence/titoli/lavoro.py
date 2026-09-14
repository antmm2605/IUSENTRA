"""Atti e documenti del rapporto di lavoro e del rito del lavoro."""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

_LAVORO = r"\brapporto\s+di\s+lavoro\b|\bdatore\s+di\s+lavoro\b|\blavorat\w+\b|\bretribu\w+\b|\bdipendent\w+\b"

REGOLE = (
    regola(
        "ricorso_lavoro",
        r"ricorso(?:\s+.*)?",
        r"\b414\b|\bgiudice\s+del\s+lavoro\b|\bsezione\s+lavoro\b",
        "Ricorso in materia di lavoro (art. 414 c.p.c.)",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO,
        fonte="normattiva_cpc_rito_lavoro", deposit_role="atto_principale",
        evidence="titolo del ricorso e rito del lavoro (art. 414 c.p.c.)",
    ),
    regola(
        "memoria_416",
        r"memoria(?:\s+difensiva)?(?:\s+.*)?",
        r"\b416\b|\bgiudice\s+del\s+lavoro\b|\bsezione\s+lavoro\b",
        "Memoria difensiva ex art. 416 c.p.c.",
        role="atto_difensivo", section="atti", tipo=TipoDocumento.MEMORIA,
        fonte="normattiva_cpc_rito_lavoro", deposit_role="atto_principale",
        evidence="titolo della memoria e costituzione nel rito del lavoro (art. 416 c.p.c.)",
    ),
    regola(
        "lettera_licenziamento",
        r"(?:lettera\s+di\s+|comunicazione\s+di\s+)?licenziamento(?:\s+.*)?",
        r"\breced\w+\b|\blicenzi\w+\b|\bpreavviso\b|\bgiustificato\s+motivo\b|\bgiusta\s+causa\b",
        "Lettera di licenziamento",
        role="corrispondenza", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="normattiva_l_604_1966_art_2_6", deposit_role="allegato",
        evidence="titolo della comunicazione e recesso del datore (art. 2 L. 604/1966)",
    ),
    regola(
        "impugnazione_licenziamento",
        r"impugnazione\s+(?:del\s+|di\s+)?licenziamento(?:\s+.*)?|impugnativa\s+(?:di\s+)?licenziamento(?:\s+.*)?",
        r"\bimpugn\w+\b|\blicenziamento\b|\billegittim\w+\b",
        "Impugnazione del licenziamento",
        role="corrispondenza_stragiudiziale", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="normattiva_l_604_1966_art_2_6", deposit_role="allegato",
        evidence="titolo dell'atto e impugnazione stragiudiziale (art. 6 L. 604/1966)",
    ),
    regola(
        "contestazione_disciplinare",
        r"contestazione\s+(?:disciplinare|di\s+addebito|degli\s+addebiti)(?:\s+.*)?",
        r"\bart\.?\s*7\b|\baddebit\w+\b|\bgiustificazion\w+\b|\bdisciplinar\w+\b",
        "Contestazione disciplinare",
        role="corrispondenza", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="normattiva_l_300_1970_art_7_disciplinare", deposit_role="allegato",
        evidence="titolo della contestazione e procedimento disciplinare (art. 7 L. 300/1970)",
    ),
    regola(
        "busta_paga",
        r"(?:cedolino|busta)\s+(?:di\s+)?paga(?:\s+.*)?|prospetto\s+(?:di\s+)?paga(?:\s+.*)?|cedolino(?:\s+.*)?",
        r"\bretribu\w+\b|\binps\b|\birpef\b|\bnetto\b|\blordo\b|\bcontribut\w+\b",
        "Prospetto di paga",
        role="documento_economico", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_legge_4_1953_prospetto_paga",
        evidence="titolo del prospetto e voci retributive (art. 1 L. 4/1953)",
    ),
    regola(
        "certificazione_unica",
        r"certificazione\s+unica(?:\s+.*)?",
        r"\bsostituto\b|\bredditi\b|\britenut\w+\b|\bpercipient\w+\b",
        "Certificazione unica",
        role="documento_economico", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_dpr_322_1998_dichiarazioni",
        evidence="titolo della certificazione e ritenute operate (art. 4 D.P.R. 322/1998)",
    ),
    regola(
        "contratto_lavoro",
        r"contratto\s+(?:individuale\s+)?di\s+lavoro(?:\s+.*)?|lettera\s+di\s+assunzione(?:\s+.*)?|contratto\s+di\s+(?:apprendistato|collaborazione|somministrazione)(?:\s+.*)?",
        r"\bassun\w+\b|\bmansion\w+\b|\bretribu\w+\b|\binquadr\w+\b|\bccnl\b|\borario\s+di\s+lavoro\b",
        "Contratto di lavoro",
        role="contratto", section="contratti", tipo=TipoDocumento.CONTRATTO,
        fonte="normattiva_d_lgs_152_1997_informazioni_lavoro",
        evidence="titolo del contratto e condizioni del rapporto (art. 1 D.Lgs. 152/1997)",
    ),
    regola(
        "verbale_conciliazione_lavoro",
        r"verbale\s+di\s+conciliazione(?:\s+.*)?",
        r"\bconcili\w+\b|\bispettorato\b|\bsindacal\w+\b|\brinunci\w+\b|\btransa\w+\b",
        "Verbale di conciliazione",
        role="verbale_ufficio", section="allegati", tipo=TipoDocumento.VERBALE,
        fonte="normattiva_cpc_rito_lavoro",
        evidence="titolo del verbale e accordo conciliativo (artt. 410 e 411 c.p.c.)",
    ),
    regola(
        "estratto_contributivo",
        r"estratto\s+(?:conto\s+)?contributivo(?:\s+.*)?",
        r"\binps\b|\bcontribut\w+\b|\bsettiman\w+\b|\bperiod\w+\b",
        "Estratto conto contributivo",
        role="documento_economico", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_legge_4_1953_prospetto_paga",
        evidence="titolo dell'estratto e posizione contributiva",
    ),
    regola(
        "dimissioni",
        r"(?:lettera\s+di\s+)?dimissioni(?:\s+volontarie)?(?:\s+.*)?|comunicazione\s+di\s+dimissioni(?:\s+.*)?",
        r"\bdimett\w+\b|\brassegn\w+\b|\bpreavviso\b|\brapporto\s+di\s+lavoro\b",
        "Dimissioni",
        role="corrispondenza", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="normattiva_d_lgs_151_2015_dimissioni_telematiche", deposit_role="allegato",
        evidence="titolo della comunicazione e recesso del lavoratore (art. 26 D.Lgs. 151/2015)",
    ),
    regola(
        "ricorso_amministrativo_previdenziale",
        r"ricorso\s+amministrativo(?:\s+.*)?",
        r"\binps\b|\binail\b|\bcomitato\b|\bprestazion\w+\b|\bpension\w+\b",
        "Ricorso amministrativo previdenziale",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO,
        fonte="normattiva_cpc_rito_lavoro", deposit_role="allegato",
        evidence="titolo del ricorso e ente previdenziale destinatario",
    ),
)

__all__ = ["REGOLE"]
