"""Persone e famiglia, minori, successioni, volontaria giurisdizione, immigrazione, cittadinanza e protezione internazionale.

Regole d'identità dal titolo aggiunte il 02/11/2026 per coprire tutte le materie (direttiva dell'avvocato del
01/11/2026). Ogni regola cita la norma che definisce l'atto, registrata in `FONTI` con URL ufficiale e data di
consultazione. Le tipologie già riconosciute da `famiglia.py`, `tutela.py` e `immigrazione.py` (separazione e
divorzio, modifica delle condizioni, piano genitoriale, amministrazione di sostegno, testamento, rinuncia ed
accettazione beneficiata, espulsione, Commissione territoriale, ricongiungimento…) non sono ripetute qui.
"""

from __future__ import annotations

from typing import Any

from pct.fascicoli import TipoDocumento

from ._modello import RegolaTitolo, regola

_VERIFICA = "testo vigente consultato su Normattiva il 02/11/2026"
_NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"
_CC = "regio.decreto:1942-03-16;262~art"
_CPC = "regio.decreto:1940-10-28;1443~art"
_TUI = "decreto.legislativo:1998-07-25;286~art"
_D_LGS_25_2008 = "decreto.legislativo:2008-01-28;25~art"
_L_184_1983 = "legge:1983-05-04;184~art"
_L_91_1992 = "legge:1992-02-05;91~art"
_L_898_1970 = "legge:1970-12-01;898~art"
_D_LGS_150_2011 = "decreto.legislativo:2011-09-01;150~art"
_DPR_396_2000 = "decreto.del.presidente.della.repubblica:2000-11-03;396~art"

# Frammenti ricorrenti dei titoli.
_CODA = r"(?:\s+.*)?"
_EREDITA = r"eredit[aà]"
_DELL = r"dell.?\s*"


def _fonte(label: str, urn: str) -> dict[str, Any]:
    return {"label": label, "official_url": _NORMATTIVA + urn, "verification_status": _VERIFICA, "source_type": "normativa"}


FONTI: dict[str, dict[str, Any]] = {
    # Famiglia (rito unificato)
    "estesa_persone_cc_figli_fuori_matrimonio": _fonte("c.c., artt. 337-bis e 337-ter: affidamento e mantenimento dei figli nati fuori dal matrimonio", _CC + "337ter"),
    "estesa_persone_cpc_provvedimenti_temporanei": _fonte("c.p.c., art. 473-bis.22: provvedimenti temporanei e urgenti alla prima udienza", _CPC + "473bis.22"),
    "estesa_persone_cpc_ordini_protezione": _fonte("c.p.c., artt. 473-bis.69 e 473-bis.70; c.c., art. 342-ter: ordini di protezione contro gli abusi familiari", _CPC + "473bis.70"),
    "estesa_persone_cpc_inadempienze": _fonte("c.p.c., art. 473-bis.39: provvedimenti in caso di inadempienze o violazioni", _CPC + "473bis.39"),
    "estesa_persone_cpc_pagamento_diretto": _fonte("c.p.c., art. 473-bis.37: pagamento diretto del terzo", _CPC + "473bis.37"),
    "estesa_persone_cpc_ascolto_minore": _fonte("c.p.c., artt. 473-bis.4 e 473-bis.5: ascolto del minore e verbale", _CPC + "473bis.5"),
    "estesa_persone_l_898_1970_tfr": _fonte("L. 898/1970, art. 12-bis: quota dell'indennità di fine rapporto all'ex coniuge", _L_898_1970 + "12bis"),
    "estesa_persone_l_898_1970_reversibilita": _fonte("L. 898/1970, art. 9: pensione di reversibilità all'ex coniuge", _L_898_1970 + "9"),
    "estesa_persone_cc_alimenti": _fonte("c.c., artt. 433-438: obbligo degli alimenti", _CC + "433"),
    # Filiazione
    "estesa_persone_cc_riconoscimento_figlio": _fonte("c.c., art. 250: riconoscimento del figlio e autorizzazione del giudice", _CC + "250"),
    "estesa_persone_cc_disconoscimento": _fonte("c.c., artt. 243-bis e 244: azione di disconoscimento della paternità", _CC + "243bis"),
    "estesa_persone_cc_dichiarazione_paternita": _fonte("c.c., art. 269: dichiarazione giudiziale di paternità e maternità", _CC + "269"),
    "estesa_persone_cc_impugnazione_riconoscimento": _fonte("c.c., art. 263: impugnazione del riconoscimento per difetto di veridicità", _CC + "263"),
    "estesa_persone_cc_responsabilita_genitoriale": _fonte("c.c., artt. 330-333: decadenza, reintegrazione e condotta pregiudizievole del genitore", _CC + "332"),
    # Adozione e affidamento
    "estesa_persone_l_184_1983_adottabilita": _fonte("L. 184/1983, art. 15: dichiarazione dello stato di adottabilità", _L_184_1983 + "15"),
    "estesa_persone_l_184_1983_disponibilita": _fonte("L. 184/1983, art. 22: dichiarazione di disponibilità all'adozione e affidamento preadottivo", _L_184_1983 + "22"),
    "estesa_persone_l_184_1983_casi_particolari": _fonte("L. 184/1983, art. 44: adozione in casi particolari", _L_184_1983 + "44"),
    "estesa_persone_l_184_1983_idoneita": _fonte("L. 184/1983, art. 30: decreto di idoneità all'adozione internazionale", _L_184_1983 + "30"),
    "estesa_persone_l_184_1983_affidamento_familiare": _fonte("L. 184/1983, art. 4: affidamento familiare del minore", _L_184_1983 + "4"),
    "estesa_persone_cc_adozione_maggiorenni": _fonte("c.c., artt. 291 e 296: adozione di persone maggiori di età", _CC + "291"),
    # Unioni civili e convivenze
    "estesa_persone_l_76_2016": _fonte("L. 76/2016, art. 1, commi 24-25, 50, 59 e 65: unioni civili, contratto di convivenza e alimenti", "legge:2016-05-20;76~art1"),
    # Persone
    "estesa_persone_cc_interdizione": _fonte("c.c., artt. 414 e 415; c.p.c., art. 712: interdizione e inabilitazione", _CC + "414"),
    "estesa_persone_cc_tutela_minori": _fonte("c.c., artt. 343 e 349: apertura della tutela e giuramento del tutore", _CC + "343"),
    "estesa_persone_l_164_1982": _fonte("L. 164/1982, art. 1; D.Lgs. 150/2011, art. 31: rettificazione di attribuzione di sesso", "legge:1982-04-14;164~art1"),
    "estesa_persone_dpr_396_2000_rettificazione": _fonte("D.P.R. 396/2000, art. 95: rettificazione degli atti dello stato civile", _DPR_396_2000 + "95"),
    "estesa_persone_dpr_396_2000_nome": _fonte("D.P.R. 396/2000, art. 89: cambiamento del nome e del cognome", _DPR_396_2000 + "89"),
    "estesa_persone_cc_assenza_morte_presunta": _fonte("c.c., artt. 49 e 58: dichiarazione di assenza e di morte presunta", _CC + "58"),
    # Successioni
    "estesa_persone_cc_accettazione_eredita": _fonte("c.c., art. 475: accettazione espressa dell'eredità", _CC + "475"),
    "estesa_persone_cc_actio_interrogatoria": _fonte("c.c., art. 481: fissazione di un termine per l'accettazione", _CC + "481"),
    "estesa_persone_cpc_inventario": _fonte("c.p.c., artt. 769 e 775: procedimento e processo verbale d'inventario", _CPC + "775"),
    "estesa_persone_cc_petizione_eredita": _fonte("c.c., art. 533: petizione di eredità", _CC + "533"),
    "estesa_persone_cc_divisione": _fonte("c.c., art. 713; c.p.c., art. 784: divisione ereditaria", _CC + "713"),
    "estesa_persone_cc_riduzione": _fonte("c.c., artt. 553-564: azione di riduzione per lesione di legittima", _CC + "554"),
    "estesa_persone_cpc_sigilli": _fonte("c.p.c., art. 752: apposizione dei sigilli", _CPC + "752"),
    # Volontaria giurisdizione
    "estesa_persone_cpc_reclamo_739": _fonte("c.p.c., art. 739: reclamo contro i decreti in camera di consiglio", _CPC + "739"),
    "estesa_persone_cc_autorizzazioni_tutelare": _fonte("c.c., artt. 320, 374, 375 e 411: autorizzazioni del giudice tutelare", _CC + "374"),
    # Immigrazione
    "estesa_persone_d_lgs_150_2011_espulsione": _fonte("D.Lgs. 150/2011, art. 18; D.Lgs. 286/1998, art. 13, c. 8: opposizione al decreto di espulsione", _D_LGS_150_2011 + "18"),
    "estesa_persone_tui_trattenimento": _fonte("D.Lgs. 286/1998, art. 14: trattenimento nei centri di permanenza per il rimpatrio e convalida", _TUI + "14"),
    "estesa_persone_tui_respingimento": _fonte("D.Lgs. 286/1998, art. 10: respingimento", _TUI + "10"),
    "estesa_persone_tui_permesso_soggiorno": _fonte("D.Lgs. 286/1998, art. 5: permesso di soggiorno, rilascio, rinnovo e rifiuto", _TUI + "5"),
    "estesa_persone_tui_ricorso_permesso": _fonte("D.Lgs. 286/1998, art. 6, c. 10: ricorso al TAR contro i provvedimenti sul permesso di soggiorno", _TUI + "6"),
    "estesa_persone_tui_ricongiungimento_ricorso": _fonte("D.Lgs. 286/1998, art. 30, c. 6; D.Lgs. 150/2011, art. 20: ricorso contro il diniego del ricongiungimento", _TUI + "30"),
    "estesa_persone_tui_protezione_speciale": _fonte("D.Lgs. 286/1998, art. 19, c. 1.1; D.Lgs. 25/2008, art. 32, c. 3: protezione speciale", _TUI + "19"),
    "estesa_persone_d_lgs_25_2008_domanda": _fonte("D.Lgs. 25/2008, art. 26: presentazione della domanda di protezione internazionale", _D_LGS_25_2008 + "26"),
    "estesa_persone_d_lgs_25_2008_audizione": _fonte("D.Lgs. 25/2008, artt. 12 e 14: colloquio personale e verbale", _D_LGS_25_2008 + "14"),
    "estesa_persone_d_lgs_25_2008_reiterata": _fonte("D.Lgs. 25/2008, artt. 29 e 29-bis: domanda reiterata", _D_LGS_25_2008 + "29"),
    # Cittadinanza e apolidia
    "estesa_persone_l_91_1992_domanda": _fonte("L. 91/1992, artt. 5 e 9: concessione della cittadinanza per matrimonio e per residenza", _L_91_1992 + "9"),
    "estesa_persone_l_91_1992_diniego": _fonte("L. 91/1992, artt. 6 e 8: preclusioni e rigetto dell'istanza di cittadinanza", _L_91_1992 + "8"),
    "estesa_persone_l_91_1992_giuramento": _fonte("L. 91/1992, art. 10: decreto di concessione e giuramento", _L_91_1992 + "10"),
    "estesa_persone_d_lgs_150_2011_cittadinanza": _fonte("D.Lgs. 150/2011, art. 19-bis: accertamento dello stato di apolidia e della cittadinanza italiana", _D_LGS_150_2011 + "19bis"),
}


# ── Costruttori per tipo di documento ───────────────────────────────────────


def _ricorso(id: str, titolo: str, conferma: str, label: str, *, fonte: str, evidence: str) -> RegolaTitolo:
    return regola(id, titolo, conferma, label, role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO,
                  fonte=fonte, deposit_role="atto_principale", evidence=evidence)


def _provvedimento(id: str, titolo: str, conferma: str, label: str, *, fonte: str, evidence: str,
                   tipo: TipoDocumento = TipoDocumento.DECRETO) -> RegolaTitolo:
    return regola(id, titolo, conferma, label, role="provvedimento", section="provvedimenti", tipo=tipo,
                  fonte=fonte, deposit_role="fuori_busta", deposit_candidate=False, evidence=evidence)


def _amministrativo(id: str, titolo: str, conferma: str, label: str, *, fonte: str, evidence: str) -> RegolaTitolo:
    """Atto della pubblica amministrazione (questore, prefetto, Ministero): si allega a chi lo impugna."""
    return regola(id, titolo, conferma, label, role="atto_amministrativo", section="provvedimenti",
                  tipo=TipoDocumento.ALLEGATO, fonte=fonte, deposit_role="allegato", evidence=evidence)


def _domanda(id: str, titolo: str, conferma: str, label: str, *, fonte: str, evidence: str) -> RegolaTitolo:
    """Domanda o istanza rivolta all'amministrazione o all'ufficiale dello stato civile."""
    return regola(id, titolo, conferma, label, role="atto_amministrativo", section="atti", tipo=TipoDocumento.RICORSO,
                  fonte=fonte, deposit_role="atto_principale", evidence=evidence)


def _successorio(id: str, titolo: str, conferma: str, label: str, *, fonte: str, evidence: str,
                 tipo: TipoDocumento = TipoDocumento.ALLEGATO) -> RegolaTitolo:
    return regola(id, titolo, conferma, label, role="atto_successorio", section="allegati", tipo=tipo,
                  fonte=fonte, evidence=evidence)


def _verbale(id: str, titolo: str, conferma: str, label: str, *, fonte: str, evidence: str) -> RegolaTitolo:
    return regola(id, titolo, conferma, label, role="verbale_ufficio", section="provvedimenti", tipo=TipoDocumento.VERBALE,
                  fonte=fonte, deposit_role="fuori_busta", deposit_candidate=False, evidence=evidence)


# Domanda giudiziale introdotta con ricorso, citazione o domanda (filiazione e successioni).
_DOMANDA_GIUDIZIALE = r"(?:ricorso|atto\s+di\s+citazione|domanda)\s+(?:per\s+(?:l.?\s*|la\s+)?|di\s+|in\s+)?"
_PERMESSO = r"(?:permesso|titolo)\s+di\s+soggiorno"


_FAMIGLIA = (
    _ricorso(
        "per_ricorso_figli_fuori_matrimonio",
        r"ricorso\s+per\s+(?:l.?\s*)?(?:affidamento|affido)\s+(?:e\s+(?:il\s+)?mantenimento\s+)?(?:de[il]\s+|dell[ae]\s+)?figli\w*" + _CODA,
        r"\bfuori\s+(?:dal|del)\s+matrimonio\b|\b337[\s-]*(?:bis|ter)\b|\bnon\s+coniugat\w+\b|\bmai\s+(?:stat[oa]\s+)?coniugat\w+\b|\bconviv\w+\b",
        "Ricorso per affidamento e mantenimento dei figli",
        fonte="estesa_persone_cc_figli_fuori_matrimonio",
        evidence="titolo del ricorso e figli nati fuori dal matrimonio (artt. 337-bis e 337-ter c.c.)",
    ),
    _provvedimento(
        "per_provvedimenti_temporanei_urgenti",
        r"(?:ordinanza|decreto)\s+(?:di|con)\s+provvedimenti\s+temporanei\s+e\s+urgenti" + _CODA
        + r"|provvedimenti\s+temporanei\s+e\s+urgenti" + _CODA,
        r"\b473[\s.-]*bis[\s.]*22\b|\bp\.?\s*q\.?\s*m\b|\bin\s+via\s+provvisoria\b",
        "Provvedimenti temporanei e urgenti",
        tipo=TipoDocumento.ORDINANZA, fonte="estesa_persone_cpc_provvedimenti_temporanei",
        evidence="titolo del provvedimento del giudice alla prima udienza (art. 473-bis.22 c.p.c.)",
    ),
    _provvedimento(
        "per_decreto_ordine_protezione",
        r"decreto\s+(?:di|con)\s+(?:emissione\s+(?:dell.?\s*|di\s+)?)?ordine\s+di\s+protezione" + _CODA
        + r"|ordine\s+di\s+protezione\s+contro\s+gli\s+abusi\s+familiari" + _CODA,
        r"\ballontan\w+\b|\b473[\s.-]*bis[\s.]*(?:69|70)\b|\b342[\s-]*ter\b|\bcessa\w*\s+la\s+condotta\b",
        "Decreto di ordine di protezione",
        fonte="estesa_persone_cpc_ordini_protezione",
        evidence="titolo del decreto e ordine di cessazione della condotta (art. 473-bis.70 c.p.c.; art. 342-ter c.c.)",
    ),
    _ricorso(
        "per_ricorso_inadempienze_violazioni",
        r"ricorso\s+(?:ex\s+art\.?\s*473[\s.-]*bis[\s.]*39|per\s+(?:provvedimenti\s+in\s+caso\s+di\s+)?inadempienze\s+o\s+violazioni"
        r"|ex\s+art\.?\s*709[\s-]*ter)" + _CODA,
        r"\binadempien\w+\b|\bviolazion\w+\b|\b473[\s.-]*bis[\s.]*39\b|\b709[\s-]*ter\b|\bammoni\w+\b",
        "Ricorso per inadempienze o violazioni",
        fonte="estesa_persone_cpc_inadempienze",
        evidence="titolo del ricorso e inadempienze del genitore (art. 473-bis.39 c.p.c.)",
    ),
    _ricorso(
        "per_ricorso_pagamento_diretto",
        r"ricorso\s+per\s+(?:il\s+|l.?\s*ordine\s+di\s+)?pagamento\s+diretto" + _CODA
        + r"|(?:istanza|ricorso)\s+ex\s+art\.?\s*473[\s.-]*bis[\s.]*37" + _CODA,
        r"\bterz\w+\b|\bdatore\s+di\s+lavoro\b|\b473[\s.-]*bis[\s.]*37\b|\bobbligat\w+\b",
        "Ricorso per il pagamento diretto del terzo",
        fonte="estesa_persone_cpc_pagamento_diretto",
        evidence="titolo del ricorso e ordine al terzo debitore dell'obbligato (art. 473-bis.37 c.p.c.)",
    ),
    _ricorso(
        "per_ricorso_quota_tfr",
        r"ricorso\s+per\s+(?:la\s+|l.?\s*attribuzione\s+(?:della|di\s+una)\s+)?quota\s+(?:del(?:l.?\s*)?\s*)?"
        r"(?:indennit[aà]\s+di\s+fine\s+rapporto|tfr|trattamento\s+di\s+fine\s+rapporto)" + _CODA,
        r"\b12[\s-]*bis\b|\bfine\s+rapporto\b|\btfr\b|\bex\s+coniuge\b",
        "Ricorso per quota dell'indennità di fine rapporto",
        fonte="estesa_persone_l_898_1970_tfr",
        evidence="titolo del ricorso e quota del trattamento di fine rapporto (art. 12-bis L. 898/1970)",
    ),
    _ricorso(
        "per_ricorso_pensione_reversibilita",
        r"ricorso\s+per\s+(?:la\s+(?:ripartizione\s+della\s+)?|l.?\s*attribuzione\s+(?:della|di\s+una)\s+)?(?:quota\s+(?:della\s+)?)?pensione\s+di\s+reversibilit[aà]" + _CODA,
        r"\breversibilit\w+\b|\bconiuge\s+superstite\b|\bex\s+coniuge\b",
        "Ricorso per la pensione di reversibilità",
        fonte="estesa_persone_l_898_1970_reversibilita",
        evidence="titolo del ricorso e pensione di reversibilità dell'ex coniuge (art. 9 L. 898/1970)",
    ),
    _verbale(
        "per_verbale_ascolto_minore",
        r"verbale\s+(?:di|dell.?)\s*ascolto\s+del(?:\s+|la\s+|l.?\s*)?minore" + _CODA,
        r"\bminor\w+\b|\bascolt\w+\b|\b473[\s.-]*bis[\s.]*[45]\b",
        "Verbale di ascolto del minore",
        fonte="estesa_persone_cpc_ascolto_minore",
        evidence="titolo del verbale e ascolto del minore da parte del giudice (artt. 473-bis.4 e 473-bis.5 c.p.c.)",
    ),
    _ricorso(
        "per_ricorso_alimenti_convivente",
        r"ricorso\s+per\s+(?:gli\s+)?alimenti\s+(?:all.?\s*)?(?:ex\s+)?convivente" + _CODA,
        r"\bconviv\w+\b|\bcomma\s+65\b|\b76\s*/\s*2016\b",
        "Ricorso per alimenti all'ex convivente",
        fonte="estesa_persone_l_76_2016",
        evidence="titolo del ricorso e cessazione della convivenza di fatto (art. 1, c. 65, L. 76/2016)",
    ),
    _ricorso(
        "per_ricorso_alimenti",
        r"ricorso\s+per\s+(?:la\s+prestazione\s+degli\s+|gli\s+)?alimenti" + _CODA,
        r"\b43[3-9]\b|\balimen\w+\b|\bstato\s+di\s+bisogno\b",
        "Ricorso per alimenti",
        fonte="estesa_persone_cc_alimenti",
        evidence="titolo del ricorso e stato di bisogno dell'alimentando (artt. 433 e 438 c.c.)",
    ),
)


_FILIAZIONE = (
    _ricorso(
        "per_ricorso_riconoscimento_figlio",
        r"ricorso\s+per\s+(?:l.?\s*autorizzazione\s+al\s+|il\s+)?riconoscimento\s+del(?:\s+|la\s+|l.?\s*)?figli\w*" + _CODA
        + r"|ricorso\s+ex\s+art\.?\s*250\s+c\.?\s*c\.?" + _CODA,
        r"\briconosc\w+\b|\b250\b",
        "Ricorso per il riconoscimento del figlio",
        fonte="estesa_persone_cc_riconoscimento_figlio",
        evidence="titolo del ricorso e riconoscimento del figlio (art. 250 c.c.)",
    ),
    _ricorso(
        "per_disconoscimento_paternita",
        _DOMANDA_GIUDIZIALE + r"(?:azione\s+di\s+)?disconoscimento\s+(?:della\s+|di\s+)?paternit[aà]" + _CODA,
        r"\bdisconosciment\w+\b|\b24[34][\s-]*bis\b|\b244\b|\bpaternit\w+\b",
        "Ricorso per disconoscimento della paternità",
        fonte="estesa_persone_cc_disconoscimento",
        evidence="titolo dell'atto e azione di disconoscimento (artt. 243-bis e 244 c.c.)",
    ),
    _ricorso(
        "per_dichiarazione_giudiziale_paternita",
        _DOMANDA_GIUDIZIALE + r"(?:dichiarazione|accertamento)\s+giudiziale\s+(?:della\s+|di\s+)?(?:paternit[aà]|maternit[aà])" + _CODA,
        r"\b269\b|\bpaternit\w+\b|\bmaternit\w+\b|\bgenetic\w+\b",
        "Ricorso per dichiarazione giudiziale di paternità",
        fonte="estesa_persone_cc_dichiarazione_paternita",
        evidence="titolo dell'atto e accertamento del rapporto di filiazione (art. 269 c.c.)",
    ),
    _ricorso(
        "per_impugnazione_riconoscimento",
        _DOMANDA_GIUDIZIALE + r"impugnazione\s+del\s+riconoscimento" + _CODA,
        r"\b263\b|\bdifetto\s+di\s+veridicit\w+\b|\briconosciment\w+\b",
        "Ricorso per impugnazione del riconoscimento",
        fonte="estesa_persone_cc_impugnazione_riconoscimento",
        evidence="titolo dell'atto e difetto di veridicità del riconoscimento (art. 263 c.c.)",
    ),
    _ricorso(
        "per_ricorso_reintegrazione_responsabilita",
        r"ricorso\s+per\s+(?:la\s+)?(?:reintegrazione|reintegra)\s+nella\s+responsabilit[aà]\s+genitoriale" + _CODA
        + r"|ricorso\s+in\s+materia\s+di\s+responsabilit[aà]\s+genitoriale" + _CODA
        + r"|ricorso\s+(?:per\s+provvedimenti\s+)?ex\s+artt?\.?\s*33[03]\s+c\.?\s*c\.?" + _CODA,
        r"\b33[023]\b|\breintegr\w+\b|\bcondotta\s+pregiudizievole\b|\bresponsabilit\w+\s+genitorial\w+\b",
        "Ricorso in materia di responsabilità genitoriale",
        fonte="estesa_persone_cc_responsabilita_genitoriale",
        evidence="titolo del ricorso e responsabilità genitoriale (artt. 330, 332 e 333 c.c.)",
    ),
)


_ADOZIONE = (
    _provvedimento(
        "per_sentenza_adottabilita",
        r"sentenza\s+(?:dichiarativa\s+)?(?:dello\s+stato\s+)?di\s+adottabilit[aà]" + _CODA
        + r"|sentenza\s+(?:che\s+dichiara\s+lo|di\s+dichiarazione\s+dello)\s+stato\s+di\s+adottabilit[aà]" + _CODA,
        r"\badottabilit\w+\b|\babbandon\w+\b|\b184\s*/\s*1983\b",
        "Sentenza di adottabilità",
        tipo=TipoDocumento.SENTENZA, fonte="estesa_persone_l_184_1983_adottabilita",
        evidence="titolo della sentenza e stato di abbandono del minore (art. 15 L. 184/1983)",
    ),
    _domanda(
        "per_dichiarazione_disponibilita_adozione",
        r"(?:dichiarazione|domanda)\s+di\s+disponibilit[aà]\s+(?:all.?\s*)?adozione" + _CODA
        + r"|domanda\s+di\s+adozione\s+(?:nazionale|internazionale)" + _CODA,
        r"\badott\w+\b|\bidoneit\w+\b|\bconiug\w+\b|\b184\s*/\s*1983\b",
        "Dichiarazione di disponibilità all'adozione",
        fonte="estesa_persone_l_184_1983_disponibilita",
        evidence="titolo della dichiarazione dei coniugi al tribunale per i minorenni (artt. 22 e 29-bis L. 184/1983)",
    ),
    _provvedimento(
        "per_decreto_affidamento_preadottivo",
        r"(?:decreto|ordinanza)\s+di\s+affidamento\s+preadottivo" + _CODA,
        r"\bpreadottiv\w+\b|\badott\w+\b|\bminor\w+\b",
        "Decreto di affidamento preadottivo",
        fonte="estesa_persone_l_184_1983_disponibilita",
        evidence="titolo del decreto e affidamento preadottivo del minore (art. 22, c. 6, L. 184/1983)",
    ),
    _ricorso(
        "per_ricorso_adozione_casi_particolari",
        r"(?:ricorso|domanda|istanza)\s+(?:per\s+(?:l.?\s*)?|di\s+)?adozione\s+in\s+casi\s+particolari" + _CODA
        + r"|ricorso\s+per\s+adozione\s+ex\s+art\.?\s*44" + _CODA,
        r"\b44\b|\badott\w+\b|\bcasi\s+particolari\b",
        "Ricorso per adozione in casi particolari",
        fonte="estesa_persone_l_184_1983_casi_particolari",
        evidence="titolo del ricorso e adozione in casi particolari (art. 44 L. 184/1983)",
    ),
    _provvedimento(
        "per_decreto_idoneita_adozione",
        r"decreto\s+di\s+idoneit[aà]\s+(?:all.?\s*)?adozione" + _CODA,
        r"\bidoneit\w+\b|\badozion\w+\b|\benti?\s+autorizzat\w+\b",
        "Decreto di idoneità all'adozione internazionale",
        fonte="estesa_persone_l_184_1983_idoneita",
        evidence="titolo del decreto e idoneità dei coniugi all'adozione (art. 30 L. 184/1983)",
    ),
    _ricorso(
        "per_ricorso_adozione_maggiorenne",
        r"ricorso\s+per\s+(?:l.?\s*)?adozione\s+(?:di\s+(?:persona\s+)?maggiore\s+(?:di\s+|d.?\s*)?et[aà]|di\s+(?:un\s+)?maggiorenne|del\s+maggiorenne)" + _CODA,
        r"\b29[16]\b|\badott\w+\b|\bassenso\b|\bmatrign\w+\b|\bpatrign\w+\b|\bconsenso\b",
        "Ricorso per adozione di persona maggiore di età",
        fonte="estesa_persone_cc_adozione_maggiorenni",
        evidence="titolo del ricorso e adozione del maggiorenne (artt. 291 e 296 c.c.)",
    ),
    _provvedimento(
        "per_affidamento_familiare",
        r"(?:provvedimento|decreto)\s+di\s+affidamento\s+familiare" + _CODA
        + r"|progetto\s+di\s+affidamento\s+familiare" + _CODA,
        r"\baffid\w+\b|\bminor\w+\b|\b184\s*/\s*1983\b",
        "Provvedimento di affidamento familiare",
        fonte="estesa_persone_l_184_1983_affidamento_familiare",
        evidence="titolo del provvedimento e affidamento del minore a una famiglia (art. 4 L. 184/1983)",
    ),
)


_UNIONI = (
    _ricorso(
        "per_ricorso_scioglimento_unione_civile",
        r"ricorso\s+(?:congiunto\s+)?(?:per\s+(?:lo\s+)?)?scioglimento\s+" + _DELL + r"unione\s+civile" + _CODA,
        r"\bunion\w+\s+civil\w+\b|\b76\s*/\s*2016\b",
        "Ricorso per scioglimento dell'unione civile",
        fonte="estesa_persone_l_76_2016",
        evidence="titolo del ricorso e unione civile (art. 1, cc. 24 e 25, L. 76/2016)",
    ),
    regola(
        "per_dichiarazione_scioglimento_unione_civile",
        r"dichiarazione\s+(?:di\s+volont[aà]\s+)?di\s+scioglimento\s+" + _DELL + r"unione\s+civile" + _CODA,
        r"\bufficiale\s+dello\s+stato\s+civile\b|\bunion\w+\s+civil\w+\b",
        "Dichiarazione di scioglimento dell'unione civile",
        role="atto_stato_civile", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_persone_l_76_2016",
        evidence="titolo della dichiarazione all'ufficiale dello stato civile (art. 1, c. 24, L. 76/2016)",
    ),
    regola(
        "per_risoluzione_contratto_convivenza",
        r"(?:atto\s+di\s+|dichiarazione\s+di\s+)?(?:risoluzione|recesso\s+(?:unilaterale\s+)?)\s*(?:dal|del)\s+contratto\s+di\s+convivenza" + _CODA,
        r"\bconviv\w+\b|\brecess\w+\b|\brisoluzion\w+\b",
        "Risoluzione del contratto di convivenza",
        role="contratto", section="allegati", tipo=TipoDocumento.CONTRATTO,
        fonte="estesa_persone_l_76_2016",
        evidence="titolo dell'atto e risoluzione del contratto (art. 1, cc. 59 e 60, L. 76/2016)",
    ),
    regola(
        "per_contratto_convivenza",
        r"contratto\s+di\s+convivenza" + _CODA,
        r"\bconviv\w+\b|\b76\s*/\s*2016\b|\bcoabitazion\w+\b",
        "Contratto di convivenza",
        role="contratto", section="allegati", tipo=TipoDocumento.CONTRATTO,
        fonte="estesa_persone_l_76_2016",
        evidence="titolo del contratto e rapporti patrimoniali dei conviventi (art. 1, c. 50, L. 76/2016)",
    ),
)


_PERSONE = (
    _ricorso(
        "per_ricorso_interdizione_inabilitazione",
        r"ricorso\s+per\s+(?:la\s+)?(?:dichiarazione\s+di\s+|pronuncia\s+di\s+)?(?:l.?\s*)?(?:interdizione|inabilitazione)" + _CODA,
        r"\binterdi\w+\b|\binabilit\w+\b|\b41[45]\b|\b712\b",
        "Ricorso per interdizione o inabilitazione",
        fonte="estesa_persone_cc_interdizione",
        evidence="titolo del ricorso e infermità di mente dell'interdicendo (artt. 414 e 415 c.c.; art. 712 c.p.c.)",
    ),
    _ricorso(
        "per_ricorso_apertura_tutela",
        r"ricorso\s+per\s+(?:l.?\s*apertura\s+della\s+tutela|la\s+nomina\s+(?:del|di\s+un)\s+tutore)" + _CODA,
        r"\btutel\w+\b|\btutor\w+\b|\b34[3-6]\b",
        "Ricorso per l'apertura della tutela",
        fonte="estesa_persone_cc_tutela_minori",
        evidence="titolo del ricorso e minore privo di genitori esercenti la responsabilità (art. 343 c.c.)",
    ),
    _verbale(
        "per_verbale_giuramento_tutore",
        r"verbale\s+di\s+giuramento\s+(?:del(?:l.?\s*)?\s*)?(?:tutore|protutore|curatore|amministratore\s+di\s+sostegno)" + _CODA,
        r"\bgiur\w+\b|\b349\b|\b411\b|\bgiudice\s+tutelare\b",
        "Verbale di giuramento del tutore o dell'amministratore di sostegno",
        fonte="estesa_persone_cc_tutela_minori",
        evidence="titolo del verbale e giuramento davanti al giudice tutelare (artt. 349 e 411 c.c.)",
    ),
    _ricorso(
        "per_ricorso_rettificazione_sesso",
        r"ricorso\s+(?:per\s+(?:la\s+)?)?(?:rettificazione|rettifica)\s+(?:di\s+|dell.?\s*)?attribuzione\s+di\s+sesso" + _CODA,
        r"\b164\s*/\s*1982\b|\bsesso\b|\bgenere\b",
        "Ricorso per rettificazione di attribuzione di sesso",
        fonte="estesa_persone_l_164_1982",
        evidence="titolo del ricorso e attribuzione di sesso (art. 1 L. 164/1982; art. 31 D.Lgs. 150/2011)",
    ),
    _ricorso(
        "per_ricorso_rettificazione_stato_civile",
        r"ricorso\s+(?:per\s+(?:la\s+)?)?(?:rettificazione|rettifica|correzione)\s+(?:di\s+|dell.?\s*|degli\s+)?att[oi]\s+(?:dello\s+|di\s+)?stato\s+civile" + _CODA
        + r"|ricorso\s+ex\s+art\.?\s*95\s+d\.?\s*p\.?\s*r\.?\s*(?:n\.?\s*)?396(?:\s*/\s*2000)?" + _CODA,
        r"\bstato\s+civile\b|\b396\s*/\s*2000\b|\brettific\w+\b",
        "Ricorso per rettificazione degli atti dello stato civile",
        fonte="estesa_persone_dpr_396_2000_rettificazione",
        evidence="titolo del ricorso e atto dello stato civile da rettificare (art. 95 D.P.R. 396/2000)",
    ),
    _domanda(
        "per_istanza_cambio_nome",
        r"(?:istanza|domanda|richiesta)\s+(?:di|per\s+(?:il\s+)?)\s*(?:cambiamento|cambio|modifica(?:zione)?)\s+(?:del\s+)?(?:nome|cognome)" + _CODA,
        r"\bprefett\w+\b|\b396\s*/\s*2000\b|\bcognom\w+\b",
        "Istanza di cambiamento del nome o del cognome",
        fonte="estesa_persone_dpr_396_2000_nome",
        evidence="titolo dell'istanza al prefetto e nome da cambiare (art. 89 D.P.R. 396/2000)",
    ),
    _ricorso(
        "per_ricorso_assenza_morte_presunta",
        r"ricorso\s+per\s+(?:la\s+)?dichiarazione\s+(?:di\s+)?(?:assenza|morte\s+presunta)" + _CODA,
        r"\bscompars\w+\b|\bassenz\w+\b|\bmorte\s+presunta\b",
        "Ricorso per dichiarazione di assenza o morte presunta",
        fonte="estesa_persone_cc_assenza_morte_presunta",
        evidence="titolo del ricorso e scomparsa della persona (artt. 49 e 58 c.c.)",
    ),
)


_SUCCESSIONI = (
    _successorio(
        "per_accettazione_eredita",
        r"(?:atto\s+di\s+|dichiarazione\s+di\s+)?accettazione\s+(?:espressa\s+|pura\s+e\s+semplice\s+)?(?:dell.?\s*|di\s+)" + _EREDITA
        + r"(?!.*benefici)" + _CODA,
        r"\bered\w+\b|\baccett\w+\b|\b47[45]\b",
        "Accettazione dell'eredità",
        fonte="estesa_persone_cc_accettazione_eredita",
        evidence="titolo dell'atto e accettazione del chiamato (art. 475 c.c.)",
    ),
    _ricorso(
        "per_ricorso_termine_accettazione",
        r"ricorso\s+per\s+(?:la\s+)?fissazione\s+(?:di\s+un\s+|del\s+)?termine\s+per\s+(?:l.?\s*)?accettare\s+(?:l.?\s*)?" + _EREDITA + _CODA
        + r"|ricorso\s+ex\s+art\.?\s*481\s+c\.?\s*c\.?" + _CODA + r"|actio\s+interrogatoria" + _CODA,
        r"\b481\b|\bchiamat\w+\b|\bered\w+\b",
        "Ricorso per la fissazione di un termine per accettare l'eredità",
        fonte="estesa_persone_cc_actio_interrogatoria",
        evidence="titolo del ricorso e chiamato all'eredità (art. 481 c.c.)",
    ),
    _successorio(
        "per_verbale_inventario_ereditario",
        r"(?:processo\s+)?verbale\s+di\s+inventario" + _CODA,
        r"\bered\w+\b|\bde\s+cuius\b|\bdefunt\w+\b|\b769\b|\b775\b",
        "Verbale di inventario ereditario",
        tipo=TipoDocumento.VERBALE, fonte="estesa_persone_cpc_inventario",
        evidence="titolo del verbale e beni del defunto (artt. 769 e 775 c.p.c.; art. 484 c.c.)",
    ),
    _ricorso(
        "per_petizione_eredita",
        _DOMANDA_GIUDIZIALE + r"petizione\s+(?:di\s+|" + _DELL + r")" + _EREDITA + _CODA
        + r"|petizione\s+di\s+" + _EREDITA + _CODA,
        r"\b533\b|\bered\w+\b|\bpetizion\w+\b",
        "Domanda di petizione di eredità",
        fonte="estesa_persone_cc_petizione_eredita",
        evidence="titolo della domanda e qualità di erede (art. 533 c.c.)",
    ),
    _ricorso(
        "per_divisione_ereditaria",
        _DOMANDA_GIUDIZIALE + r"(?:(?:lo\s+)?scioglimento\s+della\s+comunione\s+ereditaria|divisione\s+(?:giudiziale\s+)?(?:ereditaria|" + _DELL + _EREDITA + r"))" + _CODA,
        r"\b713\b|\b78[4-9]\b|\bcoered\w+\b|\bcomunione\b|\bered\w+\b",
        "Domanda di divisione ereditaria",
        fonte="estesa_persone_cc_divisione",
        evidence="titolo della domanda e comunione ereditaria (art. 713 c.c.; art. 784 c.p.c.)",
    ),
    _ricorso(
        "per_azione_riduzione",
        _DOMANDA_GIUDIZIALE + r"(?:azione\s+di\s+)?riduzione\s+(?:per\s+lesione\s+(?:della\s+|di\s+)?legittima|delle\s+disposizioni\s+testamentarie|delle\s+donazioni)" + _CODA,
        r"\blegittim\w+\b|\b55[3-9]\b|\briserv\w+\b|\blesion\w+\b|\bdonazion\w+\b",
        "Domanda di riduzione per lesione di legittima",
        fonte="estesa_persone_cc_riduzione",
        evidence="titolo della domanda e quota di riserva del legittimario (artt. 553 e 554 c.c.)",
    ),
    _ricorso(
        "per_ricorso_apposizione_sigilli",
        r"(?:ricorso|istanza)\s+per\s+(?:l.?\s*)?apposizione\s+dei\s+sigilli" + _CODA,
        r"\bsigill\w+\b|\b75[23]\b",
        "Ricorso per l'apposizione dei sigilli",
        fonte="estesa_persone_cpc_sigilli",
        evidence="titolo del ricorso e beni dell'eredità da custodire (art. 752 c.p.c.)",
    ),
)


_VOLONTARIA = (
    _ricorso(
        "per_reclamo_739",
        r"reclamo\s+(?:ex\s+art\.?\s*739" + _CODA + r"|(?:avverso|contro)\s+(?:il\s+)?decreto\s+(?:del\s+giudice\s+tutelare|camerale|"
        r"reso\s+in\s+camera\s+di\s+consiglio|di\s+volontaria\s+giurisdizione)" + _CODA + r")",
        r"\b739\b|\bcamera\s+di\s+consiglio\b|\bgiudice\s+tutelare\b|\breclam\w+\b",
        "Reclamo contro decreto camerale",
        fonte="estesa_persone_cpc_reclamo_739",
        evidence="titolo del reclamo e decreto reso in camera di consiglio (art. 739 c.p.c.)",
    ),
    _provvedimento(
        "per_decreto_autorizzazione_giudice_tutelare",
        r"decreto\s+(?:di\s+autorizzazione|autorizzativo)(?:\s+del\s+giudice\s+tutelare)?" + _CODA,
        r"\bgiudice\s+tutelare\b",
        "Decreto di autorizzazione del giudice tutelare",
        fonte="estesa_persone_cc_autorizzazioni_tutelare",
        evidence="titolo del decreto e autorizzazione del giudice tutelare (artt. 320, 374, 375 e 411 c.c.)",
    ),
)


_IMMIGRAZIONE = (
    _ricorso(
        "per_ricorso_espulsione",
        r"ricorso\s+(?:avverso|contro|in\s+opposizione\s+al)\s+(?:il\s+)?(?:decreto|provvedimento)\s+(?:prefettizio\s+)?di\s+espulsione" + _CODA
        + r"|opposizione\s+(?:al|avverso\s+il)\s+decreto\s+di\s+espulsione" + _CODA,
        r"\bespuls\w+\b|\b286\s*/\s*1998\b|\bgiudice\s+di\s+pace\b",
        "Ricorso contro il decreto di espulsione",
        fonte="estesa_persone_d_lgs_150_2011_espulsione",
        evidence="titolo del ricorso al giudice di pace e decreto di espulsione (art. 13, c. 8, D.Lgs. 286/1998; art. 18 D.Lgs. 150/2011)",
    ),
    _provvedimento(
        "per_convalida_trattenimento",
        r"(?:decreto|verbale|ordinanza)\s+(?:di\s+)?(?:convalida|proroga)\s+(?:del\s+)?trattenimento" + _CODA,
        r"\bconvalid\w+\b|\bproroga\b|\btrattenim\w+\b",
        "Decreto di convalida del trattenimento",
        fonte="estesa_persone_tui_trattenimento",
        evidence="titolo del decreto e convalida del trattenimento dello straniero (art. 14, c. 4, D.Lgs. 286/1998)",
    ),
    _amministrativo(
        "per_decreto_trattenimento",
        r"(?:decreto|provvedimento)\s+di\s+trattenimento" + _CODA,
        r"\btrattenim\w+\b|\bcentr\w+\s+di\s+permanenza\b|\bcpr\b|\bquestor\w+\b",
        "Decreto di trattenimento",
        fonte="estesa_persone_tui_trattenimento",
        evidence="titolo del decreto del questore e centro di permanenza per il rimpatrio (art. 14, c. 1, D.Lgs. 286/1998)",
    ),
    _amministrativo(
        "per_ordine_questore_allontanamento",
        r"ordine\s+(?:del\s+questore\s+)?di\s+(?:lasciare|allontanamento\s+dal)\s+(?:il\s+)?territorio" + _CODA
        + r"|ordine\s+di\s+allontanamento\s+del\s+questore" + _CODA,
        r"\bquestor\w+\b|\b5[\s-]*bis\b|\bterritorio\b",
        "Ordine del questore di lasciare il territorio",
        fonte="estesa_persone_tui_trattenimento",
        evidence="titolo dell'ordine del questore e termine per lasciare il territorio (art. 14, c. 5-bis, D.Lgs. 286/1998)",
    ),
    _amministrativo(
        "per_decreto_respingimento",
        r"(?:decreto|provvedimento)\s+di\s+respingimento" + _CODA,
        r"\brespingim\w+\b|\bfrontier\w+\b|\bquestor\w+\b",
        "Decreto di respingimento",
        fonte="estesa_persone_tui_respingimento",
        evidence="titolo del provvedimento e respingimento alla frontiera (art. 10 D.Lgs. 286/1998)",
    ),
    _ricorso(
        "per_ricorso_diniego_permesso",
        r"ricorso\s+(?:avverso|contro)\s+(?:il\s+|la\s+)?(?:diniego|rifiuto|revoca|mancato\s+rinnovo)\s+(?:del\s+(?:rilascio|rinnovo)\s+)?(?:del\s+)?" + _PERMESSO + _CODA,
        r"\bpermess\w+\s+di\s+soggiorno\b|\bquestor\w+\b|\bannullament\w+\b",
        "Ricorso contro il diniego del permesso di soggiorno",
        fonte="estesa_persone_tui_ricorso_permesso",
        evidence="titolo del ricorso e provvedimento sul permesso di soggiorno (art. 6, c. 10, D.Lgs. 286/1998)",
    ),
    _amministrativo(
        "per_diniego_permesso",
        r"(?:provvedimento|decreto)\s+di\s+(?:diniego|rifiuto|revoca)\s+(?:del\s+(?:rilascio|rinnovo)\s+)?(?:del\s+)?" + _PERMESSO + _CODA,
        r"\bpermess\w+\s+di\s+soggiorno\b|\bquestur\w+\b|\bquestor\w+\b",
        "Provvedimento di diniego del permesso di soggiorno",
        fonte="estesa_persone_tui_permesso_soggiorno",
        evidence="titolo del provvedimento del questore e permesso di soggiorno (art. 5, c. 5, D.Lgs. 286/1998)",
    ),
    _domanda(
        "per_conversione_permesso",
        r"(?:istanza|domanda|richiesta)\s+(?:di|per\s+la)\s+conversione\s+(?:del\s+)?" + _PERMESSO + _CODA,
        r"\bconversion\w+\b|\bsportello\s+unico\b",
        "Istanza di conversione del permesso di soggiorno",
        fonte="estesa_persone_tui_permesso_soggiorno",
        evidence="titolo dell'istanza e conversione del titolo di soggiorno (artt. 5 e 6 D.Lgs. 286/1998)",
    ),
    _domanda(
        "per_istanza_protezione_speciale",
        r"(?:istanza|domanda|richiesta)\s+(?:di|per\s+il\s+(?:rilascio|riconoscimento)\s+(?:del(?:la)?\s+)?)\s*(?:permesso\s+di\s+soggiorno\s+per\s+)?protezione\s+speciale" + _CODA,
        r"\bprotezione\s+speciale\b|\b286\s*/\s*1998\b|\bvita\s+privata\b",
        "Istanza di protezione speciale",
        fonte="estesa_persone_tui_protezione_speciale",
        evidence="titolo dell'istanza e divieto di allontanamento (art. 19, c. 1.1, D.Lgs. 286/1998)",
    ),
    _domanda(
        "per_domanda_permesso_soggiorno",
        r"(?:domanda|istanza|richiesta)\s+(?:di|per\s+(?:il\s+)?)\s*(?:rilascio|rinnovo|aggiornamento|duplicato)\s+(?:del\s+)?" + _PERMESSO + _CODA
        + r"|(?:domanda|istanza)\s+di\s+permesso\s+di\s+soggiorno" + _CODA,
        r"\bpermess\w+\s+di\s+soggiorno\b|\bquestur\w+\b",
        "Domanda di permesso di soggiorno",
        fonte="estesa_persone_tui_permesso_soggiorno",
        evidence="titolo della domanda al questore e permesso di soggiorno (art. 5 D.Lgs. 286/1998)",
    ),
    _ricorso(
        "per_ricorso_diniego_ricongiungimento",
        r"ricorso\s+(?:avverso|contro)\s+(?:il\s+)?(?:diniego|rifiuto)\s+(?:del\s+)?(?:nulla\s+osta\s+(?:al\s+)?)?"
        r"(?:ricongiungimento(?:\s+familiare)?|visto\s+(?:di\s+ingresso\s+)?per\s+ricongiungimento)" + _CODA,
        r"\bricongiung\w+\b|\bnulla\s+osta\b|\bvisto\b",
        "Ricorso contro il diniego del ricongiungimento familiare",
        fonte="estesa_persone_tui_ricongiungimento_ricorso",
        evidence="titolo del ricorso e diniego del nulla osta o del visto (art. 30, c. 6, D.Lgs. 286/1998; art. 20 D.Lgs. 150/2011)",
    ),
    _domanda(
        "per_domanda_reiterata",
        r"domanda\s+(?:reiterata|successiva)(?:\s+di\s+protezione\s+internazionale)?" + _CODA,
        r"\breiterat\w+\b|\bsuccessiv\w+\b|\bnuov\w+\s+elementi\b|\belementi\s+nuov\w+\b|\binammissibil\w+\b",
        "Domanda reiterata di protezione internazionale",
        fonte="estesa_persone_d_lgs_25_2008_reiterata",
        evidence="titolo della domanda e nuovi elementi (artt. 29 e 29-bis D.Lgs. 25/2008)",
    ),
    _domanda(
        "per_domanda_protezione_internazionale",
        r"domanda\s+(?:di|per\s+il\s+riconoscimento\s+della)\s+protezione\s+internazionale" + _CODA
        + r"|(?:verbale\s+(?:delle\s+dichiarazioni\s+)?)?modello\s+c\s*3" + _CODA,
        r"\bquestur\w+\b|\brichiedent\w+\b|\bc\s*3\b",
        "Domanda di protezione internazionale",
        fonte="estesa_persone_d_lgs_25_2008_domanda",
        evidence="titolo della domanda presentata alla questura (art. 26 D.Lgs. 25/2008)",
    ),
    _verbale(
        "per_verbale_audizione_commissione",
        r"verbale\s+(?:di|dell.?)\s*audizione(?:\s+personale|\s+del\s+richiedente)?" + _CODA
        + r"|verbale\s+del(?:l.?\s*)?\s*colloquio\s+personale" + _CODA,
        r"\bcommissione\s+territoriale\b|\bprotezione\s+internazionale\b",
        "Verbale di audizione del richiedente",
        fonte="estesa_persone_d_lgs_25_2008_audizione",
        evidence="titolo del verbale e colloquio davanti alla Commissione territoriale (artt. 12 e 14 D.Lgs. 25/2008)",
    ),
)


_CITTADINANZA = (
    _domanda(
        "per_domanda_cittadinanza",
        r"(?:domanda|istanza|richiesta)\s+(?:di|per\s+(?:la\s+)?(?:concessione|acquisto)\s+(?:della\s+)?)\s*cittadinanza(?:\s+italiana)?" + _CODA,
        r"\b91\s*/\s*1992\b|\bprefett\w+\b|\bresidenz\w+\b",
        "Domanda di cittadinanza italiana",
        fonte="estesa_persone_l_91_1992_domanda",
        evidence="titolo della domanda e requisiti di matrimonio o residenza (artt. 5 e 9 L. 91/1992)",
    ),
    _amministrativo(
        "per_diniego_cittadinanza",
        r"(?:provvedimento|decreto)\s+di\s+(?:diniego|rigetto|inammissibilit[aà])\s+(?:della\s+(?:domanda\s+di\s+)?)?(?:concessione\s+della\s+)?cittadinanza(?:\s+italiana)?" + _CODA,
        r"\b91\s*/\s*1992\b|\bcittadinanz\w+\b",
        "Provvedimento di diniego della cittadinanza",
        fonte="estesa_persone_l_91_1992_diniego",
        evidence="titolo del provvedimento e rigetto dell'istanza (artt. 6 e 8 L. 91/1992)",
    ),
    _amministrativo(
        "per_decreto_concessione_cittadinanza",
        r"decreto\s+di\s+concessione\s+della\s+cittadinanza(?:\s+italiana)?" + _CODA,
        r"\bgiurament\w+\b|\b91\s*/\s*1992\b",
        "Decreto di concessione della cittadinanza",
        fonte="estesa_persone_l_91_1992_giuramento",
        evidence="titolo del decreto e giuramento entro sei mesi (art. 10 L. 91/1992)",
    ),
    _verbale(
        "per_giuramento_cittadinanza",
        r"(?:verbale\s+di\s+)?giuramento\s+(?:di\s+fedelt[aà]\s+alla\s+repubblica|per\s+(?:l.?\s*acquisto\s+del)?la\s+cittadinanza)" + _CODA,
        r"\bgiur\w+\b|\bcostituzione\b|\bcittadinanz\w+\b",
        "Verbale di giuramento per la cittadinanza",
        fonte="estesa_persone_l_91_1992_giuramento",
        evidence="titolo del verbale e giuramento davanti all'ufficiale dello stato civile (art. 10 L. 91/1992)",
    ),
    _ricorso(
        "per_ricorso_accertamento_cittadinanza",
        r"ricorso\s+per\s+(?:l.?\s*)?accertamento\s+(?:dello\s+status\s+|della\s+)?(?:cittadinanza(?:\s+italiana)?|civitatis)" + _CODA
        + r"|ricorso\s+per\s+(?:il\s+)?riconoscimento\s+della\s+cittadinanza(?:\s+italiana)?" + _CODA,
        r"\biure\s+sanguinis\b|\b91\s*/\s*1992\b|\b19[\s-]*bis\b|\bdiscenden\w+\b",
        "Ricorso per accertamento della cittadinanza italiana",
        fonte="estesa_persone_d_lgs_150_2011_cittadinanza",
        evidence="titolo del ricorso e accertamento della cittadinanza (art. 19-bis D.Lgs. 150/2011; art. 1 L. 91/1992)",
    ),
    _ricorso(
        "per_ricorso_apolidia",
        r"(?:ricorso|istanza|domanda)\s+per\s+(?:il\s+|l.?\s*)?(?:riconoscimento|accertamento)\s+dello\s+(?:stato|status)\s+di\s+apolid\w+" + _CODA,
        r"\bapolid\w+\b|\b19[\s-]*bis\b",
        "Ricorso per il riconoscimento dello stato di apolidia",
        fonte="estesa_persone_d_lgs_150_2011_cittadinanza",
        evidence="titolo del ricorso e stato di apolidia (art. 19-bis D.Lgs. 150/2011)",
    ),
)


REGOLE: tuple[RegolaTitolo, ...] = (
    _FAMIGLIA + _FILIAZIONE + _ADOZIONE + _UNIONI + _PERSONE + _SUCCESSIONI + _VOLONTARIA + _IMMIGRAZIONE + _CITTADINANZA
)

__all__ = ["FONTI", "REGOLE"]
