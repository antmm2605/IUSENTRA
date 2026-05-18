# Percorso obbligatorio per arrivare alla risposta di Lex AI

Data di registrazione: 18 maggio 2026.

Questo documento serve a impedire risposte generiche quando una domanda ha già
un riferimento ufficiale nel database. Ogni passaggio deve essere verificabile:
se un punto non funziona, Lex deve dire quale punto è saltato, non rispondere
con un finto completamento.

## Caso guida

Domanda utente:

```text
Quale allegato ufficiale ha la questione penale R.G. 9926/2026?
```

Evidenza ufficiale già acquisita:

- pagina Cassazione: `https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194`;
- allegato ufficiale: `Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf`;
- titolo allegato: `Ordinanza di rimessione`;
- testo OCR salvato nel database;
- hash SHA-256 salvato;
- nota obbligatoria: la domanda scrive `9926/2026`, mentre il documento ufficiale
  acquisito riporta `9966/2026`. Lex deve segnalare la discrepanza e non deve
  fingere che i due numeri siano identici.

Risposta minima attesa:

```text
Ho trovato una fonte ufficiale Cassazione collegata. L'allegato ufficiale è
"Ordinanza di rimessione", PDF:
https://www.cortedicassazione.it/resources/cms/documents/Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf

Attenzione: nella domanda compare R.G. 9926/2026, mentre nell'allegato ufficiale
acquisito risulta R.G. 9966/2026. Va verificato se è un refuso o se si cerca un
altro procedimento.
```

## Passaggi obbligatori

1. L'utente scrive la domanda nel widget Lex.
   - Il testo non deve essere modificato in modo distruttivo.
   - Numeri, sigle e URL devono restare disponibili: `R.G.`, `9926/2026`,
     `QSP50194`, `Cassazione`, `allegato`, `ordinanza`, `PDF`.

2. Il frontend invia la richiesta all'endpoint chat.
   - Il widget deve inviare domanda, route corrente, eventuale fascicolo attivo,
     tenant e contesto autorizzato.
   - La UI non deve sostituire una risposta tecnica con un messaggio generico se
     il backend restituisce sorgenti o lacune.

3. Il backend costruisce il contesto operativo.
   - Vengono risolti utente, studio e tenant.
   - I permessi decidono quali archivi possono essere consultati.
   - La domanda non deve uscire dallo studio senza percorso governato.

4. Il router classifica la domanda.
   - Se la domanda contiene segnali come `Cassazione`, `QSP`, `R.G.`,
     `questione penale`, `allegato ufficiale`, `ordinanza di rimessione`,
     `circolare`, `messaggio`, `Gazzetta`, `Normattiva` o `fonte ufficiale`,
     deve usare la rotta delle fonti ufficiali e degli aggiornamenti legali.
   - Non deve usare `documenti collegati` salvo richiesta esplicita di documenti
     del fascicolo interno o allegati caricati dallo studio.

5. Il servizio operativo esegue gli strumenti della rotta scelta.
   - Per fonti legali deve interrogare almeno:
     - inventario legal intelligence;
     - archivio aggiornamenti legali;
     - catalogo fonti ufficiali.
   - Il percorso decisivo per questo caso è l'archivio aggiornamenti legali.

6. L'archivio aggiornamenti legali interroga il database.
   - La ricerca deve usare titolo, URL, fonte, estratto, testo OCR, hash,
     `attachment_url`, `attachments_json` e numero R.G.
   - Se la domanda chiede un allegato, i risultati con `attachment_url` e testo
     OCR reale devono essere promossi prima della pagina generica.

7. Il database deve restituire prove reali, non solo riferimenti.
   - Prova minima valida:
     - URL pagina ufficiale;
     - URL allegato ufficiale;
     - titolo allegato;
     - estratto leggibile;
     - hash o metadato di download;
     - stato della verifica.
   - Se manca il testo OCR ma esistono URL e hash, Lex deve dirlo chiaramente.

8. Il compositore costruisce una risposta leggibile.
   - Deve citare il nome dell'allegato e il link ufficiale.
   - Deve indicare se la fonte è Cassazione, Gazzetta, INPS, Normattiva o altra
     fonte riconosciuta.
   - Deve evidenziare le discrepanze, per esempio `9926/2026` contro
     `9966/2026`.
   - Non deve limitarsi a contare le fonti trovate.

9. La risposta torna al widget Lex.
   - Il testo deve essere impaginato in modo leggibile.
   - I link devono essere cliccabili.
   - Non devono comparire messaggi come `Non ho trovato dati reali sufficienti`
     quando il database ha restituito un allegato ufficiale valido.

10. L'audit registra cosa è stato consultato.
    - Devono essere tracciati rotta scelta, strumenti chiamati, numero risultati,
      sorgenti, eventuali lacune e motivo di blocco.
    - Se viene usata la rotta sbagliata, il test deve fallire.

## Ricerca web libera manuale

La ricerca web libera non deve essere un job, una pianificazione o una coda.
Parte solo dalla domanda Lex quando l'utente attiva il comando `Web libero` nel
widget.

Passaggi obbligatori:

1. Il widget invia insieme alla singola domanda:
   - `free_web_enabled=true`;
   - `force_free_web_search=true`;
   - `public_web_forced=true`;
   - `web_execution_requested=true`;
   - `source_mode=free_web`.
2. Il backend applica questi flag solo a quella richiesta.
3. Lex continua a interrogare prima gli archivi interni utili, poi esegue la
   ricerca web libera manuale se serve integrare risultati.
4. I risultati web liberi restano distinti dalle fonti ufficiali già acquisite:
   quando una pagina o un allegato è utile, va acquisito nell'archivio dello
   studio per diventare fonte stabile interrogabile.
5. La console pianificazioni non deve creare, avviare o mostrare job per questa
   funzione.

## Prove prima di dichiarare risolto

1. Test del router:
   - la domanda `Quale allegato ufficiale ha la questione penale R.G. 9926/2026?`
     deve andare alle fonti ufficiali, non a `documenti_fascicolo`.

2. Test del repository:
   - la stessa domanda deve restituire come primo risultato l'allegato
     `Ordinanza di rimessione` con URL PDF ufficiale.

3. Test del compositore:
   - la risposta deve contenere `Ordinanza di rimessione`;
   - deve contenere il link PDF;
   - deve segnalare la discrepanza `9926/2026` / `9966/2026` quando presente;
   - non deve contenere `Non ho trovato dati reali sufficienti`.

4. Test end-to-end del servizio Lex:
   - chiamata con lo stesso testo della domanda reale;
   - verifica della rotta;
   - verifica del testo finale;
   - verifica delle sorgenti restituite.

5. Verifica produzione:
   - il container deve avere la versione corretta;
   - il database di produzione deve contenere pagina, PDF, OCR e hash;
   - la domanda reale deve rispondere con allegato e nota sulla discrepanza;
   - il deploy deve rispettare `no backup`.

## Regola di blocco

Il lavoro non può essere dichiarato chiuso se uno solo di questi punti resta
vero:

- la domanda viene classificata come `documenti collegati`;
- il repository trova l'allegato ma Lex non lo usa;
- la risposta non mostra il link ufficiale;
- la risposta ignora la differenza tra `9926/2026` e `9966/2026`;
- il widget mostra ancora `Non ho trovato dati reali sufficienti` per questo
  caso.
