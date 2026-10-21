# Patch 2.446.0 — integrazione controllata

Archivio: E:/patch-2.446.0.zip.

SHA-256 verificata dell’archivio: `371fbceb34f3f89db654339cd379ae5cdede46b816e8b4f39337c35698926948`.

## Perimetro

La serie contiene le patch precedenti già integrate. Applicata la modifica 0013, conservando aggiornamenti di sicurezza e WIP offline/PEC fuori dal rilascio.

EXTRACTED: schede JSON e generatori dichiarano il termine; pct/schede_compilazione.py risolve i campi; pct/schede_termini.py riusa ItalianDeadlineCalculator; pct/template_atti_lex_deadlines.py trasmette le scadenze alla risposta Lex. La guida React esistente mostra domande e provenienza. Le nuove funzioni decisione/messaggio_blocco sono utilità importabili: la loro presenza non dimostra l’applicazione della decisione a ogni percorso runtime Lex.

## Correzioni rispetto all’archivio

Non applicata la regressione SOC_005: sospensione feriale e proroga civile già verificate restano conservate (Tribunale Roma 6452/2017, https://www.ilcaso.it/giurisprudenza/archivio/19100.pdf).
Non estesa automaticamente l’esclusione del sabato ai ricorsi giudiziali LAV_003 e LAV_013: preservato il comportamento precedente, distinto dall’impugnazione stragiudiziale. Il testo della decisione Vasto 86/2025 rinvenuto su https://www.doctrine.it/decisions/ittribi0sj0966ot3yyi2 segnala proprio l’applicazione della proroga al deposito giudiziale. Il successivo accesso richiede autenticazione; non è assunto come verifica globale delle altre fattispecie.

## Riscontri eseguiti

46 test mirati: schede, risposta Lex e motore dei termini; lint dei moduli modificati e controllo packaging passati. Build Vite del candidato senza WIP; provenienza verificata su 750 sorgenti e 294 asset. Nell’immagine locale confrontati 320 file, nessuna discordanza.

Copia reale Docker 127.0.0.1:8080 aggiornata a 2.446.0, /api/pronto ok. Browser reale: ricerca “licenziamento”, apertura LAV_003, pulsante Come si compila, espansione Provenienza di ogni dato e scorrimento. Visibili la distinzione fra termine stragiudiziale e deposito del ricorso, fonti e dati mancanti. In seguito create soltanto bozze controllate nel fascicolo di collaudo; nessuna firma, notifica o deposito inviato. Questo riscontro non certifica la nuova decisione nei percorsi Lex non ancora collegati né il lavoro offline.

Server: rimossi soltanto 78 record cache immutabili, non condivisi e inutilizzati, discendenti dai layer IUSENTRA identificati. Procedura governata sotto deploy.lock; nessuna immagine attiva o di ripristino rimossa. Spazio fisico libero da 24.761.470.976 a 40.628.957.184 byte. Dati, volumi e backup conservati. Esito pulizia zero, servizi sani.

Commit, CI remota, deploy e verifica finale saranno registrati dopo l’esecuzione. Il lavoro offline e la sincronizzazione PC-online restano aperti e separati.

## Compilazione ed editor: verifica successiva

EXTRACTED: `TemplateCompilerView` carica i campi e sostituisce i segnaposto visibili; `ProfessionalTemplateEditorWorkspace.focusDocumentField` seleziona il testo narrativo nel corpo. `buildGuideFormData` trasmette HTML e layout alla route `compila_guida_pratica_salva`, che usa `_compiled_editor_html_builder` e il servizio nativo `create_editor_draft`. Il repository fascicoli conserva il documento cifrato; l’editor professionale lo riapre dal documento collegato. I riferimenti sono i simboli nei sorgenti modificati, non una prova autonoma di funzionamento.

Difetti osservati e corretti: GET del compilatore tentava la scrittura del registro analisi e falliva; errore API presentato come documento vuoto; valori collegati non risolti nel corpo; spaziatore iniziale generato durante una transizione CSS della geometria; avvocato indicato genericamente; salvataggio che scartava l’HTML ricevuto. La consultazione non produce più analisi scritte; i POST mantengono l’audit. Le geometrie fisiche della pagina non vengono interpolate e i riferimenti della paginazione vengono aggiornati dopo il commit CSS.

Prova reale 8080: selezionati cliente e fascicolo di collaudo; scritti fatti, argomentazioni e conclusioni tramite i comandi «Scrivi nell’atto»; modificato il titolo; salvato e riaperto il documento dal fascicolo. Confermati testo e nome del difensore; la prima riapertura ha dimostrato la perdita di formattazione, quindi non è stata accettata come esito finale. Corretto il percorso per conservare HTML sanitizzato e attributi pagina già riconosciuti dal lettore nativo. Verifica finale di questa correzione ancora in corso.

Confronto produzione: consultati in sola lettura i metadati SQL e gli originali di un ricorso di otto pagine e una procura di una pagina. Esaminate prima/ultima pagina del ricorso e procura. Il ricorso usa principalmente Times New Roman 12, con titoli distinti, intestazione ripetuta e firma finale; la procura ha una propria struttura e un originale scansito. Non è dimostrata identità globale fra i modelli del compilatore e tutti gli atti di produzione. Gli esempi e le immagini private restano fuori dal repository e dal grafo Graphify. Non vengono ricopiati recapiti storici, firme o dati delle parti nei modelli.

Ulteriore pulizia governata server: 40 record cache builder di proprietà IUSENTRA, immutabili, non condivisi e inutilizzati; spazio libero finale 42.058.657.792 byte, servizi sani e backup invariati. Occorre nuova misura prima del backup/deploy.
