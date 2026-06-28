# Fatturazione, XML SdI, PEC e commercialista - lavori da eseguire

Data analisi: 28 giugno 2026
Stato: implementazione in corso, prima verifica reale locale eseguita su PDF e dettaglio fattura
Pagina reale di riferimento: `http://127.0.0.1:8080/fatturazione/`

## Richieste utente raccolte

- `Apri dettaglio` deve aprire davvero una vista utile per modificare la parcella/fattura e aggiungere o modificare le voci.
- Il PDF deve essere visualizzato dentro la stessa pagina, senza aprire una nuova pagina, con opzione a tutto schermo.
- L'XML FatturaPA deve poter essere firmato digitalmente con Local Signer.
- Dopo la firma XML, IUSENTRA deve preparare la PEC per SdI allegando il file XML firmato.
- L'indirizzo SdI deve arrivare dalle impostazioni, senza invii server-side non governati.
- Se la PEC SdI viene inviata, la fattura deve registrare data invio, canale, identificativo e successivo esito SdI.
- Serve anche l'invio al commercialista: nelle impostazioni deve esserci l'indirizzo email del commercialista e dalla fattura deve essere preparata una email con allegato.
- Tutta la UI deve restare responsive desktop, tablet e mobile, con hover/focus leggibili e senza regressioni.

## Stato attuale rilevato nel codice

- La pagina React vive in `frontend/src/components/FatturazionePage.tsx`.
- I dati e le API frontend vivono in `frontend/src/fatturazioneData.ts`.
- `Apri dettaglio` chiama gia' `getFatturazioneDetail`, ma il pannello dettaglio e' renderizzato in fondo alla pagina e non offre modifica delle voci.
- I pulsanti `PDF` e `XML` sono link diretti (`pdfHref`, `xmlHref`), quindi oggi portano fuori dal flusso in pagina.
- Il backend ha gia' generazione PDF e XML in `web/blueprints/fatturazione.py`.
- La generazione XML usa `pct/fattura_pa.py`.
- Il modello `pct/fatturazione.py` contiene gia' campi SdI: stato, identificativo, data invio, data esito, ricevuta, note.
- Le impostazioni SdI esistono gia' in `ConfigSDI`, bridge React e tab `Canali SdI`, ma non c'e' ancora un campo commercialista.
- Il Local Signer espone gia' `/firma`, `/firma-batch`, `/pec/send` e `/pec/smtp/test`.
- Esistono helper per invio PEC locale tramite Local Signer in `web/services/local_pec_runtime.py`.

## Soluzione proposta

1. Trasformare `Apri dettaglio` in un pannello operativo sulla stessa pagina.
   - Desktop: pannello contestuale sotto la fattura selezionata o subito sotto l'archivio con scroll/focus automatico.
   - Tablet/mobile: pannello full-width, con sezioni compatte e pulsanti ben leggibili.
   - Funzioni minime: modifica dati principali, modifica voci, aggiungi voce, rimuovi voce, salva, annulla, stati loading/errore/successo.

2. Sostituire il link PDF con anteprima in pagina.
   - Usare l'endpoint PDF esistente in modalita' inline.
   - Toolbar: scarica, aggiorna, tutto schermo, chiudi.
   - Su mobile/tablet l'anteprima deve diventare pannello quasi fullscreen per non tagliare il documento.

3. Governare l'XML FatturaPA come workflow, non come semplice download.
   - Genera XML da backend con le funzioni esistenti.
   - Mostra stato XML nella fattura.
   - Firma XML tramite Local Signer dal browser sul PC dell'avvocato.
   - Salva il file firmato `.xml.p7m` in percorso tenant-aware, con hash, data firma e audit.

4. Preparare e inviare PEC SdI dal PC locale.
   - Il server prepara destinatario, oggetto, corpo e allegato firmato.
   - Il browser invia il payload al Local Signer `/pec/send`.
   - Solo dopo risposta positiva il backend registra invio, data italiana, message-id e stato SdI.
   - Gli esiti successivi SdI vanno registrati nella timeline della fattura.

5. Aggiungere commercialista nelle impostazioni.
   - Nuovi campi proposti in `Canali SdI` o sezione fatturazione collegata:
     - email commercialista
     - nome commercialista
     - allegati predefiniti: PDF, XML firmato, entrambi
   - Dalla fattura: azione `Email commercialista` con bozza in pagina o apertura composer IUSENTRA precompilato.

6. Verifiche anti-regressione.
   - Prova reale su `127.0.0.1:8080/fatturazione/`.
   - Hover/focus/click su `Apri dettaglio`, `PDF`, `XML`, firma, invio PEC, email commercialista.
   - Responsive desktop, tablet e mobile.
   - Test mirati frontend/backend sulle API toccate.
   - Documentazione finale in questo file e nei report React pertinenti.

## Domande da chiudere prima del codice

1. Per il commercialista devo usare email ordinaria o PEC?
2. Per il commercialista devo allegare solo PDF, oppure PDF piu' XML firmato?
3. Per SdI vuoi un campo dedicato `PEC destinatario SdI` separato dalla `PEC per notifiche SdI`, oppure riuso il campo esistente?
4. Dopo la firma XML, il software deve solo preparare la PEC per controllo finale o deve inviarla con un secondo pulsante esplicito `Invia PEC SdI`?

## File da toccare dopo conferma

- `frontend/src/components/FatturazionePage.tsx`
- `frontend/src/components/FatturazionePage.css`
- `frontend/src/fatturazioneData.ts`
- `web/services/react_fatturazione_bridge.py`
- `web/blueprints/api_v1_react.py`
- `web/blueprints/fatturazione.py`
- `pct/fatturazione.py`
- `pct/fattura_pa.py`, solo se serve esporre metadati/validazioni senza cambiare il generatore stabile
- `frontend/src/features/impostazioni/constants.ts`
- `frontend/src/features/impostazioni/types.ts`
- `web/services/react_impostazioni_bridge.py`
- `web/blueprints/impostazioni.py`
- `pct/config_studio.py`
- Test mirati in `tests/` e documentazione in `artifacts/react-migration/`

## Aggiornamento operativo - 28 giugno 2026

Richiesta aggiuntiva utente: togliere il colore di sfondo dalle intestazioni della tabella nella parcella PDF e applicare una sola impostazione comune a tutti i PDF generati da IUSENTRA.

Soluzione applicata:

- creata la regola unica `pct/pdf_style.py::pdf_table_header_style`;
- impostazione centrale: intestazione tabella con sfondo bianco, testo scuro e linea inferiore blu IUSENTRA;
- rimossi gli stili locali scuri sulle intestazioni tabellari ReportLab nei generatori PDF principali;
- generatori riallineati: parcelle/fatture, preventivi, notifiche, template atti, editor documenti, report e PDP penale;
- aggiunto presidio automatico `tests/test_pdf_style.py` per impedire il ritorno di intestazioni scure locali sui PDF principali.

Verifica reale locale eseguita:

- Docker reale locale `127.0.0.1:8080` ricreato e healthy;
- `/api/pronto` restituisce `ok=true`, `timezone=Europe/Rome`, `versione=2.253.134`;
- browser integrato visibile su `http://127.0.0.1:8080/fatturazione/`;
- click reale su `Apri dettaglio`: il dettaglio si apre in finestra sovrapposta nella stessa pagina;
- click reale su `Anteprima PDF`: il PDF viene visualizzato nella stessa finestra;
- nella sezione `Prestazioni professionali` sono leggibili `Descrizione`, `Q.tà`, `Prezzo unit.` e `Importo`, senza sfondo scuro.
- tab `XML e SdI` verificato: mostra XML originale disponibile, XML firmato da generare, PEC SdI non configurata, PEC non ancora inviata e pulsante rapido `Inserisci impostazioni PEC`;
- tab `Commercialista` verificato: mostra commercialista non configurato, destinatario non configurato, stato `Commercialista non ancora inviato`, scelta email ordinaria/PEC, scelta allegati e pulsante rapido `Inserisci commercialista`.

Guardrail eseguiti:

- `python -m pytest tests\test_pdf_style.py tests\test_react_fatturazione_bridge.py -q` -> OK;
- `python -m py_compile pct\pdf_style.py pct\reports.py pct\editor.py web\blueprints\fatturazione.py web\blueprints\preventivi.py web\notifiche.py web\template_atti.py web\services\pdp_penale_runtime.py` -> OK;
- `pnpm --filter @iusentra/studio typecheck` -> OK.

Stato aperto da non perdere:

- verificare simulazione firma XML e preparazione PEC SdI senza invio reale;
- verificare entrambi i percorsi commercialista, email ordinaria e PEC, con stato visibile `inviato/non inviato`;
- confrontare il file XML FatturaPA allegato dall'utente con l'XML generato da IUSENTRA;
- prima della chiusura complessiva restano necessari commit, push branch gemelli, check GitHub e deploy Hetzner come da `AGENTS.md`.

## Aggiornamento operativo - formato euro italiano - 28 giugno 2026

Richiesta utente: standardizzare in tutto IUSENTRA gli importi visibili con formato italiano e simbolo euro, escludendo i tracciati tecnici come XML FatturaPA/SdI dove lo schema impone formato macchina.

Soluzione applicata:

- creato `scripts/standardizza_formato_euro.py`, script idempotente che aggiorna sorgenti e template ma non modifica dati runtime, bundle compilati, XML FatturaPA/SdI, parser o campi tecnici valuta;
- creato `pct/formatting.py` con `format_euro_it`, `format_decimal_it` e `format_signed_euro_it`;
- registrati i filtri Jinja `euro` ed `euro_signed` in `web/bootstrap/template_runtime.py`;
- creato `frontend/src/formatting.ts` con `formatEuroIt`, `formatEuroInput` e `parseItalianAmount`, forzando il separatore delle migliaia anche sui valori a quattro cifre (`€ 1.500,00`);
- aggiornati Fatturazione, Fascicoli, Preventivi wizard, Impostazioni/Pagamenti, Tariffario, Lex e template principali per usare il formato `€ 1.234,56`;
- i campi visibili `Prezzo unitario` nel dettaglio fattura mostrano `€ 1.500,00` e `€ 125,00`, ma il payload di salvataggio viene riconvertito in numero macchina prima dell'invio API;
- `XML FatturaPA`, `Divisa=EUR`, parser OCR/regex e test privacy restano esclusi per compatibilità tecnica e schema.

Verifica reale locale eseguita:

- Docker reale locale `127.0.0.1:8080` ricostruito e healthy;
- `/api/pronto` restituisce `ok=true`, `timezone=Europe/Rome`, `versione=2.253.134`;
- browser integrato visibile su `http://127.0.0.1:8080/fatturazione/`;
- archivio fatturazione mostra `€ 2.028,20`, nessun importo monetario `EUR`;
- `Apri dettaglio` apre il modal nella stessa pagina; riepilogo `Importo: € 2.028,20`;
- input `Prezzo unitario` verificati nel modal: `€ 1.500,00` e `€ 125,00`, placeholder `€ 0,00`;
- tab `Anteprima PDF` verificato: PDF caricato nella stessa pagina con valori `€ 1.500,00`, `€ 125,00`, `€ 2.028,20`;
- tab `XML e SdI` verificato: stati XML/PEC, pulsante rapido `Inserisci impostazioni PEC`, azioni `Firma XML`, `Prepara PEC SdI`, `Registra esito`, nessun `EUR` monetario;
- tab `Commercialista` verificato: configurazione rapida, scelta email ordinaria/PEC, scelta `Solo PDF`/`PDF più XML firmato`, nessun `EUR` monetario;
- hover e focus tastiera sui pulsanti del modal verificati: testo, icone, opacità e visibilità restano leggibili;
- controllo campione su `http://127.0.0.1:8080/tariffario`: importi in formato `€`, nessun `EUR` monetario e console senza errori.

Guardrail eseguiti:

- `python scripts\standardizza_formato_euro.py` -> `modified_files=0`, `visible_eur_findings=16` solo su parser, OCR, EUR-Lex, test privacy, compatibilità zero e fonti ministeriali;
- `python -m py_compile pct\formatting.py scripts\standardizza_formato_euro.py web\bootstrap\template_runtime.py` -> OK;
- `python -m pytest tests\test_formatting.py tests\test_react_fatturazione_bridge.py tests\test_pdf_style.py -q` -> OK;
- `pnpm --filter @iusentra/studio typecheck` -> OK;
- `pnpm --filter @iusentra/studio build` -> OK;
- manifest React verificato: zero asset mancanti.

Stato ancora aperto prima di dichiarare chiusa la tranche completa:

- pulizia/staging degli asset Vite necessari al manifest finale;
- commit, push branch gemelli, controllo GitHub/CodeQL e deploy Hetzner come da `AGENTS.md`;
- eventuale estensione puntuale su altre schermate se la prova reale dell'utente evidenzia un importo residuo in formato non italiano.
## Aggiornamento operativo - date e orari italiani Europe/Rome - 28 giugno 2026

Aggiornamento post-bump `2.253.135`: Docker reale locale ricostruito con `docker compose build --no-cache app` e riavviato healthy; `/api/pronto` restituisce `ok=true`, `timezone=Europe/Rome`, `versione=2.253.135`; verifica browser integrato ripetuta su Tariffario, PEC, email ordinaria e PDF Fatturazione senza `Data UTC` o ISO raw `...Z`, con PDF parcella a `Data e ora italiana: 28/06/2026 22:04 (Europe/Rome)`.

Richiesta utente: eliminare le date/orari visibili in UTC o formato ISO raw, includendo esplicitamente PDF, PEC/email in arrivo, report e audit visibili. Il valore tecnico può restare nei tracciati, ma ciò che vede l'avvocato deve essere italiano e in `Europe/Rome`.

Soluzione applicata:

- aggiunta regola permanente in `AGENTS.md` e in `artifacts/data-flow/incarico-operativo-permanente.md`;
- esteso `pct/formatting.py` con `parse_datetime_rome`, `format_date_it`, `format_time_it` e `format_datetime_it`;
- registrati i filtri Jinja `data_it`, `dataora_it` e `ora_it`;
- creato `scripts/standardizza_date_italiane.py`, idempotente, per inserire `Europe/Rome` nei formattatori frontend e presidiare residui visibili;
- corretto il PDF parcella: la riga `Data UTC` diventa `Data e ora italiana: ... (Europe/Rome)`;
- corretto il bridge React PEC/email: le date di arrivo/invio usano `Europe/Rome` prima di produrre label come `oggi`, `ieri`, `1 giu` o orario `HH:MM`.

Verifica reale locale eseguita:

- Docker reale locale `127.0.0.1:8080` ricostruito e healthy;
- `/api/pronto` restituisce `ok=true`, `timestamp=2026-06-28T21:46:05+02:00`, `timezone=Europe/Rome`, `versione=2.253.134`;
- browser integrato visibile su `http://127.0.0.1:8080/tariffario`: nessun `Data UTC` e nessun timestamp ISO `...Z` visibile;
- browser integrato su `http://127.0.0.1:8080/fatturazione/`: `Apri dettaglio` apre il modal, senza `Data UTC` né timestamp ISO raw nel DOM;
- anteprima PDF nella stessa pagina verificata; aprendo la stessa route PDF nel viewer reale Chrome, la sezione `Tracciabilità e prove` mostra `Data e ora italiana: 28/06/2026 21:48 (Europe/Rome)`;
- browser integrato su `http://127.0.0.1:8080/email`: nessun `Data UTC`, nessun timestamp ISO raw; la lista PEC mostra date italiane brevi come `1 giu`, mentre il contenuto tecnico originale della PEC conserva l'header ricevuto;
- browser integrato su `http://127.0.0.1:8080/email-ordinaria`: nessun `Data UTC`, nessun timestamp ISO raw.

Guardrail eseguiti:

- `python scripts\standardizza_date_italiane.py` -> `modified_files=0`, `visible_datetime_findings=0`;
- `python -m py_compile pct\formatting.py scripts\standardizza_date_italiane.py web\bootstrap\template_runtime.py web\blueprints\fatturazione.py web\services\react_email_bridge.py` -> OK;
- `python -m pytest tests\test_formatting.py tests\test_pdf_style.py tests\test_react_email_datetime.py tests\test_react_fatturazione_bridge.py -q` -> OK, `16 passed`;
- `python -m pytest tests\test_web_bootstrap.py::test_template_runtime_registers_filters_and_globals -q` -> OK;
- `pnpm --filter @iusentra/studio typecheck` -> OK;
- `pnpm --filter @iusentra/studio build` -> OK.
