# Profili canale deposito

La firma non e' applicata "all'intero pacchetto" in modo indistinto: IUSENTRA usa una `SignaturePolicy` per canale.

## Canali supportati

| Codice | Nome | Invio diretto | Upload manuale | Firma |
| --- | --- | --- | --- | --- |
| `pct_pst` | PCT/PST civile | Si, PEC | No | CAdES sull'atto principale |
| `pec_stragiudiziale` | PEC stragiudiziale | Si | No | Non obbligatoria |
| `notifiche_pec` | Notifiche PEC | Si | No | Policy canale |
| `pat_siga` | PAT/SIGA | No | Si | Policy canale |
| `ptt_sigit` | PTT/SIGIT | No | Si | Policy canale |
| `pdp_penale` | PDP Penale | Tramite client PDP se abilitato | Si | PAdES o CAdES secondo regola ufficio |
| `upload_manuale_guidato` | Upload manuale guidato | No | Si | Facoltativa/policy canale |
| `portal_upload` | Portale generico | No | Si | Facoltativa/policy canale |

I canali PAT, PTT e portali generici sono predisposti come preparazione e upload guidato: non fingono automazioni non disponibili o non autorizzate.

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
