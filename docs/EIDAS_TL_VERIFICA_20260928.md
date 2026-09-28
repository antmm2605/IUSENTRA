# Verifica tecnica Trusted List ed eIDAS — 28/09/2026

## Fonti e portata

- AgID, [certificati della Trusted List](https://www.agid.gov.it/it/piattaforme/firma-elettronica-qualificata/certificati), aggiornamento 22/01/2026: dal 10/02/2026 la TL italiana può essere firmata anche con TL5 o TL6. Le impronte SHA-256 pubblicate da AgID sono usate dal monitor solo per accertare che entrambe le chiavi siano presenti nella LOTL firmata, mai come trust anchor del verificatore.
- AgID, [chiarimenti transizione eIDAS 2](https://www.agid.gov.it/it/notizie/eidas-2-online-i-chiarimenti-di-agid-ladeguamento-dei-prestatori-di-servizi-fiduciari): indicazioni ai prestatori fiduciari, non prova che una firma individuale sia qualificata.
- [Regolamento di esecuzione (UE) 2026/248](https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32026R0248), artt. 1–6 e allegati I–II: formati di firme e sigilli avanzati da riconoscere nei servizi pubblici. Gli artt. 1(1) e 3(1) si applicano dal 23/02/2027; i formati dell'allegato II creati prima del 23/02/2028 restano oggetto della disposizione transitoria.

## Risultato della verifica sul codice e sulla fonte live

`scripts/check_eidas_tl.py` verifica la firma XML della LOTL europea con il bootstrap pubblicato nella libreria pyHanko, ricava da quella LOTL i certificati autorizzati per la TL italiana, verifica la firma XML della TL e controlla sequenza e scadenza. Il job `.github/workflows/eidas-tl-monitor.yml` lo esegue ogni lunedì e può essere avviato manualmente. Nessun elenco statico di QTSP determina la fiducia; le impronte TL5/TL6 sono solo un controllo di rotazione successivo alla validazione della LOTL.

Esecuzione live del 28/09/2026: LOTL e TL con firma valida; TL italiana sequenza 224, `NextUpdate` 24/03/2027 08:16:56 UTC (dato tecnico XML); TL5 e TL6 presenti nella LOTL firmata. La libreria segnala **33 errori di interpretazione di servizi storici**, in particolare estensioni critiche `TakenOverBy`: il registro dei servizi non è completo (`qualification_complete=false`). Questo non invalida la firma XML della TL, ma impedisce di attribuire con questo controllo una qualifica affidabile a tutti i certificati dei firmatari. Il job non usa tale risultato incompleto per approvare firme.

I percorsi applicativi esaminati (`pct/firma.py`, `pct/document_signature_state.py`, `pct/firme_cades.py`) verificano l'integrità crittografica di CAdES/PAdES o estraggono contenuto senza controllo della catena (`openssl -noverify`). Non consumano la TL per valutare catena, revoca e qualifica. Il monitor non è integrato nel verificatore dei documenti. La firma del documento e il flusso deposito/PEC accettato il 09/09/2026 non sono stati modificati.

## Matrice di regressione richiesta dal regolamento

| Profilo allegato I | Stato nel perimetro verificato | Prova ancora necessaria |
| --- | --- | --- |
| CAdES | Integrità crittografica esistente | Catena TL, revoca, tempo di firma, qualifica e sigillo; campioni dei diversi QTSP |
| PAdES | Integrità crittografica esistente | Stessi controlli, più revisioni PDF e profili ETSI |
| XAdES | Nessun validatore eIDAS verificato | Fixture valida e alterata, catena e qualifica |
| JAdES | Nessun validatore eIDAS verificato | Fixture valida e alterata, parametro `x5c`, catena e qualifica |
| ASiC | Nessun validatore eIDAS verificato | ASiC-S/ASiC-E, contenitori CAdES/XAdES, integrità dei file |

Servono inoltre prove per firme e sigilli dell'allegato II nel periodo transitorio, catena non affidabile, certificato scaduto/revocato, TL scaduta o manomessa e cambio del certificato TL. La suite attuale `tests/test_eidas_tl_monitor.py` copre i metadati e la presenza delle nuove chiavi, mentre il job live esercita le firme XML. Non è una suite di conformità documentale 2026/248.

## Limite operativo e anti-regressione

Il verificatore documentale e il Local Signer non sono stati cambiati: la baseline congelata lo vieta senza una successiva istruzione esplicita che la sostituisca. Il nuovo monitor è indipendente dal flusso operativo e non attesta validità legale o qualificazione di una firma individuale. Nessuna UI, API, tabella SQLite/PostgreSQL o dato di studio è stato modificato. Test mirati: `python -m pytest -q --noconftest tests/test_eidas_tl_monitor.py` (4 superati) e `python scripts/check_eidas_tl.py` (firma XML valida, 33 errori di interpretazione storica). Il test isolato esclude le fixture applicative di `tests/conftest.py`, non pertinenti al monitor e che richiedono l'intero stack del prodotto. **Non verificato su macchina reale** tramite browser `127.0.0.1:8080`; non è stata modificata alcuna interazione visibile.
