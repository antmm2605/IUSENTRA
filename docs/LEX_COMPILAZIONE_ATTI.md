# Lex e compilazione degli atti — ricognizione e schede pilota

Ricognizione del 19/10/2026 sul catalogo `pct/template_atti_catalogo_data/catalogo_master.json`.

## Principio

I dati che il gestionale conosce (anagrafiche, difensore, ufficio, ruolo, date, importi calcolabili) li
compila il software con la precompilazione esistente (`pct/template_atti_prefill.py`). Lex scrive solo
le parti narrative (fatto, diritto, conclusioni) usando i fatti del fascicolo e gli articoli della
biblioteca «Codici e leggi», chiede all'avvocato solo i dati mancanti e si astiene quando un presupposto
manca. Nessun dato reale dei clienti entra nell'addestramento: gli esempi usano fascicoli fittizi.

## Il catalogo oggi

- 420 modelli (core 140, advanced 133, professional 119, specialist 28), tutti in stato `draft_professionale`.
- Canali: PST 249, nessun deposito 77, PDP 25, PTT 20, PAT 18, PST Giudice di pace 16.
- In media 13 campi per modello: 11 hanno già un collegamento al database, circa 2 restano da chiedere.
- Il registro delle fonti (`pct/template_atti_legal_sources.py`) collega a ogni modello in media 17 fonti ufficiali.

## Cosa manca

1. **Campi di sostanza.** I campi obbligatori coprono quasi solo intestazione e parti: 173 modelli su 420
   hanno gli stessi 6 campi (cliente, difensore, oggetto, data, ufficio, controparte). Non sono dichiarati gli
   elementi che la legge richiede per quell'atto, come i requisiti dell'art. 163 c.p.c. per la citazione,
   dell'art. 414 per il ricorso di lavoro o dell'art. 480 per il precetto.
2. **Fatti dai documenti.** Nessun campo è collegato all'archivio delle letture (`pct/archivio_letture/`):
   date, importi, titoli e notifiche letti dai documenti non arrivano ai modelli.
3. **Norme generiche nei modelli.** Il campo `normativa_riferimento` di tutti i 420 modelli contiene frasi
   generiche senza articoli. Gli articoli precisi ci sono nel registro delle fonti, ma non sempre i più
   pertinenti: per il ricorso di lavoro mancano gli artt. 409, 413 e 414 c.p.c., per il precetto gli artt. 474-482.
4. **Luogo di sottoscrizione.** In tutti i 420 modelli il campo `place` legge per primo `studio.indirizzo`,
   mentre la regola del software vuole la città dello studio (`studio.citta`). Da correggere nel catalogo.

## Schede pilota

In `pct/template_atti_schede/` (lette da `pct/schede_compilazione.py`), una per atto:

| Scheda | Modelli coperti | Norme principali |
|---|---|---|
| MON_001 Ricorso per decreto ingiuntivo | MON_001, MON_002 | artt. 633-642 c.p.c., 1219 e 1224 c.c., D.Lgs. 231/2002 |
| CIV_ORD_001 Atto di citazione | CIV_ORD_001, 004, 005, 006 | artt. 163, 163-bis, 164, 166, 167 c.p.c., D.Lgs. 28/2010 art. 5 |
| CIV_ORD_009 Comparsa di costituzione | CIV_ORD_009, 010, 011 | artt. 38, 115, 166, 167, 269 c.p.c. |
| ESE_001 Atto di precetto | ESE_001, 003, 004, 005, MON_018 | artt. 474-482 c.p.c. |
| LAV_001 Ricorso rito lavoro | LAV_001, LAV_012 | artt. 409, 413, 414, 415 c.p.c., L. 604/1966 art. 6, L. 300/1970 art. 18 |

Ogni campo dichiara la fonte (`database`, `archivio_letture`, `documento`, `calcolo`, `avvocato`, `lex`),
la norma che lo rende necessario e cosa fare se manca. Ogni articolo citato è stato verificato
nell'archivio `codici_leggi.sqlite` aggiornato al 19/10/2026.

## Prossimi passi

1. Collegare le schede alla precompilazione e all'archivio delle letture, così che il software proponga
   solo le domande di `campi_da_chiedere`.
2. Generare il dataset pilota (1.000-1.500 esempi su fascicoli fittizi): scelta dell'atto, dati mancanti,
   parti narrative con citazioni, astensione.
3. Addestrare partendo dal modello della fase 5, dopo la sua valutazione, e verificare che le capacità attuali
   non peggiorino.
