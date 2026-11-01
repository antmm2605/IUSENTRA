# 2.470.0 — Registro delle letture per fascicolo, pannelli del fascicolo più chiari e più leggeri

- **Registro del fascicolo** (direttiva dell'avvocato del 01/11/2026): ogni fascicolo ha una riga di sintesi nel
  registro delle letture con cliente, tipo di pratica, ufficio e RG, stato, date di apertura, definizione e
  archiviazione, prossima udienza (solo futura), documenti, PEC e allegati presenti e, per ogni motore di
  lettura, quanti oggetti ha letto, quanti restano, quanti non sono leggibili, con quale versione e quando.
  Nel fascicolo è la scheda «Registro del fascicolo» in «Letture e verifiche».
- **Ogni modifica ai documenti arriva ai motori**: aggiunta, sostituzione, rimozione, ripristino, eliminazione
  e copia nella fusione dei doppioni avvisano il registro da qualunque via (import massivo, editor, firma, CTU,
  PagoPA, portale); i motori leggono solo ciò che è nuovo o cambiato.
- **Rilettura senza giri a vuoto**: un documento letto da una versione precedente del motore si rilegge dai testi
  già salvati (OCR e indice documentale); un documento senza testo salvato conserva la lettura precedente e non
  torna «da rileggere» a ogni giro. Le versioni dichiarate compatibili non si rileggono. Il giro automatico
  completa anche i fascicoli rimasti con oggetti «da leggere» dopo il cambio di versione del motore.
- **PEC**: l'impronta del fascicolo si calcola con una sola interrogazione e senza leggere il testo OCR degli
  allegati; il motore PEC registra la propria riga (la panoramica non mostra più zero PEC lette).
- **Pannelli del fascicolo** (giro visivo del 01/11/2026 su un fascicolo reale, computer e telefono):
  - Gestione: un fascicolo definito non appare più «Aperto»; Profilo: «Ultima udienza» per una data trascorsa,
    stato del portale datato all'acquisizione, un solo conteggio dei documenti (file presenti, con quelli noti
    al portale a parte);
  - Servizi telematici: solo i servizi della materia (PCT per il civile, PDP per il penale, PAT e PTT per
    amministrativo e tributario);
  - Documenti: prima l'elenco, poi caricamento, scanner e riconoscimento del testo su richiesta;
  - Comunicazioni: la stessa ricevuta acquisita più volte si mostra una volta; documenti monitorati richiudibili;
  - Avanzamento: stati in italiano, nessun passaggio «Definito → Definito», nessuna voce ripetuta, nessun codice
    tecnico; Soggetti: le parti lette dal portale non ancora registrate sono mostrate con la loro fonte;
  - Audit e testi: «pacchetto probatorio» al posto di «bundle», nessun «catalogo SQL»;
  - gli avvisi di caricamento non coprono più il contenuto: piccolo avviso in basso.
- **Velocità**: il catalogo dei tipi di deposito (2,7 MB) solo nella pagina del deposito; la lettura iniziale del
  fascicolo (circa 140 KB) non si rispedisce a ogni sezione; le sezioni caricano solo il fascicolo aperto.
- **Deploy**: il controllo dei gate richiesti non scambia più la copia annullata di un'esecuzione per l'esito della CI
  vera ancora in corso (deploy della 2.469.0 fermato con tutta la CI verde).
