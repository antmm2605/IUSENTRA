# IUSENTRA 2.486.0 — Conto economico del fascicolo

## Conto economico nella vista economica e dentro il fascicolo

Lo stesso pannello «Conto economico» si apre in due punti:
- con il pulsante nella riga di ogni fascicolo della vista economica (`/fascicoli?vista=economica`);
- nella sezione «Conto economico» del fascicolo (`/fascicoli/<id>#conto-economico`).

I dati arrivano da `GET /api/v1/ui/fascicoli/<id>/conto-economico`, in sola lettura (moduli
`pct/fascicolo_conto_economico.py` e `web/services/fascicolo_conto_economico_runtime.py`).

### Percorso, con le norme vigenti

Sentenza → proforma (avviso di parcella) → pagamento ricevuto → fattura elettronica di pari importo → conferma
dell'avvocato.

- **Momento della fattura.** Per l'avvocato la prestazione si considera effettuata al pagamento (art. 6, terzo comma,
  D.P.R. 633/1972). La fattura si emette per l'importo ricevuto entro dodici giorni (art. 21, comma 4, D.P.R.
  633/1972). Il pannello indica la data limite e segnala se è superata.
- **Pulsanti dei passaggi.** Ogni passaggio ancora da fare ha il suo pulsante: «Prepara la proforma», «Registra
  l'incasso», «Emetti la fattura elettronica», «Conferma il pagamento». Le operazioni fiscali restano un gesto
  dell'avvocato nel documento economico.
- **«Pagato» automatico.** Un «pagato» segnato dalla lettura automatica della sentenza non è una prova di incasso: il
  pannello lo dice e chiede di registrare l'incasso reale.

### Voci, ognuna con la sua fonte cliccabile

- **Importo liquidato in sentenza.**
  - Si considerano solo le sentenze della causa: quelle allegate come precedenti sono escluse.
  - Se il giudice ha disposto la distrazione delle spese in favore dell'avvocato (art. 93 c.p.c.), il pannello lo
    indica.
  - Lo stesso importo letto da più copie della sentenza si conta una volta sola, con l'avviso di verificare.
- **Contributo unificato.**
  - Versato, se c'è la ricevuta (art. 13 D.P.R. 115/2002).
  - Esente, se c'è l'autocertificazione del reddito (art. 9, comma 1-bis, D.P.R. 115/2002); «da confermare» finché
    il documento non è confermato.
  - Una PEC di deposito classificata come «versamento» non prevale sull'autocertificazione.
- **Parcella, spese ed esborsi, anticipazioni.** Si leggono dai documenti economici e dal fondo spese. Le
  anticipazioni sono documentate con la loro fonte (art. 15, primo comma, n. 3, D.P.R. 633/1972).

### Vista economica

- Il contributo unificato con autocertificazione si mostra come «Esente · Autocertificazione», non più «n.d.».
- I valori non vengono più tagliati con i puntini.

## Cerca norme e sentenze

Quando la norma citata viene trovata, non compare più l'avviso tecnico «riferimento non reperito nell'archivio
generale».

## Velocità dei caricamenti, senza cambiare i comportamenti

Tempi misurati prima e dopo sui dati reali dello studio:

- **Fascicoli letti dall'archivio: da 3,5 s a 1,1 s.**
  - Prima, a ogni caricamento, il software ricalcolava subito per ogni fascicolo, documenti compresi, la «fotografia»
    che serve solo a un eventuale salvataggio.
  - Ora la calcola al primo uso, ricostruendola dalla stessa riga con la stessa funzione pura (`pct/fascicoli.py`).
  - Verificato sui 336 fascicoli reali: la fotografia è identica a quella di prima.
  - Il guadagno vale per agenda, elenco fascicoli, Lettura, guida e conto economico.
- **Agenda: da circa 4,9 s a circa 2,6 s per richiesta.**
  - Le modifiche fatte da altri (lavori automatici, letture dei fascicoli) la ricaricavano ogni 2-3 secondi.
  - Ora la aggiornano al più ogni 30 secondi, e non mentre la scheda del browser è nascosta.
  - I comandi dell'avvocato restano immediati.
  - La regolazione si sceglie pagina per pagina (`OperationalRefreshPacing`): le altre pagine si comportano come
    prima.
