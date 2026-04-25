# Portali telematici - acquisizione guidata

Questa release consolida il flusso comune per PST/SIGP, PDP, PAT e PTT/SIGIT.

## Regola operativa

IUSENTRA non esegue scraping HTML dei portali ministeriali. Quando un portale non espone un canale tecnico utilizzabile dal backend, il gestionale accompagna l'utente al portale ufficiale, mantiene il contesto del fascicolo e importa poi file, ZIP, cartelle o payload JSON autorizzati prodotti da Local Connector, PdA o Model Office.

## Canali ufficiali

- PST / PolisWeb e SIGP: acquisizione con Local Signer o import file gia scaricati; la copia di consultazione con annotazioni ministeriali resta il default.
- PDP Penale: apertura guidata su `https://appweb.giustizia.it/snt`, import nel fascicolo penale interno, workflow PDP e catalogo documentale.
- PAT Amministrativo: apertura guidata sul Portale dell'Avvocato, import manuale dei file e payload autorizzati nel fascicolo amministrativo interno.
- PTT / SIGIT: apertura guidata su SIGIT / Telecontenzioso, import nel fascicolo tributario interno.

## Smistamento nella UI fascicolo

Il payload autorizzato viene normalizzato e smistato nelle sezioni gia presenti nella UI:

- `Documenti fascicolo`: documenti, catalogo buste, metadati ufficiali, file/ZIP importati.
- `Attivita processuali`: eventi, depositi, esiti e cronologia non documentale.
- `Udienze e scadenze`: udienze e termini, con generazione scadenziario quando richiesto.
- `Comunicazioni di cancelleria`: comunicazioni, notifiche ed esiti provenienti dal portale.
- `Istanze`: istanze e relativi esiti censiti nel payload.

## Formato payload

Endpoint comune:

```text
POST /api/portali/<pst|pdp|pat|ptt>/acquisizione/importa-payload
```

Il JSON puo contenere `fascicolo`, `parti`, `eventi`, `udienze`, `documenti`, `comunicazioni`, `istanze` e `depositi`. I campi vengono accettati anche con alias frequenti dei connettori locali, ad esempio `numero_ricorso`, `numero_rgt`, `numero_rg`, `dataDeposito`, `dataUdienza`, `nome_file`, `tipo_atto`.

## Garanzie anti-regressione

- I documenti dei portali PAT/PDP/PTT non vengono piu classificati come servizio `PAT`, `PDP` o `PTT`: nel catalogo del fascicolo restano `DocumentiFascicolo`.
- Il wizard accetta file `.json` autorizzati oltre a ZIP, PDF, P7M, EML, MSG, XML e cartelle scaricate.
- I test `tests/test_portali_payload_import_ui.py` verificano che PDP, PAT e PTT arrivino realmente nella UI fascicolo con documenti, attivita, udienze, comunicazioni e istanze.
