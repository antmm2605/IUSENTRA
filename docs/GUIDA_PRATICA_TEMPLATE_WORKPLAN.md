# Piano Guida Pratica, catalogo template e compilatore atti

Aggiornato: 2026-05-22.

Questo documento è memoria operativa vincolante per la tranche Guida Pratica + template + compilatore atti.

Non iniziare l'integrazione nell'app reale prima di aver mostrato e approvato la visualizzazione.

## Obiettivo

Trasformare la Guida Pratica in un piano assistito della pratica:

- parte sempre dal fascicolo aperto;
- legge dati già presenti nel fascicolo;
- usa il catalogo template come fonte governata;
- consente di generare il documento richiesto dalla guida;
- mantiene la guida aperta durante la generazione;
- salva il documento nel fascicolo;
- marca la voce della guida come completata;
- arricchisce Lex con guida, template, fonti e stato della pratica.

## Errore da non ripetere

Il generatore non deve chiedere campi già presenti nel fascicolo.

Cliente, ufficio, parti, oggetto, valore, rito, fase, documenti e dati pratica vengono definiti nell'apertura o gestione del fascicolo. La finestra di generazione deve mostrarli come dati acquisiti, non come nuovo form da compilare.

Se un dato manca:

- il sistema non lo inventa;
- il generatore non crea un campo isolato;
- la UI rimanda alla sezione corretta della scheda fascicolo;
- la guida segnala la mancanza come controllo operativo.

## Sequenza corretta dal fascicolo

1. L'avvocato apre o crea il fascicolo.
2. Il fascicolo acquisisce cliente, parti, ufficio, oggetto pratica, codice oggetto, valore, rito, fase, documenti e scadenze.
3. La Guida Pratica si aggancia al fascicolo come opzione facoltativa.
4. La guida legge il contesto del fascicolo.
5. La guida propone un piano assistito: controlli, documenti, allegati, fonti e avvertenze.
6. Quando serve un documento, la guida interroga il catalogo template.
7. Il catalogo template seleziona il modello coerente.
8. Il compilatore atti riceve dati del fascicolo, template, guida curata e fonti.
9. La finestra di generazione si apre sopra il fascicolo senza chiudere la guida.
10. La finestra mostra dati acquisiti, controlli mancanti, anteprima e azioni.
11. L'avvocato conferma.
12. Il documento viene salvato nel fascicolo.
13. La guida marca la voce come completa.
14. Lex conosce lo stato aggiornato.

## Catalogo template

Il catalogo template è la fonte governata. La Guida Pratica non deve creare documenti fuori catalogo quando esiste un template applicabile.

Stato rilevato:

- catalogo master: 420 template;
- core: 122;
- advanced: 186;
- specialist: 92;
- studio interno: 20.

Ogni voce documentale della guida deve collegare:

- `template_id`;
- `link_compilatore_code`;
- titolo template;
- area, rito, fase e canale telematico;
- depositabilità;
- campi richiesti;
- dati fascicolo usati;
- allegati essenziali;
- controlli redazionali;
- controlli deposito, se pertinenti;
- fonti usate per arricchire;
- stato nella guida.

## Impaginazione: modello PDF

Il modello fornito dall'utente (`modello da seguire per templeate.pdf`) è il riferimento di impaginazione.

La visualizzazione mostrata finora non è ancora identica. In particolare l'intestazione studio è stata centrata e ingrandita, mentre nel PDF è posizionata più in alto e più a sinistra.

Misure estratte dalla prima pagina del PDF:

- formato pagina: A4, 595,32 x 842,04 punti;
- intestazione studio: `x=77,9`, `y=6,5`, larghezza `194,3`, altezza `79,2`;
- ufficio giudiziario: `x=132,6`, `y=130,3`, larghezza `269,6`, altezza `18,8`;
- titolo atto riga 1: `x=192,9`, `y=157,8`, larghezza `152,7`, altezza `14,0`;
- titolo atto riga 2: `x=179,4`, `y=180,8`, larghezza `175,5`, altezza `14,0`;
- prima riga corpo: `x=79,5`, `y=204,5`, larghezza `374,3`, altezza `13,3`;
- larghezza colonna corpo: circa `374,5` punti;
- testo verticale firma digitale: `x=577,8`, `y=381,1`, larghezza `9,6`, altezza `420,9`;
- blocco firma digitale visibile: `x=445,5`, `y=6,8`, larghezza `142,5`, altezza `121,6`;
- immagine/timbro firma digitale: `x=446,5`, `y=0,9`, larghezza `148,0`, altezza `143,1`.

La firma digitale visibile e il timbro del certificatore non devono essere confusi con il layout base del template. Sono un overlay del processo di firma. Il compilatore atti deve produrre l'atto base con impaginazione coerente; l'eventuale firma visibile si applica dopo, con regole separate.

## Regola per il compilatore atti

Il compilatore atti deve usare lo stesso profilo di impaginazione per tutti i template.

Non sono ammessi template con impaginazioni divergenti salvo eccezione giuridica documentata.

Il profilo unico deve includere:

- formato A4;
- intestazione studio nella posizione del PDF modello;
- ufficio giudiziario nella posizione del PDF modello;
- titolo atto centrato come nel PDF modello;
- corpo con colonna e interlinea coerenti al PDF modello;
- sezioni interne centrate;
- chiusura e firma coerenti;
- nessuna estetica moderna nel documento finale;
- nessun placeholder visibile se il dato è già nel fascicolo;
- nessun dato inventato se il dato manca.

## Visualizzazione da mostrare prima dell'integrazione

Prima di iniziare l'integrazione reale bisogna mostrare:

1. Fascicolo aperto con guida laterale.
2. Guida che propone documento dal catalogo template.
3. Finestra generazione aperta senza chiudere la guida.
4. Dati del fascicolo mostrati come acquisiti.
5. Avviso operativo se manca un dato, con rinvio alla scheda fascicolo.
6. Anteprima documento con intestazione studio nella stessa posizione del PDF.
7. Anteprima documento con dimensioni coerenti al PDF.
8. Stato dopo conferma: documento salvato e voce guida completata.
9. Stato guida nascosta: fascicolo pienamente operativo.
10. Stato fascicolo senza guida: nessun blocco.

Solo dopo approvazione della visualizzazione si passa all'implementazione.

## Arricchimento contenutistico

Il lavoro non deve limitarsi a collegare template e guida. Ogni scheda deve essere rafforzata con fonti ufficiali e trasformata in contenuto pratico per l'avvocato.

Fonti ufficiali iniziali:

- Normattiva, Codice civile;
- Normattiva, Codice di procedura civile;
- Normattiva, D.Lgs. 10 ottobre 2022, n. 149;
- Normattiva, D.Lgs. 4 marzo 2010, n. 28;
- Normattiva, D.L. 12 settembre 2014, n. 132;
- Normattiva, D.P.R. 30 maggio 2002, n. 115;
- Normattiva, D.M. Giustizia 21 febbraio 2011, n. 44;
- Portale Servizi Telematici del Ministero della Giustizia;
- schemi XSD e note di modifica PST;
- documentazione interna `docs/specs/ministero/`.

Ogni arricchimento deve produrre:

- prima verifica da fare;
- presupposti;
- competenza;
- rito;
- condizioni di procedibilità;
- struttura dell'atto;
- documenti essenziali;
- allegati;
- controlli deposito, se pertinenti;
- avvisi pratici;
- motivazione della scelta del template;
- domande utili che Lex può usare in modo conversazionale.

## Lex

Lex deve conoscere:

- fascicolo;
- guida pratica;
- catalogo template;
- template scelto;
- fonti usate;
- documenti generati;
- stato del piano assistito.

Lex deve parlare con l'avvocato in modo conversazionale, senza trasformare la guida in un blocco.

## Piano di lavoro

### Fase 1: Visualizzazione approvata

- Correggere mockup con misure reali del PDF.
- Mostrare header/intestazione nella posizione corretta.
- Mostrare flusso da fascicolo aperto.
- Mostrare generazione senza campi duplicati.
- Mostrare completamento guida.
- Attendere approvazione utente.

### Fase 2: Analisi codice

- Analizzare catalogo template e binding compilatore.
- Analizzare flusso apertura fascicolo.
- Analizzare Guida Pratica esistente.
- Analizzare compilatore atti e renderer documento.
- Analizzare salvataggio documenti nel fascicolo.
- Analizzare integrazione Lex.

### Fase 3: Layout unico

- Definire profilo layout base.
- Applicarlo al compilatore atti.
- Garantire che tutti i template passino dal profilo unico.
- Separare firma visibile e timbri digitali dal corpo base dell'atto.

### Fase 4: Guida + catalogo template

- Collegare documenti richiesti dalla guida al catalogo template.
- Usare `template_id` e `link_compilatore_code`.
- Mostrare template suggerito e motivazione.
- Evitare generazione fuori catalogo se esiste un modello coerente.

### Fase 5: Generazione assistita

- Aprire finestra sopra fascicolo e guida.
- Usare dati fascicolo in sola lettura.
- Mostrare dati mancanti come controlli.
- Salvare bozza o documento finale nel fascicolo.
- Aggiornare stato guida.

### Fase 6: Arricchimento e Lex

- Ampliare schede con fonti ufficiali.
- Inserire linguaggio operativo per avvocato.
- Rendere la guida leggibile a Lex.
- Rendere Lex consapevole dello stato del piano assistito.

### Fase 7: Test e audit

- Audit 420 template master.
- Audit binding template-compilatore.
- Audit layout su template rappresentativi e poi su catalogo completo.
- Test fascicolo: nessun dato duplicato richiesto.
- Test guida facoltativa: nessun blocco se nascosta.
- Test generazione: salvataggio nel fascicolo.
- Test Lex: risposta su guida, template e documento.
- Test browser desktop, tablet e mobile.
- Test regressione compilatore atti.

## Criteri di completamento

Il lavoro è completo solo se:

- la visualizzazione è approvata;
- il fascicolo resta il punto di partenza;
- il generatore non chiede dati già presenti;
- tutti i template usano il profilo comune;
- il compilatore atti usa la stessa impaginazione;
- la Guida Pratica resta facoltativa;
- Lex conosce guida e documenti;
- il catalogo template è governato;
- gli audit non rilevano incoerenze;
- i test sono documentati.
