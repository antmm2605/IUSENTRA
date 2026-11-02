"""Impresa e crisi, società, proprietà intellettuale e industriale, banca, finanza, assicurazioni, consumatori, concorrenza.

Regole d'identità dal titolo aggiunte il 02/11/2026 per coprire tutte le materie (direttiva dell'avvocato del
01/11/2026). Ogni regola cita la norma che definisce l'atto, registrata in `FONTI` con URL ufficiale e data di
consultazione.

Le tipologie già coperte dalle aree `crisi`, `crisi_procedure`, `societario` e `consumo` (domanda di ammissione al
passivo e tardiva, stato passivo e decreto di esecutività, opposizione allo stato passivo, concordato preventivo e
minore, piano del consumatore, esdebitazione, azione di responsabilità, recesso del socio, impugnazione di delibera
e di bilancio, verbale di assemblea, contenzioso bancario, Centrale dei rischi, richiesta ex art. 119 TUB, reclamo
del consumatore, conciliazione paritetica, clausole vessatorie) non si ripetono qui.
"""

from __future__ import annotations

from typing import Any

from pct.fascicoli import TipoDocumento

from ._modello import RegolaTitolo, regola

_VERIFICA = "testo vigente consultato su Normattiva il 02/11/2026"
_NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"
_CCII = "decreto.legislativo:2019-01-12;14~art"
_CC = "regio.decreto:1942-03-16;262~art"
_CPC = "regio.decreto:1940-10-28;1443~art"
_CPI = "decreto.legislativo:2005-02-10;30~art"
_LDA = "legge:1941-04-22;633~art"
_TUB = "decreto.legislativo:1993-09-01;385~art"
_TUF = "decreto.legislativo:1998-02-24;58~art"
_CAP = "decreto.legislativo:2005-09-07;209~art"
_CONSUMO = "decreto.legislativo:2005-09-06;206~art"
_ANTITRUST = "legge:1990-10-10;287~art"
_DANNO_ANTITRUST = "decreto.legislativo:2017-01-19;3~art"


def _fonte(label: str, urn: str) -> dict[str, Any]:
    return {"label": label, "official_url": _NORMATTIVA + urn, "verification_status": _VERIFICA, "source_type": "normativa"}


FONTI: dict[str, dict[str, Any]] = {
    # Codice della crisi d'impresa e dell'insolvenza (D.Lgs. 14/2019)
    "estesa_impresa_ccii_17": _fonte("D.Lgs. 14/2019, artt. 12 e 17: accesso alla composizione negoziata, esperto e relazione finale", _CCII + "17"),
    "estesa_impresa_ccii_19": _fonte("D.Lgs. 14/2019, artt. 18 e 19: misure protettive e procedimento di conferma", _CCII + "19"),
    "estesa_impresa_ccii_44": _fonte("D.Lgs. 14/2019, art. 44: domanda di accesso con riserva", _CCII + "44"),
    "estesa_impresa_ccii_47": _fonte("D.Lgs. 14/2019, art. 47: decreto di apertura del concordato preventivo", _CCII + "47"),
    "estesa_impresa_ccii_48": _fonte("D.Lgs. 14/2019, art. 48: omologazione con sentenza", _CCII + "48"),
    "estesa_impresa_ccii_49": _fonte("D.Lgs. 14/2019, art. 49: sentenza di apertura della liquidazione giudiziale", _CCII + "49"),
    "estesa_impresa_ccii_51": _fonte("D.Lgs. 14/2019, art. 51: impugnazioni (reclamo contro la sentenza)", _CCII + "51"),
    "estesa_impresa_ccii_56": _fonte("D.Lgs. 14/2019, art. 56: accordi in esecuzione di piani attestati di risanamento", _CCII + "56"),
    "estesa_impresa_ccii_57": _fonte("D.Lgs. 14/2019, artt. 57, 60 e 61: accordi di ristrutturazione dei debiti", _CCII + "57"),
    "estesa_impresa_ccii_64bis": _fonte("D.Lgs. 14/2019, art. 64-bis: piano di ristrutturazione soggetto a omologazione", _CCII + "64bis"),
    "estesa_impresa_ccii_68": _fonte("D.Lgs. 14/2019, artt. 68, 76 e 269: relazione particolareggiata dell'OCC", _CCII + "68"),
    "estesa_impresa_ccii_87": _fonte("D.Lgs. 14/2019, art. 87, comma 3: attestazione del professionista indipendente", _CCII + "87"),
    "estesa_impresa_ccii_105": _fonte("D.Lgs. 14/2019, art. 105: relazione del commissario giudiziale", _CCII + "105"),
    "estesa_impresa_ccii_107": _fonte("D.Lgs. 14/2019, art. 107: voto nel concordato preventivo", _CCII + "107"),
    "estesa_impresa_ccii_130": _fonte("D.Lgs. 14/2019, art. 130: relazioni e rapporti riepilogativi del curatore", _CCII + "130"),
    "estesa_impresa_ccii_166": _fonte("D.Lgs. 14/2019, art. 166: atti a titolo oneroso, pagamenti e garanzie (revocatoria)", _CCII + "166"),
    "estesa_impresa_ccii_195": _fonte("D.Lgs. 14/2019, art. 195: inventario", _CCII + "195"),
    "estesa_impresa_ccii_200": _fonte("D.Lgs. 14/2019, art. 200: avviso ai creditori e agli altri interessati", _CCII + "200"),
    "estesa_impresa_ccii_213": _fonte("D.Lgs. 14/2019, art. 213: programma di liquidazione", _CCII + "213"),
    "estesa_impresa_ccii_220": _fonte("D.Lgs. 14/2019, art. 220: procedimento di ripartizione", _CCII + "220"),
    "estesa_impresa_ccii_231": _fonte("D.Lgs. 14/2019, art. 231: rendiconto del curatore", _CCII + "231"),
    "estesa_impresa_ccii_240": _fonte("D.Lgs. 14/2019, art. 240: proposta di concordato nella liquidazione giudiziale", _CCII + "240"),
    "estesa_impresa_ccii_268": _fonte("D.Lgs. 14/2019, art. 268: domanda di liquidazione controllata", _CCII + "268"),
    "estesa_impresa_ccii_270": _fonte("D.Lgs. 14/2019, art. 270: apertura della liquidazione controllata", _CCII + "270"),
    # Codice civile: società, impresa e contratti
    "estesa_impresa_cc_2328": _fonte("c.c., artt. 2328 e 2463: atto costitutivo e statuto delle società di capitali", _CC + "2328"),
    "estesa_impresa_cc_2341bis": _fonte("c.c., art. 2341-bis: patti parasociali", _CC + "2341bis"),
    "estesa_impresa_cc_2409": _fonte("c.c., art. 2409: denunzia al tribunale di gravi irregolarità", _CC + "2409"),
    "estesa_impresa_cc_2423": _fonte("c.c., art. 2423: redazione del bilancio", _CC + "2423"),
    "estesa_impresa_cc_2429": _fonte("c.c., art. 2429: relazione dei sindaci e deposito del bilancio", _CC + "2429"),
    "estesa_impresa_cc_2470": _fonte("c.c., art. 2470: efficacia e pubblicità del trasferimento delle partecipazioni", _CC + "2470"),
    "estesa_impresa_cc_2487": _fonte("c.c., art. 2487: nomina e revoca dei liquidatori", _CC + "2487"),
    "estesa_impresa_cc_2501ter": _fonte("c.c., artt. 2501-ter e 2506-bis: progetto di fusione e di scissione", _CC + "2501ter"),
    "estesa_impresa_cc_2556": _fonte("c.c., art. 2556: trasferimento dell'azienda", _CC + "2556"),
    "estesa_impresa_cc_1813": _fonte("c.c., art. 1813: contratto di mutuo", _CC + "1813"),
    "estesa_impresa_cc_1882": _fonte("c.c., artt. 1882 e 1888: contratto di assicurazione e polizza", _CC + "1882"),
    "estesa_impresa_cc_1913": _fonte("c.c., art. 1913: avviso all'assicuratore in caso di sinistro", _CC + "1913"),
    "estesa_impresa_cc_1936": _fonte("c.c., art. 1936: fideiussione", _CC + "1936"),
    "estesa_impresa_l129_2004": _fonte("L. 129/2004, art. 3: forma e contenuto del contratto di affiliazione commerciale", "legge:2004-05-06;129~art3"),
    # Proprietà industriale e diritto d'autore
    "estesa_impresa_cpi_20": _fonte("D.Lgs. 30/2005 (c.p.i.), art. 20: diritti conferiti dalla registrazione del marchio", _CPI + "20"),
    "estesa_impresa_cpi_23": _fonte("D.Lgs. 30/2005 (c.p.i.), art. 23: trasferimento e licenza del marchio", _CPI + "23"),
    "estesa_impresa_cpi_53": _fonte("D.Lgs. 30/2005 (c.p.i.), art. 53: effetti della brevettazione e della registrazione", _CPI + "53"),
    "estesa_impresa_cpi_122": _fonte("D.Lgs. 30/2005 (c.p.i.), art. 122: azioni di nullità e decadenza", _CPI + "122"),
    "estesa_impresa_cpi_124": _fonte("D.Lgs. 30/2005 (c.p.i.), art. 124: misure correttive e sanzioni civili per la contraffazione", _CPI + "124"),
    "estesa_impresa_cpi_128": _fonte("D.Lgs. 30/2005 (c.p.i.), artt. 128 e 129: descrizione e sequestro", _CPI + "128"),
    "estesa_impresa_cpi_131": _fonte("D.Lgs. 30/2005 (c.p.i.), art. 131: inibitoria", _CPI + "131"),
    "estesa_impresa_cpi_148": _fonte("D.Lgs. 30/2005 (c.p.i.), artt. 148 e 156: domanda di registrazione del marchio", _CPI + "156"),
    "estesa_impresa_cpi_160": _fonte("D.Lgs. 30/2005 (c.p.i.), art. 160: domanda di brevetto", _CPI + "160"),
    "estesa_impresa_cpi_176": _fonte("D.Lgs. 30/2005 (c.p.i.), art. 176: opposizione alla registrazione del marchio", _CPI + "176"),
    "estesa_impresa_lda_118": _fonte("L. 633/1941, art. 118: contratto di edizione", _LDA + "118"),
    "estesa_impresa_lda_156": _fonte("L. 633/1941, art. 156: azione inibitoria a difesa dei diritti di utilizzazione", _LDA + "156"),
    # Banca e finanza
    "estesa_impresa_tub_50": _fonte("D.Lgs. 385/1993 (TUB), art. 50: estratto conto certificato per il decreto ingiuntivo", _TUB + "50"),
    "estesa_impresa_tub_117": _fonte("D.Lgs. 385/1993 (TUB), art. 117: forma e contenuto dei contratti bancari", _TUB + "117"),
    "estesa_impresa_tub_124": _fonte("D.Lgs. 385/1993 (TUB), art. 124: obblighi precontrattuali nel credito ai consumatori", _TUB + "124"),
    "estesa_impresa_tub_125bis": _fonte("D.Lgs. 385/1993 (TUB), art. 125-bis: contratti di credito ai consumatori", _TUB + "125bis"),
    "estesa_impresa_tub_128bis": _fonte("D.Lgs. 385/1993 (TUB), art. 128-bis: risoluzione delle controversie (Arbitro Bancario Finanziario)", _TUB + "128bis"),
    "estesa_impresa_tuf_23": _fonte("D.Lgs. 58/1998 (TUF), art. 23: contratti per i servizi di investimento", _TUF + "23"),
    "estesa_impresa_tuf_32ter": _fonte("D.Lgs. 58/1998 (TUF), art. 32-ter: risoluzione stragiudiziale delle controversie (ACF)", _TUF + "32ter"),
    "estesa_impresa_dpr_180_1950": _fonte("D.P.R. 180/1950, art. 5: cessione di quote dello stipendio o della pensione", "decreto.del.presidente.della.repubblica:1950-01-05;180~art5"),
    "estesa_impresa_l124_2017": _fonte("L. 124/2017, art. 1, commi 136-140: contratto di locazione finanziaria", "legge:2017-08-04;124~art1"),
    # Assicurazioni
    "estesa_impresa_cap_7": _fonte("D.Lgs. 209/2005 (CAP), art. 7: reclami all'IVASS e alle imprese", _CAP + "7"),
    "estesa_impresa_cap_187_1": _fonte("D.Lgs. 209/2005 (CAP), art. 187.1: sistemi di risoluzione stragiudiziale (Arbitro assicurativo)", _CAP + "187.1"),
    # Consumatori, azioni collettive e concorrenza
    "estesa_impresa_consumo_27": _fonte("D.Lgs. 206/2005, artt. 20 e 27: pratiche commerciali scorrette e tutela amministrativa", _CONSUMO + "27"),
    "estesa_impresa_consumo_52": _fonte("D.Lgs. 206/2005, artt. 52-54: diritto di recesso del consumatore", _CONSUMO + "52"),
    "estesa_impresa_consumo_135bis": _fonte("D.Lgs. 206/2005, art. 135-bis: rimedi per il difetto di conformità", _CONSUMO + "135bis"),
    "estesa_impresa_cpc_840bis": _fonte("c.p.c., artt. 840-bis e 840-ter: azione di classe", _CPC + "840bis"),
    "estesa_impresa_cpc_840septies": _fonte("c.p.c., art. 840-septies: adesione all'azione di classe", _CPC + "840septies"),
    "estesa_impresa_cpc_840sexiesdecies": _fonte("c.p.c., art. 840-sexiesdecies: azione inibitoria collettiva", _CPC + "840sexiesdecies"),
    "estesa_impresa_l287_12": _fonte("L. 287/1990, art. 12: poteri d'indagine su denuncia (intese e abusi)", _ANTITRUST + "12"),
    "estesa_impresa_l287_14ter": _fonte("L. 287/1990, art. 14-ter: impegni", _ANTITRUST + "14ter"),
    "estesa_impresa_l287_15": _fonte("L. 287/1990, art. 15: diffide e sanzioni dell'Autorità", _ANTITRUST + "15"),
    "estesa_impresa_dlgs3_2017_1": _fonte("D.Lgs. 3/2017, artt. 1 e 18: azioni per il risarcimento del danno antitrust", _DANNO_ANTITRUST + "1"),
    "estesa_impresa_dlgs3_2017_3": _fonte("D.Lgs. 3/2017, art. 3: esibizione delle prove", _DANNO_ANTITRUST + "3"),
}

_CODA = r"(?:\s+.*)?"
_CPI_SEGNALI = r"(?:12[89]|131|c\.?\s*p\.?\s*i\b|propriet[aà]\s+(?:industriale|intellettuale)|marchi|brevett|contraffa|diritt[oi]\s+d.?\s*autore|633/1941)"


def _r(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str, section: str, role: str,
       tipo: TipoDocumento, deposit_role: str = "allegato", deposit_candidate: bool = True) -> RegolaTitolo:
    return regola(id, titolo, conferma, label, role=role, section=section, tipo=tipo, fonte=fonte,
                  deposit_role=deposit_role, deposit_candidate=deposit_candidate, evidence=evidence)


def _ricorso(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str,
             tipo: TipoDocumento = TipoDocumento.RICORSO, in_busta: bool = True) -> RegolaTitolo:
    return _r(id, titolo, conferma, label, evidence, fonte=fonte, section="atti", role="atto_principale", tipo=tipo,
              deposit_role="atto_principale" if in_busta else "allegato", deposit_candidate=in_busta)


def _istanza(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str,
             in_busta: bool = True) -> RegolaTitolo:
    return _r(id, titolo, conferma, label, evidence, fonte=fonte, section="atti", role="istanza",
              tipo=TipoDocumento.MEMORIA, deposit_role="atto_principale" if in_busta else "allegato",
              deposit_candidate=in_busta)


def _provvedimento(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str,
                   tipo: TipoDocumento = TipoDocumento.DECRETO, role: str = "provvedimento") -> RegolaTitolo:
    return _r(id, titolo, conferma, label, evidence, fonte=fonte, section="provvedimenti", role=role, tipo=tipo,
              deposit_role="fuori_busta", deposit_candidate=False)


def _relazione(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str) -> RegolaTitolo:
    """Relazioni e documenti degli organi della procedura: depositati da loro, non dallo studio."""
    return _r(id, titolo, conferma, label, evidence, fonte=fonte, section="allegati", role="relazione_terzi",
              tipo=TipoDocumento.ALLEGATO, deposit_role="fuori_busta", deposit_candidate=False)


def _documento(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str,
               role: str = "documento_economico") -> RegolaTitolo:
    return _r(id, titolo, conferma, label, evidence, fonte=fonte, section="allegati", role=role,
              tipo=TipoDocumento.ALLEGATO)


def _contratto(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str) -> RegolaTitolo:
    return _r(id, titolo, conferma, label, evidence, fonte=fonte, section="contratti", role="contratto",
              tipo=TipoDocumento.CONTRATTO)


def _lettera(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str,
             role: str = "corrispondenza_stragiudiziale") -> RegolaTitolo:
    return _r(id, titolo, conferma, label, evidence, fonte=fonte, section="comunicazioni", role=role,
              tipo=TipoDocumento.COMUNICAZIONE)


_CRISI = (
    _provvedimento(
        "imp_sentenza_apertura_liquidazione_giudiziale",
        r"sentenza\s+(?:dichiarativa\s+)?(?:di\s+)?(?:apertura\s+(?:della\s+)?)?liquidazione\s+giudiziale" + _CODA
        + r"|sentenza\s+(?:dichiarativa\s+)?di\s+fallimento" + _CODA,
        r"\bcurator\w+\b|\bgiudice\s+delegato\b|\bdichiara\s+aperta\b|\b49\b",
        "Sentenza di apertura della liquidazione giudiziale",
        "titolo della sentenza e nomina del curatore e del giudice delegato (art. 49 CCII)",
        fonte="estesa_impresa_ccii_49", tipo=TipoDocumento.SENTENZA,
    ),
    _ricorso(
        "imp_reclamo_sentenza_concorsuale",
        r"reclamo\s+(?:contro|avverso)\s+(?:la\s+)?sentenza\s+(?:di\s+apertura\s+(?:della\s+)?liquidazione\s+(?:giudiziale|controllata)"
        r"|(?:dichiarativa\s+)?di\s+(?:liquidazione\s+(?:giudiziale|controllata)|fallimento|omologa(?:zione)?))" + _CODA
        + r"|reclamo\s+ex\s+art\.?\s*51(?:\s+ccii)?" + _CODA,
        r"\breclam\w+\b|\bcorte\s+d.?\s*appello\b|\b51\b",
        "Reclamo contro la sentenza di liquidazione giudiziale o di omologazione (art. 51 CCII)",
        "titolo del reclamo e sentenza impugnata davanti alla corte d'appello (art. 51 CCII)",
        fonte="estesa_impresa_ccii_51",
    ),
    _relazione(
        "imp_relazione_curatore",
        r"relazione\s+(?:particolareggiata\s+|iniziale\s+|(?:ex\s+)?art\.?\s*130\s+(?:ccii\s+)?)?del\s+curatore" + _CODA
        + r"|relazione\s+ex\s+art\.?\s*130" + _CODA + r"|rapporto\s+riepilogativo(?:\s+(?:semestrale|del\s+curatore|finale))?" + _CODA,
        r"\bcurator\w+\b|\bcause\s+(?:e\s+circostanze\s+)?del(?:lo|l.)?\s*(?:dissesto|insolvenza)\b|\b130\b",
        "Relazione del curatore (art. 130 CCII)",
        "titolo della relazione e cause dell'insolvenza esposte dal curatore (art. 130 CCII)",
        fonte="estesa_impresa_ccii_130",
    ),
    _relazione(
        "imp_programma_liquidazione",
        r"(?:supplemento\s+al\s+|modifica\s+del\s+)?programma\s+di\s+liquidazione" + _CODA,
        r"\bcurator\w+\b|\b213\b|\bliquidazione\s+giudiziale\b|\battivo\b",
        "Programma di liquidazione",
        "titolo del programma e modalità di realizzo dell'attivo (art. 213 CCII)",
        fonte="estesa_impresa_ccii_213",
    ),
    _relazione(
        "imp_inventario_concorsuale",
        r"inventario\s+(?:fallimentare|dei\s+beni\s+(?:acquisiti\s+all.?\s*attivo|della\s+procedura(?:\s+concorsuale)?|del\s+debitore))" + _CODA,
        r"\bcurator\w+\b|\b195\b|\bcancellier\w+\b|\bliquidazione\s+giudiziale\b",
        "Inventario dei beni della procedura concorsuale",
        "titolo dell'inventario redatto dal curatore (art. 195 CCII)",
        fonte="estesa_impresa_ccii_195",
    ),
    _lettera(
        "imp_avviso_curatore_creditori",
        r"avviso\s+(?:del\s+curatore\s+)?ai\s+creditori" + _CODA
        + r"|comunicazione\s+(?:del\s+curatore\s+)?ai\s+creditori(?:\s+ex\s+art\.?\s*200)?" + _CODA,
        r"\bcurator\w+\b|\b200\b|\bdomand\w+\s+di\s+ammissione\b",
        "Avviso del curatore ai creditori (art. 200 CCII)",
        "titolo dell'avviso e termine per le domande di ammissione al passivo (art. 200 CCII)",
        fonte="estesa_impresa_ccii_200", role="atto_ufficio",
    ),
    _provvedimento(
        "imp_progetto_ripartizione_concorsuale",
        r"progetto\s+di\s+(?:ripartizione|riparto)\s+(?:parziale|finale|dell.?\s*attivo|fallimentare|concorsuale)" + _CODA
        + r"|progetto\s+di\s+ripartizione" + _CODA,
        r"\bcurator\w+\b|\b220\b|\bgiudice\s+delegato\b",
        "Progetto di ripartizione dell'attivo (art. 220 CCII)",
        "titolo del progetto e riparto delle somme fra i creditori ammessi (art. 220 CCII)",
        fonte="estesa_impresa_ccii_220", tipo=TipoDocumento.ALLEGATO, role="atto_ufficio",
    ),
    _relazione(
        "imp_rendiconto_curatore",
        r"rendiconto\s+(?:finale\s+)?(?:della\s+gestione\s+)?(?:del\s+curatore|ex\s+art\.?\s*231)" + _CODA,
        r"\bcurator\w+\b|\b231\b|\bgestione\b",
        "Rendiconto del curatore",
        "titolo del rendiconto della gestione (art. 231 CCII)",
        fonte="estesa_impresa_ccii_231",
    ),
    _provvedimento(
        "imp_decreto_apertura_concordato",
        r"decreto\s+di\s+(?:apertura|ammissione)\s+(?:della\s+procedura\s+di\s+|al\s+|del\s+)?concordato\s+preventivo" + _CODA,
        r"\bcommissario\s+giudiziale\b|\bgiudice\s+delegato\b|\b47\b|\bvot\w+\b",
        "Decreto di apertura del concordato preventivo",
        "titolo del decreto e nomina del commissario giudiziale (art. 47 CCII)",
        fonte="estesa_impresa_ccii_47",
    ),
    _ricorso(
        "imp_domanda_accesso_con_riserva",
        r"(?:domanda|ricorso)\s+(?:di|per\s+l.?)\s*accesso\s+.*con\s+riserva" + _CODA + r"|(?:domanda|ricorso)\s+con\s+riserva" + _CODA
        + r"|(?:domanda|ricorso)\s+(?:prenotativ[ao]|in\s+bianco)" + _CODA + r"|ricorso\s+ex\s+art\.?\s*44(?:\s+ccii)?" + _CODA,
        r"\briserva\b|\b44\b|\btermine\b|\bproposta\b",
        "Domanda di accesso con riserva (art. 44 CCII)",
        "titolo della domanda e termine per depositare proposta e piano (art. 44 CCII)",
        fonte="estesa_impresa_ccii_44",
    ),
    _provvedimento(
        "imp_sentenza_omologazione_ccii",
        r"sentenza\s+di\s+omologa(?:zione)?\s+(?:del\s+|dell[ae'’]\s*|degli\s+)?(?:concordato|accord[oi]\s+di\s+ristrutturazione|piano\s+di\s+ristrutturazione)" + _CODA,
        r"\bomolog\w+\b|\bcreditor\w+\b|\b48\b",
        "Sentenza di omologazione del concordato o degli accordi di ristrutturazione",
        "titolo della sentenza che omologa lo strumento di regolazione della crisi (art. 48 CCII)",
        fonte="estesa_impresa_ccii_48", tipo=TipoDocumento.SENTENZA,
    ),
    _relazione(
        "imp_relazione_commissario_giudiziale",
        r"relazione\s+(?:particolareggiata\s+)?del\s+commissario\s+giudiziale" + _CODA + r"|relazione\s+ex\s+art\.?\s*105" + _CODA,
        r"\bcommissari\w+\b|\b105\b|\bcreditor\w+\b",
        "Relazione del commissario giudiziale",
        "titolo della relazione depositata prima dell'adunanza dei creditori (art. 105 CCII)",
        fonte="estesa_impresa_ccii_105",
    ),
    _lettera(
        "imp_dichiarazione_voto_concordato",
        r"(?:dichiarazione|espressione|manifestazione)\s+(?:di|del)\s+voto(?:\s+(?:del\s+creditore|sulla\s+proposta|nel\s+concordato).*)?"
        r"|voto\s+del\s+creditore" + _CODA,
        r"\bconcordat\w+\b|\b107\b|\bcommissario\s+giudiziale\b",
        "Dichiarazione di voto del creditore",
        "titolo della dichiarazione e voto sulla proposta di concordato (art. 107 CCII)",
        fonte="estesa_impresa_ccii_107", role="corrispondenza",
    ),
    _documento(
        "imp_attestazione_professionista",
        r"(?:relazione\s+di\s+)?attestazione\s+(?:del\s+professionista\s+indipendente|di\s+veridicit[aà]|ex\s+art\.?\s*(?:56|57|87)).*"
        r"|relazione\s+del\s+professionista\s+(?:indipendente|attestatore)" + _CODA,
        r"\bveridicit\w+\b|\bfattibilit\w+\b|\battest\w+\b",
        "Relazione di attestazione del professionista indipendente",
        "titolo della relazione e attestazione di veridicità dei dati e fattibilità del piano (art. 87, comma 3, CCII)",
        fonte="estesa_impresa_ccii_87", role="perizia_di_parte",
    ),
    _ricorso(
        "imp_omologazione_accordi_ristrutturazione",
        r"(?:ricorso|domanda)\s+(?:per\s+(?:l.?\s*)?)?(?:di\s+)?omologa(?:zione)?\s+(?:degli\s+|dell.?\s*)?accord[oi]\s+di\s+ristrutturazione" + _CODA,
        r"\bcreditor\w+\b|\b5[7-9]\b|\b6[01]\b|\battest\w+\b",
        "Domanda di omologazione degli accordi di ristrutturazione dei debiti",
        "titolo della domanda e accordi con i creditori (artt. 57, 60 e 61 CCII)",
        fonte="estesa_impresa_ccii_57",
    ),
    _ricorso(
        "imp_piano_ristrutturazione_omologazione",
        r"(?:(?:domanda|ricorso)\s+(?:di\s+accesso\s+al|per\s+(?:l.?\s*)?omologazione\s+del|di\s+omologazione\s+del)\s+)?"
        r"piano\s+di\s+ristrutturazione\s+soggetto\s+(?:a|ad)\s+omologa(?:zione)?" + _CODA,
        r"\b64-?bis\b|\bclass[ie]\b|\bcreditor\w+\b",
        "Piano di ristrutturazione soggetto a omologazione",
        "titolo della domanda e piano votato per classi di creditori (art. 64-bis CCII)",
        fonte="estesa_impresa_ccii_64bis",
    ),
    _documento(
        "imp_piano_attestato_risanamento",
        r"piano\s+(?:attestato\s+)?di\s+risanamento" + _CODA,
        r"\battest\w+\b|\brisanament\w+\b|\b56\b",
        "Piano attestato di risanamento",
        "titolo del piano e attestazione del professionista indipendente (art. 56 CCII)",
        fonte="estesa_impresa_ccii_56",
    ),
    _istanza(
        "imp_istanza_composizione_negoziata",
        r"istanza\s+di\s+(?:nomina\s+dell.?\s*esperto|accesso\s+alla\s+composizione\s+negoziata)" + _CODA
        + r"|istanza\s+(?:per\s+la\s+)?composizione\s+negoziata" + _CODA,
        r"\besperto\b|\bcomposizione\s+negoziata\b|\b17\b|\bpiattaforma\b",
        "Istanza di accesso alla composizione negoziata della crisi",
        "titolo dell'istanza e nomina dell'esperto tramite la piattaforma telematica (artt. 12 e 17 CCII)",
        fonte="estesa_impresa_ccii_17", in_busta=False,
    ),
    _ricorso(
        "imp_ricorso_misure_protettive",
        r"ricorso\s+per\s+(?:la\s+)?(?:conferma|concessione)\s+(?:delle\s+)?misure\s+protettive" + _CODA
        + r"|ricorso\s+(?:ex\s+)?artt?\.?\s*(?:18|19)(?:\s+e\s+19)?\s+ccii" + _CODA
        + r"|istanza\s+di\s+(?:applicazione\s+di\s+)?misure\s+protettive" + _CODA,
        r"\bprotettiv\w+\b|\bcautelar\w+\b|\besperto\b|\b19\b",
        "Ricorso per la conferma delle misure protettive",
        "titolo del ricorso e conferma delle misure protettive nella composizione negoziata (artt. 18 e 19 CCII)",
        fonte="estesa_impresa_ccii_19",
    ),
    _relazione(
        "imp_relazione_finale_esperto",
        r"relazione\s+finale\s+dell.?\s*esperto" + _CODA,
        r"\bcomposizione\s+negoziata\b|\btrattative\b|\b17\b",
        "Relazione finale dell'esperto (composizione negoziata)",
        "titolo della relazione con cui l'esperto chiude le trattative (art. 17, comma 8, CCII)",
        fonte="estesa_impresa_ccii_17",
    ),
    _ricorso(
        "imp_domanda_liquidazione_controllata",
        r"(?:domanda|ricorso|istanza)\s+(?:di|per\s+(?:l.?\s*apertura\s+della\s+)?)\s*liquidazione\s+controllata" + _CODA,
        r"\bsovraindebit\w+\b|\bocc\b|\bgestore\b|\b268\b|\bliquidator\w+\b",
        "Domanda di liquidazione controllata",
        "titolo della domanda e sovraindebitamento del debitore (art. 268 CCII)",
        fonte="estesa_impresa_ccii_268",
    ),
    _provvedimento(
        "imp_sentenza_liquidazione_controllata",
        r"sentenza\s+(?:di\s+apertura\s+(?:della\s+)?|dichiarativa\s+(?:della\s+)?|che\s+dichiara\s+aperta\s+la\s+)?liquidazione\s+controllata" + _CODA,
        r"\bliquidator\w+\b|\b270\b|\bdichiara\s+aperta\b",
        "Sentenza di apertura della liquidazione controllata",
        "titolo della sentenza e nomina del liquidatore (art. 270 CCII)",
        fonte="estesa_impresa_ccii_270", tipo=TipoDocumento.SENTENZA,
    ),
    _relazione(
        "imp_relazione_occ",
        r"relazione\s+(?:particolareggiata\s+)?(?:del(?:l.)?\s*)?(?:occ|organismo\s+di\s+composizione\s+della\s+crisi|gestore\s+della\s+crisi)" + _CODA,
        r"\bsovraindebit\w+\b|\bdiligenza\b|\bmeritevol\w+\b|\b68\b|\b76\b|\b269\b",
        "Relazione particolareggiata dell'OCC",
        "titolo della relazione del gestore della crisi sul sovraindebitamento (artt. 68, 76 e 269 CCII)",
        fonte="estesa_impresa_ccii_68",
    ),
    _ricorso(
        "imp_azione_revocatoria_concorsuale",
        r"(?:atto\s+di\s+citazione\s+(?:per|in)\s+|azione\s+)revocatoria\s+(?:fallimentare|concorsuale|ex\s+art\.?\s*16[56])" + _CODA,
        r"\bcurator\w+\b|\b16[3-6]\b|\binsolvenz\w+\b|\bliquidazione\s+giudiziale\b",
        "Azione revocatoria concorsuale",
        "titolo dell'atto e revoca di pagamenti e garanzie del debitore insolvente (art. 166 CCII)",
        fonte="estesa_impresa_ccii_166", tipo=TipoDocumento.CITAZIONE,
    ),
    _ricorso(
        "imp_concordato_liquidazione_giudiziale",
        r"proposta\s+di\s+concordato\s+(?:fallimentare|nella\s+liquidazione\s+giudiziale)" + _CODA,
        r"\bcreditor\w+\b|\b240\b|\bcurator\w+\b|\bproponent\w+\b",
        "Proposta di concordato nella liquidazione giudiziale",
        "titolo della proposta ai creditori nella liquidazione giudiziale (art. 240 CCII)",
        fonte="estesa_impresa_ccii_240",
    ),
)

_SOCIETA = (
    _contratto(
        "imp_atto_costitutivo",
        r"atto\s+costitutivo" + _CODA + r"|costituzione\s+di\s+societ[aà]" + _CODA,
        r"\bcapitale\s+sociale\b|\boggetto\s+sociale\b|\b2328\b|\b2463\b",
        "Atto costitutivo di società",
        "titolo dell'atto e capitale e oggetto sociale (artt. 2328 e 2463 c.c.)",
        fonte="estesa_impresa_cc_2328",
    ),
    _contratto(
        "imp_statuto_sociale",
        r"statuto(?:\s+(?:sociale|della\s+societ[aà]|di\s+.+))?",
        r"\bcapitale\s+sociale\b|\boggetto\s+sociale\b|\bdenominazione\s+sociale\b|\b2328\b",
        "Statuto sociale",
        "titolo dello statuto e norme di funzionamento della società (art. 2328, terzo comma, c.c.)",
        fonte="estesa_impresa_cc_2328",
    ),
    _contratto(
        "imp_cessione_quote",
        r"(?:atto\s+di\s+)?(?:cessione|trasferimento|compravendita)\s+(?:di\s+)?(?:quote|partecipazion[ei])" + _CODA,
        r"\bquot\w+\b|\bcedent\w+\b|\bcessionari\w+\b|\b2470\b",
        "Atto di cessione di quote sociali",
        "titolo dell'atto e trasferimento delle partecipazioni di s.r.l. (art. 2470 c.c.)",
        fonte="estesa_impresa_cc_2470",
    ),
    _documento(
        "imp_bilancio_esercizio",
        r"bilancio\s+(?:d.?\s*esercizio|di\s+esercizio|abbreviato|consolidato|(?:chiuso\s+)?al\s+\d.*|(?:dell.?\s*)?esercizio\s+\d.*)" + _CODA,
        r"\bstato\s+patrimoniale\b|\bconto\s+economico\b|\bnota\s+integrativa\b|\b2423\b",
        "Bilancio d'esercizio",
        "titolo del bilancio e stato patrimoniale, conto economico e nota integrativa (art. 2423 c.c.)",
        fonte="estesa_impresa_cc_2423",
    ),
    _documento(
        "imp_relazione_sindaci_revisore",
        r"relazione\s+(?:unitaria\s+)?(?:del\s+collegio\s+sindacale|dei\s+sindaci|del\s+sindaco\s+unico|del\s+revisore(?:\s+(?:legale|indipendente))?"
        r"|della\s+societ[aà]\s+di\s+revisione|di\s+revisione)" + _CODA,
        r"\bbilanci\w+\b|\b2429\b|\brevision\w+\b|\bsindac\w+\b",
        "Relazione del collegio sindacale o del revisore",
        "titolo della relazione sul bilancio dell'esercizio (art. 2429 c.c.)",
        fonte="estesa_impresa_cc_2429",
    ),
    _ricorso(
        "imp_denuncia_gravi_irregolarita",
        r"(?:ricorso|denuncia|denunzia)\s+(?:per|di)\s+gravi\s+irregolarit[aà]" + _CODA
        + r"|(?:ricorso|denuncia|denunzia)\s+(?:ex\s+)?art\.?\s*2409" + _CODA,
        r"\bamministrator\w+\b|\b2409\b|\birregolarit\w+\b",
        "Denuncia di gravi irregolarità (art. 2409 c.c.)",
        "titolo del ricorso e gravi irregolarità nella gestione degli amministratori (art. 2409 c.c.)",
        fonte="estesa_impresa_cc_2409",
    ),
    _ricorso(
        "imp_nomina_liquidatore_societa",
        r"ricorso\s+per\s+(?:la\s+)?nomina\s+(?:del\s+|dei\s+)?liquidator[ei](?:\s+della\s+societ[aà])?" + _CODA
        + r"|ricorso\s+(?:per\s+l.?\s*accertamento\s+della\s+causa\s+di\s+scioglimento|ex\s+art\.?\s*248[57])" + _CODA,
        r"\bscioglimento\b|\b248[457]\b|\bsoci\b",
        "Ricorso per la nomina del liquidatore della società",
        "titolo del ricorso e causa di scioglimento della società (artt. 2484 e 2487 c.c.)",
        fonte="estesa_impresa_cc_2487",
    ),
    _contratto(
        "imp_patto_parasociale",
        r"patt[oi]\s+parasocial[ei]" + _CODA + r"|accordo\s+parasociale" + _CODA + r"|sindacato\s+di\s+(?:voto|blocco)" + _CODA,
        r"\bsoci\b|\bazion\w+\b|\bquot\w+\b|\bvoto\b|\b2341\b",
        "Patto parasociale",
        "titolo del patto e accordi fra soci sul voto o sul trasferimento delle partecipazioni (art. 2341-bis c.c.)",
        fonte="estesa_impresa_cc_2341bis",
    ),
    _contratto(
        "imp_fusione_scissione",
        r"progetto\s+(?:comune\s+)?di\s+(?:fusione|scissione)" + _CODA + r"|atto\s+di\s+(?:fusione|scissione|trasformazione)" + _CODA,
        r"\bincorporant\w+\b|\bbeneficiari\w+\b|\bconcambio\b|\b2501\b|\b2506\b|\b2498\b",
        "Progetto di fusione o scissione",
        "titolo del progetto e rapporto di cambio fra le società partecipanti (artt. 2501-ter e 2506-bis c.c.)",
        fonte="estesa_impresa_cc_2501ter",
    ),
    _contratto(
        "imp_trasferimento_azienda",
        r"(?:atto\s+di\s+|contratto\s+di\s+)?(?:cessione|affitto|conferimento|trasferimento)\s+(?:di\s+|dell.?\s*|del\s+)?(?:ramo\s+)?d.?\s*azienda" + _CODA
        + r"|(?:atto\s+di\s+|contratto\s+di\s+)?(?:cessione|affitto|conferimento|trasferimento)\s+(?:dell.?\s*|di\s+)azienda" + _CODA,
        r"\bcedent\w+\b|\bcessionari\w+\b|\baffittuari\w+\b|\b255[6-9]\b|\b2560\b",
        "Atto di trasferimento d'azienda",
        "titolo dell'atto e trasferimento dell'azienda o del ramo d'azienda (art. 2556 c.c.)",
        fonte="estesa_impresa_cc_2556",
    ),
    _contratto(
        "imp_contratto_franchising",
        r"contratto\s+di\s+(?:affiliazione\s+commerciale|franchising)" + _CODA,
        r"\baffiliant\w+\b|\baffiliat\w+\b|\bfranchisor\b|\bfranchisee\b|\b129/2004\b|\broyalt\w+\b",
        "Contratto di affiliazione commerciale (franchising)",
        "titolo del contratto e obblighi di affiliante e affiliato (art. 3 L. 129/2004)",
        fonte="estesa_impresa_l129_2004",
    ),
)

_PROPRIETA_INTELLETTUALE = (
    _documento(
        "imp_domanda_registrazione_marchio",
        r"domanda\s+di\s+(?:registrazione\s+(?:di|del|per)\s+(?:un\s+)?marchio|marchio)" + _CODA,
        r"\bmarchi\w*\b|\bclassi\b|\bnizza\b|\b156\b|\buibm\b",
        "Domanda di registrazione di marchio",
        "titolo della domanda e classi dei prodotti e servizi (artt. 148 e 156 c.p.i.)",
        fonte="estesa_impresa_cpi_148", role="titolo_proprieta_industriale",
    ),
    _documento(
        "imp_domanda_brevetto",
        r"domanda\s+di\s+brevetto" + _CODA
        + r"|domanda\s+di\s+(?:registrazione\s+(?:di|del)\s+)?(?:modello\s+di\s+utilit[aà]|disegno\s+(?:o|e)\s+modello)" + _CODA,
        r"\brivendicazion\w+\b|\binvenzion\w+\b|\b160\b|\binventor\w+\b",
        "Domanda di brevetto",
        "titolo della domanda, descrizione e rivendicazioni (art. 160 c.p.i.)",
        fonte="estesa_impresa_cpi_160", role="titolo_proprieta_industriale",
    ),
    _documento(
        "imp_attestato_titolo_proprieta_industriale",
        r"(?:attestato|certificato)\s+di\s+(?:registrazione\s+(?:di|del|dell.?\s*)\s*(?:marchio|disegno|modello)|brevetto|concessione\s+(?:di\s+|del\s+)?brevetto)" + _CODA
        + r"|brevetto\s+per\s+invenzione\s+industriale" + _CODA,
        r"\btitolar\w+\b|\buibm\b|\bufficio\s+italiano\s+brevetti\b|\bdata\s+di\s+deposito\b|\b53\b",
        "Attestato di brevetto o di registrazione di marchio",
        "titolo dell'attestato e diritti acquisiti con la brevettazione o la registrazione (art. 53 c.p.i.)",
        fonte="estesa_impresa_cpi_53", role="certificato",
    ),
    _ricorso(
        "imp_opposizione_registrazione_marchio",
        r"(?:atto\s+di\s+)?opposizione\s+(?:alla\s+(?:domanda\s+di\s+)?registrazione\s+(?:di|del|dell.?\s*)\s*marchio|(?:al|a)\s+marchio"
        r"|(?:ex\s+)?art\.?\s*176(?:\s+c\.?\s*p\.?\s*i\.?)?)" + _CODA,
        r"\bmarchi\w*\b|\bopponent\w+\b|\b176\b|\buibm\b|\beuipo\b|\banteriorit\w+\b",
        "Opposizione alla registrazione di marchio",
        "titolo dell'atto e marchio anteriore dell'opponente (art. 176 c.p.i.)",
        fonte="estesa_impresa_cpi_176", in_busta=False,
    ),
    _lettera(
        "imp_diffida_contraffazione",
        r"(?:lettera\s+di\s+)?diffida\s+(?:per|da|dalla|alla\s+cessazione\s+(?:della|dell.?))\s*(?:contraffazione"
        r"|violazione\s+(?:del|dei|di)\s+(?:marchio|marchi|brevetto|brevetti|diritt[oi]\s+(?:d.?\s*autore|di\s+propriet[aà]\s+(?:industriale|intellettuale))))" + _CODA
        + r"|diffida\s+(?:all.?\s*)?uso\s+(?:illecito\s+)?(?:del\s+)?marchio" + _CODA,
        r"\bcontraffa\w+\b|\bmarchi\w*\b|\bbrevett\w+\b|\bdiritto\s+d.?\s*autore\b|\b633/1941\b",
        "Diffida per contraffazione",
        "titolo della diffida e diritti esclusivi del titolare (art. 20 c.p.i.; art. 156 L. 633/1941)",
        fonte="estesa_impresa_cpi_20",
    ),
    _ricorso(
        "imp_ricorso_descrizione_sequestro",
        r"ricorso\s+(?:cautelare\s+)?per\s+(?:la\s+)?(?:descrizione(?:\s+e\s+(?:il\s+)?sequestro)?|sequestro)\b.*" + _CPI_SEGNALI + r".*"
        + r"|ricorso\s+per\s+(?:la\s+)?descrizione" + _CODA,
        r"\bcontraffa\w+\b|\b12[89]\b|\bc\.?\s*p\.?\s*i\b|\bmarchi\w*\b|\bbrevett\w+\b",
        "Ricorso per descrizione e sequestro (artt. 128-129 c.p.i.)",
        "titolo del ricorso e prova della contraffazione (artt. 128 e 129 c.p.i.)",
        fonte="estesa_impresa_cpi_128",
    ),
    _ricorso(
        "imp_ricorso_inibitoria_proprieta_industriale",
        r"ricorso\s+(?:cautelare\s+)?per\s+(?:l.?\s*)?inibitoria\b.*" + _CPI_SEGNALI + r".*"
        + r"|ricorso\s+(?:ex\s+)?art\.?\s*131\s+c\.?\s*p\.?\s*i\.?" + _CODA,
        r"\binibitori\w+\b|\b131\b|\bcontraffa\w+\b",
        "Ricorso per inibitoria in materia di proprietà industriale (art. 131 c.p.i.)",
        "titolo del ricorso e inibitoria della fabbricazione e del commercio (art. 131 c.p.i.)",
        fonte="estesa_impresa_cpi_131",
    ),
    _ricorso(
        "imp_azione_contraffazione",
        r"(?:atto\s+di\s+citazione\s+(?:per|in\s+materia\s+di)\s+|azione\s+(?:di|per)\s+)contraffazione" + _CODA,
        r"\bcontraffa\w+\b|\b12[45]\b|\bc\.?\s*p\.?\s*i\b|\bsezione\s+specializzata\b",
        "Azione di contraffazione",
        "titolo dell'atto e misure correttive e risarcimento per la contraffazione (artt. 124 e 125 c.p.i.)",
        fonte="estesa_impresa_cpi_124", tipo=TipoDocumento.CITAZIONE,
    ),
    _ricorso(
        "imp_azione_nullita_titolo",
        r"(?:atto\s+di\s+citazione\s+per\s+|azione\s+di\s+)(?:la\s+)?(?:nullit[aà]|decadenza)\s+(?:(?:e|o)\s+(?:nullit[aà]|decadenza)\s+)?"
        r"(?:del|di|dei)\s+(?:marchio|marchi|brevetto|brevetti|disegno|modello)" + _CODA,
        r"\b11[78]\b|\b122\b|\bc\.?\s*p\.?\s*i\b|\bregistrazion\w+\b|\banteriorit\w+\b",
        "Azione di nullità o decadenza del marchio o brevetto",
        "titolo dell'atto e invalidità del titolo di proprietà industriale (art. 122 c.p.i.)",
        fonte="estesa_impresa_cpi_122", tipo=TipoDocumento.CITAZIONE,
    ),
    _contratto(
        "imp_licenza_proprieta_industriale",
        r"contratto\s+di\s+licenza\s+(?:d.?\s*uso\s+)?(?:di|del|dei|su)\s+(?:marchio|marchi|brevetto|brevetti|know.?how)" + _CODA,
        r"\blicenziant\w+\b|\blicenziatari\w+\b|\broyalt\w+\b|\b23\b",
        "Contratto di licenza di marchio o brevetto",
        "titolo del contratto e licenza d'uso del titolo di proprietà industriale (art. 23 c.p.i.)",
        fonte="estesa_impresa_cpi_23",
    ),
    _contratto(
        "imp_contratto_edizione",
        r"contratto\s+di\s+edizione" + _CODA
        + r"|contratto\s+di\s+cessione\s+(?:dei\s+)?diritti\s+(?:d.?\s*autore|di\s+utilizzazione\s+economica)" + _CODA,
        r"\beditor\w+\b|\b118\b|\b633/1941\b|\bdiritti\s+di\s+utilizzazione\b",
        "Contratto di edizione o di cessione dei diritti d'autore",
        "titolo del contratto e concessione all'editore del diritto di pubblicare l'opera (art. 118 L. 633/1941)",
        fonte="estesa_impresa_lda_118",
    ),
    _ricorso(
        "imp_azione_diritto_autore",
        r"(?:atto\s+di\s+citazione\s+per\s+|azione\s+(?:di|per)\s+|ricorso\s+per\s+)(?:(?:la\s+)?violazione\s+(?:del\s+|dei\s+)?diritt[oi]\s+d.?\s*autore|plagio)" + _CODA,
        r"\bautor\w+\b|\b156\b|\b633/1941\b|\bplagi\w+\b",
        "Azione per violazione del diritto d'autore",
        "titolo dell'atto e tutela giurisdizionale dei diritti di utilizzazione (art. 156 L. 633/1941)",
        fonte="estesa_impresa_lda_156", tipo=TipoDocumento.CITAZIONE,
    ),
)

_BANCA_FINANZA = (
    _contratto(
        "imp_contratto_conto_corrente",
        r"contratto\s+di\s+(?:apertura\s+di\s+)?conto\s+corrente(?:\s+(?:bancario|di\s+corrispondenza|ordinario))?" + _CODA,
        r"\bbanc\w+\b|\bcorrentist\w+\b|\b117\b|\b1852\b",
        "Contratto di conto corrente bancario",
        "titolo del contratto e forma scritta dei contratti bancari (art. 117 D.Lgs. 385/1993)",
        fonte="estesa_impresa_tub_117",
    ),
    _contratto(
        "imp_contratto_mutuo",
        r"(?:contratto|atto)\s+di\s+mutuo" + _CODA + r"|mutuo\s+(?:fondiario|ipotecario|chirografario)" + _CODA,
        r"\bmutuatari\w+\b|\bmutuant\w+\b|\bammortament\w+\b|\b1813\b",
        "Contratto di mutuo",
        "titolo del contratto e consegna della somma con obbligo di restituzione (art. 1813 c.c.)",
        fonte="estesa_impresa_cc_1813",
    ),
    _contratto(
        "imp_contratto_fideiussione",
        r"(?:contratto|atto)\s+di\s+fideiussione" + _CODA + r"|fideiussione\s+(?:omnibus|specifica|bancaria|a\s+garanzia)" + _CODA
        + r"|garanzia\s+fideiussoria" + _CODA,
        r"\bfideiussor\w+\b|\b1936\b|\b1944\b|\bdebitore\s+principale\b",
        "Contratto di fideiussione",
        "titolo del contratto e obbligazione del fideiussore verso il creditore (art. 1936 c.c.)",
        fonte="estesa_impresa_cc_1936",
    ),
    _documento(
        "imp_estratto_conto_certificato",
        r"estratto\s+(?:di\s+|del\s+)?(?:saldaconto|conto)\s+(?:certificato\s+)?(?:conforme\s+)?(?:ex|ai\s+sensi\s+dell.?)\s*art\.?\s*50" + _CODA
        + r"|estratto\s+(?:conto\s+)?certificato" + _CODA + r"|saldaconto\s+certificato" + _CODA,
        r"\b50\b|\bcertific\w+\b|\bdirigent\w+\b|\b385/1993\b",
        "Estratto conto certificato (art. 50 TUB)",
        "titolo dell'estratto e certificazione del credito per il decreto ingiuntivo bancario (art. 50 D.Lgs. 385/1993)",
        fonte="estesa_impresa_tub_50",
    ),
    _ricorso(
        "imp_ricorso_abf",
        r"ricorso\s+(?:all.?\s*|al\s+collegio\s+(?:di\s+\w+\s+)?dell.?\s*|presso\s+l.?\s*)arbitro\s+bancario(?:\s+finanziario)?" + _CODA
        + r"|ricorso\s+(?:all.?\s*)?abf" + _CODA,
        r"\barbitro\s+bancario\b|\babf\b|\b128-?bis\b|\bintermediari\w*\b",
        "Ricorso all'Arbitro Bancario Finanziario (ABF)",
        "titolo del ricorso e controversia con l'intermediario (art. 128-bis D.Lgs. 385/1993)",
        fonte="estesa_impresa_tub_128bis", in_busta=False,
    ),
    _provvedimento(
        "imp_decisione_abf",
        r"decisione\s+(?:del\s+collegio\s+(?:di\s+\w+\s+)?)?(?:dell.?\s*)?(?:arbitro\s+bancario(?:\s+finanziario)?|abf)" + _CODA,
        r"\bcollegio\b|\bricorrent\w+\b|\bintermediari\w*\b",
        "Decisione dell'Arbitro Bancario Finanziario",
        "titolo della decisione del collegio ABF (art. 128-bis D.Lgs. 385/1993)",
        fonte="estesa_impresa_tub_128bis", tipo=TipoDocumento.ALLEGATO, role="atto_ufficio",
    ),
    _lettera(
        "imp_reclamo_intermediario",
        r"reclamo\s+(?:alla\s+banca|all.?\s*intermediario|all.?\s*ufficio\s+reclami|(?:ex\s+)?(?:art\.?\s*)?128-?bis)" + _CODA,
        r"\bbanc\w+\b|\bintermediari\w*\b|\b128\b",
        "Reclamo all'intermediario bancario o finanziario",
        "titolo del reclamo che precede il ricorso all'ABF o all'ACF (art. 128-bis D.Lgs. 385/1993)",
        fonte="estesa_impresa_tub_128bis",
    ),
    _ricorso(
        "imp_ricorso_acf",
        r"ricorso\s+(?:all.?\s*|presso\s+l.?\s*)?(?:arbitro\s+per\s+le\s+controversie\s+finanziarie|acf)" + _CODA,
        r"\bconsob\b|\bacf\b|\bcontroversie\s+finanziarie\b|\bintermediari\w*\b|\b32-?ter\b",
        "Ricorso all'Arbitro per le Controversie Finanziarie (ACF)",
        "titolo del ricorso e servizi di investimento contestati (art. 32-ter D.Lgs. 58/1998)",
        fonte="estesa_impresa_tuf_32ter", in_busta=False,
    ),
    _provvedimento(
        "imp_decisione_acf",
        r"decisione\s+(?:del\s+collegio\s+)?(?:dell.?\s*)?(?:arbitro\s+per\s+le\s+controversie\s+finanziarie|acf)" + _CODA,
        r"\bcollegio\b|\bricorrent\w+\b|\bintermediari\w*\b",
        "Decisione dell'Arbitro per le Controversie Finanziarie",
        "titolo della decisione del collegio ACF (art. 32-ter D.Lgs. 58/1998)",
        fonte="estesa_impresa_tuf_32ter", tipo=TipoDocumento.ALLEGATO, role="atto_ufficio",
    ),
    _contratto(
        "imp_contratto_servizi_investimento",
        r"contratto\s+(?:quadro\s+)?(?:per\s+(?:la\s+prestazione\s+(?:dei|di)\s+)?servizi\s+di\s+investimento"
        r"|di\s+(?:gestione\s+(?:di\s+portafogli|patrimoniale)|consulenza\s+in\s+materia\s+di\s+investimenti))" + _CODA,
        r"\binvestiment\w+\b|\bstrumenti\s+finanziari\b|\b58/1998\b|\bmifid\b",
        "Contratto quadro per servizi di investimento",
        "titolo del contratto e forma scritta per i servizi di investimento (art. 23 D.Lgs. 58/1998)",
        fonte="estesa_impresa_tuf_23",
    ),
    _contratto(
        "imp_contratto_credito_consumatori",
        r"contratto\s+di\s+(?:credito\s+(?:ai\s+consumatori|al\s+consumo)|prestito\s+personale|finanziamento\s+(?:finalizzato|al\s+consumo|personale))" + _CODA,
        r"\btaeg\b|\btan\b|\bconsumator\w+\b|\b125-?bis\b|\bfinanziator\w+\b",
        "Contratto di credito ai consumatori",
        "titolo del contratto e TAEG indicato per iscritto (art. 125-bis D.Lgs. 385/1993)",
        fonte="estesa_impresa_tub_125bis",
    ),
    _documento(
        "imp_modulo_secci",
        r"(?:modulo\s+)?(?:secci|informazioni\s+europee\s+di\s+base\s+sul\s+credito\s+ai\s+consumatori)" + _CODA,
        r"\btaeg\b|\btan\b|\bfinanziator\w+\b|\b124\b",
        "Modulo SECCI (informazioni europee di base sul credito ai consumatori)",
        "titolo del modulo e informazioni precontrattuali sul credito ai consumatori (art. 124 D.Lgs. 385/1993)",
        fonte="estesa_impresa_tub_124",
    ),
    _contratto(
        "imp_contratto_cessione_quinto",
        r"contratto\s+di\s+(?:prestito\s+(?:con|contro)\s+)?cessione\s+(?:del|di\s+un)\s+quinto" + _CODA
        + r"|(?:contratto\s+di\s+)?delegazione\s+di\s+pagamento" + _CODA,
        r"\bquinto\b|\bstipendi\w*\b|\bpension\w+\b|\b180/1950\b",
        "Contratto di cessione del quinto",
        "titolo del contratto e cessione di quote dello stipendio o della pensione (art. 5 D.P.R. 180/1950)",
        fonte="estesa_impresa_dpr_180_1950",
    ),
    _contratto(
        "imp_contratto_leasing",
        r"contratto\s+di\s+(?:locazione\s+finanziaria|leasing)(?:\s+(?:finanziario|immobiliare|strumentale|abitativo|mobiliare))?" + _CODA,
        r"\bconcedent\w+\b|\butilizzator\w+\b|\briscatto\b|\b124/2017\b",
        "Contratto di leasing finanziario",
        "titolo del contratto e obblighi di concedente e utilizzatore (art. 1, commi 136-140, L. 124/2017)",
        fonte="estesa_impresa_l124_2017",
    ),
)

_ASSICURAZIONI = (
    _contratto(
        "imp_polizza_assicurazione",
        r"polizza\s+(?:di\s+assicurazione|assicurativa)" + _CODA + r"|contratto\s+di\s+assicurazione" + _CODA
        + r"|condizioni\s+(?:generali\s+)?di\s+assicurazione" + _CODA,
        r"\bcontraente\b|\bpremio\b|\bmassimal\w+\b|\b1882\b",
        "Polizza di assicurazione",
        "titolo della polizza e obbligo dell'assicuratore verso il contraente (artt. 1882 e 1888 c.c.)",
        fonte="estesa_impresa_cc_1882",
    ),
    _lettera(
        "imp_denuncia_sinistro_assicuratore",
        r"denuncia\s+(?:di|del)\s+sinistro(?:\s+(?:all.?\s*assicurat\w+|alla\s+compagnia|all.?\s*impresa\s+(?:di\s+assicurazione|assicuratrice)|ex\s+art\.?\s*1913).*)?"
        r"|avviso\s+di\s+sinistro" + _CODA,
        r"\b1913\b|\bpolizza\b|\bassicurat\w+\b|\bcompagnia\b",
        "Denuncia di sinistro all'assicuratore",
        "titolo della denuncia e avviso del sinistro all'assicuratore (art. 1913 c.c.)",
        fonte="estesa_impresa_cc_1913",
    ),
    _lettera(
        "imp_reclamo_ivass",
        r"reclamo\s+(?:all.?\s*)?ivass" + _CODA + r"|reclamo\s+all.?\s*istituto\s+per\s+la\s+vigilanza\s+sulle\s+assicurazioni" + _CODA,
        r"\bivass\b|\bimpresa\s+di\s+assicurazion\w+\b|\bpolizza\b|\bintermediari\w*\b",
        "Reclamo all'IVASS",
        "titolo del reclamo all'autorità di vigilanza sulle assicurazioni (art. 7 D.Lgs. 209/2005)",
        fonte="estesa_impresa_cap_7",
    ),
    _lettera(
        "imp_reclamo_impresa_assicurazione",
        r"reclamo\s+(?:alla\s+compagnia(?:\s+(?:di\s+assicurazion\w+|assicuratrice))?|all.?\s*impresa\s+(?:di\s+assicurazion\w+|assicuratrice)|all.?\s*assicuratore)" + _CODA,
        r"\bpolizza\b|\bsinistro\b|\bassicurat\w+\b|\b45\s+giorni\b",
        "Reclamo all'impresa di assicurazione",
        "titolo del reclamo all'impresa che precede il reclamo all'IVASS (art. 7 D.Lgs. 209/2005)",
        fonte="estesa_impresa_cap_7",
    ),
    _ricorso(
        "imp_ricorso_arbitro_assicurativo",
        r"ricorso\s+(?:all.?\s*)?(?:arbitro\s+assicurativo|aas)" + _CODA,
        r"\bivass\b|\barbitro\s+assicurativo\b|\bimpresa\s+di\s+assicurazion\w+\b|\bpolizza\b|\b187\b",
        "Ricorso all'Arbitro assicurativo",
        "titolo del ricorso al sistema di risoluzione stragiudiziale presso l'IVASS (art. 187.1 D.Lgs. 209/2005)",
        fonte="estesa_impresa_cap_187_1", in_busta=False,
    ),
)

_CONSUMATORI_CONCORRENZA = (
    _lettera(
        "imp_recesso_consumatore",
        r"(?:modulo|comunicazione|dichiarazione)\s+(?:tipo\s+)?(?:di\s+)?(?:esercizio\s+del\s+(?:diritto\s+di\s+)?)?recesso"
        r"(?:\s+(?:del\s+consumatore|dal\s+contratto\s+(?:a\s+distanza|concluso\s+fuori\s+dei\s+locali\s+commerciali)|ex\s+art\.?\s*5[2-9]).*)?",
        r"\bconsumator\w+\b|\bcodice\s+del\s+consumo\b|\b206/2005\b|\bfuori\s+dei\s+locali\b",
        "Comunicazione di recesso del consumatore",
        "titolo della comunicazione e recesso dal contratto a distanza o fuori dei locali (artt. 52-54 D.Lgs. 206/2005)",
        fonte="estesa_impresa_consumo_52",
    ),
    _lettera(
        "imp_garanzia_legale_conformita",
        r"richiesta\s+(?:di\s+)?(?:intervento\s+in\s+garanzia|riparazione\s+o\s+sostituzione|ripristino\s+della\s+conformit[aà]"
        r"|rimedi\s+per\s+(?:il\s+)?difetto\s+di\s+conformit[aà])" + _CODA
        + r"|(?:richiesta|attivazione)\s+(?:della\s+)?garanzia\s+legale(?:\s+di\s+conformit[aà])?" + _CODA,
        r"\bconformit\w+\b|\bgaranzi\w+\b|\b135\b",
        "Richiesta di rimedi per difetto di conformità (garanzia legale)",
        "titolo della richiesta e rimedi del consumatore contro il venditore (art. 135-bis D.Lgs. 206/2005)",
        fonte="estesa_impresa_consumo_135bis",
    ),
    _istanza(
        "imp_adesione_azione_classe",
        r"(?:domanda|atto)\s+di\s+adesione\s+(?:all.?\s*)?azione\s+di\s+classe" + _CODA + r"|adesione\s+all.?\s*azione\s+di\s+classe" + _CODA,
        r"\baderent\w+\b|\b840\b|\badesion\w+\b|\bportale\b",
        "Domanda di adesione all'azione di classe",
        "titolo della domanda di adesione inserita nel fascicolo informatico (art. 840-septies c.p.c.)",
        fonte="estesa_impresa_cpc_840septies",
    ),
    _ricorso(
        "imp_ricorso_azione_classe",
        r"(?:ricorso|atto)\s+(?:per|di|introduttivo\s+(?:dell.?|di))\s*(?:l.?\s*)?azione\s+di\s+classe" + _CODA
        + r"|azione\s+di\s+classe" + _CODA + r"|class\s+action" + _CODA,
        r"\b840\b|\bclasse\b|\bdiritti\s+individuali\s+omogenei\b",
        "Ricorso per azione di classe",
        "titolo del ricorso e diritti individuali omogenei (artt. 840-bis e 840-ter c.p.c.)",
        fonte="estesa_impresa_cpc_840bis",
    ),
    _ricorso(
        "imp_azione_inibitoria_collettiva",
        r"(?:ricorso|atto)\s+(?:per\s+(?:l.?\s*)?)?(?:azione\s+)?inibitoria\s+collettiva" + _CODA + r"|azione\s+inibitoria\s+collettiva" + _CODA,
        r"\b840\b|\binibitori\w+\b|\bcondott\w+\b",
        "Azione inibitoria collettiva",
        "titolo dell'atto e cessazione di condotte lesive di una pluralità di soggetti (art. 840-sexiesdecies c.p.c.)",
        fonte="estesa_impresa_cpc_840sexiesdecies",
    ),
    _lettera(
        "imp_segnalazione_pratica_commerciale_scorretta",
        r"(?:segnalazione|denuncia|esposto)\s+(?:all.?\s*(?:agcm|autorit[aà]\s+garante\s+della\s+concorrenza\s+e\s+del\s+mercato)\s+)?"
        r"(?:per|di)\s+(?:una\s+)?pratic\w+\s+commercial\w+\s+scorrett\w+" + _CODA,
        r"\bpratic\w+\b|\bscorrett\w+\b|\b2[0-7]\b|\b206/2005\b",
        "Segnalazione di pratica commerciale scorretta",
        "titolo della segnalazione e tutela amministrativa contro le pratiche scorrette (artt. 20 e 27 D.Lgs. 206/2005)",
        fonte="estesa_impresa_consumo_27",
    ),
    _lettera(
        "imp_segnalazione_agcm",
        r"(?:segnalazione|denuncia|esposto)\s+(?:all.?\s*)?(?:agcm|autorit[aà]\s+garante\s+della\s+concorrenza\s+e\s+del\s+mercato)" + _CODA
        + r"|denuncia\s+di\s+(?:intesa\s+restrittiva|abuso\s+di\s+posizione\s+dominante)" + _CODA,
        r"\bintes\w+\b|\babuso\s+di\s+posizione\s+dominante\b|\b287/1990\b|\bconcorrenza\b",
        "Segnalazione all'Autorità garante della concorrenza e del mercato",
        "titolo della segnalazione di intese o abusi all'AGCM (art. 12 L. 287/1990)",
        fonte="estesa_impresa_l287_12",
    ),
    _r(
        "imp_provvedimento_agcm",
        r"provvedimento\s+(?:n\.?\s*\d+\s+)?(?:dell.?\s*)?(?:autorit[aà]\s+garante\s+della\s+concorrenza\s+e\s+del\s+mercato|agcm)" + _CODA
        + r"|l.?\s*autorit[aà]\s+garante\s+della\s+concorrenza\s+e\s+del\s+mercato",
        r"\bnella\s+(?:sua\s+)?adunanza\b|\bdelibera\b|\bdiffid\w+\b|\bsanzione\s+amministrativa\s+pecuniaria\b",
        "Provvedimento dell'Autorità garante della concorrenza e del mercato",
        "titolo del provvedimento e delibera dell'Autorità (art. 15 L. 287/1990; art. 27 D.Lgs. 206/2005)",
        fonte="estesa_impresa_l287_15", section="provvedimenti", role="atto_amministrativo", tipo=TipoDocumento.ALLEGATO,
    ),
    _lettera(
        "imp_proposta_impegni_agcm",
        r"(?:proposta|formulario|presentazione)\s+(?:di\s+(?:presentazione\s+)?)?(?:degli\s+)?impegni" + _CODA,
        r"\b14-?ter\b|\bimpegni\b|\bautorit\w+\b|\bagcm\b",
        "Proposta di impegni all'AGCM",
        "titolo della proposta di impegni per chiudere l'istruttoria (art. 14-ter L. 287/1990)",
        fonte="estesa_impresa_l287_14ter",
    ),
    _ricorso(
        "imp_risarcimento_danno_antitrust",
        r"(?:atto\s+di\s+citazione\s+per\s+(?:il\s+)?|azione\s+(?:di|per\s+il)\s+)risarcimento\s+(?:del\s+danno\s+)?(?:antitrust"
        r"|da\s+(?:violazione\s+del(?:le)?\s+(?:diritto|norme)\s+della\s+concorrenza|intesa|illecito\s+antitrust|cartello))" + _CODA,
        r"\b3/2017\b|\bantitrust\b|\bconcorrenza\b|\bcartell\w+\b|\bintes\w+\b",
        "Azione di risarcimento del danno antitrust",
        "titolo dell'atto e danno da violazione del diritto della concorrenza (artt. 1 e 18 D.Lgs. 3/2017)",
        fonte="estesa_impresa_dlgs3_2017_1", tipo=TipoDocumento.CITAZIONE,
    ),
    _istanza(
        "imp_esibizione_prove_antitrust",
        r"istanza\s+di\s+(?:ordine\s+di\s+)?esibizione\s+(?:delle\s+prove\s+)?(?:ex\s+art\.?\s*3\s+d\.?\s*lgs\.?\s*(?:n\.?\s*)?3/2017"
        r"|nel(?:l.?)?\s*(?:azione|giudizio)\s+(?:di\s+risarcimento\s+)?antitrust|in\s+materia\s+antitrust)" + _CODA,
        r"\b3/2017\b|\bantitrust\b|\besibizion\w+\b|\bconcorrenza\b",
        "Istanza di esibizione delle prove in materia antitrust",
        "titolo dell'istanza ed esibizione delle prove rilevanti (art. 3 D.Lgs. 3/2017)",
        fonte="estesa_impresa_dlgs3_2017_3",
    ),
)

REGOLE: tuple[RegolaTitolo, ...] = _CRISI + _SOCIETA + _PROPRIETA_INTELLETTUALE + _BANCA_FINANZA + _ASSICURAZIONI + _CONSUMATORI_CONCORRENZA

__all__ = ["FONTI", "REGOLE"]
