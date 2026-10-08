# Provenienza verificabile delle ricevute SdI via PEC

Consultazione: 08/09/2026. Implementazione separata dai flussi di firma e deposito.

Fonti primarie:
- AgID, [certificati per i gestori PEC](https://www.agid.gov.it/it/piattaforme/posta-elettronica-certificata/certificati-gestori-pec-siti-web), aggiornamento 22/07/2026. La pagina ha risposto 403 al canale di lettura; il repository ufficiale seguente è accessibile.
- [Repository AgID/ca-agid-ca1](https://github.com/AgID/ca-agid-ca1/tree/c46c9f107f49f032363e237d25e25285725ebc02), copia del certificato e impronta SHA-256 conservate in `ministero/fonti_ufficiali/2026-09-08`. L'impronta del file coincide con SHA256SUMS pubblicato. Non è una dichiarazione di verifica della firma PGP separata.
- [CPS AgID CA1 v10.0](https://github.com/AgID/ca-agid-ca1/blob/c46c9f107f49f032363e237d25e25285725ebc02/ICSPC-SIA-SPKI-Manuale%20Operativo%20AgID%20CA%20v10.0_EN_20260716.md), §§1.3.3, 3.2.2.4, 4.10, 7.1: certificati di firma destinati ai gestori PEC, identità organizzazione e indirizzo di firma controllati, informazioni di revoca pubbliche. La versione PDF prevale in caso di difformità.
- [Regole tecniche PEC, DM 2 novembre 2005](https://www.agid.gov.it/sites/default/files/repository_files/leggi_decreti_direttive/pec_regole_tecniche_dm_2-nov-2005.pdf), §§7.3–7.4: busta firmata, messaggio originale e dati di certificazione.
- [Guida Agenzia delle Entrate](https://www1.agenziaentrate.gov.it/web_app_entrate/fatturazione_elettronica.html): canale PEC SdI `sdi01@pec.fatturapa.it`; ricevute consultabili nel monitoraggio del portale Fatture e Corrispettivi.
- [OpenSSL CMS](https://docs.openssl.org/3.0/man1/openssl-cms/): verifica del contenuto firmato e certificati del firmatario, finalità `smimesign`; intestazioni esterne non fanno parte del contenuto firmato.

## Procedura primaria

La pipeline già acquisisce l'EML originale nello storage PEC tenant-aware. Solo l'output della verifica S/MIME viene analizzato per estrarre un unico daticert.xml e il messaggio postacert.eml. La firma deve risalire alla CA PEC AgID fissata nel prodotto e alla radice Actalis presente nel trust store nativo. Finalità S/MIME, validità temporale, restrizioni dei certificati e revoche di gestore e CA vengono controllate prima della promozione. Le CRL provengono esclusivamente dagli URL pubblicati nei certificati governati, hanno firma e periodo di validità controllati; nessun URL di allegato può pilotare una richiesta di rete.

La busta deve essere posta-certificata senza errori; il mittente attestato deve appartenere esattamente al dominio PEC SdI governato e coincidere con l'originale; il destinatario deve includere la casella configurata del tenant. L'hash dell'XML da applicare deve appartenere al messaggio originale coperto dalla stessa firma. La correlazione fiscale usa identificativo SdI o nome esatto del file preparato, mai importo o nome della persona. Nessuna ricevuta attesta un incasso.

Gli URL HTTP delle CRL sono la pubblicazione primaria ufficiale; l'autenticità dipende dalla firma crittografica e dal certificato fissato, non da HTTP. Le varianti HTTPS sono state controllate e hanno certificati hostname non corrispondenti: non viene disattivata la verifica TLS.

## Errori e storico

Rete/CRL scaduta/mancanza del trust store producono errore specifico e ripetizione governata della verifica sull'EML già acquisito, senza reimportare o inviare. Una busta alterata, un mittente non coerente o un allegato estraneo non possono essere promossi. Certificati storici scaduti richiedono prova archivistica della catena e dello stato alla data di firma: non si retrodata la verifica per trasformare la sola data dichiarata in marca temporale. Resta disponibile registrazione esplicita dell'avvocato con protocollo/documento e audit, distinta da provenienza automatica.

Stato: sorgenti in sviluppo server-first; non verificato su macchina reale. Nessun invio, modifica dati o prova di firma utente eseguiti.
