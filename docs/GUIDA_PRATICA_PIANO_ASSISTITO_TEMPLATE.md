# Guida Pratica, catalogo template e piano assistito della pratica

Aggiornato: 2026-05-22.

## Decisione di prodotto

La Guida Pratica non sostituisce il fascicolo e non crea un flusso parallelo. Il percorso corretto parte sempre dall'apertura del fascicolo.

Il fascicolo è la fonte operativa principale: cliente, parti, ufficio, oggetto pratica, codice oggetto, valore, rito, fase, documenti già presenti, scadenze e note sono dati del fascicolo. La Guida Pratica legge questi dati, li interpreta e propone controlli, documenti e passaggi operativi.

Il generatore documenti non deve mostrare una sezione generica "campi da completare" per dati già presenti nel fascicolo. Deve invece mostrare:

- dati acquisiti dal fascicolo, in sola lettura;
- eventuali dati mancanti o incoerenti, con rinvio alla scheda fascicolo;
- template selezionato dal catalogo ufficiale interno;
- anteprima dell'atto con impaginazione uniforme;
- conferma finale dell'avvocato prima del salvataggio.

Se un dato manca, il sistema non deve inventarlo e non deve chiederlo in modo isolato dentro la finestra di generazione. Deve riportare l'avvocato alla sezione corretta del fascicolo.

## Sequenza corretta

1. L'avvocato apre o crea un fascicolo.
2. Nella scheda fascicolo vengono definiti almeno oggetto pratica, cliente, parti, ufficio, fase e dati necessari alla gestione.
3. La Guida Pratica si aggancia al fascicolo come opzione facoltativa.
4. La guida legge oggetto, codice e contesto del fascicolo.
5. La guida propone un piano assistito: controlli, documenti, allegati, avvertenze, fonti e passaggi.
6. Quando un documento è richiesto, la guida interroga il catalogo template.
7. Il catalogo template resta la fonte: 420 template master, con binding al compilatore operativo.
8. Il documento viene generato con dati del fascicolo, regole del template, contenuto curato della Guida Pratica e conoscenza di Lex.
9. La finestra di generazione si apre sopra il fascicolo senza chiudere la guida.
10. La guida resta visibile sotto o a lato, così l'avvocato non perde il piano assistito.
11. Dopo la conferma, il documento viene salvato nel fascicolo.
12. La Guida Pratica marca quel passaggio come completato.

## Regola sul catalogo template

Il catalogo template non è un accessorio della Guida Pratica. È la fonte governata per la generazione documentale.

Il piano assistito deve collegare ogni voce documentale della guida a:

- `template_id` del catalogo master;
- `link_compilatore_code`;
- area, rito, fase, canale telematico e depositabilità;
- campi richiesti dal template;
- dati del fascicolo usati per la precompilazione;
- allegati essenziali e controlli di deposito, quando pertinenti;
- fonti normative o operative usate per arricchire la scheda.

## Regola sull'impaginazione

L'impaginazione di tutti i template deve seguire un profilo unico, derivato dal modello PDF fornito dall'utente (`modello da seguire per templeate.pdf`). La stessa impaginazione deve essere usata anche dal compilatore atti.

Il profilo comune deve includere:

- formato A4;
- intestazione studio centrata in alto;
- nome studio in maiuscolo e grassetto;
- nome avvocato e qualifica in stile professionale;
- indirizzo, telefono, codice fiscale, partita IVA e PEC in intestazione;
- ufficio giudiziario centrato;
- titolo dell'atto centrato;
- corpo dell'atto in stile tradizionale da studio legale;
- paragrafi giustificati;
- titoli interni centrati, ad esempio "Premesse", "Motivi", "Conclusioni";
- firma finale coerente;
- nessuna impaginazione diversa per singolo template salvo necessità giuridica specifica documentata.

Gli elementi di firma digitale visibile o marcatura del PDF firmato non devono essere confusi con l'impaginazione del template. Se la firma produce timbri o marcature, sono parte del processo di firma, non del corpo base dell'atto.

## Arricchimento contenutistico obbligatorio

Per rafforzare i template e la Guida Pratica non basta il catalogo interno. Ogni scheda deve essere arricchita con fonti ufficiali e trasformata in controlli pratici.

Fonti ufficiali iniziali da usare:

- Normattiva, Codice civile e Codice di procedura civile;
- Normattiva, D.Lgs. 10 ottobre 2022, n. 149, riforma processo civile;
- Normattiva, D.Lgs. 4 marzo 2010, n. 28, mediazione civile e commerciale;
- Normattiva, D.L. 12 settembre 2014, n. 132, negoziazione assistita;
- Normattiva, D.P.R. 30 maggio 2002, n. 115, spese di giustizia e contributo unificato;
- Normattiva, D.M. Giustizia 21 febbraio 2011, n. 44, processo telematico;
- Portale Servizi Telematici del Ministero della Giustizia, specifiche tecniche DM 44/2011;
- Portale Servizi Telematici del Ministero della Giustizia, schemi XSD e note di modifica.

L'arricchimento deve produrre contenuto operativo per l'avvocato:

- prima cosa da verificare;
- presupposti;
- rito e competenza;
- struttura dell'atto;
- documenti da allegare;
- condizioni di procedibilità;
- rischi redazionali;
- controlli di deposito quando pertinenti;
- domande che Lex può usare in modo conversazionale;
- motivazione della scelta del template.

## Regola Lex

Lex deve conoscere:

- il fascicolo;
- il catalogo template;
- il template scelto;
- la Guida Pratica curata;
- le fonti usate per arricchire la guida;
- lo stato dei documenti generati.

Lex deve parlare in modo conversazionale con l'avvocato e spiegare cosa manca o cosa è stato completato senza imporre blocchi arbitrari.

## Regola UX

La Guida Pratica è facoltativa. Se l'avvocato non vuole usarla, il fascicolo resta pienamente operativo.

Quando l'avvocato genera un documento dal piano assistito:

- la guida non si chiude;
- il fascicolo non viene sostituito;
- la finestra di generazione mostra dati acquisiti dal fascicolo, non campi duplicati;
- l'anteprima documento usa il profilo di impaginazione unico;
- la conferma salva il documento e aggiorna il piano assistito.

## Test e audit richiesti prima dell'integrazione finale

Prima di dichiarare completa l'integrazione servono:

- audit catalogo: nessun template master senza binding governato;
- audit layout: tutti i template generano con il profilo comune;
- audit fascicolo: nessun dato già presente viene richiesto di nuovo nel generatore;
- audit guida: nessun blocco se la guida è nascosta o non usata;
- audit Lex: Lex legge guida, template e stato pratica;
- test browser del flusso fascicolo, guida, generazione, conferma, rientro;
- test di salvataggio documento nel fascicolo;
- test di regressione sul compilatore atti.
