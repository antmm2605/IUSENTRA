# Catalogo template atti - Suite professionale

La pagina `/template-atti/catalogo` integra la Suite professionale completa nella stessa superficie del catalogo esistente. Non esiste una pagina o un tab separato `Master professionale`: i 192 modelli operativi del compilatore restano la sorgente primaria per la compilazione reale, mentre il catalogo master v1.2.0 da 420 template alimenta classificazione, filtri, controlli, precompilazione, timbro studio e template repository.

## Dati governati

- Versione suite: `v1.2.0`
- Modelli operativi compilatore: `192`
- Template master: `420`
- Totale card catalogo: `612`
- Moduli professionali: `22`
- Canali telematici governati: `7`
- Sorgente master: `pct/template_atti_catalogo_data/catalogo_master.json`
- Sorgente operativa: `pct.compilatore_atti.MODELS`
- Split catalogo: `core.json`, `advanced.json`, `specialist.json`, `studio_interno.json`
- Ruleset Cartabia: `pct/template_cartabia_rules.py`
- Resolver precompilazione: `pct/template_atti_prefill.py`
- Timbro studio: `pct/studio_timbro.py`

## Superficie utente

La pagina mostra un riepilogo professionale, anteprima del timbro studio, gruppi suite, ricerca libera, chip rapidi e filtri combinabili per materia, area, macro-area, sottobranca, procedimento, rito, fase, tipologia atto, categoria suite, canale, portale, stato, stato Cartabia, area processuale, dati precompilabili, firma digitale, PDF/A, DatiAtto.xml, allegati, contributo, marca e controlli completi.

Ogni card template espone codice, titolo, sorgente, categoria suite, materia, procedimento, rito, fase, canale/portale deposito, stato Cartabia, precompilabilita', richiesta di verifica avvocato, controlli deposito disponibili, allegati obbligatori, dati obbligatori e azioni `Compila`, `Anteprima`, `Verifica deposito`, `Dettagli normativa`, `Duplica` quando applicabile.

I modelli con sorgente `compilatore` aprono sempre `/template-atti/compila/<codice>`. Anche i 420 template master aprono lo stesso flusso reale: quando esiste un binding esatto viene usato quello, altrimenti il sistema assegna un modello operativo del compilatore in base a canale telematico, modulo professionale e titolo dell'atto. Nessun master deve restare scollegato dalla logica compilatore funzionante.

## Controlli deposito

Le regole vivono in `pct/template_deposit_rules.py` e sono versionate con:

- fonte normativa o fonte configurabile;
- versione regola;
- data ultimo aggiornamento;
- severita;
- blocco deposito;
- messaggio utente;
- suggerimento correzione.

I canali gestiti sono PST/PCT Civile, SIGP/Giudice di Pace, PAT/SIGA, PTT/SIGIT, PDP Penale, PEC/Stragiudiziale e Atti interni studio.

## Endpoint

- `GET /template-atti/catalogo/data`
- `GET /template-atti/catalogo/filters`
- `GET /template-atti/<codice>/compliance`
- `POST /template-atti/<codice>/verifica-deposito`

Gli endpoint rispettano l'autenticazione esistente e non modificano i template master.

## Limite professionale

IUSENTRA non dichiara un atto "100% conforme" con un badge statico. La UI mostra stato, dati disponibili, dati mancanti, controlli bloccanti e controlli consigliati. Quando il catalogo o i dati del fascicolo non permettono una verifica automatica certa, lo stato resta `cartabia_review_required` o `needs_review` e la revisione dell'avvocato rimane necessaria.

## Editor professionale 2.249.13

Dal 4 giugno 2026 la compilazione `/template-atti/compila/<codice>` espone un workspace React professionale integrato con la Guida Pratica: catalogo laterale dei template, toolbar documento, pagina A4 centrale, pannello `Campi`, `Stile`, `Lex`, `Fonti`, `Controlli` ed `Export`.

Il registry font è versionato in `template_atti/font_registry.json` e copre famiglie classiche, moderne, giudiziarie, contrattuali, privacy e placeholder. Il layout salvato in `template_atti/template_atti/editor_layout.json` include font documento, titoli, interfaccia, placeholder, fallback export, preset stile, dimensioni, margini, spaziatura firma e opzione per pulire i placeholder in export.

Lex è integrato come assistente redazionale locale con modalità `Correttore`, `Redattore`, `Revisore Normativo`, `Revisore Privacy`, `Template Builder` e `Final Check`. Ogni proposta resta in diff accettabile, rifiutabile o modificabile; l'editor mantiene un registro visibile delle decisioni e non applica modifiche senza conferma dell'avvocato. L'invio a servizi esterni resta vietato finché non è presente una policy privacy esplicita.

I formati presidiati sono DOCX/PDF/RTF/TXT in importazione e DOCX/PDF/RTF in export. L'RTF viene generato localmente dal browser usando il fallback font previsto dal registry; PDF e documento compatibile Word continuano a passare dai percorsi server esistenti con layout normalizzato.

La verifica reale del 4 giugno 2026 su Docker locale `http://127.0.0.1:8080/template-atti/compila/CIV_COM_001` ha confermato desktop, tablet e mobile con scroll completo, nessun overflow, nessun errore console, data italiana `4 giugno 2026`, import TXT, salvataggio, rigenerazione, export RTF/DOCX/PDF, copia documento, topbar, campi, stile, Guida Pratica, controlli e Lex. Lex non applica modifiche prima dell'accettazione: il browser ha creato proposte in diff, accettato, rifiutato, modificato e applicato solo su comando esplicito. Report: `artifacts/react-migration/template-editor-browser-2.249.13.json`.
