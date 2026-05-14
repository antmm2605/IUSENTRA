# Portali telematici - acquisizione guidata

Questa release consolida il flusso comune per PST/SIGP, PDP, PAT e PTT/SIGIT.

## Regola operativa

IUSENTRA non esegue scraping HTML dei portali ministeriali e non salva PIN, password, credenziali SPID/CIE/CNS, cookie o token di sessione del portale. L'utente resta dentro l'esperienza IUSENTRA: quando il portale non e' PST, il gestionale apre una sessione assistita locale tramite Local Signer / Local Connector, mantiene il contesto del fascicolo e importa poi file, ricevute, esiti, ZIP, cartelle o payload JSON autorizzati.

Nessun deposito viene segnato come depositato, acquisito o finalizzato senza ricevuta/esito ufficiale importato o identificativo ufficiale verificato.

## Canali ufficiali

- PST / PolisWeb: integrazione diretta interna tramite canali tecnici autorizzati e Local Signer. Mantiene ricerca, preview, download e acquisizione interna dove gia governati.
- PTT / SIGIT: portale ufficiale assistito; import automatico fascicolo, ricevute ed esiti nel fascicolo tributario interno.
- PAT: portale ufficiale assistito; import automatico file, ricevute ed esiti nel fascicolo amministrativo interno.
- PDP: portale ufficiale assistito di default; canale diretto solo con manifest verificato, completo, non scaduto e con test reali passati.

## Regola fail-closed

PAT, PTT e PDP non vengono mai promossi a integrazione diretta solo perché esiste codice client, endpoint prototipale, WSDL ipotizzato o demo offline. Serve un manifest verificato, con fonte ufficiale, hash evidenze, test reali passati e scadenza valida.

Il manifest diretto deve indicare almeno `allow_direct=true`, stato `verified`, fonte ufficiale HTTPS, hash SHA-256 dell'evidenza, data di verifica, scadenza non superata, test integrazione reali passati, tipo canale autorizzato e soggetto verificatore. In assenza anche di un solo requisito, IUSENTRA resta su `official_portal_assisted`.

## Sessione assistita

Endpoint comuni:

```text
POST /api/portali/<ptt|pat|pdp>/assistant/start
GET  /api/portali/<ptt|pat|pdp>/assistant/<session_id>/status
POST /api/portali/<ptt|pat|pdp>/assistant/<session_id>/collect
POST /api/portali/<ptt|pat|pdp>/assistant/<session_id>/close
POST /api/portali/<ptt|pat|pdp>/assistant/<session_id>/cancel
POST /api/portali/<ptt|pat|pdp>/acquisizione/importa-file
```

`pst` viene rifiutato da questo flusso perché resta direct internal. Se Local Connector non e' raggiungibile, lo stato resta `local_connector_required`: il flusso principale non degrada a un semplice link esterno.

La UI React di PDP/PAT/PTT non espone il portale ufficiale come CTA primaria: parte da `Sessione IUSENTRA`, apre la sessione locale assistita, raccoglie i file nel software e li importa nel fascicolo scelto. `importa-file` salva i binari in `Documenti fascicolo`, collega ricevute/esiti a depositi, timeline ed evidence pack quando riconoscibili, e aggiorna audit/metadati del fascicolo. Il payload JSON autorizzato resta su `importa-payload` e non richiede selezione/anteprima fittizia.

## Deposito assistito PTT/PAT/PDP

Endpoint comuni:

```text
POST /api/portali/<ptt|pat|pdp>/deposito/precheck
POST /api/portali/<ptt|pat|pdp>/deposito/prepara
POST /api/portali/<ptt|pat|pdp>/deposito/assistant/start
POST /api/portali/<ptt|pat|pdp>/deposito/importa-ricevute
POST /api/portali/<ptt|pat|pdp>/deposito/finalizza
```

Il precheck verifica fascicolo target, tipo atto, atto principale, allegati, procura/notifica/pagamento quando richiesti, firma digitale dove richiesta, hash documenti e coerenza minima di ufficio/registro/numero/anno. `prepara` crea solo un pacchetto interno; l'utente completa il deposito sul portale ufficiale assistito. `finalizza` porta allo stato finale solo se esiste ricevuta ufficiale SHA-256, esito ufficiale SHA-256 o identificativo deposito ufficiale verificato.

Le ricevute e gli esiti importati vengono collegati al deposito assistito, alla timeline/evidence pack e alla sezione Comunicazioni/Cancelleria del fascicolo con classificazione operativa: ricevuta accettazione deposito, esito controlli automatici, esito segreteria/cancelleria, rifiuto deposito o anomalia deposito.

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
- I test `tests/test_portali_payload_import_ui.py` verificano che PDP, PAT e PTT arrivino realmente nella UI fascicolo con documenti, attivita, udienze, comunicazioni e istanze, e che `importa-file` smisti file/ricevute nel fascicolo interno senza uscire dal flusso IUSENTRA.
- I test verificano inoltre policy fail-closed, guard dei client diretti, endpoint di sessione assistita, finalizzazione deposito senza evidenza ufficiale e import ricevute in Comunicazioni/Cancelleria con timeline/evidence pack.
