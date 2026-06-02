# Fonti ufficiali telematico, spese e deontologia - 2 giugno 2026

Questo dossier salva le fonti usate per la verifica "360 gradi" richiesta sul
perimetro telematico, pagamenti, contributo unificato e Codice Deontologico
Forense. Le fonti sono state consultate il 2 giugno 2026 e, dove tecnicamente
scaricabili, salvate anche in `docs/specs/ministero/fonti_ufficiali/2026-06-02/`.

## Metodo operativo

1. Prima si salva la fonte ufficiale o un estratto verificato.
2. Poi si estrae la regola utile per il software.
3. Poi si confronta con codice, UI e test.
4. Se una fonte necessaria manca, non si lascia un test rosso come risultato
   finale: si ricerca la fonte, si salva nel registro e si implementa la regola.
5. Se la fonte consultabile non consente una regola certa, il software deve
   avvisare e non inventare automatismi.

## Fonti salvate localmente

| Ambito | URL ufficiale | File locale | Dato salvato |
| --- | --- | --- | --- |
| DPR 115/2002 art. 13 | `https://def.giustiziatributaria.gov.it/DocTribFrontend/executePrintArticolo.do?...Articolo+13...` | `fonti_ufficiali/2026-06-02/dpr-115-2002-art-13-contributo-unificato.pdf` | Scaglioni CU, riduzioni 50%, impugnazione +50%, Cassazione x2, sezioni impresa x2, esecuzioni, amministrativo, tributario. |
| DPR 115/2002 consolidato | `https://www.normattiva.it/eli/id/2002/06/15/002G0139/CONSOLIDATED/20241015` | `fonti_ufficiali/2026-06-02/normattiva-dpr-115-2002.html` | Testo vigente consolidato e aggiornamento Normattiva. |
| PST servizi | `https://pst.giustizia.it/PST/it/services.page` | `fonti_ufficiali/2026-06-02/pst-services.html` | Elenco servizi pubblici/riservati, inclusi uffici giudiziari, registri, Cassazione, PDP, RegIndE. |
| PST uffici civili | `https://servizipst.giustizia.it/PST/it/pst_2_4.wp?ufficioSelect=giudiziari...` | `fonti_ufficiali/2026-06-02/pst-uffici-giudiziari-civili.html` | Catalogo pubblico uffici giudiziari civili. |
| PST uffici penali | `https://servizipst.giustizia.it/PST/it/pst_2_4.wp?ufficioSelect=penali...` | `fonti_ufficiali/2026-06-02/pst-uffici-giudiziari-penali.html` | Catalogo pubblico uffici giudiziari penali/PDP. |
| PST pagamenti | `https://pst.giustizia.it/PST/it/dettaglio_schede_tematiche.page?contentId=ACC433&modelId=12` | `fonti_ufficiali/2026-06-02/pst-pagamenti-scheda.html` | Canali pagamento telematico PST/PCT. |
| PST vademecum pagamenti | `https://pst.giustizia.it/PST/resources/cms/documents/PagTel_Vademecum_unico.pdf` | `fonti_ufficiali/2026-06-02/pst-vademecum-pagamenti.pdf` | Regole operative pagamento telematico. |
| PST flussi pagoPA | `https://pst.giustizia.it/PST/resources/cms/documents/PDA__Flussi_pagamento_telematico_tramite_PST_vers._6.3.pdf` | `fonti_ufficiali/2026-06-02/pst-flussi-pagamento-pst-6-3.pdf` | RT.xml, stati e codici pagamento. |
| PST pagoPA pubblico | `https://servizipst.giustizia.it/PST/it/pagopa.wp` | `fonti_ufficiali/2026-06-02/pst-pagopa-pubblico.html` | Pagamento pagoPA per utenti non registrati. |
| PAT Portale Avvocato | `https://www.giustizia-amministrativa.it/web/guest/portale-avvocato` | `fonti_ufficiali/2026-06-02/pat-portale-avvocato.html` | Processo amministrativo telematico, portale avvocato, fascicoli/depositi. |
| PAT FAQ | `https://www.giustizia-amministrativa.it/faq-nuovo-portale` | `fonti_ufficiali/2026-06-02/pat-faq-nuovo-portale.html` | Informazioni operative PAT e pagamenti. |
| PAT F24 Elide | `https://www.giustizia-amministrativa.it/documents/20142/0/nsiga_4464814.pdf/...` | `fonti_ufficiali/2026-06-02/pat-f24-elide.pdf` | Campi F24 Elide e codici tributo Giustizia Amministrativa. |
| PTT assistenza | `https://assistenza.dgt.mef.gov.it/GiustiziaTributaria/s/most-viewed` | `fonti_ufficiali/2026-06-02/ptt-assistenza-most-viewed.html` | Pagina assistenza servizi online Giustizia Tributaria. Il contenuto utile è anche riportato negli audit perché la pagina è dinamica. |
| PTT processo | `https://assistenza.dgt.mef.gov.it/GiustiziaTributaria/s/articolo-detail?urlName=DF-GiustiziaTributaria-3016` | `fonti_ufficiali/2026-06-02/ptt-processo-tributario-articolo-3016.html` | Workflow PTT; contenuto dinamico riportato negli audit. |
| PTT pagamenti | `https://assistenza.dgt.mef.gov.it/GiustiziaTributaria/s/articolo-detail?urlName=DF-GiustiziaTributaria-3059` | `fonti_ufficiali/2026-06-02/ptt-pagamenti-articolo-3059.html` | Deposito telematico e pagamenti; contenuto dinamico riportato negli audit. |
| PTT CUT | `https://www.mef.gov.it/ufficio-stampa/comunicati/2019/documenti/prot._5764-19_Circolare_PTT_4-7-2019.pdf` | `fonti_ufficiali/2026-06-02/ptt-circolare-cut-2019.pdf` | CUT pagoPA con RGR/RGA e abbinamento al ricorso/appello. |
| CDF sito CNF | `https://codicedeontologico-cnf.it/` | `fonti_ufficiali/2026-06-02/cnf-codice-deontologico-home.html` | Sito CNF del Codice Deontologico Forense. |
| CDF art. 25-bis CNF | `https://codicedeontologico-cnf.it/nuovo-articolo-25-bis-cdf-con-tabella-di-confronto/` | `fonti_ufficiali/2026-06-02/cnf-cdf-art-25bis-confronto.html` | Nuovo art. 25-bis e confronto vecchio/nuovo. |
| CDF art. 27 CNF | `https://codicedeontologico-cnf.it/tag/27-ncdf/` | `fonti_ufficiali/2026-06-02/cnf-cdf-art-27-tag.html` | Dovere di informazione, anche su CU e comunicazioni al cliente. |
| CDF art. 25-bis G.U. | `https://www.gazzettaufficiale.it/atto/vediMenuHTML?atto.codiceRedazionale=26A00480...` | `fonti_ufficiali/2026-06-02/gazzetta-cdf-art-25bis-2026.html` | Delibera CNF n. 959/2026 su equo compenso. |
| CDF modifiche 2025 G.U. | `https://www.gazzettaufficiale.it/atto/vediMenuHTML?atto.codiceRedazionale=25A04804...` | `fonti_ufficiali/2026-06-02/gazzetta-cdf-modifiche-2025.html` | Modifiche CDF 2025 su articoli 48, 50, 51, 56, 61, 62, 62-bis e Titolo IV. |
| CDF circolare CNF | `https://www.ordineforense.re.it/wp-content/uploads/2026/04/N.-1-C-2026-Entrata-in-vigore-art.-25-bis-Codice-Deontologico-Forense.pdf` | `fonti_ufficiali/2026-06-02/cnf-circolare-1c-2026-art-25bis.pdf` | Decorrenza 7 aprile 2026 e ambito soggettivo art. 25-bis. |
| FatturaPA formato XML | `https://www.fatturapa.gov.it/export/documenti/fatturapa/v1.3.1/Specifiche_tecniche_del_formato_FatturaPA_V1.3.1.pdf` | `fonti_ufficiali/2026-06-02/fatturapa-specifiche-formato-v1-3-1.pdf` | Formato XML FatturaPA e dati tecnici di fattura elettronica. |
| FatturaPA trasmissione SdIFtp | `https://www.fatturapa.gov.it/export/documenti/sdi/Specifiche_tecniche_SdIFtp_v4.2.pdf` | `fonti_ufficiali/2026-06-02/fatturapa-sdiftp-specifiche-v4-2.pdf` | Canale di trasmissione SdI accreditato via FTP. |
| FatturaPA trasmissione SDICoop | `https://www.fatturapa.gov.it/export/fatturazione/sdi/ws/trasmissione/v1.1/SDICoop_trasmissione_v1.1.pdf` | `fonti_ufficiali/2026-06-02/fatturapa-sdicoop-trasmissione-v1-1.pdf` | Canale di trasmissione SdI accreditato via servizio cooperativo. |
| Agenzia Entrate fatturazione elettronica | `https://www.agenziaentrate.gov.it/portale/guida-fatturazione-elettronica` | `fonti_ufficiali/2026-06-02/agenzia-entrate-guida-fatturazione-elettronica.html` | Invio tramite SdI, ricevute, scarto, monitoraggio e portale Fatture e Corrispettivi. |
| Garante registro trattamenti | `https://www.garanteprivacy.it/registro-delle-attivita-di-trattamento` | `fonti_ufficiali/2026-06-02/garante-registro-attivita-trattamento.html` | Contenuti del registro GDPR, aggiornamento e casi rilevanti per studi professionali. |
| Garante istruzioni registro trattamenti | `https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/9047529` | `fonti_ufficiali/2026-06-02/garante-istruzioni-registro-attivita-trattamento-9047529.html` | Indicazioni operative del Garante sul registro dei trattamenti. |
| Garante GDPR Regolamento 2016/679 | `https://www.garanteprivacy.it/regolamentoue` | `fonti_ufficiali/2026-06-02/garante-gdpr-regolamento-2016-679.html` | Fonte di riferimento GDPR e collegamento al testo del regolamento. |

## Regole DPR 115/2002 art. 13 estratte e stato software

| Regola ufficiale | Stato software | Esito |
| --- | --- | --- |
| Scaglioni civile: 43, 98, 237, 518, 759, 1214, 1686. | `pct/normative_tables.py`, `pct/strumenti_legali.py`. | Coperto, con test. |
| Valore indeterminabile civile: 518; valore non indicato: 1686. | `contributo_defaults("civile")`. | Coperto, con test. |
| Impugnazione: aumento della metà. | Campo `cu_grado=appello`. | Coperto per categorie certe, con test. |
| Cassazione: raddoppio. | Campo `cu_grado=cassazione`. | Coperto per categorie certe, con test; esclusi casi non certi con avviso. |
| Sezioni specializzate impresa: raddoppio e poi applicazione regola sul grado. | Campo `cu_sezione_specializzata_impresa`. | Implementato e testato. |
| Decreto ingiuntivo, lavoro e processi speciali libro IV titolo I c.p.c.: riduzione alla metà. | Categorie `decreto_ingiuntivo`, `lavoro`, `processo_speciale_libro_iv`. | Implementato e testato. |
| Ricerca beni ex art. 492-bis: 43 euro e niente art. 30. | Categoria `ricerca_beni_492bis`. | Implementato e testato. |
| Accertamento cittadinanza italiana: 600 euro per ogni ricorrente. | Categoria `cittadinanza_italiana` e campo `cu_numero_parti_ricorrenti`. | Implementato; niente impugnazione automatica senza fonte specifica. |
| Esecuzione immobiliare 278; altre esecuzioni metà; mobiliare sotto 2.500 euro 43; opposizione atti esecutivi 168. | Categorie esecuzioni. | Implementato e testato. |
| Procedura fallimentare: 851. | Categoria `procedura_fallimentare`. | Implementato e testato. |
| Amministrativo 300/650/1800/appalti 2000-4000-6000. | Categorie amministrative. | Coperto; aggiunta categoria 300 euro. |
| Tributario 30/60/120/250/500/1500 e valore non indicato 1500. | Categoria `tributario`. | Coperto, con test. |
| Omessa PEC/fax/codice fiscale/dichiarazione valore: maggiorazione 50%. | Campo `cu_dati_obbligatori_mancanti`. | Implementato con warning e test. |

## Regole pagamento telematico estratte e stato software

| Canale | Regola ufficiale | Stato software |
| --- | --- | --- |
| PST/PCT | La ricevuta tecnica è `RT.xml`; codici pagamento governati: `CONTRIB`, `DIRCANC`, `DIRCOPIA`, `CONTRBENI`, `UNPIG`, `UNNOT`; il promemoria PDF non sostituisce la RT. | `legal_deposit/payment_policies.py`, warning in `pct/deposito_guidato.py`, test dedicati. |
| PAT/SIGA | CU tracciato con F24 Elide: data, estremi, importo, codice tributo, numero riga, elementi identificativi e quietanza. | `pat_f24_elide_contributo_unificato`, test dedicato. |
| PTT/SIGIT | CUT pagoPA da link PEC o area personale PTT, con riferimento RGR/RGA e abbinamento al ricorso/appello. | `ptt_cut_pagopa`, test dedicato. |

## Regole deontologiche estratte e stato software

| Fonte | Regola utile per IUSENTRA | Stato |
| --- | --- | --- |
| CDF art. 25-bis, G.U. 5 febbraio 2026 e circolare CNF 1-C-2026 | Nei rapporti con banche/assicurazioni, grandi imprese e PA il compenso deve rispettare equo compenso e parametri; se il contratto è predisposto dall'avvocato serve avviso scritto. | Fonte registrata in `FONTI_OPERATIVE`, `config/lex_official_sources.example.json` e controlli onorari/preventivi in `pct/strumenti_legali.py`. |
| CDF art. 27, sito CNF | Informazioni al cliente chiare, complete, tempestive e comprensibili; particolare attenzione a costi prevedibili, CU e atti necessari a evitare pregiudizi. | Fonte registrata e collegata ai presidi deontologici del calcolo onorari/preventivi. |
| G.U. 1 settembre 2025 | Modifiche CDF su riservatezza corrispondenza, istanze ripetute, ascolto minore, arbitrato, mediazione e negoziazione assistita. | Fonte salvata; da mappare nei controlli atti/bozze quando si toccano quei moduli. |

## Regole FatturaPA/SdI estratte e stato software

| Fonte | Regola utile per IUSENTRA | Stato |
| --- | --- | --- |
| Specifiche formato FatturaPA 1.3.1 | La fattura elettronica deve essere predisposta in XML conforme al formato FatturaPA. | `pct/fatturazione.py` conserva dati SdI; `web/services/react_fatturazione_bridge.py` espone fonti, workflow ed esiti; test dedicati. |
| Agenzia Entrate guida fatturazione elettronica | Se la fattura non è XML o non passa da SdI non è una fattura elettronica validamente emessa; lo scarto richiede correzione e nuovo invio. | La UI mostra stati `Preparata`, `Inviata`, `Consegnata`, `Mancata consegna`, `Scartata`, `Decorrenza termini` e non crea automatismi se manca canale reale. |
| Specifiche SdIFtp/SDICoop/SPCoop | Il canale automatico richiede servizio/intermediario o canale accreditato. | In `Impostazioni > Canali SdI` si configurano modalità, intermediario, codice canale, indirizzo servizio, utente e PEC notifiche; l'invio automatico resta prudente se manca canale reale. |

## Regole GDPR Registro Trattamenti estratte e stato software

| Fonte | Regola utile per IUSENTRA | Stato |
| --- | --- | --- |
| Garante registro delle attività di trattamento | Il registro deve indicare titolare/responsabile, finalità, categorie interessati e dati, destinatari, trasferimenti, conservazione e misure di sicurezza. | `pct/privacy.py`, bridge React e UI Registro GDPR includono campi e checklist ufficiale. |
| Istruzioni Garante DocWeb 9047529 | Il registro deve essere aggiornato e riflettere i trattamenti reali; gli studi professionali sono presidiati quando trattano dati particolari/giudiziari o hanno organizzazione con personale/responsabili. | Il software mostra alert professionali e fonti salvate, senza sostituire valutazione privacy dello studio. |

## Gap ancora da chiudere

| Gap | Azione |
| --- | --- |
| Estendere i presidi art. 25-bis/art. 27 anche al wizard preventivo completo, oltre al calcolo onorari degli strumenti. | Dopo i test mirati, collegare gli stessi campi al flusso `/preventivi/wizard` se non già derivati dal bridge. |
| Esporre nel risultato CU tutte le regole applicate anche nella superficie React. | Implementato in `pct/applicazioni_runtime.py`; verificare browser. |
| Mantenere aggiornato il registro strutturato delle fonti quando nasce una nuova regola. | Usare `registro_fonti_ufficiali_2026-06-02.json` come fonte di lavoro e aggiornarlo prima della regola applicativa. |
| Aggiornare audit e test UTF-8 dopo modifiche a documentazione e UI. | Eseguire test mirati. |
