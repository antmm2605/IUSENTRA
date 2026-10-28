# Archivio normativo locale su immagine dati

`mount_data_image.py` monta soltanto l'immagine ext4 indicata da `/etc/iusentra/normativa-image.json`, verificando UUID, backing file e punto di mount. Non crea immagini o database e non formatta dischi. Il punto di mount deve essere già predisposto e vuoto se non montato; un mount esistente diverso blocca l'avvio.

Il servizio oneshot `iusentra-normativa-image.service` attende fino a 120 secondi la disponibilità del file su D: all'avvio WSL. Il controllo `--check` non monta nulla. Il servizio non smonta l'archivio quando viene fermato: prima di qualsiasi manutenzione del filesystem occorre chiudere in modo governato i lettori e gli scrittori. Non riavviare WSL per provare questa configurazione durante acquisizioni, importazioni, salvataggi o addestramenti attivi.

Il file di configurazione è locale, amministrato e separato dai sorgenti; deve contenere `image`, `target` e `uuid`. Un errore mantiene indisponibile l'archivio: non va sostituito con un database vuoto. Conservare gli originali e le copie necessarie al ripristino.

## Registro temporale separato dall'archivio

Il runtime legge facoltativamente `PCT_NORMATTIVA_APPLICABILITA_MANIFEST` e il suo SHA-256 atteso in `PCT_NORMATTIVA_APPLICABILITA_MANIFEST_SHA256`. Il file schema1 contiene `regole` e `approvazioni`: le impronte approvate e il riferimento dell'approvazione sono distinti dalla raccolta del testo ufficiale. Nessuna approvazione viene generata dal modello o dall'importatore. Non impostare questi valori su proposte prive di approvazione.

La regola identifica l'atto con tipo, data e numero interi, ambito, evento confermato, intervallo ed esito. Gli eventuali `articoli` e `partizione_xml` ne limitano il perimetro: una regola dell'articolo390 non esclude tutto il codice. `fonti_congiunte` consente di riscontrare tutte le disposizioni necessarie alla stessa regola.

Per attivare il filtro occorre anche che la fonte della regola, nella cache `PCT_NORMATTIVA_VERSIONI_DB`, coincida con testo, URL, edizione e provenienza approvati alla data dell'evento. La sola presenza della legge o la dicitura VIGENTE non sono sufficienti. Cambiare la provenienza a testo identico invalida il riscontro precedente. Senza evento, versione o approvazione riscontrati, l'applicabilità resta da verificare. Le esclusioni realmente provate sono registrate nella risposta di ricerca; una norma di scheda certamente non applicabile ferma la stesura prima della richiesta al modello, senza modificare la definizione della scheda.


### Proiezione offline verificabile

`tools/proietta_cache_akn.py` è il comando versionato per proiettare una cache chiusa e qualificata nell'archivio candidato. Richiede percorsi espliciti, gate con SHA finale, archivio primario disponibile e rapporto nuovo; crea il backup prima di modificare il catalogo e mantiene gli ID già presenti. La stessa edizione può contenere articoli integrali e avvisi: solo i primi possono fornire testo a Lex, senza scartare l'intero codice. Le edizioni senza alcun corpo acquisito non sono promosse a testi integrali. I test nativi comprendono un'edizione mista, una composta solo da avvisi e un SHA sorgente discordante.

La data d'importazione non è usata come data d'acquisizione. I timestamp dotati di fuso sono ricondotti a Europe/Rome; una data dichiarata senza fuso resta tale, senza inventare un timestamp UTC. Le ricevute del manifest NIR sono dati di provenienza, non prova d'applicabilità temporale.


### Riscontri dei metadati tecnici

`lex.normativa.metadati_akn_riscontrati` non riscrive le fonti ufficiali. Interpreta un attributo tecnico solo quando il riscontro letterale è univoco nel corpo originale: data non valida della Costituzione, con firma ed ELI concordanti, oppure suffisso non valido di un articolo di allegato, con identico numero romano e suffisso scritto nell'intestazione. Testo visibile e corpi canonici devono mantenere la stessa impronta. Il derivato ha una propria impronta ed è dichiarato come derivato tecnico, non come esportazione ufficiale.

Il pacchetto conserva l'XML originale. L'importazione ne ripete la lettura e confronta identità, pubblicazione, testo, partizione, localizzatore, rubrica, struttura e provenienza. Una successione fisica conserva separatamente data formale del fotogramma e data letterale dell'espressione; non attribuisce da sola applicabilità al fascicolo e non copre date successive all'acquisizione. La verifica di tutti i file precede backup e scrittura, ed è ripetuta prima del commit SQL. I riscontri condivisi nella stessa importazione evitano una rilettura dell'intera successione per ogni articolo.

La presenza di avvisi di abrogazione in alcuni articoli non elimina gli altri articoli integrali dello stesso atto. Articoli omonimi con localizzatori XML distinti rimangono distinti: non vengono uniti, rinumerati o selezionati arbitrariamente.

### Un solo dispositivo per immagine

Prima di qualsiasi mount, il helper acquisisce un lock globale e confronta
l'identità del backing file fra tutti i dispositivi loop. Se un altro namespace
ha già associato l'immagine, riusa quel medesimo dispositivo; non crea una seconda
associazione dello stesso file. Più dispositivi associati bloccano l'operazione e
richiedono il ripristino verificato. Il controllo finale riscontra dispositivo,
backing file e UUID. La correzione non riavvia WSL e non smonta archivi in uso.

### Il correttore testuale precedente non riscrive una fonte XML

Il comando `normattiva_riallinea.py` conserva struttura, localizzatori XML e
provenienza già registrata: se occorre rettificare una fonte, si usa la rilettura
nativa della stessa edizione. I numeri romani e le numerazioni storiche fuori
dalla grammatica del correttore non vengono reinterpretati come decimali. Il
report distingue le fonti preservate e i metadati non leggibili dalle correzioni
eseguite; preservare una fonte non ne certifica il contenuto. La riparazione
idempotente degli archivi testuali precedenti resta disponibile.
