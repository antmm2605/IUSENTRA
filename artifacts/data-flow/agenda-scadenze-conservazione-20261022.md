# Agenda e Scadenziario: conservazione dello storico SQL

Stato: candidato2.447.5, incarico aperto. Collaudo locale reale eseguito;
commit, gate remoti e distribuzione ancora da eseguire. La replica offline complessiva resta disabilitata.

Risultato richiesto: aprire e modificare una voce SQL contenente estensioni
storiche senza perdere tali dati, mantenendo il confronto dello snapshot e la
proiezione ordinaria utilizzata dalle viste.

## Percorso verificato nei sorgenti — EXTRACTED

- `pct/agenda.py`, `Appuntamento.from_dict`: proiezione dei soli campi nativi.
  Gli altri campi restano nello snapshot SQL, senza impedire la lettura.
- `pct/calendar_sql_records.py`, `updated_payload`: riutilizza
  `pct/json_snapshot_delta.py:merge_delta` per applicare la variazione del
  modello alla fonte verificata. I campi nativi mancanti conservano il riempimento
  canonico già eseguito dal writer precedente.
- `pct/agenda_sql_writer.py` e `pct/scadenziario_sql_writer.py`, `write_changes`:
  lo snapshot completo SQL/JSON deve ancora coincidere. La persistenza e la
  proiezione `calendar_query_writer.project_if_registered` restano nella stessa
  transazione, con rollback del comando superato.
- `pct/scadenziario_sql_adoption.py:read_source`: rimane il controllo esplicito
  degli input storici prima dell'adozione; la modifica del lettore non autorizza
  l'importazione silenziosa di campi non riconosciuti.

Non sono state cambiate le regole dei termini, le date, i controlli degli
appuntamenti sovrapposti o i flussi deposito/firma/PEC. Nessuna scansione o
reimportazione viene aggiunta alla lettura di una pagina.

## Riscontri tecnici

Riprodotti prima della correzione due difetti su dati controllati: Agenda
sollevava TypeError per una chiave storica aggiuntiva; lo Scadenziario eliminava
la stessa estensione durante la modifica della nota. Dopo la correzione,
estensione annidata conservata, nota aggiornata e secondo salvataggio con
snapshot superato respinto. Banco SQLite e PostgreSQL reale positivo.

Verifiche adiacenti: 26 controlli lettori/concorrenza/conservazione, 48 controlli Agenda/adozione e 6 Topbar isolati superati nella copia di rilascio.
Corretto anche un test statico già disallineato: contava due controlli di
scrittura, ma il codice corrente ne ha tre. Ora controlla distintamente i
permessi di creazione, modifica, cambio stato ed eliminazione.

Il helper Topbar usa registro studi e radice dati temporanei espliciti. Il
runtime rispetta PCT_DATA_ROOT fornito nella configurazione, mantenendo i valori
precedenti quando assente. Si evita che un test usi il registro reale dello
studio. La correzione non introduce i ruoli o le API offline nel rilascio.

## Accettazione ancora necessaria

Prova materiale sulla copia Docker8080 con appuntamento e scadenza controllati:
apertura, modifica, riapertura, conservazione SQL e controllo delle altre viste.
Poi commit su main, gate remoti, deploy con backup, riscontro sul server,
riallineamento locale allo stesso commit e pulizia governata. Nessun risultato
positivo del solo banco tecnico chiude queste verifiche.

## Prova materiale locale 22/10/2026

Copia Docker reale8080, immagine candidata2.447.5: creato tramite interfaccia
appuntamento controllato AFFCBE67 (01/12/2040, 5 minuti, nessun promemoria,
cliente o fascicolo) e scadenza controllata4c9636ea-d470-43f2-94a8-f9339e2eab63
(02/12/2040, ALTRO, nessun fascicolo). Aggiunta mediante CAS e audit una
estensione annidata di collaudo ai soli due record. Riaperti i moduli ordinari,
modificata esclusivamente la nota e salvato con i pulsanti normali. Nel browser
reale il dettaglio riaperto mostra la nuova nota; SQL conferma estensione
annidata intatta. Entrambe le attività tecniche completate tramite comando
ordinario, conservando storico, note ed estensione. Nessuna pratica reale modificata.

Backup SQLite coerente precedente verificato con quick_check e SHA-256; chiavi
locali preesistenti conservate. La prova non certifica la replica offline globale.
