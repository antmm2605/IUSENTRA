# Profili canale deposito

La firma non e' applicata "all'intero pacchetto" in modo indistinto: IUSENTRA usa una `SignaturePolicy` per canale.

## Canali supportati

| Codice | Nome | Invio diretto | Upload manuale | Firma |
| --- | --- | --- | --- | --- |
| `pct_sicid` | PCT SICID civile | Si, PEC | No | CAdES sull'atto principale |
| `pct_siecic` | PCT SIECIC esecuzioni/concorsuali | Si, PEC | No | CAdES sull'atto principale |
| `sigp_gdp` | SIGP Giudice di Pace | No | Si | Policy canale |
| `unep` | UNEP notifiche/esecuzioni | No | Si | Policy canale |
| `pec_stragiudiziale` | PEC stragiudiziale | Si | No | Non obbligatoria |
| `notifiche_pec` | Notifiche PEC | Si | No | Policy canale |
| `pat_siga` | PAT/SIGA | No | Si | PAdES sull'atto/modulo principale |
| `ptt_sigit` | PTT/SIGIT | No | Si | Policy canale |
| `pdp_penale` | PDP Penale | Tramite client PDP se abilitato | Si | PAdES o CAdES secondo regola ufficio |
| `upload_manuale_guidato` | Upload manuale guidato | No | Si | Facoltativa/policy canale |
| `portal_upload` | Portale generico manuale | No | Si | Facoltativa/policy canale |

I canali PAT, PTT, SIGP, UNEP e portali manuali sono predisposti come preparazione e upload guidato: non fingono automazioni non disponibili o non autorizzate.

## Regole PAT/SIGA accertate

Fonte ufficiale controllata il 2 giugno 2026: `https://www.giustizia-amministrativa.it/web/guest/portale-avvocato`.

La pagina del Portale dell'Avvocato conferma che il Processo Amministrativo Telematico usa il canale dedicato PAT/SIGA, distinto dal PST civile e penale. Per i depositi amministrativi IUSENTRA applica quindi queste regole:

- i moduli dei depositi di ricorsi e atti devono essere firmati in formato PAdES;
- la PEC usata per l'invio deve essere presente nel Registro Generale degli Indirizzi Elettronici;
- NRG, UID deposito e sede TAR/CdS restano identificativi PAT e non diventano codici ufficio PST;
- il portale operativo verificato è `https://pe.prod.cloud.giustizia-amministrativa.it`.

## Regole pagamenti accertate

Fonte di dettaglio salvata in
`docs/specs/ministero/PAGAMENTI_TELEMATICI_PST_PAT_PTT_2026-06-02.md`.

Le policy runtime vivono in `legal_deposit/payment_policies.py` e sono agganciate
ai profili canale:

- `pct_sicid`, `pct_siecic`, `sigp_gdp` e `unep`: policy
  `pst_pagopa_cu_diritti_spese`. Il documento prova tecnico è la `RT.xml`; il
  promemoria PDF non sostituisce la ricevuta telematica quando la RT è richiesta
  per il deposito. Codici riscossione censiti: `CONTRIB`, `DIRCANC`, `DIRCOPIA`,
  `CONTRBENI`, `UNPIG`, `UNNOT`.
- `pat_siga`: policy `pat_f24_elide_contributo_unificato`. Il deposito PAT
  presidia quietanza F24 Elide, data, estremi, importo, codice tributo, numero
  riga, elementi identificativi e copia informatica della quietanza.
- `ptt_sigit`: policy `ptt_cut_pagopa`. Per il CUT tributario pagoPA il SIGIT
  associa il pagamento al numero `RGR/RGA`; IUSENTRA non inventa allegati
  sostitutivi quando l'abbinamento è gestito dal portale.

Il software non calcola automaticamente importi o esenzioni del contributo
unificato senza fonte normativa aggiornata e dati del caso concreto verificati.

## Regola fail-closed

Il profilo generico PCT/PST non esiste piu' come scelta produttiva. `pct`, `pst` e `pct_pst` sono ambigui e bloccano il flusso: l'utente deve scegliere `pct_sicid`, `pct_siecic`, `sigp_gdp` o `unep` secondo registro e procedimento.

Un canale sconosciuto solleva `UnknownChannelError`. `portal_upload` puo' essere usato solo se richiesto come caricamento manuale e confermato, mai come fallback automatico.

## Limiti PTT/SIGIT

`ptt_sigit` applica i limiti tributari correnti registrati nel codice:

- singolo file massimo 10 MB;
- massimo 50 file;
- totale invio massimo 50 MB;
- nome file massimo 100 caratteri;
- PDF/A-1a o PDF/A-1b;
- firma digitale quando richiesta dal procedimento.

## Stati PDP esposti

Gli stati canonici PDP sono:

- `INVIATO`
- `IN_TRANSITO`
- `IN_FASE_DI_VERIFICA`
- `ACCOLTO`
- `RIGETTATO`
- `ERRORE_TECNICO`

Per compatibilita' con dati storici, IUSENTRA mantiene anche mapping legacy verso `IN_VERIFICA`, `ACCETTATO` e `RIFIUTATO` dove necessario.

## Fonti locali configurabili

Le prassi locali sono in `legal_rules/ppt_office_rules.json`.

La regola Palmi produce un avviso forte per CAdES `.p7m` e raccomanda PAdES `.pdf`, ma non invalida CAdES.

Le regole Locri, Taranto e Bari sono registrate come verifica informativa: ammettono PAdES e CAdES e non generano avviso forte.
