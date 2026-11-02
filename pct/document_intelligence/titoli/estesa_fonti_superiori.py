"""Costituzione, diritto dell'Unione europea e CEDU, ADR e arbitrato, procedura civile e diritto civile non ancora coperti.

Regole d'identità dal titolo aggiunte il 02/11/2026 per coprire tutte le materie (direttiva dell'avvocato del
01/11/2026). Ogni regola cita la norma che definisce l'atto, registrata in `FONTI` con URL ufficiale e data di
consultazione.

Già coperti altrove e quindi non ripetuti qui: domanda di arbitrato, clausola compromissoria e compromesso,
nomina dell'arbitro, invito e risposta alla negoziazione assistita, convenzione e accordo di negoziazione
(famiglia), ricorso per consulenza tecnica preventiva (art. 696-bis), ricorso per sequestro, reclamo cautelare,
regolamento di competenza, ricorso possessorio, denuncia di nuova opera e di danno temuto, impugnazione di
delibera e verbale di assemblea condominiale, transazione, ricognizione di debito, ricorso per decreto
ingiuntivo (anche per oneri condominiali, art. 63 disp. att. c.c.).
"""

from __future__ import annotations

from typing import Any

from pct.fascicoli import TipoDocumento

from ._modello import RegolaTitolo, regola

_VERIFICA = "testo vigente consultato su Normattiva il 02/11/2026"
_NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"
_CPC = "regio.decreto:1940-10-28;1443~art"
_CC = "regio.decreto:1942-03-16;262~art"
_DISP_ATT_CC = "regio.decreto:1942-03-30;318~art"
_L87 = "legge:1953-03-11;87~art"
_COM = "decreto.legislativo:2010-03-15;66~art"
_L24 = "legge:2017-03-08;24~art"
_P = "estesa_fonti_superiori_"


def _fonte(label: str, urn: str) -> dict[str, Any]:
    return {"label": label, "official_url": _NORMATTIVA + urn, "verification_status": _VERIFICA, "source_type": "normativa"}


FONTI: dict[str, dict[str, Any]] = {
    # Giustizia costituzionale
    _P + "l87_1953_incidentale": _fonte("L. 87/1953, art. 23: questione di legittimità costituzionale sollevata nel giudizio e ordinanza di rimessione", _L87 + "23"),
    _P + "l87_1953_pronunce": _fonte("L. 87/1953, art. 18: la Corte costituzionale giudica con sentenza, gli altri provvedimenti con ordinanza", _L87 + "18"),
    _P + "l87_1953_costituzione_parti": _fonte("L. 87/1953, art. 25: pubblicazione dell'ordinanza, costituzione delle parti e intervento", _L87 + "25"),
    _P + "l87_1953_via_principale": _fonte("L. 87/1953, artt. 31-33: questioni di legittimità costituzionale in via principale (art. 127 Cost.)", _L87 + "31"),
    _P + "l87_1953_conflitti": _fonte("L. 87/1953, artt. 37-42: conflitti di attribuzione tra poteri dello Stato e tra Stato e Regioni (art. 134 Cost.)", _L87 + "37"),
    # Unione europea e CEDU
    _P + "tfue_l130_2008": _fonte("L. 130/2008, ratifica del Trattato di Lisbona: TFUE artt. 227, 258, 263 e 267 e Statuto della Corte di giustizia", "legge:2008-08-02;130"),
    _P + "cedu_l848_1955": _fonte("L. 848/1955, ratifica della CEDU: artt. 34 (ricorsi individuali), 39 (composizione amichevole), 44 e 46 (sentenze)", "legge:1955-08-04;848"),
    _P + "cpc_391_quater": _fonte("c.p.c., art. 391-quater: revocazione per contrarietà alla Convenzione europea dei diritti dell'uomo", _CPC + "391quater"),
    # Arbitrato e negoziazione assistita
    _P + "cpc_815_ricusazione_arbitri": _fonte("c.p.c., art. 815: ricusazione degli arbitri", _CPC + "815"),
    _P + "cpc_823_lodo": _fonte("c.p.c., artt. 823-824-bis: deliberazione, requisiti ed efficacia del lodo", _CPC + "823"),
    _P + "cpc_825_esecutorieta": _fonte("c.p.c., art. 825: deposito del lodo e decreto di esecutorietà", _CPC + "825"),
    _P + "cpc_828_impugnazione_lodo": _fonte("c.p.c., artt. 827-829: impugnazione del lodo per nullità", _CPC + "828"),
    _P + "cpc_839_lodi_stranieri": _fonte("c.p.c., art. 839: riconoscimento ed esecuzione dei lodi stranieri", _CPC + "839"),
    _P + "dl_132_2014_art4": _fonte("D.L. 132/2014, art. 4: non accettazione dell'invito e dichiarazione di mancato accordo certificata dagli avvocati", "decreto.legge:2014-09-12;132~art4"),
    # Procedura civile
    _P + "cpc_52_ricusazione": _fonte("c.p.c., artt. 51-54: astensione e ricusazione del giudice", _CPC + "52"),
    _P + "cpc_192_ricusazione_ctu": _fonte("c.p.c., art. 192: astensione e ricusazione del consulente tecnico", _CPC + "192"),
    _P + "cpc_214_disconoscimento": _fonte("c.p.c., artt. 214-215: disconoscimento della scrittura privata", _CPC + "214"),
    _P + "cpc_216_verificazione": _fonte("c.p.c., art. 216: istanza di verificazione della scrittura privata", _CPC + "216"),
    _P + "cpc_221_querela_falso": _fonte("c.p.c., art. 221: proposizione della querela di falso", _CPC + "221"),
    _P + "cpc_692_istruzione_preventiva": _fonte("c.p.c., art. 692: assunzione preventiva di testimoni", _CPC + "692"),
    _P + "cpc_696_atp": _fonte("c.p.c., art. 696: accertamento tecnico e ispezione giudiziale preventivi", _CPC + "696"),
    _P + "cpc_186_bis": _fonte("c.p.c., art. 186-bis: ordinanza per il pagamento di somme non contestate", _CPC + "186bis"),
    _P + "cpc_186_ter": _fonte("c.p.c., art. 186-ter: istanza e ordinanza di ingiunzione in corso di causa", _CPC + "186ter"),
    _P + "cpc_186_quater": _fonte("c.p.c., art. 186-quater: ordinanza successiva alla chiusura dell'istruzione", _CPC + "186quater"),
    _P + "cpc_671_sequestro": _fonte("c.p.c., artt. 670-671: sequestro giudiziario e conservativo", _CPC + "671"),
    _P + "cpc_703_possessorio": _fonte("c.p.c., art. 703: provvedimenti sulle domande di reintegrazione e manutenzione nel possesso", _CPC + "703"),
    # Diritto civile: proprietà, condominio, contratti
    _P + "cc_948_rivendicazione": _fonte("c.c., art. 948: azione di rivendicazione", _CC + "948"),
    _P + "cc_949_negatoria": _fonte("c.c., art. 949: azione negatoria", _CC + "949"),
    _P + "cc_950_confini": _fonte("c.c., artt. 950-951: regolamento di confini e apposizione di termini", _CC + "950"),
    _P + "cc_1079_confessoria": _fonte("c.c., art. 1079: accertamento della servitù (azione confessoria)", _CC + "1079"),
    _P + "cc_1158_usucapione": _fonte("c.c., artt. 1158-1159-bis: usucapione dei beni immobili", _CC + "1158"),
    _P + "cc_1129_amministratore": _fonte("c.c., art. 1129: nomina, revoca e obblighi dell'amministratore di condominio", _CC + "1129"),
    _P + "cc_1130_bis_rendiconto": _fonte("c.c., art. 1130-bis: rendiconto condominiale", _CC + "1130bis"),
    _P + "disp_att_cc_68_tabelle": _fonte("disp. att. c.c., art. 68: tabelle millesimali", _DISP_ATT_CC + "68"),
    _P + "cc_1351_preliminare": _fonte("c.c., art. 1351: contratto preliminare", _CC + "1351"),
    _P + "cc_1470_vendita": _fonte("c.c., art. 1470: vendita", _CC + "1470"),
    _P + "cc_1552_permuta": _fonte("c.c., art. 1552: permuta", _CC + "1552"),
        _P + "cc_1703_mandato": _fonte("c.c., art. 1703: mandato", _CC + "1703"),
    _P + "cc_1803_comodato": _fonte("c.c., art. 1803: comodato", _CC + "1803"),
    _P + "cc_2222_opera": _fonte("c.c., art. 2222: contratto d'opera", _CC + "2222"),
    _P + "cc_1260_cessione": _fonte("c.c., art. 1260: cedibilità dei crediti", _CC + "1260"),
    _P + "cc_1264_notifica_cessione": _fonte("c.c., art. 1264: efficacia della cessione riguardo al debitore ceduto", _CC + "1264"),
    _P + "cc_1199_quietanza": _fonte("c.c., art. 1199: diritto del debitore alla quietanza", _CC + "1199"),
    # Responsabilità sanitaria
    _P + "l24_2017_art8": _fonte("L. 24/2017, art. 8: tentativo obbligatorio di conciliazione con ricorso ex art. 696-bis c.p.c.", _L24 + "8"),
    _P + "l24_2017_art12": _fonte("L. 24/2017, art. 12: azione diretta del danneggiato contro l'impresa di assicurazione", _L24 + "12"),
    _P + "l24_2017_art13": _fonte("L. 24/2017, art. 13: comunicazione all'esercente la professione sanitaria del giudizio", _L24 + "13"),
    # Ordinamento militare
    _P + "com_1370_contestazione": _fonte("D.Lgs. 66/2010, art. 1370: contestazione degli addebiti e diritto di difesa del militare", _COM + "1370"),
    _P + "com_1357_sanzioni": _fonte("D.Lgs. 66/2010, artt. 1357-1358: sanzioni disciplinari di stato e di corpo", _COM + "1357"),
    _P + "com_1376_inchiesta": _fonte("D.Lgs. 66/2010, art. 1376: inizio del procedimento disciplinare di stato con l'inchiesta formale", _COM + "1376"),
    _P + "com_1366_ricorso_gerarchico": _fonte("D.Lgs. 66/2010, art. 1366: ricorso gerarchico avverso le sanzioni disciplinari di corpo", _COM + "1366"),
}

_CODA = r"(?:\s+.*)?"
_ART = r"(?:ex|ai\s+sensi\s+dell.?|a\s+norma\s+dell.?)\s*art(?:icolo|\.)?\s*"
_L_24 = r"(?:della\s+)?(?:l\.?|legge)\s*(?:n\.?\s*)?24(?:/|\s+del\s+)2017"
_DELL = r"dell.?\s*"
_CIVILE = r"\bc\.\s*p\.\s*c\.|\bcodice\s+di\s+procedura\s+civile\b"
_MILITARE = (
    r"\bmilitar\w*\b|\b66/2010\b|\bordinamento\s+militare\b|\bcomandante\s+(?:di\s+corpo|del\s+reparto)\b|"
    r"\bconsegna\s+di\s+rigore\b|\bcarabinieri\b|\besercito\b|\bmarina\s+militare\b|\baeronautica\b"
)
_UE = (
    r"\b267\b|\btfue\b|\bunione\s+europea\b|\bdiritto\s+(?:dell.?\s*unione|europeo|comunitario)\b|"
    r"\bcorte\s+di\s+giustizia\s+(?:dell.?\s*unione|ue|europea)\b"
)

# Presentazione per famiglia di documento: ruolo, sezione, tipo, ruolo nella busta, candidato al deposito.
_ATTO = ("atto_principale", "atti", TipoDocumento.RICORSO, "atto_principale", True)
_CITAZIONE = ("atto_principale", "atti", TipoDocumento.CITAZIONE, "atto_principale", True)
_ATTO_ESTERNO = ("atto_principale", "atti", TipoDocumento.RICORSO, "fuori_busta", False)
_DIFESA = ("atto_difensivo", "atti", TipoDocumento.MEMORIA, "atto_principale", True)
_DIFESA_ESTERNA = ("atto_difensivo", "atti", TipoDocumento.MEMORIA, "fuori_busta", False)
_ISTANZA = ("istanza", "atti", TipoDocumento.MEMORIA, "atto_principale", True)
_ORDINANZA = ("provvedimento", "provvedimenti", TipoDocumento.ORDINANZA, "fuori_busta", False)
_DECRETO = ("provvedimento", "provvedimenti", TipoDocumento.DECRETO, "fuori_busta", False)
_PRONUNCIA = ("precedente_giurisprudenziale", "allegati", TipoDocumento.SENTENZA, "allegato", True)
_LODO = ("provvedimento", "provvedimenti", TipoDocumento.SENTENZA, "allegato", True)
_PROVV_AMM = ("atto_amministrativo", "provvedimenti", TipoDocumento.ALLEGATO, "allegato", True)
_CONTRATTO = ("contratto", "contratti", TipoDocumento.CONTRATTO, "allegato", True)
_LETTERA = ("corrispondenza_stragiudiziale", "comunicazioni", TipoDocumento.COMUNICAZIONE, "allegato", True)
_VERBALE_ADR = ("verbale_adr", "allegati", TipoDocumento.VERBALE, "allegato", True)
_ECONOMICO = ("documento_economico", "allegati", TipoDocumento.ALLEGATO, "allegato", True)
_CONDOMINIO = ("regolamento", "allegati", TipoDocumento.ALLEGATO, "allegato", True)
_ACCORDO = ("accordo", "allegati", TipoDocumento.ALLEGATO, "allegato", True)


def _r(id: str, titolo: str, conferma: str, label: str, evidence: str, fonte: str, forma: tuple) -> RegolaTitolo:
    role, section, tipo, deposit_role, candidato = forma
    return regola("sup_" + id, titolo, conferma, label, role=role, section=section, tipo=tipo, fonte=_P + fonte,
                  evidence=evidence, deposit_role=deposit_role, deposit_candidate=candidato)


_GIUSTIZIA_COSTITUZIONALE = (
    _r("ordinanza_rimessione_corte_costituzionale",
       r"ordinanza\s+(?:di\s+)?(?:rimessione|trasmissione\s+degli\s+atti|promovimento\s+del\s+giudizio\s+di\s+legittimit[aà]\s+costituzionale)"
       r"(?:\s+(?:degli\s+atti\s+)?(?:alla|innanzi\s+alla|davanti\s+alla)\s+corte\s+costituzionale|\s+(?:della\s+)?questione\s+di\s+legittimit[aà]\s+costituzionale)?" + _CODA,
       r"\blegittimit[aà]\s+costituzional\w*\b|\bnon\s+manifestamente\s+infondat\w*\b|\b87/1953\b|\bcorte\s+costituzionale\b",
       "Ordinanza di rimessione alla Corte costituzionale",
       "ordinanza del giudice che solleva la questione di legittimità costituzionale (art. 23 L. 87/1953)",
       "l87_1953_incidentale", _ORDINANZA),
    _r("eccezione_legittimita_costituzionale",
       r"(?:istanza|eccezione|memoria)\s+(?:di|per\s+(?:sollevare\s+)?(?:la\s+)?)\s*(?:questione\s+di\s+)?(?:il)?legittimit[aà]\s+costituzionale" + _CODA,
       r"\bnon\s+manifestamente\s+infondat\w*\b|\brilevan\w+\b|\bart(?:icolo|\.)?\s*23\b|\b87/1953\b|\bparametr\w+\s+costituzional\w*\b",
       "Eccezione di legittimità costituzionale",
       "istanza di parte che solleva la questione nel giudizio (art. 23 L. 87/1953)",
       "l87_1953_incidentale", _DIFESA),
    _r("sentenza_corte_costituzionale",
       r"sentenza\s+(?:n\.?\s*\d+(?:\s*/\s*\d{4})?\s+(?:anno\s+\d{4}\s+)?)?(?:della\s+)?corte\s+costituzionale" + _CODA,
       r"\blegittimit[aà]\s+costituzional\w*\b|\bconflitto\s+di\s+attribuzion\w+\b|\bpalazzo\s+della\s+consulta\b|\bordinanza\s+di\s+rimessione\b",
       "Sentenza della Corte costituzionale",
       "pronuncia definitiva della Corte costituzionale (art. 18 L. 87/1953; art. 136 Cost.)",
       "l87_1953_pronunce", _PRONUNCIA),
    _r("ordinanza_corte_costituzionale",
       r"ordinanza\s+(?:n\.?\s*\d+(?:\s*/\s*\d{4})?\s+(?:anno\s+\d{4}\s+)?)?(?:della\s+)?corte\s+costituzionale" + _CODA,
       r"\blegittimit[aà]\s+costituzional\w*\b|\binammissibil\w+\b|\brestituzione\s+degli\s+atti\b|\bpalazzo\s+della\s+consulta\b",
       "Ordinanza della Corte costituzionale",
       "provvedimento della Corte adottato con ordinanza (art. 18 L. 87/1953)",
       "l87_1953_pronunce", _PRONUNCIA),
    _r("costituzione_corte_costituzionale",
       r"(?:atto\s+di\s+|memoria\s+di\s+)?(?:costituzione|intervento)(?:\s+o\s+(?:di\s+)?(?:intervento|costituzione))?\s+(?:in\s+giudizio\s+|nel\s+giudizio\s+(?:di\s+legittimit[aà]\s+costituzionale\s+)?)?"
       r"(?:(?:davanti|dinanzi|innanzi)\s+alla\s+corte\s+costituzionale|di\s+legittimit[aà]\s+costituzionale)" + _CODA,
       r"\bart(?:icolo|\.)?\s*25\b|\b87/1953\b|\bventi\s+giorni\b|\bgazzetta\s+ufficiale\b|\bordinanza\s+di\s+rimessione\b|\bnorme\s+integrative\b",
       "Atto di costituzione o di intervento davanti alla Corte costituzionale",
       "costituzione della parte del giudizio a quo o intervento (art. 25 L. 87/1953)",
       "l87_1953_costituzione_parti", _DIFESA_ESTERNA),
    _r("ricorso_via_principale",
       r"ricorso\s+in\s+via\s+principale(?:\s+(?:alla|davanti\s+alla|dinanzi\s+alla)\s+corte\s+costituzionale)?" + _CODA
       + r"|ricorso\s+per\s+(?:questione\s+di\s+)?legittimit[aà]\s+costituzionale(?:\s+in\s+via\s+principale)?" + _CODA,
       r"\b127\b|\bregion\w+\b|\bpresidente\s+del\s+consiglio\s+dei\s+ministri\b|\b87/1953\b|\bprovinc\w+\s+autonom\w+\b",
       "Ricorso in via principale alla Corte costituzionale",
       "impugnazione diretta di una legge statale o regionale (art. 127 Cost.; artt. 31-33 L. 87/1953)",
       "l87_1953_via_principale", _ATTO_ESTERNO),
    _r("conflitto_attribuzione",
       r"ricorso\s+(?:per\s+)?(?:la\s+risoluzione\s+del\s+)?conflitto\s+(?:di\s+attribuzion[ei]|tra\s+poteri)" + _CODA
       + r"|conflitto\s+di\s+attribuzion[ei]\s+(?:tra|fra)\s+(?:poteri\s+dello\s+stato|stato\s+e\s+region\w+)" + _CODA,
       r"\b134\b|\bart(?:icolo|\.)?\s*(?:3[7-9]|4[0-2])\b|\bpoteri\s+dello\s+stato\b|\bregion\w+\b|\b87/1953\b|\bcorte\s+costituzionale\b",
       "Ricorso per conflitto di attribuzione",
       "conflitto tra poteri dello Stato o tra Stato e Regioni (art. 134 Cost.; artt. 37-42 L. 87/1953)",
       "l87_1953_conflitti", _ATTO_ESTERNO),
)

_UNIONE_EUROPEA_E_CEDU = (
    _r("pronuncia_corte_giustizia_ue",
       r"(?:sentenza|ordinanza)\s+(?:della\s+)?corte\s+(?:di\s+giustizia\s+(?:" + _DELL + r"unione\s+europea|ue|europea|delle\s+comunit[aà]\s+europee)|ue|europea\s+di\s+giustizia)" + _CODA
       + r"|(?:sentenza|ordinanza)\s+(?:del\s+)?tribunale\s+" + _DELL + r"unione\s+europea" + _CODA,
       r"\bunione\s+europea\b|\btfue\b|\becli:eu\b|\bavvocato\s+generale\b|\bpronuncia\s+pregiudiziale\b|\bgrande\s+sezione\b|\bcausa\s+[ct]-\d+",
       "Sentenza della Corte di giustizia dell'Unione europea",
       "pronuncia della Corte di giustizia o del Tribunale dell'Unione (artt. 263 e 267 TFUE)",
       "tfue_l130_2008", _PRONUNCIA),
    _r("ordinanza_rinvio_pregiudiziale",
       r"(?![^\n]*cassazion)(?:ordinanza\s+(?:di\s+)?rinvio\s+pregiudiziale|domanda\s+di\s+pronuncia\s+pregiudiziale|"
       r"ordinanza\s+di\s+rinvio\s+alla\s+corte\s+di\s+giustizia)" + _CODA,
       _UE, "Ordinanza di rinvio pregiudiziale alla Corte di giustizia UE",
       "domanda del giudice nazionale sull'interpretazione o validità del diritto dell'Unione (art. 267 TFUE)",
       "tfue_l130_2008", _ORDINANZA),
    _r("istanza_rinvio_pregiudiziale",
       r"(?![^\n]*cassazion)(?:istanza|richiesta|memoria)\s+(?:di|per\s+(?:il\s+)?)\s*rinvio\s+pregiudiziale" + _CODA,
       _UE, "Istanza di rinvio pregiudiziale alla Corte di giustizia UE",
       "richiesta di parte al giudice di sottoporre la questione alla Corte di giustizia (art. 267 TFUE)",
       "tfue_l130_2008", _DIFESA),
    _r("osservazioni_corte_giustizia",
       r"osservazioni\s+scritte\s+(?:nella\s+causa\s+c-\d+/\d+|(?:davanti|dinanzi|innanzi)\s+alla\s+corte\s+di\s+giustizia|nel\s+procedimento\s+pregiudiziale)" + _CODA,
       r"\bstatuto\s+della\s+corte\b|\bpregiudizial\w+\b|\bunione\s+europea\b|\bcausa\s+c-\d+|\bart(?:icolo|\.)?\s*23\b",
       "Osservazioni scritte davanti alla Corte di giustizia UE",
       "osservazioni delle parti nel procedimento pregiudiziale (art. 23 Statuto della Corte; art. 267 TFUE)",
       "tfue_l130_2008", _DIFESA_ESTERNA),
    _r("ricorso_annullamento_ue",
       r"ricorso\s+(?:di|per|in)\s+annullamento\s+(?:" + _ART + r"263\s+tfue|(?:davanti|dinanzi|innanzi)\s+(?:alla\s+corte\s+di\s+giustizia|al\s+tribunale\s+" + _DELL + r"unione\s+europea))" + _CODA,
       r"\b263\b|\btfue\b|\bunione\s+europea\b|\bcommission\w+\b|\bregolament\w+\b",
       "Ricorso di annullamento ex art. 263 TFUE",
       "impugnazione di un atto delle istituzioni dell'Unione (art. 263 TFUE)",
       "tfue_l130_2008", _ATTO_ESTERNO),
    _r("denuncia_commissione_europea",
       r"(?:denuncia|reclamo|esposto)\s+alla\s+commissione\s+europea" + _CODA
       + r"|denuncia\s+(?:per\s+)?(?:violazione|inadempimento)\s+del\s+diritto\s+(?:" + _DELL + r"unione|europeo|comunitario)" + _CODA,
       r"\b258\b|\btfue\b|\binfrazion\w+\b|\bstato\s+membro\b|\bdiritto\s+(?:dell.?\s*unione|europeo)\b|\binadempiment\w+\b",
       "Denuncia alla Commissione europea",
       "segnalazione dell'inadempimento di uno Stato membro (art. 258 TFUE)",
       "tfue_l130_2008", _LETTERA),
    _r("petizione_parlamento_europeo",
       r"petizione\s+al\s+parlamento\s+europeo" + _CODA,
       r"\b227\b|\btfue\b|\bunione\s+europea\b|\bcommissione\s+per\s+le\s+petizioni\b|\bcittadin\w+\b",
       "Petizione al Parlamento europeo",
       "petizione del cittadino su materie di competenza dell'Unione (art. 227 TFUE)",
       "tfue_l130_2008", _LETTERA),
    _r("ricorso_cedu",
       r"ricorso\s+(?:individuale\s+)?(?:alla|davanti\s+alla|dinanzi\s+alla|innanzi\s+alla)\s+corte\s+(?:europea\s+dei\s+diritti\s+" + _DELL + r"uomo|edu)" + _CODA
       + r"|ricorso\s+(?:individuale\s+)?" + _ART + r"34\s+(?:della\s+)?(?:cedu|convenzione\s+europea)" + _CODA
       + r"|formulario\s+di\s+ricorso\s+(?:alla\s+corte\s+europea|cedu)" + _CODA,
       r"\bconvenzione\s+europea\b|\bcedu\b|\bstrasburgo\b|\bart(?:icolo|\.)?\s*3[45]\b|\bprotocoll\w+\b|\bdiritti\s+dell.?\s*uomo\b",
       "Ricorso alla Corte europea dei diritti dell'uomo (art. 34 CEDU)",
       "ricorso individuale per violazione della Convenzione (artt. 34 e 35 CEDU)",
       "cedu_l848_1955", _ATTO_ESTERNO),
    _r("pronuncia_corte_edu",
       r"(?:sentenza|decisione)\s+(?:della\s+)?corte\s+(?:europea\s+dei\s+diritti\s+" + _DELL + r"uomo|edu)" + _CODA,
       r"\bconvenzione\b|\bstrasburgo\b|\bricors\w+\s+n\.|\bviolazion\w+\b|\bcedu\b",
       "Sentenza della Corte europea dei diritti dell'uomo",
       "sentenza o decisione della Corte europea (artt. 44 e 46 CEDU)",
       "cedu_l848_1955", _PRONUNCIA),
    _r("regolamento_amichevole_cedu",
       r"(?:dichiarazione\s+di\s+)?(?:composizione|regolamento)\s+amichevole" + _CODA
       + r"|dichiarazione\s+unilaterale\s+del\s+governo" + _CODA,
       r"\bart(?:icolo|\.)?\s*(?:37|39)\b|\bcorte\s+europea\b|\bcedu\b|\bconvenzione\s+europea\b|\bstrasburgo\b",
       "Regolamento amichevole davanti alla Corte EDU (art. 39 CEDU)",
       "composizione amichevole del ricorso davanti alla Corte europea (art. 39 CEDU)",
       "cedu_l848_1955", _ACCORDO),
    _r("revocazione_cedu",
       r"(?:ricorso\s+(?:per|di)\s+|istanza\s+di\s+|atto\s+di\s+)?revocazione\s+(?:" + _ART + r"391[\s-]*quater|per\s+contrariet[aà]\s+alla\s+(?:cedu|convenzione\s+europea))" + _CODA,
       r"\b391\b|\bcorte\s+europea\b|\bcedu\b|\bconvenzione\s+europea\b|\bstrasburgo\b",
       "Ricorso per revocazione per contrarietà alla CEDU (art. 391-quater c.p.c.)",
       "revocazione della decisione dopo la sentenza della Corte europea (art. 391-quater c.p.c.)",
       "cpc_391_quater", _ATTO),
)

_ARBITRATO_E_NEGOZIAZIONE = (
    _r("lodo_arbitrale",
       r"lodo(?:\s+arbitrale)?(?:\s+(?:rituale|irrituale|definitivo|non\s+definitivo|parziale|di\s+equit[aà]))?" + _CODA,
       r"\barbitr\w+\b|\bcollegio\s+arbitrale\b|\bart(?:icolo|\.)?\s*82[0-4]\b",
       "Lodo arbitrale",
       "decisione degli arbitri con i requisiti di legge (artt. 823 e 824-bis c.p.c.)",
       "cpc_823_lodo", _LODO),
    _r("impugnazione_lodo",
       r"(?:atto\s+di\s+citazione\s+(?:in|per|di)\s+|atto\s+di\s+)?impugnazione\s+(?:per\s+nullit[aà]\s+)?(?:del\s+|avverso\s+(?:il\s+)?)?lodo" + _CODA,
       r"\bart(?:icolo|\.)?\s*8(?:2[789]|3[01])\b|\bnullit\w+\b|\bnull[oa]\b|\bcorte\s+d.?\s*appello\b",
       "Impugnazione del lodo arbitrale (artt. 828-829 c.p.c.)",
       "impugnazione per nullità del lodo davanti alla Corte d'appello (artt. 827-829 c.p.c.)",
       "cpc_828_impugnazione_lodo", _CITAZIONE),
    _r("riconoscimento_lodo_straniero",
       r"(?:ricorso|istanza)\s+(?:" + _ART + r"839\s*(?:c\.?\s*p\.?\s*c\.?)?\s*-?\s*)?(?:(?:per|di)\s+(?:il\s+|l.?\s*)?)?(?:riconoscimento|exequatur)\s+(?:e\s+(?:l.?\s*)?esecuzione\s+)?(?:del\s+|di\s+)?lodo\s+(?:arbitrale\s+)?stranier[oi]" + _CODA
       + r"|exequatur\s+(?:del\s+)?lodo\s+stranier[oi]" + _CODA,
       r"\b839\b|\b840\b|\bconvenzione\s+di\s+new\s+york\b|\bstranier\w+\b",
       "Ricorso per il riconoscimento del lodo straniero (art. 839 c.p.c.)",
       "riconoscimento ed esecuzione del lodo straniero (art. 839 c.p.c.)",
       "cpc_839_lodi_stranieri", _ATTO),
    _r("ricorso_esecutorieta_lodo",
       r"(?:ricorso|istanza)\s+(?:per\s+(?:la\s+|l.?\s*)?(?:dichiarazione\s+di\s+)?(?:esecutivit[aà]|esecutoriet[aà])\s+del\s+lodo|" + _ART + r"825)" + _CODA
       + r"|deposito\s+del\s+lodo\s+" + _ART + r"825" + _CODA,
       r"\b825\b|\blodo\b|\besecutiv\w+\b",
       "Ricorso per l'esecutività del lodo (art. 825 c.p.c.)",
       "deposito del lodo e richiesta del decreto di esecutorietà (art. 825 c.p.c.)",
       "cpc_825_esecutorieta", _ATTO),
    _r("decreto_esecutorieta_lodo",
       r"decreto\s+(?:di\s+)?(?:esecutivit[aà]|esecutoriet[aà])\s+del\s+lodo" + _CODA
       + r"|decreto\s+che\s+dichiara\s+esecutivo\s+il\s+lodo" + _CODA
       + r"|decreto\s+" + _ART + r"825" + _CODA,
       r"\b825\b|\besecutiv\w+\b|\blodo\b",
       "Decreto di esecutività del lodo (art. 825 c.p.c.)",
       "decreto del tribunale che dichiara esecutivo il lodo (art. 825 c.p.c.)",
       "cpc_825_esecutorieta", _DECRETO),
    _r("ricusazione_arbitro",
       r"(?:ricorso|istanza)\s+(?:di|per\s+(?:la\s+)?)\s*ricusazione\s+(?:" + _DELL + r"|del\s+|degli\s+)?arbitr[oi]" + _CODA,
       r"\b815\b|\barbitr\w+\b|\bricusa\w+\b",
       "Istanza di ricusazione dell'arbitro (art. 815 c.p.c.)",
       "ricusazione dell'arbitro per i motivi di legge (art. 815 c.p.c.)",
       "cpc_815_ricusazione_arbitri", _ATTO),
    _r("mancato_accordo_negoziazione",
       r"(?:dichiarazione|verbale|attestazione|certificazione)\s+di\s+(?:mancato\s+accordo|mancata\s+adesione|mancata\s+risposta)\s+(?:[\w'’]+\s+){0,4}negoziazione\s+assistita" + _CODA,
       r"\b132/2014\b|\bart(?:icolo|\.)?\s*4\b|\bavvocat\w+\b|\bcertific\w+\b",
       "Dichiarazione di mancato accordo nella negoziazione assistita",
       "dichiarazione di mancato accordo certificata dagli avvocati (art. 4 D.L. 132/2014)",
       "dl_132_2014_art4", _VERBALE_ADR),
)

_PROCEDURA_CIVILE = (
    _r("ricusazione_ctu",
       r"(?:ricorso|istanza|atto)\s+(?:di|per\s+(?:la\s+)?)\s*ricusazione\s+(?:del\s+|" + _DELL + r")?(?:consulente\s+tecnico(?:\s+d.?\s*ufficio)?|c\.?\s*t\.?\s*u\.?)" + _CODA,
       r"\b192\b|\b63\b|\bconsulent\w+\b|\bc\.?t\.?u\b",
       "Istanza di ricusazione del consulente tecnico d'ufficio (art. 192 c.p.c.)",
       "ricusazione del consulente per i motivi dell'art. 51 (art. 192 c.p.c.)",
       "cpc_192_ricusazione_ctu", _ISTANZA),
    _r("ricusazione_giudice",
       r"(?:ricorso|istanza|atto)\s+(?:di|per\s+(?:la\s+)?)\s*ricusazione(?:\s+del\s+(?:giudice|magistrato|collegio|presidente))?" + _CODA,
       r"\bart(?:icolo|\.)?\s*5[1-4]\b|" + _CIVILE + r"|\bgiudice\s+istruttore\b",
       "Istanza di ricusazione del giudice (art. 52 c.p.c.)",
       "ricusazione del giudice nei casi di astensione obbligatoria (artt. 51-52 c.p.c.)",
       "cpc_52_ricusazione", _ISTANZA),
    _r("querela_falso",
       r"(?:atto\s+di\s+(?:citazione\s+(?:per|in)\s+)?|ricorso\s+(?:per|di)\s+|istanza\s+(?:di\s+)?(?:proposizione\s+(?:di|della)\s+)?|atto\s+di\s+proposizione\s+(?:di|della)\s+)?querela\s+di\s+falso" + _CODA,
       r"\b22[1-7]\b|\bfals\w+\b",
       "Querela di falso (art. 221 c.p.c.)",
       "querela di falso contro l'atto pubblico o la scrittura privata (art. 221 c.p.c.)",
       "cpc_221_querela_falso", _ISTANZA),
    _r("disconoscimento_scrittura",
       r"(?:atto\s+di\s+|dichiarazione\s+di\s+|memoria\s+di\s+)?disconoscimento\s+(?:della\s+|di\s+)?(?:scrittura\s+privata|sottoscrizione|firma|conformit[aà])" + _CODA,
       r"\b21[45]\b|\b2719\b|\bscrittur\w+\b|\bsottoscrizion\w+\b|\bdisconosc\w+\b",
       "Disconoscimento della scrittura privata (art. 214 c.p.c.)",
       "disconoscimento della scrittura o della sottoscrizione (artt. 214-215 c.p.c.)",
       "cpc_214_disconoscimento", _DIFESA),
    _r("istanza_verificazione",
       r"(?:istanza|domanda|ricorso)\s+(?:di|per\s+(?:la\s+)?)\s*verificazione\s+(?:della\s+|di\s+)?(?:scrittura\s+privata|sottoscrizione)" + _CODA,
       r"\b21[6-9]\b|\bscrittur\w+\b|\bdisconosc\w+\b|\bsottoscrizion\w+\b",
       "Istanza di verificazione della scrittura privata (art. 216 c.p.c.)",
       "verificazione della scrittura disconosciuta (art. 216 c.p.c.)",
       "cpc_216_verificazione", _ISTANZA),
    _r("ctp_sanitaria",
       r"ricorso\s+(?:per\s+)?(?:consulenza\s+tecnica\s+preventiva|accertamento\s+tecnico\s+preventivo)\s+"
       r"(?:" + _ART + r"8\s+" + _L_24 + r"|in\s+materia\s+di\s+responsabilit[aà]\s+(?:sanitaria|medica|professionale\s+sanitaria)|per\s+responsabilit[aà]\s+(?:sanitaria|medica))" + _CODA,
       r"\b24/2017\b|\bsanitari\w+\b|\bmedic\w+\b|\bospedal\w+\b",
       "Ricorso per consulenza tecnica preventiva in materia di responsabilità sanitaria (art. 8 L. 24/2017)",
       "condizione di procedibilità dell'azione di responsabilità sanitaria (art. 8 L. 24/2017; art. 696-bis c.p.c.)",
       "l24_2017_art8", _ATTO),
    _r("ricorso_atp",
       r"ricorso\s+(?:per\s+)?(?:accertamento\s+tecnico\s+preventivo|ispezione\s+giudiziale\s+preventiva|a\.?\s*t\.?\s*p\.?)(?![^\n]*(?:696[\s-]*bis|obbligatori|445))" + _CODA
       + r"|ricorso\s+" + _ART + r"696(?![\s-]*bis)" + _CODA,
       r"\b696(?![\s-]*bis)\b|\bstato\s+dei\s+luoghi\b|\burgen\w+\b|\bpericolo\b|\bdispersion\w+\b",
       "Ricorso per accertamento tecnico preventivo (art. 696 c.p.c.)",
       "accertamento tecnico o ispezione giudiziale per urgenza (art. 696 c.p.c.)",
       "cpc_696_atp", _ATTO),
    _r("assunzione_preventiva_testimoni",
       r"ricorso\s+(?:per\s+(?:l.?\s*)?)?(?:assunzione\s+preventiva\s+(?:di|dei)\s+testimon[ei]|audizione\s+preventiva\s+(?:di|dei)\s+testimon[ei]|istruzione\s+preventiva)" + _CODA
       + r"|ricorso\s+" + _ART + r"692" + _CODA,
       r"\b69[2-9]\b|\btestimon\w+\b|\bfondato\s+timore\b|\burgen\w+\b",
       "Ricorso per assunzione preventiva di testimoni (art. 692 c.p.c.)",
       "assunzione preventiva di testimoni per fondato timore (art. 692 c.p.c.)",
       "cpc_692_istruzione_preventiva", _ATTO),
    _r("ordinanza_186_bis",
       r"ordinanza\s+(?:(?:di|per\s+il)\s+pagamento\s+(?:delle\s+|di\s+)?somme\s+non\s+contestate|" + _ART + r"186[\s-]*bis)" + _CODA,
       r"\b186\b|\bnon\s+contestat\w+\b|\bpagament\w+\b",
       "Ordinanza di pagamento di somme non contestate (art. 186-bis c.p.c.)",
       "ordinanza per il pagamento delle somme non contestate (art. 186-bis c.p.c.)",
       "cpc_186_bis", _ORDINANZA),
    _r("ordinanza_186_ter",
       r"ordinanza\s+(?:di\s+)?(?:ingiunzione\s+)?" + _ART + r"186[\s-]*ter" + _CODA,
       r"\b186\b|\bingiun\w+\b|\b63[34]\b",
       "Ordinanza di ingiunzione ex art. 186-ter c.p.c.",
       "ordinanza di ingiunzione pronunciata in corso di causa (art. 186-ter c.p.c.)",
       "cpc_186_ter", _ORDINANZA),
    _r("ordinanza_186_quater",
       r"ordinanza\s+(?:successiva\s+alla\s+chiusura\s+" + _DELL + r"istruzione|" + _ART + r"186[\s-]*quater)" + _CODA,
       r"\b186\b|\bistruzion\w+\b|\bpagament\w+\b|\bconsegna\b|\brilascio\b",
       "Ordinanza successiva alla chiusura dell'istruzione (art. 186-quater c.p.c.)",
       "ordinanza di condanna dopo l'esaurimento dell'istruzione (art. 186-quater c.p.c.)",
       "cpc_186_quater", _ORDINANZA),
    _r("ordinanza_sequestro",
       r"(?:ordinanza|decreto)\s+(?:che\s+(?:autorizza|dispone|concede)\s+(?:il\s+)?|di\s+(?:autorizzazione\s+(?:al|del)\s+)?)?sequestro\s+(?:conservativo|giudiziario)" + _CODA,
       r"\b6(?:69|7\d)\b|" + _CIVILE,
       "Ordinanza di sequestro conservativo o giudiziario (artt. 670-671 c.p.c.)",
       "provvedimento che autorizza il sequestro (artt. 669-sexies, 670 e 671 c.p.c.)",
       "cpc_671_sequestro", _ORDINANZA),
    _r("ordinanza_possessoria",
       r"(?:ordinanza|decreto)\s+(?:di\s+)?(?:reintegra(?:zione)?|manutenzione)(?:\s+nel\s+possesso)?" + _CODA
       + r"|ordinanza\s+possessoria" + _CODA
       + r"|(?:ordinanza|decreto)\s+" + _ART + r"703" + _CODA,
       r"\bpossess\w+\b|\b703\b|\b116[89]\b|\b1170\b|\bspoli\w+\b",
       "Ordinanza possessoria (art. 703 c.p.c.)",
       "provvedimento sulla domanda di reintegrazione o manutenzione (art. 703 c.p.c.)",
       "cpc_703_possessorio", _ORDINANZA),
)

_DIRITTI_REALI_E_CONDOMINIO = (
    _r("azione_rivendicazione",
       r"(?:atto\s+di\s+citazione\s+(?:per|in|di)\s+(?:(?:l.?\s*)?azione\s+di\s+)?|azione\s+di\s+)rivendicazione" + _CODA,
       r"\b948\b|\bpropriet\w+\b|\bpossied\w+\b|\bdetien\w+\b|\brestitu\w+\b",
       "Azione di rivendicazione (art. 948 c.c.)",
       "domanda del proprietario contro chi possiede o detiene il bene (art. 948 c.c.)",
       "cc_948_rivendicazione", _CITAZIONE),
    _r("azione_negatoria",
       r"(?:atto\s+di\s+citazione\s+(?:per|in|di)\s+(?:(?:l.?\s*)?azione\s+)?|azione\s+)negatoria(?:\s+servitutis)?" + _CODA,
       r"\b949\b|\bpropriet\w+\b|\bnegatori\w*\b|\bdiritt\w+\s+real\w+\b|\bservit\w+\b|\bturbativ\w+\b|\bmolesti\w+\b",
       "Azione negatoria (art. 949 c.c.)",
       "domanda di accertamento dell'inesistenza di diritti altrui sul bene (art. 949 c.c.)",
       "cc_949_negatoria", _CITAZIONE),
    _r("azione_confessoria",
       r"(?:atto\s+di\s+citazione\s+(?:per|in|di)\s+(?:(?:l.?\s*)?azione\s+)?|azione\s+)confessoria(?:\s+(?:di\s+)?servit[uù])?(?:\s+servitutis)?" + _CODA
       + r"|atto\s+di\s+citazione\s+per\s+(?:l.?\s*)?accertamento\s+(?:della|di)\s+servit[uù]" + _CODA,
       r"\b1079\b|\bservit\w+\b|\bconfessori\w*\b|\bpassaggio\b|\bfondo\s+(?:dominante|servente)\b",
       "Azione confessoria di servitù (art. 1079 c.c.)",
       "accertamento dell'esistenza della servitù (art. 1079 c.c.)",
       "cc_1079_confessoria", _CITAZIONE),
    _r("regolamento_confini",
       r"(?:atto\s+di\s+citazione\s+(?:per|in|di)\s+|azione\s+di\s+)?(?:regolamento\s+(?:di|dei)\s+confini|apposizione\s+(?:di|dei)\s+termini)" + _CODA,
       r"\b95[01]\b|\bconfin\w+\b|\bfond[oi]\b|\bmappal\w+\b",
       "Azione di regolamento di confini o apposizione di termini (artt. 950-951 c.c.)",
       "determinazione del confine incerto o apposizione dei termini (artt. 950-951 c.c.)",
       "cc_950_confini", _CITAZIONE),
    _r("usucapione",
       r"(?:atto\s+di\s+citazione|ricorso|domanda)\s+(?:[\w'’]+\s+){0,5}usucapione" + _CODA,
       r"\b115[89]\b|\b1159[\s-]*bis\b|\bposse(?:ss|d)\w+\b|\busucapi\w+\b|\bventennal\w+\b|\binterrott\w+\b",
       "Domanda di usucapione (art. 1158 c.c.)",
       "acquisto della proprietà per possesso continuato (artt. 1158-1159-bis c.c.)",
       "cc_1158_usucapione", _CITAZIONE),
    _r("amministratore_condominio",
       r"ricorso\s+(?:per\s+(?:la\s+)?)?(?:revoca|nomina)(?:\s+o\s+(?:(?:la\s+)?revoca|(?:la\s+)?nomina))?\s+(?:giudiziale\s+)?(?:" + _DELL + r")?amministratore\s+(?:di|del)\s+condominio" + _CODA,
       r"\b1129\b|\bart(?:icolo|\.)?\s*64\b|\b1105\b|\bcondomin\w+\b",
       "Ricorso per nomina o revoca dell'amministratore di condominio (art. 1129 c.c.)",
       "nomina o revoca giudiziale dell'amministratore (art. 1129 c.c.; art. 64 disp. att. c.c.)",
       "cc_1129_amministratore", _ATTO),
    _r("rendiconto_condominiale",
       r"(?:rendiconto|bilancio)\s+(?:condominiale|consuntivo|annuale|della\s+gestione|di\s+gestione)" + _CODA,
       r"\bcondomin\w+\b|\bmillesim\w+\b|\b1130[\s-]*bis\b",
       "Rendiconto condominiale (art. 1130-bis c.c.)",
       "rendiconto della gestione redatto dall'amministratore (art. 1130-bis c.c.)",
       "cc_1130_bis_rendiconto", _ECONOMICO),
    _r("tabella_millesimale",
       r"(?:tabell[ae]\s+millesimal[ei]|tabell[ae]\s+(?:dei\s+)?millesimi)" + _CODA,
       r"\bmillesim\w+\b|\bcondomin\w+\b|\bart(?:icolo|\.)?\s*6[89]\b",
       "Tabella millesimale (art. 68 disp. att. c.c.)",
       "valore delle unità espresso in millesimi (art. 68 disp. att. c.c.)",
       "disp_att_cc_68_tabelle", _CONDOMINIO),
)

_RESPONSABILITA_SANITARIA = (
    _r("comunicazione_esercente_sanitario",
       r"comunicazione\s+(?:all.?\s*esercente\s+la\s+professione\s+sanitaria|(?:di\s+)?(?:avvio|instaurazione|pendenza)\s+(?:del\s+)?giudizio\s+(?:all.?\s*esercente|al\s+(?:medico|sanitario)))" + _CODA
       + r"|comunicazione\s+" + _ART + r"13\s+" + _L_24 + _CODA,
       r"\b24/2017\b|\bart(?:icolo|\.)?\s*13\b|\bquarantacinque\s+giorni\b|\bsanitari\w+\b",
       "Comunicazione all'esercente la professione sanitaria (art. 13 L. 24/2017)",
       "comunicazione dell'instaurazione del giudizio entro quarantacinque giorni (art. 13 L. 24/2017)",
       "l24_2017_art13", _LETTERA),
    _r("azione_diretta_sanitaria",
       r"atto\s+di\s+citazione\s+(?:in\s+|per\s+)?(?:azione\s+diretta|" + _ART + r"12\s+" + _L_24 + r")" + _CODA
       + r"|azione\s+diretta\s+(?:contro|nei\s+confronti\s+del(?:l.?\s*)?)\s*(?:l.?\s*)?(?:assicurator\w+|impresa\s+di\s+assicurazione)" + _CODA,
       r"\b24/2017\b|\bstruttur\w+\s+sanitari\w+\b|\besercente\s+la\s+professione\s+sanitaria\b|\bresponsabilit\w+\s+sanitari\w+\b",
       "Azione diretta contro l'assicuratore in materia sanitaria (art. 12 L. 24/2017)",
       "azione diretta del danneggiato verso l'impresa di assicurazione (art. 12 L. 24/2017)",
       "l24_2017_art12", _CITAZIONE),
)

_CONTRATTI = (
    _r("preliminare_compravendita",
       r"(?:contratto\s+)?preliminare\s+(?:di\s+)?(?:compra)?vendita" + _CODA
       + r"|compromesso\s+(?:di\s+)?(?:compra)?vendita" + _CODA
       + r"|promessa\s+(?:di\s+)?(?:vendita|acquisto)" + _CODA,
       r"\bpromissari\w+\b|\bpromittent\w+\b|\bpreliminar\w+\b|\b1351\b|\bcontratto\s+definitivo\b|\brogito\b|\bcaparra\b",
       "Contratto preliminare di compravendita (art. 1351 c.c.)",
       "obbligo di concludere il contratto definitivo di vendita (artt. 1351 e 2645-bis c.c.)",
       "cc_1351_preliminare", _CONTRATTO),
    _r("compravendita",
       r"(?:contratto|atto|scrittura\s+privata)\s+di\s+(?:compra)?vendita" + _CODA
       + r"|compravendita" + _CODA,
       r"\bvendit\w+\b|\bacquirent\w+\b|\bcompratore\b|\bprezzo\b|\b1470\b",
       "Contratto di compravendita (art. 1470 c.c.)",
       "trasferimento della proprietà verso il corrispettivo di un prezzo (art. 1470 c.c.)",
       "cc_1470_vendita", _CONTRATTO),
    _r("comodato",
       r"(?:contratto\s+di\s+)?comodato(?:\s+d.?\s*uso)?(?:\s+gratuito)?" + _CODA,
       r"\bcomodat\w+\b|\b1803\b|\bgratuit\w+\b|\brestitu\w+\b",
       "Contratto di comodato (art. 1803 c.c.)",
       "consegna gratuita di un bene con obbligo di restituzione (art. 1803 c.c.)",
       "cc_1803_comodato", _CONTRATTO),
    _r("permuta",
       r"(?:contratto\s+di\s+|atto\s+di\s+)?permuta" + _CODA,
       r"\bpermut\w+\b|\b1552\b|\btrasferiment\w+\b",
       "Contratto di permuta (art. 1552 c.c.)",
       "reciproco trasferimento della proprietà di cose o diritti (art. 1552 c.c.)",
       "cc_1552_permuta", _CONTRATTO),
    _r("contratto_opera",
       r"contratto\s+(?:di\s+prestazione\s+)?d.?\s*opera(?![^\n]*(?:professional|intellettual))" + _CODA,
       r"\b2222\b|\bcommittent\w+\b|\bcorrispettiv\w+\b|\bopera\b",
       "Contratto d'opera (art. 2222 c.c.)",
       "opera o servizio con lavoro prevalentemente proprio (art. 2222 c.c.)",
       "cc_2222_opera", _CONTRATTO),
    _r("mandato",
       r"contratto\s+di\s+mandato" + _CODA,
       r"\bmandat\w+\b|\b1703\b",
       "Contratto di mandato (art. 1703 c.c.)",
       "obbligo di compiere atti giuridici per conto del mandante (art. 1703 c.c.)",
       "cc_1703_mandato", _CONTRATTO),
    _r("notifica_cessione_credito",
       r"(?:notifica(?:zione)?|comunicazione|avviso)\s+(?:della\s+|di\s+(?:avvenuta\s+)?)?cessione\s+(?:del|di|dei)\s+credit[oi]" + _CODA,
       r"\b126[45]\b|\bdebitore\s+ceduto\b|\bcessionari\w+\b|\bpagament\w+\b",
       "Notifica della cessione del credito al debitore ceduto (art. 1264 c.c.)",
       "efficacia della cessione verso il debitore ceduto (art. 1264 c.c.)",
       "cc_1264_notifica_cessione", _LETTERA),
    _r("cessione_credito",
       r"(?:contratto|atto|scrittura\s+privata)\s+di\s+cessione\s+(?:del|di|dei)\s+credit[oi]" + _CODA
       + r"|cessione\s+(?:del|di)\s+credito" + _CODA,
       r"\b126[0-7]\b|\bcedent\w+\b|\bcessionari\w+\b|\bdebitore\s+ceduto\b",
       "Contratto di cessione del credito (art. 1260 c.c.)",
       "trasferimento del credito a titolo oneroso o gratuito (art. 1260 c.c.)",
       "cc_1260_cessione", _CONTRATTO),
    _r("quietanza",
       r"quietanza(?:\s+(?:liberatoria|di\s+pagamento|a\s+saldo|di\s+saldo|di\s+avvenuto\s+pagamento))?" + _CODA
       + r"|dichiarazione\s+di\s+quietanza" + _CODA,
       r"\bricev\w+\b|\bpagat\w+\b|\bsomm\w+\b|\b1199\b|\bsaldo\b|\bquietanz\w+\b",
       "Quietanza di pagamento (art. 1199 c.c.)",
       "dichiarazione del creditore di aver ricevuto il pagamento (art. 1199 c.c.)",
       "cc_1199_quietanza", _ECONOMICO),
)

_ORDINAMENTO_MILITARE = (
    _r("contestazione_addebiti_militare",
       r"(?:atto\s+di\s+|verbale\s+di\s+)?contestazione\s+(?:degli\s+|di\s+)?addebit[oi](?:\s+disciplinar[ei])?" + _CODA,
       _MILITARE + r"|\b1370\b",
       "Contestazione degli addebiti al militare (art. 1370 D.Lgs. 66/2010)",
       "contestazione degli addebiti e termine per le giustificazioni (art. 1370 D.Lgs. 66/2010)",
       "com_1370_contestazione", _LETTERA),
    _r("giustificazioni_militare",
       r"(?:memoria\s+(?:difensiva\s+)?(?:con\s+)?|atto\s+di\s+)?giustificazioni" + _CODA,
       _MILITARE,
       "Giustificazioni del militare nel procedimento disciplinare",
       "giustificazioni del militare incolpato (art. 1370 D.Lgs. 66/2010)",
       "com_1370_contestazione", _DIFESA_ESTERNA),
    _r("inchiesta_formale_militare",
       r"(?:ordine|decisione|provvedimento|determinazione)\s+di\s+(?:sottoporre\s+(?:il\s+militare\s+)?a\s+)?inchiesta\s+formale" + _CODA
       + r"|(?:relazione\s+(?:conclusiva\s+)?(?:" + _DELL + r")?|verbale\s+(?:" + _DELL + r")?)?inchiesta\s+formale" + _CODA,
       _MILITARE + r"|\bufficiale\s+inquirente\b|\bcommissione\s+di\s+disciplina\b",
       "Inchiesta formale disciplinare militare (art. 1376 D.Lgs. 66/2010)",
       "inchiesta formale che apre il procedimento disciplinare di stato (artt. 1376-1378 D.Lgs. 66/2010)",
       "com_1376_inchiesta", _PROVV_AMM),
    _r("sanzione_disciplinare_militare",
       r"(?:provvedimento|determinazione|decreto|atto)\s+(?:di\s+)?(?:irrogazione|inflizione|applicazione)\s+(?:della\s+)?sanzione\s+disciplinare" + _CODA
       + r"|(?:provvedimento|decreto)\s+(?:di\s+)?(?:consegna(?:\s+di\s+rigore)?|perdita\s+del\s+grado|sospensione\s+disciplinare)" + _CODA
       + r"|provvedimento\s+disciplinare\s+militare" + _CODA,
       _MILITARE + r"|\b135[78]\b",
       "Provvedimento disciplinare militare (artt. 1357-1358 D.Lgs. 66/2010)",
       "irrogazione di una sanzione disciplinare di stato o di corpo (artt. 1357-1358 D.Lgs. 66/2010)",
       "com_1357_sanzioni", _PROVV_AMM),
    _r("ricorso_gerarchico_militare",
       r"ricorso\s+gerarchico" + _CODA,
       _MILITARE + r"|\b1366\b",
       "Ricorso gerarchico avverso sanzione disciplinare militare (art. 1366 D.Lgs. 66/2010)",
       "ricorso all'autorità gerarchica superiore contro la sanzione di corpo (art. 1366 D.Lgs. 66/2010)",
       "com_1366_ricorso_gerarchico", _ATTO_ESTERNO),
)

REGOLE: tuple[RegolaTitolo, ...] = (
    _GIUSTIZIA_COSTITUZIONALE
    + _UNIONE_EUROPEA_E_CEDU
    + _ARBITRATO_E_NEGOZIAZIONE
    + _PROCEDURA_CIVILE
    + _DIRITTI_REALI_E_CONDOMINIO
    + _RESPONSABILITA_SANITARIA
    + _CONTRATTI
    + _ORDINAMENTO_MILITARE
)

__all__ = ["FONTI", "REGOLE"]
