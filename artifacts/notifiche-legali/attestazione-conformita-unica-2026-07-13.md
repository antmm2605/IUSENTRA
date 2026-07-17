# Attestazione di conformità unica - audit 13/07/2026

## Obiettivo verificato

L'attestazione di conformità della notifica deve essere una sola e deve comprendere tutte e sole le copie selezionate dall'avvocato. La selezione dei documenti resta manuale; il software propone i documenti del fascicolo ma non li include automaticamente. Originali informatici e documenti già firmati non vengono dichiarati copie conformi se la loro origine non richiede attestazione.

## Modello e fedeltà grafica

- Modello ricevuto: `D:\marco non codex ad utilizzare\attestazione\Attestazione di conformità.docx`.
- Modello applicativo: `pct/data/templates/attestazione_conformita.docx`.
- SHA-256 di entrambi: `81D16BD3669B2975BE76DF73F7C66DC8C98E925A55C2CF5F49EA7C1A1EA3C242`.
- Il modello originale non viene modificato né sovrascritto.
- La compilazione cambia esclusivamente `word/document.xml`; tutte le altre parti del pacchetto DOCX restano byte per byte quelle del modello.
- Restano invariati A4 verticale, margini, Times New Roman, dimensioni, allineamenti, rientri, numerazione a trattino, grassetto, corsivo, sottolineatura spessa e posizione della firma.
- Le evidenziazioni gialle del modello sono trattate soltanto come marcatori dei campi e vengono rimosse dal documento generato.
- Non vengono aggiunti luogo o data perché non sono presenti nel modello consegnato.

## Campi compilati

- nome e cognome dell'avvocato;
- codice fiscale;
- foro;
- tipo e descrizione di ogni copia scelta;
- ufficio, sezione e data del provvedimento, quando disponibili e pertinenti;
- numero e anno del ruolo generale;
- formula singolare o plurale coerente con il numero di copie;
- firma in calce e dicitura di firma digitale.

Le descrizioni con virgole interne vengono conservate integralmente. È stata aggiunta una regressione specifica per impedire che una virgola nel contenuto del ricorso tronchi la descrizione.

## Flusso applicativo

1. L'avvocato cerca e sceglie la pratica.
2. I documenti risultano disponibili ma non selezionati.
3. L'avvocato seleziona le copie da notificare.
4. IUSENTRA costruisce una sola dichiarazione cumulativa nella relata.
5. `Vedi testo unico` mostra la stessa dichiarazione prima della firma.
6. `Scarica attestazione unica` genera il DOCX dal modello dello studio.
7. Se manca un dato essenziale, l'API restituisce l'elenco puntuale dei campi da completare e non produce un documento incompleto.

Il file viene creato in una directory temporanea per la risposta autenticata e tenant-aware; il server non conserva una copia parallela. La generazione viene registrata nell'audit operativo senza registrare una notifica come inviata.

## Fonti e confronto operativo

- [Legge 21 gennaio 1994, n. 53](https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Alegge%3A1994-01-21%3B53%21vig=), testo vigente consultato per notificazione e attestazione nella relata.
- [Decreto-legge 18 ottobre 2012, n. 179](https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legge%3A2012-10-18%3B179%21vig=), artt. 16-decies e 16-undecies.
- [Specifiche tecniche ex art. 34 D.M. 44/2011, pubblicate il 7 agosto 2024](https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3429), efficaci dal 30 settembre 2024 e corredate dagli avvisi di rettifica pubblicati sul PST.
- Matrice locale di confronto del flusso notifiche: `artifacts/react-migration/studio-telematico-notifiche-legali-confronto-2026-07-03.md`.

Il materiale di confronto conferma la separazione tra scelta dei documenti, origine della copia, attestazione, relata firmata e ricevute. In IUSENTRA la stessa logica è applicata senza esporre nella UI nomi di software confrontati, classi, tabelle o dettagli tecnici.

## Verifiche automatiche

- `python -m pytest -q tests/test_notifiche_legali.py -k attestazione`: `9/9` superati.
- `python -m pytest -q tests/test_notifiche_legali.py tests/test_regia_ui_react.py -k "notifiche or attestazione"`: `65/65` superati.
- `npm --prefix frontend run typecheck`: superato.
- `python -m pytest -q tests/test_utf8_integrity.py`: `4/4` superati.
- Contratto DOCX: stesso inventario del modello, unica parte modificata `word/document.xml`, zero `w:highlight`, tre righe di elenco, un solo `Attesta` e una sola conclusione cumulativa.

## Prova reale locale

Prova eseguita nel browser integrato visibile sulla copia Docker reale `http://127.0.0.1:8080/notifiche-legali`, container unico `iusentra-app` healthy e `/api/pronto` con `ok=true`, versione `2.256.1`, data e ora `Europe/Rome`.

- pratica scelta tramite ricerca reale: `2026/007 - RG 139/2023 — solo danni a cose`;
- documenti selezionati con click reali: `Memoria183_68894819.pdf`, `Documento_80195202.pdf`, `Ordinanza_61235697.pdf`;
- riepilogo osservato: `Una sola dichiarazione comprende 3 documenti.`;
- anteprima osservata: un solo titolo, un solo `Attesta`, tre righe, una sola conclusione, nessuna riga aggiuntiva di luogo/data;
- foro inserito esclusivamente nello stato locale controllato della prova per completare il modello;
- click reale su `Scarica attestazione unica` e stato visibile `Attestazione unica scaricata.`;
- DOCX campione riaperto con Microsoft Word, esportato in PDF e renderizzato: una pagina, nessuna evidenziazione, nessun taglio, sovrapposizione o salto di impaginazione.

Non sono state selezionate conferme di abilitazione, verifica PEC, firma o approvazione finale e non è stata inviata alcuna PEC o notifica reale. La prova chiude il perimetro dell'attestazione cumulativa e del suo download, non certifica l'esito futuro di una notifica dipendente da destinatario, domicilio digitale, firma e ricevute del caso concreto.
