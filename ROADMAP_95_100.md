# Roadmap verso 95/100

## Stato dopo blocchi 1-4
Se hai applicato tutti i blocchi:
- governance migliorata
- security docs solide
- CI più severa
- packaging più stabile
- CLI coverage meno duplicate
- Local Signer preparato al refactor incrementale
- quality gates AI/performance introdotti

## Cosa ti porta a 95/100
### 1. Qualità misurabile Lex
Devi pretendere sempre:
- risposta non vuota
- citazioni/fonte quando il task lo richiede
- latenza sotto soglia per casi standard
- fallback esplicito
- niente risposta “allucinata” senza base

### 2. Performance con budget
Ogni release deve avere:
- benchmark smoke
- budget massimo di latenza
- controllo regressioni

### 3. Refactor progressivo, non distruttivo
I moduli più pesanti vanno spezzati solo dove hai già confini naturali:
- Local Signer: security / AI / bootstrap / PST dispatch
- Lex: orchestrator / retrieval / evaluation / telemetry
- web: route / service / repository

### 4. Policy release
Nessuna release senza:
- CI verde
- governance check
- Python baseline check
- Local Signer boundary check
- Lex quality gates
- performance budget check

## Cosa manca per 100/100
Onestamente, il 100/100 non è un file in più.
È:
- mesi di disciplina
- regressioni quasi azzerate
- telemetria reale in produzione
- suite test completa sui moduli critici
- manutenzione costante delle integrazioni telematiche

## Valutazione onesta
Con i 4 blocchi applicati bene:
- Architettura: 9/10
- CI/Governance: 9/10
- Sicurezza base: 8.5/10
- Affidabilità: 8.5/10
- Visione prodotto: 9.5/10
- Maturità repo complessiva: 95/100
