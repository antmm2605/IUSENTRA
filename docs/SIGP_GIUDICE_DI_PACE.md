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

La prima tranche non invia al Ministero e non genera busta: blocca correttamente su `SIGP_XSD_MANCANTE` finche' lo XSD ufficiale non e' presente in locale.

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

Coprono versioni schema, uffici SIGP, depositi, allegati e validazioni. Il runtime iniziale e' stateless per la sola validazione, ma il dominio persistente e' gia' predisposto per SQLite e PostgreSQL.

## Prossime tranche

1. Allineare il builder ai tag reali dello XSD ufficiale installato.
2. Persistire bozza deposito, XML e validazioni nel repository SIGP.
3. Aggiungere controlli PDF/A, firma digitale, dimensione busta e allegati obbligatori.
4. Preparare busta telematica solo dopo validazione XSD positiva.
5. Configurare Model Office SIGP con GLMV e certificato di cifratura di test.
