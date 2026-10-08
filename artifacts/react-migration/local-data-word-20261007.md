# Lettura locale e conversione Word — lavoro aperto

Data: 07/10/2026, ora italiana. Accettazione sulla copia reale `127.0.0.1:8080`.

## Dati locali

Il database SQLite del tenant registrato aveva una corruzione nella tabella dei
record dei moduli. Prima dell'intervento sono stati fermati tutti i processi
scriventi e conservati snapshot verificati fuori dal repository. La ricostruzione
ha mantenuto integralmente le 125 tabelle leggibili, schema, rowid, sequenze,
indici, trigger e tabelle virtuali. Nessuna sostituzione con database remoto.

La fonte dei record ricostruiti è SQL: recupero SQLite, snapshot SQL storici,
repository verticali locali e un campo verificato nel database SQL di produzione.
I mirror JSON sono stati usati per confronti, non come fonte per riparazioni massive.
Il nuovo strumento `tools/repair_sqlite_module_table.py` produce solo un candidato
offline e un rapporto; non può installarlo sul database operativo.

Applicata la migrazione nativa delle caselle con piano verificato e backup:
2.092 record ordinari e 218 PEC. Sedici nuove acquisizioni PEC hanno un originale
con impronta verificata. Nessun cambio massivo dello stato di lettura.

Nel browser reale: casella PEC con elenco, conteggi e dettaglio; casella ordinaria
con 2.092 messaggi, apertura del messaggio controllato, contenuto completo e data
italiana. L'apertura ha aggiornato automaticamente lo stato a letto e il conteggio
da 1.578 a 1.577; il filtro Lette nella cartella In arrivo ha restituito quel
messaggio. App, scheduler e worker OCR healthy.

Restano aperti: un record storico redazionale con JSON danneggiato, conservato
senza cancellazioni; moduli storici incompleti dichiarati nel rapporto di recupero;
quattro riferimenti orfani preesistenti conservati; verifica dei tempi iniziali
PEC e della decodifica di alcuni testi. Non dichiarata recovery integrale.

## Word

Aggiunto percorso dedicato PDF in Word negli strumenti documentali, con API
autenticata, permessi, audit, originale conservato e copia temporanea cifrata
isolata per studio e utente. Processo di conversione separato con timeout.
Il risultato è un DOCX modificabile; l'anteprima è la resa del DOCX effettivamente
generato, non una copia del PDF originale. Correzioni misurate per larghezza
delle tabelle, spessore dei bordi e posizione verticale delle linee abbinabili.

Prova materiale già eseguita nel browser autentico sulla Docker reale: selezione
del PDF controllato di due pagine, conversione, stato loading, risultato,
Visualizza, scroll fino alla seconda pagina e al fondo, chiusura, download DOCX
in Downloads. Confrontati visivamente tutti i fogli del campione renderizzato.
Build Vite e typecheck positivi, come guardrail tecnici.

Limiti attuali da completare prima dell'accettazione: scansioni non ancora
convertite da questo percorso; corpus complesso, font incorporati, immagini,
impaginazioni multiple, stati hover/focus e responsive da collaudare. Nessuna
garanzia di identità universale ricavata dal solo campione. Il limite interattivo
attuale è 100 pagine. Il renderer usa un profilo Writer privato per operazione.

Il codice corrente è WIP nella copia locale: commit/push gemelli, CI completa,
rilascio locale sul nuovo commit e deploy Hetzner ancora da eseguire dopo le
correzioni e le prove richieste. Il flusso congelato deposito/firma/invio PEC
non è stato modificato.

## Prove successive del 07/10/2026 — lavoro ancora aperto

SQL locale: `quick_check=ok`; confronto identificativi del piano PEC recuperato
con la tabella nativa: tutte le 218 PEC presenti, zero mancanti, 13 nuove
acquisizioni (231 record PEC). Posta ordinaria: 2.092 record nativi.
Nessun dato è stato cancellato per correggere un conteggio.

PEC «prova 7»: aperta materialmente nel browser locale; il corpo HTML originale
mostra «è stato inviato» correttamente e quattro allegati. La selezione della
versione MIME segue RFC 2046. Neutralizzato lo stato del dettaglio precedente
quando cambia il messaggio selezionato; nuova prova di questa transizione aperta.

Esportazione OCR versione intermedia v3: prova reale negativa, PDF controllato
di due pagine diventato Word di quattro, font e bordi persi. Non accettata.
Il percorso nativo successivo usa il PDF originale e conserva struttura e
grafica; una revisione è applicata sul DOCX prima della resa di controllo.

Prova reale v4: upload/lettura/salvataggio/download da Strumenti Forensi nella
Docker autentica su 8080; Word scaricato di due pagine. Renderizzati e osservati
tutti i fogli: famiglie, corpi, corsivo, colore, tabella e numeri di pagina.
Prova reale v6: correzione «Societa, attivita» in «Società, attività» sulla sola
prima pagina, download reale, render di entrambe le pagine; correzione presente,
seconda pagina conservata, tabelle e formati conservati. Individuato lieve scarto
verticale del testo modificato; taratura v7 preparata, prova materiale da ripetere.

Gli artefatti dei download e delle rese sono nel backup privato fuori Git,
`consolidamento-20261007/word-browser`. Build e typecheck dopo la revisione:
positivi; Vite 3,63 s. Restano aperti export delle scansioni, revisioni strutturali
e formati complessi, corpus esteso, prove responsive/hover/focus, recupero storico
residuo e consolidamento dei gate/release. Nessuna consegna finale dichiarata.

Prova reale v7 ripetuta dopo taratura: Word di due pagine, correzione degli
accenti sulla sola prima pagina nella posizione originale; entrambi i fogli
renderizzati e osservati. Regressione PEC introdotta nell'anteprima individuata
materialmente e corretta (riferimento `email_obj` fuori contesto); prova v8 con
click Riprova: 231 messaggi, 128 in arrivo, anteprima «è stato inviato» leggibile.
Il passaggio da ACCETTAZIONE a prova 7 mostra il nuovo messaggio in loading
senza il profilo precedente. Corpo completo verificato, quattro allegati
visibili, XML aperto con click nel lettore interno e contenuto fino al tag finale.
Salvate prove visive della lettura nella cartella privata `word-browser`.

## Prove materiali successive v9–v14 — incarico aperto

Scansione controllata `01-sans.png`: upload, lettura, salvataggio e download
materiali su 8080. v9 non accettata (tema Word applicato ai titoli, margini
alterati); v10 non accettata (corpo predefinito e righe sovrapposte). Individuato
il ritaglio improprio dei margini bianchi nella preparazione OCR; il foglio
bianco ora resta intero. v11 osservata interamente: una pagina, margini e
posizioni conservati, sovrapposizioni eliminate. Il corpo assente nella
scansione è stimato dai riquadri; non è una prova di identità del carattere.
Persistono differenze di famiglia/stile e letture errate di simboli nel corpus:
non dichiarare identica la conversione delle scansioni.

v12: controllo della resa Word contro testo perso e contenuti fuori pagina;
download reale della scansione consentito dopo questo controllo. PDF nativo:
comando Centra sul primo capoverso, download reale, entrambe le pagine
renderizzate e osservate. Centrato solo il capoverso scelto sulla prima pagina;
seconda pagina, tabelle e formati restano presenti.

v13: prima correzione del clic Salva negativa sul successivo clic Conferma;
nessun errore di conversione, comando perso durante il blur della revisione.
v14: chiusura esplicita dell'editing prima di aprire la conferma. Prova materiale
ripetuta: modifica accenti, un clic Salva, un clic Conferma, download effettivo
`originale-layout - testo riconosciuto (8).docx`; entrambe le pagine osservate
con correzione sulla sola prima, font, corpi, colori, tabella e piè di pagina.
Artefatti fuori Git in `consolidamento-20261007/word-browser`.

Guardrail tecnici: 81 test OCR/export/revisione Word passati dopo riallineamento
di due aspettative obsolete (testo nativo conservato; corpo inline consentito).
20 test email/revisione/margini/recupero SQL passati; Ruff sui file mirati
positivo. Build/typecheck v14 positivo. Non sono accettazione dell'intero prodotto.

SQL reale ricontrollato in sola lettura: quick_check=ok, posta ordinaria 2092,
PEC 231, un payload storico redaction_assistant ancora invalido. Non è stato
rimosso né sostituito con testo inventato. Produzione e GitHub non ancora
riallineati a questo WIP; CI completa, deploy e verifiche ulteriori aperti.

## Prove materiali v17–v22 e libreria font — incarico aperto

Posta ordinaria: ricerca reale del messaggio storico SQL recuperato, apertura
nel lettore interno, destinatari, corpo e data italiana osservati. Alla chiusura
il numero delle non lette passa automaticamente da 1577 a 1576. Corretta
l'etichetta MIME assente: il corpo grafico salvato resta disponibile e non viene
chiamato impropriamente PEC. Guardrail email: 14 passati.

v18–v19: PDF controllato di due pagine con cinque stili nella stessa frase;
il blocco OCR raggruppa due paragrafi Word. Prima prova rifiutata, causa
corretta nella corrispondenza dei paragrafi; download reale con correzione
di un carattere sulla prima pagina. Entrambe le pagine renderizzate e osservate:
grassetto, corsivo, monospace, blu, corpi diversi e seconda pagina conservati.
Ripetuto il download dopo Carattere del documento, Corpo del documento e
ripristino del colore; stessi stili originali osservati. 32 guardrail strumenti
e revisione passati dopo correzione dell'inserimento in fondo a una cella.

Estensione richiesta dall'utente: Word 2021 rilevato sul PC; 376 file TTF/TTC
installati. I file Windows non sono stati copiati nel software o sul server:
le condizioni Microsoft distinguono uso locale, incorporamento documentale
e redistribuzione. Aggiunti al Dockerfile Noto core/extra/mono/CJK e URW;
installati nella copia 8080, 228 famiglie effettive (prima 21).
Non confondere queste famiglie con la disponibilità di tutti i font Microsoft.

Il nuovo servizio document_word_fonts usa i font incorporati nel PDF soltanto
nel documento e nel render privato, senza libreria globale o invii esterni.
Controlla OS/2 fsType, esclude restricted/preview-only/bitmap-only e subset
non consentiti, verifica cmap e glifi richiesti, incorpora in Word con fontKey
e parti ODTTF. I font non recuperabili restano un problema aperto, non una
prova di identità. v20 (PDF con cmap non Unicode) non ha incorporato i font;
la resa usava caratteri metricamente compatibili: prova non accettata come
identica. Il caso richiede ulteriore gestione della mappatura originale.

v21: upload/lettura/download reali su 8080 del PDF controllato con Arial,
Arial grassetto, Times New Roman e Calibri completi. Quattro font originali
incorporati nel DOCX. Render del download con profilo indipendente: entrambi
i fogli osservati e confrontati con gli originali, stessi font, corpi, margini
e posizioni. v22: selezione reale dei cinque caratteri «Arial», Sottolineato,
Salva e Conferma; primo controllo testo negativo per normalizzazione Unicode
non uniforme nella revisione, causa corretta. Secondo download reale positivo:
solo la parola selezionata è sottolineata sulla prima pagina, seconda intatta;
quattro font originali ancora presenti. Guardrail font/revisione: 10 passati.

FontTools 4.66.1 reso dipendenza esplicita tramite sync_packaging_files.
Artefatti e screenshot privati nel backup word-browser. Il container attivo
contiene le modifiche in verifica; immagine riproducibile, CI/release e deploy
restano da consolidare. Scansioni, font parziali/assenti e storico SQL residuo
mantengono formalmente aperto l'incarico.

Fonti primarie: Microsoft Font redistribution FAQ,
https://learn.microsoft.com/en-us/typography/fonts/font-faq ; OpenType OS/2
fsType, https://learn.microsoft.com/en-us/typography/opentype/spec/os2 ; OpenXML
embedRegular, https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.embedregularfont ;
Debian Noto core, https://packages.debian.org/bookworm/fonts-noto-core .

## Licenze dei caratteri: riscontro ufficiale e perimetro operativo — 07/10/2026

La richiesta dell’utente comprende uso dei caratteri in tutti gli editor, conversione
PDF/Word, anteprime, esportazioni e funzionamento locale e SaaS. Sono diritti
separati: la presenza del file sul PC, un acquisto desktop o il solo flag fsType
non autorizzano la distribuzione del font dall’applicazione.

Fonti primarie consultate:

- Microsoft, uso Windows, CSS locale, incorporamento documentale e diritti estesi:
  https://learn.microsoft.com/en-us/typography/fonts/font-faq
- OpenType, flag di incorporamento OS/2:
  https://learn.microsoft.com/en-us/typography/opentype/spec/os2#fstype
- Monotype, categorie server, applicazione e SaaS:
  https://www.monotype.com/font-licensing-explained-designers-and-brands
- Monotype, termini contrattuali, inclusa esclusione dell’authoring dal normale
  diritto Web Page Content:
  https://www.monotype.com/terms-and-conditions
- Microsoft Graph, conversione ufficiale DOC/DOCX in PDF:
  https://learn.microsoft.com/en-us/graph/api/driveitem-get-content-format?view=graph-rest-1.0

Decisione operativa: non acquistare una generica licenza web pensando che copra
un elaboratore di testi SaaS. L’accordo da ottenere dal titolare deve nominare
espressamente IUSENTRA, gli editor per gli studi, caricamento del font nel browser,
installazione nei container locali e Hetzner, generazione automatizzata di PDF e
Word modificabili, incorporamento nel documento, varianti, utenti/tenant,
redistribuzione Docker/on-premise e ogni eventuale trasformazione tecnica. Verificare
per ciascuna famiglia titolare, versioni e stili effettivamente coperti. Le FAQ
Microsoft escludono Segoe UI Variable dall’uso fuori dai prodotti Microsoft o su
piattaforme non Windows: non promettere una licenza universale per tutti i font.
Nessun contratto accettato, ordine, pagamento o richiesta commerciale inviati.

Percorsi primari distinti:

1. I font già installati sul dispositivo Windows possono essere richiamati dal
   browser con CSS locale, senza trasferire i file sul server. Questo non dimostra
   che il render Linux o il PC di un altro avvocato li possiedano.
2. I font incorporati nella fonte restano nel documento e nel suo render privato,
   secondo i diritti documentali verificati. Non diventano la libreria globale.
3. I font distribuibili con licenze aperte possono entrare nel catalogo condiviso,
   mantenendo avvisi, attribuzioni e testo della licenza.
4. Le famiglie proprietarie globali richiedono il contratto SaaS/authoring e server
   pertinente. Il registro dei diritti deve derivare dall’accordo effettivo,
   non da un flag dichiarato dall’utente o dalla semplice installazione di Office.
5. Graph è un canale ufficiale per Word verso PDF, non fornisce la libreria di font
   da distribuire e non offre PDF verso DOCX nell’endpoint consultato. Nessun
   documento dello studio è stato inviato a Microsoft per questa verifica.

Inventario materiale del PC, sola lettura: 376 file TTF/TTC, 399 facce, 201 famiglie,
zero errori dopo corretta lettura delle collezioni TTC. Arial, Times New Roman,
Calibri e Cambria mostrano fsType=8 nelle varianti rilevate: permesso tecnico di
incorporamento modificabile, non attestazione di diritto di redistribuzione.
Aptos non presente nell’inventario Windows; Segoe UI Variable presente. Il dettaglio
privato con titolare, copyright, URL e descrizione licenza è in
`D:/legale/backups/IUSENTRA/controllo-studio-20261005/consolidamento-20261007/font-licenses-local-inventory.json`.
Nessun file di font del PC è stato copiato nella libreria globale/server.

Prova tecnica aggiuntiva v23: browser reale autenticato su porta 8080, lettura del
PDF controllato `font-word-subset.pdf`, Salva sul computer, Conferma e download
Word. Render indipendente del DOCX: due pagine, Arial/Arial Bold/Times New Roman/
Calibri originali, testi italiani e simboli presenti. Entrambe le pagine renderizzate
sono state osservate. La ricostruzione della mappa Unicode del font parziale è
una modifica tecnica da valutare rispetto ai diritti della fonte: l’esito tecnico
non costituisce autorizzazione contrattuale, né autorizza l’esposizione del font
come risorsa globale. Occorre mantenere distinta questa verifica dalla licenza
commerciale del catalogo condiviso. L’incarico complessivo resta formalmente aperto.

## Verifica strutturale e confronto condiviso — 07/10/2026, lavoro aperto

Registrata in AGENTS.md la direttiva di verifica visiva autonoma, estesa a stili,
elenchi anche annidati, tabelle, caselle, immagini, intestazioni, piè, colonne e
cambi di pagina, con modifica, salvataggio e riapertura.

Fascicolo e Strumenti condividono ora OcrConfronto e il servizio ocrDocumento:
lettura ordinata con due richieste concorrenti, interruzione, geometrie, confronto,
schermo intero e scelta del convertitore. Le azioni di destinazione restano nel
contesto di appartenenza. La prova precedente con font-word-subset.pdf ha percorso
entrambi i pannelli nei due contesti, fino al fondo; non è accettazione dell'intero
perimetro strutturale o responsive.

Documento controllato privato stili-completi-v24.pdf: due pagine native, normale,
grassetto, corsivo, grassetto-corsivo, sottolineato, barrato, decorazioni combinate,
colore e corpi 9/12/16/18 pt. Upload, confronto reale e download da porta 8080;
entrambe le pagine del Word scaricato sono state renderizzate e osservate.
Persistono differenze di baseline/spaziatura: nessuna attestazione di identità.

Documento strutture-complete-v25.pdf: tre pagine con puntati, numerati, annidati,
lettere e romani; tabella a tre colonne; casella con sfondo e bordo; immagine
incorporata; pagina orizzontale con due colonne e piè. Il browser reale ha mostrato
inizialmente assenza di immagini/bordi/sfondi, rientri errati e colonne spezzate.
La rappresentazione nativa ora conserva la grafica in un fondo privato privo di
testo (copia PyMuPDF, mai modifica dell'originale), sovrappone testo modificabile
nelle coordinate native e usa dimensioni fisiche e orientamento della fonte.
Scorrimento completo materiale nei due versi; visti elenchi, tabella, casella,
immagine, pagina orizzontale e piè. Restano differenze visibili delle metriche
tipografiche e il perimetro scansioni non usa questo fondo nativo.

Il primo export reale v25 è stato correttamente bloccato dal controllo: il Word
aveva quattro pagine e spostava colonna e piè. Diagnosi sul DOCX effettivo e sul
parser: NEW_COLUMN produceva una sezione aggiuntiva, con bilanciamento errato e
righe concatenate. Il worker isolato ora ancora le colonne native di solo testo
alla pagina e conserva il passo uniforme in punti. Download materiale successivo:
tre pagine; render indipendente del file scaricato, tutte e tre osservate.
Provati correzione Registrato → Verificato e grassetto nella cella, salvataggio e
render del Word scaricato: testo e grassetto presenti, struttura e immagine
conservate. Quest'ultima prova ha individuato una regressione di spaziatura nella
casella: la taratura delle righe è stata quindi limitata ai blocchi delle colonne.
Questa ultima restrizione deve essere nuovamente provata dal browser reale.

Guardrail tecnico aggiunto: conservazione di casella e immagine nel fondo, testo
rimosso senza modificare l'originale. 10 test native_fidelity passati sul Python
locale; pytest assente nel container applicativo. Typecheck/build passati; statici
e servizi aggiornati nel container locale unico iusentra-app e riavvio eseguito,
health osservata. Nessun commit, push o deploy di questa tranche ancora aperta.

Restano necessari: prova strutturale completa nel fascicolo con codice corrente,
prove scansioni e casi complessi (celle unite, immagini flottanti, apici/pedici,
rotazioni), stili/azioni hover e focus, responsive, correzione delle differenze
misurate, verifiche dopo le ultime modifiche, catalogo font governato, dati locali
ancora presidiati, consolidamento e riallineamento GitHub/locale/Hetzner.

### Prosecuzione materiale: righe native e Word strutturale — 07/10/2026

Riletta AGENTS.md; regola visiva già applicata e registrata. Aggiunti offset
verticali per ciascuna riga nativa, conservati soltanto finché il testo coincide
con l'originale; non sono inventati per letture ottiche. Nel browser reale 8080
riletti e scorsi completamente tutti e tre i fogli v25 con bundle corrente:
elenco, tabella, casella, immagine, colonne e piè. La casella non accumula più
la differenza di passo tra le sue tre righe; rimangono differenze delle metriche
orizzontali del carattere nell'anteprima. Test mirato native_fidelity: 11 passati.

Nuovi download reali v25 (2), (3), (4), (5). La prova (4) ha trovato scostamenti
nelle ultime voci dell'elenco dopo la trasformazione dell'interlinea automatica.
Nel worker privato l'interlinea è ora fissata prima della misura, per impedire che
w:position ridimensioni i capoversi. Abbinamento sempre per testo, occorrenza,
pagina e corpo; nessuna modifica a testo o originale. La prova (5), scaricata
materialmente dal browser, è stata renderizzata indipendentemente: tutte le tre
pagine osservate, nessun foglio aggiuntivo, font/stili/testo preservati. Sulle
righe abbinabili del campione, massimo scostamento verticale osservato 0,31 pt.
Questo NON certifica identità: la geometria di bordi/disegni risente ancora del
flusso Word e va corretta/verificata, così come font browser e casi complessi.
La restrizione della taratura alle colonne del worker è stata riprovata realmente.

Riconoscimento/esportazione del campione stili v24 avviato nuovamente dopo queste
modifiche per verifica di non regressione. Lavoro formalmente aperto; nessun
commit/push/deploy di questa fase. File di prova e documenti scaricati conservati
nella cartella privata di backup, mai nel repository o nei dati reali dello studio.

Ultima conversione materiale dal fascicolo (download v25 numero 6): la misura
in punti ora usa anche le metriche hhea dei font incorporati della fonte, invece
di assumere che corpo e altezza di riga coincidano. Render indipendente di tre
pagine e confronto quantitativo: scostamento delle baseline abbinabili entro
0,29 pt; bordo tabella circa 0,42 pt rispetto alla fonte. Non è certificazione
di identità arbitraria. Il download precedente v24 con tutti gli stili è stato
renderizzato e tutte e due le pagine osservate, con B/I/U/barrato, combinazioni,
colore e corpi misti leggibili.

Prova reale nel fascicolo ha individuato un menu Salva tagliato. OcrSaveChoices
ora contiene altezza/scroll e decide sopra/sotto tenendo conto della navigazione
fissa del fascicolo; summary esposto come pulsante, focus evidente, Escape
riporta al comando. Prima correzione visualizzata: menu sopra ancora sotto la
barra fissa; affinata la misura del bordo alto. La verifica materiale dell'ultima
versione del menu è ancora in corso, non costituisce accettazione positiva.
