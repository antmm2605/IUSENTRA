# Deposito: requisiti tecnici essenziali

Data: 25/08/2026

## Decisione operativa

La preparazione del deposito resta sempre disponibile per creare la sessione di lavoro e ordinare i documenti. L'invio resta bloccato soltanto da requisiti tecnici o procedurali obbligatori, determinati dal canale e dal profilo della pratica.

Non bloccano più il deposito né l'apertura del fascicolo:

- l'avvocato referente dello studio;
- l'accettazione del preventivo;
- la firma del conferimento;
- la registrazione di pagamento o acconto.

Queste informazioni restano nel Presidio del fascicolo come avvisi economici o organizzativi, con una prossima azione chiara e senza simulare un requisito ministeriale.

Restano bloccanti, quando applicabili al profilo, dati identificativi essenziali, ufficio e registro competenti, atto principale, procura se richiesta, integrità e conformità dei file, firma, dati della busta e requisiti del canale telematico.

## Verifica da eseguire

La prova visiva sulla pagina reale del fascicolo deve confermare che la lista `In preparazione` mostra solo blocchi tecnici/procedurali e che gli avvisi economici non impediscono il comando `Prepara deposito`.

## Notifica: ricerca destinatari

Nel percorso di notifica l'inserimento manuale è collocato subito dopo la pratica selezionata. Il filtro `Elenco pubblico PEC` limita risultati e interrogazioni locali alla fonte scelta. ReGIndE e Registro PP.AA./PST interrogano l'indice locale; per INI-PEC, Registro Imprese e INAD vengono mostrati solo gli indirizzi già associati a quella fonte e il percorso ufficiale guidato resta esplicito.

## Notifica: spazio di lavoro della relata

Nel pannello **Relata e attestazione** l'avvocato dispone di due comandi di vista, senza modificare dati o contenuto:

- **Chiudi/Apri laterale** nasconde o ripristina il catalogo modelli, l'esito e le fonti operative; lo stato resta nella pagina e non viene perso.
- **Tutto schermo/Riduci** concentra il flusso di compilazione nella superficie IUSENTRA; `Esc` torna alla vista normale.

Entrambi i comandi hanno etichetta visibile, tooltip, focus visibile e semantica ARIA. Non aprono finestre esterne e non avviano invii PEC.

## Elenco fascicoli: azioni rapide leggibili

Nelle viste **Schede** e **Compatta** le azioni `Apri`, `Modifica`, `Deposito`, `Notifica`, `PDF` ed `Elimina` mantengono sempre insieme icona e testo. La vista Schede usa celle uniformi sotto il fascicolo; la vista Compatta dedica alle azioni una riga propria, così i dati della pratica non vengono compressi e le etichette non si sovrappongono.

Prova visiva eseguita il 25/08/2026 su `http://127.0.0.1:8080/fascicoli`: verificate entrambe le viste, l'hover e il focus da tastiera su un comando rapido.
