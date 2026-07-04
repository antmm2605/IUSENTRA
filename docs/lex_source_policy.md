# Lex — Policy delle fonti per l'apprendimento autonomo

Aggiornato: 2026-07-02. Questa pagina descrive come il ciclo autonomo
(`lex/autonomy`) decide **quali fonti può leggere e con quale peso**. La policy
NON è definita qui: vive nei cataloghi governati già esistenti — questa è la
guida operativa al loro uso.

## Gerarchia delle fonti (tier governati)

Fonte di verità: `lex/research/source_policy/catalog.py` (facciata pubblica
`ai_lex_sources.py`) — 20 aree del diritto, ciascuna con liste di domini per tier.

| Tier | Significato | Peso (`SOURCE_WEIGHTS`) | Esempi |
|---|---|---|---|
| `tier_1` | Fonte primaria ufficiale | 1.0 | Normattiva, Gazzetta Ufficiale, Corte costituzionale, Cassazione, EUR-Lex, Garante Privacy |
| `tier_2` | Istituzionale secondaria | 0.72 | autorità di settore, documentazione istituzionale |
| `tier_3` | Contesto professionale | 0.32 | dottrina/manualistica autorevole: MAI verità primaria |
| `unknown` | Non classificata | 0.08 | blog, forum, social, siti commerciali: mai autorevoli |

Il registro fonti governato (`lex/research/source_registry.py`,
`sources_registry.yaml`) aggiunge per ogni fonte: `official`, `trust_class` A/B,
`requires_credentials`, `requires_registration`, `restricted`,
`supports_public_web_search`.

## Decisione di ammissione (`lex/sources/trust.py::assess_source`)

Ordine fail-closed (la prima regola che scatta decide):

1. **denylist** configurata → mai ammessa (vince su tutto);
2. fonte `restricted` nel registro → mai ammessa;
3. `requires_credentials` **e** non leggibile pubblicamente → mai ammessa
   (es. banche dati riservate). Fonti come EUR-Lex, che richiedono registrazione
   solo per l'API ma restano pubblicamente leggibili, sono ammesse con warning;
4. **allowlist** configurata e dominio fuori lista → esclusa, `requires_review`;
5. `require_official_sources=true` (default) → ammessi solo `tier_1`/`tier_2`;
6. `tier_3` ammesso SOLO con `require_official_sources=false`, marcato
   `requires_review` e mai usato come verità primaria;
7. `unknown` → mai ammesso per l'apprendimento.

Ogni valutazione è persistita in `trust_assessments.jsonl` con motivazioni.

## Cortesia di accesso (`lex/sources/polite_fetcher.py`)

- **robots.txt rispettato sempre**, con cache per dominio. Semantica:
  2xx → si applica il file; 4xx → accesso consentito (standard de facto);
  **errore di rete o 5xx → accesso NEGATO (fail-closed)**: nel dubbio non si scarica.
- **Rate-limit per dominio**: intervallo minimo configurabile
  (`politeness.min_interval_seconds`, ≥1s obbligatorio in modalità web), che si
  somma al delay di cortesia del client HTTP condiviso.
- **Tetto dimensione** (`max_bytes`, ≤5MB) su Content-Length e corpo.
- **Solo URL pubbliche** http/https: IP privati, loopback e host locali rifiutati.
- User-agent chiaro e identificabile; nessun cookie sensibile, nessuna credenziale,
  nessun retry aggressivo, nessun bypass di paywall.

## Regole non negoziabili

- Contenuti generati dagli utenti (blog, forum, social) non sono MAI fonti
  autoritative: al più contesto, mai base di una citazione.
- Nessun dato personale reale nei campioni, nei test o nelle query: il
  `query_builder` costruisce le query SOLO da campi strutturati (norma
  normalizzata, termine, area), mai dal testo libero.
- Ogni riferimento normativo/giurisprudenziale usato da Lex deve essere
  tracciabile a una fonte con tier noto; se le fonti mancano il ciclo registra
  la lacuna (`unknown_concepts`) invece di inventare.

## Archivi ufficiali locali (mirror sanzionati)

Per Normattiva e Gazzetta Ufficiale il ciclo legge PRIMA dagli archivi locali
(scaricati ogni notte dal job `legal_official_archives_daily` tramite i canali
ufficiali OpenData): zero traffico verso il sito live e nessun attrito con le
protezioni anti-bot (che nella run reale #2 hanno bloccato i fetch diretti —
gestiti fail-closed). Regola di provenienza: il contenuto viene dal mirror, ma
l'ancora di fiducia è sempre l'URL ufficiale del documento (URN risolto sul
dominio normattiva.it) e la valutazione tier resta quella del dominio reale;
un contenuto senza ancora ufficiale non entra in memoria.

## Come proporre nuove fonti

Il ciclo stesso genera `ImprovementProposal` quando incontra domini ufficiali non
classificati (P2) o domini tier_1 bloccati da robots (P5 → connettore dedicato in
`lex/sources/connectors`). Le proposte richiedono sempre revisione umana; le
modifiche ai cataloghi (`SOURCE_POLICIES`, `sources_registry.yaml`) seguono il
normale flusso di review del repository.
