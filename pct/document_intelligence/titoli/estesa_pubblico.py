"""Amministrativo e appalti, ambiente ed edilizia, beni culturali, pubblico impiego, Corte dei conti.

Regole d'identità dal titolo aggiunte il 02/11/2026 per coprire tutte le materie (direttiva dell'avvocato del
01/11/2026). Ogni regola cita la norma che definisce l'atto, registrata in `FONTI` con URL ufficiale e data di
consultazione.

Le regole di quest'area si applicano prima di `amministrativo` e `pubblico`: per questo il titolo è sempre
specifico (mai il solo «RICORSO» o la sola «DETERMINAZIONE») e, quando il titolo è comune ad altri processi
(appello, revocazione, opposizione di terzo, atto di citazione), la conferma richiede il giudice amministrativo o
contabile, così gli atti civili restano alle loro regole.
"""

from __future__ import annotations

from typing import Any

from pct.fascicoli import TipoDocumento

from ._modello import RegolaTitolo, regola

_VERIFICA = "testo vigente consultato su Normattiva il 02/11/2026"
_NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"
_CPA_URN = "decreto.legislativo:2010-07-02;104~art"
_L241 = "legge:1990-08-07;241~art"
_APPALTI = "decreto.legislativo:2023-03-31;36~art"
_TUE = "decreto.del.presidente.della.repubblica:2001-06-06;380~art"
_AMBIENTE = "decreto.legislativo:2006-04-03;152~art"
_BENI_CULTURALI = "decreto.legislativo:2004-01-22;42~art"
_ESPROPRI = "decreto.del.presidente.della.repubblica:2001-06-08;327~art"
_CONTABILE = "decreto.legislativo:2016-08-26;174:1~art"


def _fonte(label: str, urn: str) -> dict[str, Any]:
    return {"label": label, "official_url": _NORMATTIVA + urn, "verification_status": _VERIFICA, "source_type": "normativa"}


FONTI: dict[str, dict[str, Any]] = {
    # Processo amministrativo
    "estesa_pubblico_cpa_cautelare": _fonte("c.p.a., artt. 55, 56, 61 e 62: domanda cautelare, decreto monocratico, misure anteriori alla causa, appello cautelare", _CPA_URN + "56"),
    "estesa_pubblico_cpa_riti_speciali": _fonte("c.p.a., artt. 31, 116 e 117: azione avverso il silenzio e rito in materia di accesso ai documenti", _CPA_URN + "116"),
    "estesa_pubblico_cpa_giudizio": _fonte("c.p.a., artt. 46 e 73: costituzione delle parti intimate, memorie e repliche prima dell'udienza", _CPA_URN + "46"),
    "estesa_pubblico_cpa_impugnazioni": _fonte("c.p.a., artt. 100, 106 e 108: appello, revocazione e opposizione di terzo", _CPA_URN + "106"),
    "estesa_pubblico_d_lgs_373_2003_cgars": _fonte("D.Lgs. 373/2003, artt. 1 e 9: Consiglio di giustizia amministrativa per la Regione siciliana e ricorso straordinario al Presidente della Regione", "decreto.legislativo:2003-12-24;373~art9"),
    "estesa_pubblico_dpr_1199_1971_trasposizione": _fonte("D.P.R. 1199/1971, art. 10: opposizione al ricorso straordinario e trasposizione in sede giurisdizionale", "decreto.del.presidente.della.repubblica:1971-11-24;1199~art10"),
    "estesa_pubblico_d_lgs_198_2009_efficienza": _fonte("D.Lgs. 198/2009, artt. 1 e 3: ricorso per l'efficienza delle amministrazioni e dei concessionari di servizi pubblici", "decreto.legislativo:2009-12-20;198~art1"),
    # Procedimento amministrativo
    "estesa_pubblico_l241_partecipazione": _fonte("L. 241/1990, artt. 7, 8, 10 e 10-bis: avvio del procedimento, partecipazione, memorie e osservazioni", _L241 + "7"),
    "estesa_pubblico_l241_potere_sostitutivo": _fonte("L. 241/1990, art. 2, commi 9-bis e 9-ter: titolare del potere sostitutivo", _L241 + "2"),
    "estesa_pubblico_l241_conferenza_servizi": _fonte("L. 241/1990, artt. 14-14-quinquies: conferenza di servizi e determinazione conclusiva", _L241 + "14bis"),
    "estesa_pubblico_l241_autotutela": _fonte("L. 241/1990, artt. 21-quinquies e 21-nonies: revoca e annullamento d'ufficio", _L241 + "21nonies"),
    "estesa_pubblico_l241_ricorso_accesso": _fonte("L. 241/1990, art. 25, comma 4: ricorso alla Commissione per l'accesso o al difensore civico", _L241 + "25"),
    "estesa_pubblico_d_lgs_33_2013_riesame": _fonte("D.Lgs. 33/2013, art. 5, comma 7: richiesta di riesame dell'accesso civico", "decreto.legislativo:2013-03-14;33~art5"),
    # Contratti pubblici
    "estesa_pubblico_appalti_bandi": _fonte("D.Lgs. 36/2023, art. 83: bandi e avvisi, contenuti e modalità di redazione", _APPALTI + "83"),
    "estesa_pubblico_appalti_aggiudicazione": _fonte("D.Lgs. 36/2023, art. 17, comma 5: proposta di aggiudicazione e aggiudicazione", _APPALTI + "17"),
    "estesa_pubblico_appalti_informazione": _fonte("D.Lgs. 36/2023, art. 90: informazione ai candidati e agli offerenti (aggiudicazione ed esclusione)", _APPALTI + "90"),
    "estesa_pubblico_appalti_dgue": _fonte("D.Lgs. 36/2023, art. 91: domande, documento di gara unico europeo, offerte", _APPALTI + "91"),
    "estesa_pubblico_appalti_commissione": _fonte("D.Lgs. 36/2023, art. 93: commissione giudicatrice e seggio di gara", _APPALTI + "93"),
    "estesa_pubblico_appalti_soccorso": _fonte("D.Lgs. 36/2023, art. 101: soccorso istruttorio", _APPALTI + "101"),
    "estesa_pubblico_appalti_garanzie": _fonte("D.Lgs. 36/2023, artt. 106 e 117: garanzie per la partecipazione e garanzie definitive", _APPALTI + "106"),
    "estesa_pubblico_appalti_accesso": _fonte("D.Lgs. 36/2023, artt. 35 e 36: accesso agli atti di gara e riservatezza", _APPALTI + "35"),
    "estesa_pubblico_appalti_precontenzioso": _fonte("D.Lgs. 36/2023, art. 220: pareri di precontenzioso dell'ANAC", _APPALTI + "220"),
    # Edilizia e urbanistica
    "estesa_pubblico_tue_permesso": _fonte("D.P.R. 380/2001, artt. 10 e 20: permesso di costruire e procedimento per il rilascio", _TUE + "10"),
    "estesa_pubblico_tue_cila": _fonte("D.P.R. 380/2001, art. 6-bis: comunicazione di inizio lavori asseverata", _TUE + "6bis"),
    "estesa_pubblico_tue_scia": _fonte("D.P.R. 380/2001, artt. 22 e 23: segnalazione certificata di inizio attività", _TUE + "22"),
    "estesa_pubblico_tue_agibilita": _fonte("D.P.R. 380/2001, art. 24: segnalazione certificata per l'agibilità", _TUE + "24"),
    "estesa_pubblico_tue_sospensione": _fonte("D.P.R. 380/2001, art. 27: vigilanza sull'attività urbanistico-edilizia e sospensione dei lavori", _TUE + "27"),
    "estesa_pubblico_tue_cdu": _fonte("D.P.R. 380/2001, art. 30, comma 3: certificato di destinazione urbanistica", _TUE + "30"),
    "estesa_pubblico_tue_demolizione": _fonte("D.P.R. 380/2001, art. 31: interventi in assenza di permesso, ingiunzione a demolire", _TUE + "31"),
    "estesa_pubblico_tue_sanatoria": _fonte("D.P.R. 380/2001, artt. 36 e 36-bis: accertamento di conformità", _TUE + "36"),
    "estesa_pubblico_legge_47_1985_condono": _fonte("L. 47/1985, art. 31: sanatoria delle opere abusive (condono), richiamata da L. 724/1994 e D.L. 269/2003", "legge:1985-02-28;47~art31"),
    # Ambiente
    "estesa_pubblico_ambiente_via": _fonte("D.Lgs. 152/2006, artt. 25 e 27-bis: provvedimento di VIA e provvedimento autorizzatorio unico regionale", _AMBIENTE + "25"),
    "estesa_pubblico_ambiente_aia": _fonte("D.Lgs. 152/2006, art. 29-sexies: autorizzazione integrata ambientale", _AMBIENTE + "29sexies"),
    "estesa_pubblico_ambiente_rifiuti": _fonte("D.Lgs. 152/2006, art. 192: divieto di abbandono e ordinanza di rimozione dei rifiuti", _AMBIENTE + "192"),
    "estesa_pubblico_ambiente_bonifica": _fonte("D.Lgs. 152/2006, artt. 242 e 244: procedure di bonifica e ordinanze", _AMBIENTE + "244"),
    "estesa_pubblico_dpr_59_2013_aua": _fonte("D.P.R. 59/2013, art. 3: autorizzazione unica ambientale", "decreto.del.presidente.della.repubblica:2013-03-13;59~art3"),
    # Beni culturali e paesaggio
    "estesa_pubblico_beni_interesse_culturale": _fonte("D.Lgs. 42/2004, artt. 13-15: dichiarazione dell'interesse culturale", _BENI_CULTURALI + "13"),
    "estesa_pubblico_beni_alienazione": _fonte("D.Lgs. 42/2004, artt. 59-62: denuncia di trasferimento e prelazione", _BENI_CULTURALI + "59"),
    "estesa_pubblico_paesaggio_notevole_interesse": _fonte("D.Lgs. 42/2004, artt. 136-141: dichiarazione di notevole interesse pubblico", _BENI_CULTURALI + "140"),
    "estesa_pubblico_paesaggio_autorizzazione": _fonte("D.Lgs. 42/2004, art. 146: autorizzazione paesaggistica", _BENI_CULTURALI + "146"),
    "estesa_pubblico_paesaggio_compatibilita": _fonte("D.Lgs. 42/2004, art. 167, commi 4 e 5: accertamento della compatibilità paesaggistica", _BENI_CULTURALI + "167"),
    # Espropriazione
    "estesa_pubblico_espropri_avvio": _fonte("D.P.R. 327/2001, artt. 11 e 16: partecipazione degli interessati e avviso di avvio del procedimento", _ESPROPRI + "11"),
    "estesa_pubblico_espropri_pubblica_utilita": _fonte("D.P.R. 327/2001, art. 12: dichiarazione di pubblica utilità", _ESPROPRI + "12"),
    "estesa_pubblico_espropri_indennita": _fonte("D.P.R. 327/2001, art. 20: determinazione provvisoria dell'indennità di espropriazione", _ESPROPRI + "20"),
    "estesa_pubblico_espropri_occupazione": _fonte("D.P.R. 327/2001, art. 22-bis: occupazione d'urgenza preordinata all'espropriazione", _ESPROPRI + "22bis"),
    "estesa_pubblico_espropri_decreto": _fonte("D.P.R. 327/2001, art. 23: contenuto ed effetti del decreto di esproprio", _ESPROPRI + "23"),
    "estesa_pubblico_espropri_acquisizione_sanante": _fonte("D.P.R. 327/2001, art. 42-bis: utilizzazione senza titolo di un bene per scopi di interesse pubblico", _ESPROPRI + "42bis"),
    # Pubblico impiego e concorsi
    "estesa_pubblico_dpr_487_1994_bando": _fonte("D.P.R. 487/1994, art. 3: bando di concorso", "decreto.del.presidente.della.repubblica:1994-05-09;487~art3"),
    "estesa_pubblico_d_lgs_165_2001_reclutamento": _fonte("D.Lgs. 165/2001, art. 35: reclutamento del personale e vigenza delle graduatorie", "decreto.legislativo:2001-03-30;165~art35"),
    # Corte dei conti
    "estesa_pubblico_cgc_denuncia": _fonte("Codice di giustizia contabile (D.Lgs. 174/2016, all. 1), art. 52: obbligo di denuncia di danno", _CONTABILE + "52"),
    "estesa_pubblico_cgc_invito_dedurre": _fonte("Codice di giustizia contabile (D.Lgs. 174/2016, all. 1), art. 67: invito a fornire deduzioni", _CONTABILE + "67"),
    "estesa_pubblico_cgc_citazione": _fonte("Codice di giustizia contabile (D.Lgs. 174/2016, all. 1), art. 86: citazione", _CONTABILE + "86"),
    "estesa_pubblico_cgc_conto_giudiziale": _fonte("Codice di giustizia contabile (D.Lgs. 174/2016, all. 1), artt. 137-139: giudizio sui conti e presentazione del conto", _CONTABILE + "139"),
    "estesa_pubblico_cgc_impugnazioni": _fonte("Codice di giustizia contabile (D.Lgs. 174/2016, all. 1), artt. 177 e 178: mezzi di impugnazione e termini", _CONTABILE + "177"),
    # Enti locali
    "estesa_pubblico_tuel_ordinanze": _fonte("D.Lgs. 267/2000, artt. 50, comma 5, e 54, comma 4: ordinanze contingibili e urgenti del sindaco", "decreto.legislativo:2000-08-18;267~art54"),
}

# Giudice amministrativo nominato nel corpo: distingue gli atti del c.p.a. da quelli omonimi del processo civile.
_GIUDICE_AMMINISTRATIVO = (
    r"\bt\.a\.r\.|\btar\b|\btribunale\s+amministrativo\b|\bconsiglio\s+di\s+stato\b|\bc\.p\.a\.|\b104/2010\b"
    r"|\bconsiglio\s+di\s+giustizia\s+amministrativa\b"
)
_CORTE_CONTI = r"\bcorte\s+dei\s+conti\b|\bprocura\s+regionale\b|\bdanno\s+erariale\b"
_NUMERO = r"(?:\s+n\.?\s*\d+(?:/\d+)?)?"


def _atto(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str,
          role: str = "atto_principale", tipo: TipoDocumento = TipoDocumento.RICORSO) -> RegolaTitolo:
    """Atto di parte depositato nel giudizio."""
    return regola(id, titolo, conferma, label, role=role, section="atti", tipo=tipo, fonte=fonte,
                  deposit_role="atto_principale", evidence=evidence)


def _istanza(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str) -> RegolaTitolo:
    """Istanza o richiesta rivolta all'amministrazione: allegato del fascicolo."""
    return regola(id, titolo, conferma, label, role="istanza", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
                  fonte=fonte, deposit_role="allegato", evidence=evidence)


def _giudice(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str,
             tipo: TipoDocumento = TipoDocumento.DECRETO) -> RegolaTitolo:
    """Provvedimento del giudice: fuori dalla busta di deposito."""
    return regola(id, titolo, conferma, label, role="provvedimento", section="provvedimenti", tipo=tipo, fonte=fonte,
                  deposit_role="fuori_busta", deposit_candidate=False, evidence=evidence)


def _amministrazione(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str,
                     tipo: TipoDocumento = TipoDocumento.ALLEGATO, section: str = "provvedimenti") -> RegolaTitolo:
    """Provvedimento o comunicazione dell'amministrazione: allegato del fascicolo."""
    tipo_effettivo = TipoDocumento.COMUNICAZIONE if section == "comunicazioni" and tipo is TipoDocumento.ALLEGATO else tipo
    return regola(id, titolo, conferma, label, role="atto_amministrativo", section=section, tipo=tipo_effettivo,
                  fonte=fonte, deposit_role="allegato", evidence=evidence)


def _documento(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str,
               role: str = "certificato") -> RegolaTitolo:
    return regola(id, titolo, conferma, label, role=role, section="allegati", tipo=TipoDocumento.ALLEGATO,
                  fonte=fonte, deposit_role="allegato", evidence=evidence)


_PROCESSO_AMMINISTRATIVO = (
    _giudice(
        "pub_decreto_cautelare_monocratico",
        r"decreto(?:\s+presidenziale)?\s+cautelare(?:\s+.*)?|decreto\s+monocratico(?:\s+.*)?|decreto\s+(?:presidenziale\s+)?ex\s+art\.?\s*56(?:\s+.*)?",
        _GIUDICE_AMMINISTRATIVO,
        "Decreto cautelare monocratico",
        "titolo del decreto e misura provvisoria del presidente prima della camera di consiglio (art. 56 c.p.a.)",
        fonte="estesa_pubblico_cpa_cautelare",
    ),
    _giudice(
        "pub_ordinanza_cautelare_amministrativa",
        r"ordinanza\s+cautelare(?:\s+.*)?",
        _GIUDICE_AMMINISTRATIVO,
        "Ordinanza cautelare del giudice amministrativo",
        "titolo dell'ordinanza e decisione collegiale sulla domanda cautelare in camera di consiglio (art. 55 c.p.a.)",
        fonte="estesa_pubblico_cpa_cautelare", tipo=TipoDocumento.ORDINANZA,
    ),
    _atto(
        "pub_istanza_cautelare_ante_causam",
        r"(?:istanza|domanda|ricorso)\s+(?:per\s+|di\s+)?(?:misure\s+)?cautelar[ei]\s+(?:ante\s+causam|anterior[ei]\s+(?:alla\s+)?(?:causa|notificazione\s+del\s+ricorso))(?:\s+.*)?|istanza\s+ex\s+art\.?\s*61(?:\s+c\.?\s*p\.?\s*a\.?)?(?:\s+.*)?",
        r"\b61\b|\bante\s+causam\b|\beccezionale\s+gravit[aà]\b|" + _GIUDICE_AMMINISTRATIVO,
        "Istanza di misure cautelari anteriori alla causa (art. 61 c.p.a.)",
        "titolo dell'istanza ed eccezionale gravità e urgenza prima della notifica del ricorso (art. 61 c.p.a.)",
        fonte="estesa_pubblico_cpa_cautelare", role="istanza", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
    ),
    _atto(
        "pub_appello_cautelare",
        r"(?:atto\s+di\s+|ricorso\s+in\s+)?appello\s+(?:cautelare|avverso\s+(?:l.?\s*)?ordinanza\s+cautelare)(?:\s+.*)?",
        r"\b62\b|\bconsiglio\s+di\s+stato\b|\bconsiglio\s+di\s+giustizia\s+amministrativa\b|\bordinanza\s+cautelare\b",
        "Appello cautelare (art. 62 c.p.a.)",
        "titolo dell'appello e ordinanza cautelare del TAR impugnata (art. 62 c.p.a.)",
        fonte="estesa_pubblico_cpa_cautelare",
    ),
    _atto(
        "pub_ricorso_accesso_documenti",
        r"ricorso\s+(?:ex\s+art\.?\s*116(?:\s+c\.?\s*p\.?\s*a\.?)?|avverso\s+il\s+diniego\s+di\s+accesso|per\s+l.?\s*accesso\s+ai\s+documenti|in\s+materia\s+di\s+accesso)(?:\s+.*)?",
        r"\b116\b|\baccesso\s+ai\s+documenti\b|\bdiniego\s+di\s+accesso\b|\bdocumenti\s+amministrativi\b",
        "Ricorso in materia di accesso ai documenti (art. 116 c.p.a.)",
        "titolo del ricorso e diniego o silenzio sull'istanza di accesso (art. 116 c.p.a.)",
        fonte="estesa_pubblico_cpa_riti_speciali",
    ),
    _atto(
        "pub_ricorso_silenzio",
        r"ricorso\s+(?:avverso|contro|sul|per\s+la\s+declaratoria\s+di\s+illegittimit[aà]\s+del)\s+(?:il\s+)?silenzio(?:[\s-]+(?:inadempimento|rifiuto))?(?:\s+.*)?|ricorso\s+ex\s+artt?\.?\s*(?:31\s+e\s+)?117(?:\s+c\.?\s*p\.?\s*a\.?)?(?:\s+.*)?",
        r"\b117\b|\b31\b|\bsilenzio\b|\bobbligo\s+di\s+provvedere\b",
        "Ricorso avverso il silenzio dell'amministrazione",
        "titolo del ricorso e obbligo dell'amministrazione di provvedere (artt. 31 e 117 c.p.a.)",
        fonte="estesa_pubblico_cpa_riti_speciali",
    ),
    _atto(
        "pub_costituzione_giudizio_amministrativo",
        r"(?:atto|memoria)\s+di\s+costituzione(?:\s+.*)?|costituzione\s+in\s+giudizio(?:\s+.*)?",
        r"\bamministrazione\s+resistente\b|\bcontrointeressat\w+\b|" + _GIUDICE_AMMINISTRATIVO,
        "Atto di costituzione nel giudizio amministrativo",
        "titolo dell'atto e costituzione dell'amministrazione o del controinteressato (art. 46 c.p.a.)",
        fonte="estesa_pubblico_cpa_giudizio", role="atto_difensivo", tipo=TipoDocumento.MEMORIA,
    ),
    _atto(
        "pub_memoria_art_73_cpa",
        r"(?:memoria|replica|memoria\s+o\s+replica|memoria\s+di\s+replica|memoria\s+difensiva|memoria\s+conclusiva)\s+(?:ex|ai\s+sensi\s+dell.?)\s*art\.?\s*73(?:\s+.*)?",
        _GIUDICE_AMMINISTRATIVO + r"|\b73\b",
        "Memoria o replica ex art. 73 c.p.a.",
        "titolo della memoria e termini prima dell'udienza di discussione (art. 73 c.p.a.)",
        fonte="estesa_pubblico_cpa_giudizio", role="atto_difensivo", tipo=TipoDocumento.MEMORIA,
    ),
    _atto(
        "pub_revocazione_amministrativa",
        r"(?:ricorso\s+per\s+)?revocazione(?:\s+.*)?",
        _GIUDICE_AMMINISTRATIVO,
        "Ricorso per revocazione nel processo amministrativo",
        "titolo del ricorso e sentenza del giudice amministrativo impugnata (art. 106 c.p.a.)",
        fonte="estesa_pubblico_cpa_impugnazioni",
    ),
    _atto(
        "pub_opposizione_terzo_amministrativa",
        r"(?:atto\s+di\s+|ricorso\s+(?:per|in)\s+)?opposizione\s+di\s+terzo(?:\s+.*)?",
        _GIUDICE_AMMINISTRATIVO,
        "Opposizione di terzo nel processo amministrativo",
        "titolo dell'atto e sentenza del giudice amministrativo che pregiudica il terzo (art. 108 c.p.a.)",
        fonte="estesa_pubblico_cpa_impugnazioni",
    ),
    _atto(
        "pub_appello_cgars",
        r"(?:atto\s+di\s+|ricorso\s+in\s+)?appello(?:\s+.*)?",
        r"\bconsiglio\s+di\s+giustizia\s+amministrativa\b|\bc\.g\.a\.r\.s\.|\bcgars\b",
        "Appello al Consiglio di Giustizia Amministrativa per la Regione Siciliana",
        "titolo dell'appello e giudice d'appello per la Sicilia (art. 1 D.Lgs. 373/2003; art. 100 c.p.a.)",
        fonte="estesa_pubblico_d_lgs_373_2003_cgars",
    ),
    _atto(
        "pub_ricorso_straordinario_sicilia",
        r"ricorso\s+straordinario\s+al\s+presidente\s+della\s+regione(?:\s+.*)?",
        r"\bregione\s+sicilian\w+\b|\bstatuto\b|\b373/2003\b|\bconsiglio\s+di\s+giustizia\s+amministrativa\b",
        "Ricorso straordinario al Presidente della Regione Siciliana",
        "titolo del ricorso e rimedio straordinario regionale (art. 9 D.Lgs. 373/2003)",
        fonte="estesa_pubblico_d_lgs_373_2003_cgars",
    ),
    _atto(
        "pub_opposizione_ricorso_straordinario",
        r"(?:atto\s+di\s+)?opposizione\s+(?:al\s+ricorso\s+straordinario|ex\s+art\.?\s*10\s+d\.?\s*p\.?\s*r\.?\s*(?:n\.?\s*)?1199(?:/1971)?)(?:\s+.*)?|(?:atto\s+di\s+)?trasposizione(?:\s+in\s+sede\s+giurisdizionale)?(?:\s+.*)?",
        r"\b1199\b|\btrasposizion\w+\b|\bsede\s+giurisdizionale\b|\b48\b",
        "Opposizione al ricorso straordinario e trasposizione in sede giurisdizionale",
        "titolo dell'atto e richiesta di decisione in sede giurisdizionale (art. 10 D.P.R. 1199/1971; art. 48 c.p.a.)",
        fonte="estesa_pubblico_dpr_1199_1971_trasposizione",
    ),
    _atto(
        "pub_ricorso_efficienza_amministrazioni",
        r"ricorso\s+(?:per\s+l.?\s*efficienza\s+delle\s+amministrazioni|ex\s+(?:art\.?\s*1\s+)?d\.?\s*lgs\.?\s*(?:n\.?\s*)?198/2009)(?:\s+.*)?|(?:azione|ricorso)\s+collettiv[ao]\s+pubblic[ao](?:\s+.*)?|class\s+action\s+pubblica(?:\s+.*)?",
        r"\b198/2009\b|\b(?:in)?efficienz\w*\b|\bstandard\s+qualitativ\w+\b|\bdiffida\b",
        "Ricorso per l'efficienza delle amministrazioni (class action pubblica)",
        "titolo del ricorso e violazione degli standard qualitativi del servizio (art. 1 D.Lgs. 198/2009)",
        fonte="estesa_pubblico_d_lgs_198_2009_efficienza",
    ),
)

_PROCEDIMENTO = (
    # Espropriazione prima dell'avvio generico: l'avviso dell'esproprio ha regole proprie.
    _amministrazione(
        "pub_avvio_procedimento_espropriativo",
        r"(?:comunicazione|avviso)\s+(?:di\s+)?avvio\s+del\s+procedimento\s+(?:espropriativo|di\s+esproprio|di\s+espropriazione|(?:finalizzato|diretto|preordinato)\s+(?:all.?\s*)?(?:apposizione\s+del\s+vincolo|dichiarazione\s+di\s+pubblica\s+utilit[aà]|esproprio))(?:\s+.*)?",
        r"\b327/2001\b|\bpreordinato\s+all.?\s*esproprio\b|\bpubblica\s+utilit[aà]\b|\bespropri\w+\b",
        "Avviso di avvio del procedimento espropriativo",
        "titolo dell'avviso e vincolo preordinato all'esproprio (artt. 11 e 16 D.P.R. 327/2001)",
        fonte="estesa_pubblico_espropri_avvio", section="comunicazioni",
    ),
    _amministrazione(
        "pub_avvio_procedimento",
        r"comunicazione\s+(?:di\s+)?avvio\s+(?:del\s+)?procedimento(?:\s+.*)?|avviso\s+di\s+avvio\s+del\s+procedimento(?:\s+.*)?",
        r"\bartt?\.?\s*[78]\b|\bresponsabile\s+del\s+procedimento\b|\b241/1990\b",
        "Comunicazione di avvio del procedimento",
        "titolo della comunicazione e responsabile del procedimento (artt. 7 e 8 L. 241/1990)",
        fonte="estesa_pubblico_l241_partecipazione", section="comunicazioni",
    ),
    _istanza(
        "pub_osservazioni_procedimento",
        r"memori[ae]\s+procedimental[ei](?:\s+.*)?|(?:osservazioni|memorie(?:\s+scritte)?|controdeduzioni)(?:\s+e\s+(?:documenti|memorie))?\s+(?:al\s+preavviso\s+di\s+rigetto|ai\s+sensi\s+dell.?\s*art\.?\s*10(?:[\s-]*bis)?|ex\s+artt?\.?\s*10(?:[\s-]*bis)?|procedimental[ei]|alla\s+comunicazione\s+dei\s+motivi\s+ostativi|nel\s+procedimento\s+amministrativo)(?:\s+.*)?",
        r"\b10(?:[\s-]*bis)?\b|\b241/1990\b|\bmotivi\s+ostativi\b|\bpartecipazion\w+\b|\bpreavviso\s+di\s+(?:diniego|rigetto)\b",
        "Osservazioni e memorie nel procedimento amministrativo",
        "titolo dell'atto e partecipazione dell'interessato al procedimento (artt. 10 e 10-bis L. 241/1990)",
        fonte="estesa_pubblico_l241_partecipazione",
    ),
    _istanza(
        "pub_riesame_accesso_civico",
        r"(?:richiesta|istanza|domanda)\s+di\s+riesame\s+(?:dell.?\s*(?:istanza\s+di\s+)?accesso(?:\s+civico)?|ex\s+art\.?\s*5)(?:\s+.*)?",
        r"\baccesso\s+civico\b|\b33/2013\b|\bresponsabile\s+della\s+prevenzione\s+della\s+corruzione\b",
        "Richiesta di riesame dell'accesso civico",
        "titolo della richiesta e diniego dell'accesso civico (art. 5, comma 7, D.Lgs. 33/2013)",
        fonte="estesa_pubblico_d_lgs_33_2013_riesame",
    ),
    _istanza(
        "pub_ricorso_commissione_accesso",
        r"ricorso\s+alla\s+commissione\s+per\s+l.?\s*accesso(?:\s+.*)?|ricorso\s+al\s+difensore\s+civico(?:\s+.*)?",
        r"\b25\b|\bcommissione\s+per\s+l.?\s*accesso\b|\bdifensore\s+civico\b|\bdiniego\b",
        "Ricorso alla Commissione per l'accesso o al difensore civico",
        "titolo del ricorso e diniego dell'accesso documentale (art. 25, comma 4, L. 241/1990)",
        fonte="estesa_pubblico_l241_ricorso_accesso",
    ),
    _istanza(
        "pub_istanza_autotutela",
        r"(?:istanza|richiesta|domanda)\s+di\s+(?:annullamento\s+(?:d.?\s*ufficio|in\s+autotutela)|revoca\s+in\s+autotutela|riesame\s+in\s+autotutela|autotutela)(?:\s+.*)?",
        r"\b21[\s-]*(?:nonies|quinquies)\b|\b241/1990\b|\bannullament\w+\s+d.?\s*ufficio\b",
        "Istanza di autotutela amministrativa",
        "titolo dell'istanza e annullamento d'ufficio o revoca del provvedimento (artt. 21-quinquies e 21-nonies L. 241/1990)",
        fonte="estesa_pubblico_l241_autotutela",
    ),
    _amministrazione(
        "pub_annullamento_autotutela",
        r"(?:provvedimento|determinazione|decreto)\s+di\s+(?:annullamento\s+(?:d.?\s*ufficio|in\s+autotutela)|revoca\s+(?:in\s+autotutela|del\s+provvedimento))(?:\s+.*)?|provvedimento\s+di\s+annullamento\s+o\s+revoca(?:\s+.*)?|annullamento\s+d.?\s*ufficio(?:\s+.*)?|revoca\s+in\s+autotutela(?:\s+.*)?",
        r"\b21[\s-]*(?:nonies|quinquies)\b|\bautotutela\b|\binteresse\s+pubblico\b",
        "Provvedimento di annullamento o revoca in autotutela",
        "titolo del provvedimento e ragioni di interesse pubblico (artt. 21-quinquies e 21-nonies L. 241/1990)",
        fonte="estesa_pubblico_l241_autotutela",
    ),
    _istanza(
        "pub_istanza_potere_sostitutivo",
        r"(?:istanza|richiesta|domanda)\s+(?:di\s+intervento\s+)?(?:al|del)\s+titolare\s+del\s+potere\s+sostitutivo(?:\s+.*)?|(?:istanza|richiesta)\s+di\s+esercizio\s+del\s+potere\s+sostitutivo(?:\s+.*)?",
        r"\bpotere\s+sostitutivo\b|\b9[\s-]*ter\b|\btermine\s+di\s+conclusione\b",
        "Istanza al titolare del potere sostitutivo",
        "titolo dell'istanza e inerzia oltre il termine di conclusione del procedimento (art. 2, comma 9-ter, L. 241/1990)",
        fonte="estesa_pubblico_l241_potere_sostitutivo",
    ),
    _amministrazione(
        "pub_indizione_conferenza_servizi",
        r"(?:indizione|convocazione)\s+(?:della\s+)?conferenza\s+di\s+servizi(?:\s+.*)?|(?:avviso|comunicazione)\s+di\s+(?:indizione|convocazione)\s+(?:della\s+)?conferenza\s+di\s+servizi(?:\s+.*)?",
        r"\b14[\s-]*(?:bis|ter)\b|\bconferenza\s+di\s+servizi\b|\bamministrazioni\s+coinvolte\b",
        "Indizione della conferenza di servizi",
        "titolo dell'atto e amministrazioni coinvolte nella conferenza (artt. 14-bis e 14-ter L. 241/1990)",
        fonte="estesa_pubblico_l241_conferenza_servizi", section="comunicazioni",
    ),
    _amministrazione(
        "pub_determinazione_conferenza_servizi",
        r"determinazione\s+(?:motivata\s+)?(?:di\s+)?conclusi(?:va|one)(?:\s+(?:positiva|negativa))?\s+(?:della|del\s+procedimento\s+di)\s+conferenza\s+di\s+servizi(?:\s+.*)?|verbale\s+(?:conclusivo\s+)?della\s+conferenza\s+di\s+servizi(?:\s+.*)?",
        r"\b14[\s-]*(?:bis|ter|quater)\b|\bconferenza\s+di\s+servizi\b",
        "Determinazione conclusiva della conferenza di servizi",
        "titolo della determinazione e assensi delle amministrazioni coinvolte (art. 14-quater L. 241/1990)",
        fonte="estesa_pubblico_l241_conferenza_servizi",
    ),
)

_APPALTI_PUBBLICI = (
    _amministrazione(
        "pub_bando_gara",
        r"bando\s+(?:o\s+disciplinare\s+)?di\s+gara(?:\s+.*)?|bando\s+per\s+l.?\s*affidamento(?:\s+.*)?|(?:avviso|disciplinare)\s+di\s+gara(?:\s+.*)?|lettera\s+di\s+invito\s+(?:alla\s+)?(?:gara|procedura\s+negoziata)(?:\s+.*)?",
        r"\b36/2023\b|\bstazione\s+appaltante\b|\boperator\w+\s+economic\w+\b|\bcig\b|\bofferte\b",
        "Bando o disciplinare di gara",
        "titolo del bando e stazione appaltante con le regole della procedura (art. 83 D.Lgs. 36/2023)",
        fonte="estesa_pubblico_appalti_bandi",
    ),
    _amministrazione(
        "pub_aggiudicazione",
        r"(?:provvedimento|determinazione|determina|decreto|comunicazione)\s+di\s+aggiudicazione(?:\s+.*)?|aggiudicazione\s+(?:definitiva|efficace|dell.?\s*appalto)(?:\s+.*)?",
        r"\baggiudicatari\w*\b|\bstazione\s+appaltante\b|\bproposta\s+di\s+aggiudicazione\b|\b36/2023\b",
        "Provvedimento di aggiudicazione",
        "titolo del provvedimento e approvazione della proposta di aggiudicazione (artt. 17, comma 5, e 90 D.Lgs. 36/2023)",
        fonte="estesa_pubblico_appalti_aggiudicazione",
    ),
    _amministrazione(
        "pub_esclusione_gara",
        r"(?:provvedimento|determinazione|determina|comunicazione)\s+di\s+esclusione(?:\s+dalla\s+(?:gara|procedura))?(?:\s+.*)?",
        r"\bgara\b|\bprocedura\s+di\s+affidamento\b|\bstazione\s+appaltante\b|\boperatore\s+economico\b|\b36/2023\b",
        "Provvedimento di esclusione dalla gara",
        "titolo del provvedimento e motivi di esclusione comunicati all'offerente (art. 90 D.Lgs. 36/2023)",
        fonte="estesa_pubblico_appalti_informazione",
    ),
    _amministrazione(
        "pub_soccorso_istruttorio",
        r"(?:richiesta|comunicazione|nota)\s+(?:di\s+)?soccorso\s+istruttorio(?:\s+.*)?|soccorso\s+istruttorio(?:\s+.*)?",
        r"\b101\b|\bsoccorso\s+istruttorio\b|\bintegra\w+\b|\bdocumentazione\s+di\s+gara\b",
        "Richiesta di soccorso istruttorio",
        "titolo della richiesta e termine per integrare la documentazione di gara (art. 101 D.Lgs. 36/2023)",
        fonte="estesa_pubblico_appalti_soccorso", section="comunicazioni",
    ),
    _istanza(
        "pub_accesso_atti_gara",
        r"(?:istanza|richiesta|domanda)\s+di\s+accesso\s+(?:agli\s+atti|ai\s+documenti)\s+(?:della|di)\s+(?:gara|procedura(?:\s+di\s+(?:gara|affidamento))?)(?:\s+.*)?|(?:istanza|richiesta)\s+di\s+accesso\s+ex\s+artt?\.?\s*35(?:\s+e\s+36)?(?:\s+.*)?",
        r"\b3[56]\b|\bgara\b|\bofferta\b|\bstazione\s+appaltante\b|\b36/2023\b",
        "Istanza di accesso agli atti di gara",
        "titolo dell'istanza e documenti della procedura di affidamento (artt. 35 e 36 D.Lgs. 36/2023)",
        fonte="estesa_pubblico_appalti_accesso",
    ),
    _istanza(
        "pub_istanza_precontenzioso_anac",
        r"(?:istanza|richiesta|domanda)\s+di\s+parere\s+(?:di\s+)?precontenzioso(?:\s+.*)?|istanza\s+(?:di\s+)?precontenzioso(?:\s+.*)?",
        r"\banac\b|\bautorit[aà]\s+nazionale\s+anticorruzione\b|\b220\b|\bprecontenzioso\b",
        "Istanza di parere di precontenzioso ANAC",
        "titolo dell'istanza e questione insorta durante la gara sottoposta all'ANAC (art. 220, comma 1, D.Lgs. 36/2023)",
        fonte="estesa_pubblico_appalti_precontenzioso",
    ),
    _amministrazione(
        "pub_parere_precontenzioso_anac",
        r"parere\s+(?:di\s+)?precontenzioso(?:\s+.*)?|parere\s+(?:anac\s+)?(?:ex\s+)?art\.?\s*220(?:\s+.*)?",
        r"\banac\b|\bautorit[aà]\s+nazionale\s+anticorruzione\b|\b220\b",
        "Parere di precontenzioso ANAC",
        "titolo del parere e decisione dell'ANAC sulla questione di gara (art. 220, comma 1, D.Lgs. 36/2023)",
        fonte="estesa_pubblico_appalti_precontenzioso",
    ),
    _amministrazione(
        "pub_verbale_gara",
        r"verbale\s+(?:di\s+gara|(?:della\s+)?seduta\s+(?:pubblica\s+|riservata\s+)?(?:di\s+gara|della\s+commissione\s+giudicatrice)|della\s+commissione\s+giudicatrice|del\s+seggio\s+di\s+gara)(?:\s+.*)?",
        r"\b93\b|\bcommissione\s+giudicatrice\b|\bseggio\s+di\s+gara\b|\bofferte\b|\bpunteggi\w*\b",
        "Verbale di gara",
        "titolo del verbale e lavori della commissione giudicatrice o del seggio di gara (art. 93 D.Lgs. 36/2023)",
        fonte="estesa_pubblico_appalti_commissione", tipo=TipoDocumento.VERBALE,
    ),
    _documento(
        "pub_dgue",
        r"documento\s+di\s+gara\s+unico\s+europeo(?:\s+.*)?|d\.g\.u\.e\.(?:\s+.*)?|dgue(?:\s+.*)?",
        r"\boperatore\s+economico\b|\bmotivi\s+di\s+esclusione\b|\b91\b|\bcriteri\s+di\s+selezione\b",
        "Documento di gara unico europeo (DGUE)",
        "titolo del documento e dichiarazioni dell'operatore economico sui motivi di esclusione (art. 91 D.Lgs. 36/2023)",
        fonte="estesa_pubblico_appalti_dgue", role="dichiarazione_sostitutiva",
    ),
    _documento(
        "pub_garanzia_appalti",
        r"(?:garanzia|cauzione)\s+(?:provvisoria|definitiva)(?:\s+.*)?|polizza\s+fideiussoria\s+(?:provvisoria|definitiva|per\s+la\s+partecipazione\s+alla\s+gara)(?:\s+.*)?",
        r"\b10[67]\b|\b117\b|\bstazione\s+appaltante\b|\bfideiussion\w+\b",
        "Garanzia provvisoria o definitiva negli appalti pubblici",
        "titolo della garanzia e stazione appaltante beneficiaria (artt. 106 e 117 D.Lgs. 36/2023)",
        fonte="estesa_pubblico_appalti_garanzie", role="documento_economico",
    ),
)

_EDILIZIA = (
    _amministrazione(
        "pub_sanatoria_edilizia",
        r"(?:permesso\s+di\s+costruire\s+in\s+sanatoria|(?:istanza|domanda|richiesta)\s+di\s+(?:accertamento\s+di\s+conformit[aà]|sanatoria(?:\s+edilizia)?|permesso\s+(?:di\s+costruire\s+)?in\s+sanatoria)|accertamento\s+di\s+conformit[aà]|sanatoria\s+edilizia)(?:\s+.*)?",
        r"\b36(?:[\s-]*bis)?\b|\bdoppia\s+conformit[aà]\b|\bsanatoria\b|\b380/2001\b",
        "Accertamento di conformità e sanatoria edilizia",
        "titolo dell'atto e conformità alla disciplina urbanistica ed edilizia (artt. 36 e 36-bis D.P.R. 380/2001)",
        fonte="estesa_pubblico_tue_sanatoria",
    ),
    _amministrazione(
        "pub_condono_edilizio",
        r"(?:domanda|istanza)\s+di\s+condono(?:\s+edilizio)?(?:\s+.*)?|condono\s+edilizio(?:\s+.*)?|concessione\s+(?:edilizia\s+)?in\s+sanatoria(?:\s+.*)?",
        r"\b47/1985\b|\b724/1994\b|\b269/2003\b|\bcondono\b|\boblazione\b",
        "Condono edilizio",
        "titolo dell'atto e oblazione per le opere abusive (art. 31 L. 47/1985; art. 39 L. 724/1994; art. 32 D.L. 269/2003)",
        fonte="estesa_pubblico_legge_47_1985_condono",
    ),
    _istanza(
        "pub_domanda_permesso_costruire",
        r"(?:domanda|istanza|richiesta)\s+(?:di|per\s+il\s+rilascio\s+del)\s+permesso\s+di\s+costruire(?:\s+.*)?",
        r"\b380/2001\b|\bsportello\s+unico\s+per\s+l.?\s*edilizia\b|\bprogett\w+\b|\btitolo\s+abilitativo\b",
        "Domanda di permesso di costruire",
        "titolo della domanda e progetto presentato allo sportello unico per l'edilizia (art. 20 D.P.R. 380/2001)",
        fonte="estesa_pubblico_tue_permesso",
    ),
    _amministrazione(
        "pub_permesso_costruire",
        r"permesso\s+di\s+costruire(?:\s+.*)?",
        r"\b380/2001\b|\bsportello\s+unico\s+per\s+l.?\s*edilizia\b|\brilascia\b|\btitolo\s+abilitativo\b|\bart\.?\s*(?:10|20)\b",
        "Permesso di costruire",
        "titolo del provvedimento e rilascio del titolo abilitativo (artt. 10 e 20 D.P.R. 380/2001)",
        fonte="estesa_pubblico_tue_permesso",
    ),
    _amministrazione(
        "pub_agibilita",
        r"(?:segnalazione\s+certificata|s\.?\s*c\.?\s*a\.?|s\.?\s*c\.?\s*i\.?\s*a\.?)\s+(?:per\s+l.?\s*|di\s+)?agibilit[aà](?:\s+.*)?|certificato\s+di\s+agibilit[aà](?:\s+.*)?",
        r"\b24\b|\bagibilit[aà]\b|\b380/2001\b",
        "Segnalazione certificata per l'agibilità",
        "titolo della segnalazione e sicurezza, igiene e salubrità dell'edificio (art. 24 D.P.R. 380/2001)",
        fonte="estesa_pubblico_tue_agibilita",
    ),
    _amministrazione(
        "pub_scia",
        r"(?:s\.?\s*c\.?\s*i\.?\s*a\.?|segnalazione\s+certificata\s+di\s+inizio\s+attivit[aà])(?:\s+.*)?",
        r"\b2[23]\b|\b380/2001\b|\b19\b|\b241/1990\b|\binizio\s+(?:dei\s+)?lavori\b|\bsportello\s+unico\b",
        "Segnalazione certificata di inizio attività (SCIA)",
        "titolo della segnalazione e interventi edilizi assoggettati (artt. 22 e 23 D.P.R. 380/2001; art. 19 L. 241/1990)",
        fonte="estesa_pubblico_tue_scia",
    ),
    _amministrazione(
        "pub_cila",
        r"(?:c\.?\s*i\.?\s*l\.?\s*a\.?(?:\s*s\.?)?|comunicazione\s+(?:di\s+)?inizio\s+lavori\s+asseverata)(?:\s+.*)?",
        r"\b6[\s-]*bis\b|\bassever\w+\b|\btecnico\s+abilitato\b|\b380/2001\b",
        "Comunicazione di inizio lavori asseverata (CILA)",
        "titolo della comunicazione e asseverazione del tecnico abilitato (art. 6-bis D.P.R. 380/2001)",
        fonte="estesa_pubblico_tue_cila",
    ),
    _amministrazione(
        "pub_ordinanza_demolizione",
        r"ordinanza(?:\s+(?:dirigenziale|sindacale))?" + _NUMERO + r"\s+(?:di\s+)?(?:demolizione|ingiunzione\s+(?:alla\s+|a\s+)?demoli\w+|rimessione\s+in\s+pristino|ripristino\s+dello\s+stato\s+dei\s+luoghi)(?:\s+.*)?|ingiunzione\s+(?:di|a|alla)\s+demoli\w+(?:\s+.*)?",
        r"\b31\b|\b380/2001\b|\babusiv\w+\b|\bdemoli\w+\b|\bnovanta\s+giorni\b",
        "Ordinanza di demolizione",
        "titolo dell'ordinanza e ingiunzione a demolire le opere abusive (art. 31 D.P.R. 380/2001)",
        fonte="estesa_pubblico_tue_demolizione", tipo=TipoDocumento.ORDINANZA,
    ),
    _amministrazione(
        "pub_ordinanza_sospensione_lavori",
        r"ordinanza(?:\s+(?:dirigenziale|sindacale))?" + _NUMERO + r"\s+(?:di\s+)?sospensione\s+(?:dei\s+)?lavori(?:\s+.*)?",
        r"\b27\b|\b380/2001\b|\bsospension\w+\b|\babusiv\w+\b",
        "Ordinanza di sospensione dei lavori",
        "titolo dell'ordinanza e vigilanza sull'attività edilizia (art. 27 D.P.R. 380/2001)",
        fonte="estesa_pubblico_tue_sospensione", tipo=TipoDocumento.ORDINANZA,
    ),
    _documento(
        "pub_certificato_destinazione_urbanistica",
        r"certificato\s+di\s+destinazione\s+urbanistica(?:\s+.*)?",
        r"\b30\b|\bprescrizioni\s+urbanistiche\b|\bfoglio\b|\bparticell\w+\b|\bpiano\s+regolatore\b|\bzona\b",
        "Certificato di destinazione urbanistica",
        "titolo del certificato e prescrizioni urbanistiche dell'area (art. 30, comma 3, D.P.R. 380/2001)",
        fonte="estesa_pubblico_tue_cdu",
    ),
)

_AMBIENTE_E_PAESAGGIO = (
    _amministrazione(
        "pub_provvedimento_via",
        r"(?:provvedimento|decreto|determinazione)\s+(?:di\s+|del(?:la)?\s+)?(?:valutazione\s+(?:di\s+|dell.?\s*)?impatto\s+ambientale|v\.?\s*i\.?\s*a\.?|compatibilit[aà]\s+ambientale|verifica\s+di\s+assoggettabilit[aà](?:\s+a\s+v\.?\s*i\.?\s*a\.?)?)(?:\s+.*)?|provvedimento\s+autorizzatorio\s+unico(?:\s+regionale)?(?:\s+.*)?",
        r"\b2[5-7](?:[\s-]*bis)?\b|\b152/2006\b|\bimpatto\s+ambientale\b|\b(?:prescrizion|condizion)\w+\s+ambiental\w+\b|\bcompatibilit[aà]\s+ambientale\b",
        "Provvedimento di valutazione di impatto ambientale (VIA)",
        "titolo del provvedimento e valutazione degli impatti del progetto (artt. 25 e 27-bis D.Lgs. 152/2006)",
        fonte="estesa_pubblico_ambiente_via",
    ),
    _amministrazione(
        "pub_autorizzazione_integrata_ambientale",
        r"autorizzazione\s+integrata\s+ambientale(?:\s+.*)?|(?:provvedimento|decreto|determinazione)\s+di\s+(?:rilascio\s+(?:dell.?\s*)?)?autorizzazione\s+integrata\s+ambientale(?:\s+.*)?",
        r"\b29[\s-]*(?:sexies|ter|octies|decies)\b|\b152/2006\b|\binstallazion\w+\b|\bemission\w+\b|\bmigliori\s+tecniche\s+disponibili\b",
        "Autorizzazione integrata ambientale (AIA)",
        "titolo dell'autorizzazione e condizioni dell'installazione (art. 29-sexies D.Lgs. 152/2006)",
        fonte="estesa_pubblico_ambiente_aia",
    ),
    _amministrazione(
        "pub_autorizzazione_unica_ambientale",
        r"autorizzazione\s+unica\s+ambientale(?:\s+.*)?|(?:provvedimento|determinazione)\s+di\s+(?:rilascio\s+(?:dell.?\s*)?)?autorizzazione\s+unica\s+ambientale(?:\s+.*)?",
        r"\b59/2013\b|\bsuap\b|\bsportello\s+unico\s+per\s+le\s+attivit[aà]\s+produttive\b|\bscarich\w+\b|\bemission\w+\b",
        "Autorizzazione unica ambientale (AUA)",
        "titolo dell'autorizzazione e titoli ambientali sostituiti (art. 3 D.P.R. 59/2013)",
        fonte="estesa_pubblico_dpr_59_2013_aua",
    ),
    _amministrazione(
        "pub_ordinanza_rimozione_rifiuti",
        r"ordinanza(?:\s+(?:sindacale|dirigenziale))?" + _NUMERO + r"\s+(?:di\s+)?(?:rimozione(?:\s+e\s+smaltimento)?\s+(?:dei\s+)?rifiuti|rimozione,?\s+avvio\s+a\s+recupero)(?:\s+.*)?|ordinanza\s+ex\s+art\.?\s*192(?:\s+.*)?",
        r"\b192\b|\b152/2006\b|\babbandon\w+\b|\brifiuti\b|\brecupero\b|\bsmaltiment\w+\b",
        "Ordinanza di rimozione dei rifiuti",
        "titolo dell'ordinanza e abbandono o deposito incontrollato di rifiuti (art. 192 D.Lgs. 152/2006)",
        fonte="estesa_pubblico_ambiente_rifiuti", tipo=TipoDocumento.ORDINANZA,
    ),
    _amministrazione(
        "pub_ordinanza_bonifica",
        r"ordinanza(?:\s+(?:provinciale|dirigenziale|sindacale))?" + _NUMERO + r"\s+(?:di\s+)?(?:bonifica|messa\s+in\s+sicurezza)(?:\s+.*)?|diffida\s+(?:alla\s+)?bonifica(?:\s+.*)?|ordinanza\s+ex\s+art\.?\s*244(?:\s+.*)?",
        r"\b24[2-5]\b|\b152/2006\b|\bcontamina\w+\b|\bconcentrazion\w+\s+soglia\b",
        "Ordinanza di bonifica del sito contaminato",
        "titolo dell'ordinanza e responsabile della contaminazione (art. 244 D.Lgs. 152/2006)",
        fonte="estesa_pubblico_ambiente_bonifica", tipo=TipoDocumento.ORDINANZA,
    ),
    _istanza(
        "pub_istanza_autorizzazione_paesaggistica",
        r"(?:istanza|domanda|richiesta)\s+di\s+(?:rilascio\s+(?:dell.?\s*)?)?autorizzazione\s+paesaggistica(?:\s+.*)?",
        r"\b146\b|\b42/2004\b|\bsoprintendenz\w+\b|\brelazione\s+paesaggistica\b|\b31/2017\b|\bvincolo\b",
        "Istanza di autorizzazione paesaggistica",
        "titolo dell'istanza e relazione paesaggistica allegata al progetto (art. 146 D.Lgs. 42/2004)",
        fonte="estesa_pubblico_paesaggio_autorizzazione",
    ),
    _amministrazione(
        "pub_autorizzazione_paesaggistica",
        r"autorizzazione\s+paesaggistica(?:\s+.*)?|(?:provvedimento|determinazione)\s+di\s+(?:rilascio\s+(?:dell.?\s*)?)?autorizzazione\s+paesaggistica(?:\s+.*)?",
        r"\b146\b|\b42/2004\b|\bsoprintendenz\w+\b|\bcompatibilit[aà]\s+paesaggistica\b|\b31/2017\b|\bvincol\w+\b",
        "Autorizzazione paesaggistica",
        "titolo dell'autorizzazione e parere della soprintendenza (art. 146 D.Lgs. 42/2004)",
        fonte="estesa_pubblico_paesaggio_autorizzazione",
    ),
    _amministrazione(
        "pub_compatibilita_paesaggistica",
        r"(?:istanza|domanda|richiesta)\s+di\s+accertamento\s+(?:della\s+|di\s+)?compatibilit[aà]\s+paesaggistica(?:\s+.*)?|accertamento\s+(?:della\s+|di\s+)?compatibilit[aà]\s+paesaggistica(?:\s+.*)?",
        r"\b167\b|\b181\b|\b42/2004\b|\bsoprintendenz\w+\b|\bindennit[aà]\s+pecuniaria\b|\bsenza\s+autorizzazione\b|\bmateriali\s+diversi\b",
        "Accertamento di compatibilità paesaggistica",
        "titolo dell'atto e opere eseguite senza autorizzazione paesaggistica (art. 167, commi 4 e 5, D.Lgs. 42/2004)",
        fonte="estesa_pubblico_paesaggio_compatibilita",
    ),
    _amministrazione(
        "pub_dichiarazione_interesse_culturale",
        r"(?:decreto\s+di\s+|provvedimento\s+di\s+)?dichiarazione\s+(?:dell.?\s*|di\s+)?interesse\s+(?:culturale|storico[\s-]*artistico|archeologico)(?:\s+.*)?|(?:decreto\s+di\s+)?vincolo\s+(?:storico[\s-]*artistico|culturale|monumentale|archeologico)(?:\s+.*)?",
        r"\b1[34]\b|\b42/2004\b|\binteresse\s+(?:artistico|storico|archeologico|etnoantropologico|culturale)\b|\bsoprintendenz\w+\b",
        "Dichiarazione di interesse culturale",
        "titolo del provvedimento e interesse culturale del bene (artt. 13 e 14 D.Lgs. 42/2004)",
        fonte="estesa_pubblico_beni_interesse_culturale",
    ),
    _amministrazione(
        "pub_notevole_interesse_paesaggistico",
        r"(?:decreto\s+di\s+|provvedimento\s+di\s+|proposta\s+di\s+)?dichiarazione\s+di\s+notevole\s+interesse\s+pubblico(?:\s+.*)?|vincolo\s+paesaggistico(?:\s+.*)?",
        r"\b13[6-9]\b|\b140\b|\b42/2004\b|\bpaesaggi\w+\b|\bbellezz\w+\b|\bvalore\s+estetico\b",
        "Dichiarazione di notevole interesse pubblico paesaggistico",
        "titolo del provvedimento e immobili o aree di notevole interesse pubblico (artt. 136 e 140 D.Lgs. 42/2004)",
        fonte="estesa_pubblico_paesaggio_notevole_interesse",
    ),
    _amministrazione(
        "pub_denuncia_trasferimento_bene_culturale",
        r"denuncia\s+(?:di\s+)?(?:trasferimento|alienazione)(?:\s+.*)?",
        r"\bprelazion\w+\b|\b42/2004\b|\bministero\s+della\s+cultura\b|\bsoprintendenz\w+\b|\bbene\s+culturale\b",
        "Denuncia di trasferimento di bene culturale",
        "titolo della denuncia e diritto di prelazione dello Stato (artt. 59 e 60 D.Lgs. 42/2004)",
        fonte="estesa_pubblico_beni_alienazione", section="comunicazioni",
    ),
    _amministrazione(
        "pub_prelazione_bene_culturale",
        r"(?:provvedimento|decreto|atto)\s+di\s+(?:esercizio\s+(?:del\s+diritto\s+)?(?:di\s+|della\s+)?)?prelazione(?:\s+.*)?",
        r"\b42/2004\b|\bbene\s+culturale\b|\bbeni\s+culturali\b|\bministero\s+della\s+cultura\b|\bsoprintendenz\w+\b",
        "Provvedimento di prelazione sul bene culturale",
        "titolo del provvedimento e acquisto in via di prelazione del bene culturale (artt. 61 e 62 D.Lgs. 42/2004)",
        fonte="estesa_pubblico_beni_alienazione",
    ),
)

_ESPROPRIAZIONE = (
    _amministrazione(
        "pub_dichiarazione_pubblica_utilita",
        r"(?:(?:provvedimento|decreto|atto)\s+di\s+)?dichiarazione\s+di\s+pubblica\s+utilit[aà](?:\s+.*)?",
        r"\b12\b|\b327/2001\b|\bespropri\w+\b|\bopera\s+pubblica\b|\bditta\s+catastale\b|\bapprovazione\s+del\s+progetto\b",
        "Dichiarazione di pubblica utilità",
        "titolo del provvedimento e approvazione del progetto dell'opera pubblica (art. 12 D.P.R. 327/2001)",
        fonte="estesa_pubblico_espropri_pubblica_utilita",
    ),
    _amministrazione(
        "pub_indennita_provvisoria_esproprio",
        r"(?:determinazione|decreto|offerta|comunicazione)\s+(?:dell.?\s*|di\s+)?indennit[aà]\s+(?:provvisoria(?:\s+di\s+espropri(?:o|azione))?|di\s+espropri(?:o|azione)(?:\s+provvisoria)?)(?:\s+.*)?",
        r"\b2[02]\b|\b327/2001\b|\bespropri\w+\b|\bcondivision\w+\b",
        "Determinazione dell'indennità provvisoria di espropriazione",
        "titolo dell'atto e misura dell'indennità offerta al proprietario (art. 20 D.P.R. 327/2001)",
        fonte="estesa_pubblico_espropri_indennita",
    ),
    _amministrazione(
        "pub_decreto_occupazione_urgenza",
        r"decreto\s+di\s+occupazione(?:\s+d.?\s*urgenza|\s+anticipata|\s+temporanea)?(?:\s+.*)?",
        r"\b22[\s-]*bis\b|\b49\b|\b327/2001\b|\bimmissione\s+in\s+possesso\b|\bstato\s+di\s+consistenza\b|\bespropri\w+\b|\bindennit[aà]\b|\boccup\w+\b",
        "Decreto di occupazione d'urgenza",
        "titolo del decreto e immissione in possesso preordinata all'esproprio (art. 22-bis D.P.R. 327/2001)",
        fonte="estesa_pubblico_espropri_occupazione", tipo=TipoDocumento.DECRETO,
    ),
    _amministrazione(
        "pub_decreto_esproprio",
        r"decreto\s+(?:definitivo\s+)?di\s+espropri(?:o|azione)(?:\s+.*)?|decreto\s+di\s+asservimento(?:\s+.*)?",
        r"\b2[3-5]\b|\b327/2001\b|\bpassaggio\s+del\s+diritto\s+di\s+propriet[aà]\b|\bespropri\w+\b|\bindennit[aà]\b",
        "Decreto di esproprio",
        "titolo del decreto e passaggio del diritto di proprietà all'espropriante (art. 23 D.P.R. 327/2001)",
        fonte="estesa_pubblico_espropri_decreto", tipo=TipoDocumento.DECRETO,
    ),
    _amministrazione(
        "pub_acquisizione_sanante",
        r"(?:provvedimento|decreto|determinazione|delibera(?:zione)?)\s+di\s+acquisizione\s+(?:sanante|ex\s+art\.?\s*42[\s-]*bis)(?:\s+.*)?|acquisizione\s+sanante(?:\s+.*)?",
        r"\b42[\s-]*bis\b|\butilizzazione\s+senza\s+titolo\b|\b327/2001\b|\bpregiudizio\s+(?:patrimoniale|non\s+patrimoniale)\b",
        "Provvedimento di acquisizione sanante",
        "titolo del provvedimento e utilizzazione senza titolo del bene (art. 42-bis D.P.R. 327/2001)",
        fonte="estesa_pubblico_espropri_acquisizione_sanante",
    ),
)

_PUBBLICO_IMPIEGO = (
    _amministrazione(
        "pub_bando_concorso",
        r"bando\s+di\s+(?:concorso|selezione)(?:\s+.*)?|avviso\s+(?:pubblico\s+)?di\s+(?:selezione|concorso)(?:\s+.*)?",
        r"\b487/1994\b|\b165/2001\b|\bportale\s+(?:unico\s+del\s+reclutamento|inpa)\b|\bposti\b|\bcandidat\w+\b|\brequisiti\s+di\s+ammissione\b",
        "Bando di concorso pubblico",
        "titolo del bando, posti messi a concorso e requisiti (art. 3 D.P.R. 487/1994; art. 35 D.Lgs. 165/2001)",
        fonte="estesa_pubblico_dpr_487_1994_bando",
    ),
    _istanza(
        "pub_domanda_partecipazione_concorso",
        r"domanda\s+di\s+(?:partecipazione|ammissione)\s+(?:al\s+concorso|alla\s+selezione|al\s+bando)(?:\s+.*)?",
        r"\bconcorso\b|\bselezione\b|\bbando\b|\brequisiti\b",
        "Domanda di partecipazione al concorso",
        "titolo della domanda e requisiti richiesti dal bando (art. 3 D.P.R. 487/1994)",
        fonte="estesa_pubblico_dpr_487_1994_bando",
    ),
    _amministrazione(
        "pub_graduatoria_concorso",
        r"graduatoria(?:\s+(?:finale|definitiva|provvisoria|di\s+merito|di\s+concorso))?(?:\s+.*)?|(?:approvazione|decreto\s+di\s+approvazione)\s+(?:della\s+)?graduatoria(?:\s+.*)?",
        r"\bconcorso\b|\bconcorsi\b|\bvincitor\w+\b|\bidone\w+\b|\bselezione\s+pubblica\b",
        "Graduatoria di concorso pubblico",
        "titolo della graduatoria e vincitori e idonei del concorso (art. 35 D.Lgs. 165/2001)",
        fonte="estesa_pubblico_d_lgs_165_2001_reclutamento",
    ),
)

_CORTE_DEI_CONTI = (
    _amministrazione(
        "pub_denuncia_danno_erariale",
        r"denuncia\s+(?:di\s+)?(?:danno\s+erariale|danno\s+all.?\s*erario|ex\s+art\.?\s*52)(?:\s+.*)?|segnalazione\s+di\s+danno\s+erariale(?:\s+.*)?",
        r"\b52\b|" + _CORTE_CONTI,
        "Denuncia di danno erariale",
        "titolo della denuncia e fatti che possono dar luogo a responsabilità erariale (art. 52 c.g.c.)",
        fonte="estesa_pubblico_cgc_denuncia", section="comunicazioni",
    ),
    regola(
        "pub_invito_dedurre",
        r"invito\s+a\s+(?:fornire\s+)?dedurre(?:\s+.*)?|invito\s+a\s+fornire\s+deduzioni(?:\s+.*)?",
        r"\b67\b|\baudizione\s+personale\b|" + _CORTE_CONTI,
        "Invito a dedurre",
        role="atto_ufficio", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO, fonte="estesa_pubblico_cgc_invito_dedurre",
        deposit_role="fuori_busta", deposit_candidate=False,
        evidence="titolo dell'invito e contestazione del danno da parte della Procura contabile (art. 67 c.g.c.)",
    ),
    _atto(
        "pub_deduzioni_invito_dedurre",
        r"deduzioni(?:\s+difensive)?\s+(?:all.?\s*|in\s+risposta\s+all.?\s*|sull.?\s*)invito\s+a\s+dedurre(?:\s+.*)?|deduzioni\s+(?:difensive\s+)?ex\s+art\.?\s*67(?:\s+.*)?|deduzioni\s+difensive(?:\s+.*)?",
        r"\binvito\s+a\s+dedurre\b|" + _CORTE_CONTI,
        "Deduzioni all'invito a dedurre",
        "titolo dell'atto e difese del presunto responsabile prima della citazione (art. 67 c.g.c.)",
        fonte="estesa_pubblico_cgc_invito_dedurre", role="atto_difensivo", tipo=TipoDocumento.MEMORIA,
    ),
    _atto(
        "pub_citazione_responsabilita_erariale",
        r"atto\s+di\s+citazione(?:\s+.*)?|citazione\s+in\s+giudizio(?:\s+.*)?",
        r"\bprocura\s+regionale\b|\bdanno\s+erariale\b|\bcorte\s+dei\s+conti\b|\bsezione\s+giurisdizionale\s+(?:regionale|per\s+la\s+regione)\b",
        "Atto di citazione per responsabilità erariale",
        "titolo dell'atto e danno erariale contestato dal pubblico ministero contabile (art. 86 c.g.c.)",
        fonte="estesa_pubblico_cgc_citazione", tipo=TipoDocumento.CITAZIONE,
    ),
    _atto(
        "pub_appello_contabile",
        r"(?:atto\s+di\s+)?appello(?:\s+.*)?",
        r"\bsezion\w+\s+giurisdizional\w+\s+central\w+\b|\bsezione\s+giurisdizionale\s+d.?\s*appello\b|\bcodice\s+di\s+giustizia\s+contabile\b|\bcorte\s+dei\s+conti\b",
        "Appello nel giudizio contabile",
        "titolo dell'appello e sentenza della Corte dei conti impugnata (artt. 177 e 178 c.g.c.)",
        fonte="estesa_pubblico_cgc_impugnazioni",
    ),
    _documento(
        "pub_conto_giudiziale",
        r"conto\s+(?:giudiziale|della\s+gestione)(?:\s+.*)?|conto\s+dell.?\s*agente\s+contabile(?:\s+.*)?|conto\s+(?:del\s+tesoriere|dell.?\s*economo|del\s+consegnatario)(?:\s+.*)?",
        r"\b13[7-9]\b|\bagente\s+contabile\b|\bcorte\s+dei\s+conti\b|\bparificazion\w+\b|\bdiscarico\b|\bconsegnatari\w*\b|\btesorier\w+\b|\beconomo\b",
        "Conto giudiziale dell'agente contabile",
        "titolo del conto e gestione dell'agente contabile sottoposta al giudizio (artt. 137-139 c.g.c.)",
        fonte="estesa_pubblico_cgc_conto_giudiziale", role="documento_economico",
    ),
)

_ENTI_LOCALI = (
    _amministrazione(
        "pub_ordinanza_contingibile_urgente",
        r"ordinanza(?:\s+(?:sindacale|del\s+sindaco|presidenziale|regionale))?" + _NUMERO + r"\s+contingibile\s+e\s+urgente(?:\s+.*)?|ordinanza\s+(?:sindacale\s+)?(?:ex\s+)?artt?\.?\s*(?:50|54)(?:,?\s*comma\s*[45])?(?:\s+.*)?",
        r"\b267/2000\b|\b5[04]\b|\bcontingibil\w+\b|\bincolumit[aà]\s+pubblica\b|\bsicurezza\s+urbana\b|\bsindaco\b",
        "Ordinanza contingibile e urgente",
        "titolo dell'ordinanza e pericolo per l'incolumità pubblica o l'igiene (artt. 50, comma 5, e 54, comma 4, D.Lgs. 267/2000)",
        fonte="estesa_pubblico_tuel_ordinanze", tipo=TipoDocumento.ORDINANZA,
    ),
)

REGOLE: tuple[RegolaTitolo, ...] = (
    _PROCESSO_AMMINISTRATIVO + _PROCEDIMENTO + _APPALTI_PUBBLICI + _EDILIZIA + _AMBIENTE_E_PAESAGGIO
    + _ESPROPRIAZIONE + _PUBBLICO_IMPIEGO + _CORTE_DEI_CONTI + _ENTI_LOCALI
)

__all__ = ["FONTI", "REGOLE"]
