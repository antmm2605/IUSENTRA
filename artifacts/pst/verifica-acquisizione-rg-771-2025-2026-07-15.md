# Verifica acquisizione fascicolo RG 771/2025

Data verifica: 15/07/2026
Ambiente: produzione `https://app.iusentra.it`
Stato: IN CORSO

## Obiettivo

Registrare e verificare, passaggio per passaggio, l'acquisizione del fascicolo `RG 771/2025` dal portale, inclusi identificazione dell'ufficio e del registro, autenticazione locale, ricerca, lettura dei dati, scaricamento dei documenti, associazione del cliente, deduplicazione, persistenza tenant-aware e aggiornamento di agenda e fascicolo.

## Regole di accettazione

- Ogni passaggio deve essere osservato nella UI reale o confermato dai log applicativi correlati.
- Un fascicolo già presente deve essere aggiornato, non duplicato.
- Documenti già acquisiti e invariati non devono essere riletti; i nuovi documenti devono essere acquisiti e analizzati.
- Il cliente deve essere ricavato da una fonte verificabile e collegato al fascicolo e agli eventi dell'agenda.
- Errori o blocchi devono essere visibili e comprensibili nella UI.
- Nessun invio PEC o deposito reale fa parte di questa verifica.

## Cronologia osservata

| Ora italiana | Passaggio | Evidenza | Esito |
|---|---|---|---|
| 17:13 | Apertura acquisizione PST | Browser reale in produzione; route `/portali/pst/acquisizione` | Riuscito |
| 17:13 | Compilazione chiave di ricerca | Ufficio `Tribunale di Palmi`, codice `0910011`, numero `771`, anno `2025`, tabella ministeriale automatica | Riuscito |
| 17:13 | Suggerimento tabella ministeriale | Chiamate `schema-hint` durante la compilazione di numero e anno | Riuscito |
| 17:16 | Ricerca fascicolo sul portale | Un risultato: `RG 771/2025`, `Tribunale di Palmi`, `MANDAGLIO DANIELA`, data `07/03/2025` | Riuscito |
| 17:16 | Controllo corrispondenze interne | `POST /api/portali/pst/acquisizione/local-matches`, risposta HTTP 200 | Riuscito; destinazione proposta: nuova pratica |
| 17:16 | Diagnostica Local Signer | `POST /api/v1/ui/local-signer/diagnostics`, risposta HTTP 200 | Riuscito |
| 17:17 | Caricamento anteprima | `POST /api/portali/pst/acquisizione/preview`, risposta HTTP 200 | Riuscito |
| 17:17 | Analisi dati acquisibili | `POST /api/portali/pst/acquisizione/analyze`, risposta HTTP 200 | Riuscito; rilevati 46 documenti e 5 eventi |
| 17:17 | Avvio scaricamento documenti | UI reale: `Scaricamento documenti dal PST`, primo file visibile `Decreto_35421669.pdf`, avanzamento iniziale `0/46` | In corso |
| 17:18 | Scaricamento documenti completato | UI reale: `Documenti ricevuti dal PST`, ultimo file visibile `23_02_2025 ore_ 10_14 ACCETTAZIONE_ Richiesta pagamento annualit_ CARTA DEL DOCENTE.eml`, avanzamento `46/46` | Riuscito |
| 17:18 | Transizione finale | A `46/46` la UI è rimasta sullo Step 7; `Crea pratica e importa` risultava ancora disabilitato e il fascicolo non è stato aperto automaticamente | Fallito; correzione necessaria |
| 17:18 | Gestione PIN | Nella prova reale sono state richieste tre immissioni PIN per la sola consultazione e una per lo scaricamento | Fallito; atteso un PIN per consultazione e uno per scaricamento |
| 18:35 | Lettura della scheda reale post-deposito | `C:\Users\antmm\Downloads\Documento_30446614.pdf`, una pagina, 779 caratteri testuali nativi | Riuscito; tutti i campi operativi attesi sono stati estratti |
| 18:48 | Prova automatica del job documentale | Test d'integrazione con documento nuovo, secondo ciclo invariato e blocco esplicito di qualsiasi nuova lettura | Riuscito; un aggiornamento al primo ciclo, nessuna rilettura al secondo |

## Controlli finali

- [x] Ricerca ministeriale completata
- [x] Fascicolo corretto individuato
- [ ] Cliente e parti acquisiti
- [ ] Ufficio, registro e RG coerenti
- [ ] Documenti scaricati e classificati
- [ ] Deduplicazione verificata
- [ ] Fascicolo creato o aggiornato senza doppioni
- [ ] Agenda riallineata con cliente e fascicolo
- [ ] Prova visiva finale completata
- [ ] Log applicativi senza errori correlati

## Problemi rilevati e correzioni

- Prima dell'acquisizione il fascicolo non risultava né tra le pratiche attive né nell'archivio IUSENTRA; l'evento agenda `642D3DB8` mostrava quindi `Cliente/parte: Da collegare`.
- L'acquisizione reale ha identificato la parte `MANDAGLIO DANIELA`; dopo l'import va verificato che il fascicolo e l'evento agenda vengano riallineati automaticamente.
- Durante lo scaricamento iniziale il comando finale resta correttamente disabilitato finché i file non sono disponibili e controllati.
- Dopo il completamento `46/46`, il comando finale è rimasto disabilitato e non si è verificata l'apertura automatica del fascicolo.
- La sessione di consultazione non ha riutilizzato l'autenticazione del dispositivo: tre richieste PIN invece di una. La correzione deve preservare il confine previsto tra sessione di consultazione e sessione di scaricamento.
- Il documento reale `Documento_30446614.pdf`, rilasciato dalla cancelleria dopo il deposito e successivamente scaricato dal portale, contiene testo nativo leggibile con RG `771/2025`, ufficio, sezione, giudice, ruolo, materia, oggetto, ricorrente, difensore, controparti, esenzione dal contributo unificato e prima udienza. Nella UI di produzione risulta tuttavia classificato genericamente come `ATTO GIUDIZIARIO` e non aggiorna il presidio economico: il riconoscimento post-indicizzazione deve essere corretto e reso incrementale.
- Il flusso atteso è automatico: la PEC di cancelleria collega la prima evidenza al deposito; la copia ufficiale scaricata dal portale completa e conferma i dati; impronta del contenuto e riferimenti del procedimento impediscono duplicazioni e riletture del documento invariato.

## Implementazione automatica introdotta

- La scheda ufficiale di iscrizione a ruolo viene riconosciuta anche quando l'estrattore restituisce il testo su una sola riga e non conserva l'impaginazione del PDF.
- Vengono letti e consolidati: ufficio, RG, data di iscrizione, sezione, giudice, ruolo, materia, oggetto, ricorrente, avvocato, controparti, contributo unificato e prima udienza.
- Il fascicolo viene aggiornato soltanto se RG e anno coincidono; dati esistenti discordanti non vengono sovrascritti e restano registrati come conflitto.
- L'esenzione dal contributo unificato viene registrata come non dovuta, con riferimento al documento e alla sua impronta, senza generare importi o proforme.
- Il documento viene classificato come `Iscrizione a ruolo / dati fascicolo`, fuori dalla busta e non candidabile automaticamente tra i documenti da depositare.
- La lettura viene avviata sia al completamento dell'indicizzazione Lex sia dal job incrementale. Il secondo passaggio riusa l'impronta già registrata e non apre nuovamente il contenuto invariato.
- La consultazione PST riusa il catalogo completo già ottenuto dalla ricerca quando disponibile; anteprima e analisi non devono aprire una seconda sessione del dispositivo.
- Al completamento dello scaricamento, se l'analisi non contiene blocchi, il flusso registra o aggiorna automaticamente il fascicolo e apre il dettaglio restituito dall'importazione.

## Evidenza campo per campo sul documento reale

| Campo | Valore letto |
|---|---|
| Ufficio | Tribunale di Palmi |
| RG | 771/2025 |
| Iscrizione | 07/03/2025 |
| Sezione | 01 |
| Giudice | Gabutti Carlo |
| Ruolo | Controversie in materia di lavoro, previdenza e assistenza obbligatoria |
| Materia | Pubblico impiego |
| Oggetto | Retribuzione |
| Ricorrente | Mandaglio Daniela |
| Avvocato | Montagnese Giuseppe |
| Controparti | Avvocatura Distrettuale dello Stato di Reggio Calabria; Ministero dell'Istruzione e del Merito |
| Contributo unificato | Esente |
| Prima udienza | 14/07/2026 |

## Guardrail eseguiti prima della prova visibile

- Parser e automazione scheda: `4` test superati.
- Job documentale incrementale e non rilettura: `3` test d'integrazione superati.
- Indicizzazione, catalogo ed esenzione contributo: `42` test mirati superati.
- Acquisizione PST React: `18` test mirati superati.
- Typecheck e build React superati.

Questi esiti non chiudono la verifica: restano obbligatorie la prova materiale su `127.0.0.1:8080`, il deploy e la ripetizione reale in produzione con conteggio delle richieste PIN e controllo anti-duplicazione.

## Esito finale

Non ancora determinato.
