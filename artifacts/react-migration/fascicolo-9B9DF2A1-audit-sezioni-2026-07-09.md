# Audit fascicolo 9B9DF2A1 - sezioni, payload e UI

Data verifica: 09/07/2026, ambiente produzione `https://app.iusentra.it`, studio `studio-legale-giuseppe-montagnese`.

## Perimetro

- Fascicolo: `Spagnolo Sara c. MIM`, `RG 3950/2026`, riferimento interno `2026/308`.
- Controlli richiesti: caricamento fascicolo, Documenti, Attività processuali, Udienze/scadenze, Comunicazioni/Cancelleria, Contesto economico, Sentenze - controllo economico.
- Fonti confrontate: SQLite tenant `/data/tenants/studio-legale-giuseppe-montagnese/studio.db`, payload React `/api/v1/ui/fascicoli/9B9DF2A1`, UI reale nel browser integrato su produzione.

## Correzioni applicate

- Il dettaglio fascicolo non ricalcola più evidenze economiche/documentali durante l'apertura iniziale: usa il riepilogo persistito e lascia la lettura profonda ai presidi automatici.
- La sezione Documenti non richiama più il classificatore live per ogni riga: usa prima la classificazione salvata dal presidio, poi il tipo documento già salvato nel fascicolo.
- Il riepilogo Lex della sezione Documenti ora usa un riepilogo rapido tenant-aware sui documenti correnti, senza avviare automazioni sentenza in caricamento UI.
- In caso di hash duplicato Lex, il riepilogo preferisce il record `ready` e poi il record più recente.
- Attività processuali esclude comunicazioni di cancelleria e udienze già presidiate nelle rispettive sezioni dedicate.
- Il conteggio Comunicazioni/Cancelleria nella navigazione si allinea al conteggio deduplicato della sezione quando i dati lazy sono caricati.
- Il messaggio del presidio documenti non dice più "nessun testo indicizzato" quando Lex è pronto: indica che i documenti sono stati controllati e non risultano ulteriori termini processuali da presidiare.

## Esiti payload server

- Payload iniziale fascicolo: circa `1,3 s`, documenti non caricati nel main payload.
- Payload Documenti: circa `2,8 s`, `63` documenti.
- Payload Attività: circa `1,1 s`, `3` attività.
- Payload Udienze/scadenze: circa `1,2 s`.
- Payload Economia: circa `1,0 s`.
- Riepilogo Lex Documenti: `Totali 63`, `Pronti 63`, `In coda 0`, `In corso 0`, `Errori 0`, ultimo indice `08/07/2026 22:40` ora italiana.

## Esiti UI reale

- Apertura produzione del fascicolo osservata nel browser integrato: circa `2,5 s`.
- Documenti e atti: visibili, `63`, Lex `63/63`, ultimo indice valorizzato, ricorsi classificati come `Ricorso - atto principale`.
- Attività processuali: `3`, contiene assegnazione giudice, assegnazione sezione e iscrizione a ruolo; non contiene PEC di cancelleria.
- Udienze e scadenze: `3`, mostra udienza `13/01/2027` e presidio PEC collegato.
- Comunicazioni/Cancelleria: conteggio coerente `19` dopo deduplica UI.
- Contesto economico: mostra `Controllo economico € 21,50 Parziale`.
- Sentenze - controllo economico: mostra `Contributo unificato € 21,50 Pagato` con fonte `rt_15E000GLTO69C7671DZC7BGLQZXVYC2U73U.xml`.

## Test eseguiti

- `python -m py_compile web/services/react_fascicoli_bridge.py`
- `python -m pytest tests/test_fascicolo_detail_ux.py::test_dettaglio_fascicolo_espone_ux_documenti_e_cabina_collassabile tests/test_fascicoli_pagination.py::test_fascicolo_dettaglio_principale_include_quadro_operativo_e_tab_lazy -q`
- `pnpm --filter @iusentra/studio build:vite`
- Deploy Hetzner con profilo `deploy/hetzner` e verifica container `iusentra-app` healthy.
- Verifica visiva reale sul browser integrato in produzione.

## Limiti residui

- Il fascicolo contiene duplicazioni documentali storiche importate da fonti diverse; questa verifica ha corretto prestazioni, classificazione UI e sezioni, non ha effettuato cancellazioni dati.
- Il conteggio Comunicazioni/Cancelleria è deduplicato lato UI dopo il caricamento delle sezioni lazy; il dato è coerente a video dopo apertura sezione.
