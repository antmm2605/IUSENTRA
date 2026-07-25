# Matrice casi notifica Montagnese - 24/07/2026

Obiettivo: confrontare il generatore notifiche IUSENTRA con il decompilato Studio Telematico, con il database reale dello Studio Legale Giuseppe Montagnese e con le fonti normative/tecniche, evitando decisioni basate sul solo nome file.

## Fonti incrociate

- Decompilato locale: `%TEMP%\quickorganizer_decompiled_full\FormSentMailBee.cs` e componenti collegati `QuickOrganizer\PCT.cs`, `WizardImportaPraticheDaPolisWeb.cs`, `SchedaAnagrafica.cs`.
- Esempi DOCX utente letti dal contenuto OOXML: `Attestazione di conformità decreto fissazione .docx`, `modello da seguire realata.docx`, più gli esempi sentenza presenti nella stessa area.
- Tenant locale registrato: `studio-montagnese` -> storage key `tenant-8bf98719c459`, `data\tenants\tenant-8bf98719c459\studio.db`.
- Tenant produzione corretto: `/opt/iusentra/data/tenants/studio-legale-giuseppe-montagnese/studio.db` e `/opt/iusentra/data/tenants/studio-legale-giuseppe-montagnese/email/pec_audit.sqlite`.
- Fonti: L. 53/1994 art. 3-bis, DM 48/2013 art. 18/DM 44/2011, specifiche tecniche PST ex art. 34 DM 44/2011 del 7 agosto 2024, artt. 196-octies/196-undecies disp. att. c.p.c. per le attestazioni.

## Verifica database

Il dubbio dell'utente sul DB locale era fondato.

- Locale `tenant-8bf98719c459`: `studio.db` circa 150 MB, `10` fascicoli; `pec_audit.sqlite` circa 1,2 GB, `326` messaggi PEC e `1.174` allegati.
- Produzione corretta Montagnese: `studio.db` circa 785 MB, `334` fascicoli; `pec_audit.sqlite` circa 2,4 GB, `1.377` messaggi PEC e `4.690` allegati.
- Produzione Montagnese notifiche/presidi: `33` presidi, `33` destinatari, `36` documenti, `8` evidenze, `52` transizioni; DB notifiche con `624` record.
- Fascicoli JSON produzione: `334` fascicoli, `11.645` record documento; `5.033` record collegati a notifica/conformità/relata/ricevute; `1.948` documenti con suffisso `(originale notificato)`.
- Oggetti PEC reali: `66` gruppi con `[Notifica_ID:...]`. Le accettazioni contengono normalmente `daticert.xml`/`smime.p7s`; le consegne contengono anche atti, attestazione e `Relata di notifica.pdf`.

Esempi reali:

- `JQ278-L01`, `Notifica_ID:sywMJ9dq`: `Sentenza.PDF`, `Attestazione di conformità sentenza.pdf`, `Relata di notifica.pdf`, una accettazione e quattro consegne.
- `JQ331-L01`, `Notifica_ID:l1rBFo62`: `Ricorso Merdini.PDF`, `Procura.PDF`, `Decreto fissazione udienza.PDF`, `Attestazione di conformità.pdf`, `Relata di notifica.pdf`.
- `JQ203-L01`, `Notifica_ID:go2KugWr`: sentenza, attestazione sentenza, relata e quattro consegne.
- `JQ329-L01`, `Notifica_ID:Cc25btuS`: precetto, sentenza, relata; non sempre è presente un PDF autonomo di attestazione quando la natura dei documenti non lo richiede.

## Comportamento Studio Telematico ricostruito

Studio Telematico non decide il valore giuridico dal nome file. Fa scegliere o memorizza la natura del documento:

| Tipo decompilato | Significato operativo | Testo attestazione decompilato |
| --- | --- | --- |
| `OriginalePredispostoAvvocato` | Originale informatico predisposto dall'avvocato | originale informatico predisposto dal sottoscritto |
| `DuplicatoInformatico` | Duplicato informatico ex art. 23-bis CAD | duplicato informatico conforme all'originale |
| `AcquisizioneScanner` | Scansione di originale/copia conforme cartacea | conforme alla copia originale dalla quale è stato estratto mediante scansione |
| `CopiaEstrattaFascicoloInformatico` | Copia estratta dal fascicolo informatico | conforme alla copia digitale presente nel fascicolo informatico di cancelleria |

Altri passaggi confermati:

- blocca la notifica se destinatario, PEC, pubblico elenco o qualifica mancano;
- genera `Relata di notifica.pdf`;
- firma digitalmente la relata prima di allegarla;
- costruisce l'oggetto con `Notificazione ai sensi della legge n. 53/1994 e succ. mod.` e `[Notifica_ID:...]`;
- dopo l'invio marca gli allegati, esclusa la relata, con `(originale notificato)`;
- riconcilia `ACCETTAZIONE:`, `CONSEGNA:` e `AVVISO DI MANCATA CONSEGNA:` cercando lo stesso `Notifica_ID`.

## Matrice documento -> relata/attestazione

La regola IUSENTRA è: prima leggere contenuto e metadati del documento; il nome file è solo recupero se il testo non è disponibile.

| Caso documento letto | Relata suggerita | Attestazione PDF autonoma | Note |
| --- | --- | --- | --- |
| Originale informatico dell'avvocato | base L. 53 / caso processuale collegato | normalmente no | La relata indica natura originale informatico; nessuna scansione. |
| Duplicato informatico | base L. 53 / caso processuale collegato | sì se serve prova separata | Attesta duplicato conforme all'originale. |
| Scansione da cartaceo | base L. 53 / caso processuale collegato | sì | Attesta copia per immagine da originale/copia conforme analogica. |
| Copia estratta dal fascicolo informatico | base L. 53 / caso processuale collegato | sì | È il caso tipico dei PDF Montagnese per provvedimenti e sentenze. |
| Sentenza | `relata_sentenza_attestazione_conformita` | sì, spesso `Attestazione di conformità sentenza.pdf` | Allineato ai casi reali `JQ278-L01` e `JQ203-L01`. |
| Ricorso + procura + decreto fissazione udienza | `relata_decreto_fissazione_udienza` o caso base con decreto | sì, unico PDF per tutti i documenti conformi | Allineato al DOCX utente e a `JQ331-L01`. |
| Decreto ingiuntivo | `relata_decreto_ingiuntivo` | sì se estratto da fascicolo/scansione | Può diventare opposizione se il documento letto contiene opposizione. |
| Opposizione a decreto ingiuntivo | `relata_opposizione_decreto_ingiuntivo` | secondo origine copie | Scelta dal testo "opposizione" + "decreto ingiuntivo". |
| Titolo esecutivo / precetto | `relata_titolo_esecutivo_precetto` | secondo origine copie | Allineato ai casi reali con precetto e titolo. |
| Pignoramento presso terzi | `relata_pignoramento_presso_terzi` | secondo origine copie | Caso già presente nel catalogo modelli. |
| Atto di appello / impugnazione | `relata_appello_impugnazione` | secondo origine copie | Identificato da contenuto, non dal nome. |
| Ricorso in riassunzione | `relata_riassunzione` | secondo origine copie | Caso già presente nel catalogo modelli. |
| Chiamata in causa del terzo | `relata_chiamata_terzo` | secondo origine copie | Caso già presente nel catalogo modelli. |
| Integrazione del contraddittorio | `relata_integrazione_contraddittorio` | secondo origine copie | Caso già presente nel catalogo modelli. |
| Rinnovo notifica | `relata_rinnovo_notifica` | secondo origine copie | Caso operativo distinto dal primo invio. |
| Famiglia, persone, minori | `relata_famiglia_persone_minori` | secondo origine copie | Caso identificato da materia/testo quando disponibile. |
| Provvedimento urgente/cautelare o reclamo cautelare | `relata_provvedimento_urgente` / `relata_reclamo_cautelare` | secondo origine copie | Priorità al reclamo quando il testo contiene reclamo. |
| Accordo transattivo, diffida, messa in mora | `relata_accordo_transazione_stragiudiziale` / stragiudiziale | secondo origine copie | Resta canale L. 53 stragiudiziale, non deposito PCT. |

## Adeguamento IUSENTRA del 24/07/2026

- L'attestazione non viene più prodotta come DOCX finale: l'endpoint React restituisce `Attestazione_di_conformita.pdf`.
- Il piano output mostra materialmente `Relata di notifica.pdf` e, quando dovuta, `Attestazione di conformità.pdf`.
- Il PDF dell'attestazione usa un unico documento per tutti gli allegati che richiedono conformità, come nel modello Montagnese con ricorso, procura e decreto di fissazione udienza.
- La relata continua a contenere il richiamo alle attestazioni/natura documento secondo il comportamento Studio Telematico.
- Il classificatore React/backend è stato esteso sui casi del catalogo modelli, privilegiando contenuto/metadati del documento.
- Il download frontend accetta `application/pdf` e mostra `Scarica PDF`.
- Correzione successiva su segnalazione utente: l'elenco `I seguenti atti` include tutti i documenti scelti o aggiunti manualmente, poi `Attestazione di conformità` quando dovuta, poi `Relata di notifica`; la chiusura della relata non ripete più la riga `Firmato digitalmente` dopo `F.to digitalmente da` e nome avvocato.

## Limiti e blocchi corretti

- Nessuna PEC reale è stata inviata in questa fase.
- La firma digitale effettiva della relata richiede prova materiale con dispositivo/PIN reale: il software deve bloccare l'invio finché la relata non risulta firmata.
- La verifica ReGIndE può partire senza PIN precompilato, come Studio Telematico; il middleware/certificato o il comando firma chiedono il PIN quando serve.
- Registro PP.AA. resta consultazione PST/anagrafica: non è stato introdotto scraping inventato.

## Tre ingressi documenti verificati - 25/07/2026

Il documento da notificare può arrivare in tre modi, tutti distinti nella UI e nel payload:

| Ingresso | Regola | Esito atteso in relata |
| --- | --- | --- |
| Fascicolo con selezione | URL con `documenti=<id>` senza `ingresso=presidio` | i documenti selezionati sono già inclusi |
| Presidio notifiche | URL con `documenti=<id>&ingresso=presidio` | il documento del presidio è già incluso e la modalità visibile è `Presidio porta il documento` |
| Manuale | URL senza `documenti` | nessun documento preselezionato; l'avvocato spunta i documenti del fascicolo da importare |

Prova reale locale su Docker `127.0.0.1:8080`, dopo rebuild completo del bundle React:

- `DD242366&documenti=BB94330C`: modalità `Fascicolo documenti selezionati`, documento `Ordinanza_32473463.pdf` già spuntato, elenco finale `A) Ordinanza`, `B) Attestazione di conformità.pdf`, `C) Relata di notifica.pdf`;
- `DD242366&documenti=BB94330C&ingresso=presidio`: modalità `Presidio porta il documento`, lo stesso documento viene portato automaticamente dal presidio notifiche e resta incluso nella relata;
- `DD242366` senza `documenti`: modalità `Manuale vedi e spunta`, 13 documenti del fascicolo visibili e zero selezioni iniziali; dopo click reale sulla spunta di `Ordinanza_32473463.pdf`, il documento entra nell'elenco finale con attestazione unica e relata;
- `Vedi attestazione`: la pagina apre l'anteprima `Attestazione di conformità.pdf` con testo `ATTESTAZIONE DI CONFORMITÀ`;
- `Controlla relata`: simulazione eseguita senza invio PEC; `Invio PEC` resta bloccato finché mancano firma/approvazione finale.

Il fascicolo temporaneo `CODXPRSD` usato nella prova intermedia è stato rimosso da SQLite, mirror JSON, scadenziario, audit tecnico, documenti fisici e OCR/AI; il controllo finale non trova più quel marker nel tenant locale. Nessuna PEC reale è stata inviata, il PIN non è stato usato e il campo PIN visibile nella sessione browser è stato svuotato.
