# Logica Studio Legale Telematico

Generato: 30/06/2026 18:10 (Europe/Rome).

## Flusso deposito ricostruito

1. L'albero schema propone macroarea, categoria e tipo deposito.
2. La scelta imposta una chiave tecnica come `Introduttivi_SICID::Citazione` o `Atti_UNEP::Pignoramento`.
3. `QualeTipologiaDeposito` e `FindSchemaXSD` decidono campi, validazioni e generatore `DatiAtto.xml`.
4. La busta viene preparata con atto principale, allegati, `DatiAtto.xml`, indice documenti e riferimenti MIME.
5. I documenti richiesti vengono firmati, `DatiAtto.xml` viene firmato CAdES, il messaggio viene cifrato con il certificato dell'ufficio e nasce `Atto.enc`.
6. L'invio PEC usa MailBee dal PC locale configurato, non un canale server remoto.

## Regole che conviene portare in IUSENTRA

- Il selettore deposito non deve essere una lista piatta: deve portare con sé canale, schema, codice oggetto, validazioni e documenti obbligatori.
- Gli introduttivi esecuzioni impostano codici oggetto fissi per pignoramento mobiliare presso debitore, mobiliare presso terzi e immobiliare.
- Cassazione, SIGP e UNEP hanno campi speciali: ruolo difensore, motivi, registro, urgenza, natura atto, date specifiche.
- Gli allegati `EML`, `MSG`, `P7M` e `XML` hanno comportamento firma diverso dai PDF/documenti ordinari.
- I depositi complementari vengono raggruppati e marcati con soggetto PEC dedicato.

## Riferimenti soggetto PEC/ricevute

- ` AND (UCASE(Subject) NOT LIKE '%ACCETTAZIONE: DEPOSITO%') `
- ` AND (UCASE(Subject) NOT LIKE '%CONSEGNA: DEPOSITO%') `
- `) AND (Deleted = False) AND (Subject LIKE '%DEPOSITO TELEMATICO%') `
- `) AND (Deleted = False) AND (Subject LIKE '%NOTIFICAZIONE AI SENSI DELLA LEGGE N. 53%')`
- `184 - CONSEGNA BENE MOBILE`
- `185 - CONSEGNA DI IMMOBILE`
- `190 - CONSEGNA MINORI`
- `194 - RILASCIO E CONSEGNA BENE MOBILE`
- `ACCETTAZIONE `
- `ACCETTAZIONE DEPOSITO TELEMATICO`
- `ACCETTAZIONE:`
- `ACCETTAZIONE: `
- `ACCETTAZIONE: DEPOSITO TELEMATICO COMPLEMENTARE `
- `ACCETTAZIONE: DEPOSITO TELEMATICO: `
- `ACCETTAZIONE: Re: POSTA CERTIFICATA: `
- `ATTENZIONE: TRATTASI DI NOTIFICAZIONE ESEGUITA EX ART. 3-BIS LEGGE n. 53/1994 E SUCC. MOD. SI INVITA IL DESTINATARIO A PRENDERE VISIONE DEGLI ALLEGATI CHE COSTITUISCONO GLI ATTI NOTIFICATI. `
- `ATTENZIONE: TRATTASI DI NOTIFICAZIONE ESEGUITA EX ART. 3-BIS LEGGE n. 53/1994 NONCHE' EX ART. 16-BIS, COMMA 3, D.L. 546/1992 E SUCC. MOD. SI INVITA IL DESTINATARIO A PRENDERE VISIONE DEGLI ALLEGATI CHE COSTITUISCONO GLI ATTI NOTIFICATI. `
- `AVVISO DI MANCATA CONSEGNA:`
- `COMUNICAZIONE DI AVVENUTA ACCETTAZIONE DEPOSITO COMPLEMENTARE `
- `COMUNICAZIONE DI AVVENUTA ACCETTAZIONE: `
- `CONSEGNA:`
- `CONSEGNA: `
- `CONSEGNA: DEPOSITO TELEMATICO COMPLEMENTARE `
- `CONSEGNA: DEPOSITO TELEMATICO: `
- `CONSEGNA: Re: POSTA CERTIFICATA: `
- `COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO COMPLEMENTARE N° `
- `COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO PRINCIPALE: `
- `COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO: `
- `DEPOSITO TELEMATICO`
- `DEPOSITO TELEMATICO COMPLEMENTARE`
- `DEPOSITO TELEMATICO COMPLEMENTARE N° `
- `DEPOSITO TELEMATICO PRINCIPALE: `
- `DEPOSITO TELEMATICO: `
- `NOTIFICAZIONE`
- `POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO`
- `POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO COMPLEMENTARE `
- `POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO: `
- `POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO COMPLEMENTARE `
- `POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO: `
- `RICEVUTA DI ACCETTAZIONE DEPOSITO COMPLEMENTARE `
- `RICEVUTA DI ACCETTAZIONE: `
- `RICEVUTA DI CONSEGNA DEPOSITO COMPLEMENTARE `
- `RICEVUTA DI CONSEGNA: `
- `SELECT COUNT(*) FROM EMAILS WHERE Subject LIKE '%DEPOSITO TELEMATICO%' `
- `Subject LIKE 'DEPOSITO TELEMATICO: %'`
- `Subject LIKE 'POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO: %'`

## Differenze note rispetto a IUSENTRA

- QuickOrganizer cataloga 779 codici oggetto foglia; IUSENTRA ne ha 1018 da catalogo PST/XSD.
- Codici QuickOrganizer non presenti in IUSENTRA: 461401, 461402, 461403, 481321, 481322, 481323.
- IUSENTRA deve mantenere la propria fonte ufficiale XSD più ampia e usare QuickOrganizer come confronto comportamentale, non come fonte normativa unica.
