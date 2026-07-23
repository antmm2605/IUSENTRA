# Analisi comparativa LexDay → IUSENTRA

Ricognizione del 23/07/2026 sul confronto tra il catalogo funzioni pubblicizzato
da LexDay (gestionale + 21 calcolatori giuridici) e le funzioni presenti in
IUSENTRA, con l'elenco di ciò che è stato implementato per colmare i gap.

## 1. I 21 calcolatori LexDay: mappa di copertura

| # | Calcolatore LexDay | Stato in IUSENTRA | Dove |
|---|---|---|---|
| 1 | Interessi legali e di mora | Già presente | `strumenti_legali.calcola_interessi` (art. 1284 c.c., D.Lgs. 231/2002) |
| 2 | Interessi con acconti (art. 1194 c.c.) | **Nuovo** | `pct/calcolatori/interessi_acconti.py` |
| 3 | Rivalutazione monetaria ISTAT | Già presente | `strumenti_legali.calcola_rivalutazione_istat` (FOI/NIC) |
| 4 | Maggior danno ex art. 1224 c.c. | **Nuovo** | `pct/calcolatori/maggior_danno.py` (Cass. SS.UU. 1712/1995) |
| 5 | Parcella avvocato DM 55/2014 | Già presente | `strumenti_legali.calcola_onorari_forensi` + `pct/tariffario.py` |
| 6 | Contributo unificato | Già presente | `strumenti_legali.calcola_contributo_unificato` (D.P.R. 115/2002) |
| 7 | Danno biologico Milano 2024 | Già presente | `strumenti_legali.calcola_danno_biologico` |
| 8 | Danno parentale Milano 2024 | **Nuovo** | `pct/calcolatori/danno_parentale.py` (tabella a punti, 5 parametri Cassazione) |
| 9 | Quote ereditarie | Già presente (legittima) + **nuovo** (riserva) | `calcola_successione_legittima` + `pct/calcolatori/quote_riserva.py` (artt. 536-556 c.c.) |
| 10 | Usufrutto e nuda proprietà | **Nuovo** | `pct/calcolatori/usufrutto.py` (D.P.R. 131/1986, tasso legale corrente) |
| 11 | Assegno di mantenimento | **Nuovo** | `pct/calcolatori/assegno_mantenimento.py` (stima di prassi, dichiarata) |
| 12 | Termini processuali (65+ voci) | Già presente | `pct/termini_processuali.py` + import Guida Pratica (100+ template) |
| 13 | Memorie 171-ter e 189 | 171-ter già presente; **189 nuovo** | template `CIV_NOTE_CONCLUSIONI_189`, `CIV_CONCLUSIONALI_189`, `CIV_REPLICHE_189` |
| 14 | Termini d'appello | Già presente | `CIV_APPELLO_BREVE` / `CIV_APPELLO_LUNGO` |
| 15 | Impugnazioni (brevi e lunghi) | Già presente | template cassazione, revocazione, opposizione |
| 16 | Multe e sanzioni CdS | **Nuovo** | template `CDS_PAGAMENTO_RIDOTTO_5GG`, `CDS_PAGAMENTO_60GG`, `CDS_RICORSO_PREFETTO_60GG`, `CDS_RICORSO_GDP_30GG` |
| 17 | Termini esecuzioni | **Nuovo** | template `ESE_PRECETTO_*`, `ESE_OPPOSIZIONE_ATTI_617`, `ESE_ISCRIZIONE_RUOLO_*` |
| 18 | Deposito CTU (compensi) | Già presente | `strumenti_legali.calcola_ctu` (L. 319/1980) |
| 19 | Prescrizione civile | Già presente | `strumenti_legali.calcola_prescrizione` |
| 20 | Prescrizione reati | Già presente | `strumenti_legali.calcola_prescrizione_penale` |
| 21 | Vecchio rito (ante Cartabia) | **Nuovo** | template `VR_MEMORIA_183_6_N1/N2/N3`, `VR_CONCLUSIONALI_190`, `VR_REPLICHE_190` |

In più rispetto a LexDay, IUSENTRA offre già: verifica soglia usura, contributi
Cassa Forense, imposta di registro, TFR, cedolare secca, indennità di
licenziamento, piano di ammortamento, custodia cautelare, pignoramento
stipendio/pensione, adeguamento canone, uffici competenti per Comune.

## 2. Funzioni suite (non calcolatori)

| Funzione LexDay | Stato in IUSENTRA |
|---|---|
| Gestione pratiche/fascicoli | Presente (`pct/fascicoli.py`, practice_engine) |
| Scadenze, promemoria, catene di scadenze | Presente (`scadenziario`, notifiche, presidio PEC con scadenze automatiche) |
| Calendario, iCal, Google Calendar | Presente (`calendar_sync_engine`, provider Google/Microsoft/Apple) |
| Analisi AI dei documenti | Presente e più ampia (document_intelligence, OCR legal-grade, Lex fail-closed) |
| Time tracking e compensi | Presente (`compensi_a_tempo`, motore preventivo, fatturazione) |
| Fatture e solleciti | Presente (`fatturazione`, FatturaPA/SdI) |
| Condivisione col cliente | Presente (`condivisione`, portale cliente) |
| Avvisi normativi in dashboard | Presente (`legal_update_*`, legal_intelligence) |
| Brief del mattino | Copertura equivalente tramite Panoramica + centro notifiche |
| Calcolatori pubblici senza login | **Non previsto per scelta**: in IUSENTRA gli strumenti sono dietro autenticazione (multi-tenant, dati studio nei prefill) |

## 3. Nuovi moduli implementati (v2.259.0)

- `pct/calcolatori/` — sottopacchetto con 6 moduli piccoli e governabili, ognuno
  con base normativa dichiarata nel docstring; l'orchestrazione resta in
  `pct/strumenti_legali.py` (metodi di delega).
- 19 nuovi template termini in `pct/termini_processuali.py`, con auto-upgrade
  del repository (JSON e SQLite) per le installazioni esistenti.
- Wiring completo: catalogo strumenti, blueprint `/strumenti-legali/api/*`,
  schemi React (`TOOL_SCHEMAS` + `build_tool_result` in
  `pct/applicazioni_runtime.py`), form Jinja legacy.
- Test: `tests/test_calcolatori_lexday.py` (31 casi).

## 4. Avvertenze sulle fonti

- Danno parentale: valori punto Milano 2024 dichiarati come approssimazione
  operativa (stesso approccio del danno biologico); il risultato espone sempre
  l'avvertenza di verificare la griglia ufficiale del Tribunale di Milano.
- Assegno di mantenimento: la legge non prevede formule; il modulo dichiara in
  ogni risultato che si tratta di stima orientativa su criteri di prassi
  (artt. 337-ter, 316-bis c.c.; art. 5 L. 898/1970; Cass. SS.UU. 18287/2018).
- Interessi/maggior danno: tassi e indici provengono dalle tabelle normative
  versionate; i periodi non coperti bloccano o segnalano il calcolo
  (fail-closed), mai stime implicite.
