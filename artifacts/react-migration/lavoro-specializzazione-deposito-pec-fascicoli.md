# Lavoro IUSENTRA da aggiungere dopo analisi QuickOrganizer

Generato: 30/06/2026 18:10 (Europe/Rome).

## Obiettivo

Specializzare IUSENTRA mantenendo blindato ciò che è già stato provato realmente: cache certificati PST, accettazione cancelleria, invio PEC dal PC locale, deposito React e controlli anti-regressione.

## Deposito telematico React

- Aggiungere repository catalogo deposito con 270 tipi QuickOrganizer come confronto e con fonte ufficiale PST/XSD come autorità normativa.
- Nel passo `2. Documenti da inviare`, aggiungere menu compatto macroarea/categoria/tipo simile a QuickOrganizer.
- Alla scelta salvare `schema_key`, `channel`, `datiatto_methods`, root XML, codice oggetto proposto, documenti obbligatori e validazioni.
- Rendere visibili i requisiti bloccanti puntuali quando `Invia deposito reale` resta disabilitato.
- Non toccare la prova reale già blindata di accettazione cancelleria se non con test mirati e nuova prova reale.

## XSD e busta

- Creare mappa IUSENTRA `schema_key -> generator -> root XML -> IndiceBusta -> document rules`.
- Verificare ogni generatore contro XSD ufficiali PST aggiornati, incluse rettifiche DGSIA e news 2026.
- Controllare `DatiAtto.xml.p7m`, `IndiceBusta.xml`, `IndiceDocumentiDepositati.PDF`, Content-ID MIME e `Atto.enc` CMS AES256.

## Firma/PIN/Local Signer

- Allineare firma multipla alla logica sessione: PIN solo in memoria, firma più file, salvataggio esito per documento.
- Separare certificato firma, certificato autenticazione portali e certificato pubblico ufficio.
- Auditare errori PIN/certificato senza fallback silenziosi.

## PEC, notifiche e ricevute

- Estendere normalizzazione oggetti PEC con prefissi QuickOrganizer.
- Collegare ricevute ad agenda, scadenziario, notifiche interne e Web Push solo dopo classificazione certa.
- Tenere notifiche L. 53 separate dal deposito PCT, con relata firmata quando richiesta e prova senza invio reale.

## Ricerca fascicoli e download

- Migliorare ricerca globale fascicoli con segnali equivalenti a `PRATICHE`, `TESTI`, `EMAILS`, `AGENDA`, `TAVOLA`.
- Indicizzare RG, anno, ufficio, oggetto, parti, documenti, PEC, ricevute, notifiche e scadenze.
- Per portali/PolisWeb salvare origine, hash, ufficio, data italiana, ruolo e fascicolo tenant-aware.
- Integrare la mappa registri consultazione: 18 combinazioni/alias registrate in `quickorganizer-registri-consultazione-fascicoli.md`.
- Replicare in React le azioni operative rilevate nel menu `Accesso al PolisWeb...`: 13 comandi distinti tra wizard, fascicolo d'ufficio, agenda, scadenze, documenti, Cassazione e notifiche.
- Separare `Importa Pratiche dal PolisWeb` da `Accesso al PolisWeb`: il primo sincronizza dati tramite wizard/servizi, il secondo apre il portale PST assistito con WebView2 e intercetta download.
- Aggiungere ricerca fascicolo per anno come parametro governato: quando manca il numero ruolo usare `numero=0` solo sui registri/metodi che lo prevedono.
- Implementare `Scarica intero fascicolo` come batch di scarichi singoli con deduplica `idCat/IdDocumento/hash`, progress, ripresa su errore e salvataggio SQL tenant-aware.

## Certificati e codici

- Audit IUSENTRA certificati: 593 operativi, 593 coperti secondo audit locale.
- Watchlist codici QuickOrganizer non in IUSENTRA: 461401, 461402, 461403, 481321, 481322, 481323.
- Non importare certificati storici o sezioni distaccate senza servizi come blocchi globali.

## Dati/tenant/SQL

- Ogni nuovo dato va su SQLite e PostgreSQL con JSON solo mirror.
- API JSON e React full devono restare la superficie primaria.
- Ogni import QuickOrganizer deve evitare password/account e dati personali non richiesti.

## Verifiche obbligatorie future

- Test mirati su catalogo deposito, mapping schema, PEC workflow, ricerca fascicoli e certificati.
- Prova reale su `127.0.0.1:8080` prima di dichiarare qualunque comportamento utente.
- Browser reale, scroll completo, hover/focus, responsive e testo italiano corretto quando la UI verrà modificata.
