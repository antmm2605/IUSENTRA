# Conoscenza del software per gli agenti

Graphify è uno strumento di sviluppo dell’agente. Non è un motore di IUSENTRA, non acquisisce fascicoli e non modifica i dati dello studio.

## Fonte e installazione

Usare il pacchetto ufficiale `graphifyy==0.9.93` e la skill Codex originale distribuita dal pacchetto, con i suoi riferimenti. Non sostituire la skill con un riassunto. La configurazione locale verificata usa Python in `C:/Users/antmm/.codex/tools/graphify-env`; Graphify e l’estensione SQL rimangono separati dall’ambiente applicativo. La skill installata viene scoperta da Codex dal turno successivo; in una sessione già avviata leggerla esplicitamente prima di applicarla.

Fonte ufficiale: https://github.com/Graphify-Labs/graphify.

## Costruzione ripetibile e incrementale

Eseguire `tools/agent_knowledge/build_graph.py --out <cartella esterna dedicata>` con il Python dell’ambiente Graphify. Il comando:

1. Seleziona soltanto sorgenti versionati e configurazioni JSON esplicitamente ammesse, mantenendo i percorsi relativi originali. Registra HEAD, versione, SHA-256 e dimensione di ogni file della copia di lavoro: HEAD da solo non certifica modifiche non ancora committate.
2. Esclude risultati e prove in `artifacts`, asset e bundle generati, patch, esempi, pacchetti già generati in tools/dist e baseline storiche metaharness; non enumera database, volumi, allegati o addestramenti. Le esclusioni sono esplicite nel manifesto.
3. Aggiorna solo copie cambiate in una cartella di proprietà attestata, senza cancellazioni ricorsive. Una cartella estranea o un collegamento che esce dal perimetro viene rifiutato.
4. Richiama l’estrazione ufficiale Graphify in modalità `--code-only`, con un solo processo di estrazione e cache persistente. Non avvia backend semantici, server, modelli o chiamate a fornitori AI.

Destinazione locale: `C:/Users/antmm/.codex/knowledge/IUSENTRA/`. Il grafo è `graphify-out/graph.json`; `source-manifest.json` identifica i sorgenti selezionati; la diagnostica e l’indice distinguono quelli effettivamente riconosciuti. `source/` è soltanto una copia per analisi, non è una copia applicativa e non va avviata, collaudata o distribuita. Tutte le modifiche e le prove del prodotto restano nella copia reale IUSENTRA.

Per comunità e rapporto usare il comando ufficiale `cluster-only <source> --graph <graph.json> --no-label --no-viz`; per la visualizzazione usare `export html --graph <graph.json>`. La visualizzazione aggregata non mostra ogni simbolo: il grafo JSON resta la fonte interrogabile completa dell’estrazione.

Per creare l’indice navigabile eseguire `tools/agent_knowledge/index_graph.py --out <stessa cartella>`. Produce `SOFTWARE_INDEX.md` e `coverage-index.json`: settori, tassonomia delle materie e simboli per ogni file, con ID e posizione. Registra separatamente l’impronta del grafo e del manifesto, senza modificare il grafo originale o aggiungere relazioni inferite come se fossero estratte.

## Uso prima di intervenire

1. Leggere AGENTS.md e la skill Graphify. Controllare manifesto, revisione, modifiche dei file pertinenti e diagnostica dell’estrattore.
2. Consultare `query`, `explain`, `path` e `affected` ufficiali, usando `--graph` sul grafo corretto e un budget mirato. Evitare di caricare il grafo intero nel contesto dell’agente.
3. Seguire sorgente → motore → repository SQL → evento/job → API → interfaccia → persistenza, includendo chiamanti indiretti, tenant, autorizzazioni e audit. Conservare file e righe delle evidenze.
4. Separare `EXTRACTED`, `INFERRED` e collegamenti ambigui. Leggere i sorgenti dei passaggi non risolti. Un import dinamico, una tabella creata dentro una stringa o una chiamata risolta a runtime possono richiedere riscontri aggiuntivi.
5. Scegliere la modifica minima e i test dei consumatori interessati. Dopo la modifica aggiornare il grafo tramite lo stesso costruttore e confrontare l’impatto. Le prove reali su 8080, CI e deploy continuano a seguire AGENTS.md.

## Settori, funzioni e materie

`tools/agent_knowledge/domains.json` contiene punti d’ingresso verificabili per i settori operativi. È un indice di navigazione: l’appartenenza suggerita non è un nuovo contratto applicativo. I simboli, le funzioni e i collegamenti si ricavano dal grafo, con provenienza al sorgente, senza duplicare regole operative in istruzioni locali divergenti.

Per le materie usare la tassonomia già dichiarata in `lex/normativa/materie.py` (`MATERIE`), i cataloghi di `pct/template_atti_catalogo_data/` e le procedure di `pct/practice_engine/`. Non assegnare una materia per somiglianza del nome e non confondere la presenza di un modulo con una capacità collaudata. Per nuovi casi seguire nel grafo il catalogo effettivo, il resolver, i vincoli e i test della procedura.

Gli inventari storici di route, SQL/JSON e sincronizzazione sono indizi da riconfermare sui sorgenti attuali, non prove di copertura globale. I dati dell’avvocato e le fonti legali correnti restano nei repository proprietari: Graphify non sostituisce RAG, motori documentali o verifiche giuridiche.

## Limiti da rendere sempre espliciti

- Copertura dei sorgenti, riconoscimento dei simboli, relazioni inferite e accettazione funzionale sono misure diverse.
- File esclusi, non supportati, parzialmente estratti o senza simboli devono restare nel resoconto; non diventano automaticamente funzioni mancanti o errori del prodotto.
- HTML/Jinja, YAML, documentazione e contenuti binari non sono analizzati semanticamente dalla modalità code-only. Anche i JSON con forma di dati e gli schemi non riconosciuti sono esclusi intenzionalmente dal passaggio AST ufficiale Graphify; il manifesto e l’indice li distinguono dai sorgenti con simboli. Quando servono a una modifica, leggerli e applicare il percorso semantico ufficiale soltanto al materiale tecnico pertinente, mantenendo fuori dati e documenti dello studio.
- Nessuna dichiarazione di conoscenza perfetta o di assenza di regressioni può derivare dal solo grafo.
