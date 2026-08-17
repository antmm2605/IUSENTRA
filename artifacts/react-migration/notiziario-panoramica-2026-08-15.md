# Notiziario nella Panoramica

## Stato dell'intervento

Data del collaudo: 15 agosto 2026.

Il Notiziario è stato integrato nella Panoramica React come superficie operativa reale. Non usa dati dimostrativi e non contiene riferimenti visibili a prodotti esterni.

## Dati e proprietà tenant

- Le notizie pubblicate provengono dal repository strutturato `legal_updates` già usato dalla pipeline di aggiornamento legale.
- Fonte, categoria e ufficialità sono lette tramite le relazioni SQL `news`, `source_documents_normalized`, `source_documents_raw` e `sources`.
- Stato di lettura, preferito e collegamento al fascicolo sono salvati per utente nella tabella tenant `settings_config`.
- SQLite locale e PostgreSQL di produzione usano lo stesso schema `settings_config`; il JSON non è fonte operativa.
- Le fonti rapide sono una lista chiusa di siti istituzionali. Il lettore rifiuta URL non riconosciuti e limita dimensione, durata e redirect del recupero.

## API e interfaccia

- `GET /api/v1/ui/notiziario`: elenco delle sole notizie pubblicate, filtri, fascicoli disponibili e stato utente.
- `PATCH /api/v1/ui/notiziario/<id>/interazione`: lettura, preferito e collegamento al fascicolo con controllo tenant.
- `GET /api/v1/ui/notiziario/fonti/<fonte>`: lettura testuale governata della fonte istituzionale selezionata.
- Il componente React consente ricerca, filtri per fonte e stato, tutto schermo, lettura, preferiti, collegamento a fascicolo e apertura della nuova scadenza precompilata.
- Il lettore delle fonti non usa riquadri esterni vuoti: quando il sito non offre testo leggibile mostra una spiegazione e conserva il collegamento al sito ufficiale.

## Prova reale locale

Collaudo eseguito nella sessione autenticata reale su `http://127.0.0.1:8080` dopo ricostruzione del container `iusentra-app`, risultato healthy.

Sono stati osservati materialmente:

- caricamento di 8 aggiornamenti reali dalla Gazzetta Ufficiale;
- passaggio del contatore da 8 a 7 dopo la lettura e persistenza dopo ricaricamento;
- aggiunta e rimozione del preferito con filtro dedicato;
- collegamento al fascicolo `RG 1025/2026` e successiva rimozione del dato di prova;
- apertura di `Nuova scadenza` con titolo, descrizione, fonte e note precompilati, senza salvataggio di una scadenza di prova;
- lettura interna riuscita per Gazzetta Ufficiale e Consiglio Nazionale Forense;
- messaggio esplicito, senza area vuota, per una fonte non leggibile nel pannello;
- ricerca testuale, stato hover, focus visibile, tutto schermo e scroll completo;
- resa desktop, tablet `900 × 900` e mobile `390 × 844`, poi ripristino della dimensione normale.

Gli stati di lettura e preferito usati nel collaudo sono stati ripristinati; nessuna scadenza o collegamento di prova è rimasto salvato.

## Guardrail automatici

- `python -m pytest tests/test_notiziario_react.py -q`
- compilazione Python dei moduli modificati;
- typecheck TypeScript;
- build Vite nella ricostruzione Docker reale;
- controllo di URL istituzionali, estrazione testuale, API elenco/interazioni/fonti e persistenza SQL tenant.

## Limite governato

Alcuni siti istituzionali possono non esporre testo leggibile senza autenticazione o possono rifiutare il recupero automatico. In quel caso il pannello non simula contenuti: dichiara l'indisponibilità e offre il collegamento ufficiale. Il Notiziario e tutte le altre azioni restano operativi.


## Aggiornamento 17 agosto 2026 - Notizie utili

Il nome visibile della superficie è stato aggiornato in **Notizie utili**, coerente con l'uso quotidiano di uno studio legale.

### Fonti ufficiali presidiate

L'aggiornamento dedicato interroga esclusivamente queste fonti:

- Ministero della giustizia;
- Portale dei Servizi Telematici del Ministero della giustizia;
- Consiglio Nazionale Forense;
- Cassa Forense tramite CF News;
- Gazzetta Ufficiale;
- Corte Suprema di Cassazione.

La fonte fiscale non pertinente è stata rimossa dalla superficie. Ogni risposta e ogni reindirizzamento devono restare nei domini ufficiali ammessi.

### Aggiornamento e persistenza

- POST /api/v1/ui/notiziario/aggiorna aggiorna le sei fonti in parallelo con limiti di tempo e quantità.
- La cache ufficiale è salvata nella tabella tenant settings_config, sezione notizie_utili_fonti_v1, valida sia per SQLite sia per PostgreSQL.
- Il caricamento iniziale usa la cache SQL e richiede automaticamente un aggiornamento quando manca o supera sei ore.
- Se una sola fonte non risponde, vengono conservati soltanto i suoi elementi precedenti; le altre fonti continuano ad aggiornarsi.
- Lettura, preferito e collegamento al fascicolo restano persistenti anche per gli identificativi ufficiali stabili.

### Interfaccia

- Il comando Aggiorna esegue ora un recupero reale dalle fonti, non una semplice rilettura del database.
- I filtri e le fonti rapide comprendono anche PST Giustizia e Corte di Cassazione.
- La freccia nell'angolo inferiore destro chiude e riapre l'intero pannello.
- Il pannello conserva ricerca, lettore interno, tutto schermo, preferiti, fascicolo e creazione della scadenza.

### Verifiche eseguite prima del collaudo visivo

- python -m compileall pct web -q;
- npm run typecheck;
- python -m pytest tests/test_notizie_utili.py tests/test_notiziario_react.py tests/test_utf8_integrity.py -q: 19 test superati;
- recupero reale delle sei fonti: tutte raggiungibili, con contenuti più recenti rilevati il 17 agosto 2026 per Gazzetta Ufficiale e Corte di Cassazione.
- container locale ricostruito e healthy su http://127.0.0.1:8080;
- POST reale /api/v1/ui/notiziario/aggiorna nel container: 61 elementi, sette filtri compreso Tutte e sei fonti con esito positivo.

### Stato della prova visiva

Il servizio di controllo del browser integrato Codex non si è avviato per un errore del sandbox Windows. La nuova freccia e i filtri non sono quindi dichiarati verificati materialmente in questa sessione; la prova API reale non viene usata come sostituto della prova visiva.
