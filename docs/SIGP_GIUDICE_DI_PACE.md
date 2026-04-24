# Integrazione SIGP - Giudice di Pace

Il modulo SIGP e' separato dalla semplice consultazione PST perche' governa redazione, XML, validazione XSD, controlli di predeposito e futura busta telematica per gli Uffici del Giudice di Pace.

## Fonti ufficiali

- PST - dettaglio documentazione: https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3460
- PST - nota modifiche XSD SIGP 27/08/2024: https://pst.giustizia.it/PST/resources/cms/documents/modifiche_XSD_SIGP_20240827.pdf

La nota ufficiale indica `Professionista.xsd` versione 2.0 e il nuovo atto CTU per giuramento telematico.

## Stato implementazione

- `integrations/sigp/registry.py`: registry versionato degli XSD.
- `integrations/sigp/xsd_loader.py`: loader e stato schema.
- `integrations/sigp/validator.py`: validazione XML contro XSD ufficiale.
- `integrations/sigp/xml_builder.py`: builder XML di bozza tecnica.
- `integrations/sigp/predeposito.py`: controlli minimi di predeposito.
- `integrations/sigp/service.py`: orchestrazione `dati -> XML -> XSD`.
- `integrations/sigp/routes.py`: UI `/sigp` e API `/sigp/depositi/prepara`.
- `integrations/sigp/sync_mapper.py`: normalizzazione di payload reali autorizzati PST/PdA/Local Connector.
- `integrations/sigp/sync_repository.py`: persistenza SQLite dello snapshot completo del fascicolo SIGP.
- `integrations/sigp/sync_service.py`: importazione controllata dei dati autorizzati nel repository.
- `integrations/sigp/sync_policy.py`: policy pubblica che vieta scraping HTML, PIN salvato e credenziali cloud.

La prima tranche non invia al Ministero e non genera busta: blocca correttamente su `SIGP_XSD_MANCANTE` finche' lo XSD ufficiale non e' presente in locale.

## Sincronizzazione fascicolo telematico

La sincronizzazione fascicolo SIGP importa solo payload reali ottenuti tramite canali autorizzati:

- PST pubblico con sessione ufficiale e autenticazione forte.
- Punto di Accesso autorizzato.
- Model Office SIGP per test software house.
- Local Connector/Signer sul PC dello studio, con token CNS/smart card e sessione temporanea.

Il gestionale non effettua scraping HTML di pagine come `sigp_infofascicolo.wp`, non salva PIN, non salva credenziali del portale nel cloud e non esegue download massivo non presidiato.

Endpoint applicativi:

```text
GET  /sigp/sync/status
POST /sigp/sync/importa-payload
```

`POST /sigp/sync/importa-payload` accetta un payload JSON reale gia' ottenuto dal canale autorizzato e lo salva come snapshot completo: fascicolo, parti, eventi, udienze, documenti, provvedimenti e comunicazioni. Non usa fixture e non applica limiti fissi sul numero di documenti.

## Installazione XSD

Estrarre il pacchetto ufficiale PST nella cartella:

```text
integrations/sigp/schemas/2024-08-27/xsd/
```

Il file principale atteso e':

```text
Professionista.xsd
```

Se il pacchetto ufficiale cambia nome del file principale, aggiornare `integrations/sigp/registry.py`.

## Storage

Le migrazioni governate sono:

```text
pct/sql/20260424_sigp_repository.sql
pct/sql/20260424_sigp_repository_postgres.sql
```

Coprono versioni schema, uffici SIGP, depositi, allegati, validazioni e snapshot di sincronizzazione fascicolo. Il runtime iniziale di validazione resta stateless, mentre la sincronizzazione autorizzata persiste i dati completi su SQLite e ha schema PostgreSQL allineato.

## Prossime tranche

1. Allineare il builder ai tag reali dello XSD ufficiale installato.
2. Persistire bozza deposito, XML e validazioni nel repository SIGP.
3. Aggiungere controlli PDF/A, firma digitale, dimensione busta e allegati obbligatori.
4. Preparare busta telematica solo dopo validazione XSD positiva.
5. Configurare Model Office SIGP con GLMV e certificato di cifratura di test.
