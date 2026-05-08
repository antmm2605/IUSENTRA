# LEX — Response Quality Guard (v2.200.0)

Sistema a due guard per garantire la qualità professionale delle risposte Lex.

## Architettura

```
LexOrchestrator
    ├── EvidenceRelevanceGuard   → filtra fonti irrilevanti per workflow
    └── LegalAnswerQualityGuard  → blocca risposte non conformi agli standard professionali
```

## EvidenceRelevanceGuard

File: `lex/guards/evidence_relevance_guard.py`

Controlla che le evidenze recuperate siano pertinenti al workflow corrente.

### Logica per workflow

| Workflow | Fonti rilevanti | Fonti irrilevanti | Azione |
|----------|----------------|-------------------|--------|
| `drafting_legal_letter`, `lettera`, `bozza_lettera`, `atto`, `bozza_atto`, `pec_comunicazioni` | diffida, messa in mora, lettera, sollecito, PEC, modello, formula, art. 1219 | sentenza n., Cass. Civ., Gazzetta Ufficiale, d.lgs., legge n. | Warning se irrilevanti senza rilevanti |
| `termini_processuali` | termine, scadenza, giorni, art. 325, art. 641, c.p.c., decadenza, perentorio | giurisprudenza, sentenza, massima, rassegna | Warning se solo giurisprudenza |
| `deposito_telematico`, `telematico_status`, `compliance` | deposito telematico, PST, PDP, PAT, busta, firma, CAdES, PDF/A | — | Warning se nessuna fonte tecnica specifica |

### Output: GuardVerdict

```python
GuardVerdict(
    allowed=True,           # sempre True — non blocca, solo avverte
    warnings=["..."],       # lista avvertenze
    risk_level="medium",    # "low" | "medium" | "high"
)
```

## LegalAnswerQualityGuard

File: `lex/guards/legal_answer_quality_guard.py`

Pipeline a 6 stadi che può bloccare (`allowed=False`) la risposta prima che arrivi al cliente.

### Pipeline di controllo

```
Stadio 1: Disclaimer "consulta un avvocato"
    → allowed=False, risk_level="high"
    
Stadio 2: Formule da chatbot
    → allowed=False, risk_level="medium"
    
Stadio 3: JSON non richiesto (solo workflow non tecnici)
    → allowed=False, risk_level="medium"
    
Stadio 4: Output in inglese (solo workflow di redazione)
    → allowed=False, risk_level="high"
    
Stadio 5: Formule generiche conversazionali
    → warning (non blocca da solo)
    
Stadio 6: Workflow legali — verifica fonti e limiti
    → può bloccare se generiche + nessuna fonte citata
```

### Marker bloccanti

**Disclaimer vietati (Stadio 1):**
- "ti consiglio di consultare un avvocato"
- "consulta un avvocato"
- "rivolgiti a un avvocato"
- "non posso fornire consulenza legale"
- "non sono un avvocato"
- "questo non costituisce consulenza"
- "è sempre consigliabile consultare"
- (+ 7 varianti)

**Formule chatbot vietate (Stadio 2):**
- "spero di essere stato utile"
- "resto a disposizione"
- "non esitare a contattarmi"
- "fammi sapere se hai altre domande"
- "sono felice di aiutarti"
- (+ 3 varianti)

**Frammenti inglesi vietati in redazione (Stadio 4):**
- "dear recipient", "dear sir", "dear madam"
- "i am writing to", "please be advised"
- "in accordance with", "pursuant to"
- "notwithstanding", "whereas", "hereinafter"
- (+ 6 varianti)

### Metadata draft annotati

Quando la guard rileva problemi, aggiunge al `draft.metadata`:

```python
{
    "legal_quality_guard_applied": True,
    "legal_quality_warnings": ["Risposta contiene disclaimer vietati...", ...]
}
```

## Regole non negoziabili

1. Lex **non dice mai** "consulta un avvocato" o varianti
2. Lex **non usa** formule da chatbot generiche
3. Lex **non produce** output in inglese per workflow di redazione italiana
4. Lex **non produce** JSON non richiesto per workflow non tecnici
5. Lex **non inventa** riferimenti giurisprudenziali (norm `no_invented_references`)

## Integrazione con orchestratore

```python
# Nel ciclo run_workflow:
verdict = guard_orchestrator.check(
    workflow=workflow,
    draft=draft,
    evidence=evidence,
)
if not verdict.allowed:
    # rigenerazione o fallback
    ...
```
