# Release 2.458.0

- Termini «almeno N giorni prima dell'udienza» (artt. 166, 171-ter, 189, 415, 473-bis.16 c.p.c. e schede degli atti): la data da rispettare è quella prudenziale a giorni liberi; accanto si mostra la scadenza di legge secondo la lettura a giorni pieni. Motore dei termini, scadenziario, schede di Lex e obblighi di notifica usano la stessa regola; le memorie già salvate a giorni pieni passano alla data prudenziale con nota, senza toccare le date scelte dall'avvocato.
- Festività del 4 ottobre dal 2026 (L. 151/2025); termini penali senza proroga del sabato; controversie di lavoro senza sospensione feriale anche nelle proposte da PEC; provenienza delle scadenze proposte dalle PEC.
- Catalogo documenti: titolo dell'atto prima del corpo, normalizzazione OCR, nessuna proposta automatica dalle sole parole del corpo.
- PEC: classificatore unico delle ricevute; mancata consegna, non accettazione e virus mai lette come consegna; deposito rifiutato riconosciuto.
- Notifiche e calendari: bozze escluse da avvisi e calendari esterni, errori per voce con nuovo tentativo, giorni di preavviso rispettati.
- Presidio economico: importi esatti, pagoPA non eseguito, prenotazione a debito, esiti SdI EC01/EC02.
- Escluso dall'integrazione il declassamento del registro delle fonti senza impronta: bloccava ogni bozza finale degli atti e resta da completare.

## Base normativa
- Art. 155 c.p.c. (computo dei termini), artt. 163-bis, 166, 171-ter, 189, 415, 473-bis.16 c.p.c.; L. 742/1969 (sospensione feriale); L. 151/2025 (festività del 4 ottobre).
- D.M. 44/2011 e Specifiche tecniche DGSIA per le ricevute PEC; D.P.R. 115/2002 per il contributo unificato; specifiche FatturaPA/SdI.

## Verifiche
- Test nuovi: tests/test_scadenziario_171ter_ritroso.py (doppia data e riconvalida), tests/test_*_audit_20261029.py.
- Gate locale completo verde prima del push.
