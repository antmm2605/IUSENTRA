# Revisione del sito commerciale, 04/10/2026

## Obiettivo e perimetro

Rendere il percorso più coinvolgente e dare un motivo concreto per proseguire
fino al fondo. Destinatari: avvocati e studi legali italiani che stanno
conoscendo IUSENTRA. Solo `sito-vendita/` sul branch commerciale; nessuna modifica
al gestionale, a dati, portali, firma, deployment Hetzner o branch gemelli.

## Analisi della pagina pubblicata prima delle modifiche

URL osservato: https://iusentra-sito-vendita.up.railway.app/.
La pagina rispondeva HTTP 200, senza overflow a 1440px. Esaminati apertura e
scorrimento completo nel browser Chromium.

- Il titolo astratto non spiegava immediatamente il collegamento tra i moduli.
- La catena animata attenuava molto i testi e ricominciava senza intervento del visitatore.
- Cifre, tabella, giornata e inventario anticipavano molte informazioni ripetute.
- La giornata tipo aveva una lunga colonna di testo e una grande area inutilizzata a destra.
- Le dieci schede avanzavano automaticamente ogni sette secondi, interrompendo la lettura.
- Prezzi con importi vuoti, indicazione «Il più scelto» senza evidenza e modulo demo senza invio indebolivano il finale.

L'utente ha chiarito che gli ordini non sono aperti e sono in corso ulteriori
verifiche prima del rilascio. La chiusura deve rappresentare questo stato.

## Scelte applicate

- Identità notte legale, blu e oro mantenuta; titolo concreto e testo leggibile.
- Esempio PEC su richiesta, stati separati di preparazione, conferma e ripetizione.
- Scelta iniziale con risposta contestuale, senza cambiare la posizione di scroll.
- Racconto in tre scene, illustrazioni coerenti della stessa pratica e indice desktop.
- Vetrina a controllo manuale, navigazione tastiera e scorrimento solo orizzontale delle schede mobili.
- Confronto ridotto a quattro passaggi, altre otto funzioni disponibili su richiesta.
- Riferimenti normativi in un dettaglio consultabile, senza nascondere il ruolo decisionale dell'avvocato.
- Piani in definizione senza prezzi inventati o popolarità non dimostrata.
- Chiusura con riepilogo della preferenza e ritorno alla funzione scelta; nessuna raccolta dati o falsa prenotazione.
- Contenuti leggibili senza JavaScript, animazioni ridotte e focus visibile.
- URL asset con versione per evitare CSS/JS precedenti nelle cache dopo il deploy.

Rischio principale: far sembrare l'illustrazione un'operazione reale o suggerire
che gli ordini siano già aperti. Mitigazione: testi espliciti, nessun invio e
stato pre-rilascio nel finale. Non introdotti numeri di risparmio, testimonianze
inventate o promesse di maggiore permanenza già misurata.

## Criterio keep/discard

Keep se i percorsi locali funzionano, i contenuti restano accessibili e
leggibili a tutte le larghezze, la selezione resta coerente fino al fondo e il
sito pubblicato coincide con il commit. Discard o correzione se una nuova
interazione interrompe lo scroll, crea overflow, perde contenuti o finge un invio.

## Verifiche

Risultati e stato della pubblicazione vengono aggiunti dopo i controlli.
La verifica sulla macchina personale dell'utente non è stata eseguita; le prove
Chromium nell'ambiente di lavoro sono controlli tecnici e visivi di sviluppo,
non un'accettazione materiale sulla macchina reale dell'utente.

Controlli di sviluppo eseguiti con esito positivo:

- `node --check sito-vendita/assets/app.js` e `git diff --check`.
- `verifica_sito.py` a 1440×1000, 1366×768, 820×1180, 390×844 e 320×740.
- Preparazione, conferma e ripetizione della PEC illustrata.
- Tutte le tre preferenze, coerenza della vetrina e del riepilogo, assenza di salti di scroll.
- Tutte le dieci schede, frecce tastiera, Home/End e permanenza della selezione oltre sette secondi.
- Espansione/richiusura delle funzioni, dieci riferimenti normativi e sette FAQ.
- Ritorno alla preferenza dal finale, presenza dello stato pre-rilascio e assenza di form di invio.
- Scorrimento completo, destinazioni dei link, nessun overflow orizzontale e nessun errore JavaScript.
- Animazioni ridotte e disponibilità di tutte le funzioni senza JavaScript.
- Screenshot esaminati per apertura, racconto, vetrina e layout mobile.

Esito di sviluppo: keep. La permanenza effettiva dei visitatori non è ancora
misurata. La verifica della versione pubblicata verrà eseguita sul dominio
Railway dopo il push; non è equiparata all'accettazione sulla macchina dell'utente.

Prima pubblicazione verificata sul dominio Railway: HTML, CSS e JavaScript
corrispondenti byte per byte al commit `36d9761`. Durante la verifica visiva
mobile individuati e rifiniti due dettagli: allineamento orizzontale della
scheda preselezionata e testo della toolbar dell'editor che ora va a capo.
I percorsi rifiniti sono stati riprovati a 320, 390, 820 e 1440px, inclusi
ritorno dal finale e tastiera. Il controllo della visibilità della scheda
selezionata è stato aggiunto allo script ripetibile. La versione degli asset
è aggiornata anche per questa rifinitura.

## Ripristino del movimento nelle anteprime

Su richiesta dell’utente, ripristinate le animazioni illustrative di scadenze,
cursore dell’editor, barra di calcolo, onda e frasi vocali, ricevute del deposito.
Partono quando il pannello entra in vista, con sequenze finite e senza cambio
automatico della scheda. Ricevute e testi rimangono leggibili al termine.
Le scene del racconto entrano con lo stesso movimento delle altre sezioni.
Il movimento ridotto mantiene le illustrazioni statiche.


## Primo impatto e continuità dello scorrimento

Apertura riscritta attorno al tempo dell’avvocato: “Il tuo tempo. Di nuovo tuo.”
Confronto interattivo tra passaggi separati e pratica collegata, mantenendo
visibili e leggibili tutti i passaggi dell’esempio. Segnale luminoso e icone
animate all’ingresso; nessun dato reale o promessa di risparmio quantificata.
Sul telefono anteprima e confronto sono già presenti nella prima schermata.
Il racconto prosegue con un esempio vocale attivabile, senza microfono o AI
reale, prima delle dieci funzioni. Inviti e testi anticipano il passo seguente.
Resta esplicito che ordini e acquisti non sono aperti.
Verifica browser comprende confronto reversibile, esempio vocale, cinque
formati di schermo, tastiera, scorrimento, movimento ridotto e lettura senza JS.
La curiosità e la permanenza effettiva richiedono osservazione di visitatori
reali: i controlli tecnici verificano il comportamento del sito.

## Revisione con Impeccable 4.5 — esperienza completa

Apertura trasformata in una pratica a sei nodi selezionabili: ogni nodo
racconta la relazione tra PEC, lettura, fascicolo, termini, agenda e cliente.
La sequenza illustrativa e la conferma rimangono separate. La composizione
usa il blu e l’oro già presenti, con tipografia editoriale nei tre momenti
della giornata. Rimossi la griglia decorativa del fondale e i titoletti di
sezione ripetitivi. Il filo della pratica segue lo scorrimento normale.

Aggiunte tre interazioni reversibili nelle anteprime: documento cliente
caricato, dati del fascicolo evidenziati nell’atto, PEC e ricevuta collegate.
Gli esiti descrivono esplicitamente una simulazione. L’indice di esplorazione
compare dopo l’apertura e lascia libera la chiusura. Gli eventi di scorrimento
sono riuniti in un singolo aggiornamento per frame; nessuna nuova dipendenza.

Creati contesti PRODUCT.md e DESIGN.md specifici del sito commerciale: il
sistema del gestionale e il suo deploy restano separati. Rilascio in
preparazione, nessun ordine o prenotazione attivo.

Il detector Impeccable è stato eseguito una volta: 144 avvisi consultivi e 77
warning, prevalentemente confronto con il design operativo ereditato e
interpretazione dei fondi trasparenti. Corretti la dimensione del testo della
nuova navigazione e il suo focus; rimossa la griglia decorativa effettiva.
Le differenze tipografiche della superficie commerciale sono intenzionali e
documentate nel suo DESIGN.md. Non si dichiara il detector privo di avvisi né
una certificazione completa WCAG. Ispezione visiva con un passaggio di
correzione e una conferma; verifiche funzionali sui cinque formati di schermo.
