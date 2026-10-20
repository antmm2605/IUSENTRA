# Fonti economiche e prova della lettura — 20 ottobre 2026

## Risultato richiesto

Aprire il documento probatorio dal contributo o dalla liquidazione, anche prima
della conferma nel form. Consultare le evidenze in una finestra senza aumentare
l'altezza delle righe. Nessuna lettura o scansione documentale aggiunta alle GET.

## Procedura riutilizzata

Il payload SQL esistente fornisce `fontiVerifica`, fonte, impronta, collegamento
autorizzato e riscontri. Il lettore e il gestore finestre restano quelli condivisi.
Una fonte unica senza riscontri mancanti si apre direttamente; più fonti,
discordanze o collegamento assente aprono il pannello delle evidenze. La
ricevuta dimostra un pagamento; la dichiarazione di esenzione resta distinta.
Aprire o chiudere la fonte non salva la bozza e non spunta la conferma.

## Prova materiale sulla copia reale 8080

- Sentenza originale Polisweb, documento `DF326A39`: comando normale
  «Riconosci il testo», 11 pagine su 11 e 22.587 caratteri da testo nativo.
  Confrontate tutte le pagine affiancate fino al dispositivo, compresi grassetti,
  corsivi, sottolineature e importi. Distinti beneficio di 500 euro e onorari di
  257,50 euro con accessori. Originale non sostituito né modificato.
- Corretto il falso ruolo `37/2018` prodotto dall'intestazione ripetuta prima
  della continuazione di un riferimento normativo. Ripetuto lo stesso comando
  sullo stesso PDF: stessi caratteri e pagine, solo ruolo `2313/2025`; il numero
  della norma resta nel testo originale.
- Vista economica: clic sulla liquidazione controllata di 321 euro apre il
  PDF collegato; clic sul contributo apre la ricevuta controllata, oppure
  l'autocertificazione originale nel caso di esenzione. In assenza di fonte
  collegata viene mostrata esplicitamente la mancanza.
- Nel caso con fonte fiscale discordante restano leggibili entrambe le
  evidenze e la causa; nessun importo della fonte discordante viene attribuito.
- Campo modificato senza salvataggio: apertura e chiusura del lettore con Esc
  conservano il valore; ripristinato il valore iniziale senza scritture.
  La casella di conferma rimane deselezionata dopo la lettura.
- Verificati desktop e apertura del lettore da scheda mobile a 390 × 844.
  Le prove sui documenti di collaudo non costituiscono verifica di pagamenti reali.

La firma di preparazione del catalogo locale era mancante: eseguita la procedura
nativa sul solo proprietario SQL con backup persistente e controllo d'integrità;
il comando «Riprova» ha poi mostrato il catalogo senza errore di schema.

## Guardrail e compatibilità degli incassi

La CI precedente attendeva ancora che un cambio di stato producesse un incasso.
Questa aspettativa contraddice il registro incassi SQL introdotto nella 2.442.0.
I test del vecchio comando verificano ora il rifiuto e l'assenza di scritture,
anche su ripetizione, mantenendo controlli su cliente, revisione, importo e data.
Eliminata inoltre la creazione parziale della proforma prima del rifiuto.
I cicli positivi di incasso, saldo, storno, idempotenza, concorrenza e parità SQL
restano verificati dai test del repository incassi e del suo ciclo nativo.
Nessun gate CI viene disabilitato o escluso.

Questa nota registra le prove osservate; la chiusura del rilascio richiede ancora
riscontro dello stesso commit nell'immagine locale e su Hetzner, gate remoti,
servizi sani e pulizia governata con spazio prima/dopo.

## Adeguamento CodeQL nella 2.442.2

La CI applicativa della 2.442.1 è passata. CodeQL ha segnalato il controllo regex
del separatore tra ruoli; la finestra del prefisso era già limitata a 90 caratteri,
ma il controllo ora usa soltanto confronti letterali. Nessuna soppressione o
modifica dei gate. Conservati gli elenchi con virgola, punto e virgola, congiunzioni
e marcatore «n.»; provata anche una sequenza di 200.000 tabulazioni.
