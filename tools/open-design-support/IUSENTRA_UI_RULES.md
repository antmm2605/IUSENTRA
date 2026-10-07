# Regole UI/UX per Codex - IUSENTRA

## Regole generali

- Tutto il testo visibile deve essere in italiano.
- Le date devono usare formati italiani.
- La UI deve essere professionale, sobria e adatta a studi legali.
- Ogni pagina deve indicare chiaramente stato, prossima azione e dati mancanti.
- Ogni azione sensibile deve avere feedback chiaro.
- Ogni modifica UI deve rispettare permessi, tenant e audit quando applicabile.

## Prima di modificare una UI

Codex deve dichiarare:
- schermata interessata;
- obiettivo;
- utenti coinvolti;
- file modificabili;
- file vietati;
- rischio principale;
- test o smoke da eseguire;
- criterio keep/discard.

## Stati obbligatori

Per ogni nuova superficie UI valutare:

- stato normale;
- stato vuoto;
- stato loading;
- stato errore;
- stato successo/conferma;
- stato permesso negato;
- stato dato incompleto.

## Coerenza visiva

- usare componenti esistenti quando possibile;
- evitare CSS isolato non governabile;
- preferire classi Bootstrap/coerenti con il bundle esistente;
- se si aggiunge SCSS/CSS, deve essere collocato nel percorso governato;
- non creare stili inline sparsi salvo casi minimi e motivati.

## Accessibilita'

- label associate ai campi;
- contrasto sufficiente;
- focus visibile;
- bottoni con testo comprensibile;
- icone non usate da sole per azioni importanti;
- gerarchia heading coerente.

## Criteri di scarto

Scartare o rivedere una proposta UI se:
- sembra un template generico;
- usa testi inglesi;
- usa colori fuori palette;
- crea layout bello ma poco operativo;
- rompe responsive;
- nasconde azioni principali;
- non gestisce stati vuoti/errori;
- non rispetta navigazione esistente;
- richiede modifiche backend non autorizzate.


## Regola permanente: card operative, compatte e aggiornamento automatico

Direttiva dell'utente, 05–06/10/2026, valida per nuove card e card già presenti in tutto IUSENTRA:

- Ogni card con conteggio o stato è un comando utile al proprio contesto: filtra l'elenco corrispondente o apre il dettaglio nella stessa area di lavoro. Il numero e il risultato usano lo stesso perimetro, stato, periodo, tenant e permesso. Le card a zero restano interrogabili e mostrano uno stato vuoto esplicito.
- Filtri combinabili, ricerca, azzeramento e stato selezionato riconoscibile. Le liste che consentono lettura prevedono selezione singola/tutte le corrispondenze e conferma della lettura dei selezionati, oltre le pagine visibili. Segnare letto non completa scadenze, attività processuali o presìdi e non nasconde un problema reale.
- Le card sono compatte e lasciano spazio al contenuto principale. Nessun titolo o comando indispensabile viene coperto da finestre, dock, header sticky o footer; su touch i testi utili devono essere leggibili senza tooltip.
- Ogni scrittura confermata aggiorna automaticamente la vista, i conteggi e le finestre correlate, preservando filtri e contesto. Feedback immediato di caricamento, controllo disabilitato durante l'operazione e risultato/errore comprensibile. Aggiorna manuale serve per ricaricare fonti, non per vedere l'esito del comando appena eseguito. Risposte HTML, incomplete o negative non generano conferme positive.
- Finestre spostabili anche quando inattive, riducibili, ripristinabili, ingrandibili, affiancabili e chiudibili con X; un dettaglio incorporato usa i comandi della finestra contenitrice, senza duplicare cornici per lo stesso oggetto. Focus, tastiera, hover e contrasto restano verificabili.
- Le regole si applicano retroattivamente alle superfici esistenti. L'inventario e l'accettazione materiale restano aperti finché ogni punto del perimetro assegnato è stato verificato su browser reale e copia locale8080 aggiornata; questa registrazione non sostituisce l'implementazione né la prova.
### Finestre: ridimensionamento e affiancamento
Ogni finestra di lavoro deve offrire ridimensionamento libero dai bordi e dagli angoli, utilizzabile anche su una finestra non attiva. Tastiera: frecce per modifiche precise, Shift+frecce per passi maggiori. Dimensioni minime adattive, limiti del viewport e spazio riservato alla barra delle finestre mantengono raggiungibili contenuti e azioni. Ingrandimento e affiancamento a metà/quadranti devono consentire il ripristino delle dimensioni libere scelte. La gestione condivisa di OperationalModal e pannelli esistenti evita controlli divergenti; ogni superficie va provata nel browser reale, compresi scroll completo, responsive e focus. Nessuna lettura massiva può completare attività legali.

Un clic o il focus nel contenuto porta davanti la finestra scelta, compresi i contenuti incorporati; la barra delle finestre indica quella attiva. Le colonne interne si adattano alla larghezza della finestra, non soltanto alla larghezza dello schermo. Gli stili della barra dei comandi si applicano soltanto all’intestazione e non alterano menu, passi o navigazioni all’interno del contenuto. Non lasciare titoli, azioni o riepiloghi coperti dal dock durante lo scorrimento completo.


## Finestre documentali nel contesto principale
L’apertura di un documento persistente da un fascicolo già incorporato deve creare una finestra indipendente nel gestore principale, con lo stesso lettore e gli stessi comandi esistenti. Le riaperture richiamano la finestra esistente anche se minimizzata. Ogni richiesta è vincolata all’origine, a un iframe noto e alla corrispondenza tra fascicolo, documento, preview e download. I percorsi congelati di firma/deposito/PEC e i file temporanei conservano la procedura accettata. I limiti dimensionali usano la larghezza utile senza scrollbar; nelle finestre strette l’intestazione deve lasciare spazio al documento, con nome accessibile e comandi visibili.
