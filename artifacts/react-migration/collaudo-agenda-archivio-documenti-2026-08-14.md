# Collaudo Agenda e archivio documenti

Data: 14/08/2026. Fuso orario: Europe/Rome.

## Perimetro

- Agenda: menu delle nuove voci, viste giorno/settimana/mese/cronologia, gestione evento, stampa, aggiornamento, tutto schermo, importazione ed esportazione calendario.
- Archivio documenti: aggregazione dei documenti conservati nei fascicoli, ricerca, filtri, paginazione, anteprima, download, modifica, collegamento al fascicolo, cestino e resa responsive.
- Audit funzionale: separazione dei contratti relativi ad archivio, nuovo documento, ricerca e filtri, modifica, cestino, esportazione ed editor rapido.
- Fascicoli: vista operativa/economica, modalità tabella/compatta/schede, pieno schermo e riuso delle analisi documentali economiche già consolidate.

## Struttura dati

- L'archivio React legge lo stesso repository tenant-aware dei fascicoli tramite `get_fascicoli`; non introduce un secondo archivio JSON operativo.
- Il documento rimosso passa da `documenti` a `documenti_cestino`; il file originale resta conservato fino all'eliminazione definitiva.
- Ripristino ed eliminazione definitiva aggiornano lo stesso fascicolo. Se la cancellazione fisica non riesce, la registrazione viene ripristinata nel cestino e l'errore non viene nascosto.
- I campi del cestino sono serializzati nello stesso modello usato dai backend supportati dal repository Fascicoli.
- Il presidio economico salva versione dell'analisi e impronta dei documenti letti. Se il fascicolo è già stato analizzato e l'impronta non cambia, l'apertura della vista economica riusa il dato consolidato e non riapre i documenti; un documento nuovo o modificato cambia l'impronta e riattiva soltanto l'analisi necessaria.

## Prova reale Agenda

Ambiente: copia Docker reale autenticata `http://127.0.0.1:8080`, viewport 1048 x 912.

- Ricerca, filtro e cinque comandi sono risultati sulla stessa riga.
- La barra misura 723 px sia come larghezza visibile sia come larghezza di scorrimento: nessun overflow.
- I cinque pulsanti misurano 44 x 44 px; il centro di ogni icona coincide con il centro del pulsante.
- Hover osservato: sfondo chiaro e icona blu leggibile. Focus osservato: contorno blu da 2 px con scostamento di 2 px.
- Il comando tutto schermo ha attivato lo stato espanso e il comando di uscita ha ripristinato la vista ordinaria.

## Prova reale archivio

Ambiente: copia Docker reale autenticata `http://127.0.0.1:8080/editor-professionale`.

- Dati osservati: 76 documenti, 5 fascicoli, 3 formati e cestino vuoto.
- Ricerca `Attestazione_di_conformita`: un risultato reale.
- Filtro formato `PDF.P7M`: 15 risultati reali.
- Viewport provati: 1280 x 720, 820 x 900 e 390 x 844.
- Nessun overflow orizzontale della pagina. Su smartphone le righe diventano schede e tutte le azioni misurano 44 px.
- La pagina è stata scorsa dall'inizio alle azioni dei documenti su desktop, tablet e smartphone.
- Nessun documento dell'utente è stato modificato, spostato o eliminato durante la prova visiva.

## Prova reale Fascicoli

Ambiente: copia Docker reale autenticata `http://127.0.0.1:8080/fascicoli?visualizzazione=schede&vista=economica`, versione `2.278.51`.

- Dati osservati: 10 fascicoli e 76 documenti nel perimetro visibile.
- `Compatta` e `Schede` mantengono la vista economica: per ciascun fascicolo sono visibili contributo unificato, spese/esborsi, liquidazione e parcella, con controllo documentale e modifica economica.
- Il comando `Tutto schermo` è collocato in una riga autonoma sopra `Operativa` e `Economica`.
- Il comando apre realmente la superficie sull'intero monitor; la vista resta `Economica`, la modalità resta `Schede` e sono presenti 10 blocchi economici. `Riduci` ripristina la pagina ordinaria senza perdere la selezione della vista.
- In pieno schermo la superficie misurata è 1936 x 1048 px. L'intestazione misura 127 px e contiene interamente la barra comandi di 110 px, senza tagli.
- Viewport provati: 1146 x 912, 820 x 900 e 390 x 844. Nessun overflow orizzontale; su smartphone sono visibili 10 schede dedicate con i quattro riepiloghi economici.
- Hover verificato sul comando prima dell'apertura; dopo il click il focus resta sul comando `Riduci` con etichetta accessibile corretta.

## Verifiche automatiche

- `py -3.12 -m pytest tests/test_agenda.py -q`: 21 test superati.
- `py -3.12 -m pytest tests/test_fascicoli.py -q`: 73 test superati.
- `py -3.12 -m pytest tests/test_functional_parity_audit.py tests/test_react_document_archive.py -q`: 10 test superati.
- `npm --prefix frontend run typecheck`: superato.
- Test mirati pieno schermo e viste economiche compatta/schede: superati.
- Test mirati riuso impronta documenti invariati e riapertura su nuovo documento: superati.
- Suite estesa Agenda, Fascicoli, dettaglio fascicolo, shell React, audit funzionale e archivio documenti: 348 test superati.
- Suite mirata archivio e Fascicoli dopo la separazione delle route cestino: 108 test superati.
- Contratti React, design system, coverage UI, governance repository, Ruff con la selezione CI, integrità UTF-8 e controllo whitespace: superati.
- Build Docker/Vite: superata; `iusentra-app` healthy sulla porta 8080.
- `/api/pronto`: stato `pronto`, versione `2.278.51`, fuso `Europe/Rome`.

## Stato audit

- Funzioni censite: 1428.
- Funzioni con contratto puntuale: 51.
- Funzioni verificate materialmente: 30.
- Funzioni presenti da provare: 21.
- Funzioni ancora da mappare: 1377.
- L'apertura dell'archivio e ricerca/filtri documenti sono verificate materialmente.
- Nuovo documento, modifica, cestino, esportazione ed editor rapido sono distinti e restano `presente_da_provare` finché non viene eseguita la rispettiva azione reale.

## Limiti residui

- La cancellazione definitiva è stata verificata con file temporanei controllati nei test, non su documenti reali dello studio.
- L'equivalenza complessiva del software non è dichiarata: la matrice conserva esplicitamente tutte le funzioni ancora da mappare o da provare.
