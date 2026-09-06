# Rilascio 2.279.0 — 06/09/2026

Richiesta corrente: commit e deploy. Il rilascio consolida i sorgenti già
sviluppati e le correzioni UI; non certifica la chiusura di tutte le richieste
storiche, un deposito legale o il funzionamento di dispositivi non provati.

## Perimetro incluso

- Mediazione nel fascicolo: repository SQL, API JSON con autorizzazioni,
  organismi/sedi/moduli con provenienza, allegati multipli, PDF compilabile,
  calendario, incontri, esito e audit. Il deposito via API/PEC dell'organismo
  e il presidio automatico delle relative risposte restano lavoro aperto:
  salvare un procedimento non lo trasmette.
- PDF: Tutto schermo, Esc, focus restituito, zoom e foglio centrato a 800 px.
- Scanner/webcam/fotocamera: anteprima, ordine pagine e conferma esplicita
  prima di salvare nel fascicolo; nessun invio automatico e nessun audio.
- PST: catalogo allegati e aggiornamento versionato dei contenuti con hash,
  conservazione della versione precedente e controllo del fascicolo bersaglio.
  Local Signer distribuito 1.6.127; nessuna modifica aggiuntiva al suo runtime
  durante la preparazione di questo rilascio.
- Incluse le correzioni già presenti sul server per eventi, scadenze,
  cartelle condivise e microcopy. Otto file server coincidono integralmente
  con la locale; gli altri due ne sono un sottoinsieme verificato.
- Corretto il catalogo fonti: un tentativo fallito non fa ricomparire un
  modulo ritirato nell'ultimo inventario riuscito.

## Verifiche prima del commit

- Frontend: test completi, typecheck e build passati; 11 guardrail Node per
  acquisizione e salvataggio. Nessun asset oltre il budget di 500 kB.
- Test mirati passati: mediazione (fonti, sedi, catalogo, procedimenti SQL/API),
  acquisizione documenti, strumenti PDF, PST versionato, presidio documentale
  e operativo, UTF-8 e sei contratti React coinvolti.
- Local Signer/installer/build: suite passata dopo il riallineamento del test
  al dettaglio allegati. Restano verificati assenza di preflight aggiuntivo,
  stesso cookie/certificato e divieto di retry certificato.
- Governance repository, Ruff critico e confini Local Signer passati.
- PostgreSQL reale: schema isolato, storico fonti, lease, disattivazione,
  procedimento, versionamento, conflitto atomico e audit verificati; solo lo
  schema temporaneo della prova è stato rimosso. Nessun dato studio toccato.
- Test React shell completo interrotto perché troppo ampio per il controllo
  locale mirato: non conteggiato come superato; i contratti coinvolti sono
  stati rilanciati separatamente. La matrice estesa resta a carico della CI.
- Docker locale ricostruito senza cache e ricreato: /api/pronto risponde
  ok=true, versione 2.279.0, container iusentra-app healthy.
- Prova materiale locale dopo rebuild: aperto il modulo ufficiale già nel
  fascicolo controllato DD242366, cliccato Tutto schermo, osservato il foglio
  centrato, scroll e ritorno con Esc alla vista normale e focus al pulsante.
  Nessun campo salvato né istanza inviata; la scheda originale dell'utente
  non è stata ricaricata per tutelarne i campi non salvati.

## Accettazioni ancora aperte

Scanner/fotocamera fino al PDF salvato: **non verificato su macchina reale**.
La prova precedente ha rilevato assenza di scanner e attesa del permesso video.
PST aggiornamento effettivo dei file e wizard con PIN: da ripetere con l'utente.
Responsive tablet/mobile e campagna completa del procedimento: da concludere.
Queste limitazioni non sono nascoste dai test tecnici o dal rilascio.

## Materiale locale escluso dal rilascio

Backup immutabili Local Signer, copie di recupero, schermate delle prove,
report tecnici storici e vecchi installer non sono stati cancellati. Restano
materiale locale; nessun PIN o screenshot di autenticazione va nel commit.
La .dockerignore esclude esplicitamente copie di recupero, backup e schermate
dal contesto applicativo. I sorgenti utili sono inclusi senza ripristini
distruttivi. I dieci hotfix server saranno conservati in uno stash nominato
prima del deploy, oltre alla loro integrazione nel commit.

CI dello SHA, push gemelli, backup preventivo e deploy sono passaggi successivi
da verificare materialmente; questo verbale pre-commit non li attesta.
