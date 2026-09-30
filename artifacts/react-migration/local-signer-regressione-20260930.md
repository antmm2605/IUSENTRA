# Firma multipla e installer — 30/09/2026

## Perimetro e autorizzazione

Correzioni richieste dall’utente a deposito, firma multipla, notifiche, finestra PIN e installer. Deroga esplicita al congelamento del 09/09/2026 limitata a queste regressioni. Nessuna firma su documenti dello studio e nessun invio PEC reale. Dopo i controlli iniziali l’utente ha chiesto di continuare senza ulteriori simulazioni; dispositivo non disponibile.

## Confronto con i backup

Consultati il baseline accettato `deposito-firma-pec-baseline-20260909.md`, il backup `D:/legale/backups/IUSENTRA/deposito-accettato-20260909_195010` e il successivo ripristino `ripristino-deposito-20260922`.

Nel backup del 22 settembre la firma Windows usa `windows_signing_session.sign_raw`, conserva la sessione della chiave e attiva il monitor della finestra PIN per 240 secondi. In 1.6.137 questo percorso era tornato al processo PowerShell separato. Ripristinata la funzione del backup del 22 settembre; il modulo persistente non richiede modifiche.

`visible_signature.py` non è modificato: preservati rilevamento dello spazio occupato, laterale destro, laterale sinistro e fondo pagina. Preservate le firme esistenti e la scelta esplicita della cofirma. Nessuna modifica a classificazione, busta ministeriale, trasporto, SMTP o dati persistenti; non servono migrazioni SQLite/PostgreSQL.

## Correzioni

- Attesa firma multipla adeguata al lotto, almeno cinque minuti e 240 secondi per documento più un minuto di margine. Alla scadenza la UI segnala che l’operazione sul dispositivo potrebbe essere ancora attiva, evitando un invito indiscriminato a rifirmare.
- Local Signer 1.6.138 con sessione Windows persistente e monitor PIN ripristinati.
- Luogo inizialmente vuoto e data/ora disattivate; nessun recupero automatico da impostazioni dello studio o preferenze precedenti. La scelta esplicita è rispettata anche nel timbro incrementale PAdES su PDF già firmati e nelle notifiche legali.
- Scadenza del certificato mostrata in formato italiano.
- Installer Windows, Linux e macOS 1.6.138, con `dispositivi_firma.py` incluso. L’endpoint Windows non restituisce silenziosamente l’alias precedente se manca il pacchetto della versione corrente.

## Evidenze disponibili

Prima della richiesta di non eseguire altre simulazioni: 118 test mirati superati su firma, posizionamento, deposito simulato, installer e contratti React. Prove PAdES su certificati di test: firma precedente conservata e verificabile, timbro coerente nelle tre modalità data/ora. Il controllo completo Local Signer ha rilevato un import richiesto dal contratto pubblico: ripristinato e controllo specifico superato. Non è stato dichiarato superato il controllo completo dopo questa correzione.

Typecheck/build React e lint mirato superati. Archivio CAB dell’installer Windows estratto e confrontato: `local_signer.py` coincide byte per byte con il sorgente e il modulo dispositivi è presente. Installer locale eseguito senza firma; `/ping` risponde `ok=true`, `versione=1.6.138`.

Browser reale di produzione: aperto il pannello di cofirma per scelta esplicita; osservati luogo vuoto e “Senza data”. Inserito un luogo e selezionata sola data con tastiera, poi ripristinati i valori vuoti senza avviare la firma. Controllato il fondo del pannello.

Nel caso aperto il pulsante invio segnala “Scegli il tipo di deposito”: tre documenti sono classificati come allegati, nessun atto principale è selezionato. Questo blocco è coerente con i dati e non viene aggirato. Nessuna modifica salvata alle scelte della pratica.

## Accettazione ancora aperta

Firma multipla con dispositivo, PIN in primo piano, esito dei documenti della pratica e abilitazione finale dell’invio: **non verificato su macchina reale**. L’utente non ha il dispositivo e ha chiesto di proseguire senza altre simulazioni. Nessun invio reale è autorizzato in questo collaudo. Installer macOS/Linux generati e verificati nei contenuti, non eseguiti sui rispettivi sistemi.

Le modifiche preesistenti di Controllo Studio rimangono separate da questo intervento e non sono incluse nel rilascio della firma.
