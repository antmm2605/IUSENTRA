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

---

# Run #5 (2026-07-04) — connettori dettagli sentenze e archivi locali verificati

Esecuzione: run #5 del workflow (commit `5b7c907d`, v2.253.171), auto-innescata dal push.
Il job ha atteso il deploy dello stesso commit nel container (12'47"), poi fase 1 in 54s e
fase 2 in 65s — **tutti gli step verdi**, artifact `lex-web-cycle-memoria` sulla run.
Le run intermedie: #2 ha rivelato i blocchi anti-bot IPZS (P5 auto-generata → connettore
archivi locali della v2.253.169), #3 è fallita per la race deploy/run (fix v2.253.170),
#4 ha verificato il connettore archivi.

## Fase 1 — il composito «archivi locali → corpus → web» al lavoro: exit 0

```
Modalità: web | Cicli: 1 | Arresto: raggiunto il numero massimo di fonti (10)
Domande generate: 5 | Query eseguite: 2 | Fonti lette: 10 | Respinte: 0
Nuovi termini: 43 | Nuove citazioni: 86 | Letture: 10 | Lacune: 18 | Proposte: 2
```

La novità rispetto alla run #1: le prime letture arrivano dal **mirror locale
Normattiva/GU** (`archivio_locale:gazzetta_ufficiale`, 4 candidati nel riepilogo), zero
rete e immune ai blocchi anti-bot. Dalla query `L. 300/1970 site:normattiva.it` (nata dal
campione lavoro) sono entrate Gazzette fresche di maggio/giugno 2026 (Serie Generale
n. 125 dell'1/6, n. 120 del 26/5, n. 96 del 27/4 + S.O. 17) con citazioni normalizzate
reali: `L. 20 maggio 1970, n. 300`, `D.Lgs. 10 agosto 2018, n. 101`,
`Regolamento (UE) 2016/679`, `direttiva (UE) 2019/1152`. Trust: `tier_1 /
istituzionale_o_primaria / score 1.0` su ogni lettura.

`LocalCorpusSearchProvider` (corpus giurisprudenza) è in catena ma non ha prodotto
candidati: il corpus di produzione è ancora vuoto — si popola man mano che i motori
giurisprudenza verificano sentenze. Comportamento fail-closed confermato: nessun DB
creato, nessun errore.

## Fase 2 — drill-down dei dettagli Cassazione: i TESTI delle decisioni

Il nuovo passo ha estratto **4 href di dettaglio** dalle due liste ufficiali
(`giurisprudenza_civile.page` + `giurisprudenza_penale.page`) e ne ha letti 2 unici
(dedup sugli href duplicati delle liste):

| Dettaglio | Area | Esito | Caratteri | Citazioni |
|---|---|---|---|---|
| `civile_dettaglio.page?contentId=SZC51228` | civile | ok | 3.955 | **18** |
| `penale_dettaglio.page?contentId=SZP51291` | penale | ok | 4.315 | **12** |

È il salto di qualità chiesto: non più solo le liste-vetrina ma il **contenuto della
singola decisione** (30 citazioni normalizzate estratte dai due provvedimenti), il
materiale con cui si costruiscono le strategie di causa.

Seed diretti: 8/12 ok (liste Cassazione civile/penale, Consulta, G.A., Garante,
Agenzia Entrate, INPS); Normattiva ×3 e listing GU `robots_blocked` live (IPZS,
fail-closed — è esattamente il buco che il connettore archivi locali copre in fase 1);
EUR-Lex `empty_text` sullo stesso URL CELEX che nella run #1 aveva reso 387K caratteri
(risposta server intermittente, es. interstitial: gestita fail-closed, nessun
apprendimento da testo vuoto).

## Memoria finale (artifact)

`legal_terms: 155 · citations: 361 · source_readings: 24 · source_profiles: 16 ·
unknown_concepts: 18 · research_questions: 5 · learning_signals: 9 ·
improvement_proposals: 8 · trust_assessments: 24`

Le proposte scendono da 68 (run #1) a **8**: le stop-word estese della v2.253.168 hanno
tolto il rumore dai bigrammi («accesso civico» resta, «trattamento nonché» sparisce).
Tra le 8: la P4 attesa su «accesso civico» e la P5 sul connettore Normattiva (gli
archivi locali la soddisfano già per la normativa; resta aperta per il fetch live).
Tutte con `requires_human_review: true`.

## Stato dei connettori a valle delle 5 run

| Canale | Stato | Copertura |
|---|---|---|
| Archivi locali Normattiva/GU (mirror notturni) | ✅ verificato (run #4, #5) | normativa + Gazzette, zero rete |
| Corpus giurisprudenza locale (`can_cite_sentenza`) | ✅ in catena, fail-closed | massime verificate (si popola con l'uso) |
| Drill-down dettagli Cassazione (fase 2) | ✅ verificato (run #5) | testi delle decisioni civile/penale |
| Ricerca web governata + seed diretti | ✅ verificato (run #1, #5) | Cassazione, Consulta, G.A., Garante, AE, INPS |
| Normattiva/GU live | ⛔ robots IPZS (fail-closed) | coperto dagli archivi locali |
| EUR-Lex testo integrale | ⚠️ `empty_text` intermittente (run #5; ok in run #1 con 387K caratteri) | GDPR e atti UE via CELEX |
