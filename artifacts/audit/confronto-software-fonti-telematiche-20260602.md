# Confronto software e fonti telematiche ufficiali - 2 giugno 2026

Questo confronto collega le fonti ufficiali lette il 2 giugno 2026 alle regole
effettivamente presenti in IUSENTRA. Non contiene credenziali, PIN o dati
processuali riservati.

| Area | Fonte ufficiale | Stato software | Verifica / limite |
| --- | --- | --- | --- |
| Uffici giudiziari civili PST | `servizipst.giustizia.it`, ricerca `ufficioSelect=giudiziari` | Catalogo salvato in `pct/data/uffici_pst_pubblici.json`; resolver evita voci storiche/non operative per selezione automatica. | Audit 1.781 voci, 1.041 depositabili prudenziali, zero errori dettaglio. |
| Uffici giudiziari penali/PDP PST | `servizipst.giustizia.it`, ricerca `ufficioSelect=penali` | PDP usa il catalogo penale pubblico prima di ogni fallback civile. | Audit 1.416 voci, 1.413 depositabili prudenziali; test Reggio `08006300604`. |
| Servizi web PST / PolisWeb | `Documentazione servizi web v1.69`, WSDL locali | Namespace e servizi JPW sono mappati per SICID, SIL, SIVG, MIN/SIMIN, SIECIC, SIGP, CASSCI, CASSPE e UNEP. | Test mirati `tests/test_polisweb.py`, `tests/test_reginde.py`, `tests/test_local_signer.py`. |
| Cassazione penale | XSD Cassazione e servizio `JPW_CASSPE` | Ricerca su `QP_Ricorsi`; Cassazione distinta da SICID e PDP. | Test live `12756/2026` OK. |
| Cassazione civile | XSD Cassazione e servizio `JPW_CASSCI` | Ricerca su `QC_Ricorsi`; canale distinto da SICID. | Serve numero ruolo civile realmente visibile al certificato per prova live esatta. |
| Giudice di Pace / SIGP | XSD Giudice di Pace, catalogo PST | Suffisso `GDP` normalizzato su `SIGP`, namespace `urn:CONS-SIGP-BE`. | Test live Palmi già documentato; test automatici proteggono da regressione a `CC`. |
| Volontaria giurisdizione / SIVG | WSDL PST | Registro `VG` usa `JPW_SIVG`. | Test live Roma `63/2025/VG` OK. |
| Lavoro / SIL | WSDL PST | Registro `LAV` usa SIL/SIL_DISTR, non SICID. | Test live precedente tabella raggiunta; nessun fascicolo visibile con dati di prova. |
| SIECIC | WSDL PST | Registro concorsuale/esecutivo separato; non inventa `idRuoloJPW`. | Prova live ha prodotto fault ministeriale su parametro mancante; comportamento corretto fail-closed. |
| Giustizia Map / competenza territoriale | `giustizia.it`, ricerca uffici per Comune | `/fascicoli/nuovo` usa fonte territoriale per autorità, PEC e tipo ufficio; il codice deposito arriva solo da PST/WSDL. | Audit comuni e UI con avviso se manca codice depositabile. |
| Corte di Assise di Appello Reggio Calabria | Giustizia Map | Ufficio territoriale valido, ma senza codice PST dedicato; non viene sostituito con Corte d'Appello civile. | Avviso utente obbligatorio prima del deposito. |
| PAT / SIGA | Giustizia Amministrativa, Portale dell'Avvocato | Profilo `pat_siga`, portale operativo `https://pe.prod.cloud.giustizia-amministrativa.it`, atto principale PAdES. | Test blocca CAdES `.p7m` come atto principale PAT. |
| PTT / SIGIT | MEF assistenza Giustizia Tributaria e SIGIT | Profilo `ptt_sigit`, checklist e fonti aggiornate su SIGIT/MEF; non usa PST. | Verifica browser renderizzata su `most-viewed`, `3016`, `3059`, `area-video`, SIGIT. |
| Richieste copie | Documentazione servizi web v1.69 | Solo lettura read-only `RicercaRichieste`/`ProfiloRichiesta`, nessun invio automatico. | SOAP 200 `available=0`; manca richiesta reale visibile al certificato per prova dispositiva. |
| Local Signer | Policy interne e flusso locale | Installer include cataloghi PST pubblici; PIN resta sul PC; test foreground/pin e catalogo pubblico. | Verificare in UI locale dopo build su `127.0.0.1:8080`. |

## Decisioni chiave

- Non si dichiara valido un codice deposito se la fonte territoriale esiste ma il
  catalogo PST/WSDL non espone codice depositabile.
- Non si usa il codice civile di un ufficio per depositi penali.
- PAT e PTT restano portali autonomi: NRG/UID/CGT non sono codici PST.
- Le richieste copie restano read-only finché il certificato non mostra una
  richiesta reale su cui operare senza simulazioni.
