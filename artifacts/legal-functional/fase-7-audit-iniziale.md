# Fase 7 - Audit funzionale iniziale

## Aree verificate

Fascicoli, Clienti, Soggetti, Documenti, Agenda, Scadenziario, Attivita, Telematico, Depositi, PEC/Messaggi, Template atti, Redazione atti, Tariffario, Preventivi, Conferimenti, Parcelle/Fatture, Incassi/Pagamenti, Lex AI, Legal Intelligence, Audit/permessi/multi-tenant.

## Flussi disponibili

- Cliente/Soggetto/Fascicolo: presenti nel dominio e nelle API React gia censite.
- Documenti: console e bridge esistenti, stati OCR/PDF-A/firma da preservare.
- Agenda/Scadenziario: collegamenti a fascicolo gia previsti dal dominio.
- Economico: preventivi, conferimenti, tariffario, fatturazione e incassi hanno route React full gia governate.
- Legal Intelligence/Template: metadati reali ora in React full read-only.

## Flussi incompleti

- Generazione atto end-to-end e passaggio firma/deposito restano su percorsi dedicati.
- Portali telematici specifici restano legacy per compliance.
- Dettagli/export economici e documentali restano legacy.
- PEC completa non va dichiarata completa se configurazione reale non e' presente.

## Endpoint usati

Endpoint `/api/v1/ui/*` per le route React; endpoint telematico esistenti solo dove gia censiti. Nessun nuovo endpoint massivo introdotto.

## Errori e rischi

Rischio principale: falsa promozione React di route con file, firme, PDF/A, XSD, PIN, sessioni o export. Mitigazione: mantenute legacy e documentate.

## Test mancanti

Mancano ancora test end-to-end completi su tutti gli 8 workflow legali richiesti; aggiunto test di registro fonti ufficiali come base compliance.
