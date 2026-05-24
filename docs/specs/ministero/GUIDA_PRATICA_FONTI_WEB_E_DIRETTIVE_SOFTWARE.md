# Guida Pratica: fonti web ufficiali e direttive software

Aggiornato: 24 maggio 2026.

Questo documento conserva nella repository le fonti e le direttive usate per arricchire la Guida Pratica IUSENTRA. Le regole qui sotto sono operative: non devono restare nella chat e non devono trasformarsi in automatismi bloccanti per il fascicolo.

## Regole software permanenti

1. Il codice che apre il fascicolo resta sempre il codice ufficiale PST/XSD o normativo scelto nel fascicolo.
2. La Guida Pratica può usare alias interni e fonti di supporto, ma non sostituisce mai `codice_oggetto_pst`.
3. Le verifiche web arricchiscono la scheda con fonti, presidi e avvertenze, senza bloccare apertura fascicolo, redazione documento o lavoro ordinario.
4. Il blocco vero sul deposito resta demandato ai controlli del deposito telematico, sulla base del codice ufficiale del fascicolo e degli XSD locali.
5. La UI deve mostrare le fonti ufficiali e i presidi integrativi in modo compatto: tab `Normativa` per le fonti, tab `Contesto` per i presidi operativi.
6. Lex deve leggere fonti e presidi in modo conversazionale, distinguendo fatto certo, dato mancante, guida interna e codice deposito.
7. Ogni nuova fonte deve avere ente, titolo, URL, ambito, data di verifica e regola software applicata.

## Fonti tecniche deposito e catalogo

- Portale Servizi Telematici, download PCT: https://pst.giustizia.it/PST/it/download.page
  - Ambito: XSD SICI, Giudici di pace, Cassazione, file ufficiali PCT.
  - Regola software: fonte primaria per distinguere catalogo ufficiale e alias interni.

- Portale Servizi Telematici, XSD SICI 23 gennaio 2024: https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3094
  - Ambito: schemi XSD SICI, tipi-base e codici oggetto.
  - Regola software: il validatore usa il catalogo locale derivato dagli XSD, non le descrizioni delle guide.

- Portale Servizi Telematici, specifiche tecniche 16 aprile 2014: https://servizipst.giustizia.it/PST/it/pst_26_1.wp?contentId=DOC416&previousPage=pst_1_0
  - Ambito: regole tecniche deposito telematico.
  - Regola software: la Guida Pratica non può inventare campi XML o vincoli di deposito.

## Fonti normative generali

- Codice di procedura civile, R.D. 28 ottobre 1940, n. 1443: https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=040U1443&atto.dataPubblicazioneGazzetta=1940-10-28&tipoDettaglio=multivigenza
  - Ambito: rito civile, opposizioni, cautelari, esecuzioni, impugnazioni, famiglia e volontaria giurisdizione.
  - Regola software: fonte base per termini, rito, atto e passaggi processuali.

- Codice civile, R.D. 16 marzo 1942, n. 262: https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=042U0262&atto.dataPubblicazioneGazzetta=1942-04-04&tipoDettaglio=multivigenza
  - Ambito: famiglia, successioni, diritti reali, contratti, responsabilità, società e persone.
  - Regola software: fonte sostanziale generale per presupposti, legittimazione e rimedi.

- D.Lgs. 10 ottobre 2022, n. 149: https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=22G00158&atto.dataPubblicazioneGazzetta=2022-10-17
  - Ambito: riforma del processo civile, famiglia, esecuzione forzata, mediazione, negoziazione assistita e arbitrato.
  - Regola software: fonte per presidi di rito e aggiornamento Cartabia.

## Procedibilità, ADR e canali specialistici

- D.Lgs. 4 marzo 2010, n. 28, art. 5: https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2010;28~art5=
  - Ambito: mediazione civile e commerciale.
  - Regola software: segnala condizione di procedibilità dove pertinente, mai come blocco automatico della redazione.

- D.L. 12 settembre 2014, n. 132, art. 3: https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legge:2014;132~art3=
  - Ambito: negoziazione assistita.
  - Regola software: presidio per circolazione, pagamento somme entro soglia e casi fuori mediazione.

- Banca d'Italia, Arbitro Bancario Finanziario: https://www.bancaditalia.it/compiti/tutela-educazione/abf/index.html
  - Ambito: controversie bancarie e finanziarie con intermediari.
  - Regola software: suggerire reclamo/ABF nei contenziosi bancari coerenti.

- CONSOB, Arbitro per le Controversie Finanziarie: https://www.consob.it/web/area-pubblica/arbitro-per-le-controversie-finanziarie
  - Ambito: servizi di investimento e intermediari finanziari.
  - Regola software: distinguere ABF e ACF in base alla materia.

- IVASS, Arbitro Assicurativo: https://www.ivass.it/consumatori/aas/index.html
  - Ambito: controversie assicurative dopo reclamo.
  - Regola software: suggerire reclamo e ricorso assicurativo quando la scheda è assicurativa.

- AGCOM, ConciliaWeb: https://www.agcom.it/agcom-per-te/i-miei-diritti/contenzioso-tra-utenti-e-operatori
  - Ambito: comunicazioni elettroniche, servizi media e operatori.
  - Regola software: presidio specialistico solo quando la pratica riguarda operatori di comunicazione.

## Fonti specialistiche aggiunte

- D.Lgs. 1 settembre 1993, n. 385, Testo unico bancario: https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=093G0427&atto.dataPubblicazioneGazzetta=1993-09-30&tipoDettaglio=vigente
- D.Lgs. 24 febbraio 1998, n. 58, Testo unico della finanza: https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=098G0075&atto.dataPubblicazioneGazzetta=1998-03-26&tipoDettaglio=vigente
- D.Lgs. 7 settembre 2005, n. 209, Codice delle assicurazioni private: https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=005G0233&atto.dataPubblicazioneGazzetta=2005-10-13&tipoDettaglio=vigente
- D.Lgs. 10 febbraio 2005, n. 30, Codice della proprietà industriale: https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=005G0055&atto.dataPubblicazioneGazzetta=2005-03-04&tipoDettaglio=vigente
- L. 8 marzo 2017, n. 24, responsabilità sanitaria: https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2017-03-08;24~art10-com2=
- D.Lgs. 6 settembre 2005, n. 206, Codice del consumo: https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2005;206!vig=
- L. 15 luglio 1966, n. 604, licenziamenti individuali: https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=066U0604&atto.dataPubblicazioneGazzetta=1966-08-06
- L. 20 maggio 1970, n. 300, Statuto dei lavoratori: https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1970;300~art35-com=
- D.P.R. 30 giugno 1965, n. 1124, Testo unico INAIL: https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=065U1124&atto.dataPubblicazioneGazzetta=1965-10-13&tipoDettaglio=vigente
- D.P.R. 30 maggio 2002, n. 115, Testo unico spese di giustizia: https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=002G0139&atto.dataPubblicazioneGazzetta=2002-06-15&tipoDettaglio=vigente

## Fonti operative istituzionali

- Ministero della Giustizia, patrocinio a spese dello Stato: https://www.giustizia.it/giustizia/page/it/patrocinio_a_spese_dello_stato_nei_giudizi_civili_e_amministrativi
- Ministero della Giustizia, contributo unificato e PagoPA: https://www.giustizia.it/giustizia/it/mg_1_40_0.page?contentId=IGC408325&facetNode_2=0_23
- PST, servizi telematici e pagamenti: https://pst.giustizia.it/PST/it/services.page
- Agenzia delle Entrate, tassazione atti giudiziari: https://www1.agenziaentrate.gov.it/servizi/tassazioneattigiudiziari/registrazione.htm?passo=0
- INAIL, denuncia infortunio e malattia professionale: https://www.inail.it/portale/assicurazione/it/Datore-di-Lavoro/Impresa-con-dipendenti-industria-artigianato-terziario-altre-attivita/denunce-infortuni-e-malattie-professionali-impresa-con-dipendenti/denuncia-malattia-professionale-impresa-con-dipendenti.html
- INPS, ricorsi amministrativi: https://www.inps.it/it/it/dettaglio-scheda.it.schede-servizio-strumento.schede-servizi.ricorsi-amministrativi.html
- Registro Imprese, fonte camerale: https://www.vr.camcom.gov.it/content/il-registro-imprese
- Tribunale per i Minorenni, competenza per materia: https://tribmin-trento.giustizia.it/it/comp_per_materia.page
- Procura della Repubblica, negoziazione assistita famiglia: https://procura-roma.giustizia.it/it/nulla_osta_separaz_divorzi.page

## Implementazione collegata

- Runtime: `pct/guida_pratica/web_enrichment.py`.
- Servizio: `pct/guida_pratica/service.py` applica l'arricchimento a ogni scheda restituita.
- API: `/api/v1/ui/guida-pratica/<codice>` e `/api/guida/<codice>` restituiscono `fonti_verifica_web`, `presidi_operativi_integrativi` e `arricchimento_iusentra`.
- UI: `frontend/src/components/GuidaPraticaSidebar.tsx` mostra fonti e presidi.
- Lex: `lex/retrieval/sources/guida_pratica.py` espone fonti e presidi nelle evidenze conversazionali.
- Audit: `scripts/audit_guida_pratica_user_material_fields.py` controlla che fonti e presidi siano presenti in KB full, servizio, UI e Lex.
