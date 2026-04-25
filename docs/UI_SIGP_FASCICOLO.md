# UI SIGP - Fascicolo Giudice di Pace

La patch `iusentra_sigp_ui_patch.zip` e' stata integrata come pagina `/sigp-sync/`.

La UI originale prevedeva endpoint demo e `importa-fixture`; in IUSENTRA e' stata adattata al flusso reale:

- nessuna fixture come sorgente dati;
- nessuno scraping HTML del portale;
- importazione di payload JSON reali ottenuti da Local Connector, PST/PdA autorizzato o Model Office SIGP;
- lettura dello snapshot normalizzato persistito da `integrations.sigp.sync_repository`.

Endpoint principali:

```text
GET  /sigp-sync/
GET  /sigp-sync/api/health
POST /sigp-sync/api/schema/ensure
POST /sigp-sync/api/preflight
POST /sigp-sync/api/fascicoli/importa-payload
GET  /sigp-sync/api/fascicoli
GET  /sigp-sync/api/fascicoli/<id>
POST /sigp-sync/api/fascicoli/<id>/download
```

`/download` non scarica dal server cloud: restituisce un messaggio operativo finche' non viene collegato un Local Connector autorizzato con selezione utente.
