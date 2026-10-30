# Release 2.461.0

- Pacchetto per addestrare sul PC dello studio il modello di catalogazione (autorizzazione dell'avvocato del 30/10/2026): testi dei documenti pseudonimizzati (nomi noti al fascicolo e preceduti da titolo, indirizzi, nascita, codice fiscale, partita IVA, IBAN, contatti, numero di ruolo), codici opachi, corrispondenze solo sul server.
- Documenti inventati per tutte le voci del catalogo (regole di titolo e voci riconosciute dal contenuto), accettati solo se il classificatore completo del catalogo assegna la voce prevista e la citazione è verificata.
- Formato della seconda lettura di Lex (domanda e risposta JSON), gruppi di addestramento, verifica, decisioni dell'avvocato, banco inventato e proposte da rivedere.
- Script del PC in tools/addestramento_catalogo (fuori dalle dipendenze del prodotto): QLoRA per Qwen 4B e Spark-X2.5 4B, misura e banco di prova che confronta regole, Spark del catalogo, classificatore lineare e modelli prima e dopo l'addestramento.

## Base normativa
- GDPR 2016/679 art. 4, n. 5 (pseudonimizzazione), art. 25 e art. 32: i testi lasciano il server solo pseudonimizzati, per l'addestramento autorizzato dall'avvocato sul PC dello studio, e si cancellano a fine lavoro.
- Art. 3 D.M. 44/2011 e art. 20 CAD: si leggono solo i testi già estratti e registrati dal catalogo.
- Gli esempi inventati portano l'etichetta che le regole governate del catalogo assegnano: nessuna voce scelta liberamente.

## Verifiche
- tests/test_addestramento_catalogo.py: pseudonimizzazione, esempi inventati verificati dal catalogo, citazioni, esportazione, funzioni del PC e banco di prova.
