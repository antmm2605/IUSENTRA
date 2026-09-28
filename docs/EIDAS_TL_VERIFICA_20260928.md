# Verifica tecnica Trusted List ed eIDAS — 28/09/2026

## Fonti e portata

- AgID, [certificati della Trusted List](https://www.agid.gov.it/it/piattaforme/firma-elettronica-qualificata/certificati), aggiornamento 22/01/2026: dal 10/02/2026 la TL italiana può essere firmata anche con TL5 o TL6. Le impronte SHA-256 pubblicate da AgID sono usate dal monitor solo per accertare che entrambe le chiavi siano presenti nella LOTL firmata, mai come trust anchor del verificatore.
- AgID, [chiarimenti transizione eIDAS 2](https://www.agid.gov.it/it/notizie/eidas-2-online-i-chiarimenti-di-agid-ladeguamento-dei-prestatori-di-servizi-fiduciari): indicazioni ai prestatori fiduciari, non prova che una firma individuale sia qualificata.
- [Regolamento di esecuzione (UE) 2026/248](https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32026R0248), artt. 1–6 e allegati I–II: formati di firme e sigilli avanzati da riconoscere nei servizi pubblici. Gli artt. 1(1) e 3(1) si applicano dal 23/02/2027; i formati dell'allegato II creati prima del 23/02/2028 restano oggetto della disposizione transitoria.
- [ETSI TS 119 612 V2.1.1, §5.5.9.3](https://www.etsi.org/deliver/etsi_ts/119600_119699/119612/02.01.01_60/ts_119612v020101p.pdf): `TakenOverBy` identifica il prestatore che assume la responsabilità del servizio storico. Se l'estensione è critica, il verificatore deve comprenderla interamente; l'estensione non impone da sola un diverso esito di validazione della firma.
- [EU DSS](https://github.com/esig/dss): campioni documentali indipendenti per XAdES, JAdES e ASiC, con provenienza e impronte in `tests/fixtures/eidas_formats/README.md`.

## Risultato della verifica sul codice e sulla fonte live

`scripts/check_eidas_tl.py` verifica la firma XML della LOTL europea con il bootstrap pubblicato nella libreria pyHanko, ricava da quella LOTL i certificati autorizzati per la TL italiana, verifica la firma XML della TL e controlla sequenza e scadenza. Il job `.github/workflows/eidas-tl-monitor.yml` lo esegue ogni lunedì e può essere avviato manualmente. Nessun elenco statico di QTSP determina la fiducia; le impronte TL5/TL6 sono solo un controllo di rotazione successivo alla validazione della LOTL.

Esecuzione live del 28/09/2026: LOTL e TL con firma valida; TL italiana sequenza 224, `NextUpdate` 24/03/2027 08:16:56 UTC (dato tecnico XML); TL5 e TL6 presenti nella LOTL firmata. pyHanko 0.37.0 produceva **33 errori** perché non interpreta l'estensione critica `TakenOverBy` nei servizi storici. Il monitor ora verifica prima la firma dell'XML originale, controlla che tutti i 33 errori abbiano esattamente questa causa, interpreta i campi dell'estensione e ricostruisce in memoria la vista per il parser, conservando l'XML firmato come fonte. La nuova esecuzione restituisce `original_service_parse_errors=33`, `takeover_extensions_interpreted=223`, `service_parse_errors=0` e `registry_parse_complete=true`. Il numero 223 riguarda tutte le occorrenze dell'estensione nella TL; 33 erano gli errori incontrati dal parser. Qualunque altro errore o campo dell'estensione sconosciuto fa fallire il controllo. La completezza qui riguarda **solo il parsing del registro**: non prova la qualifica di una firma individuale.

I percorsi applicativi esaminati (`pct/firma.py`, `pct/document_signature_state.py`, `pct/firme_cades.py`) verificano l'integrità crittografica di CAdES/PAdES o estraggono contenuto senza controllo della catena (`openssl -noverify`). Non consumano la TL per valutare catena, revoca e qualifica. Il monitor non è integrato nel verificatore dei documenti. La firma del documento e il flusso deposito/PEC accettato il 09/09/2026 non sono stati modificati.

## Matrice di regressione richiesta dal regolamento

| Profilo allegato I | Stato nel perimetro verificato | Prova ancora necessaria |
| --- | --- | --- |
| CAdES | Integrità crittografica esistente | Catena TL, revoca, tempo di firma, qualifica e sigillo; campioni dei diversi QTSP |
| PAdES | Integrità crittografica esistente | Stessi controlli, più revisioni PDF e profili ETSI |
| XAdES | Campione EU DSS Baseline B: firma XML, riferimenti al documento e `SignedProperties` verificati; manomissione respinta | Catena, revoca, tempo, qualifica e profili superiori |
| JAdES | Campione EU DSS Baseline B: JWS RSA-SHA256, `x5c`, impronta certificato e manomissione verificati | Catena, revoca, tempo, qualifica e varianti detached/multiple |
| ASiC | Campioni EU DSS ASiC-E e ASiC-S con XAdES: contenitore, firma e digest del file verificati; manomissione respinta | Contenitori CAdES, più file/firme, catena e qualifica |

Servono inoltre prove per firme e sigilli dell'allegato II nel periodo transitorio, catena non affidabile, certificato scaduto/revocato, TL scaduta o manomessa e cambio del certificato TL. `tests/test_eidas_tl_monitor.py` copre i controlli negativi sul parser e sui metadati; il job live esercita le firme XML della LOTL e della TL. `tests/test_eidas_document_formats.py` controlla struttura e integrità crittografica di quattro file indipendenti. I certificati di prova EU DSS sono storici e scaduti: la suite non verifica attendibilità del certificato, revoca o qualifica eIDAS e non è una certificazione di conformità completa al regolamento.

## Limite operativo e anti-regressione

Il verificatore documentale e il Local Signer non sono stati cambiati: la baseline congelata lo vieta senza una successiva istruzione esplicita che la sostituisca. Il monitor e la suite sono indipendenti dal flusso operativo e non attestano validità legale o qualificazione di una firma individuale. Nessuna UI, API, tabella SQLite/PostgreSQL o dato di studio è stato modificato. Test mirati: `python -m pytest -q --noconftest tests/test_eidas_tl_monitor.py tests/test_eidas_document_formats.py` e `python scripts/check_eidas_tl.py --strict-services`. Il test isolato esclude le fixture applicative di `tests/conftest.py`, non pertinenti al monitor e che richiedono l'intero stack del prodotto. **Non verificato su macchina reale** tramite browser `127.0.0.1:8080`; non è stata modificata alcuna interazione visibile. Restano aperti l'integrazione del registro TL nella validazione documentale e il controllo dei profili eIDAS completi.
