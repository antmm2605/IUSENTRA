# Portale Cliente — Workflow firma documenti (firma elettronica con evidence pack)

Aggiornato: 2026-07-10. Questo documento descrive il modello di firma del
Portale Cliente e i suoi limiti, in modo che non venga mai presentato come
qualcosa che non è.

## Cos'è (e cosa NON è) la firma del portale

- La firma applicata internamente dal Portale Cliente è una **firma elettronica
  semplice con pacchetto di evidenze** (CAD D.Lgs. 82/2005, artt. 20-21: valore
  probatorio liberamente valutabile dal giudice, rafforzato dalle evidenze).
- **Non è una firma elettronica qualificata** ai sensi del Regolamento eIDAS
  910/2014. La firma qualificata richiede un prestatore di servizi fiduciari
  qualificato esterno e **non è attiva**: il provider `qualified_stub` non è
  operativo e non dichiara MAI una firma qualificata completata. L'API pubblica
  espone `qualifiedSignature.available: false` con nota esplicita.
- Resta sempre disponibile il **fallback**: scarico del documento, firma
  manuale fuori dal portale e ricarico del documento firmato (che entra "in
  revisione" presso lo studio).

## Feature flag

Il flusso storico di firma semplice resta governato da
`routes.appV2.clientPortal.signatures`.

Il **workflow professionale completo** (preventivo → conferimento → documento
d'identità → firma su PDF → ricevuta) è governato dal flag dedicato
**`routes.appV2.clientPortal.signingWorkflow`**, **default-off e fail-closed**:
con il flag disattivato tutti gli endpoint `/public/signing/*` e
`/studio/documents/<id>/review` rispondono `feature_disabled` (403). Nessuna
migrazione distruttiva: attivazione/disattivazione senza toccare i dati.

## Workflow del cliente (flag `signingWorkflow` attivo)

1. **Invito**: lo studio genera l'invito (token opaco firmato, salvato solo
   come hash, con scadenza e revoca); può referenziare un `preventivoId` che
   viene evidenziato al cliente. URL: `/portale-cliente/invito/<token>`.
2. **Preventivo** (`GET /public/signing/overview`): il cliente vede i propri
   preventivi (stati INVIATO/APERTO/ACCETTATO/CONVERTITO), scarica il PDF
   **materializzato una sola volta** (hash SHA-256 stabile), conferma la presa
   visione e accetta o rifiuta con motivo. L'accettazione registra sul dominio
   `StatoPreventivo.ACCETTATO` (via `PORTALE_CLIENTE_APP`, canale ONLINE) e
   crea automaticamente il conferimento.
3. **Documento d'identità**: acquisizione da file, fotocamera del cellulare
   (`capture="environment"`) o webcam (`getUserMedia` avviata SOLO dopo click
   esplicito, mai all'apertura pagina), con anteprima e sostituzione prima
   dell'invio. Richiede il consenso `acquisizione_documento_identita`
   registrato PRIMA dell'upload. Dopo l'invio il documento è "in revisione":
   lo studio approva o respinge con nota.
4. **Conferimento incarico**: disponibile SOLO dopo accettazione preventivo e
   anagrafica minima completa (nome, email, codice fiscale). Consenso di
   accettazione **separato** da quello del preventivo.
5. **Firma**: quattro dichiarazioni obbligatorie (testi versionati lato server,
   versione `2026-07`, validati contro le costanti — mai contro testo del
   client), firma disegnata su canvas / nome digitato / immagine JPEG caricata,
   posizione del riquadro a scelta. Il PDF firmato è una **nuova versione**
   immutabile (`firmato_definitivo`); l'originale non viene mai mutato.
6. **Ricevuta** (`GET /public/signing/receipt`): riepilogo non sensibile con
   impronte abbreviate; nessuna evidenza interna.

### OTP step-up (opzionale per studio)

Con il setting `signatures.otpStepUp` attivo, prima della firma il cliente
verifica la propria identità con un codice a 6 cifre inviato via email
(`POST /public/signing/otp/start` / `verify`). Il codice è salvato **solo come
hash con pepper**, TTL 10 minuti, massimo 5 tentativi poi lockout,
**fail-closed**: se l'email non parte la firma resta bloccata con messaggio
controllato. L'esito entra nell'evidence, mai il codice.

## Provider di firma (adapter)

`web/services/client_signature_providers.py` espone un'interfaccia comune
`SignatureProvider` con tre implementazioni intercambiabili:

| Provider | `name` | Tipo | Operativo | Note |
|---|---|---|---|---|
| `InternalGraphicSignatureProvider` | `internal_graphic` | firma grafica/elettronica | sì | timbro visibile sul PDF (nuova versione) con coordinate reali e tratto firma JPEG + evidence pack |
| `ManualUploadSignatureProvider` | `manual_upload` | upload manuale | sì | fallback: il cliente ricarica il documento firmato a mano (→ revisione studio) |
| `QualifiedSignatureProviderStub` | `qualified_stub` | qualificata remota | **no** | segnaposto non operativo; non dichiara MAI una firma qualificata completata |

Metodi dell'interfaccia: `create_signature_request`, `get_signature_status`,
`download_signed_document`, `cancel_signature_request`. Una futura integrazione
con un provider qualificato esterno si aggiunge implementando l'interfaccia,
senza toccare il flusso del portale.

### Immagine firma: solo JPEG

ReportLab senza Pillow decodifica nativamente solo JPEG: il tratto firma
(canvas o upload) viaggia come **data URL JPEG ≤ 300 KB** (magic bytes
verificati lato server). Un'immagine non valida degrada al timbro solo testo,
tracciato in evidence come `stampFallback: "testo"` — mai un errore.

## Evidence pack (probatorio, lato studio)

`build_signature_evidence_pack(...)` produce il pacchetto di evidenze salvato
con la richiesta firma. Contiene:

- id firma, tipo firma, provider;
- tenant / cliente / pratica / documento risolti **lato server**;
- testo del consenso mostrato + versione (`2026-07`), dichiarazione;
- hash SHA-256 del documento originale e del documento firmato;
- coordinate firma e hash SHA-256 dell'immagine firma (mai l'immagine);
- **hash dell'IP** (mai l'IP in chiaro), user agent, **riferimento hash del token** (mai il token in chiaro);
- timestamp server; id documento firmato; esito OTP quando previsto;
- esito marca temporale RFC 3161 (`tsaStatus`, best-effort: la TSA esterna
  irraggiungibile non blocca mai la firma);
- riferimento all'evento WORM (`wormAuditRef`) quando il modulo `audit/` è
  configurato: l'evento `CLIENT_SIGNATURE_ACQUIRED` porta nella catena
  hash/WORM solo gli hash, mai tratto firma, IP o token;
- `payloadSha256`: checksum dell'intero pacchetto per rilevare manomissioni.

Privacy by design:

- l'evidence pack **non viene mai restituito al cliente**: `_public_row` lo
  rimuove dai payload pubblici del portale (resta visibile solo lato studio per
  l'audit);
- nei log non finiscono né contenuti documentali né firme né IP/token in chiaro;
- il timbro visibile produce sempre una **nuova versione** del PDF: i byte
  originali non vengono mai mutati e la versione firmata (`firmato_definitivo`)
  non è più modificabile né sostituibile;
- su PDF cifrato o corrotto la firma **fallisce in modo sicuro**
  (`SignatureProviderError`), senza stack trace verso il client.

## Coerenza degli stati sulla superficie pubblica

Gli endpoint pubblici del portale (`/api/v1/ui/client-portal/public/*`) sono
autenticati tramite **token opaco** (salvato solo come hash, con scadenza e
revoca), non con le credenziali dello studio. Un accesso senza sessione cliente
valida riceve `401 unauthorized`; token non valido/scaduto/revocato riceve
`404 invalid_invite` con messaggio opaco; un utente studio autenticato ma privo
del permesso riceve `403 forbidden`. In nessun caso vengono rivelati tenant,
cliente o pratica. Nessun endpoint pubblico accetta `tenant_id`, `studio_id`,
path o ruoli (guardia backend-security, 400 in caso contrario).

## Limiti residui

- Il workflow vive dentro gli inviti del Portale Cliente (cliente + fascicolo
  esistente): il prospect senza fascicolo resta servito dal portale legacy
  `/portale/<token>` (accettazione preventivo + firma conferimento + apertura
  fascicolo automatica), che è invariato.
- La firma qualificata remota richiede l'integrazione di un provider esterno
  qualificato (lo stub non è operativo).
- L'acquisizione da scanner fisico non è integrata: il Local Signer non espone
  oggi un canale scanner; restano upload, fotocamera e webcam.
- La primitiva magic-link + OTP di `pct/client_portal_access.py` è riusata per
  l'hashing del codice OTP; il magic-link monouso completo resta una
  predisposizione non ancora cablata all'accesso del portale.
