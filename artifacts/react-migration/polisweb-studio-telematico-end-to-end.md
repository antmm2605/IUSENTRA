# PolisWeb/PST: procedura interoperabile e registro prove

Aggiornato il 26/08/2026, fuso orario Europe/Rome.

## Perimetro clean-room

IUSENTRA implementa un flusso proprio, basato su documentazione PST ufficiale,
propri modelli dati, log autorizzati dello studio e comportamento osservabile
del prodotto di riferimento indicato dall'utente. Non vengono letti,
decompilati, trascritti, inclusi o derivati codici proprietari di terzi.

La fonte funzionale di confronto è il comportamento operativo osservato: il
codice pratica già presente determina silenziosamente il registro corretto;
l'avvocato non deve scegliere la tabella ministeriale né compilare oggetto o
materia per una ricerca esatta R.G./anno.

Fonti ammesse:

- Documentazione ufficiale PST e pagina servizi del Ministero della Giustizia.
- Catalogo ministeriale degli uffici e dei servizi disponibili.
- Dati SQL tenant-aware dello studio già autorizzati.
- Risposte, stati e log del Local Signer generati durante prove autorizzate.
- Codice e test di IUSENTRA.

## Selezione automatica della tabella

Prima di trasmettere una ricerca al PST, IUSENTRA effettua soltanto una
deduzione locale, senza chiamate esterne:

1. Cerca il fascicolo locale indicato dal collegamento oppure il fascicolo con
   stesso ufficio, R.G. e anno.
2. Ricava il profilo ministeriale dal tipo procedimento e dal registro
   operativo persistito.
3. Converte il profilo nella tabella e nel servizio PST corretti.
4. Invia una sola ricerca autenticata sul servizio risolto.

La deduzione non usa cache generiche di ricerche precedenti e non prova
silenziosamente registri alternativi. Se non esiste un fascicolo locale
compatibile, il flusso invia una sola ricerca sul servizio ufficialmente
compatibile con l'ufficio, mantenendo l'esito esplicito.

| Tabella visibile internamente | Registro | Servizio PST |
| --- | --- | --- |
| Civile ordinario | CC | JPW_SICID |
| Lavoro e previdenza | LAV | JPW_SIL_DISTR o JPW_SILP_DISTR |
| Volontaria giurisdizione | VG | JPW_SIVG |
| Minorenni | MIN | JPW_MIN o JPW_SIMIN |
| Esecuzioni mobiliari | ESM | JPW_SIECIC |
| Esecuzioni immobiliari | ESIM | JPW_SIECIC |
| Procedure concorsuali | FALL | JPW_SIECIC |
| Giudice di Pace | GDP | JPW_SIGP |
| Cassazione civile | CASSCI | JPW_CASSCI |
| Cassazione penale | CASSPE | JPW_CASSPE |

Le tabelle sono una regola tecnica interna: la UI non espone selettori,
codici JPW o altre scelte non necessarie all'avvocato.

## Sessione, PIN e singolo lotto

- Il PIN resta esclusivamente nella finestra nativa del provider del
  certificato. IUSENTRA non lo legge, non lo registra e non lo trasmette.
- La ricerca e la visualizzazione usano una sessione `view` riusabile per
  evitare richieste PIN ripetute.
- La visualizzazione completa usa un unico processo curl autenticato con un
  lotto di richieste correlate: dati, catalogo e sezioni arrivano nello stesso
  risultato e l'anteprima non apre un job aggiuntivo.
- Lo scarico selezionato usa un job locale per
  `/pst/download-documenti-batch`: una sola operazione curl per il lotto,
  senza scarichi singoli concorrenti. Il job pubblica un avanzamento soltanto
  quando curl ha concluso una risposta documentale, quindi la barra e il
  documento corrente non sono una stima temporale.
- Copia e originale restano proprietà di ciascun documento selezionato; il
  batch deve importare nel fascicolo soltanto i file effettivamente scelti.
- Il Local Signer tenta di portare in primo piano il dialogo PIN del provider
  per tutta la durata della richiesta. Questa parte richiede sempre prova
  materiale sul PC che ospita token e browser.

## Persistenza e importazione

Il risultato del PST conserva registro, ufficio, ruolo, identificativi del
fascicolo, eventuale subprocedimento e identificativi documento. La
destinazione primaria è il fascicolo SQL tenant-aware; JSON può essere solo
mirror. Documenti, eventi, parti e scadenze sono deduplicati prima della
registrazione e l'audit memorizza origine, modalità copia/originale ed esito.
Per i documenti PST, la deduplicazione usa prima gli identificativi
ministeriali (`id_documento`, `id_cat`, `id_repeatto`, `msg_id`): due PDF con
lo stesso nome e tipo, ma identificativi ufficiali diversi, restano due
documenti distinti. Il registro separa i documenti nuovi, quelli riusati e
quelli complessivamente registrati, così il conteggio visibile è
riconducibile ai file selezionati.

## Prove eseguite il 26/08/2026

- Typecheck React: superato.
- Test mirati del resolver locale, delle dieci tabelle e della ricerca PST:
  superati.
- Controlli del lotto Local Signer e della finestra PIN: superati come
  guardrail tecnico.
- Copia Docker locale ricostruita; `http://127.0.0.1:8080/api/pronto` ha
  risposto correttamente e il servizio applicativo locale è healthy.
- La prova precedente di scarico batch ha registrato i documenti selezionati
  nel fascicolo con un solo PIN per il lotto.
- La prova precedente di ricerca ha dato esito vuoto perché la UI non
  applicava il profilo locale già dedotto. La correzione ora collega il
  resolver alla richiesta e disabilita temporaneamente il tasto finché la
  deduzione locale non è terminata.
- In una prova reale successiva, avviata dall'utente e con PIN digitato solo
  nel dialogo nativo, il flusso ha raggiunto il fascicolo interno senza timeout.
  I log aggregati hanno mostrato una sola nuova ricerca-snapshot e nessun job
  aggiuntivo di visualizzazione. La selezione documentale è rimasta disponibile
  per l'importazione nel fascicolo scelto.
- È stato aggiunto il progresso del lotto documento per documento: documento
  corrente, contatore elaborati/totale, barra accessibile, avvisi e stato
  finale. Il controllo automatico verifica che ogni risposta del batch pubblichi
  il proprio avanzamento e che il percorso non richiami il download singolo.
- Nell'ultima prova reale l'utente ha completato la consultazione e lo scarico
  del lotto senza messaggi di timeout o di errore nella UI. Il registro di
  importazione ha rilevato 30 file attesi, ricevuti e decodificati, senza file
  vuoti o scartati. Il fascicolo ha però mostrato 29 righe: la causa era la
  deduplicazione per solo nome/tipo descritta sopra. La correzione è coperta
  dal test `test_documenti_portale_con_identificativi_distinti_e_stesso_nome_restano_distinti`.

## Verifica reale ancora richiesta

La prima ricerca successiva alla correzione è stata autorizzata e inviata il
26/08/2026. Si è chiusa prima della risposta del fascicolo con mancata
conferma del certificato/PIN, senza timeout, senza risultati e senza modifiche
al fascicolo. Non è stato avviato alcun secondo tentativo automatico.

Resta da effettuare una nuova prova reale del lotto dopo l'aggiornamento,
per confermare nella UI che il numero di righe nel fascicolo coincide con il
numero di documenti selezionati. L'avvocato inserisce manualmente il PIN nel
dialogo nativo visualizzato in primo piano; vanno osservati e registrati senza
dati personali: numero processi curl, numero richieste PIN, stato del dialogo
in primo piano, avanzamento progressivo, esito del lotto, numero di documenti
selezionati e importati, modalità copia/originale e assenza di download
singoli o job di visualizzazione aggiuntivi.
