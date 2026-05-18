# App V2 handover

Aggiornato: 2026-05-14, fase 12 `fasereact`.

App V2 e' la shell React progressiva di IUSENTRA. Convive con le route Flask storiche e usa API Flask reali, feature flag per rollout/rollback, RBAC e isolamento tenant lato backend.

## Stato reale

- Registro route: [app-v2-page-registry](app-v2-page-registry.md).
- Riepilogo frontend: [frontend-app-v2-pages](frontend-app-v2-pages.md).
- Requisiti area: [app-v2-area-requirements](app-v2-area-requirements.md).
- Test plan: [test-plan-app-v2](test-plan-app-v2.md).

Sintesi corrente dai registri generati:

- route manifest: 98;
- priorita: P0=30, P1=33, P2=35;
- aree: `complete_tested`=4, `complete_unverified`=4, `partial`=6, `blocked`=1;
- Storybook: presente come infrastruttura frontend, non gate visuale completo; VRT: non attivo, gap documentato;
- smoke autenticati: richiedono env dedicate, non sono marcati verdi se assenti.

## Regole App V2

1. Una pagina App V2 gia' operativa parte attiva di default ed e' spegnibile con flag `routes.appV2.*` per rollback.
2. Una capability non parificata o sensibile parte default-off; il frontend non carica dati della pagina quando il flag e' spento.
3. Il backend resta fonte autoritativa per auth, RBAC, tenant e validazioni.
4. Il fallback legacy resta solo se governato e non deve diventare CTA primaria.
5. Una pagina `partial`, `pending`, `blocked` o `complete_unverified` non va descritta come completa.
6. Le route ministeriali/telematiche non parificate restano protette.

## Routing

Le route ufficiali React gia' promosse possono vivere su path legacy come `/fascicoli` o `/impostazioni`. La shell sperimentale vive su `/app` e `/app-v2`.

Il redirect legacy -> App V2 e' ammesso solo se:

- esiste mapping in `web/services/app_v2_routing.py`;
- il target e' interno;
- il flag pagina e' acceso;
- query pericolose sono rimosse;
- auth/RBAC/tenant sono gia' risolti prima dei dati.

## Feature flag

Fonte runtime: `web/services/feature_flags.py`.

Fonte frontend: `frontend/src/lib/featureFlags.ts`.

Documentazione: [feature-flags](feature-flags.md).

Rollback rapido: spegnere il flag, riavviare app/worker, verificare `/api/v1/ui/feature-flags`, smoke routing/workflow.

## Checklist nuova pagina

- [ ] Route censita in `tools/react-migration/route-manifest.json`.
- [ ] Feature flag `routes.appV2.<area>.<pagina>` default-off finche' la superficie non e' verificata come operativa.
- [ ] Menu/sidebar nascosti se flag spento o permesso mancante.
- [ ] API JSON reale o esplicita assenza API per superficie read-only.
- [ ] Backend auth, RBAC e tenant isolation.
- [ ] Nessun `tenant_id`, `studio_id`, token o path accettato dal client.
- [ ] Stati UI: loading, empty, error, forbidden, flag-off, readonly, success se mutazione.
- [ ] Test frontend, test backend, flag on/off, RBAC/tenant, OpenAPI se API.
- [ ] Browser smoke desktop/tablet/mobile se pagina user-facing importante.
- [ ] Documenti e registry aggiornati/generati.
- [ ] Rollback con flag o fallback chiaro.

## Checklist nuova rotta API

- [ ] Endpoint in Flask con autenticazione.
- [ ] Permission dominio e audit quando scrive o legge dati sensibili.
- [ ] Tenant context server-side, fail-closed in multi-studio.
- [ ] Validazione input e schema errore normalizzato.
- [ ] OpenAPI aggiornata tramite `generate_api_contracts.py`.
- [ ] Provider verification aggiornata o limite documentato.
- [ ] Test `401`, `403`, `400/422`, success path sicuro.
- [ ] Nessun segreto, token, password hash, path filesystem o PII non necessaria nel payload.

## Checklist nuovo componente

- [ ] Usare componenti IUSENTRA/shadcn esistenti quando disponibili.
- [ ] Testi italiani e non tecnici.
- [ ] Icone `lucide-react` se serve un'icona.
- [ ] Nessun dato demo o hardcoded come reale.
- [ ] Layout responsive senza spazio morto anomalo.
- [ ] Focus, label, aria-label e stati disabled/readonly.
- [ ] Chiamate API tramite client esistente e gestione errori controllata.

## Pending e blocked

Le aree partial/blocked sono intenzionali. In particolare i servizi telematici non parificati, download ministeriali, allegati, export e workflow tecnici restano protetti finche' non hanno parita React, dati reali, test, browser smoke e rollback.
