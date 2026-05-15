# Report UI/UX severo 2.236.4

Data: 15/05/2026  
Perimetro browser: 46 route, desktop 1440x980 e mobile 390x844, sessione tenant reale.  
Report tecnico visuale: `artifacts/react-migration/visual-2.236.4/visual-load-audit.md`.

## Sintesi severa

- Esito finale: 92 controlli browser su 92 superati.
- Nessun redirect alla pagina di accesso durante l'audit autenticato.
- Nessun testo tecnico vietato rilevato nel testo visibile delle route verificate.
- Nessun overflow orizzontale rilevato.
- Nessun form POST HTML residuo nel perimetro React verificato.
- Picco prestazionale osservato: `/statistiche` mobile 4421 ms.

## Pagina: Amministrazione studi / `/admin/studi`, `/admin/studi/<slug>`, `/admin/studi/<slug>/database`

### Problemi critici
- Il dettaglio studio poteva bloccare il worker durante una semplice apertura pagina perche' avviava riconciliazioni archivio e scansioni dati in fase di rendering.
- File coinvolti: `web/blueprints/admin.py`, `pct/tenant.py`, `web/templates/admin/studio_dettaglio.html`.
- Correzione applicata: lettura percorsi tenant con `reconcile_aliases=False`, manifest storage opzionale senza riconciliazione, conteggio spazio spostato su API lazy time-boxed.

### Problemi importanti
- Etichette come `slug`, messaggi di errore connessione grezzi e riferimenti archivio troppo tecnici non erano adatti a personale di studio.
- File coinvolti: `web/templates/admin/studi_lista.html`, `web/templates/admin/studio_dettaglio.html`.
- Correzione applicata: `slug` tradotto in `identificativo`, date con filtri italiani, errore connessione reso professionale, riferimenti tecnici nascosti in sezione assistenza.

### Miglioramenti consigliati
- Conservare il conteggio archivio come dato progressivo e non bloccante, con eventuale cache futura lato servizio se il volume cresce ancora.
- File coinvolti: `web/blueprints/admin.py`.
- Modifica consigliata futura: persistere l'ultimo conteggio riuscito con data aggiornamento visibile.

### Controlli superati
- Dettaglio studio 48 ms circa.
- Configurazione archivio 30 ms circa.
- API spazio archivio entro budget parziale di 2 secondi.

## Pagina: Agenda importa / `/agenda/importa`

### Problemi critici
- La superficie React conteneva ancora un form POST HTML, incoerente con il contratto full React e fragile negli stati errore/loading.
- File coinvolti: `frontend/src/components/AgendaImportPage.tsx`, `web/blueprints/api_v1_react.py`, `scripts/react-migration/check-full-react-route-contract.mjs`.
- Correzione applicata: submit React con `fetch`, stato di caricamento, successo ed errore, mantenendo l'anteprima esistente.

### Problemi importanti
- Il caricamento non comunicava in modo sufficiente l'operazione in corso.
- File coinvolti: `frontend/src/components/AgendaImportPage.tsx`, `frontend/src/components/AgendaImportPage.css`.
- Correzione applicata: pulsante disabilitato durante l'invio e messaggio visibile.

### Miglioramenti consigliati
- Aggiungere validazione preventiva lato client sui formati importati prima dell'invio.

### Controlli superati
- Route React operativa, nessun form POST HTML residuo, build e test mirati verdi.

## Pagina: Shell React, TopBar, Drawer e Modal

### Problemi critici
- Drawer e modali non avevano garanzia uniforme di focus trap, Escape, ripristino focus e blocco scroll.
- File coinvolti: `frontend/src/ui/legalPrimitives.tsx`, `frontend/src/ui/ui.css`.
- Correzione applicata: hook `useManagedDialog`, z-index coerente, azioni mobile wrappabili.

### Problemi importanti
- Alcuni bottoni icona non avevano nome accessibile o tooltip, e testi lunghi nel menu potevano essere tagliati.
- File coinvolti: `frontend/src/components/layout/TopBarCreateMenu.tsx`, `frontend/src/components/layout/TopBar.css`, `frontend/src/components/sitoStudioBuilder/BuilderProperties.tsx`, `web/templates/admin/base.html`.
- Correzione applicata: `aria-label`, `title`, icone decorative nascoste, focus ring visibile e clamp a due righe.

### Miglioramenti consigliati
- Consolidare una primitiva unica `IconButton` per evitare regressioni future.

### Controlli superati
- Navigazione tastiera di base preservata, focus visibile, nessuna sovrapposizione rilevata nel visual audit.

## Pagina: Tabelle e liste operative

### Problemi critici
- Le tabelle con molte colonne rischiavano lettura difficile o scroll orizzontale su mobile.
- File coinvolti: `frontend/src/components/iusentra/IusDataTableShell.tsx`, `frontend/src/styles/iusentra-design-system.css`.
- Correzione applicata: celle con `data-label`, layout mobile a card, scrollbar e wrapping governati.

### Problemi importanti
- Nomi lunghi, badge e valori potevano stringere le card/list row.
- File coinvolti: `frontend/src/index.css`, `frontend/src/styles/iusentra-design-system.css`.
- Correzione applicata: wrapping, clamp a due righe, dimensioni stabili per action row e bottoni.

### Miglioramenti consigliati
- Aggiungere test visuali automatici specifici per nomi utente oltre 60 caratteri e tabelle oltre 8 colonne.

### Controlli superati
- Nessun overflow orizzontale su desktop/mobile nelle 46 route verificate.

## Pagina: AI locale, Lex assistant e Compensi

### Problemi critici
- Alcuni messaggi rivolti all'avvocato contenevano termini da sviluppatore o diagnostica non professionale.
- File coinvolti: `web/static/js/impostazioni-ai.js`, `web/static/js/pct-lex-assistant.js`, `frontend/src/components/CompensiForensiPage.tsx`.
- Correzione applicata: sostituiti testi tecnici con linguaggio operativo, errori comprensibili e stato locale leggibile.

### Problemi importanti
- Gli errori grezzi potevano esporre dettagli non utili all'utente.
- File coinvolti: `web/static/js/impostazioni-ai.js`.
- Correzione applicata: ultimo errore tradotto in invito a ripetere verifica o preparazione.

### Miglioramenti consigliati
- Spostare eventuale diagnostica estesa in log o pannello assistenza non visibile nella UI ordinaria.

### Controlli superati
- `node --check` verde e visual audit senza termini tecnici vietati.

## Pagine verificate senza problemi residui

| Pagina / route | Desktop | Mobile | Esito |
| --- | ---: | ---: | --- |
| Panoramica `/` | 677 ms | 3038 ms | OK |
| Regia Operativa `/workspace-intelligente` | 2811 ms | 699 ms | OK |
| Ricerca Studio `/global-search` | 1354 ms | 1178 ms | OK |
| Agenda `/agenda` | 1061 ms | 1064 ms | OK |
| Nuovo Appuntamento `/agenda/nuovo` | 756 ms | 1333 ms | OK |
| Timesheet `/timesheet` | 1294 ms | 1790 ms | OK |
| Fascicoli `/fascicoli` | 775 ms | 1310 ms | OK |
| Nuovo Fascicolo `/fascicoli/nuovo` | 1420 ms | 1021 ms | OK |
| Archivio Fascicoli `/fascicoli/archivio` | 1020 ms | 976 ms | OK |
| Clienti `/clienti` | 742 ms | 1472 ms | OK |
| Nuovo Cliente `/clienti/nuovo` | 718 ms | 1472 ms | OK |
| Cartelle Condivise `/cartelle-condivise` | 1290 ms | 1787 ms | OK |
| Soggetti `/soggetti` | 723 ms | 1061 ms | OK |
| Nuovo Soggetto `/soggetti/nuovo` | 726 ms | 1077 ms | OK |
| Email PEC `/email` | 796 ms | 1267 ms | OK |
| Email ordinaria `/email-ordinaria` | 1903 ms | 4337 ms | OK |
| Messaggi `/messaggi` | 4025 ms | 1837 ms | OK |
| Nuovo SMS/WA `/messaggi/nuovo` | 799 ms | 1866 ms | OK dopo retry strumentale |
| Scadenziario `/scadenziario` | 1843 ms | 1989 ms | OK |
| Nuova Scadenza `/scadenziario/nuova` | 1762 ms | 1822 ms | OK |
| Preparazione Udienza `/wizard-pro` | 2318 ms | 2612 ms | OK |
| Controlli Atti `/deposito/checklist` | 924 ms | 2346 ms | OK |
| Studio `/studio` | 1369 ms | 1245 ms | OK |
| Fatturazione `/fatturazione` | 1019 ms | 1765 ms | OK |
| Preventivi `/preventivi` | 1235 ms | 1391 ms | OK |
| Nuovo Preventivo `/preventivi/nuovo` | 1379 ms | 2664 ms | OK |
| Nuovo Conferimento `/preventivi/conferimento/nuovo` | 1365 ms | 1290 ms | OK |
| Dettaglio Conferimento | 1325 ms | 1305 ms | OK |
| Compensi Forensi `/compensi-forensi` | 2302 ms | 2342 ms | OK |
| Redazione Atti `/redazione-atti` | 3065 ms | 1805 ms | OK |
| Statistiche `/statistiche` | 3574 ms | 4421 ms | OK, da mantenere come baseline massimo |
| Ricerca Legale `/ricerca-legale` | 3470 ms | 1880 ms | OK |
| Giurisprudenza `/giurisprudenza` | 1221 ms | 1250 ms | OK |
| Strumenti Forensi `/strumenti-legali` | 712 ms | 1470 ms | OK |
| Strumenti Operativi `/strumenti-operativi` | 1160 ms | 1005 ms | OK |
| Sito Studio `/sito-studio` | 1553 ms | 1476 ms | OK |
| Amministrazione `/amministrazione` | 1124 ms | 1072 ms | OK |
| Utenti `/utenti` | 2864 ms | 1192 ms | OK |
| Profili `/profili` | 1601 ms | 1331 ms | OK |
| Registro Attivita `/audit` | 1328 ms | 2890 ms | OK |
| Database `/admin/database` | 886 ms | 3378 ms | OK |
| Registro GDPR `/privacy/registro` | 3234 ms | 1104 ms | OK |
| Impostazioni `/impostazioni` | 3112 ms | 3502 ms | OK |
| Backup `/backup` | 3180 ms | 3561 ms | OK |
| Notifiche `/notifiche` | 3257 ms | 3235 ms | OK |
| Calendari `/impostazioni/calendario` | 3222 ms | 3248 ms | OK |

## Priorita' globali

1. Evitare operazioni pesanti in rendering pagina.
2. Eliminare ogni form POST HTML dalle superfici React operative.
3. Rendere drawer e modali pienamente governati da tastiera.
4. Stabilizzare bottoni icona con label accessibili.
5. Rendere tabelle leggibili su mobile senza scroll orizzontale obbligato.
6. Impedire taglio di nomi, titoli e valori lunghi.
7. Continuare la pulizia dei testi tecnici nelle route future.
8. Tenere `/statistiche`, `/email-ordinaria` e `/messaggi` come baseline prestazionale sensibile.
9. Aggiungere test visuali automatici per zoom 125% e 150%.
10. Estrarre `IconButton`, `DataTable` e dialog primitives come componenti riutilizzabili obbligatori.

## Checklist finale

- Aprire route rappresentative in desktop, tablet, mobile e mobile landscape.
- Verificare zoom browser 125% e 150%.
- Controllare assenza di overflow orizzontale.
- Provare tastiera: Tab, Shift+Tab, Enter, Escape.
- Verificare loading, empty, error, success.
- Testare utenti e clienti con nomi lunghi.
- Testare card con pochi dati e con molti dati.
- Testare tabelle con molte colonne.
- Verificare che ogni icona abbia significato, label o tooltip.
- Verificare che i messaggi visibili siano italiani, professionali e non tecnici.
- Eseguire build, gate React, pytest mirati, Docker locale e visual audit.

## Patch ordinata per priorita'

1. Fase 1: corretto blocco visualizzazione admin studio con lazy storage e niente reconcile in rendering.
2. Fase 2: corretto form POST HTML in `/agenda/importa`, testi tagliati e bottoni icona senza label.
3. Fase 3: corretti disallineamenti e wrapping in TopBar, action row, card e tabelle.
4. Fase 4: migliorati testi/contrasto semantico degli stati admin, AI locale e Lex.
5. Fase 5: tabelle e action row rese responsive su mobile.
6. Fase 6: ridotto spazio morto negli stati vuoti/loading con dimensioni responsive.
7. Fase 7: uniformati card, modali, drawer e bottoni sulle primitive IUSENTRA.
