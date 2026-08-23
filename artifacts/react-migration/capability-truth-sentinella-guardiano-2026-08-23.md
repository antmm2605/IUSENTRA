# Capability Truth Registry, Sentinella Telematica e Guardiano Scadenze

Data: 23/08/2026
Perimetro: Centro telematico React e Scadenze e Termini React. Nessun invio PEC, deposito o modifica automatica di un termine processuale è eseguito da queste funzioni.

## Obiettivo operativo

Le tre superfici costituiscono un presidio unico:

1. il **Capability Truth Registry** distingue ciò che la piattaforma sa fare, ciò che richiede configurazione dello studio e ciò che non è ancora validato;
2. la **Sentinella Telematica** rileva, acquisisce e confronta fonti istituzionali, aprendo un presidio quando una fonte cambia, è in errore o non è ancora acquisita;
3. il **Guardiano Scadenze** evidenzia rischio, prova della fonte, responsabile e prossima azione sulle scadenze già presenti nel repository tenant.

La UI non usa badge “pronto” come promessa assoluta: l’effettiva operatività resta distinta da prerequisiti di studio, prova disponibile e limiti della singola funzione.

## Fonti ufficiali e acquisizione automatica

Il catalogo FONTI_UFFICIALI mantiene per ogni fonte identificativo, URL, motore e regole di recupero. Le fonti telematiche sono selezionate dinamicamente con official_telematic_source_ids(); il job scheduler non mantiene più una lista manuale limitata a una sola pagina.

| Famiglia | Fonte primaria | Uso nel processo |
| --- | --- | --- |
| Portale Servizi Telematici | [PST – Documentazione](https://pst.giustizia.it/PST/it/documentation.page) | indice istituzionale per servizi, download e documentazione |
| Servizi web PCT | [Documentazione servizi web 1.69](https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4571) | consultazione e contratti dei servizi web |
| Specifiche PCT | [Specifiche tecniche D.M. 44/2011](https://pst.giustizia.it/PST/resources/cms/documents/SPECIFICHE_TECNICHE_DM_44_2011REV_04.01.24.pdf) | profili tecnici, flussi e controlli di conformità |
| XSD, WSDL e strumenti | [PST – Download](https://pst.giustizia.it/PST/it/download.page) | individuazione degli artefatti tecnici pubblicati |
| Termini processuali | [Normattiva – codice di procedura civile](https://www.normattiva.it/eli/id/1940/10/28/040U1443/CONSOLIDATED/20240814) | fonte normativa da associare alle regole governate, mai a una deduzione non verificata |

Il ciclo automatico programmato esegue:

1. rilevazione dal catalogo delle fonti telematiche ufficiali;
2. recupero della pagina o dell’artefatto pubblicato, quando il canale pubblico lo consente;
3. normalizzazione, estrazione tecnica quando prevista e impronta/versione dell’evidenza;
4. confronto con l’ultima evidenza acquisita;
5. valutazione dell’impatto sulle capability associate;
6. apertura di un avviso con URL istituzionale, data dell’ultimo controllo e flussi da verificare.

Se una fonte non è accessibile, richiede credenziali o non espone il contenuto necessario, il sistema non inventa il dato e non aggira il controllo di accesso. Registra invece lo stato di acquisizione/errore, conserva il canale ufficiale e richiede il presidio umano indicato dalla UI. Uno stato senza monitoraggio non viene mostrato come “presidiato”.

## Responsabilità e fonte di verità

- Le capability sono configurazione di dominio in pct/telematico_truth_registry.py; non sono un’autocertificazione dell’avvocato.
- I monitor e le fonti provengono dal repository telematico già tenant-aware, con SQL come fonte operativa per SQLite e PostgreSQL; non sono create nuove tabelle o copie JSON usate come verità.
- Il Guardiano è una derivazione pura di scadenze esistenti: non modifica date, sospensioni, regole o titolarità e non crea scadenze da solo.
- Ogni link visibile è l’URL ufficiale presente nel catalogo o un dettaglio interno già collegato alla scadenza; nessun riferimento è generato per inferenza.

## Stato anti-falso-verde

- pronta: perimetro applicativo disponibile con prova dichiarata dalla policy; non elimina le verifiche del caso concreto.
- condizionata: richiede prerequisiti locali o di studio, per esempio PEC locale, certificato, firma, dati fascicolo o ricevute.
- assistita: il software prepara o guida un passaggio, ma la validazione professionale resta necessaria.
- da validare: il flusso non ha prova sufficiente per essere presentato come pronto.
- da presidiare (Sentinella): manca almeno un’acquisizione o una verifica fonte; non equivale a “nessuna variazione”.

## Guardiano Scadenze

Il Guardiano restituisce, per ogni elemento a rischio, una motivazione e una sola prossima azione. I segnali includono termine scaduto o vicino, termine perentorio, titolare assente, attività preparatoria oltre il termine, fascicolo assente, fonte con attendibilità bassa o prova sorgente assente, e collegamento udienza remota non verificato.

Il Guardiano non ricalcola autonomamente termini di legge, non sostituisce il controllo dell’avvocato e non trasforma un’indicazione OCR/PEC in una scadenza certa. Per la determinazione dei termini rimangono necessari la fonte normativa o il provvedimento concreto, il profilo di decorrenza e la validazione professionale.

## File e copertura

- Backend Registro/Sentinella: pct/telematico_truth_registry.py, pct/legal_intelligence.py, pct/scheduler.py, web/services/react_telematico_bridge.py.
- Backend Guardiano: pct/guardiano_scadenze.py, web/services/react_scadenziario_bridge.py.
- Superfici React: frontend/src/components/TelematicoPage.tsx e frontend/src/components/ScadenziarioPage.tsx, con relativi normalizzatori dati.
- Guardrail: tests/test_telematico_truth_registry.py, tests/test_telematico_source_recovery.py, tests/test_guardiano_scadenze.py, tests/test_react_scadenziario_additions.py.

## Verifiche eseguite nella sessione

- compilazione Python mirata delle nuove unità e dei bridge React;
- test Python mirati per Registro, Sentinella, recupero fonti, Guardiano e shell React, superati;
- typecheck React: npm run typecheck nella cartella frontend, superato.

Ricostruzione Docker locale eseguita per l’app; `iusentra-app` risulta healthy. L’endpoint http://127.0.0.1:8080/api/pronto ha restituito `ok=true`, timezone `Europe/Rome` e versione `2.278.65`.

### Prova materiale locale eseguita il 23/08/2026

La prova è stata svolta nella scheda Chrome autenticata indicata dall’utente, su `http://localhost:8080`, dopo il rebuild Docker.

- Da menu laterale è stato aperto `Servizi Telematici → Centro Servizi Telematici`. Il Registro mostra 10 capability, con ambito, requisito per lo studio, limite e riferimenti ufficiali cliccabili. I collegamenti PST verificati puntano a `https://pst.giustizia.it/PST/it/documentation.page`.
- La Sentinella espone il ciclo automatico, nessuna variazione aperta e `9 fonti presidiate su 9 controllate`; non usa lo stato positivo per fonti senza controllo.
- Il Registro è stato percorso fino al fondo. Hover e focus del riferimento ufficiale sono risultati leggibili; il focus è visibile senza spostamenti del layout.
- È stata corretta e poi ricontrollata la resa dei timestamp: ultimo controllo `23/08/2026 12:15` e cronologia `18/08/2026 12:07`, senza ISO raw né anno abbreviato.
- Da menu laterale è stato aperto `Scadenze e Termini → Scadenziario`. Al termine del caricamento dati dello studio, il Guardiano ha esposto `12 elementi richiedono un presidio preventivo`, di cui `3 critici`, con motivazioni e prossime azioni per termini oltre data prevista e fonti evento mancanti. La pagina mostra inoltre i dati della scadenza e il collegamento alla fonte quando presente.
- Sono stati verificati hover e focus dei controlli interattivi dello scadenziario, e sono stati effettuati scroll materiali delle superfici controllate.

La prova locale è positiva per il perimetro descritto. Il deploy Hetzner e la verifica di produzione restano da eseguire nel ciclo di rilascio sul commit finale.
