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
| `pat_siga` | PAT/SIGA | No | Si | Policy canale |
| `ptt_sigit` | PTT/SIGIT | No | Si | Policy canale |
| `pdp_penale` | PDP Penale | Tramite client PDP se abilitato | Si | PAdES o CAdES secondo regola ufficio |
| `upload_manuale_guidato` | Upload manuale guidato | No | Si | Facoltativa/policy canale |
| `portal_upload` | Portale generico manuale | No | Si | Facoltativa/policy canale |

I canali PAT, PTT, SIGP, UNEP e portali manuali sono predisposti come preparazione e upload guidato: non fingono automazioni non disponibili o non autorizzate.

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
