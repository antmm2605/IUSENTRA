# IUSENTRA 2.487.0 — Allineamento al server, commi non numerati, Corte costituzionale e giustizia amministrativa nella ricerca

## Allineamento al server
- **Contenuto.** La versione comprende tutto `main` del server fino al commit 5b73253: versioni da 2.480.10 a
  2.480.17 e consolidamento dell'import delle regole del pilota di Caddy.
- **Unione con il lavoro locale.** È unita al lavoro locale 2.484.0–2.486.0.
- **Numero di ruolo scritto per esteso.** È stato corretto da entrambe le parti e restano tutte e due le regole:
  - quella del server legge «n. 2539, del Ruolo Generale … dell'anno 2025»;
  - quella locale legge «iscritta al n. …» e «n. 2539/2025 del Ruolo Generale».
- **Test.** I test del server e quelli locali passano insieme.

## Commi non numerati
Negli atti più vecchi (es. D.P.R. 633/1972) i commi non hanno numero. Nell'archivio Normattiva i capoversi sono fusi e
la norma citata mostrava l'articolo intero.
- **Fonte del comma.** Ora il comma si legge dai capoversi dell'XML ufficiale da cui è stato importato l'atto
  (`pct/normattiva_commi_xml.py`). Il rientro d'inizio comma si ricava dall'impaginazione dell'atto; lettere e numeri
  restano nel loro comma; intestazione e note di aggiornamento sono escluse.
- **Esempio.** Art. 6, terzo comma, D.P.R. 633/1972: «Le prestazioni di servizi si considerano effettuate all'atto del
  pagamento del corrispettivo».
- **Avviso.** La scheda dichiara che il comma è stato individuato dall'XML.
- **Copertura.** Gli XML ufficiali sono sul PC per il 99,9% degli atti in archivio (`IUSENTRA_NORMATTIVA_RAW_DIR` per
  una cartella diversa).

## Correzioni della norma citata
- L'intestazione «Art. 2.» non è più scambiata per il comma 2.
- Fra articoli con lo stesso numero (articolo principale e articoli degli allegati) vale il principale.
- La scelta per gruppi di commi resta solo per le partizioni «(commi 101-150)».

## Altre corti nella ricerca
- **Corte costituzionale.** Le pronunce e le massime (22.414 pronunce) sono già nell'archivio giurisprudenza dello
  studio; ora la ricerca le consulta.
- **TAR e Consiglio di Stato.** Si consultano dal catalogo OpenGA: solo estremi, oggetto ed esito; il testo si apre
  sul sito ufficiale.
- **Tempi e guasti.** Ogni fonte ha un tempo massimo breve. Se non risponde, la ricerca prosegue con le altre e lo
  dice (`web/services/ricerca_legale_altre_corti.py`).

## Catalogo: dati riallineati, regole invariate
- **47 proposte rilette.** Erano classificate come contributo unificato con regole superate; sono state rilette con la
  rilettura puntuale, con traccia di audit.
- **3 PEC corrette.** Erano PEC di deposito telematico classificate come «ricevuta del contributo», fra cui Alessi RG
  821/2024; sono state corrette con nota, perché le PEC non si rileggono dall'archivio.
- **Regola non modificata.** Una modifica alla regola è stata provata e scartata dopo la misura sui documenti reali,
  che indicava voci peggiori.
