"""Atti che accompagnano il deposito telematico: nota di deposito, indice, nota di iscrizione, attestazione.

Le stesse voci il catalogo le riconosce anche dal contenuto (busta, moduli
ministeriali); qui si leggono dal titolo, come gli altri atti di parte.
Fonti: D.M. 44/2011 e specifiche tecniche DGSIA; art. 74 disp. att. c.p.c.;
art. 196-undecies disp. att. c.p.c. per l'attestazione di conformità.
"""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

_DEPOSITO = r"\bdeposit\w+\b|\bdocument\w+\b|\ballegat\w+\b|\bfascicol\w+\b|\bcancelleri\w+\b|\bprodu\w+\b"

REGOLE = (
    regola(
        "nota_deposito_documenti",
        r"(?:nota\s+di\s+)?deposito\s+(?:telematico\s+)?(?:di\s+)?document[io](?:\s+.*)?|nota\s+di\s+(?:deposito|produzione)(?:\s+(?:documentale|di\s+documenti))?(?:\s+.*)?",
        _DEPOSITO,
        "Nota di deposito",
        role="deposito", section="atti", tipo=TipoDocumento.DEPOSITO_PCT,
        fonte="pst_dm_44_2011", deposit_role="fuori_busta", deposit_candidate=False,
        evidence="titolo della nota e documenti depositati telematicamente (D.M. 44/2011; art. 87 disp. att. c.p.c.)",
    ),
    regola(
        "indice_documenti",
        r"indice\s+(?:degli\s+|dei\s+)?(?:allegati|documenti|produzioni)(?:\s+.*)?|fascicolo\s+di\s+parte(?:\s+.*)?|elenco\s+(?:dei\s+)?documenti\s+(?:depositati|prodotti)(?:\s+.*)?",
        _DEPOSITO + r"|\bdoc\.?\s*\d+\b|\b74\b",
        "Indice dei documenti depositati",
        role="indice_documenti", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_cpc", deposit_role="fuori_busta", deposit_candidate=False,
        evidence="titolo dell'indice e documenti prodotti nel fascicolo di parte (artt. 74 e 87 disp. att. c.p.c.)",
    ),
    regola(
        "nota_iscrizione_ruolo",
        r"note?\s+(?:di\s+)?iscrizione\s+(?:a|al)\s+ruolo(?:\s+.*)?",
        r"\bruolo\b|\bcontributo\s+unificato\b|\bvalore\b|\boggetto\b|\bpart[ei]\b",
        "Nota di iscrizione a ruolo",
        role="nota_iscrizione_ruolo", section="atti", tipo=TipoDocumento.DEPOSITO_PCT,
        fonte="normattiva_dpr_115_2002_spese_giustizia", deposit_role="fuori_busta", deposit_candidate=False,
        evidence="titolo della nota e dati per l'iscrizione della causa (art. 168 c.p.c.; art. 71 disp. att. c.p.c.)",
    ),
    regola(
        "attestazione_conformita",
        r"attestazione\s+di\s+conformit[aà](?:\s+.*)?|dichiarazione\s+di\s+conformit[aà]\s+(?:all.?\s*originale|della\s+copia)(?:\s+.*)?",
        r"\bconform\w+\b|\boriginal\w+\b|\bcopi\w+\b|\b196-?undecies\b|\b16-?decies\b",
        "Attestazione di conformità",
        role="attestazione", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="disp_att_cpc_art_196_undecies_attestazione", deposit_role="allegato",
        evidence="titolo dell'attestazione e conformità della copia all'originale (art. 196-undecies disp. att. c.p.c.)",
    ),
    regola(
        "proforma_parcella",
        r"(?:nota\s+)?pro-?\s*forma(?:\s+.*)?|avviso\s+di\s+parcella(?:\s+.*)?|parcella\s+pro-?\s*forma(?:\s+.*)?",
        r"\bcompens\w+\b|\bonorar\w+\b|\bimponibil\w+\b|\biva\b|\bcassa\b|\btotale\b",
        "Proforma / avviso di parcella",
        role="proforma", section="pagamenti", tipo=TipoDocumento.PARCELLA,
        fonte="normattiva_dm_55_2014_parametri_forensi",
        evidence="titolo del documento e compenso richiesto prima della fattura (D.M. 55/2014; art. 6 D.P.R. 633/1972)",
    ),
)

__all__ = ["REGOLE"]
