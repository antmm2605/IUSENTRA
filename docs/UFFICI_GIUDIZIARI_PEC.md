# Uffici giudiziari e PEC

Il modulo `Tribunali / PEC` governa la ricerca degli uffici giudiziari e degli indirizzi telematici senza mischiare gli usi delle PEC.

## Fonti

Le fonti sono distinte per ruolo operativo:

- `PST Giustizia`: fonte primaria per uffici e indirizzi collegati al deposito telematico. Il deposito generico usa una PEC verso l'indirizzo telematico dell'ufficio giudiziario destinatario, consultabile nel catalogo dei servizi telematici del PST.
- `IPA Open Data`: fonte secondaria per PEC amministrative, protocollo, AOO e UO. Il dataset `Elenco delle pec attive degli enti` contiene PEC associate a enti, AOO o UO e viene aggiornato con frequenza giornaliera.
- `Sito ufficiale dell'ufficio`: fallback documentale o verifica manuale, da non promuovere automaticamente a PEC di deposito se manca un riscontro PST o PdA autorizzato.

## Regola di prodotto

Ogni indirizzo telematico deve esporre:

- `uso`: `deposito_pct`, `deposito_penale`, `deposito_amministrativo`, `deposito_tributario`, `amministrativa`, `protocollo` o `verifica_manualizzata`;
- `fonte`: `PST`, `IPA`, `sito_ufficiale`, `bundle_interno` o `manuale`;
- `url_fonte`;
- `data_rilevazione`;
- `attiva`;
- `note`.

La UI deve mostrare chiaramente che una PEC di deposito telematico non e' una PEC amministrativa/protocollo.

## Motore di verifica

Il pulsante `Esegui verifica` usa due livelli:

1. verifica live su endpoint configurato o PST, quando la sorgente restituisce dati normalizzabili;
2. fallback governato su registro interno versionato, con report `verifica_locale_governata`, quando le sorgenti live non rispondono.

Il fallback non e' un errore silenzioso: il report indica che la verifica e' stata completata sul registro interno e mantiene nel payload le fonti PST/IPA da monitorare.

## Storage

La cache runtime resta oggi JSON-first per continuita' operativa del modulo esistente, ma la base SQL governata e' presente in:

- `pct/sql/20260430_uffici_giudiziari_pec.sql`
- `pct/sql/20260430_uffici_giudiziari_pec_postgres.sql`

Le tabelle sono:

- `uffici_giudiziari`
- `indirizzi_telematici`
- `uffici_giudiziari_verifiche`
- `uffici_giudiziari_variazioni`

Wave successiva: repository read/write SQL tenant-aware e job schedulato che scrive direttamente su SQLite/PostgreSQL, mantenendo la cache JSON come export/runtime legacy e non come fallback invisibile quando un backend SQL e' attivo.

## Superficie UI

La superficie React `Tribunali / PEC` usa:

- elenco uffici scrollabile;
- card laterali `Esiti in attesa`, `Import incompleti`, `Controlli predeposito`, `Collegamenti rapidi`;
- payload `officeSummary.sources` e `officeSummary.policy`;
- `indirizziTelematici` su ogni ufficio con PEC censita.
