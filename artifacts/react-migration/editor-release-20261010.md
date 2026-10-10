# Editor — registro della preparazione del rilascio

Data: 10/10/2026. Incarico generale aperto. Versione candidata 2.437.0.

## Riscontri materiali prima del pacchetto definitivo

Browser reale visibile sulla copia Docker 127.0.0.1:8080. Documento controllato 515E26A7 nel fascicolo tecnico; fonte legale originale preservata.

- Attestazione DOCX allegata: importazione normale, esportazioni DOCX/PDF/RTF, salvataggio e riapertura. Tutta la singola pagina renderizzata osservata; confronto testo e coordinate delle parole con differenza massima 0 pt su questo caso. Questo esito non dimostra fedeltà universale né identità della superficie HTML modificabile.
- PDF originale: importazione normale, download diretto byte-identico (53606 byte, SHA256 5CB46F136FA1242226C65DA7AF474D2647B56555E8DC869FEC001026FCB94F0A). Barra compatta, eliminazione delle spiegazioni informative ripetute; protezioni reali conservate. Vista completa della pagina, firma ed elenco.
- Tabella con celle unite: aggiunta riga e testo, due Annulla e due Ripeti, cursore recuperato, Ctrl+Z/Ctrl+Y, salvataggio e riapertura; cinque righe e testo conservati. Prima prova negativa corretta con una cronologia unica di trenta modifiche.
- Anteprima: margine vuoto rifiutato esplicitamente, valori leggibili senza decimali superflui; chiusura durante aggiornamento non riapre la finestra. Vista intera della pagina a 50%.
- Elenco puntato trasformato in numerato e collegamento inserito dal pannello, salvataggio e riapertura confermati. Prima prova visiva negativa: stile generale applicava dimensioni da pulsante al link interno e marcatore numerico non visibile. Regole limitate al contenuto editor ripristinano link inline e numero sulla stessa linea.
- Vocabolario locale: scrivendo «L’avvocato esammina il documento.» compare il suggerimento «esamina». Prima proposta Lex cambiava il presente in passato: documento invariato, proposta inaccettabile. Prompt conservativo e verifica lessicale contro il vocabolario locale aggiunti. Nuova prova normale restituisce «L’avvocato esamina il documento.», senza applicazione automatica. Sei guardrail coprono cambio di tempo, negazione, importo e refuso ambiguo.
- Full screen e scroll superiore/inferiore provati nel Chrome reale. Prova IAB 390×844: toolbar scorrevole, documento accessibile a 100%, intero a 25%. Cattura tablet precedente non accettata per dimensioni/scalatura: resta aperta.

Guardrail: 68 test editor/HTML-DOCX/RTF positivi nella copia isolata; sei test linguistici positivi; tre test JS cronologia positivi. Typecheck e Ruff positivi. Build isolata 2597 moduli, 2,49 s. Nessun dato privato di prova incluso nel repository.

## Passaggi ancora richiesti

Installazione del pacchetto definitivo, nuova accettazione su 8080, CI e sincronizzazione dei due branch, confronto sorgenti runtime recuperati e deploy sullo stesso commit non ancora effettuati al momento di questo registro. Nessuna dichiarazione di conclusione del rilascio.

Fedeltà HTML globale, numerazioni personalizzate/continuazioni, varianti delle regioni e casi complessi di impaginazione restano aperti. Il registro non dichiara tutti i formati o tutti i documenti identici. CTU, sincronizzazione globale e altri punti dell’incarico restano separatamente aperti. EmbeddingGemma 300M e flusso firma/deposito/PEC preservati.

10/10/2026 — Direttiva successiva: pannello Suggerimenti italiani ridisposto in colonne, parole e alternative su righe leggibili, proposta separata e comandi interamente contenuti a destra. Prova materiale desktop positiva sulla copia reale; screenshot privato editor-language-panel-20261010.png. Chiusura normale osservata. La copia tramite browser restituisce conferma soltanto dopo la promessa Clipboard; prova del nuovo riscontro e responsive ancora in corso. Richieste linguistiche obsolete annullate quando cambia il testo o si chiude il pannello. Nessun deploy server.

10/10/2026 — Revisione italiana locale, ancora in rilascio. Nel Chrome reale su 8080: «esammina» selezionato dal rilievo, «esamina» applicato e salvato; riapertura conserva il testo corretto e cinque righe della tabella. Annulla della correzione provato separatamente. Difetto osservato: lo scroll verso il rilievo chiudeva il popup; corretto usando lo scroll istantaneo e chiusura su scorrimento dell'utente. Alternative nel riepilogo rese comandi applicabili.
Il controllo live, senza clic su Controlla documento, segnala apostrofo in Qual'è, accento in perche, e' al posto di è e spazio prima della virgola. Il pulsante è sostituisce realmente e' nel testo; salvataggio automatico osservato. Revisore LanguageTool 6.6 installato solo sul loopback locale da distribuzione ufficiale con SHA256 fissato; testo non inviato a servizi esterni. Revisione generale a blocchi con offset UTF-16, controllo delle risposte obsolete, RBAC e audit senza contenuto testuale. Non è una promessa di individuazione di ogni errore grammaticale: il caso di concordanza artificiale provato non produce rilievo. Persistenza completa delle altre correzioni, responsive, immagine definitiva e deploy restano da accettare. Guardrail: otto test mirati positivi, Ruff e typecheck positivi.
