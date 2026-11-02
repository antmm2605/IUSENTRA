# Elenco unico dei difetti — verifica visiva del 02/11/2026 (versione 2.476.0)

Stato: R = risolto nel codice (in attesa del deploy unico), L = in lavorazione, A = aperto.

## Fascicolo (testata, pannelli)
1. [L] PEC con decreti/sentenze non collegate con certezza: il numero di ruolo nelle forme ministeriali («COMUNICAZIONE 2539/2025/LAV», «RG: 2539 - 2025») non veniva letto → 428 PEC su 500 «ruolo assente». Corretto in pct/pec_collegamento_certo.py; motivo dettagliato (cliente/ufficio).
2. [R] Sentenza: doppioni fusi, «Visualizza sentenza» con citazione, registrazione automatica nei casi certi (credito + definizione con «Annulla»), incerti da confermare con motivo. (14 test) Storico: 50 fascicoli per giro (70 in 2 giri).
3. [R] «Lettura interrotta dopo 3 tentativi»: i riavvii non contano più come tentativi, lettura a turni con progresso, documento guasto chiuso «non leggibile», fermi storici rimessi in coda da soli; scritta «n di m documenti letti». (6 test + 265 regressioni)
4. [R] «Notifiche richieste»: una voce per atto; «Notificato» con le prove o fase superata; mai «da notificare» dopo la sentenza. (17 test)
5. [R] «Parti lette»: niente C.F. di persona fisica agli enti, petitum non è parte, varianti fuse, generici scartati.
6. [R] «Fasi, termini e norme» lavoro: appello art. 434 (non 325), art. 417-bis corretto, fasi udienza/decisione aggiunte con fonti Normattiva.
7. [R] Indice Lex: busta Atto.enc non più errore («Non applicabili», nota «Buste cifrate per l'ufficio»), riconvalida degli esiti storici. Test 5 + regressioni 423.
8. [A] Fascicolo con sentenza resta «In corso» e fase «Trattazione» (dipende da 2).
9. [A] Scadenza perentoria «Impugnazione sentenza – termine lungo» con priorità «Bassa».
10. [A] «Verifiche automatiche dei presìdi eseguite il 13/10/2026» e «Motore PEC 0 letti / ultima lettura 13/10»: i presìdi non girano da tre settimane su alcuni fascicoli.
11. [A] Presidio fascicolo: «Rinvio udienza 07/10/2026» mostrato come prossima udienza dopo la sentenza.
12. [R] Profilo procedurale: dedotto dai dati certi (sezione, ufficio, registro, atto introduttivo, codice oggetto PST) e impostato da solo con la fonte; alternative solo della stessa materia; profili di rito aggiunti. (21 test) Fonte visibile, «Cambia profilo», riconvalida notturna alle 02:55 (25 test).
13. [A] Prossimi passaggi (fascicolo con udienza sostituita da note scritte, termine 04/11/2026): propone «Preparare l'udienza del 04/11/2026 … prepara la discussione» oltre a «Adempiere alla riassegnazione termine per note». Con la trattazione scritta (art. 127-ter c.p.c.) non c'è discussione: un solo passaggio «Depositare le note scritte entro il 04/11/2026», con le indicazioni del decreto.

## Già risolti nella 2.476.0 (verificati a vista)
- Contratti: campi, pulsanti, scheda, clausole in italiano (PC e telefono).
- Modifica fascicolo: stato importato non diventa «Bozza».

## Pagine dell'applicazione
(in compilazione dal giro automatico su 80 pagine, PC e telefono)
- P1. [A] /notifiche-legali: apertura lenta (21 s).
- P2. [A] /messaggi: 3 email di maggio in «Errore» senza motivo leggibile nell'elenco (da verificare il dettaglio «Apri»).
