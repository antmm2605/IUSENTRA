# Spazio Docker e disco Windows

La dimensione totale delle immagini Docker non misura lo spazio fisico restituito a Windows. I livelli condivisi possono essere contabilizzati più volte e la cancellazione interna non riduce automaticamente il file VHDX.

## Misure obbligatorie

Prima e dopo la manutenzione registrare separatamente:

- inventario immagini e cache del motore;
- dimensione del file VHDX;
- percorso fisico risolto del file, inclusi junction e collegamenti;
- spazio libero del volume Windows che contiene realmente il file;
- container precedentemente attivi, volumi e processi di addestramento da preservare.

Il preflight `tools/check_build_space.py` risolve i collegamenti e somma i budget sul medesimo volume fisico. Lo spazio libero interno al disco virtuale non compensa un volume Windows insufficiente. Un inventario Docker non disponibile interrompe la pulizia prima delle rimozioni.

## Compattazione governata

La compattazione richiede una manutenzione distinta dalla pulizia delle immagini. Verificare prima che nessun addestramento dipenda da Docker. Arrestare ordinatamente i container e soltanto Docker Desktop con i comandi nativi; non spegnere il PC, non riavviare Windows e non arrestare globalmente WSL. Conservare gli inventari e i backup esistenti; non cancellare volumi, dati, checkpoint o sorgenti.

Usare esclusivamente la procedura Microsoft sul file VHDX identificato, dinamico e scollegato. Non ridimensionare il filesystem o la capacità virtuale, non formattare e non compattare il disco mentre è aperto in scrittura. Non interrompere un'operazione nativa già avviata per simularne la conclusione. Tempi e spazio recuperabile dipendono dalla disposizione dei blocchi e dal disco fisico: nessuna promessa basata sulla somma delle immagini eliminate.

Al termine riavviare Docker, ripristinare soltanto i container che erano attivi e confrontare gli inventari dei volumi. Verificare servizi e copia locale su porta 8080, processi protetti e spazio fisico prima/dopo. Un comando riuscito senza riduzione del file non dimostra recupero di spazio.

Fonte primaria: [Microsoft Optimize-VHD](https://learn.microsoft.com/en-us/powershell/module/hyper-v/optimize-vhd).
