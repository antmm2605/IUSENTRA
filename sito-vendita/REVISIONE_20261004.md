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
