# Termini e notifiche: correzioni giuridiche della Fase 0

Prima fase del piano `docs/PIANO_CATENA_DOCUMENTALE_2026-10-29.md`, autorizzata dall'utente il 29/10/2026. Corregge calcoli che producevano scadenze sbagliate.

- **Memorie art. 171-ter c.p.c.** I preset contavano 40, 20 e 10 giorni dopo l'udienza. Ora contano a ritroso dall'udienza («almeno … giorni prima»), con sospensione feriale e, se l'ultimo giorno è sabato o festivo, anticipo al giorno utile precedente (art. 155 c.p.c.). Il risultato coincide con il motore delle schede di Lex (`pct/schede_termini.py`). Nuovi profili `TERM_40/20/10_DAYS_BEFORE`.
- **Riconvalida automatica.** Ad ogni giro degli avvisi di Agenda e Scadenziario, le memorie 171-ter aperte che portano ancora la data del vecchio calcolo vengono ricalcolate, con una nota che riporta la data precedente. Una data modificata dall'avvocato non si tocca: riceve solo una nota con la data corretta da verificare. L'operazione è idempotente (`pct/riconvalida_termini_ritroso.py`).
- **Termine lungo di impugnazione (art. 327 c.p.c.).** I preset di appello e Cassazione escludevano la sospensione feriale (L. 742/1969). Ora i sei mesi si allungano dei giorni di agosto attraversati, anche nel calcolo semplice dello scadenziario.
- **Prescrizione breve.** Il preset dei cinque anni usava il profilo da un anno: dal modulo web la scadenza risultava dopo un anno.
- **Obblighi di notifica.**
  - La relata non chiudeva mai l'obbligo: la raccolta non produceva il collegamento all'atto. Ora l'obbligo si chiude quando nella stessa copia notificata dell'atto ci sono relata confermata e ricevuta di avvenuta consegna (art. 3-bis L. 53/1994) e sono nominati tutti i destinatari. Altrimenti resta aperto e dice che cosa manca.
  - Una relata in un file separato non si collega per somiglianza.
  - Nuovo termine breve (art. 325 c.p.c.; art. 92 c.p.a.), che decorre dalla notificazione della sentenza letta nella copia notificata, solo se univoca.
- **Ora italiana.**
  - Il motore PEC dell'archivio leggeva giorno e ora di ricezione in UTC: una consegna delle 00:30 risultava del giorno prima. La versione del motore cambia, quindi le PEC vengono riconvalidate.
  - «Oggi» nei presìdi, nello scadenziario, negli obblighi di notifica e in Polisweb è ora il giorno italiano (`pct/ora_italiana.py`).
- **Calendario Microsoft.** In scrittura l'orario italiano veniva dichiarato UTC (udienza spostata di 1-2 ore in Outlook); in lettura l'UTC di Graph veniva trattato come ora italiana. Le scadenze importate da calendari esterni prendono il giorno italiano.

Non modificati: flusso deposito/firma/PEC congelato, busta, invio PEC, motore delle schede di Lex.

Test aggiunti: `tests/test_scadenziario_171ter_ritroso.py`, `tests/test_ora_italiana.py`, `tests/test_calendar_microsoft_fuso.py` e nuovi casi in `tests/test_obblighi_notifica.py`.

Punto aperto per l'avvocato: i modelli del motore dei termini (`pct/termini_processuali.py`, `CIV_MEMORIA_171_TER_*`) trattano le memorie come termini «liberi», cioè un giorno prima rispetto al calcolo delle schede e dello scadenziario. La scelta fra le due letture dell'art. 171-ter spetta all'avvocato; finché non la conferma, il motore dei termini resta invariato.
