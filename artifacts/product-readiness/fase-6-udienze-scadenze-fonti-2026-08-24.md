# Fase 6 — Udienze, scadenze e fonti documentali

## Obiettivo

Una rilevazione documentale non deve simulare un termine certo né costringere
l'avvocato a cercare manualmente un file dal nome ambiguo. La card deve rendere
disponibili il documento da cui proviene l'informazione e un passaggio operativo
controllato, senza creare una scadenza in modo automatico.

## Implementazione

- `DocumentPresidioPanel` usa l'identificativo del documento prodotto dal
  resolver per aprire il file nel lettore interno IUSENTRA con **Apri fonte**.
- Con data ISO rilevata e senza decorrenza da completare, **Prepara scadenza**
  apre il modulo React dello Scadenziario precompilando titolo, tipo,
  fascicolo, data, descrizione e nota sulla fonte. Nessun record viene creato
  dal click: il solo comando che persiste dati resta `Crea scadenza` nel modulo.
- Se serve la data di comunicazione, il pannello lo dichiara esplicitamente e
  non espone una data o un termine artificioso.
- L'apertura diretta di `#udienze` carica soltanto le sezioni pigre `scadenze`
  e `documenti`, così le azioni hanno la fonte disponibile senza appesantire
  l'apertura ordinaria del fascicolo.

## Dati e limiti governati

Non sono state introdotte tabelle, scritture SQL, migrazioni, regole di
catalogazione o modifiche a deposito, firma, PEC e notifica. La fonte dei dati
rimane il resolver documentale già esposto dalle API JSON del fascicolo; i
documenti e le loro azioni di anteprima restano tenant-aware. Un avviso come
`nessun termine è stato escluso automaticamente` rimane visibile ed esclude
ogni certezza fittizia.

## Prova reale locale

Eseguita il 24/08/2026 sulla copia Docker reale
`http://127.0.0.1:8080`, fascicolo `DC5BF1DB`, sezione **Udienze e scadenze**:

1. apertura diretta della sezione e caricamento delle fonti reali;
2. click su **Apri fonte** della rilevazione del 19/03/2023: aperto nel lettore
   interno il documento `Note trattazione scritta Alessi Robertino c Zurich
   Ass.ni-signed.pdf.p7m`, con le pagine PDF visibili;
3. chiusura del lettore e click su **Prepara scadenza**: aperto il modulo
   React `/scadenziario/nuova` con titolo, tipo `UDIENZA`, data `19/03/2023`,
   fascicolo, descrizione e nota di provenienza già valorizzati;
4. nessun click su `Crea scadenza`, quindi nessuna scrittura di dati di prova;
5. controllo visivo desktop e mobile 390×844: card, testi, pulsanti e avvisi
   leggibili; nessun overflow orizzontale (`scrollWidth` non superiore alla
   larghezza del documento); hover e focus tastiera del comando **Apri fonte**
   con contrasto e contorno visibile.

La prova riguarda questa fase. Non dichiara conclusi gli altri flussi del
fascicolo, le fasi successive o il programma completo.
