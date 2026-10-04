# Sito di vendita IUSENTRA

Sito statico commerciale (HTML, CSS e JavaScript senza dipendenze runtime).
Pubblicato su https://iusentra-sito-vendita.up.railway.app/ dal branch
`claude/software-sales-website-lkyzec`, con Root Directory Railway `sito-vendita`.

Il sito è separato dal gestionale e dal deploy Hetzner. Branch, file, asset e
servizio Railway vanno preservati durante le pulizie del repository; non
riallineare questo branch ai branch gemelli dell'applicazione.

## Stato commerciale

Decisione utente del 04/10/2026: sono in corso le verifiche prima del rilascio.
Prenotazioni, ordini e acquisti non sono ancora aperti. Non pubblicare un modulo
che sembri inviare richieste senza un canale operativo verificato. Email
commerciale e prezzi devono essere confermati dall'utente prima di attivarli.
La pagina non raccoglie dati personali: il selettore di interessi mantiene solo
lo stato in memoria nella pagina, senza invii, cookie o storage locale.

## Percorso della pagina

1. Apertura concreta, PEC illustrata con preparazione e conferma attivate dal visitatore.
2. Scelta tra PEC/scadenze, atti/depositi e clienti/parcelle, ripresa nella vetrina e nel finale.
3. Una pratica in tre scene, con indice che segue la lettura su desktop e flusso normale su mobile.
4. Dieci funzioni esplorabili, senza avanzamento automatico delle schede.
5. Confronto sintetico, otto funzioni aggiuntive espandibili, controllo dell'avvocato e riferimenti normativi.
6. Piani in definizione, domande e percorso personale da rivedere in attesa del rilascio.

Le illustrazioni sono HTML con dati di esempio, dichiarati come tali. Non sono
screenshot di studi reali. Il sito non esegue azioni su PEC, fascicoli o clienti.
I depositi PDP/PAT/PTT restano inviati dall'avvocato nei portali ufficiali; la
FatturaPA è generata, non inviata direttamente allo SdI.

## File e verifica

- `index.html`: pagina e contenuti.
- `assets/stile.css`: palette IUSENTRA, impaginazione e responsive.
- `assets/app.js`: interazioni locali, tastiera, indice e progressione della lettura.
- `Dockerfile`, `Caddyfile`, `railway.json`: hosting statico Railway.
- `verifica_sito.py`: controlli browser ripetibili, richiede Playwright nell'ambiente di sviluppo e Chromium in `/usr/bin/chromium`.
- `REVISIONE_20261004.md`: analisi, scelte e risultati della verifica.

Verifica di sviluppo:

```bash
python3 -m http.server 8080 --directory sito-vendita
python3 sito-vendita/verifica_sito.py http://127.0.0.1:8080/
node --check sito-vendita/assets/app.js
```

Verifica del sito pubblicato:

```bash
python3 sito-vendita/verifica_sito.py https://iusentra-sito-vendita.up.railway.app/
```

Le immagini di verifica sono salvate fuori dal repository in
`/tmp/iusentra-sito-verifica`. I controlli browser non misurano curiosità,
conversioni o comportamento dei visitatori e non sostituiscono l'accettazione
visiva dell'utente sul proprio dispositivo.

Per l'anteprima autonoma:

```bash
python3 sito-vendita/costruisci_anteprima.py /tmp/iusentra-anteprima.html
```

## Pubblicazione Railway

Il servizio esistente deve restare collegato al branch del sito, Root Directory
`sito-vendita`. Railway costruisce l'immagine Caddy e serve i file sulla porta
`$PORT`. Il controllo di salute è `/`. Dopo il push verificare che HTML, CSS e
JavaScript pubblicati corrispondano ai file del commit e provare le interazioni
sull'URL reale. Non creare un secondo progetto o toccare il servizio del gestionale.
