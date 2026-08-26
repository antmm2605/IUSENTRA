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

## Consultazione dal fascicolo interno

Il pannello `Fascicolo d’ufficio` non apre più una scheda del Portale Servizi
né richiede all’avvocato un download manuale. Il comando del fascicolo e il
pulsante `Visualizza fascicolo` avviano entrambi la stessa consultazione
diretta del Local Signer (`/pst/fascicolo-snapshot-job`), riutilizzando la
sessione `view` valida quando presente. L’elenco, lo stato di acquisizione e
la scelta copia/originale restano nella superficie React di IUSENTRA.

Se la sessione non è disponibile o è scaduta, il provider può chiedere il PIN
nel suo dialogo nativo; IUSENTRA non apre il sito esterno e non conserva il
PIN. Dopo l’elenco, l’acquisizione selettiva resta un unico batch
`/pst/download-documenti-batch` con importazione SQL nel fascicolo corrente.

### Ripristino della sessione scaduta

Il 26/08/2026 una sessione `view` memorizzata dal Local Signer era ancora
marcata come autenticata, ma il cookie PST non era più accettato dal gateway.
La richiesta cookie-only restava quindi in attesa fino al timeout di 90
secondi, senza poter aprire il dialogo PIN. La correzione invalida quel cookie
e ripete una sola volta la medesima chiamata con il certificato: il provider
può così mostrare il PIN nativo. Un timeout della successiva chiamata con
certificato resta invece un errore esplicito del PST, senza ulteriori retry o
ulteriori finestre PIN. La regola si applica in modo uniforme alle chiamate
SOAP singole, raw e batch, quindi a tutte le tabelle ministeriali.

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

- Guardrail superati: typecheck React, controlli del resolver locale e delle
  dieci tabelle, download batch Local Signer, progresso per risposta e
  deduplicazione di documenti con stesso nome ma identificativi PST distinti.
- Copia Docker locale ricostruita e riavviata; `http://127.0.0.1:8080/api/pronto`
  ha risposto correttamente con applicazione healthy. Nella UI reale sono stati
  verificati il wizard, i sette passi, l'assenza del selettore delle tabelle e
  l'assenza del campo oggetto/materia per la ricerca esatta.
- In una consultazione reale autorizzata, con PIN digitato esclusivamente
  dall'utente nel dialogo nativo, il resolver ha scelto in modo silenzioso una
  sola tabella, ha restituito anteprima, parti, eventi e 30 documenti. Tutti i
  documenti erano selezionati in modalità copia prima dell'avvio del lotto.
- Il lotto ha usato un'unica operazione autenticata, pubblicando avanzamento
  documento per documento. Il PST ha restituito un errore HTTP 502 per un solo
  documento; gli altri 29 sono stati importati nel fascicolo e il conteggio
  locale è rimasto coerente con i file realmente ricevuti. IUSENTRA non ha
  creato file vuoti, duplicati o sostituzioni.
- Il tentativo successivo di ripresa su uno storico precedente, privo
  dell'identificativo ufficiale del documento fallito, ha dimostrato un difetto:
  la UI poteva preselezionare un candidato non dimostrato. Il PST non ha
  completato tale richiesta entro il limite di 300 secondi. Il dettaglio è
  stato conservato solo come diagnosi del canale esterno, senza modificare i
  documenti già registrati.
- Dopo il riscontro del timeout senza PIN, sono stati aggiornati i sorgenti
  effettivamente in esecuzione del Local Signer tramite il suo hot-update
  locale: la copia attiva è stata confrontata per impronta con il sorgente
  validato. Sono stati rigenerati i pacchetti Windows, macOS e Linux della
  stessa versione. Nessun certificato, PIN, cookie o dato di studio è incluso
  nei pacchetti o nel backup della procedura.

## Correzione della ripresa mirata

Ogni nuovo errore di download persiste ora, nel registro locale della
procedura, il tipo di ripresa, la modalità copia/originale e gli identificativi
ministeriali del solo documento non ricevuto. Il collegamento di ripresa passa
un identificativo del registro, non il nome del file. Dopo una nuova
anteprima, IUSENTRA seleziona esclusivamente un documento con corrispondenza
univoca di identificativo ufficiale; una corrispondenza per nome, data o tipo
non è sufficiente.

Se uno storico precedente non contiene l'identificativo o se il documento non
è più presente nell'anteprima, la ripresa non preseleziona alcun documento e
la UI lo dichiara esplicitamente. L'avvocato può verificare e scegliere
manualmente, ma il software non sostituisce mai il documento. I log locali
disponibili sono stati esaminati solo in forma aggregata: non contengono
l'identificativo necessario per riparare in sicurezza il vecchio storico.

## Verifica reale ancora richiesta

La copia Docker locale è stata ricostruita e il Local Signer attivo è stato
riallineato al sorgente corretto. Resta aperta la prova reale del nuovo
pulsante `Visualizza fascicolo`: il PST deve restituire l’anteprima nella
stessa pagina, senza aprire il sito esterno, e il provider deve proporre il
PIN nativo quando il cookie precedente non è utilizzabile. Non viene avviato
alcun nuovo tentativo automatico né alcun invio del PIN da IUSENTRA;
l’avvocato lo digita nel dialogo nativo. La verifica conclusiva deve
osservare: una sola richiesta batch, il dialogo PIN in primo piano, selezione
esatta, modalità copia/originale preservata, avanzamento, esito e conteggio
del fascicolo.
