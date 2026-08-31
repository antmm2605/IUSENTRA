# Log tecnico — Fascicolo d’ufficio Vicenza R.G. 1084/2026

**Avvio prova:** 30/08/2026 01:05:08, ora italiana
**Pagina reale:** `http://localhost:8080/fascicoli/A1FB22FE#documenti`
**Ambiente:** container locale `iusentra-app` sano, immagine `sha256:45f77d81e4e75d5d534521fcfd7da6e954337bd24315d06d8a2a79cfb2832f16`, uguale al server.

## Richiesta iniziale osservata

| Campo | Valore |
| --- | --- |
| Endpoint Local Signer | `POST /pst/ricerca-snapshot` |
| Ufficio UI | `0640011` — Tribunale di Vicenza |
| Codice PST risolto | `0241160092` |
| R.G. | `1084/2026` |
| Tabella effettiva | `JPW_SIL_DISTR` |

La prova è separata da quella del Wizard e parte dopo la chiusura del relativo lotto. Il confronto finale riporterà richieste, tabella, PIN/sessioni, tempi, catalogo ottenuto, numero di documenti e download effettivi.

## Esito della consultazione

L’utente ha inserito un solo PIN. La richiesta ha raggiunto il Local Signer ma il lotto ha registrato, alle 01:05:56, `SOAP Fault IDATTO` sulla richiesta 7 di `JPW_SIL_DISTR`. Il pannello ha quindi mostrato cinque documenti già acquisiti, non il catalogo completo di trenta documenti ottenuto dal Wizard.

Non esiste un limite di cinque documenti nel componente: `completeCatalogRows` unisce tutti i rami disponibili della risposta e `flattenDocuments` non applica alcun taglio. Il numero cinque proviene quindi dalla risposta PST parziale ricevuta dopo l’errore `IDATTO`.

## Differenze rispetto al Wizard

| Voce | Wizard | Fascicolo d’ufficio |
| --- | --- | --- |
| Endpoint | `/pst/ricerca-snapshot` | `/pst/ricerca-snapshot` |
| Codice UI → PST | `0640011 → 0241160092` | `0640011 → 0241160092` |
| Tabella | `JPW_SIL_DISTR` | `JPW_SIL_DISTR` |
| Lotto unico e snapshot completo | sì | sì, dichiarato nella richiesta |
| `ruolo_polisweb` | inviato esplicitamente come `AVV` | **non inviato** |
| Identificativi del fascicolo e sessione memorizzata | non inviati nella ricerca iniziale | inviati (`id_fascicolo`, sotto-procedimento, identificativi JPW e sessione) |

La differenza da correggere prima della prossima prova è il payload del pannello: deve usare lo stesso costruttore condiviso del Wizard, compreso `ruolo_polisweb=AVV`, invece di comporre una variante propria con campi aggiuntivi. Fino a quella correzione la parità richiesta non è dimostrata.

## Allineamento del pannello distribuito il 30/08/2026

- Immagine base locale: `iusentra-app:server-baseline-20260830` (`sha256:45f77d81e4e75d5d534521fcfd7da6e954337bd24315d06d8a2a79cfb2832f16`).
- È stato creato un overlay Docker che modifica soltanto `/app/web/static/react`; nessun volume, dato, Local Signer, backend o Wizard è stato modificato.
- Il bundle attivo su `http://localhost:8080` è `OfficeDocumentsPanel-BKk78ads.js`.
- La richiesta di visualizzazione usa `/pst/ricerca-snapshot`, `servizio_pst_preferito`, `registro_portale`, `tabella_ministeriale`, `tipo_registro`, `registro`, `materia`, `schema`, `quick_filter` e `ruolo_polisweb=AVV`.
- Gli identificativi storici `id_fascicolo`, `id_dfa` e `id_ruolo_jpw` non fanno più parte della richiesta di ricerca.
- Verifica statica: gli asset attivi del Wizard, `FascicoliPage` e `TelematicoSurfacePage` sono semanticamente identici al bundle precedente, al netto degli hash Vite.
- Verifica HTTP locale: `/api/pronto` ha risposto `ok=true`; il chunk servito non contiene `/pst/fascicolo-snapshot-job` e contiene i campi del contratto PST allineato.
- Prova reale con certificato/PIN e risposta PST: ancora da eseguire sulla pagina visibile dell’utente. Non è un esito funzionale conclusivo.
