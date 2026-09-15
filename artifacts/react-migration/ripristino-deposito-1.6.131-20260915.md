# Ripristino deposito accettato — 15/09/2026

## Richiesta successiva: finestra Bit4id — app 2.319.3 / Signer 1.6.132

La schermata fornita dall’utente mostra `bit4id_universal_mw_notification_window` e una scheda `/diagnosi`. Causa riscontrata nel sorgente accettato: il classificatore delle finestre attribuisce un punteggio al nome Bit4id; il richiamo esegue `ShowWindow` anche sulla finestra tecnica nascosta. La correzione esclude esattamente quel titolo/classe, anche in presenza di testo figlio. Non chiude processi, non intercetta input e conserva il riconoscimento del dialogo PIN effettivo. L’avvio Windows apre la diagnostica solo con `--diagnosi`; avvio automatico e protocollo restano in background.

Nuovi pacchetti 1.6.132 generati per Windows/macOS/Linux; eseguibile accettato 1.6.131 preservato con SHA-256 originale. Installazione atomica sul PC corrente eseguita e `/ping?light=1` risponde 1.6.132. Nessuna variazione ai 17 file v21, alla firma multipla, ai byte firmati o alla PEC. Nessuna migrazione SQL necessaria: modelli dati e API invariati.

Il test controllato del richiamo verifica che la finestra tecnica nascosta non riceva `ShowWindow`/focus e che la finestra PIN reale sia ancora mostrata. Non è un collaudo fisico del middleware del cliente. Il dispositivo non è presente sul PC corrente e la pagina locale richiede accesso: **correzione finestra durante il PIN e firma multipla non verificate su macchina reale**. Servono token del cliente, accesso a `127.0.0.1:8080`, firma di più documenti, PIN digitato direttamente dall’avvocato e verifica di ogni esito, senza invio PEC.

Verifiche del recupero eseguite per gruppi: Signer 266, deposito 31, busta 42, catalogo 19 (audit generale 254 secondi), anagrafica ministeriale 20, PolisWeb 109, PKCS#11 11. Il test PolisWeb inizialmente fallito richiedeva pdf-inspector già dichiarato nelle requirements: installazione locale della 1.17.0 e rilancio positivo. CI del primo commit `2e1ea5912f` fermata dal guardrail React obsoleto; aggiornato alla selezione esplicita e rieseguito (26 superati). Log nella cartella del ripristino; CI e deploy del nuovo commit da verificare prima del rapporto finale.

## Richiesta e perimetro

Ripristino esplicitamente richiesto dall'utente del codice deposito/firma/PEC accettato il 09/09/2026 con Local Signer **1.6.131**, mantenendo il successivo aggiornamento delle tabelle Cassazione **v21** e gli aggiornamenti del repository fino a `3bc52bc1a5683bd27a6ef30a7200df24028bb801`. Versione applicazione: **2.319.2**.

La fonte è il backup immutabile `deposito-accettato-20260909_195010`, documentato in [baseline accettata](deposito-firma-pec-baseline-20260909.md). Il ripristino riguarda i sorgenti e i pacchetti; non ripristina database, documenti o dati storici dello studio. Copia preventiva delle parti sostituite e log conservati in `D:/legale/backups/IUSENTRA/ripristino-deposito-20260915`.

## Integrità del recupero

SHA-256 verificati contro `SHA256SUMS` del backup:

| Artefatto | SHA-256 |
| --- | --- |
| sources.tar.zst | fbfc7e80ceb49077d7ed39771a3824d5f081e902fdf398585dee078e7ead119e |
| source-manifest.json | f89cb72d8dd9d24a3cbb7fefbcdafc7f7ebc9747226cc268873503e3c658ef3b |
| SetupLocalSigner-1.6.131.exe | b80e46de0e29a030e6ba779a4516097ef3bbcd449fd63af3a9e6b56163df4eb7 |

I sorgenti recuperati sono stati confrontati con le singole impronte del manifest. La pagina React e i test condivisi sono stati integrati a tre vie rispetto all'antenato `bc4106eb4df24b878ef24cd98c4d4d00eac9d1f7`, preservando le modifiche successive. Non è stato eseguito un rollback globale. I 17 file di catalogo, schemi e integrazione v21 hanno impronta identica a quella precedente al ripristino.

## Comportamenti recuperati

- Pacchetti Windows, macOS e Linux 1.6.131, compreso l'eseguibile Windows accettato e l'alias pubblico.
- Rilevamento e verifica delle firme esistenti; firma aggiuntiva soltanto su scelta esplicita dell'avvocato; conservazione delle firme precedenti.
- Firma multipla con la sessione del dispositivo riutilizzata e salvataggio verificato degli esiti nel fascicolo.
- Campi PAdES univoci, verifica crittografica del contenuto e conservazione incrementale del PDF già firmato.
- Verifica PDF per deposito senza trasformazione dei documenti firmati; classificazione e selezione preservate.
- PEC esclusivamente dal PC: AUTH UTF-8 e Message-ID IDNA del bridge accettato.
- Cassazione v21 attiva; gli otto atti aggiuntivi predisposti rimangono disabilitati come già deciso dallo studio. Catalogo operativo: 270 tipi.

Un'unica correzione tecnica oltre al recupero: il backend PKCS#11 registra l'OID ESSCertIDv2 come già fa il Local Signer accettato. Il test isolato ha rilevato che una precedente operazione CAdES può inizializzare la cache ASN.1 prima dell'import degli attributi PAdES. La registrazione evita l'errore `signing_certificate_v2` senza cambiare il profilo di firma, il documento o la gestione del PIN. Il test riproduce esplicitamente quella cache e verifica la firma prodotta.

## Verifiche e limite dell'accettazione

- Verificati runtime locale e server: Cassazione `v21`, schema `parte_v21/Parte-cassazione.xsd`.
- Sul PC il servizio locale risponde già come Local Signer 1.6.131: non è stata eseguita una reinstallazione.
- Nel browser Chrome reale su `127.0.0.1:8080`, aperte Impostazioni/Firma e la preparazione del deposito: pacchetto disponibile 1.6.131, controllo dispositivo, catalogo dei 270 tipi, selezione documenti e navigazione delle fasi.
- Il controllo dispositivo segnala assenza del token PKCS#11. **Firma multipla con PIN e salvataggio di più documenti non verificata su macchina reale in questa sessione**. Non è stato effettuato alcun invio PEC.
- Build frontend finale e typecheck positivi; compilazione Vite 2,04 secondi. Contratti React, confini Local Signer e sincronizzazione packaging verificati.
- Test mirati e stato operativo sono registrati nei report `pytest-confirmed-ok.md` e `pytest-open-issues.md`. L'accettazione funzionale resta aperta fino alla nuova prova materiale con token, pur procedendo al commit e deploy esplicitamente richiesti.

Verifica finale correzione 1.6.132: intero `test_local_signer.py` 269 superati; installer atomico, build pacchetti, guardrail React e versione impostazioni 44 superati. Confini Local Signer, packaging e Ruff positivi; typecheck/build frontend 2,04 secondi.
