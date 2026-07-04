# Lex — Prima prova reale del ciclo autonomo in modalità web (2026-07-04)

Esecuzione: workflow "Lex ciclo web" run #1 (GitHub Actions → container di produzione
`iusentra-app` su Hetzner), commit `9317cd9c`, durata 90 secondi, **tutti gli step verdi**.
Memoria solo in `/tmp` del container (pulita a fine run), `/data` mai toccato; artifact
`lex-web-cycle-memoria` disponibile 14 giorni sulla run.

## Esito in sintesi

**La modalità web governata funziona end-to-end in produzione.** Il ciclo ha cercato,
valutato, letto e appreso da fonti ufficiali REALI, rispettando robots.txt e rate-limit,
senza una sola violazione di policy (0 fonti respinte, 0 `robots_blocked`).

## Fase 1 — ciclo web puro (ricerca governata): exit 0

```
Modalità: web | Cicli: 1 | Arresto: raggiunto il numero massimo di fonti (10)
Domande generate: 5 | Query eseguite: 2 | Fonti lette: 10 | Respinte: 0
Nuovi termini: 85 | Nuove citazioni: 194 | Letture: 10 | Lacune: 18 | Proposte: 2
```

Esempio del funzionamento: dal campione "lavoro" il gap detector ha rilevato la norma
`L. 300/1970` citata ma mai letta → domanda «Cosa stabilisce L. 300/1970?» → query
`L. 300/1970 site:normattiva.it` → lettura di pagine reali Normattiva (tra i profili
fonte: «LEGGE 24 maggio 1970, n. 336 — Normattiva», «DECRETO LEGISLATIVO 7 maggio 2026,
n. 96 — Normattiva»). La ricerca governata (`official_web`) ha funzionato dal server:
10 fonti lette con sole 2 query.

## Fase 2 — lettura diretta delle fonti seminate (valore forense): 10/11 ok

| Fonte | Area | Esito | Caratteri | Citazioni |
|---|---|---|---|---|
| Normattiva — art. 2043 c.c. (URN) | civile | `too_large` (>2MB: l'URN restituisce l'intero c.c.) | — | — |
| Normattiva — L. 241/1990 | amministrativo | ok | 5.562 | 8 |
| **Normattiva — D.Lgs. 149/2022 (Cartabia)** | civile | ok | 19.035 | **64** |
| Gazzetta Ufficiale — ultime pubblicazioni | civile | ok | 2.825 | 1 |
| **Corte di Cassazione** | civile | ok | 13.165 | 64 |
| Corte costituzionale | civile | ok | 9.005 | 35 |
| Giustizia amministrativa | amministrativo | ok | 9.228 | 64 |
| **EUR-Lex — GDPR (CELEX 32016R0679)** | privacy | ok | **387.678** | 64 |
| Garante Privacy | privacy | ok | 28.042 | 64 |
| Agenzia delle Entrate | tributario | ok | 3.668 | 2 |
| INPS | lavoro | ok | 54.577 | 64 |

L'unico esito non-ok è il tetto byte sul c.c. intero: comportamento fail-closed corretto
(per gli articoli singoli servirà un URN puntuale o un connettore dedicato — proposta
tracciata).

## Cosa ha acquisito di utile per lo studio

- **Decreti e leggi appena pubblicati**: dalla lettura Normattiva/GU sono entrate in
  memoria citazioni normalizzate di norme **fresche del 2026** — es. `D.L. 22 maggio
  2026, n. 89`, `D.Lgs. 16 aprile 2026, n. 83`, `D.Lgs. 29 aprile 2026, n. 86`,
  `D.Lgs. 7 maggio 2026, n. 91` — esattamente il flusso "novità normative" utile al
  lavoro quotidiano.
- **Riforma Cartabia alla fonte**: il testo del D.Lgs. 149/2022 letto da Normattiva con
  64 riferimenti estratti (termini processuali per la strategia difensiva).
- **Giurisprudenza**: home/novità di Cassazione, Consulta e Giustizia amministrativa
  raggiunte e indicizzate (le DECISIONI sono il materiale per le strategie di causa; i
  calendari d'udienza dei fascicoli restano dominio PST/polisWeb già coperto dal
  gestionale).
- **GDPR integrale** (387K caratteri da EUR-Lex) con 318 osservazioni terminologiche.

## Memoria finale (artifact)

`legal_terms: 488 · citations: 548 · source_readings: 21 · source_profiles: 16 ·
unknown_concepts: 18 · research_questions: 5 · learning_signals: 9 ·
improvement_proposals: 68 · trust_assessments: 21`

Trust: tutte le fonti lette valutate `tier_1 / istituzionale_o_primaria / score 1.0`.

## Proposte generate (revisione umana obbligatoria, mai auto-applicate)

68 proposte, in prevalenza P4 (nuovi concetti per l'ontologia): accanto a candidati
sensati («accesso civico», «danno subito») compaiono candidati rumorosi dal testo
integrale del GDPR («trattamento tale», «trattamento nonché») — il sistema propone con
onestà e il filtro resta umano. Miglioramento futuro tracciato: stop-word aggiuntive nel
raccoglitore di bigrammi per i testi normativi lunghi.

## Limiti osservati (onesti)

1. URN Normattiva di un singolo articolo può restituire l'intero codice → `too_large`
   fail-closed; serve un connettore dedicato (proposta P5-like già prevista).
2. Il raccoglitore di termini candidati produce rumore sui testi normativi integrali
   (bigrammi con congiunzioni): da raffinare con stop-word estese.
3. Le homepage istituzionali danno testo "vetrina": utile per reachability/trust e
   novità, meno per contenuto profondo — i connettori per liste/sentenze specifiche
   sono il passo successivo naturale.

## Riferimenti

- Workflow: `.github/workflows/lex-web-cycle.yml` (manuale da Actions; auto-run quando
  il file cambia sul branch di sviluppo).
- Config: `examples/lex_autonomous_config_web.json` (18 domini tier_1/tier_2 verificati).
- Architettura: `docs/lex_autonomous_learning.md`, policy fonti: `docs/lex_source_policy.md`.
