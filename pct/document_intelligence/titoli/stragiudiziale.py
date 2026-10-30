"""Corrispondenza stragiudiziale e accordi fra le parti oltre alla diffida generica.

Vengono prima delle regole generiche, che altrimenti le leggerebbero tutte
come «Lettera» o «Lettera di diffida». Fonti: c.c. (mora, prescrizione,
ricognizione di debito, transazione); L. 247/2012 e Codice deontologico
forense per gli atti del rapporto con il cliente.
"""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

_DEBITO = r"\bpagament\w+\b|\bimport\w+\b|\beuro\b|\bsomm\w+\b|\bfattur\w+\b|\bdebit\w+\b|\bcredit\w+\b"
_CLIENTE = r"\bcliente\b|\bpratic\w+\b|\bincaric\w+\b|\bmandat\w+\b|\bavvocat\w+\b|\bstudio\b"


def _atto(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str,
          role: str = "corrispondenza_stragiudiziale", section: str = "comunicazioni",
          tipo: TipoDocumento = TipoDocumento.COMUNICAZIONE, deposit_role: str = "allegato",
          deposit_candidate: bool = True):
    return regola(id, titolo, conferma, label, role=role, section=section, tipo=tipo, fonte=fonte,
                  deposit_role=deposit_role, deposit_candidate=deposit_candidate, evidence=evidence)


REGOLE = (
    _atto(
        "sollecito_pagamento",
        r"(?:primo\s+|secondo\s+|ultimo\s+)?sollecit[oi](?:\s+(?:bonario|formale|commerciale|di\s+pagamento))?(?:\s+.*)?|"
        r"(?:intimazione\s+finale|invito\s+ad\s+adempiere|lettera\s+pre-?precetto|richiesta\s+di\s+pagamento)(?:\s+.*)?",
        _DEBITO,
        "Richiesta stragiudiziale di pagamento",
        "titolo della lettera e richiesta di adempimento (artt. 1219 e 1454 c.c.)",
        fonte="cc_art_1219_mora",
    ),
    _atto(
        "interruzione_prescrizione",
        r"(?:lettera|atto|richiesta)\s+(?:interruttiv[ao]|di\s+interruzione)\s+(?:della\s+)?prescrizione(?:\s+.*)?|comunicazione\s+di\s+riserva\s+(?:dei\s+)?diritti(?:\s+.*)?",
        r"\bprescrizion\w+\b|\binterru\w+\b|\briserv\w+\b|\bdiritt\w+\b|\b294[3-5]\b",
        "Atto interruttivo della prescrizione",
        "titolo dell'atto e costituzione in mora con effetto interruttivo (artt. 2943 e 2945 c.c.)",
        fonte="normattiva_codice_civile",
    ),
    _atto(
        "riscontro_diffida",
        r"riscontro\s+(?:a(?:lla)?\s+)?(?:diffida|lettera|richiesta|vostra)(?:\s+.*)?|risposta\s+(?:a(?:lla)?\s+)?diffida(?:\s+.*)?|lettera\s+di\s+contestazione(?:\s+.*)?",
        r"\bvostra\b|\bdiffid\w+\b|\bcontest\w+\b|\bpretes\w+\b|\binfondat\w+\b|\briscontr\w+\b",
        "Riscontro a diffida",
        "titolo della lettera e contestazione della pretesa altrui (art. 1175 c.c.)",
        fonte="normattiva_codice_civile",
    ),
    _atto(
        "richiesta_documentazione",
        r"richiesta\s+di\s+(?:documentazione|documenti|integrazione\s+documentale)(?:\s+.*)?|sollecito\s+(?:di\s+)?integrazione\s+(?:dei\s+)?documenti(?:\s+.*)?|scheda\s+(?:di\s+)?raccolta\s+(?:dei\s+)?documenti(?:\s+.*)?",
        r"\bdocument\w+\b|\btrasmett\w+\b|\bcopia\b|\bfornir\w+\b",
        "Richiesta di documentazione",
        "titolo della richiesta e documenti necessari alla pratica (art. 27 Codice deontologico forense)",
        fonte="cnf_cdf_art_27_informazione_cliente",
    ),
    _atto(
        "ricognizione_debito",
        r"ricognizione\s+di\s+debito(?:\s+.*)?|riconoscimento\s+(?:del\s+)?debito(?:\s+.*)?|piano\s+di\s+rientro(?:\s+.*)?|promessa\s+di\s+pagamento(?:\s+.*)?",
        _DEBITO + r"|\brat\w+\b|\briconosc\w+\b|\b1988\b",
        "Ricognizione di debito e piano di rientro",
        "titolo dell'atto e riconoscimento del debito (art. 1988 c.c.)",
        fonte="normattiva_codice_civile", role="contratto", section="contratti", tipo=TipoDocumento.CONTRATTO,
    ),
    _atto(
        "transazione",
        r"(?:accordo\s+)?transa(?:zione|ttivo)(?:\s+(?:novativa|semplice|finale|stragiudiziale))?(?:\s+.*)?|accordo\s+(?:di\s+)?saldo\s+e\s+stralcio(?:\s+.*)?|accordo\s+(?:a\s+)?saldo\s+parcella(?:\s+.*)?",
        r"\breciproch\w+\s+concession\w+\b|\btransa\w+\b|\bsaldo\b|\bstralcio\b|\b1965\b|\bnulla\s+(?:altro\s+)?a\s+pretendere\b",
        "Accordo transattivo",
        "titolo dell'accordo e reciproche concessioni (art. 1965 c.c.)",
        fonte="normattiva_codice_civile", role="contratto", section="contratti", tipo=TipoDocumento.CONTRATTO,
    ),
    _atto(
        "proposta_transattiva",
        r"proposta\s+(?:transattiva|di\s+transazione|conciliativa|di\s+definizione\s+bonaria)(?:\s+.*)?",
        _DEBITO + r"|\bpropon\w+\b|\btransa\w+\b|\bdefini\w+\b",
        "Proposta transattiva",
        "titolo della proposta e definizione bonaria della lite (art. 1965 c.c.)",
        fonte="normattiva_codice_civile",
    ),
    _atto(
        "parere_legale",
        r"parere(?:\s+(?:legale|pro\s+veritate|sintetico|societario|scritto|su\s+operazione\s+straordinaria|in\s+(?:merito|ordine)\s+a.*))?|report\s+(?:di\s+)?due\s+diligence(?:\s+.*)?",
        r"\bquesit\w+\b|\bconclusion\w+\b|\bnormativ\w+\b|\bvalutazion\w+\b|\bsi\s+ritiene\b|\bdue\s+diligence\b",
        "Parere legale",
        "titolo del parere e attività di consulenza dell'avvocato (art. 2, comma 6, L. 247/2012)",
        fonte="normattiva_l_247_2012_ordinamento_forense", role="adempimento_studio", section="allegati",
        tipo=TipoDocumento.ALLEGATO, deposit_candidate=False,
    ),
    _atto(
        "informativa_cliente",
        r"(?:lettera|comunicazione|relazione)\s+al\s+cliente(?:\s+.*)?|informativa\s+(?:su(?:i)?\s+)?costi\s+e\s+rischi(?:\s+.*)?|chiusura\s+(?:della\s+)?pratica(?:\s+.*)?",
        _CLIENTE,
        "Comunicazione al cliente",
        "titolo della lettera e doveri di informazione verso il cliente (art. 27 Codice deontologico forense)",
        fonte="cnf_cdf_art_27_informazione_cliente", deposit_candidate=False,
    ),
    _atto(
        "richiesta_compensi",
        r"(?:richiesta\s+(?:di\s+)?fondo\s+spese|sollecito\s+(?:di\s+)?pagamento\s+(?:della\s+)?parcella|richiesta\s+di\s+acconto)(?:\s+.*)?",
        _CLIENTE + r"|\bcompens\w+\b|\bfondo\s+spese\b|\bacconto\b|\bparcell\w+\b",
        "Richiesta di compensi o fondo spese",
        "titolo della richiesta e pagamento del compenso o dell'anticipo (art. 29 Codice deontologico forense)",
        fonte="cnf_cdf_art_29_richiesta_pagamento", role="documento_economico", deposit_candidate=False,
    ),
    _atto(
        "atto_interno_studio",
        r"(?:checklist\s+pre-?azione|piano\s+(?:delle\s+)?attivit[aà](?:\s+della)?\s+pratica|verbale\s+(?:di\s+)?riunione(?:\s+con\s+il)?\s+cliente)(?:\s+.*)?",
        _CLIENTE + r"|\battivit\w+\b|\bscadenz\w+\b",
        "Atto interno della pratica",
        "titolo dell'atto e organizzazione diligente del mandato (art. 26 Codice deontologico forense)",
        fonte="cnf_cdf_art_26_adempimento_mandato", role="adempimento_studio", section="allegati",
        tipo=TipoDocumento.ALLEGATO, deposit_candidate=False,
    ),
)

__all__ = ["REGOLE"]
