# Ponte PEC locale con Local Signer

Da IUSENTRA 2.195.24 il Local Signer include anche un ponte PEC locale.

## Sincronizzazione dashboard

Da IUSENTRA 2.198.68 la Panoramica React avvia una sincronizzazione non bloccante di PEC ed email ordinaria dopo il primo render, tramite `POST /api/v1/ui/dashboard/sync-mailboxes`.

Il servizio backend `web.services.mailbox_sync_runtime`:

- riusa la stessa logica delle route manuali `/email/sincronizza` e `/email-ordinaria/sincronizza`;
- mantiene separati i database `EMAIL_CASELLA_DB` e `EMAIL_ORDINARIA_DB`;
- applica lock per evitare sync concorrenti sulla stessa casella/tenant;
- applica cooldown di default pari a 180 secondi, bypassabile solo con `force=true` sui percorsi esplicitamente autorizzati;
- svuota la cache della dashboard dopo il tentativo di sync, cosi' un refresh esplicito legge i dati aggiornati.

La Panoramica non esegue mai IMAP nel builder sincrono del payload: si apre con dati locali/cache e aggiorna le card comunicazioni quando il job termina.

## Deduplica allegati email

Gli allegati PEC/email sono conservati sotto il data root tenant-aware (`email/allegati` o `tenants/<tenant>/email/allegati`). Il salvataggio e' content-aware: se un messaggio viene riprocessato e un allegato con stesso nome e stesso SHA-256 esiste gia', IUSENTRA riusa il file esistente invece di creare copie numerate.

Per bonificare duplicati storici si usa:

```bash
python scripts/deduplicate_email_attachments.py --data-root /data
python scripts/deduplicate_email_attachments.py --data-root /data --apply
```

Il primo comando e' un dry-run. Il secondo applica hardlink sullo stesso filesystem, mantenendo invariati i path gia' salvati nei JSON e producendo un report in `email/dedup_reports/`. Non cancella allegati reali e non introduce uno storage condiviso tra tenant.

## Perche esiste

Alcuni provider PEC, in particolare in ambienti server cloud o dedicati, possono non accettare connessioni SMTP dall'IP del server. In questi casi la ricezione IMAP puo funzionare, mentre l'invio SMTP resta in timeout anche con host, porta e credenziali corretti.

Il ponte locale permette al browser di parlare con `http://127.0.0.1:27272` sul PC dello studio. L'invio SMTP parte quindi dal computer locale, con la stessa rete da cui la PEC funziona gia.

## Flusso operativo

1. L'utente apre `Impostazioni -> PEC`.
2. Clicca `Testa SMTP dal PC`.
3. IUSENTRA verifica se Local Signer risponde su `127.0.0.1:27272`.
4. Se non risponde, prova ad avviarlo con il protocollo `iusentra-local-signer://restart`.
5. Se resta non disponibile, mostra il pacchetto Local Signer da scaricare per Windows, macOS o Linux. Su Windows il pacchetto proposto e' sempre l'eseguibile `SetupLocalSigner-<versione>.exe`.
6. La password inserita nel campo PEC viene usata solo per la chiamata locale e non viene salvata dal server se l'utente non salva il form.

## Componi PEC

Da IUSENTRA 2.248.51 la pagina React `Componi PEC` non registra più un messaggio come inviato sulla sola risposta del server applicativo. Il browser prepara il payload con configurazione PEC tenant-aware, allegati in base64 e password salvata dello studio, invia a `http://127.0.0.1:27272/pec/send` dal PC locale e chiama `/email/scrivi/conferma-locale` solo dopo una risposta positiva con `Message-ID`.

Se il Local Signer non risponde, se il provider rifiuta SMTP o se manca il `Message-ID`, l'utente vede errore e la cartella `INVIATI` non viene popolata artificialmente. La route server `/email/scrivi` resta un fallback esplicito e non dichiara successo quando lo storico messaggi contiene `FALLITO`.

## Endpoint Local Signer

- `POST /pec/smtp/test`: verifica connessione e login SMTP PEC dal PC locale.
- `POST /pec/send`: invia una PEC dal PC locale con destinatari, oggetto, corpo e allegati in base64.

Il Local Signer continua ad ascoltare solo su loopback e accetta CORS dalle origini fidate IUSENTRA, incluso `https://app.iusentra.it`.

## Limiti

Il ponte locale non sostituisce la configurazione PEC dello studio: usa gli stessi parametri host, porta, SSL/TLS e indirizzo. Se il provider blocca anche la rete locale o le credenziali non sono valide, il test resta negativo e mostra un messaggio operativo.
