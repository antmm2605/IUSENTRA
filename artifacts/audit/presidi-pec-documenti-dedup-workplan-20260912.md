# Bonifica presidi PEC e documenti fascicolo - piano operativo 2026-09-12

## Obiettivo

Portare a fine lavoro la fusione logica tra letture PEC e documenti presenti nei fascicoli, evitando nuovi duplicati e bonificando quelli gia' presenti senza cancellare storico operativo.

Il risultato atteso e' una lettura unica e completa per i presidi: ogni evento processuale deve esporre tutte le fonti utili, PEC e documento fascicolo, ma deve produrre un solo impegno operativo quando le informazioni coincidono.

## Dati gia' emersi dalla diagnosi di produzione

- Il backfill PEC a 365 giorni ha controllato 960 PEC, creato 69 voci "PEC ricevuta", aggiornato 0 impegni nuovi e prodotto 0 errori.
- Il contatore `rescheduled = 0` non prova da solo un difetto: su RG 1733/2026 e RG 1854/2026 gli impegni gia' rinviati erano presenti prima del backfill.
- La lettura completa ha coperto Agenda, Scadenziario, audit PEC, report PEC, Document AI e marker `pec.document_presidio.checked`.
- Sono emersi 19 gruppi sospetti collegati a presidi PEC/documenti e circa 250 gruppi generici/manuali da tenere separati.
- I casi collegati piu' rilevanti riguardano:
  - RG 1733/2026
  - RG 1854/2026
  - RG 5478/2025
  - RG 771/2025
  - RG 792/2025
  - RG 3571/2025
  - gruppi 127-ter generati da PEC e documenti fascicolo

## Regola di identita' da implementare

Un presidio automatico deve essere considerato lo stesso evento quando coincidono:

- tenant;
- fascicolo o, se manca, RG normalizzato;
- data processuale e, quando disponibile, ora;
- famiglia dell'attivita' processuale, per esempio opposizione 127-ter, deposito note scritte 127-ter, termine note sostituzione udienza;
- natura governata della fonte, cioe' PEC presidio e documento fascicolo quando descrivono lo stesso adempimento.

Non vanno fusi automaticamente:

- presidi manuali o generici senza fonte governata;
- "PEC ricevuta", che resta una voce informativa distinta;
- gruppi con piu' RG sostanziali non riconducibili allo stesso fascicolo;
- gruppi ambigui nei quali il software non puo' provare quale voce sia canonica.

## Lavoro da fare

1. Leggere il codice dei generatori:
   - `pct/pec_pipeline.py`
   - funzioni di scheduling PEC;
   - funzioni di presidio documenti fascicolo;
   - sincronizzazione Agenda/Scadenziario.

2. Costruire una chiave canonica unica per i presidi automatici:
   - normalizzazione titolo/attivita';
   - normalizzazione fascicolo/RG;
   - distinzione tra fonte PEC, documento fascicolo, voce manuale e voce informativa;
   - motivo esplicito quando una voce non e' fondibile.

3. Correggere il runtime:
   - prima di creare un nuovo presidio da PEC, cercare un presidio equivalente gia' aperto;
   - prima di creare un presidio da documento fascicolo, cercare anche equivalenze logiche oltre al marker tecnico;
   - arricchire la voce esistente con la nuova fonte invece di creare un duplicato;
   - mantenere separata la voce "PEC ricevuta".

4. Creare uno script di audit completo:
   - lettura da fonte SQL reale;
   - output con tenant, fascicolo, RG, data/ora, attivita', fonte primaria, fonte secondaria, ID PEC, ID documento, ID Agenda, ID Scadenziario, stato e motivo;
   - modalita' dry-run;
   - elenco dei gruppi riparabili e dei gruppi da revisione.

5. Creare una bonifica idempotente:
   - nessuna cancellazione fisica;
   - scelta deterministica della voce canonica;
   - annullamento dei duplicati automatici con nota di confluenza;
   - collegamento o arricchimento della voce canonica con tutte le fonti;
   - secondo giro senza ulteriori modifiche.

6. Aggiungere test mirati:
   - doppio presidio PEC sullo stesso evento;
   - doppio presidio documento sullo stesso evento;
   - fusione PEC + documento fascicolo;
   - esclusione di "PEC ricevuta";
   - esclusione di voci manuali/generiche;
   - idempotenza della bonifica;
   - casi ambigui multi-RG lasciati in revisione.

7. Eseguire verifiche locali:
   - test mirati;
   - eventuali gate collegati al perimetro modificato;
   - copia locale reale `127.0.0.1:8080` healthy e allineata.

8. Commit e push:
   - branch `Codex/legal-electronic-filing-kIxcV`;
   - branch gemello `claude/legal-electronic-filing-kIxcV`.

9. Deploy Hetzner:
   - aggiornare `/opt/iusentra/repo`;
   - ricostruire/ricreare il servizio app del profilo `deploy/hetzner`;
   - verificare un solo container applicativo chiamato `iusentra-app`;
   - verificare container healthy e `https://app.iusentra.it/api/pronto`;
   - pulire cache build Docker e snapshot temporanei.

10. Bonifica produzione:
    - eseguire audit dry-run;
    - controllare conteggi e gruppi da revisione;
    - applicare solo gruppi riparabili;
    - rieseguire audit e backfill/lettura completa;
    - verificare che il secondo giro non produca nuovi doppioni.

11. Riallineamento locale finale:
    - portare la macchina locale allo stesso commit e comportamento applicativo del server;
    - non copiare mai database, documenti, allegati, volumi o altri dati di produzione sulla macchina locale;
    - ricostruire la copia locale su `127.0.0.1:8080`;
    - verificare `/api/pronto`.

## Criteri di chiusura

Il lavoro si puo' dichiarare chiuso solo quando:

- i nuovi presidi non duplicano eventi gia' presenti;
- i duplicati automatici gia' esistenti sono annullati o confluiti senza perdita di storico;
- i casi ambigui restano visibili con motivo di revisione;
- l'audit completo produce numeri chiari su letti, fusi, annullati, saltati e errori;
- server Hetzner, GitHub e copia locale sono allineati;
- i container sono healthy;
- `api/pronto` risponde correttamente in produzione e in locale.

## Presidio uso Codex e spegnimento PC

L'utente ha chiesto esplicitamente il 2026-09-12 di spegnere il PC quando l'utilizzo residuo della finestra Codex da 5 ore scende al 5% o meno. Il controllo operativo deve quindi monitorare la finestra primaria da 300 minuti e, quando il residuo e' minore o uguale al 5%, eseguire lo spegnimento della macchina.

Stato al momento della scrittura: finestra primaria Codex usata 0%, residuo 100%.
