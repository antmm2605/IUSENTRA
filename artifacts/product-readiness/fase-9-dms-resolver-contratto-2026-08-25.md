# Fase 9 — Contratto DMS, comunicazioni e catalogazione dal contenuto

- Stato: implementazione applicata e verificata sul fascicolo controllato per
  contenuto, prova, lettore interno, correzione manuale e resa responsive.
  Restano i gate di test completi, commit, distribuzione e verifica della
  stessa release su Hetzner.
- Data: 25/08/2026, Europa/Roma.
- Oggetto: rendere il documento un oggetto operativo del fascicolo, con identità leggibile, prova, versioni, collegamenti e revisione professionale.
- Fonte di verità: SQLite locale e PostgreSQL produzione, con parità di schema; i JSON restano mirror rigenerabili.

## Esito dell'ispezione sul fascicolo controllato

La prova nella copia reale `127.0.0.1:8080`, fascicolo `DC5BF1DB`, ha
confermato che il catalogo SQL, il lettore interno, le versioni, l'audit e le
azioni React esistono. Ha però individuato un errore sostanziale nel resolver:
una regola di presidio processuale può sostituire l'identità del singolo
documento. Esempi osservati nel catalogo SQL:

- una memoria conclusionale che menziona il CTU viene proposta come `ATP previdenziale / CTU`;
- una sentenza che tratta anche la liquidazione della CTU viene proposta come `Decreto di liquidazione CTU`;
- note scritte e comunicazioni di cancelleria possono ereditare una materia o un termine anziché il loro tipo documentale.

Questo non è un problema grafico: può alterare sezione, tipo, ruolo di deposito
e lettura operativa. Non sono stati modificati documenti originali, firme,
download, deposito, notifica o dati del fascicolo durante l'analisi.

## Regola vincolante: identità prima, presidio separato

Per ogni versione documentale il resolver deve seguire questa precedenza:

1. **Identità locale dal contenuto**: intestazione, titolo, dispositivo e
   formule presenti nelle prime pagine del testo indicizzato; nome file e
   metadati possono solo aiutare il recupero e non provano l'identità.
2. **Provenienza e integrità**: formato, firma, contenitore, canale ufficiale,
   hash e rapporto con il fascicolo; non sostituiscono il tipo se il testo dice
   altro.
3. **Segnalazioni di presidio**: termine, udienza, richiamo normativo,
   contributo, CTU, rito o adempimento sono annotazioni separate, con evidenza
   e fonte; non sovrascrivono mai l'identità documentale.
4. **Revisione umana**: in caso di conflitto o prova insufficiente il documento
   resta `Da verificare`; non diventa automaticamente depositabile, firmabile o
   idoneo alla notifica.

La sequenza è quindi, ad esempio:

| Testo del documento | Identità proposta | Segnalazione separata |
| --- | --- | --- |
| `MEMORIA CONCLUSIVA` con richiami a CTU | Memoria conclusionale / atto difensivo | Riferimento a CTU, se utile al presidio |
| `IN NOME DEL POPOLO ITALIANO` e `SENTENZA`, anche con spese CTU | Sentenza | Eventuale liquidazione spese da controllare |
| `NOTE DI TRATTAZIONE SCRITTA` | Note scritte / atto difensivo | Possibile termine o udienza da validare |
| `NOTIFICAZIONE DI CANCELLERIA` | Comunicazione di cancelleria | Eventuale atto o termine richiamato |
| `ACCETTO L'INCARICO` e `GIURO` del CTU | Accettazione incarico e giuramento CTU | Avvio attività peritali, se espresso |

## Fonti e criteri professionali

- Le [Linee guida AgID sul documento informatico](https://www.agid.gov.it/it/linee-guida?arguments%5B268%5D=268&arguments%5B286%5D=286) trattano formazione, gestione, conservazione e metadati come un unico ciclo: IUSENTRA conserva quindi origine, versione, hash, evidenza e audit invece di una sola etichetta.
- L'[articolo 32 GDPR su EUR-Lex](https://eur-lex.europa.eu/eli/reg/2016/679/oj?eliuri=eli%3Areg%3A2016%3A679%3Aoj&locale=it) richiede misure adeguate a riservatezza, integrità, disponibilità e resilienza: il nuovo dettaglio prova mostrerà solo estratti necessari e manterrà l'apertura nel lettore interno autorizzato.
- Le [specifiche tecniche del PST](https://pst.giustizia.it/PST/resources/cms/documents/SpecificheTecnicheTestoCoordinatoArticolato.pdf), art. 11, distinguono nel fascicolo atti, allegati e ricevute PEC e richiedono profilazione/autorizzazione e log degli accessi. Il catalogo manterrà quindi distinti identità, origine, ruolo di deposito e audit; una classificazione non abilita da sola il deposito.
- Il [PST — deposito generico](https://pst.giustizia.it/PST/it/dettaglio_schede_tematiche.page?contentId=ACC239&modelId=12) conferma che atto, allegati e dati strutturati della busta hanno ruoli distinti: la proposta del catalogo non può sostituire la verifica del flusso di deposito.

## Implementazione applicata

### Resolver e pipeline

- Introdurre nel resolver Document AI un riconoscitore di **identità
  contenuto-prima**, ristretto alle evidenze forti e deterministiche.
- Lasciare intatto il ruleset di presidio; convertirne gli esiti in evidenze
  `procedural_signal` distinte dalla classificazione, con codice della regola,
  estratto e peso.
- Incrementare la versione del resolver così che i documenti già indicizzati
  siano ricalcolabili in modo idempotente, senza sovrascrivere le correzioni
  manuali dell'avvocato.
- Conservare l'assegnazione precedente come storico `superseded`, l'audit del
  ricalcolo e il legame alla medesima impronta SHA-256.

### Repository, API e React

- Estendere il payload SQL con evidenze ordinate e segnali procedurali
  separati; nessun testo integrale è duplicato nel payload.
- Nel pannello `Catalogazione documentale`, usare un disclosure `Prova e fonti`
  per mostrare: identità, estratto minimo, segnalazioni separate, fonti
  versionate e il comando `Apri nel lettore`. Non introdurre icone ridondanti
  “Informazioni” o “Catalogo”.
- Sostituire i codici tecnici del profilo, quando visibili, con denominazioni
  professionali leggibili, mantenendo il codice solo come metadato tecnico non
  esposto.
- Conservare senza refactoring i comandi già reali `Visualizza`, `Scarica`,
  `Modifica`, `Firma`, `Attesta`, `PDF/A`, `Elimina`, il lettore interno,
  versioni e i flussi deposito/notifica.

La release corrente è `2.278.77`, con resolver
`2026.08.25.catalogo-fascicolo.v14`. Sono state aggiunte formule
contenuto-prima per **Decreto di fissazione udienza**, **Istanza di
trattazione scritta**, **Nota di deposito** e **Istanze e conclusioni**. Le
formule sono memorizzate e mostrate come prova di identità; riferimenti a RG,
udienza, CTU, rito o contributo restano separati come segnali procedurali.

### Casi di regressione obbligatori

1. Memoria conclusionale con un richiamo a CTU: non diventa ATP/CTU.
2. Sentenza con liquidazione CTU: non diventa decreto.
3. Note di trattazione scritta con riferimento all'art. 127-ter: restano atto
   difensivo e segnalano separatamente il presidio.
4. Comunicazione di cancelleria che richiama un CTU: resta comunicazione.
5. Accettazione/giuramento CTU, perizia tecnica e verbale d'udienza hanno
   identità proprie.
6. Correzione manuale, hash invariato, refresh del resolver, revisione e audit
   restano idempotenti e tenant-aware in SQLite e PostgreSQL.
7. Il lettore e il download interno continuano a funzionare sul documento
   originale; il catalogo non modifica file, firme o ruoli già confermati.

## Riscontri di accettazione già eseguiti

- Sul fascicolo controllato `DC5BF1DB`, il click reale su **Aggiorna
  catalogazione** ha elaborato 20 documenti e prodotto cinque identità dal
  testo indicizzato: due *Istanze di trattazione scritta*, una *Nota di
  deposito*, un *Decreto di fissazione udienza* e una voce *Istanze e
  conclusioni*. Alla conclusione non erano rimasti documenti in revisione
  dovuta alla regola di presidio.
- Il click reale su **Prova e fonti** per il decreto ha mostrato la formula
  `Decreto di fissazione udienza`, i segnali procedurali separati e cinque
  fonti ufficiali. **Apri la prova nel lettore** ha aperto una sola preview
  interna IUSENTRA della fonte, poi chiusa correttamente, senza schede o
  lettori esterni.
- Una correzione manuale sul fascicolo controllato dedicato `2DE106E6` è
  rimasta `manual_override` dopo il refresh: identità *Memoria
  conclusionale*, natura `atto_processuale`, ruolo `fuori_busta` e candidato
  deposito disattivato. L'audit di correzione e lo storico della versione sono
  conservati in SQL.
- Nella vista reale il pannello è stato verificato con scroll completo a
  1329×912, 768×1024 e 390×844: nessun overflow orizzontale, titoli e azioni
  leggibili, pulsanti disposti su più righe se necessario. Hover e focus da
  tastiera su **Correggi catalogo** mantengono contrasto, testo e contorno
  visibili.

## Gate ancora necessari prima della chiusura della fase

- Rebuild senza cache della copia Docker locale e `GET /api/pronto` su
  `127.0.0.1:8080`.
- Test mirati Python/React, parità SQLite/PostgreSQL, performance del refresh,
  commit, push dei due branch, deploy Hetzner e verifica dell'unico
  `iusentra-app` healthy sullo stesso commit.

Finché queste prove non sono eseguite, la Fase 9 resta aperta.
