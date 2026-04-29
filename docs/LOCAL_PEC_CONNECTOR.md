# Ponte PEC locale con Local Signer

Da IUSENTRA 2.195.24 il Local Signer include anche un ponte PEC locale.

## Perche esiste

Alcuni provider PEC, in particolare in ambienti server cloud o dedicati, possono non accettare connessioni SMTP dall'IP del server. In questi casi la ricezione IMAP puo funzionare, mentre l'invio SMTP resta in timeout anche con host, porta e credenziali corretti.

Il ponte locale permette al browser di parlare con `http://127.0.0.1:27272` sul PC dello studio. L'invio SMTP parte quindi dal computer locale, con la stessa rete da cui la PEC funziona gia.

## Flusso operativo

1. L'utente apre `Impostazioni -> PEC`.
2. Clicca `Testa SMTP dal PC`.
3. IUSENTRA verifica se Local Signer risponde su `127.0.0.1:27272`.
4. Se non risponde, prova ad avviarlo con il protocollo `hacs-local-signer://restart`.
5. Se resta non disponibile, mostra il pacchetto Local Signer da scaricare per Windows, macOS o Linux. Su Windows il pacchetto proposto e' sempre l'eseguibile `SetupLocalSigner-<versione>.exe`.
6. La password inserita nel campo PEC viene usata solo per la chiamata locale e non viene salvata dal server se l'utente non salva il form.

## Endpoint Local Signer

- `POST /pec/smtp/test`: verifica connessione e login SMTP PEC dal PC locale.
- `POST /pec/send`: invia una PEC dal PC locale con destinatari, oggetto, corpo e allegati in base64.

Il Local Signer continua ad ascoltare solo su loopback e accetta CORS dalle origini fidate IUSENTRA, incluso `https://app.iusentra.it`.

## Limiti

Il ponte locale non sostituisce la configurazione PEC dello studio: usa gli stessi parametri host, porta, SSL/TLS e indirizzo. Se il provider blocca anche la rete locale o le credenziali non sono valide, il test resta negativo e mostra un messaggio operativo.
