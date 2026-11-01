# 2.470.10 — Deploy senza blocco del registro, correzioni dalla verifica a vista

- Deploy: la preparazione del registro delle letture (`tools/prepare_reading_runtime.py`) attendeva solo 5 secondi
  e fermava il deploy della 2.470.9 con «database is locked», perché la versione in servizio stava scrivendo per il
  recupero delle letture. Ora la connessione attende fino a 60 secondi e il blocco temporaneo si ritenta tre volte;
  ogni altro errore ferma il deploy come prima.
- Contiene la 2.470.9 (registro delle letture in modalità WAL), mai arrivata in produzione.
- Piano del giorno: un avviso per tipo con il numero delle attività (prima otto righe identiche).
- Agenda: l'orario scritto nella PEC o nell'atto prevale anche sulla mezzanotte; senza orario si legge «Orario da
  verificare» invece di «00:00».
- Controllo Studio: le udienze passate stanno in «Udienze passate: esito da registrare» e non contano tra i termini
  scaduti, come nello scadenziario (regola V28; artt. 126 e 127-ter c.p.c.). Prima: «10 termini scaduti» contro
  «3 scadute da chiudere» nello scadenziario.
