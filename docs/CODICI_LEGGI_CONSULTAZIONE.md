# Codici e leggi — verifica locale del 10 ottobre 2026

Stato: pronta per la verifica dell’utente in locale; pubblicazione sul server sospesa su richiesta esplicita. I due deploy automatici e465a911a risultano annullati prima del passaggio di deploy. L’acquisizione finale delle fonti pubbliche è stata eseguita su un ramo isolato, senza trigger di deploy.

Obiettivo: consentire all’avvocato di scegliere codice/raccolta, trovare un articolo o parole nel testo e leggere il documento completo con collegamento ufficiale. Utenti: avvocati autorizzati ai permessi di consultazione. Rischi controllati: confusione tra codice civile e preleggi, etichette esterne XML errate, testo mancante ricostruito, perdita delle modifiche sul server, sovrapposizione con l’addestramento in corso.

Risultato locale: 162 raccolte, 28.209 articoli, 31 codici; inclusi 17 regolamenti UE e 75 articoli deontologici. I 13 atti mancanti dell’elenco ufficiale Normattiva sono stati acquisiti con identità XML e SHA256 verificati. Le componenti e gli articoli del decreto di approvazione sono separati dai codici allegati. Gli allegati non articolati restano nel pacchetto di fonti, separati dalla ricerca per numero di articolo.

Correzioni: 33 articoli aggiunti ai quattro codici da fonti ufficiali; 25 record strutturali sostituiti solo con corrispondenza univoca; due nomi esterni errati negli XML militari riallineati al numero nel corpo; alias duplicato 281nonies conservato in quarantena, articolo canonico 281novies mantenuto. Il numero 98-quinquies del d.lgs. 259/2003 resta marcato come sola intestazione ufficiale. 817 avvisi editoriali/fonti conservati, non classificati automaticamente come troncamenti. Le normalizzazioni tipografiche delle integrazioni conservano originali e impronte.

Interfaccia: React, menu Studio → Codici e leggi, ricerca indicizzata con accenti/apostrofi normalizzati, filtri effettivi per raccolta e atto, numero con suffisso o slash, paginazione, testo integrale oltre 1.800 caratteri, errori controllati, collegamenti Normattiva/EUR-Lex/GU/CNF e data distinta del consolidamento UE. La suddivisione in parti da 1.800 caratteri riguarda l’indice/RAG, non la lettura dell’articolo.

Verifica: 13 test Python mirati passati; suite frontend con 242 test JavaScript e controlli di contratti, grafica e Storybook passati; compilazione React passata. Qualità del pacchetto: zero segnalazioni strutturali del verificatore originale, zero testi vuoti/caratteri sostitutivi. Questa verifica tecnica non è una certificazione di vigenza legale di ogni disposizione.

Per Lex B: cartella e ZIP integrazione_fonti_lex_b_20261010_finale sotto Documenti/lexds_v3, con 162 file di raccolte, originali ufficiali, catalogo e manifest SHA256. Sono fonti per il ciclo successivo; nuovi esempi e assemblaggio del dataset restano da eseguire allora. L’addestramento attuale e i suoi checkpoint non sono stati modificati.

Pubblicazione futura: integrare solo i sorgenti della biblioteca, routing/menu e importatore, ricostruendo React sullo stato aggiornato che comprende gli altri lavori. Non copiare tutta la checkout né sostituire manifest/bundle del server con quelli locali senza riconciliazione. Verificare prima le modifiche concorrenti, poi test/CI e consenso dell’utente alla pagina locale. Nessun file PEC/editor/scadenziario è incluso nella patch di questa funzionalità.
