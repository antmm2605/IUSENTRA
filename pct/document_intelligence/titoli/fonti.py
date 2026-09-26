"""Fonti normative delle regole d'identità dal titolo, verificate su Normattiva.

Ogni voce riporta l'articolo che definisce l'atto e la data in cui il testo
vigente è stato consultato. Le fonti già registrate nel catalogo dei modelli
(`pct.template_atti_legal_sources`) non vengono duplicate: le regole le
richiamano per identificativo.
"""

from __future__ import annotations

from typing import Any

_VERIFICA = "testo vigente consultato su Normattiva il 14/09/2026"
_NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"
_CPC = "regio.decreto:1940-10-28;1443~art"
_CC = "regio.decreto:1942-03-16;262~art"
_CPP = "decreto.del.presidente.della.repubblica:1988-09-22;447~art"


def _fonte(label: str, urn: str, *, tipo: str = "normativa") -> dict[str, Any]:
    return {"label": label, "official_url": _NORMATTIVA + urn, "verification_status": _VERIFICA, "source_type": tipo}


FONTI_TITOLI: dict[str, dict[str, Any]] = {
    # Procedura civile
    "normattiva_cpc_rito_lavoro": _fonte("c.p.c., artt. 409-420: rito del lavoro, ricorso e memoria difensiva", _CPC + "414"),
    "normattiva_cpc_famiglia_473_bis": _fonte("c.p.c., artt. 473-bis ss.: procedimento in materia di persone, minorenni e famiglie", _CPC + "473bis.12"),
    "normattiva_cpc_impugnazioni": _fonte("c.p.c., artt. 342 e 360: atto di appello e ricorso per cassazione", _CPC + "342"),
    "normattiva_cpc_opposizione_decreto_ingiuntivo": _fonte("c.p.c., art. 645: opposizione a decreto ingiuntivo", _CPC + "645"),
    "normattiva_cpc_opposizioni_esecutive": _fonte("c.p.c., artt. 615 e 617: opposizione all'esecuzione e agli atti esecutivi", _CPC + "615"),
    "normattiva_cpc_vendita_forzata": _fonte("c.p.c., artt. 490, 567, 586 e 596: avviso e istanza di vendita, decreto di trasferimento, distribuzione", _CPC + "567"),
    "normattiva_cpc_intervento_esecuzione": _fonte("c.p.c., art. 499: intervento dei creditori nell'esecuzione", _CPC + "499"),
    "normattiva_cpc_sfratto": _fonte("c.p.c., artt. 657 e 658: intimazione di licenza e di sfratto", _CPC + "658"),
    "normattiva_cpc_cautelari": _fonte("c.p.c., artt. 669-terdecies, 671 e 700: reclamo, sequestro e provvedimenti d'urgenza", _CPC + "700"),
    "normattiva_cpc_correzione_errore_materiale": _fonte("c.p.c., art. 287: correzione delle omissioni o degli errori materiali", _CPC + "287"),
    "normattiva_cpc_udienza_note_scritte": _fonte("c.p.c., art. 127-ter: deposito di note scritte in sostituzione dell'udienza", _CPC + "127ter"),
    # Codice civile
    "normattiva_cc_condominio": _fonte("c.c., artt. 1136-1138: assemblea, impugnazione delle deliberazioni e regolamento di condominio", _CC + "1136"),
    "normattiva_cc_successioni": _fonte("c.c., artt. 484, 519, 601 e 620: accettazione beneficiata, rinuncia, testamento e pubblicazione", _CC + "519"),
    "normattiva_cc_amministrazione_sostegno": _fonte("c.c., artt. 404 e 407: amministrazione di sostegno e procedimento", _CC + "404"),
    "normattiva_cc_locazione": _fonte("c.c., artt. 1571 e 1596: contratto di locazione e disdetta", _CC + "1571"),
    "normattiva_cc_contratto": _fonte("c.c., art. 1321: nozione di contratto", _CC + "1321"),
    # Procedura penale
    "normattiva_cpp_indagini_preliminari": _fonte("c.p.p., artt. 369, 408, 410 e 415-bis: informazione di garanzia, archiviazione e conclusione delle indagini", _CPP + "415bis"),
    "normattiva_cpp_esercizio_azione_penale": _fonte("c.p.p., artt. 416, 429, 450 e 552: richiesta di rinvio a giudizio, decreto che dispone il giudizio, citazione diretta", _CPP + "552"),
    "normattiva_cpp_procedimento_per_decreto": _fonte("c.p.p., artt. 460 e 461: decreto penale di condanna e opposizione", _CPP + "460"),
    "normattiva_cpp_difensore": _fonte("c.p.p., artt. 96 e 121: nomina del difensore di fiducia e memorie difensive", _CPP + "96"),
    "normattiva_cpp_notizia_di_reato": _fonte("c.p.p., artt. 333 e 336: denuncia e querela", _CPP + "336"),
    "normattiva_cpp_riesame": _fonte("c.p.p., art. 309: richiesta di riesame delle misure cautelari", _CPP + "309"),
    "normattiva_cpp_lista_testi": _fonte("c.p.p., art. 468: lista dei testimoni, periti e consulenti", _CPP + "468"),
    "normattiva_cpp_impugnazioni": _fonte("c.p.p., artt. 581 e 606: atto di appello e ricorso per cassazione", _CPP + "581"),
    "normattiva_cpp_sequestro_identificazione": _fonte("c.p.p., artt. 161, 253 e 354: elezione di domicilio, sequestro e accertamenti urgenti", _CPP + "253"),
    "normattiva_dpr_313_2002_casellario": _fonte("D.P.R. 313/2002, artt. 24 e 27: certificati del casellario giudiziale e dei carichi pendenti", "decreto.del.presidente.della.repubblica:2002-11-14;313~art24"),
    # Amministrativo
    "normattiva_cpc_citazione": _fonte("c.p.c., art. 163: contenuto dell'atto di citazione", _CPC + "163"),
    "normattiva_cpa_ottemperanza": _fonte("c.p.a., artt. 112 e 114: giudizio di ottemperanza e procedimento", "decreto.legislativo:2010-07-02;104~art114"),
    "normattiva_cpa_ricorso": _fonte("c.p.a., artt. 40, 43, 55 e 100: ricorso, motivi aggiunti, domanda cautelare e appello", "decreto.legislativo:2010-07-02;104~art40"),
    "normattiva_dpr_1199_1971_ricorso_straordinario": _fonte("D.P.R. 1199/1971, art. 8: ricorso straordinario al Presidente della Repubblica", "decreto.del.presidente.della.repubblica:1971-11-24;1199~art8"),
    "normattiva_legge_241_1990_procedimento": _fonte("L. 241/1990, artt. 3, 10-bis e 22: motivazione, preavviso di rigetto e accesso ai documenti", "legge:1990-08-07;241~art22"),
    "normattiva_d_lgs_33_2013_accesso_civico": _fonte("D.Lgs. 33/2013, art. 5: accesso civico", "decreto.legislativo:2013-03-14;33~art5"),
    "normattiva_legge_689_1981_sanzioni": _fonte("L. 689/1981, art. 18: ordinanza-ingiunzione", "legge:1981-11-24;689~art18"),
    # Tributario e riscossione
    "normattiva_dpr_600_1973_accertamento": _fonte("D.P.R. 600/1973, art. 42: avviso di accertamento", "decreto.del.presidente.della.repubblica:1973-09-29;600~art42"),
    "normattiva_dpr_602_1973_riscossione": _fonte("D.P.R. 602/1973, artt. 25, 50 e 86: cartella di pagamento, intimazione e fermo amministrativo", "decreto.del.presidente.della.repubblica:1973-09-29;602~art25"),
    "normattiva_d_lgs_218_1997_adesione": _fonte("D.Lgs. 218/1997, art. 6: istanza di accertamento con adesione", "decreto.legislativo:1997-06-19;218~art6"),
    # Gli artt. 18-23 del D.Lgs. 546/1992 sono abrogati dal D.Lgs. 175/2024 (Testo unico della giustizia tributaria): la fonte è il testo unico.
    "normattiva_d_lgs_546_1992_controdeduzioni": _fonte("D.Lgs. 175/2024 (Testo unico giustizia tributaria), artt. 64 e 69: ricorso e costituzione della parte resistente con controdeduzioni (ex artt. 18 e 23 D.Lgs. 546/1992)", "decreto.legislativo:2024-11-14;175~art69"),
    "normattiva_dpr_322_1998_dichiarazioni": _fonte("D.P.R. 322/1998, artt. 1 e 4: dichiarazione dei redditi e certificazione unica", "decreto.del.presidente.della.repubblica:1998-07-22;322~art4"),
    "normattiva_dpcm_159_2013_isee": _fonte("D.P.C.M. 159/2013, art. 10: dichiarazione sostitutiva unica e attestazione ISEE", "decreto.del.presidente.del.consiglio.dei.ministri:2013-12-05;159~art10"),
    # Lavoro
    "normattiva_legge_4_1953_prospetto_paga": _fonte("L. 4/1953, art. 1: prospetto di paga", "legge:1953-01-05;4~art1"),
    "normattiva_d_lgs_152_1997_informazioni_lavoro": _fonte("D.Lgs. 152/1997, art. 1: informazioni sul contratto di lavoro", "decreto.legislativo:1997-05-26;152~art1"),
    "normattiva_l_300_1970_art_7_disciplinare": _fonte("L. 300/1970, art. 7: contestazione disciplinare", "legge:1970-05-20;300~art7"),
    "normattiva_l_604_1966_art_2_6": _fonte("L. 604/1966, artt. 2 e 6: comunicazione e impugnazione del licenziamento", "legge:1966-07-15;604~art2"),
    "normattiva_d_lgs_150_2011_art_6_opposizione": _fonte("D.Lgs. 150/2011, art. 6: opposizione a ordinanza-ingiunzione", "decreto.legislativo:2011-09-01;150~art6"),
    # Famiglia e successioni
    "normattiva_d_lgs_346_1990_successioni": _fonte("D.Lgs. 346/1990, art. 28: dichiarazione di successione", "decreto.legislativo:1990-10-31;346~art28"),
    "normattiva_dl_132_2014_art_6_famiglia": _fonte("D.L. 132/2014, art. 6: negoziazione assistita per separazione e divorzio", "decreto.legislativo:2014-09-12;132~art6"),
    # Studio e obblighi professionali
    "normattiva_d_lgs_231_2007_adeguata_verifica": _fonte("D.Lgs. 231/2007, art. 18: adeguata verifica della clientela", "decreto.legislativo:2007-11-21;231~art18"),
    "normattiva_d_lgs_28_2010_art_11_proposta": _fonte("D.Lgs. 28/2010, art. 11: proposta del mediatore e verbale di accordo", "decreto.legislativo:2010-03-04;28~art11"),
}

__all__ = ["FONTI_TITOLI"]
