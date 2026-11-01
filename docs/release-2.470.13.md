# 2.470.13 — Registro delle letture sotto carico e salute dello scheduler dopo il deploy

- Lettura automatica dei fascicoli: dopo la 2.470.12 il registro (già in WAL, verificato sul server) dava ancora
  «database is locked» nel salvataggio delle letture e dei fatti quando il giro ogni 10 minuti, i presìdi e l'AI
  locale lavoravano insieme (server saturo: AI locale al 600% di CPU, memoria di scambio quasi piena). Chi scrive sul
  registro ora attende fino a 120 secondi invece di 30; le consultazioni in sola lettura restano a 30 secondi e non
  attendono chi scrive.
- Deploy: il controllo di salute dello scheduler considerava «guasto certo» anche un fallimento della versione appena
  sostituita, così l'attesa di salute del deploy della 2.470.12 è scaduta con lo scheduler giudicato non sano. Un
  fallimento concluso prima dell'avvio del worker resta segnalato come degrado ma non annulla l'attesa del primo giro.
  Test nuovo in `tests/test_scheduler_health_fallimento_precedente.py`.
- Workflow «Stato delle pianificazioni»: mostra il tipo d'errore completo, l'ultimo fallimento di ogni pianificazione
  e la modalità del registro delle letture (solo dimensioni e modalità, nessun dato dello studio).
- Verificato dal vero il 01/11 alle 23:30: piano del giorno rigenerato senza gli avvisi ripetuti; agenda con
  «Orario da verificare» al posto di 00:00; Scadenziario e Controllo Studio concordi (3 scaduti, 7 udienze con esito
  da registrare); fascicolo aperto anche dal telefono.
