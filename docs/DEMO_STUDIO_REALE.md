# Demo Studio Reale

## Obiettivo

Dimostrare in meno di 5 minuti che IUSENTRA puo' gestire uno studio reale senza hack, senza passaggi fuori flusso e senza aree economiche scollegate dal fascicolo.

Il percorso ufficiale e':

`cliente -> preventivo -> conferimento -> fascicolo -> attivita' -> parcella -> incasso`

## Dove si vede in prodotto

- Dashboard principale: card `Studio reale in 5 minuti`
- Timesheet: riepilogo valorizzazione e azione `Genera parcella dalle voci validate`
- Cartella cliente: workflow economico e stato dei documenti commerciali
- Fascicolo: cabina operativa con tab `Quadro intelligente`, `Workflow -> incasso`, `Controllo economico`, `Governo documentale` e `Deposito e conformita'`
- Portale cliente: timeline coerente di preventivi, conferimenti e parcelle

## Comando CLI ufficiale

```bash
iusentra demo-check --tenant=<slug-tenant>
```

Il comando restituisce:

- backend effettivo dello studio
- copertura dei sette passaggi chiave
- prossima azione utile
- snapshot JSON riusabile per audit o supporto operativo

## Sette passaggi da chiudere

1. Primo cliente
2. Primo preventivo
3. Primo conferimento
4. Primo fascicolo
5. Prima attivita' / tempo
6. Prima parcella
7. Primo incasso

## Regole di qualita'

- Il fascicolo resta il centro del lavoro operativo.
- I documenti di portale devono mostrare nome ufficiale, classificazione, tipo atto e identificativi deposito; il quadro intelligente usa solo controlli reali e valuta scadenze e udienze rispetto alla data corrente.
- Le attivita' validate possono diventare parcella senza ricopiare dati.
- Il saldo cliente deriva da parcelle e pagamenti, non da contatori manuali.
- La dashboard deve sempre dire `cosa fare adesso`.
- L'AI aiuta con riepiloghi e suggerimenti, ma non prende decisioni legali non verificate.
- `Sincronizza PEC` e `Auto-esiti` devono cercare le comunicazioni sul fascicolo usando almeno `RG + tribunale + nominativi cliente/controparte`, evitando associazioni deboli sul solo oggetto email.

## Evidenze minime da verificare

- esiste almeno un cliente attivo
- esiste almeno un preventivo
- esiste almeno un conferimento
- esiste almeno un fascicolo collegato
- esiste almeno una voce timesheet valorizzabile
- esiste almeno una parcella emessa
- esiste almeno un incasso registrato oppure un link di pagamento attivo

## Uso consigliato per demo e onboarding

1. Crea il cliente.
2. Apri il preventivo guidato.
   Il wizard usa le tabelle giuste per il tipo di pratica: D.M. 55/2014 per le fasi giudiziali, Tabella A25 per lo stragiudiziale e Tabella A27 per mediazione / negoziazione assistita.
   Quando la tipologia prevede il compenso unico, il wizard mantiene visibili le fasi operative e usa il flag dedicato come comando di calcolo: attivo genera l'importo tabellare, disattivo lascia il compenso a zero finche' non viene selezionata una voce o aggiunta una riga manuale.
   Se la pratica usa la mediazione civile / commerciale, puoi attivare anche i costi organismo ex D.M. 150/2023 con regime, esito procedura e maggiorazione art. 31, comma 3: il totale operativo cambia davvero sia nel wizard sia nella console tariffaria.
   Le opzioni fiscali, i costi ODM e le classificazioni tassonomiche aggiuntive entrano davvero nel totale e nella bozza.
   Il ricalcolo e' guidato da feedback inline coerenti e i log raccontano la sequenza operativa del calcolo senza messaggi tecnici ambigui.
3. Genera o conferma il conferimento.
4. Apri il fascicolo.
5. Registra la prima attivita' nel timesheet.
6. Genera la parcella dal timesheet validato.
7. Registra o avvia l'incasso.

Se tutti i passaggi sono chiusi, IUSENTRA non e' piu' solo un gestionale avanzato: e' una piattaforma legale operativa completa.
