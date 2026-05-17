# Lex AI - Mappa competenze software e dataset multi-dominio

Aggiornato: 17 maggio 2026.

Questo documento è il perimetro operativo del worker E per portare Lex AI su
tutto IUSENTRA senza training automatico, senza dati demo e senza invii esterni.
La matrice canonica è in
`docs/lex_software_domain_dataset_matrix.json`; questo file ne riassume l'uso
per progetto, test e future tranche RAG.

## Regole vincolanti

- Lex legge dati di studio solo tramite repository, API o contesto tenant-aware.
- Il canale immediato è RAG interno o lookup deterministico; il fine-tuning
  resta candidato, manuale, revisionato e separato.
- Nessuna coppia Q&A deve salvare ragionamento interno, segreti, path assoluti
  o dati di altri tenant.
- Le Q&A della matrice sono esempi da generare e casi di accettazione, non
  materiale pronto per addestramento.
- Le azioni dispositive restano fuori da Lex: invio PEC, deposito, firma,
  pagamento, pubblicazione sito, restore backup, migrazioni, creazione utenti e
  modifiche di configurazione richiedono workflow applicativi dedicati.

## Domini coperti

| Dominio | Fonti reali principali | Permessi minimi | Azioni Lex ammesse |
| --- | --- | --- | --- |
| Clienti e soggetti | `pct/clienti.py`, `pct/soggetti.py`, repository tenant-aware | `ai.usa`, `clienti.leggi` | ricerca e riepilogo read-only, lacune, proposta bozza |
| Fascicoli e documenti | `pct/fascicoli.py`, Documenti AI, chunk indicizzati | `ai.usa`, `fascicoli.leggi` | riepilogo pratica, ricerca citabile, prossime azioni |
| Agenda e scadenze | `pct/agenda.py`, `pct/scadenziario.py`, trace calcoli | `ai.usa`, `agenda.leggi`, `scadenziario.leggi` | agenda, termini, spiegazioni tracciate |
| Email ordinaria e PEC | `pct/email_client.py`, `pct/messaggi.py`, caselle tenant | `ai.usa`, `messaggi.leggi` | sintesi comunicazioni e bozze non inviate |
| Atti, template ed editor | template atti, editor AI, documenti fascicolo | `ai.usa`, `fascicoli.leggi` | scelta template, bozza, proposte modifica |
| Ricerca legale e giurisprudenza | `legal_updates.db`, Normattiva, Gazzetta, source policy | `ai.usa` | ricerca ufficiale, exact match, schede in revisione |
| Telematico | runtime PST/PDP/PAT/PTT, specifiche ministeriali, ricevute | `ai.usa`, `telematico.leggi` | checklist, spiegazione esiti, warning governati |
| Pagamenti e fatturazione | preventivi, parcelle, fatture, timesheet | `ai.usa`, `fatturazione.leggi` | riepiloghi economici e controlli coerenza |
| Impostazioni | bridge impostazioni, config tenant, stato Local Signer | `ai.usa`, `impostazioni.leggi` | diagnosi read-only e guida compilazione |
| Backup | report backup/crash test, configurazioni backup | `ai.usa`, `backup.leggi` | stato ultimo backup e checklist non distruttiva |
| Privacy e GDPR | registro GDPR, audit, privacy guard | `ai.usa`, `privacy.leggi` | lacune registro, sintesi minimizzata, bozze in revisione |
| Sito Studio | repository sito, contatti, prenotazioni, asset pubblici | `ai.usa`, `sito_studio.leggi` | riepilogo richieste e bozze non pubblicate |
| Amministrazione | utenti, profili, audit, database, osservabilità | `ai.usa`, permessi admin specifici | riepiloghi read-only e rimedi non distruttivi |

## Piano dataset/RAG

1. Inventariare sorgenti reali per dominio usando la matrice JSON come registro.
2. Per ogni dominio generare task Q&A solo da record autorizzati e fonti
   citabili, marcandoli come `pending_human_review`.
3. Indicizzare nel RAG interno chunk tenant-aware quando esiste testo citabile:
   documenti, email autorizzate, ricevute, template, fonti ufficiali, report.
4. Lasciare fuori dai chunk e dalle Q&A: segreti, credenziali, path assoluti,
   dati di altri tenant, log grezzi, chain-of-thought e contenuti non verificati.
5. Accettare una Q&A solo se supera i test di dominio: permesso, tenant,
   assenza dati esclusi, risposta prudente quando manca evidenza.

## Verifica read-only

La matrice può essere esposta in JSON senza importare il runtime Lex:

```powershell
python scripts\export_lex_domain_dataset_matrix.py --pretty
python scripts\export_lex_domain_dataset_matrix.py --domain clienti_soggetti --pretty
```

Il test dedicato verifica schema minimo, domini obbligatori, campi di sicurezza,
divieto di training automatico e assenza di espressioni vietate.
