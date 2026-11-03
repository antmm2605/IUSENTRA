# IUSENTRA 2.479.0 — notifiche dai precedenti dello studio, collaudo dei motori, dipendenze sicure (03/11/2026)

## Notifiche legali
- Istituti scolastici statali e MIM trattati come amministrazioni dello Stato: notifica presso l'Avvocatura distrettuale
  (art. 11 R.D. 1611/1933; art. 144 e 415 c.p.c.; art. 1 c. 2 D.Lgs. 165/2001; art. 417-bis c.p.c. non cambia il
  destinatario). Nota: la copia a Ministero/USR è prassi dello studio, non obbligo di legge. Fonti consultate su
  Normattiva il 03/11/2026 in `docs/specs/ministero/fonti_ufficiali/2026-11-03/notifiche_amministrazioni_statali/`.
- Precedenti dello studio: destinatario e domicilio proposti in automatico con almeno 3 notifiche precedenti concordi e
  consegnate; la norma prevale sempre; indirizzo PEC dal pubblico elenco attuale; firma e invio restano all'avvocato
  (art. 3-bis L. 53/1994).
- Notifiche L. 53/1994 già inviate collegate con certezza al fascicolo (.eml nel fascicolo, codice della notifica, stesso
  invio, relata con i tre controlli); atto, relata, .eml e ricevute portati nel fascicolo senza doppioni; destinatario
  riletto dal daticert.
- «Copia originale da scaricare dal PST» per i provvedimenti notificati: estremi compilati, collegamento al portale,
  download con l'accesso dell'avvocato (CNS/CIE/SPID).
- Le ricevute di PEC qualsiasi non valgono più come prova della notifica dell'atto.

## Motori (collaudo del 03/11/2026, registro in `docs/verifica_visiva_2026-11-02/COLLAUDO_MOTORI.md`)
- OCR: il testo letto da documenti cifrati arriva all'archivio (prima l'impronta non coincideva mai).
- Presidio notifiche fermo quando nulla cambia; caselle PEC mai esaminate riconciliate.
- Documenti caricati o modificati dall'avvocato e PEC appena collegate con precedenza nella coda delle letture, senza
  fermare il resto (colonna `priorita`, schemi SQLite e PostgreSQL allineati).
- Sintesi delle letture: «N letture in attesa in K motori» invece di «tutto letto» con letture ancora da fare.

## Interfaccia
- Pulsanti principali in Panoramica, Fascicoli e nelle altre intestazioni di pagina di nuovo leggibili (testo chiaro su
  fondo scuro).

## Sicurezza delle dipendenze
- Aggiornate zod 4.6.7, ip-address 10.7.5, body-parser 2.4.0, fast-uri 3.1.9, undici 7.30.1, qs 6.17.1,
  @hono/node-server 2.1.6, systeminformation 5.33.19, glob 14.0.3, minimatch 11.0.4, pypdf 6.21.2 (Local Signer
  rigenerato). deepmerge resta alla 4.3.1: la versione correttiva non è stata pubblicata.
