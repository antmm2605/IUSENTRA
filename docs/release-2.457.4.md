# Verifica della copertura della release 2.457.4

La CI di c241b305 ha superato tutti i test, ma ha bloccato il confronto finale: quattro moduli aggiunti al perimetro misurato non erano dichiarati né sufficientemente esercitati dalla suite critica. Il server non è stato promosso e il backup del deploy non è stato eseguito.

La suite critica include ora le prove esistenti di selezione delle fonti, ricevute di lettura e testo integrale nel prompt, oltre a contratti aggiuntivi su fonti e DB-API PostgreSQL. I test verificano contenuto e impronte, confini delle parti, rifiuto di citazioni inventate, originale invariato, allegati non articolati, filtraggio delle credenziali, parametri SQL, sessioni di sola lettura e rollback prima della ricevuta. Il driver PostgreSQL dei contratti è controllato: queste prove non attestano un server PostgreSQL reale.

Misure locali dei moduli aggiunti: lettura_fonti 74/80, lettura_normativa_rag 29/30, selezione_fonti 65/75, storage_postgres 191/198. Ogni rapporto supera la percentuale della baseline accettata. Le misure complete e omogenee restano obbligatorie nella CI del nuovo commit: la stima ottenuta unendo un artefatto CI precedente alle nuove prove locali non sostituisce quel gate.

La dichiarazione di perimetro indica la baseline realmente distribuita 104f234a17efea6696110e3ac6af23ac1a5583d6 e le impronte esatte dei quattro moduli. Nessuna modifica a soglie, esclusioni, algoritmo di confronto o test preesistenti. La modifica applicativa è limitata ai metadati di versione richiesti dal repository.

Il controllo generico Codex dev-tooling segnala i file di versione, packaging e configurazione come esterni al proprio perimetro; non è stato indebolito né dichiarato verde. Sono modifiche esplicite del rilascio autorizzato, verificate separatamente dai contratti e dal pre-push.

Il controllo OpenGA sul documento pubblico TAR Liguria 2019/341 resta distinto: il catalogo ufficiale espone il riferimento, ma il collegamento restituisce 404 anche dal PC. Non viene saltato né sostituito con testo non verificato. I lavori rinviati dall'utente restano aperti.
