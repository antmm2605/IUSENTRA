# Catalogazione documentale: matrice delle fonti e dei controlli

Ricognizione del 06/09/2026. Perimetro: lettura e classificazione dei documenti
del fascicolo, non modifica dei canali di deposito, notifica o firma.
La matrice è un requisito verificabile, non una dichiarazione di conformità
universale né una misura sperimentale dell'accuratezza dell'OCR.

## Regole comuni

Il catalogo distingue identità del documento, materia del fascicolo,
integrità del file, verifica crittografica ed efficacia giuridica. Una norma
collegata spiega una regola: non prova cosa contiene il file e non aumenta
la confidenza. Un'intestazione citata in motivazione non identifica l'atto.
La confidenza attuale è un punteggio euristico, non una probabilità calibrata.
Un valore del 95% non può essere imposto quando manca evidenza sufficiente.

| Ambito | Fonte ufficiale consultata | Applicazione al catalogo / controllo richiesto |
| --- | --- | --- |
| Identità, impronta, formato, classificazione, allegati e aggregazione | [AgID, Allegato 5](https://www.agid.gov.it/sites/default/files/repository_files/all.5_metadati.pdf), pagine 5–18 e 80–82 del PDF | Conservare identificativo, hash, versione, fascicolo proprietario e riferimenti alle prove. Usare i metadati pertinenti: non imporre automaticamente a uno studio privato la protocollazione propria delle PA. Non certificare conservazione a norma attraverso la sola catalogazione. |
| Originale, copia e duplicato | [CAD su Normattiva](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=005G0104&atto.dataPubblicazioneGazzetta=2005-05-16&tipoDettaglio=vigente), artt. 20, 22, 23 e 23-bis | Testo OCR e anteprima sono derivati: conservare il file acquisito. Un PDF estratto da CAdES non è per questo una firma verificata o un duplicato giuridicamente attestato. Il canale diretto Normattiva ha restituito errori in alcune richieste: non scambiare la pagina di errore per un testo normativo acquisito. |
| Atti, allegati, dati XML e ricevute dei portali | [PST, specifiche 2024 e rettifiche](https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3429), [testo delle specifiche](https://pst.giustizia.it/PST/resources/cms/documents/m_dg.DOG07.07082024.0004292.ID_SPECIFICHETECNICHE_DM_44_2011_FINALE_31_.pdf), artt. 15–19 | Distinguere PDF dell'atto, XML descrittivo, busta e ricevuta. Namespace e radice identificano una struttura, non ne certificano validità XSD, firma, deposito o accettazione. Le regole di invio e le rettifiche restano nel presidio telematico esistente; nessuna nuova automazione di invio in questa tranche. |
| Oggetto e materia PST | [PST, schemi ufficiali](https://pst.giustizia.it/PST/it/download.page), pacchetti XSD già versionati in questa repository | Risolvere una corrispondenza univoca per codice/descrizione ufficiale, registrando file dello schema e impronta. Non inventare il profilo dal prefisso del numero RG; non sovrascrivere scelte strutturate dell'avvocato. La voce 140011 identifica «Vendita di cose immobili». |
| Sentenza, ordinanza, decreto, verbale e atti di parte | [Codice di procedura civile](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443), [correttivo 164/2024](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.articolo.numero=3&atto.articolo.sottoArticolo=1&atto.articolo.tipoArticolo=0&atto.codiceRedazionale=24G00183&atto.dataPubblicazioneGazzetta=2024-11-11) | Usare intestazione e formule autonome concordanti. La formula solenne e il titolo di sentenza prevalgono sul contratto discusso; un generico dispositivo del giudice non basta per inventare «decreto» o «ordinanza». Non attribuire definitività, passaggio in giudicato o efficacia esecutiva dal solo titolo. |
| Attestazione di conformità, procura, indice e relata | CAD, CPC e [PST, specifiche e rettifiche](https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3429); fonti specifiche già nel registro applicativo | Classificare il documento contenitore senza trasformarlo nell'atto elencato. Il riconoscimento di un'attestazione o di una procura non ne verifica firme, poteri, completezza o uso processuale. Riutilizzare i controlli specifici esistenti per queste verifiche. |
| Ricevute e avvisi PEC | [D.M. 2 novembre 2005, art. 1](https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticoloDefault/originario?atto.codiceRedazionale=05A10742&atto.dataPubblicazioneGazzetta=2005-11-15&atto.tipoProvvedimento=DECRETO), D.P.R. 68/2005 art. 6 | Separare accettazione, non accettazione, presa in carico, avvenuta consegna e mancata consegna. Distinguere ricevuta completa, breve e sintetica quando il dato è presente. Il testo citato nel messaggio originale non cambia l'identità della ricevuta. OCR della ricevuta non sostituisce MIME, firma del gestore e correlazione del presidio PEC. |
| Fattura, proforma e XML FatturaPA | [FatturaPA, rappresentazione tabellare 1.2.2](https://www.fatturapa.gov.it/export/documenti/fatturapa/v1.2.2/Rappresentazione_Tabellare_FattOrdinaria_V1.2.2.pdf), [Agenzia delle Entrate, guida alla fatturazione elettronica](https://www1.agenziaentrate.gov.it/web_app_entrate/fatturazione_elettronica.html) | Numero alfanumerico, data, tipo documento, valuta e totale sono campi distinti. Preservare gli zeri iniziali. Leggere ogni corpo di un lotto XML, non solo il primo. Una proforma non prova emissione; un PDF non prova transito SdI, consegna o pagamento. L'estrazione non deve creare movimenti contabili. Il PDF tabellare è indicizzato dalla fonte ufficiale ma il recupero diretto ha risposto 403: nessuna asserzione di ultimo schema integralmente validato. |
| Mediazione: domanda, modulo, verbale, accordo e riservatezza | [D.Lgs. 28/2010, pubblicazione](https://www.gazzettaufficiale.it/eli/gu/2010/03/05/53/sg/pdf), [modifiche 149/2022](https://www.gazzettaufficiale.it/eli/gu/2022/10/17/243/so/38/sg/pdf), [correttivo 216/2024](https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticoloDefault/originario?atto.codiceRedazionale=25G00003&atto.dataPubblicazioneGazzetta=2025-01-10&atto.tipoProvvedimento=DECRETO+LEGISLATIVO) | Distinguere modulo non compilato, domanda, verbale ed eventuale accordo allegato. Mancata adesione, mancata partecipazione ed esito negativo non sono sinonimi. Non attribuire automaticamente efficacia esecutiva all'accordo. Riservatezza e limiti d'uso delle dichiarazioni restano da valutare: catalogare non autorizza condivisione o deposito. |
| Firma e certificati | [AgID, software di verifica](https://www.agid.gov.it/it/piattaforme/firma-elettronica-qualificata/software-verifica), [linee guida sulla firma qualificata](https://www.agid.gov.it/sites/agid/files/2024-06/Linee_guida_firma_elettronica_qualificata.pdf) | Riconoscere ed estrarre un contenitore CAdES è diverso dal verificarne firma e certificato. Non mostrare «firma valida» sulla base del nome, della parola «firmato» o della sola disponibilità del contenuto. Nessun cambio a Local Signer o verifica firme. |
| Dati personali e sicurezza | [GDPR](https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32016R0679), artt. 5, 25 e 32 | Elaborazione OCR locale al server applicativo, nessun documento privato a servizi OCR esterni, autorizzazioni tenant, minimizzazione dei dettagli esposti e audit delle correzioni. Le fonti pubbliche si consultano senza trasmettere contenuti del fascicolo. |
| Impiego professionale dell'IA | [Legge 132/2025](https://www.gazzettaufficiale.it/eli/id/2025/09/25/25G00143/sg), [testo ufficiale, art. 13](https://www.gazzettaufficiale.it/eli/gu/2025/09/25/223/sg/pdf) | Supporto alla prestazione intellettuale e informazione al cliente sull'uso dell'IA nei termini della norma. La classificazione resta motivata, correggibile e distinta dalle decisioni professionali; non dichiarare una percentuale di correttezza non misurata. |

## Matrice tecnica e accettazione

| Controllo | Stato al momento della ricognizione |
| --- | --- |
| Intestazione sentenza/attestazione prima degli atti citati | Codice e test mirati; osservato sul fascicolo locale DD242366. |
| File CAdES rinominato PDF, testo binario escluso | Implementato e provato sui file locali; originale non riscritto. |
| Tutte le pagine OCR, ordine e nessun limite di otto | Contratti automatici con 12 pagine; benchmark nativo separato documentato. |
| Salvataggio atomicamente coerente di classificazione e prove | Rollback SQLite e PostgreSQL vivo verificati; script governato in `scripts/verify_document_catalog_postgres.py`. |
| Conteggi SQL e aggiornamento parziale non presentato come successo | Modificato; riesame UI/gate della nuova versione in corso. |
| Documento soltanto censito dal portale | Nessuna classificazione dal nome; distinguere «Da acquisire» da coda OCR. Prova PIN separata. |
| Proforma, dati FatturaPA, eventi PEC e dettagli verificabili | Test positivi/negativi; XML controllato caricato e aperto nella UI locale, entrambi i corpi e dettagli osservati, anche preview mobile. Il solo XML artificiale è stato poi eliminato dalla UI; documenti originali intatti. Rilascio ancora aperto. |
| Procura di mediazione senza titolo, con dichiarazione iniziale di conferimento | Correzione v23 osservata sul DOCX reale del fascicolo, con sette riferimenti e originale aperto nel lettore. Il modulo con campi vuoti non è una procura già conferita. Test positivo e negativo contro citazioni in lettere. |
| Accuratezza universale, ogni documento senza revisione | Non dimostrata e non garantibile con l'aggiunta di fonti. Conservare revisioni motivate e casi non supportati espliciti. |

Le versioni normative storiche citate non diventano automaticamente testo
consolidato vigente. Le nuove regole devono avere casi positivi e negativi,
provenienza dell'estrazione e test tenant-aware. L'accettazione richiede la UI
reale locale dopo ricostruzione, poi gate e rilascio ordinato; ricerca e unit
test da soli non chiudono il lavoro.
