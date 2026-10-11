# Navigazione durante la compilazione — 11/10/2026

Risultato atteso: consultare le altre funzioni dal menu durante una modifica del documento, senza perdere testo, selezione, modello e contesto della bozza. La chiusura o il ricaricamento della scheda mantiene la protezione nativa delle modifiche non salvate.

## Causa e correzione candidata

Il presidio beforeunload dell’editor impediva la normale navigazione della scheda con modifiche pendenti. Il gestore condiviso delle finestre riconosceva il menu soltanto in presenza di una finestra già aperta. L’editor segnala ora la bozza pendente o il salvataggio in corso; i collegamenti del menu aprono le finestre operative native, senza smontare il documento. Nessun salvataggio implicito, nuova persistenza o ampliamento dei permessi. Gli endpoint conservano tenant e controlli server; download e azioni distruttive restano esclusi.

Il confronto con tutte le destinazioni realmente dichiarate nel menu ha individuato percorsi prima mancanti: profilo, Apprendimento Lex, recupero crediti, applicazioni, CRM, servizi telematici e altre pagine di consultazione. Guardia sulle destinazioni del menu e sui confini di origine, con esclusione di invio, eliminazione e download.

La voce della barra superiore diventa **Comandi vocali**. Catalogo delle frasi e operazioni vocali conservato.

## Riscontri materiali sulla copia reale 8080

- Candidato locale v1: Oggi e Impostazioni caricati nelle finestre native; testo controllato non salvato conservato dopo chiusura.
- Candidato v2: Profilo e Apprendimento Lex caricati; ritorno alla stessa bozza, testo conservato. Apertura del pannello Comandi vocali, 390 frasi e 59 destinazioni; nessun microfono o comando operativo attivato.
- Primo tentativo sui servizi telematici dopo ampliamento dei percorsi non apriva la finestra: l’immagine conteneva sorgenti nuovi e asset ancora precedenti. Ripetuta la compilazione Vite prima della build Docker.
- Candidato v4: Centro Servizi Telematici caricato in finestra, affiancamento a destra osservato, ritorno al testo controllato integrale. Foto privata editor-navigation-services-draft.png.
- Mobile 390×844: apertura menu e Oggi dalla bozza, piano caricato; scroll fino a Backlog, chiusura e stesso testo conservato. La prova non comporta firme, depositi o invii.
- Tablet 820×1080: Profilo caricato dal menu, scroll fino ai controlli 2FA, chiusura tramite tastiera e bozza integrale conservata. Dimensioni del browser ripristinate dopo la prova.

Selezione del modello condiviso riscontrata nel catalogo locale; questo studio tecnico non contiene un fascicolo da associare. La ripetizione su modello compilato con dati del fascicolo Anastasi richiede l’accesso locale corrente allo studio proprietario: vecchia credenziale documentata rifiutata, nessuna password cambiata o autorizzazione ampliata. Richiesta di accesso presentata all’utente; altre attività proseguono.

## Guardrail e stato

Sei guardrail JavaScript della navigazione positivi, typecheck workspace positivo, controllo vocale positivo. Build finale dei percorsi del candidato v4 in 2,99 secondi. La modifica non esegue letture documentali, nuovi job o scritture SQL.

Restano verifica sul modello compilato, preparazione della versione, controlli di rilascio, commit/push dei branch autorizzati, riallineamento locale esatto e deploy. Il punto e l’incarico generale restano aperti.

## Precedente rilascio caricamenti

Commit e22cbdf976894c634f8f7b4865d0420f137364ec: controlli richiesti positivi, deploy 38155426694 concluso. Verifica diretta Hetzner: repository pulito, stesso SHA nell’immagine, unica iusentra-app healthy, scheduler/OCR healthy sullo stesso SHA, readiness pubblica 2.437.9 Europe/Rome. Cleanup nativo concluso: una immagine conservata, cache di build ripulita e snapshot temporaneo assente. La copia locale è ora un candidato di navigazione, quindi non è presentata come installazione esatta definitiva del nuovo punto.

Primo controllo Compose senza il file ambiente è stato rifiutato prima di operare; ripetuto usando /opt/iusentra/.env.hetzner. Primo controllo dell’etichetta immagine aveva quoting non valido; ripetuto con sole etichette JSON, SHA confermato.

CI coverage parte 8: prima esecuzione scaduta a 300 secondi senza errore di asserzione; riesecuzione nativa dello stesso job conclusa positivamente. Diagnosi Windows locale: 106 test positivi, un errore del percorso bash e quattro errori di chiusura SQLite nei fixture, distinti dall’esito CI Linux. Nessun test escluso o limite attenuato. Questi problemi del canale di test locale restano registrati e non diventano prove positive.

Ulteriore prova materiale: creato il fascicolo tecnico 7ADAFE03 dal modulo normale. Nel nuovo editor selezionato il modello condiviso, preparato e applicato con quel fascicolo. Cliente Controllato Caso visibile; dati non presenti lasciati come segnaposto. Apertura Oggi dal menu e ritorno: testo del modello integralmente conservato, stessa pagina e nessun salvataggio implicito. Foto privata editor-compiled-model-navigation-preserved.png. Questa prova dimostra la navigazione con modello compilato, non la risoluzione delle discordanze del fascicolo Anastasi.
