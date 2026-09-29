# App mobile di IUSENTRA

IUSENTRA è un'applicazione web installabile (PWA): lo stesso codice serve il browser, l'app
installata su telefono, tablet e computer e l'app pubblicata negli store. Non esiste un secondo
codice «nativo» da tenere allineato: ogni rilascio del server aggiorna subito anche le app.

## Cosa c'è già nel server

| Elemento | Dove | A cosa serve |
|---|---|---|
| Manifest | `web/static/manifest.webmanifest` (servito da `/manifest.webmanifest`) | nome, icone (anche *maskable*), colori, scorciatoie Oggi/Scadenziario/Agenda/Fascicoli |
| Service worker | `web/static/sw.js` (servito da `/sw.js`) | notifiche push e pagina «Sei offline»; **non** salva pagine né dati dello studio sul dispositivo |
| Icona iPhone/iPad | `web/static/icons/apple-touch-icon.png` | icona della schermata Home su iOS |
| Digital Asset Links | `/.well-known/assetlinks.json` | associa l'app Android (Trusted Web Activity) al dominio |
| Apple App Site Association | `/.well-known/apple-app-site-association` | associa un'eventuale app iOS al dominio (universal links) |
| Pulsante «Installa IUSENTRA» | Impostazioni → Notifiche → dispositivo | installazione dal browser; istruzioni per iPhone/iPad |

Le due risposte `/.well-known/...` sono vuote finché non si impostano le variabili d'ambiente:

```bash
IUSENTRA_ANDROID_PACKAGE=it.iusentra.app
IUSENTRA_ANDROID_SHA256=AA:BB:...:FF          # impronta SHA-256 del certificato di firma (più valori separati da virgola)
IUSENTRA_IOS_APP_IDS=ABCDE12345.it.iusentra.app   # Team ID Apple + bundle ID (facoltativo)
```

## Android: pubblicazione su Google Play (Trusted Web Activity)

Serve un account sviluppatore Google Play dello studio o della società che pubblica l'app
(registrazione una tantum). I passaggi vanno fatti da chi possiede l'account: IUSENTRA non
conserva chiavi di firma né credenziali degli store.

1. Installare Node.js e Java (JDK 17) sul computer che prepara l'app.
2. Nella cartella `mobile/android-twa/` eseguire `npx @bubblewrap/cli init --manifest https://app.iusentra.it/manifest.webmanifest`
   e confermare i valori già proposti in `twa-manifest.json` (nome, colori, icone, scorciatoie).
3. `npx @bubblewrap/cli build`: crea la chiave di firma (va custodita: senza non si pubblicano
   aggiornamenti) e produce `app-release-bundle.aab`.
4. `keytool -list -v -keystore iusentra-upload.keystore` mostra l'impronta SHA-256: impostarla in
   `IUSENTRA_ANDROID_SHA256` sul server (se si usa la firma dell'app di Google Play, aggiungere
   anche l'impronta mostrata in Play Console → Integrità dell'app) e riavviare.
5. Verificare `https://app.iusentra.it/.well-known/assetlinks.json`, poi caricare l'`.aab` in
   Play Console (scheda dello store, informativa privacy, classificazione dei contenuti).

Gli aggiornamenti di IUSENTRA non richiedono una nuova versione su Play: l'app apre sempre il
server. Una nuova build serve solo se cambiano nome, icone, colori o scorciatoie.

## iPhone e iPad

Su iOS l'app si installa da Safari: Condividi → «Aggiungi alla schermata Home». Dall'icona
IUSENTRA si apre a schermo intero e, da iOS 16.4, riceve le notifiche push.

La pubblicazione sull'App Store richiede un account Apple Developer e un'app che offra funzioni
proprie oltre al sito (le linee guida App Store, punto 4.2, respingono le app che sono solo un
sito incorniciato). Se lo studio vuole comunque l'App Store, la strada è un contenitore (es.
Capacitor) con funzioni native dichiarate, e `IUSENTRA_IOS_APP_IDS` per i collegamenti.

## Sicurezza

- Nessun dato dello studio resta nella cache del dispositivo: il service worker conserva solo la
  pagina offline e le icone.
- La sessione, la doppia autenticazione e i permessi sono quelli del browser: l'app non ha
  credenziali proprie.
- Le chiavi di firma degli store restano a chi pubblica l'app; il server conosce solo le impronte
  pubbliche.
