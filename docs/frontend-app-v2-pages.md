# Pagine frontend App V2

Aggiornato: 2026-05-13, fase 2 `fasereact`.

Questo documento e' il riepilogo operativo del registro completo in `docs/app-v2-page-registry.md`. Le route sperimentali App V2 restano sotto feature flag default-off; le route ufficiali gia' React restano governate dal manifest e dal route gate.

## Shell App V2

| Path | Etichetta | Famiglia | API | Feature flag |
| --- | --- | --- | --- | --- |
| /app | Regia | regia | /api/v1/ui/dashboard | nessuno |
| /app/regia | Regia | regia | /api/v1/ui/dashboard | nessuno |
| /app/fascicoli | Fascicoli | fascicoli | /api/v1/ui/fascicoli | routes.appV2.caseFiles |
| /app/fascicoli/:id | Dettaglio fascicolo | fascicoli | /api/v1/ui/fascicoli/:id | routes.appV2.caseFiles |
| /app/anagrafiche | Clienti | anagrafiche | /api/v1/ui/clienti | nessuno |
| /app/agenda | Agenda | agenda | /api/v1/ui/agenda | routes.appV2.agenda |
| /app/mandato | Mandato | mandato | /api/v1/ui/preventivi | nessuno |
| /app/documenti | Documenti | documenti | /api/v1/ui/template-atti | routes.appV2.docsPanel |
| /app/telematico | Telematico | telematico | /api/v1/ui/telematico | nessuno |
| /app/comunicazioni | Comunicazioni | comunicazioni | /api/v1/ui/messaggi | routes.appV2.commsDeposits |
| /app/lex | Lex | lex | /api/v1/ui/legal-intelligence | nessuno |
| /app/amministrazione | Amministrazione | amministrazione | /api/v1/ui/amministrazione | nessuno |
| /app/impostazioni | Impostazioni | impostazioni | nessuna API dedicata | nessuno |

## Alias legacy verso App V2

| Legacy | Target App V2 |
| --- | --- |
| /agenda | /app/agenda |
| /agenda/nuovo | /app/agenda?drawer=evento |
| /audit | /app/amministrazione?tab=audit |
| /backup | /app/impostazioni?tab=backup |
| /clienti | /app/anagrafiche?tab=clienti |
| /compensi-forensi | /app/mandato?tab=compensi |
| /documenti | /app/documenti |
| /email | /app/comunicazioni?tab=email |
| /fascicoli | /app/fascicoli |
| /fascicoli/nuovo | /app/fascicoli?drawer=nuovo |
| /fatturazione | /app/mandato?tab=fatturazione |
| /impostazioni | /app/impostazioni |
| /impostazioni-studio | /app/impostazioni |
| /impostazioni/calendario | /app/impostazioni?tab=calendari |
| /incassi-pagamenti | /app/mandato?tab=incassi |
| /messaggi | /app/comunicazioni?tab=messaggi |
| /preventivi | /app/mandato?tab=preventivi |
| /preventivi/nuovo | /app/mandato?tab=nuovo-preventivo |
| /preventivi/wizard | /app/mandato?tab=wizard |
| /profili | /app/amministrazione?tab=profili |
| /redazione-atti | /app/documenti?tab=redazione |
| /regia-operativa | /app/regia |
| /registro-attivita | /app/amministrazione?tab=registro |
| /scadenziario | /app/agenda?tab=scadenze |
| /sincronizzazione-calendari | /app/impostazioni?tab=calendari |
| /soggetti | /app/anagrafiche?tab=soggetti |
| /tariffario | /app/mandato?tab=tariffario |
| /telematico | /app/telematico |
| /template-atti | /app/documenti?tab=template |
| /utenti | /app/amministrazione?tab=utenti |
| /workspace-intelligente | /app/regia |

## Backlog per priorita

### P0

| Route | Famiglia | Stato | Rischio | Target React | Blocco principale |
| --- | --- | --- | --- | --- | --- |
| /admin/osservabilita | amministrazione | legacy | high | /app/amministrazione | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /checklist | documenti | legacy | high | /app | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /compensi-forensi/* | mandato | legacy | high | /app/mandato?tab=compensi | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /database | amministrazione | legacy | high | /app/amministrazione | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /fatturazione/* | economico | legacy | high | /app/mandato?tab=fatturazione | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /giurisprudenza/* | documenti | legacy | high | /app/lex | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /giurisprudenza/nuova | documenti | legacy | high | /app/lex | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /guida/firma-digitale | telematico | legacy | critical | /app/telematico | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /legal-intelligence/* | documenti | legacy | high | /app/lex | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /pat | telematico | legacy | critical | /app/telematico | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /pdp | telematico | legacy | critical | /app/telematico | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /polisWeb | telematico | legacy | critical | /app/telematico | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /portali/* | telematico | legacy | critical | /app/telematico | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /preventivi/* | mandato | legacy | high | /app/mandato?tab=preventivi | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /preventivi/wizard | mandato | parziale | high | /app/mandato?tab=wizard | flag on/off, azioni JSON mancanti, browser desktop/tablet/mobile |
| /redazione-atti/* | documenti | legacy | high | /app/documenti?tab=redazione | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /ricerca-legale/* | documenti | legacy | high | /app/lex | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /scadenziario/:id/modifica | scadenze | parziale | high | /app/scadenziario/:id/modifica | flag on/off, azioni JSON mancanti, browser desktop/tablet/mobile |
| /servizi-telematici | telematico | legacy | critical | /app/telematico | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /sigit | telematico | legacy | critical | /app/telematico | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /sigp | telematico | legacy | critical | /app/telematico | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /sigp-sync | telematico | legacy | critical | /app/telematico | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /sito-studio/redazione-ai | studio | parziale | high | /app/amministrazione?tab=studio-redazione-ai | flag on/off, azioni JSON mancanti, browser desktop/tablet/mobile |
| /tariffario/* | mandato | legacy | high | /app/mandato?tab=tariffario | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /telematico | telematico | legacy | critical | /app/telematico | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /template-atti/* | documenti | legacy | high | /app/documenti?tab=template | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /template-atti/nuovo | documenti | legacy | high | /app/documenti?tab=template | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |
| /tribunali | telematico | legacy | critical | /app/telematico | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |

### P1

| Route | Famiglia | Stato | Rischio | Target React | Blocco principale |
| --- | --- | --- | --- | --- | --- |
| /applicazioni | amministrazione | legacy | medium | /app/amministrazione | feature flag dedicato, API JSON, RBAC/tenant test e smoke prima della promozione |

### P2

Nessuna route pendente in questa priorita.

### P3

Nessuna route pendente in questa priorita.

## Smoke e gate fase 2

Comandi introdotti o governati dalla fase 2:

```powershell
python scripts\react-migration\generate_app_v2_page_registry.py --check
python scripts\smoke_app_v2_pages.py --list
python -m pytest -q tests/test_app_v2_page_registry.py --tb=short
```

Per smoke autenticati usare variabili ambiente, senza credenziali nel repository:

```powershell
$env:IUSENTRA_BASE_URL='https://app.iusentra.it'
$env:IUSENTRA_SMOKE_USERNAME='<utente>'
$env:IUSENTRA_SMOKE_PASSWORD='<password>'
python scripts\smoke_app_v2_pages.py --require-credentials
```

## Stato fase 2

La fase 2 completa il censimento, la priorizzazione e i gate documentali/smoke. Le route non full restano esplicitamente backlog: non vengono dichiarate complete e saranno trattate nelle fasi successive solo dopo API reali, RBAC, tenant isolation, test e browser verification.
