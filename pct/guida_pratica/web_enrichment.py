"""Arricchimento ufficiale e non bloccante della Guida Pratica.

Il modulo applica a tutte le schede, già curate o generate, lo stesso livello
di presidio che viene usato per i nuovi materiali dell'utente: fonti ufficiali,
canali ADR/specialistici, controllo deposito separato e note operative per Lex.
"""

from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

ENRICHMENT_VERSION = "2026-06-06.web-fonti-set30-32-v3"
VERIFIED_ON = "2026-06-06"

SOURCE_LIBRARY: dict[str, dict[str, str]] = {
    "pst_download": {
        "ente": "Portale Servizi Telematici - Ministero della Giustizia",
        "titolo": "Download file ufficiali del Processo Civile Telematico",
        "url": "https://pst.giustizia.it/PST/it/download.page",
        "ambito": "XSD SICI, XSD Giudici di pace, XSD Cassazione e file ufficiali PCT",
    },
    "pst_xsd_sici_2024": {
        "ente": "Portale Servizi Telematici - Ministero della Giustizia",
        "titolo": "XSD SICI e codici oggetto migrazione famiglia - 23 gennaio 2024",
        "url": "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3094",
        "ambito": "schemi XSD SICI, tipi-base.xsd e codici oggetto PST",
    },
    "pst_specifiche_2014": {
        "ente": "Portale Servizi Telematici - Ministero della Giustizia",
        "titolo": "Provvedimento 16 aprile 2014 - specifiche tecniche ex art. 34 D.M. 44/2011",
        "url": "https://servizipst.giustizia.it/PST/it/pst_26_1.wp?contentId=DOC416&previousPage=pst_1_0",
        "ambito": "regole tecniche deposito telematico e rinvio ai file XSD ufficiali",
    },
    "normattiva_cpc": {
        "ente": "Normattiva",
        "titolo": "R.D. 28 ottobre 1940, n. 1443 - Codice di procedura civile",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=040U1443&atto.dataPubblicazioneGazzetta=1940-10-28&tipoDettaglio=multivigenza",
        "ambito": "rito civile, cautelari, opposizioni, esecuzioni, famiglia, volontaria giurisdizione e impugnazioni",
    },
    "normattiva_cc": {
        "ente": "Normattiva",
        "titolo": "R.D. 16 marzo 1942, n. 262 - Codice civile",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=042U0262&atto.dataPubblicazioneGazzetta=1942-04-04&tipoDettaglio=multivigenza",
        "ambito": "famiglia, successioni, diritti reali, contratti, responsabilità, società e persone",
    },
    "normattiva_mediazione": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 4 marzo 2010, n. 28, art. 5 - mediazione civile e commerciale",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2010;28~art5=",
        "ambito": "condizione di procedibilità e materie soggette a mediazione",
    },
    "normattiva_negoziazione_assistita": {
        "ente": "Normattiva",
        "titolo": "D.L. 12 settembre 2014, n. 132, art. 3 - negoziazione assistita",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legge:2014;132~art3=",
        "ambito": "risarcimento da circolazione e domande di pagamento entro soglia, fuori dai casi di mediazione",
    },
    "normattiva_riforma_cartabia": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 10 ottobre 2022, n. 149 - riforma del processo civile",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=22G00158&atto.dataPubblicazioneGazzetta=2022-10-17",
        "ambito": "rito civile, famiglia, esecuzione forzata, mediazione, negoziazione assistita e arbitrato",
    },
    "normattiva_614bis": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 10 ottobre 2022, n. 149 - modifica art. 614-bis c.p.c.",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.articolo.numero=3&atto.articolo.sottoArticolo=1&atto.articolo.tipoArticolo=0&atto.codiceRedazionale=22G00158&atto.dataPubblicazioneGazzetta=2022-10-17",
        "ambito": "misure di coercizione indiretta e obblighi diversi dal pagamento di somme",
    },
    "normattiva_cpi": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 10 febbraio 2005, n. 30 - Codice della proprietà industriale",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=005G0055&atto.dataPubblicazioneGazzetta=2005-03-04&tipoDettaglio=vigente",
        "ambito": "marchi, brevetti, disegni, modelli, inibitoria, descrizione e sequestro CPI",
    },
    "normattiva_sanitaria": {
        "ente": "Normattiva",
        "titolo": "Legge 8 marzo 2017, n. 24 - responsabilità sanitaria",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2017-03-08;24~art10-com2=",
        "ambito": "responsabilità sanitaria, assicurazione, rivalsa e regresso",
    },
    "normattiva_consumo": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 6 settembre 2005, n. 206 - Codice del consumo",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2005;206!vig=",
        "ambito": "garanzia legale, difetto di conformità, clausole e tutele consumeristiche",
    },
    "normattiva_lavoro_604": {
        "ente": "Normattiva",
        "titolo": "Legge 15 luglio 1966, n. 604 - licenziamenti individuali",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=066U0604&atto.dataPubblicazioneGazzetta=1966-08-06",
        "ambito": "licenziamento, motivazione, impugnazione e giustificato motivo",
    },
    "normattiva_lavoro_300": {
        "ente": "Normattiva",
        "titolo": "Legge 20 maggio 1970, n. 300 - Statuto dei lavoratori",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1970;300~art35-com=",
        "ambito": "tutele del lavoratore e rinvii alla disciplina reintegratoria/organizzativa",
    },
    "banca_italia_abf": {
        "ente": "Banca d'Italia",
        "titolo": "Arbitro Bancario Finanziario",
        "url": "https://www.bancaditalia.it/compiti/tutela-educazione/abf/index.html",
        "ambito": "ADR per controversie bancarie e finanziarie con intermediari vigilati",
    },
    "consob_acf": {
        "ente": "CONSOB",
        "titolo": "Arbitro per le Controversie Finanziarie",
        "url": "https://www.consob.it/web/area-pubblica/arbitro-per-le-controversie-finanziarie",
        "ambito": "ADR per controversie finanziarie tra investitori e intermediari",
    },
    "ivass_arbitro_assicurativo": {
        "ente": "IVASS",
        "titolo": "Arbitro Assicurativo",
        "url": "https://www.ivass.it/consumatori/aas/index.html",
        "ambito": "ricorso assicurativo dopo reclamo all'impresa o all'intermediario",
    },
    "agcom_conciliaweb": {
        "ente": "AGCOM",
        "titolo": "ConciliaWeb",
        "url": "https://www.agcom.it/agcom-per-te/i-miei-diritti/contenzioso-tra-utenti-e-operatori",
        "ambito": "conciliazione e definizione controversie utenti/operatori comunicazioni elettroniche",
    },
    "ministero_patrocinio_spese_stato": {
        "ente": "Ministero della Giustizia",
        "titolo": "Patrocinio a spese dello Stato nei giudizi civili e amministrativi",
        "url": "https://www.giustizia.it/giustizia/page/it/patrocinio_a_spese_dello_stato_nei_giudizi_civili_e_amministrativi",
        "ambito": "verifica facoltativa dei presupposti di ammissione al patrocinio a spese dello Stato",
    },
    "ministero_pagopa_pst": {
        "ente": "Ministero della Giustizia",
        "titolo": "Contributo unificato e pagamenti telematici tramite PagoPA",
        "url": "https://www.giustizia.it/giustizia/it/mg_1_40_0.page?contentId=IGC408325&facetNode_2=0_23",
        "ambito": "pagamento telematico contributo unificato, diritti e spese nei procedimenti civili telematici",
    },
    "pst_servizi_pagopa": {
        "ente": "Portale Servizi Telematici - Ministero della Giustizia",
        "titolo": "Servizi telematici e pagamenti online tramite pagoPA",
        "url": "https://pst.giustizia.it/PST/it/services.page",
        "ambito": "punti di accesso, pagamenti online, consultazioni registri e servizi PCT",
    },
    "agenzia_entrate_tassazione_atti_giudiziari": {
        "ente": "Agenzia delle Entrate",
        "titolo": "Calcolo degli importi per la tassazione degli atti giudiziari",
        "url": "https://www1.agenziaentrate.gov.it/servizi/tassazioneattigiudiziari/registrazione.htm?passo=0",
        "ambito": "registrazione e tassazione di provvedimenti giudiziari",
    },
    "inail_infortunio_malattia_professionale": {
        "ente": "INAIL",
        "titolo": "Denunce di infortunio e malattia professionale",
        "url": "https://www.inail.it/portale/assicurazione/it/Datore-di-Lavoro/Impresa-con-dipendenti-industria-artigianato-terziario-altre-attivita/denunce-infortuni-e-malattie-professionali-impresa-con-dipendenti/denuncia-malattia-professionale-impresa-con-dipendenti.html",
        "ambito": "denuncia di infortunio, malattia professionale e presidi amministrativi collegati al lavoro",
    },
    "inps_ricorsi_amministrativi": {
        "ente": "INPS",
        "titolo": "Ricorsi amministrativi",
        "url": "https://www.inps.it/it/it/dettaglio-scheda.it.schede-servizio-strumento.schede-servizi.ricorsi-amministrativi.html",
        "ambito": "ricorsi amministrativi previdenziali e assistenziali prima o accanto al contenzioso",
    },
    "registro_imprese": {
        "ente": "Camera di Commercio",
        "titolo": "Registro delle imprese e adempimenti societari",
        "url": "https://www.vr.camcom.gov.it/content/il-registro-imprese",
        "ambito": "visure, assetti societari, scioglimento, liquidazione e pubblicità legale dell'impresa",
    },
    "tribunale_minorenni_competenza": {
        "ente": "Ministero della Giustizia - Tribunale per i Minorenni",
        "titolo": "Competenza per materia del Tribunale per i Minorenni",
        "url": "https://tribmin-trento.giustizia.it/it/comp_per_materia.page",
        "ambito": "competenza civile minorile, volontaria giurisdizione, adozione e tutela dei minori",
    },
    "procura_negoziazione_famiglia": {
        "ente": "Ministero della Giustizia - Procura della Repubblica",
        "titolo": "Nulla osta e autorizzazioni per negoziazione assistita in materia di famiglia",
        "url": "https://procura-roma.giustizia.it/it/nulla_osta_separaz_divorzi.page",
        "ambito": "separazione, divorzio e modifiche consensuali con negoziazione assistita",
    },
    "pst_albo_ctu": {
        "ente": "Portale Servizi Telematici - Ministero della Giustizia",
        "titolo": "Portale albo CTU, periti ed elenco nazionale",
        "url": "https://pst.giustizia.it/PST/it/services.page",
        "ambito": "consultazione consulenti tecnici e periti, utile per CTU/ATP e cause tecniche",
    },
    "normattiva_tu_spese_giustizia": {
        "ente": "Normattiva",
        "titolo": "D.P.R. 30 maggio 2002, n. 115 - Testo unico spese di giustizia",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=002G0139&atto.dataPubblicazioneGazzetta=2002-06-15&tipoDettaglio=vigente",
        "ambito": "contributo unificato, spese di giustizia, patrocinio a spese dello Stato e prenotazioni a debito",
    },
    "normattiva_tu_bancario": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 1 settembre 1993, n. 385 - Testo unico bancario",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=093G0427&atto.dataPubblicazioneGazzetta=1993-09-30&tipoDettaglio=vigente",
        "ambito": "contratti bancari, mutui, credito, ABF e trasparenza bancaria",
    },
    "normattiva_tuf": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 24 febbraio 1998, n. 58 - Testo unico della finanza",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=098G0075&atto.dataPubblicazioneGazzetta=1998-03-26&tipoDettaglio=vigente",
        "ambito": "servizi di investimento, intermediari finanziari, obblighi informativi e ACF",
    },
    "normattiva_codice_assicurazioni": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 7 settembre 2005, n. 209 - Codice delle assicurazioni private",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=005G0233&atto.dataPubblicazioneGazzetta=2005-10-13&tipoDettaglio=vigente",
        "ambito": "contratti assicurativi, sinistri, azioni dirette e reclami assicurativi",
    },
    "normattiva_tu_inail": {
        "ente": "Normattiva",
        "titolo": "D.P.R. 30 giugno 1965, n. 1124 - Testo unico assicurazione infortuni sul lavoro",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=065U1124&atto.dataPubblicazioneGazzetta=1965-10-13&tipoDettaglio=vigente",
        "ambito": "infortuni sul lavoro, malattie professionali, denuncia e prestazioni INAIL",
    },
    "normattiva_codice_proprieta_industriale": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 10 febbraio 2005, n. 30 - Codice della proprietà industriale",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=005G0055&atto.dataPubblicazioneGazzetta=2005-03-04&tipoDettaglio=vigente",
        "ambito": "proprietà industriale, marchi, brevetti, disegni e modelli",
    },
    "normattiva_locazioni_392": {
        "ente": "Normattiva",
        "titolo": "Legge 27 luglio 1978, n. 392 - Disciplina delle locazioni di immobili urbani",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1978;392!vig=",
        "ambito": "locazioni urbane, uso diverso, prelazione, indennità di avviamento e rilascio",
    },
    "normattiva_locazioni_431": {
        "ente": "Normattiva",
        "titolo": "Legge 9 dicembre 1998, n. 431 - Locazioni abitative",
        "url": "https://www.normattiva.it/eli/id/1998/12/15/098G0483/CONSOLIDATED",
        "ambito": "locazioni abitative, durata 4+4, canone concordato, rilascio e nullità",
    },
    "enac_reg_261_2004": {
        "ente": "ENAC",
        "titolo": "Regolamento (CE) n. 261/2004 - diritti dei passeggeri aerei",
        "url": "https://www.enac.gov.it/passeggeri/diritti-dei-passeggeri/regolamentoce261_2004/",
        "ambito": "negato imbarco, cancellazione, ritardo prolungato, reclami ENAC e assistenza passeggeri",
    },
    "normattiva_montreal_2004": {
        "ente": "Normattiva",
        "titolo": "Legge 10 gennaio 2004, n. 12 - Convenzione di Montreal sul trasporto aereo internazionale",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2004;12!vig=",
        "ambito": "responsabilità del vettore aereo, bagagli, ritardi e danni nel trasporto internazionale",
    },
    "normattiva_factoring_52_1991": {
        "ente": "Normattiva",
        "titolo": "Legge 21 febbraio 1991, n. 52 - cessione dei crediti d'impresa",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1991;52!vig=",
        "ambito": "factoring, cessione crediti d'impresa, opponibilità e rapporti cedente-cessionario-debitore",
    },
    "normattiva_franchising_129_2004": {
        "ente": "Normattiva",
        "titolo": "Legge 6 maggio 2004, n. 129 - affiliazione commerciale",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2004;129!vig=",
        "ambito": "franchising, informativa precontrattuale, forma e contenuto del contratto",
    },
    "normattiva_subfornitura_192_1998": {
        "ente": "Normattiva",
        "titolo": "Legge 18 giugno 1998, n. 192 - subfornitura e abuso di dipendenza economica",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1998;192!vig=",
        "ambito": "subfornitura, termini di pagamento, abuso di dipendenza economica e tutela concorrenziale",
    },
    "normattiva_sicurezza_81_2008": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 9 aprile 2008, n. 81 - salute e sicurezza sul lavoro",
        "url": "https://www.normattiva.it/eli/stato/DECRETO_LEGISLATIVO/2008/04/09/81/CONSOLIDATED",
        "ambito": "sicurezza lavoro, amianto, DVR, obblighi datoriali e responsabilità prevenzionistica",
    },
    "ministero_lavoro_dlgs_81_2008": {
        "ente": "Ministero del Lavoro",
        "titolo": "D.Lgs. 81/2008 - testo coordinato sicurezza lavoro",
        "url": "https://www.lavoro.gov.it/documenti-e-norme/normative/Documents/2008/20080409_Dlgs_81.pdf",
        "ambito": "consultazione tecnica del testo sicurezza lavoro e allegati operativi",
    },
    "normattiva_turismo_62_2018": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 21 maggio 2018, n. 62 - pacchetti turistici e servizi turistici collegati",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2018;62!vig=",
        "ambito": "pacchetti turistici, recesso, responsabilità organizzatore/venditore e tutela viaggiatore",
    },
    "normattiva_farmaci_219_2006": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 24 aprile 2006, n. 219 - medicinali per uso umano",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2006;219!vig=",
        "ambito": "farmaci, autorizzazioni, farmacovigilanza e responsabilità collegate al prodotto medicinale",
    },
    "normattiva_whistleblowing_24_2023": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 10 marzo 2023, n. 24 - protezione delle persone segnalanti",
        "url": "https://www.normattiva.it/eli/stato/DECRETO_LEGISLATIVO/2023/03/10/24/CONSOLIDATED",
        "ambito": "whistleblowing, canali interni/esterni, misure di protezione, ritorsioni e oneri organizzativi",
    },
    "anac_whistleblowing": {
        "ente": "ANAC",
        "titolo": "Linee guida ANAC in materia di whistleblowing - D.Lgs. 24/2023",
        "url": "https://www.anticorruzione.it/documents/91439/c2669dcd-da87-65e4-0e76-4a605730921c",
        "ambito": "D.Lgs. 24/2023, procedure di segnalazione, canali interni, canale esterno ANAC e presidi organizzativi",
    },
    "normattiva_l_68_1999": {
        "ente": "Normattiva",
        "titolo": "Legge 12 marzo 1999, n. 68 - diritto al lavoro dei disabili",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1999;68!vig=",
        "ambito": "collocamento mirato, quote di riserva, prospetti informativi e sanzioni",
    },
    "normattiva_d_lgs_151_2001": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 26 marzo 2001, n. 151 - maternità, paternità e congedi",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2001;151!vig=",
        "ambito": "congedo parentale, maternità, paternità, permessi e tutele del lavoratore",
    },
    "inps_congedi_parentali": {
        "ente": "INPS",
        "titolo": "Congedi parentali - scheda INPS",
        "url": "https://www.inps.it/it/it/dati-e-bilanci/attivit--di-ricerca/collaborazioni-e-partnership/congedi-parentali.html",
        "ambito": "presidi previdenziali e amministrativi collegati ai congedi parentali",
    },
    "normattiva_dpr_380_2001": {
        "ente": "Normattiva",
        "titolo": "D.P.R. 6 giugno 2001, n. 380 - Testo unico edilizia",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:2001;380!vig=",
        "ambito": "permesso di costruire, SCIA edilizia, abusi, sanatoria e titoli edilizi",
    },
    "normattiva_d_lgs_36_2023": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 31 marzo 2023, n. 36 - Codice dei contratti pubblici",
        "url": "https://www.normattiva.it/eli/id/2023/03/31/23G00044/CONSOLIDATED",
        "ambito": "appalti pubblici, affidamenti, esecuzione, digitalizzazione, trasparenza e rimedi",
    },
    "anac_contratti_pubblici": {
        "ente": "ANAC",
        "titolo": "Contratti pubblici - attuazione D.Lgs. 36/2023 e BDNCP",
        "url": "https://www.anticorruzione.it/contratti-pubblici",
        "ambito": "piattaforme, BDNCP, pubblicità legale, FAQ e presidi ANAC sugli appalti",
    },
    "normattiva_d_lgs_59_2010": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 26 marzo 2010, n. 59 - servizi nel mercato interno",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2010;59!vig=",
        "ambito": "SCIA commerciale, servizi, autorizzazioni e controlli amministrativi",
    },
    "normattiva_codice_navigazione_327_1942": {
        "ente": "Normattiva",
        "titolo": "R.D. 30 marzo 1942, n. 327 - Codice della navigazione",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-30;327!vig=",
        "ambito": "concessioni demaniali marittime e lacuali, revoca, decadenza, beni demaniali e navigazione",
    },
    "normattiva_l_76_2016": {
        "ente": "Normattiva",
        "titolo": "Legge 20 maggio 2016, n. 76 - unioni civili e convivenze",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2016;76!vig=",
        "ambito": "unioni civili, convivenze di fatto, contratti di convivenza e rapporti personali/patrimoniali",
    },
    "normattiva_d_lgs_346_1990": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 31 ottobre 1990, n. 346 - imposta su successioni e donazioni",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:1990;346!vig=",
        "ambito": "successioni, donazioni, franchigie, aliquote e adempimenti fiscali",
    },
    "normattiva_l_160_2019_imu": {
        "ente": "Normattiva",
        "titolo": "Legge 27 dicembre 2019, n. 160 - disciplina IMU vigente",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2019;160!vig=",
        "ambito": "IMU, presupposto, soggetti passivi, base imponibile e termini",
    },
    "dipartimento_finanze_federalismo": {
        "ente": "MEF - Dipartimento delle Finanze",
        "titolo": "Portale del Federalismo Fiscale",
        "url": "https://www.portalefederalismofiscale.gov.it/",
        "ambito": "aliquote, delibere comunali, IMU, TARI e fiscalità locale",
    },
    "agenzia_entrate_isa": {
        "ente": "Agenzia delle Entrate",
        "titolo": "Indici sintetici di affidabilità fiscale",
        "url": "https://www1.agenziaentrate.gov.it/web_app_entrate/indici_sintetici_affidabilita.html",
        "ambito": "ISA, effetti premiali, accertamento e presidi dichiarativi",
    },
    "agenzia_entrate_riscossione_accertamento": {
        "ente": "Agenzia delle entrate-Riscossione",
        "titolo": "Accertamento esecutivo e avviso di addebito INPS",
        "url": "https://www.agenziaentrateriscossione.gov.it/it/Per-saperne-di-piu/documenti-della-riscossione/accertamento-esecutivo-e-avviso-di-addebito-inps/",
        "ambito": "atti impositivi esecutivi, ricorso, pagamento e affidamento alla riscossione",
    },
    "normattiva_dpr_600_1973": {
        "ente": "Normattiva",
        "titolo": "D.P.R. 29 settembre 1973, n. 600 - accertamento imposte sui redditi",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1973;600!vig=",
        "ambito": "accertamento redditi, redditometro, termini, avvisi e prove del contribuente",
    },
    "normattiva_dpr_633_1972": {
        "ente": "Normattiva",
        "titolo": "D.P.R. 26 ottobre 1972, n. 633 - IVA",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1972;633!vig=",
        "ambito": "IVA, accertamento, detrazione, liquidazione, rimborsi e sanzioni",
    },
    "normattiva_l_197_2022": {
        "ente": "Normattiva",
        "titolo": "Legge 29 dicembre 2022, n. 197 - bilancio 2023 e definizioni agevolate",
        "url": "https://www.normattiva.it/eli/stato/LEGGE/2022/12/29/197/CONSOLIDATED",
        "ambito": "definizione liti fiscali pendenti, tregua fiscale, rottamazione e misure tributarie collegate",
    },
    "normattiva_l_130_2022": {
        "ente": "Normattiva",
        "titolo": "Legge 31 agosto 2022, n. 130 - riforma della giustizia tributaria",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2022;130!vig=",
        "ambito": "giustizia tributaria, magistratura tributaria, prova, onere probatorio e definizione liti pendenti pregresse",
    },
    "normattiva_dpr_131_1986": {
        "ente": "Normattiva",
        "titolo": "D.P.R. 26 aprile 1986, n. 131 - Testo unico imposta di registro",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1986;131!vig=",
        "ambito": "imposta di registro, atti giudiziari, avvisi, liquidazione e registrazione",
    },
    "normattiva_l_147_2013_tari": {
        "ente": "Normattiva",
        "titolo": "Legge 27 dicembre 2013, n. 147 - IUC/TARI",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2013;147!vig=",
        "ambito": "TARI, presupposto, utenze, regolamenti comunali e termini locali",
    },
    "normattiva_tuir_917_1986": {
        "ente": "Normattiva",
        "titolo": "D.P.R. 22 dicembre 1986, n. 917 - TUIR",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1986;917!vig=",
        "ambito": "IRPEF, redditi, plusvalenze, base imponibile e accertamento",
    },
    "normattiva_d_lgs_14_2019": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 12 gennaio 2019, n. 14 - Codice della crisi d'impresa e dell'insolvenza",
        "url": "https://www.normattiva.it/eli/stato/DECRETO_LEGISLATIVO/2019/01/12/14/CONSOLIDATED",
        "ambito": "composizione negoziata, strumenti di regolazione della crisi, insolvenza e procedure concorsuali",
    },
    "unioncamere_composizione_negoziata": {
        "ente": "Unioncamere",
        "titolo": "Piattaforma nazionale composizione negoziata",
        "url": "https://composizionenegoziata.camcom.it/",
        "ambito": "accesso alla composizione negoziata, test pratico, istanza e gestione documentale",
    },
    "agcm_pratiche_scorrette": {
        "ente": "AGCM",
        "titolo": "Pratiche commerciali scorrette e pubblicità ingannevole/comparativa",
        "url": "https://www.agcm.it/competenze/tutela-del-consumatore/pratiche-commerciali-scorrette/",
        "ambito": "pratiche scorrette, pubblicità ingannevole, segnalazioni e poteri istruttori AGCM",
    },
    "uibm_marchi": {
        "ente": "UIBM - Ministero delle Imprese e del Made in Italy",
        "titolo": "Marchi d'impresa e marchio di fatto",
        "url": "https://uibm.mise.gov.it/index.php/it/?catid=223&id=2036051&option=com_content&view=article",
        "ambito": "marchio registrato, marchio di fatto, preuso, notorietà e ricerche UIBM",
    },
    "normattiva_l_241_1990": {
        "ente": "Normattiva",
        "titolo": "Legge 7 agosto 1990, n. 241 - procedimento amministrativo e autotutela",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1990;241!vig=",
        "ambito": "procedimento amministrativo, accesso, motivazione, autotutela, termini e partecipazione",
    },
    "normattiva_cpa_104_2010": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 2 luglio 2010, n. 104 - Codice del processo amministrativo",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2010;104!vig=",
        "ambito": "ricorso amministrativo, TAR, appello, cautelari, termini e risarcimento PA",
    },
    "normattiva_l_218_1995": {
        "ente": "Normattiva",
        "titolo": "Legge 31 maggio 1995, n. 218 - diritto internazionale privato",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1995;218!vig=",
        "ambito": "riconoscimento sentenze straniere, giurisdizione, legge applicabile e stato civile",
    },
    "normattiva_d_lgs_276_2003": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 10 settembre 2003, n. 276 - mercato del lavoro e cambio appalto",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2003;276!vig=",
        "ambito": "appalto, somministrazione, trasferimenti, clausole sociali e rapporti di lavoro",
    },
    "normattiva_d_lgs_18_2001": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 2 febbraio 2001, n. 18 - trasferimento d'azienda e tutela lavoratori",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2001;18!vig=",
        "ambito": "trasferimento d'azienda, mantenimento diritti e consultazione sindacale",
    },
    "consap_fondo_vittime_strada": {
        "ente": "CONSAP",
        "titolo": "Fondo di garanzia per le vittime della strada - normativa",
        "url": "https://www.consap.it/organismo-di-indennizzo-italiano/normativa/",
        "ambito": "veicoli non assicurati/non identificati, organismi di indennizzo e presidi assicurativi",
    },
    "normattiva_sport_invernali_40_2021": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 28 febbraio 2021, n. 40 - sicurezza nelle discipline sportive invernali",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2021;40!vig=",
        "ambito": "sport invernali, aree sciabili, casco, assicurazione, responsabilità e superamento della disciplina previgente",
    },
    "normattiva_l_47_2017_minori_stranieri": {
        "ente": "Normattiva",
        "titolo": "Legge 7 aprile 2017, n. 47 - minori stranieri non accompagnati",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2017;47!vig=",
        "ambito": "misure di protezione, tutori volontari, accertamento età, accoglienza e superiore interesse del minore",
    },
    "normattiva_d_lgs_142_2015_accoglienza": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 18 agosto 2015, n. 142 - accoglienza e protezione internazionale",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2015-08-18;142!vig=",
        "ambito": "accoglienza richiedenti protezione internazionale, procedure comuni e tutela dei minori stranieri",
    },
    "ministero_lavoro_minori_stranieri": {
        "ente": "Ministero del Lavoro e delle Politiche Sociali",
        "titolo": "Minori stranieri non accompagnati - attuazione e monitoraggio",
        "url": "https://www.lavoro.gov.it/notizie/pagine/legge-sui-minori-stranieri-non-accompagnati",
        "ambito": "tutori volontari, percorsi di protezione, coordinamento istituzionale e monitoraggio MSNA",
    },
    "normattiva_l_184_1983_adozione": {
        "ente": "Normattiva",
        "titolo": "Legge 4 maggio 1983, n. 184 - adozione e affidamento dei minori",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1983;184!vig=",
        "ambito": "adozione nazionale e internazionale, dichiarazione di adottabilità, affidamento e accesso alle origini",
    },
    "commissione_adozioni_internazionali": {
        "ente": "Commissione per le Adozioni Internazionali",
        "titolo": "La strada dell'adozione internazionale",
        "url": "https://www.commissioneadozioni.it/it/per-una-famiglia-adottiva/per-adottare/la-strada-delladozione/",
        "ambito": "decreto di idoneità, ente autorizzato, ingresso del minore, trascrizione e fase post-adottiva",
    },
    "normattiva_dpr_396_2000_stato_civile": {
        "ente": "Normattiva",
        "titolo": "D.P.R. 3 novembre 2000, n. 396 - ordinamento dello stato civile",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:presidente.repubblica:decreto:2000-11-03;396!vig=",
        "ambito": "registri di stato civile, rettifica, annotazione, trascrizione, nascita, matrimonio e cittadinanza",
    },
    "normattiva_l_164_1982_rettificazione_sesso": {
        "ente": "Normattiva",
        "titolo": "Legge 14 aprile 1982, n. 164 - rettificazione di attribuzione di sesso",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=082U0164&atto.dataPubblicazioneGazzetta=1982-04-19&tipoDettaglio=vigente",
        "ambito": "rettificazione di attribuzione di sesso, stato civile e provvedimenti conseguenti",
    },
    "eurlex_reg_2021_782_rail": {
        "ente": "EUR-Lex",
        "titolo": "Regolamento (UE) 2021/782 - diritti e obblighi dei passeggeri ferroviari",
        "url": "https://eur-lex.europa.eu/eli/reg/2021/782/oj?locale=it",
        "ambito": "ritardi, cancellazioni, rimborso, assistenza, informazioni al passeggero e indennizzo ferroviario",
    },
    "art_passeggeri_ferroviari": {
        "ente": "Autorità di Regolazione dei Trasporti",
        "titolo": "Trasporto ferroviario - tutela diritti dei passeggeri",
        "url": "https://www.autorita-trasporti.it/tutela-diritti-dei-passeggeri-trasporto-ferroviario/",
        "ambito": "reclamo di seconda istanza, organismo nazionale, Reg. 1371/2007 previgente e Reg. UE 2021/782",
    },
    "eurlex_reg_805_2004_titolo_esecutivo_europeo": {
        "ente": "EUR-Lex",
        "titolo": "Regolamento (CE) n. 805/2004 - titolo esecutivo europeo",
        "url": "https://eur-lex.europa.eu/eli/reg/2004/805/oj/?locale=IT",
        "ambito": "crediti non contestati, certificazione, circolazione del titolo e requisiti minimi di notificazione",
    },
    "eurlex_reg_1896_2006_ingiunzione_europea": {
        "ente": "EUR-Lex",
        "titolo": "Regolamento (CE) n. 1896/2006 - procedimento europeo d'ingiunzione di pagamento",
        "url": "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32006R1896",
        "ambito": "ingiunzione europea, crediti pecuniari transfrontalieri, opposizione e moduli standard",
    },
    "ejustice_ingiunzione_europea": {
        "ente": "Portale europeo della giustizia elettronica",
        "titolo": "Ingiunzione di pagamento europea",
        "url": "https://e-justice.europa.eu/353/IT/european_payment_order",
        "ambito": "procedura uniforme UE, moduli, autorità competenti e recupero crediti civili e commerciali",
    },
    "uncitral_new_york_convention": {
        "ente": "UNCITRAL - Nazioni Unite",
        "titolo": "Convenzione di New York 1958 sul riconoscimento ed esecuzione dei lodi arbitrali stranieri",
        "url": "https://uncitral.un.org/en/texts/arbitration/conventions/foreign_arbitral_awards",
        "ambito": "riconoscimento ed esecuzione dei lodi arbitrali stranieri, accordi arbitrali e fonti internazionali ufficiali",
    },
    "normattiva_l_89_2001_pinto": {
        "ente": "Normattiva",
        "titolo": "Legge 24 marzo 2001, n. 89 - equa riparazione per irragionevole durata del processo",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2001-03-24;89!vig=",
        "ambito": "Legge Pinto, durata ragionevole, equa riparazione, termine di proponibilità e rimedi preventivi",
    },
    "normattiva_d_lgs_81_2015_lavoro": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 15 giugno 2015, n. 81 - contratti di lavoro e mansioni",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=15G00095&atto.dataPubblicazioneGazzetta=2015-06-24&tipoDettaglio=vigente",
        "ambito": "part-time, somministrazione, distacco, disciplina organica dei contratti e revisione delle mansioni",
    },
    "normattiva_l_335_1995_pensioni": {
        "ente": "Normattiva",
        "titolo": "Legge 8 agosto 1995, n. 335 - riforma del sistema pensionistico",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1995;335!vig=",
        "ambito": "sistema contributivo, pensione, requisiti, trattamenti previdenziali e controversie INPS",
    },
    "normattiva_dl_201_2011": {
        "ente": "Normattiva",
        "titolo": "D.L. 6 dicembre 2011, n. 201 - crescita, equità e consolidamento conti pubblici",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legge:2011-12-06;201!vig=",
        "ambito": "pensioni, strumenti di pagamento, IVIE, IVAFE e imposte patrimoniali su attività estere",
    },
    "eurlex_gdpr": {
        "ente": "EUR-Lex",
        "titolo": "Regolamento (UE) 2016/679 - protezione dei dati personali",
        "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/ita",
        "ambito": "GDPR, responsabilità, risarcimento ex art. 82, sicurezza, basi giuridiche e diritti dell'interessato",
    },
    "normattiva_privacy_196_2003": {
        "ente": "Normattiva",
        "titolo": "D.Lgs. 30 giugno 2003, n. 196 - Codice privacy",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=003G0218&atto.dataPubblicazioneGazzetta=2003-07-29&tipoDettaglio=vigente",
        "ambito": "protezione dati personali, raccordo nazionale al GDPR, reclami, ricorsi e responsabilità",
    },
    "garante_privacy_gdpr": {
        "ente": "Garante per la protezione dei dati personali",
        "titolo": "Regolamento UE 2016/679 - testo e riferimenti del Garante",
        "url": "https://www.garanteprivacy.it/regolamentoue",
        "ambito": "testo GDPR, considerando, guide, provvedimenti e orientamenti dell'autorità competente",
    },
    "normattiva_l_219_2017": {
        "ente": "Normattiva",
        "titolo": "Legge 22 dicembre 2017, n. 219 - consenso informato e DAT",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2017;219!vig=",
        "ambito": "consenso informato, disposizioni anticipate di trattamento, relazione di cura e autodeterminazione sanitaria",
    },
    "agenzia_entrate_definizione_liti_197_2022": {
        "ente": "Agenzia delle Entrate",
        "titolo": "Definizione agevolata delle controversie tributarie pendenti - Legge 197/2022",
        "url": "https://telematici.agenziaentrate.gov.it/Main/Avviso?id=20230315101031",
        "ambito": "domande telematiche, software, provvedimento attuativo e liti fiscali pendenti",
    },
    "agenzia_entrate_ivie_ivafe_quadro_w": {
        "ente": "Agenzia delle Entrate",
        "titolo": "Quadro W - investimenti esteri, IVIE e IVAFE",
        "url": "https://infoprecompilata.agenziaentrate.gov.it/portale/quadro-w",
        "ambito": "monitoraggio fiscale, IVIE, IVAFE, imposta cripto-attività, istruzioni dichiarazione 730/2026",
    },
    "pst_udienze_da_remoto_2023": {
        "ente": "Portale Servizi Telematici - Ministero della Giustizia",
        "titolo": "Provvedimento 7 dicembre 2023 - udienze civili da remoto",
        "url": "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC2991",
        "ambito": "collegamenti audiovisivi, pubblicità dell'udienza, art. 127-bis c.p.c. e art. 196-duodecies disp. att. c.p.c.",
    },
    "ministero_giustizia_127ter_2023": {
        "ente": "Ministero della Giustizia",
        "titolo": "Circolare 30 marzo 2023 - art. 127-ter c.p.c. e deposito note scritte",
        "url": "https://www.giustizia.it/giustizia/en/mg_1_8_1.page?contentId=SDC1406116",
        "ambito": "udienza sostituita da note scritte, contraddittorio, attività equivalente all'udienza e compensi magistratura onoraria",
    },
    "ministero_sentenze_provvedimenti": {
        "ente": "Ministero della Giustizia",
        "titolo": "Servizio pubblicazioni sentenze, provvedimenti e decreti del giudice",
        "url": "https://www.giustizia.it/giustizia/page/it/servizio_pubblicazioni_sentenze_provvedimenti_decreti_del_giudice?tab=e",
        "ambito": "sentenze, provvedimenti, decreti e pubblicazioni ufficiali disponibili al pubblico",
    },
    "cassazione_sentenzeweb": {
        "ente": "Corte Suprema di Cassazione / Italgiure",
        "titolo": "SentenzeWeb - ricerca libera tra sentenze civili e penali della Corte di cassazione",
        "url": "https://www.italgiure.giustizia.it/sncass/",
        "ambito": "giurisprudenza di legittimità, sentenze e ordinanze civili/penali recenti, verifica massime e principi di diritto",
    },
    "cassazione_italgiure": {
        "ente": "Corte Suprema di Cassazione - CED",
        "titolo": "ItalgiureWeb - archivi CED della Corte di cassazione",
        "url": "https://www.italgiure.giustizia.it/",
        "ambito": "archivi giurisprudenziali e normativi CED, ECLI e raccolte di giurisprudenza civile",
    },
    "corte_costituzionale_pronunce": {
        "ente": "Corte costituzionale",
        "titolo": "Elenco pronunce della Corte costituzionale",
        "url": "https://www.cortecostituzionale.it/elenco-pronunce",
        "ambito": "sentenze, ordinanze, decisioni di accoglimento/rigetto, udienze e verifica costituzionale",
    },
    "giustizia_amministrativa_provvedimenti": {
        "ente": "Giustizia Amministrativa",
        "titolo": "Tutti i provvedimenti - Consiglio di Stato e TAR",
        "url": "https://www.giustizia-amministrativa.it/en/provvedimenti-cds",
        "ambito": "sentenze, ordinanze, decreti e pareri del Consiglio di Stato/TAR per appalti, edilizia, PA e autotutela",
    },
    "giustizia_tributaria_banca_dati": {
        "ente": "Dipartimento della Giustizia Tributaria - MEF",
        "titolo": "Portale della Giustizia Tributaria e banca dati giurisprudenziale",
        "url": "https://www.giustizia-tributaria.it/",
        "ambito": "giurisprudenza tributaria, sentenze di merito, massimario nazionale e banca dati SententIA",
    },
    "ejustice_ecli": {
        "ente": "Portale europeo della giustizia elettronica",
        "titolo": "Motore di ricerca ECLI - European Case-Law Identifier",
        "url": "https://e-justice.europa.eu/topics/legislation-and-case-law/european-case-law-identifier-ecli-search-engine_it",
        "ambito": "ricerca di decisioni giudiziarie europee e nazionali con identificatore ECLI",
    },
    "curia_giurisprudenza_ue": {
        "ente": "Corte di giustizia dell'Unione europea",
        "titolo": "CURIA - ricerca giurisprudenza UE",
        "url": "https://curia.europa.eu/juris/recherche.jsf?language=it",
        "ambito": "sentenze, ordinanze e conclusioni della Corte di giustizia e del Tribunale UE",
    },
    "hudoc_cedu": {
        "ente": "Corte europea dei diritti dell'uomo",
        "titolo": "HUDOC - banca dati giurisprudenza CEDU",
        "url": "https://www.echr.coe.int/en/hudoc-database",
        "ambito": "sentenze, decisioni, comunicazioni, opinioni consultive e sintesi giurisprudenziali CEDU",
    },
}

SOURCE_RULES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "processo civile e riforma Cartabia",
        ("rito", "ricorso", "citazione", "opposizione", "impugnazione", "cautel", "esecuzione", "volontaria"),
        ("normattiva_cpc", "normattiva_riforma_cartabia"),
    ),
    (
        "codice civile sostanziale",
        (
            "famiglia",
            "minori",
            "succession",
            "eredit",
            "divisione",
            "diritti reali",
            "contratto",
            "appalto",
            "vendita",
            "locazione",
            "responsabilità",
            "servit",
            "societ",
            "adozione",
            "stato",
        ),
        ("normattiva_cc",),
    ),
    (
        "minori, adozioni e stato civile",
        (
            "minore straniero",
            "minori stranieri",
            "tutore volontario",
            "adozione internazionale",
            "adottabilità",
            "stato di abbandono",
            "stato civile",
            "rettificazione",
            "attribuzione di sesso",
            "gender identity",
        ),
        (
            "normattiva_l_47_2017_minori_stranieri",
            "normattiva_d_lgs_142_2015_accoglienza",
            "ministero_lavoro_minori_stranieri",
            "normattiva_l_184_1983_adozione",
            "commissione_adozioni_internazionali",
            "normattiva_dpr_396_2000_stato_civile",
            "normattiva_l_164_1982_rettificazione_sesso",
            "tribunale_minorenni_competenza",
        ),
    ),
    (
        "fondo patrimoniale e tutela dei creditori",
        ("fondo patrimoniale", "revocatoria", "bisogni della famiglia", "art. 170", "2901"),
        ("normattiva_cc", "normattiva_cpc"),
    ),
    (
        "locazioni abitative e commerciali",
        ("locazione", "sfratto", "prelazione", "avviamento", "conduttore", "canone", "rilascio immobile"),
        ("normattiva_locazioni_392", "normattiva_locazioni_431", "normattiva_cc"),
    ),
    (
        "trasporto e vettori",
        (
            "vettore aereo",
            "regolamento 261",
            "montreal",
            "volo",
            "bagaglio",
            "vettore marittimo",
            "vettore terrestre",
            "trasporto",
            "ferroviario",
            "passeggeri ferroviari",
            "ritardo ferroviario",
            "reg. ue 2021/782",
        ),
        ("enac_reg_261_2004", "normattiva_montreal_2004", "eurlex_reg_2021_782_rail", "art_passeggeri_ferroviari", "normattiva_cc"),
    ),
    (
        "contratti d'impresa e filiere",
        ("factoring", "franchising", "affiliazione commerciale", "subfornitura", "dipendenza economica", "leasing", "noleggio"),
        (
            "normattiva_factoring_52_1991",
            "normattiva_franchising_129_2004",
            "normattiva_subfornitura_192_1998",
            "normattiva_cc",
        ),
    ),
    (
        "lavoro, sicurezza e previdenza",
        (
            "amianto",
            "sicurezza lavoro",
            "collocamento obbligatorio",
            "collocamento mirato",
            "congedo parentale",
            "maternità",
            "paternità",
            "invalidità",
            "pensione",
            "trasferimento azienda",
            "cambio appalto",
            "patto non concorrenza",
            "mbo",
            "premio",
            "part-time",
            "tempo parziale",
            "somministrazione",
            "distacco",
            "demansionamento",
            "mansioni",
            "pensione anticipata",
            "burn-out",
            "stress lavoro-correlato",
        ),
        (
            "normattiva_sicurezza_81_2008",
            "ministero_lavoro_dlgs_81_2008",
            "normattiva_d_lgs_81_2015_lavoro",
            "normattiva_l_68_1999",
            "normattiva_d_lgs_151_2001",
            "inps_congedi_parentali",
            "normattiva_d_lgs_276_2003",
            "normattiva_d_lgs_18_2001",
            "normattiva_l_335_1995_pensioni",
            "normattiva_dl_201_2011",
            "inps_ricorsi_amministrativi",
        ),
    ),
    (
        "amministrativo, edilizia e appalti",
        (
            "permesso di costruire",
            "scia edilizia",
            "scia commerciale",
            "concessione demaniale",
            "demanio marittimo",
            "codice della navigazione",
            "appalto pubblico",
            "contratti pubblici",
            "autotutela",
            "risarcimento pa",
            "provvedimento amministrativo",
            "tar",
        ),
        (
            "normattiva_dpr_380_2001",
            "normattiva_d_lgs_59_2010",
            "normattiva_codice_navigazione_327_1942",
            "normattiva_d_lgs_36_2023",
            "anac_contratti_pubblici",
            "normattiva_l_241_1990",
            "normattiva_cpa_104_2010",
        ),
    ),
    (
        "tributario e fiscalità locale",
        (
            "irpef",
            "redditometro",
            "iva",
            "fatture false",
            "operazioni inesistenti",
            "isa",
            "imposta di registro",
            "successione",
            "donazione",
            "imu",
            "tari",
            "ivie",
            "ivafe",
            "quadro w",
            "definizione agevolata",
            "liti fiscali",
            "plusvalenza",
            "accertamento fiscale",
        ),
        (
            "normattiva_dpr_600_1973",
            "normattiva_dpr_633_1972",
            "normattiva_dpr_131_1986",
            "normattiva_d_lgs_346_1990",
            "normattiva_l_160_2019_imu",
            "normattiva_l_147_2013_tari",
            "normattiva_tuir_917_1986",
            "normattiva_l_197_2022",
            "normattiva_l_130_2022",
            "normattiva_dl_201_2011",
            "agenzia_entrate_definizione_liti_197_2022",
            "agenzia_entrate_ivie_ivafe_quadro_w",
            "dipartimento_finanze_federalismo",
            "agenzia_entrate_isa",
            "agenzia_entrate_riscossione_accertamento",
        ),
    ),
    (
        "procedure europee, lodi stranieri e riconoscimento",
        (
            "titolo esecutivo europeo",
            "crediti non contestati",
            "ingiunzione europea",
            "procedura europea",
            "lodo arbitrale straniero",
            "exequatur",
            "convenzione di new york",
        ),
        (
            "eurlex_reg_805_2004_titolo_esecutivo_europeo",
            "eurlex_reg_1896_2006_ingiunzione_europea",
            "ejustice_ingiunzione_europea",
            "uncitral_new_york_convention",
            "normattiva_cpc",
        ),
    ),
    (
        "privacy e consenso sanitario",
        (
            "violazione dei dati personali",
            "gdpr",
            "reg. ue 679/2016",
            "art. 82",
            "consenso informato",
            "dat",
            "disposizioni anticipate",
            "responsabilità sanitaria",
        ),
        (
            "eurlex_gdpr",
            "normattiva_privacy_196_2003",
            "garante_privacy_gdpr",
            "normattiva_l_219_2017",
            "normattiva_sanitaria",
        ),
    ),
    (
        "Legge Pinto e durata ragionevole",
        ("legge pinto", "irragionevole durata", "equa riparazione", "l. 89/2001", "durata del processo"),
        ("normattiva_l_89_2001_pinto", "hudoc_cedu", "corte_costituzionale_pronunce", "cassazione_sentenzeweb"),
    ),
    (
        "crisi d'impresa",
        ("composizione negoziata", "crisi impresa", "insolvenza", "risanamento", "codice della crisi"),
        ("normattiva_d_lgs_14_2019", "unioncamere_composizione_negoziata", "registro_imprese"),
    ),
    (
        "consumer, AGCM e pratiche scorrette",
        ("pratiche commerciali scorrette", "pubblicità ingannevole", "agcm", "contratto a distanza", "e-commerce"),
        ("normattiva_consumo", "agcm_pratiche_scorrette"),
    ),
    (
        "farmaci e prodotti regolati",
        ("farmaco", "farmaceutico", "medicinale", "farmacovigilanza"),
        ("normattiva_farmaci_219_2006", "normattiva_consumo"),
    ),
    (
        "turismo e pacchetti turistici",
        ("pacchetto turistico", "servizi turistici", "viaggiatore", "organizzatore turistico"),
        ("normattiva_turismo_62_2018", "normattiva_consumo"),
    ),
    (
        "whistleblowing",
        ("whistleblowing", "segnalante", "segnalazione interna", "ritorsione"),
        ("normattiva_whistleblowing_24_2023", "anac_whistleblowing"),
    ),
    (
        "assicurazioni e Fondo vittime strada",
        ("fondo vittime strada", "veicolo non assicurato", "veicolo non identificato", "consap", "fondo di garanzia"),
        ("normattiva_codice_assicurazioni", "consap_fondo_vittime_strada", "normattiva_negoziazione_assistita"),
    ),
    (
        "sport invernali vigente",
        ("sport invernali", "piste sci", "area sciabile", "casco sci", "legge 363"),
        ("normattiva_sport_invernali_40_2021",),
    ),
    (
        "unioni civili e convivenze",
        ("unione civile", "convivenza", "contratto di convivenza"),
        ("normattiva_l_76_2016", "normattiva_cc"),
    ),
    (
        "riconoscimento sentenze straniere",
        ("sentenza straniera", "riconoscimento sentenza", "diritto internazionale privato"),
        ("normattiva_l_218_1995", "normattiva_cpc"),
    ),
    (
        "marchi e segni distintivi UIBM",
        ("marchio di fatto", "preuso", "notorietà", "uibm"),
        ("normattiva_cpi", "normattiva_codice_proprieta_industriale", "uibm_marchi"),
    ),
    (
        "udienze e provvedimenti del giudice",
        ("udienza", "127-bis", "127-ter", "note scritte", "collegamenti audiovisivi", "decreto del giudice", "provvedimento del giudice"),
        (
            "normattiva_cpc",
            "normattiva_riforma_cartabia",
            "pst_udienze_da_remoto_2023",
            "ministero_giustizia_127ter_2023",
            "ministero_sentenze_provvedimenti",
        ),
    ),
    (
        "giurisprudenza nazionale ed europea",
        (
            "sentenza",
            "sentenze",
            "ordinanza",
            "ordinanze",
            "cassazione",
            "sezioni unite",
            "corte costituzionale",
            "consiglio di stato",
            "tar",
            "giurisprudenza",
            "cedu",
            "cgue",
            "ecli",
        ),
        (
            "cassazione_sentenzeweb",
            "cassazione_italgiure",
            "corte_costituzionale_pronunce",
            "giustizia_amministrativa_provvedimenti",
            "giustizia_tributaria_banca_dati",
            "ejustice_ecli",
            "curia_giurisprudenza_ue",
            "hudoc_cedu",
        ),
    ),
    (
        "mediazione civile",
        (
            "mediazione",
            "condominio",
            "diritti reali",
            "divisione",
            "succession",
            "patti di famiglia",
            "locazione",
            "comodato",
            "affitto",
            "responsabilità medica",
            "sanitaria",
            "diffamazione",
            "assicurativ",
            "bancari",
            "finanziari",
            "franchising",
            "consorzio",
            "subfornitura",
            "opera",
            "rete",
            "somministrazione",
            "società di persone",
        ),
        ("normattiva_mediazione",),
    ),
    (
        "negoziazione assistita",
        ("negoziazione", "circolazione", "veicoli", "natanti", "pagamento", "risarcimento", "somma", "indennizzo"),
        ("normattiva_negoziazione_assistita",),
    ),
    ("proprietà industriale", ("marchio", "brevetto", "disegno", "modello", "proprietà industriale"), ("normattiva_cpi", "normattiva_codice_proprieta_industriale")),
    ("responsabilità sanitaria", ("sanitaria", "medico", "struttura sanitaria", "malpractice"), ("normattiva_sanitaria",)),
    ("consumo", ("consumatore", "consumo", "conformità", "clausole vessatorie"), ("normattiva_consumo",)),
    ("lavoro", ("lavoro", "lavoratore", "licenziamento", "mobbing", "straining", "retribuzione", "demansionamento"), ("normattiva_lavoro_604", "normattiva_lavoro_300")),
    ("bancario", ("bancari", "bancario", "mutuo", "anatocismo", "usura", "conto corrente"), ("normattiva_tu_bancario", "banca_italia_abf")),
    ("finanziario", ("finanziari", "investimento", "intermediario finanziario", "tuf"), ("normattiva_tuf", "consob_acf")),
    ("assicurativo", ("assicurativ", "polizza", "sinistro", "indennizzo"), ("normattiva_codice_assicurazioni", "ivass_arbitro_assicurativo")),
    ("comunicazioni elettroniche", ("telefon", "telecomunicazioni", "conciliaweb", "operatore"), ("agcom_conciliaweb",)),
    ("obblighi di fare", ("obblighi di fare", "non fare", "614-bis", "coercizione indiretta", "astreinte"), ("normattiva_614bis",)),
    ("patrocinio a spese dello Stato", ("patrocinio", "spese dello stato", "gratuito patrocinio", "non abbiente"), ("normattiva_tu_spese_giustizia", "ministero_patrocinio_spese_stato")),
    ("pagamenti telematici e contributo unificato", ("contributo unificato", "pagopa", "diritti di cancelleria", "spese di giustizia"), ("normattiva_tu_spese_giustizia", "ministero_pagopa_pst", "pst_servizi_pagopa")),
    ("tassazione atti giudiziari", ("registrazione", "imposta di registro", "atti giudiziari", "agenzia entrate"), ("agenzia_entrate_tassazione_atti_giudiziari",)),
    ("infortuni e malattie professionali", ("infortunio", "malattia professionale", "inail"), ("normattiva_tu_inail", "inail_infortunio_malattia_professionale")),
    ("previdenza e assistenza", ("previdenza", "assistenziale", "inps", "invalidità", "pensione"), ("inps_ricorsi_amministrativi",)),
    ("societario e registro imprese", ("registro imprese", "liquidazione", "scioglimento societ", "visura", "camera di commercio"), ("registro_imprese",)),
    ("famiglia e minori", ("minore", "minori", "adozione", "responsabilità genitoriale", "tutela minore"), ("tribunale_minorenni_competenza",)),
    ("negoziazione assistita famiglia", ("separazione", "divorzio", "modifica condizioni", "negoziazione assistita famiglia"), ("procura_negoziazione_famiglia",)),
    ("consulenza tecnica", ("ctu", "ctp", "atp", "696-bis", "consulente tecnico", "perizia"), ("pst_albo_ctu",)),
)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _fold(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", _text(value).casefold())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9_]+", " ", ascii_text).strip()


def _collect_text(value: Any, *, depth: int = 0) -> str:
    if depth > 4:
        return ""
    if isinstance(value, dict):
        return " ".join(_collect_text(item, depth=depth + 1) for item in value.values())
    if isinstance(value, list):
        return " ".join(_collect_text(item, depth=depth + 1) for item in value[:40])
    return _text(value)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _source_entry(key: str, *, matched_by: str) -> dict[str, str]:
    source = deepcopy(SOURCE_LIBRARY[key])
    source["verificato_il"] = VERIFIED_ON
    source["metodo"] = "ricerca web su fonte ufficiale"
    source["matched_by"] = matched_by
    return source


def _add_source(out: list[dict[str, str]], seen: set[str], key: str, *, matched_by: str) -> None:
    url = SOURCE_LIBRARY[key]["url"]
    if url in seen:
        return
    seen.add(url)
    out.append(_source_entry(key, matched_by=matched_by))


def web_sources_for_guidance(guidance: dict[str, Any]) -> list[dict[str, str]]:
    """Restituisce fonti ufficiali pertinenti per una scheda guida."""

    haystack = _fold(_collect_text(guidance))
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for key in ("pst_download", "pst_xsd_sici_2024", "pst_specifiche_2014"):
        _add_source(out, seen, key, matched_by="presidio catalogo PST/XSD e deposito")
    for label, tokens, source_keys in SOURCE_RULES:
        if any(_fold(token) in haystack for token in tokens):
            for key in source_keys:
                _add_source(out, seen, key, matched_by=label)
    if len(out) == 3:
        for key in ("normattiva_cpc", "normattiva_cc"):
            _add_source(out, seen, key, matched_by="presidio generale civile")
    return out


def _source_titles(sources: list[dict[str, str]]) -> list[str]:
    return [_text(source.get("titolo")) for source in sources if _text(source.get("titolo"))]


def _procedibilita_note(guidance: dict[str, Any], sources: list[dict[str, str]]) -> list[dict[str, str]]:
    titles = " ".join(_source_titles(sources)).casefold()
    notes: list[dict[str, str]] = []
    mediazione = guidance.get("obbligo_mediazione") or guidance.get("obbligo_mediazione_o_negoziazione_assistita")
    if mediazione or "mediazione" in titles:
        notes.append(
            {
                "presidio": "Mediazione civile",
                "azione": "Verifica se la materia richiede mediazione come condizione di procedibilità prima della domanda.",
                "fonte": "D.Lgs. 28/2010, art. 5",
            }
        )
    if "negoziazione assistita" in titles:
        notes.append(
            {
                "presidio": "Negoziazione assistita",
                "azione": "Controlla circolazione, pagamento somme e soglie prima di iscrivere la causa.",
                "fonte": "D.L. 132/2014, art. 3",
            }
        )
    if "arbitro bancario finanziario" in titles:
        notes.append(
            {
                "presidio": "ABF",
                "azione": "Valuta reclamo e ricorso ABF quando la controversia è bancaria o finanziaria non d'investimento.",
                "fonte": "Banca d'Italia",
            }
        )
    if "controversie finanziarie" in titles:
        notes.append(
            {
                "presidio": "ACF",
                "azione": "Valuta reclamo e ricorso ACF quando emergono servizi di investimento o obblighi informativi dell'intermediario.",
                "fonte": "CONSOB",
            }
        )
    if "arbitro assicurativo" in titles:
        notes.append(
            {
                "presidio": "Arbitro Assicurativo",
                "azione": "Prima del ricorso verifica reclamo assicurativo e decorso dei termini di risposta.",
                "fonte": "IVASS",
            }
        )
    if "conciliaweb" in titles:
        notes.append(
            {
                "presidio": "ConciliaWeb",
                "azione": "Per operatori di comunicazioni elettroniche verifica reclamo, conciliazione e definizione AGCOM.",
                "fonte": "AGCOM",
            }
        )
    if "patrocinio a spese" in titles:
        notes.append(
            {
                "presidio": "Patrocinio a spese dello Stato",
                "azione": "Valuta requisiti reddituali, non manifesta infondatezza e documenti prima o durante l'apertura del fascicolo.",
                "fonte": "Ministero della Giustizia",
            }
        )
    if "pagamenti telematici" in titles or "pagopa" in titles:
        notes.append(
            {
                "presidio": "Contributo unificato e PagoPA",
                "azione": "Prepara pagamento, ricevuta e dati economici senza bloccare la redazione dell'atto.",
                "fonte": "Ministero della Giustizia / PST",
            }
        )
    if "tassazione degli atti giudiziari" in titles:
        notes.append(
            {
                "presidio": "Tassazione atti giudiziari",
                "azione": "Dopo il provvedimento valuta registrazione e importi tramite il servizio Agenzia delle Entrate.",
                "fonte": "Agenzia delle Entrate",
            }
        )
    if "infortunio" in titles or "malattia professionale" in titles:
        notes.append(
            {
                "presidio": "INAIL",
                "azione": "Per infortunio o malattia professionale verifica denuncia, certificati e termini amministrativi collegati.",
                "fonte": "INAIL",
            }
        )
    if "ricorsi amministrativi" in titles:
        notes.append(
            {
                "presidio": "INPS",
                "azione": "Nelle materie previdenziali controlla il ricorso amministrativo e il relativo stato prima del giudizio.",
                "fonte": "INPS",
            }
        )
    if "registro delle imprese" in titles:
        notes.append(
            {
                "presidio": "Registro imprese",
                "azione": "Acquisisci visura aggiornata, assetti, liquidazione o cancellazione prima di impostare domanda e legittimazione.",
                "fonte": "Camera di Commercio",
            }
        )
    if "tribunale per i minorenni" in titles:
        notes.append(
            {
                "presidio": "Competenza minorile",
                "azione": "Distingui Tribunale ordinario, Tribunale per i Minorenni e Giudice tutelare prima di selezionare ufficio e template.",
                "fonte": "Ministero della Giustizia",
            }
        )
    if "albo ctu" in titles:
        notes.append(
            {
                "presidio": "CTU/ATP",
                "azione": "Quando la pratica è tecnica, collega quesiti, documenti e possibile consulenza preventiva senza trasformarla in blocco.",
                "fonte": "PST / Ministero della Giustizia",
            }
        )
    if "261/2004" in titles or "passeggeri aerei" in titles:
        notes.append(
            {
                "presidio": "Trasporto aereo",
                "azione": "Verifica disservizio, tratta, tempi di ritardo/cancellazione, reclamo al vettore e possibile presidio ENAC.",
                "fonte": "ENAC / Reg. CE 261/2004",
            }
        )
    if "contratti pubblici" in titles or "bdncp" in titles:
        notes.append(
            {
                "presidio": "Appalti pubblici",
                "azione": "Controlla fase della procedura, piattaforma, CIG/BDNCP, termini di impugnazione e documenti di gara.",
                "fonte": "D.Lgs. 36/2023 / ANAC",
            }
        )
    if "whistleblowing" in titles:
        notes.append(
            {
                "presidio": "Whistleblowing",
                "azione": "Distingui canale interno, canale esterno ANAC, misure anti-ritorsive e documenti di riservatezza.",
                "fonte": "D.Lgs. 24/2023 / ANAC",
            }
        )
    if "pratiche commerciali scorrette" in titles or "pubblicità ingannevole" in titles:
        notes.append(
            {
                "presidio": "Tutela consumatore AGCM",
                "azione": "Valuta segnalazione AGCM, prova della pratica, reclamo e rimedi civilistici collegati.",
                "fonte": "AGCM / Codice del consumo",
            }
        )
    if "testo unico edilizia" in titles:
        notes.append(
            {
                "presidio": "Titolo edilizio",
                "azione": "Verifica titolo, SCIA/permesso, stato legittimo, termini amministrativi e profili urbanistici locali.",
                "fonte": "D.P.R. 380/2001",
            }
        )
    if "portale del federalismo fiscale" in titles or "disciplina imu" in titles:
        notes.append(
            {
                "presidio": "Fiscalità locale",
                "azione": "Recupera delibera e regolamento comunale vigente prima di calcolare IMU/TARI o predisporre ricorso.",
                "fonte": "MEF - Dipartimento delle Finanze",
            }
        )
    if "composizione negoziata" in titles:
        notes.append(
            {
                "presidio": "Composizione negoziata",
                "azione": "Valuta test pratico, piattaforma Unioncamere, misure protettive e documenti contabili aggiornati.",
                "fonte": "Codice della crisi / Unioncamere",
            }
        )
    if "fondo di garanzia per le vittime della strada" in titles:
        notes.append(
            {
                "presidio": "Fondo vittime strada",
                "azione": "Controlla identificazione veicolo, assicurazione, denuncia, lettere all'impresa designata e termini.",
                "fonte": "Codice assicurazioni / CONSAP",
            }
        )
    return notes


def operational_presidi_for_guidance(guidance: dict[str, Any], sources: list[dict[str, str]]) -> dict[str, Any]:
    deposito = _as_dict(guidance.get("codice_deposito"))
    depositabile = bool(deposito.get("depositabile"))
    allegati_count = len(_as_list(guidance.get("allegati_obbligatori")))
    termini_count = len(_as_list(guidance.get("termini_processuali")))
    return {
        "versione": ENRICHMENT_VERSION,
        "verificato_il": VERIFIED_ON,
        "deposito": {
            "regola": "Il codice deposito resta sempre quello ufficiale del fascicolo; la guida non lo sostituisce.",
            "depositabile_dalla_scheda": depositabile,
            "azione_avvocato": (
                "Usa il codice già valorizzato nel fascicolo e verifica solo coerenza con atto e ufficio."
                if depositabile
                else "Usa questa scheda come guida operativa e seleziona nel fascicolo il codice PST/XSD ufficiale pertinente."
            ),
        },
        "procedibilita_e_adr": _procedibilita_note(guidance, sources),
        "termini": {
            "termini_censiti": termini_count,
            "azione_avvocato": "Trasforma i termini pertinenti in scadenze solo dopo aver fissato decorrenza e atto/fase reale.",
        },
        "allegati": {
            "allegati_censiti": allegati_count,
            "azione_avvocato": "Usa gli allegati come checklist fascicolo, non come blocco preventivo della redazione.",
        },
        "lex": {
            "profilo": "conversazionale_avvocato",
            "azione": "Lex deve spiegare fonte, limite, dato mancante e prossimo passo operativo senza confondere guida e deposito.",
        },
        "template": {
            "azione": "Il template va filtrato su codice/guida, rito, fase, ufficio, valore, documenti presenti e atto suggerito.",
        },
    }


def enrich_guidance_with_web_sources(guidance: dict[str, Any]) -> dict[str, Any]:
    """Applica l'arricchimento a una scheda senza sovrascrivere il contenuto curato."""

    out = deepcopy(guidance)
    existing = out.get("fonti_verifica_web") if isinstance(out.get("fonti_verifica_web"), list) else []
    by_url = {str(source.get("url")): dict(source) for source in existing if isinstance(source, dict) and source.get("url")}
    for source in web_sources_for_guidance(out):
        by_url.setdefault(source["url"], source)
    sources = list(by_url.values())
    out["fonti_verifica_web"] = sources

    existing_presidi = _as_dict(out.get("presidi_operativi_integrativi"))
    presidi = operational_presidi_for_guidance(out, sources)
    out["presidi_operativi_integrativi"] = {**presidi, **existing_presidi}
    out["arricchimento_iusentra"] = {
        "versione": ENRICHMENT_VERSION,
        "generato_il": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "scope": "applicato a tutte le schede Guida Pratica restituite dal servizio",
        "fonti_ufficiali": len(sources),
        "non_bloccante": True,
    }
    return out
