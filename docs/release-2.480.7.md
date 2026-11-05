# Release 2.480.7 — catena notturna senza blocchi

Correzioni nate dal controllo sul server del 05/11/2026 (registro della notte e registro delle letture).

1. **Passo fermo sul semaforo dei motori** — nella notte del 04/11 un passo in attesa del semaforo ha fermato la
   catena dalle 05:08 alle 07:30. Ora un passo che non ottiene il semaforo entro 20 minuti si rinvia (esito
   «Rinviato: semaforo occupato») e la catena prosegue (`pct/scheduler_notturno/catena.py`).
2. **Ogni notte dalla fase 1** — la catena ripartiva dal passo rimasto la notte prima e saltava posta e PEC.
   Ora riparte sempre dalla fase 1; resta annotato dove si era fermata la notte precedente.
3. **«database is locked» nella lettura automatica** — un archivio occupato da un altro motore rinvia la sola
   attività al giro successivo invece di far fallire il giro (`web/services/archivio_letture_runtime.py`).
4. **Riletture senza variazioni (49)** — verificate: sono la rilettura unica, dai testi già salvati, dopo il cambio
   delle regole di lettura delle parti del 02/11 (versione del lettore). Comportamento previsto, nessuna modifica.
5. **Anteprima di PDF malformati** — un allegato PEC con annotazioni cicliche dava errore 500; ora la pagina si
   mostra senza il livello di testo o senza i soli link (`web/services/pdf_reader_text.py`,
   `web/bootstrap/fascicoli_document_helpers.py`).

Inclusi anche: collaudo del lettore con scrittura atomica (4c7ec036d) e backup degli indici ricevute interrotto che
non blocca più il deploy (2.480.6).

Base: art. 3 D.M. 44/2011 e art. 20 CAD per il registro delle letture; nessun cambiamento nei flussi di deposito.
