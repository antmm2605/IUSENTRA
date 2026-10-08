# EmbeddingGemma 2 locale — integrazione in verifica

## Candidato attuale: LiteRT QAT, 08/10/2026

Il candidato scelto per il collaudo usa i [pesi testuali LiteRT ufficiali](https://huggingface.co/litert-community/embeddinggemma-2-text-270m-litert-lm),
revisione `9be6e8b90982095dc05c2bd162e4b954ee4dbac7`, LiteRT-LM `0.18.0`, CPU.
Il manifest `litert-model-manifest.json` fissa file, dimensione e SHA-256.
`provision_litert.py --root <cartella-modelli>` prepara soltanto questo artefatto
pubblico in `litert-model/`, verifica tutti i byte e conserva directory precedenti.
Il servizio non effettua download; montare la directory restituita, non la root.

Profilo distinto: `text-q4-qat-litert0180-segments768-mean-768-v1`.
Prefisso domanda `task: search query | text: `; documento `task: search result | text: `.
Il worker conserva ogni carattere, divide il documento in parti di 768 caratteri,
cede la priorità alle query fra le parti e normalizza la media ponderata.
Questo pooling non equivale al calcolo nativo sull'intero contesto; non mescolare
questi vettori con il candidato float32 o con un profilo LiteRT precedente.
Il RAG conserva inoltre i singoli segmenti con provenienza e pagina.

L'overlay locale ora punta a `Dockerfile.litert`, imposta il runtime anche su app
e worker e usa `/tmp` da 256 MiB per la cache nativa. Rete interna, nessuna porta
pubblicata, pesi in sola lettura e nessun privilegio. **Overlay non ancora applicato**:
il vecchio embedding è tuttora operativo nella copia reale. Il container sperimentale
isolato non costituisce sostituzione del prodotto.

Riscontri: 12/12 abbinamenti controllati; query sotto indicizzazione lunga
0,208–0,237 s; RSS worker 917,3 MiB. La sola differenza finale € 260,00/€ 500,00
in testi di 16.320 caratteri produce coseno 0,9999904: la media non dimostra
precisione universale sui dettagli, da verificare nei risultati effettivi.
RAG nativo su due fonti SQL correnti: cinque chunk, sei query e sei cache hit,
sessanta riscontri di provenienza. Prima costruzione Normattiva persistente:
432 voci su 756.290, ultimo lotto di 180 voci in circa 60 secondi,
zero testo troncato; indice completo e precisione sul corpus ancora aperti.

Il riscontro delle citazioni consulta inventario, versione e testo estratto
in una stessa fotografia SQL, senza OCR, file originali, DDL o connessioni SQLite
`immutable`. PostgreSQL usa una transazione dedicata di sola lettura REPEATABLE READ.
Gli esiti negativi conservano causa e audit; un nuovo riscontro aggiorna lo stato
corrente senza duplicare la medesima prova. La riconciliazione dei riferimenti
storici e la pubblicazione concorrente nel percorso degli eventi restano aperte.
Non attivare prima di completare indici, confronti e prova reale sulla porta 8080.

## Profilo float32 precedente e memoria delle prove

Artefatto ufficiale: [google/embeddinggemma-2](https://huggingface.co/google/embeddinggemma-2).
Revisione: `914f7f89142e33e77833254d9c9b90c3cef7303b`.
La [guida ufficiale](https://ai.google.dev/gemma/docs/embeddinggemma/inference-embeddinggemma-with-sentence-transformers)
richiede Sentence Transformers 6.1 e distingue float32/bfloat16 da float16,
che non è supportato. Il modello usa licenza Apache 2.0.

Il servizio predisposto usa la componente **testuale**, float32 CPU e vettori
normalizzati a 768 dimensioni. La disponibilità del modello multimodale non
equivale all'integrazione di immagini, audio o video nel prodotto: queste
superfici non sono abilitate da questa configurazione. OCR e motori documentali
rimangono quelli nativi condivisi; non sono sostituiti dall'embedder.

## Contratto e isolamento

- Modello operativo: `embeddinggemma2:<revisione>-text-f32-768-v1`.
- Domanda: `task: search result | query: `; documento: `title: … | text: `.
- Nessun tag Ollama presunto, nessuna API esterna, nessun download durante
  l'esecuzione. Il modello conversazionale resta separato.
- Pesi predisposti fuori dal repository e montati in sola lettura; manifest
  confrontato con quello pubblico verificato incluso nell'immagine, quindi
  verifica SHA-256 di ogni file. File aggiuntivi o modificati impediscono l'avvio.
- Rete Docker interna, senza porte pubblicate; utente senza privilegi,
  filesystem in sola lettura, nessuna capability, limite di memoria 4 GB.
- Una sola inferenza contemporanea. Le domande precedono i lotti documentali;
  il servizio cede il turno dopo ogni testo. Il contesto oltre 8.192 token
  produce un errore, senza troncamento silenzioso.

## Migrazione straordinaria dei repository dello studio

`provision.py --root <cartella-modelli>` predispone esclusivamente l'artefatto
pubblico ufficiale, senza token e senza accesso ai documenti. Scarica la
revisione fissata, verifica tutte le impronte e pubblica la directory soltanto
dopo il controllo. Una directory precedente viene conservata separatamente;
una preparazione già verificata non scarica nuovamente i pesi. Questo comando
va eseguito nella fase esplicita di installazione, con accesso alla rete per
scaricare il modello, separatamente dal servizio offline di inferenza.

`scripts/migra_embeddinggemma2_locale.py` riceve esplicitamente repository,
radice dello studio, destinazione del backup, tenant e limite di lotto.
Richiede anche `--registry`: RAG, radice e SQL devono coincidere con i
percorsi canonici del registro dell'installazione e del profilo nativo.
Alias storici e connessioni PostgreSQL diverse vengono respinti prima delle
scritture. Il controllo non riconcilia cartelle né prepara nuovi archivi.
Il riscontro corrente richiede `--core-db` per SQLite oppure la variabile
`IUSENTRA_STUDIO_DSN` per PostgreSQL, mai entrambi. La stessa funzione condivisa
di Lex verifica inventario, impronta, versione e passaggio documentale prima
di una nuova inferenza. Le fonti senza prova conservano motivo e audit, senza
essere trasferite come fonti confermate. I riepiloghi economici derivati non
sono la prova originale della sentenza; riferimenti a un altro tenant sono esclusi.
Questo controllo non sostituisce il recupero delle prove mancanti, ancora aperto.
Una variazione di testo, metadati, procedimento o identità/impronta RAG
invalida la conferma nella stessa transazione, conservando l'audit precedente.
Il ripristino del testo richiede un nuovo riscontro SQL prima della conferma.
I conteggi non enumerano tutto il testo per rilevare queste variazioni.
La migrazione tenta anche il recupero dei soli metadati storici mancanti:
richiede l'ID originale presente nell'inventario, la stessa impronta e un
testo estratto corrente che contenga esattamente il passaggio. Non corregge
metadati discordanti, non collega per nome file e non adotta riepiloghi derivati.
`rag_source_reconciliation` conserva prima/dopo; testo e vecchi vettori restano
invariati. Prova nativa circoscritta: cinque passaggi di due fonti recuperati,
indicizzati e registrati in audit; parità di recupero provata anche in PostgreSQL.
Il repository
deve appartenere alla radice indicata. Il backup è SQLite coerente, verificato
con `quick_check`, SHA-256 e manifest di provenienza; non sovrascrive una copia
esistente priva di manifest. Non legge i file originali e non esegue OCR.

I chunk SQL vengono suddivisi senza scartare testo mediante la funzione nativa
`_bounded_text_parts`. Documento, pagina, metadati e riferimento al chunk
originario rimangono disponibili. `rag_embedding_generations` e
`rag_embedding_segments` conservano lo spazio vettoriale nuovo separatamente
dai vettori precedenti. Sono tabelle dell'indice locale SQLite del singolo
studio, già distinto dai repository documentali/economici SQLite/PostgreSQL
nel modello di storage; non introducono una seconda verità documentale.

Checkpoint per lotto di 16 segmenti e pubblicazione atomica dell'intero chunk:
una generazione in costruzione non viene restituita dalla ricerca. Prima di
salvare e pubblicare viene ricontrollata la fonte sotto write lock. Cambi di
testo, impronta o cancellazione escludono i vecchi risultati; gli esiti negativi
restano motivati e non vengono ritentati a ogni passaggio. Un testo cifrato,
binario o non letto non è una fonte confermata e richiede recupero dal percorso
documentale nativo, con provenienza, non eliminazione del messaggio.

Il percorso ordinario `embed_pending_chunks` elabora solo i pending SQL.
La migrazione storica è un comando esplicito, riprendibile e con backup:
non viene eseguita nelle GET, nei controlli periodici o a ogni pagina.
Il cursore per modello conta anche le righe già elaborate; un lotto dispone
di 60 secondi e conserva i segmenti già preparati senza pubblicare un chunk
incompleto. Il timeout di una singola richiesta resta 120 secondi. Il backup
è ancora verificato integralmente a ogni invocazione.

## Indice Normattiva e attivazione

La costruzione nativa `lex.ricerca_giuridica.indice_vettoriale` conserva modello,
revisione, prefissi, normalizzazione e checkpoint. Il nuovo profilo usa una
cartella distinta `vettori_normattiva_<revisione>_text_f32_768_v1`; un percorso
esplicito `LEX_NORMATTIVA_VETTORI_DIR` deve indicare un indice già compatibile.
Non sovrascrivere l'indice operativo precedente.
Il candidato QAT usa `vettori_normattiva_<revisione>_text_q4_qat_litert0180_segments768_mean_768_v1`.
`--prima-costruzione --batch 1 --paralleli 1 --tempo-massimo-s 60` riprende
dal proprio watermark. Un indice parziale rimane indisponibile, anche dopo
la fine della prima costruzione, finché non passa la riconvalida nativa finale.

L'overlay `compose.local.yml` è relativo al Compose principale nella radice
del repository. Per il candidato attuale configurare `IUSENTRA_EMBEDDING_MODELS_DIR`
alla directory LiteRT verificata restituita dal provisioner. La sua applicazione abilita il nuovo
modello per applicazione e worker: **non attivarlo prima che corpus, citazioni,
isolamento e tempi siano stati confrontati, e gli indici necessari siano pronti**.
Il modello precedente e i suoi vettori restano disponibili durante la prova.
Non disinstallare Ollama: serve ancora al modello conversazionale.

L'accettazione richiede navigazione e ricerca visibili nella copia reale
`127.0.0.1:8080`, aggiornamento/sostituzione/rimozione delle fonti, citazioni,
salvataggio e riapertura, oltre ai guardrail tecnici. Il successivo rilascio
richiede branch gemelli, copia locale e Hetzner sullo stesso commit verificato.
Il container applicativo Hetzner deve rimanere unico e chiamarsi `iusentra-app`.

## Esiti misurati il 07/10/2026

Prova isolata offline sul PC reale: 12/12 domande controllate corrette per
entrambi i modelli. Query calda del precedente circa 0,03 s, del nuovo float32
quattro thread circa 0,08 s; memoria del processo nuovo circa 2.029 MiB.
Tre richieste durante l'indicizzazione hanno risposto in 0,080/0,078/0,081 s.
Questi dati non sostituiscono i tempi e la precisione del flusso UI completo.
La prima prova di quantizzazione non ne dimostrava l'applicazione. La prova
successiva ha verificato 218 moduli Linear realmente quantizzati a int8, ma
ha restituito 11/12 risultati corretti contro 12/12 del precedente e del nuovo
float32: non è adottata. L'inferenza è stata eseguita con rete bloccata.

La prova sotto indicizzazione reale ha rilevato un timeout HTTP 429 con due
testi lunghi per turno. Il servizio ora lavora un testo per turno e le nuove
generazioni conservano tutto il contenuto in segmenti di 768 caratteri.
Otto domande sotto carico hanno risposto HTTP 200 in 0,287–0,767 secondi;
il precedente, nel confronto sotto carico, in 0,046–0,319 secondi. Il requisito
prestazionale non è ancora soddisfatto e il profilo operativo rimane quello
precedente. Non mescolare vettori float32 e int8.

La ripresa della migrazione valida ogni generazione con la stessa dimensione
dei segmenti salvata nel checkpoint: il controllo con una dimensione diversa
causava due rivalutazioni ripetute pur senza nuove scritture. La correzione è
stata provata sul primo repository: 626 chunk invariati, nessuno da elaborare.

Il corpus RAG locale di due studi è in prova su copie SQL coerenti: 626 e 790
chunk, inclusi segmenti storici troppo lunghi e testo binario impropriamente
classificato come letto. In locale Normattiva contiene 756.290 chunk e manca
l'indice vettoriale precedente; in produzione l'indice precedente contiene
804.387 righe. La sostituzione definitiva e l'accettazione UI sono ancora aperte.

## Ripresa dell'08/10/2026 — attivazione ancora aperta

La ricerca dei vettori usa una cache binaria float32 del medesimo embedding,
senza quantizzare il modello. Su tre domande del corpus reale, i primi cinque
chunk e i segmenti scelti coincidono con il calcolo precedente: ordinamento
in 0,147/0,070/0,069 secondi contro 0,888/0,762/0,760 secondi. L'inferenza
isolata nello stesso confronto impiega 0,086/0,083/0,077 secondi. Non sono
misure del flusso UI sotto carico e non chiudono il requisito prestazionale.

La ricerca testuale del profilo nuovo usa stato e impronte della stessa
generazione: non restituisce testo invalido, fonte modificata o testo cambiato
coperto da un vecchio embedding. Non eredita dal modello precedente lo stato
negativo o il limite di lunghezza quando la nuova generazione completa è
verificata. Sei ricerche su copie dei due repository hanno restituito 24
candidati ciascuna, senza generazioni invalide o impronte obsolete.

Le copie controllate contengono 430/196 e 595/195 generazioni rispettivamente
valide/negative; gli esiti negativi restano registrati. Due testi sono stati
recuperati dal SQL documentale corrente, con identità della fonte, hash e
versione verificati, mediante l'indicizzatore nativo e senza leggere originali.
Le copie e i backup SQL verificati con `quick_check` sono conservati fuori Git.
Parte dei riferimenti storici non corrisponde all'inventario corrente dei
fascicoli: prima dell'attivazione occorre completarne la riconciliazione,
senza inventare collegamenti o qualificare il solo cache hit come prova.

Il lettore ordinario Normattiva aveva un errore `SQLITE_CANTOPEN`: la traccia
di sistema ha rilevato `EACCES` nella creazione del WAL sul bind mount Windows.
Una lettura con SQLite nativo Windows ha consentito la successiva apertura
ordinaria nel container, che legge 756.290 chunk in modalità WAL. Non è stato
aggiunto un bypass `immutable` al lettore applicativo. La stabilità dopo
ricreazione del container resta da provare nella copia reale.
La ripresa nativa dell'indice candidato ha conservato 32 righe e aggiunto
32 righe in 10,9 secondi, con checkpoint a 64 righe: l'indice completo non
è pronto. Il modello operativo precedente resta attivo.

Il trasporto locale ignora i proxy di ambiente e rifiuta reindirizzamenti HTTP,
anche per la health check. I 30 guardrail mirati passati verificano questi
contratti; non costituiscono accettazione del nuovo modello nell'interfaccia.

La ripresa ordinaria del RAG registra gli esiti negativi nel registro condiviso
(versione rag-locale.v3.sql-riscontri). Un file invariato con la stessa estrazione
rifiutata non viene letto o indicizzato nuovamente; una nuova versione SQL
corrente consente la ripresa puntuale. Tre guardrail SQL verificano il contratto,
ma il modulo deve ancora essere attivato e provato nel flusso reale.

08/10/2026 — Il percorso ordinario candidato riscontra le fonti SQL prima
dell'inferenza e prima di restituire citazioni. Su finestra controllata del
repository reale: due documenti originali, cinque passaggi verificati,
quattro passaggi derivati esclusi; ripetizione senza duplicazioni o nuovi
tentativi sui negativi invariati. Non è accettazione del nuovo modello nella UI.

La prima costruzione Normattiva dispone del job nativo
`embeddinggemma2_initial_normattiva`, disattivato per impostazione predefinita.
L'attivazione esplicita nel registro SQL prepara soltanto il candidato:
non cambia il provider dello studio. Ogni lotto usa il costruttore condiviso,
budget di 60 secondi, una richiesta per volta e lock di processo condiviso;
limite assoluto del processo figlio di 240 secondi. Il registro conserva
esiti, checkpoint e retry con attesa crescente fino a 60 minuti, ripristinando
l'intervallo precedente al recupero. A costruzione finita prosegue la riconvalida
nativa tramite `--riconvalida-finale`: impronte e ID cancellati vengono controllati
in lotti riprendibili di massimo 2.000 righe, entro il medesimo budget temporale.
La firma fisica del database SQLite e del WAL deve restare stabile; un cambiamento
riapre il controllo senza false conferme. La fonte non riceve scritture o trigger.
Solo dopo la riconvalida il job si disattiva, lasciando separata l'attivazione
del modello e la verifica di qualità delle ricerche. Una prova reale del modello
su campione SQL controllato ha corretto un testo modificato ed escluso un ID
cancellato; non certifica l'intero indice ancora incompleto.
Primo lotto del job candidato nel container reale: 174 nuovi passaggi in
60,812 secondi, totale796/756.290. Il checkpoint è incompleto.
Pianificazione installata e richiesta nel worker locale reale; esito periodico
persistente da osservare. La console admin è inaccessibile al profilo
Amministratore autenticato. Nessuna accettazione UI o sostituzione globale.
