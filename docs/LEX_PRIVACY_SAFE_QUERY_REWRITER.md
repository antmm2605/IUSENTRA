# Lex — Privacy-Safe Query Rewriter

**Modulo:** `lex/research/privacy_safe_query_rewriter.py`
**Versione:** 1.0.0
**Data:** 2026-05-08

---

## 1. Scopo

Il Privacy-Safe Query Rewriter risolve un problema strutturale: la query originale dell'utente — che può contenere dati personali, nomi propri, riferimenti a fascicoli specifici — non può essere trasmessa ai canali di ricerca pubblica (web ufficiale, Local Deep Research) così com'è.

Il rewriter separa in modo netto il contesto privato dalla materia giuridica pubblica. Produce quattro varianti della query originale ottimizzate per canali diversi, calcola il livello di sensitività della richiesta e determina quali canali possono essere attivati.

**Principio invariante:** la `public_research_query` non contiene mai dati personali. La `private_context_query` non lascia mai il perimetro del tenant (viene usata solo per il retrieval interno).

---

## 2. Pipeline di riscrittura (6 step)

```
Query originale dell'utente
        |
        v
  STEP 1: Classificazione privacy
  PrivacyGuard.classify_text(query)
  → sensitivity: public | internal | sensitive | highly_sensitive
        |
        v
  STEP 2: Estrazione nomi propri
  _extract_proper_names(query)
  → lista: ["Rossi", "Mario Bianchi", ...]
  (locuzioni esplicite: "contro X", "Sig. X" → alta confidenza)
  (nomi generici: parole con iniziale maiuscola non-keyword → bassa confidenza)
        |
        v
  STEP 3: Build private_context_query
  _build_private_context_query(query)
  → redacta CF, IBAN, email, telefono, RG
  → mantiene nomi propri (servono per cercare nei fascicoli)
  → aggiunge hint: [fascicolo:ID] e [allegati: N] se presenti
        |
        v
  STEP 4: Build public_research_query
  _redact_identifiers(query) → rimuove CF, IBAN, email, RG, telefono
  _remove_proper_names_from_text(text, names) → rimuove nomi propri
  _extract_legal_matter(text) → mantiene solo keyword giuridiche
  → fallback: parole >= 5 caratteri se nessuna keyword trovata
        |
        v
  STEP 5: Build official_sources_query
  _build_official_sources_query(public_query, original_query)
  → privilegia articoli di legge, materie normative, termini processuali
  → ottimizzata per normattiva.it, gazzettaufficiale.it, giustizia.it
        |
        v
  STEP 6: Determina canali consentiti
  _SENSITIVITY_CHANNELS[sensitivity]
  → can_use_internal_retrieval, can_use_official_web,
     can_use_ldr, can_use_external_provider
  → doppio check privacy su public_research_query per LDR
        |
        v
  PrivacySafeResearchQuery
```

---

## 3. `PrivacySafeResearchQuery` — tutti i campi

| Campo | Tipo | Descrizione |
|---|---|---|
| `original_query` | `str` | Query originale dell'utente, non modificata. |
| `private_context_query` | `str` | Query per il retrieval interno tenant-aware. Mantiene nomi propri, redacta solo identificatori forti (CF, IBAN, email, RG, telefono). Non esce mai dal tenant. |
| `public_research_query` | `str` | Query anonimizzata per fonti pubbliche e LDR. Solo materia giuridica, nessun dato personale. |
| `official_sources_query` | `str` | Variante ottimizzata per fonti istituzionali (normattiva, gazzettaufficiale, giustizia.it). Tende a essere più sintetica e focalizzata su norma/articolo/materia. |
| `local_deep_research_query` | `str` | Query da inviare a LDR. Uguale a `public_research_query` se `can_use_ldr=True`, stringa vuota altrimenti. |
| `removed_sensitive_tokens` | `list[str]` | Lista dei token rimossi dalla query pubblica. Include nomi propri, RG, CF, IBAN, numeri di telefono, email. |
| `sensitivity` | `str` | Livello di sensitività classificato: `public`, `internal`, `sensitive`, `highly_sensitive`. |
| `can_use_internal_retrieval` | `bool` | True se il retrieval interno tenant-aware è consentito. Sempre True salvo query vuota. |
| `can_use_official_web` | `bool` | True se la ricerca su web ufficiale (DuckDuckGo `site:`) è consentita. False se `highly_sensitive` o `public_research_query` vuota. |
| `can_use_ldr` | `bool` | True se Local Deep Research può ricevere la query. Richiede che anche la `public_research_query` superi un secondo controllo privacy (`public` o `internal`). |
| `can_use_external_provider` | `bool` | True se provider esterni (es. OpenAI) possono ricevere la query. Richiede `LEX_EXTERNAL_ALLOWED=1` e sensitivity `public` o `internal`. |
| `requires_review` | `bool` | True se la risposta finale richiede revisione umana (sensitivity `highly_sensitive` o query pubblica vuota). |
| `reason` | `str` | Spiegazione sintetica della classificazione e delle decisioni prese. |
| `warnings` | `list[str]` | Lista di avvisi generati durante la riscrittura. |

---

## 4. Token rimossi — pattern riconosciuti

Il rewriter rimuove automaticamente i seguenti pattern dalla `public_research_query`:

| Categoria | Esempi | Pattern usato |
|---|---|---|
| Codice Fiscale | `RSSMRA80A01H501U` | `CF_RE` (16 caratteri alfanumerici nel formato italiano) |
| IBAN | `IT60X0542811101000000123456` | `IBAN_RE` (formato IBAN con prefisso IT) |
| Email | `mario.rossi@studio.it` | `EMAIL_RE` |
| Numero di RG | `RG 1234/2025`, `n. 456/2024` | `RG_RE` (varie notazioni registro generale) |
| Telefono | `+39 02 1234567`, `3471234567` | `PHONE_RE` (con e senza prefisso internazionale) |
| Nomi propri italiani | `Rossi`, `Mario Bianchi`, `Avv. Verdi` | `_NOME_PROPRIO_RE` + `_LOCUZIONE_NOME_RE` |

**Logica di estrazione nomi propri:**
- Prima passa: locuzioni esplicite (`contro X`, `di X`, `Sig. X`, `Dott. X`, `Avv. X`) — alta confidenza.
- Seconda passa: sequenze di parole con iniziale maiuscola, lunghezza >= 3 caratteri, che non corrispondono a keyword giuridiche note e non sono parole comuni italiane (`Nel`, `Tribunale`, `Corte`, ecc.).
- I nomi vengono rimossi dalla query pubblica ma mantenuti nella `private_context_query`.

**Placeholder contestuali:**
I nomi propri vengono rimossi (non sostituiti), ma il contesto viene preservato:
- Nomi preceduti da "contro" → il termine viene rimosso con placeholder `[CONTROPARTE]` (poi eliminato dalla query finale)
- Nomi associati a "fascicolo" o "causa" → rimossi con `[PARTE_FASCICOLO]`
- Altri nomi → rimossi con `[PARTE_PRIVATA]`

---

## 5. Materia giuridica preservata — perché "prescrizione" non viene toccata

Il rewriter distingue tra dati personali (da rimuovere) e terminologia giuridica (da preservare). La distinzione è implementata tramite un insieme di circa 200 keyword giuridiche (`_LEGAL_KEYWORDS`) che comprende:

- Termini di prescrizione e decadenza: `prescrizione`, `decadenza`, `termine`, `interruzione`, `sospensione`, ecc.
- Responsabilità: `responsabilità`, `contrattuale`, `extracontrattuale`, `danno`, `inadempimento`, ecc.
- Procedure: `udienza`, `ricorso`, `appello`, `cassazione`, `opposizione`, ecc.
- Normativa: `legge`, `norma`, `articolo`, `codice civile`, `decreto legislativo`, ecc.
- Materie specifiche: `lavoro`, `licenziamento`, `separazione`, `divorzio`, `successione`, `locazione`, ecc.

**La regola è:** se una parola è in `_LEGAL_KEYWORDS` o in `_ITALIAN_COMMON_WORDS`, non viene mai rimossa dalla query pubblica, anche se ha l'iniziale maiuscola. Quindi:

- `"Prescrizione"` → preservata (è in `_LEGAL_KEYWORDS`)
- `"Tribunale"` → preservata (è in `_ITALIAN_COMMON_WORDS`)
- `"Rossi"` → rimossa (non è una keyword giuridica)
- `"RG 1234/2025"` → rimossa (corrisponde a `RG_RE`)

---

## 6. Esempi concreti input/output

**Esempio 1 — Query con fascicolo e nomi propri:**

```
Input:
"Nel fascicolo Rossi RG 1234/2025 posso eccepire la prescrizione
 contro Bianchi nella causa di responsabilità contrattuale?"

Output:
private_context_query:
  "Nel fascicolo Rossi posso eccepire la prescrizione contro Bianchi
   nella causa di responsabilità contrattuale?"
  (RG rimosso, nomi mantenuti per retrieval interno)

public_research_query:
  "prescrizione responsabilità contrattuale eccezione termine decorrenza"
  (nomi propri rimossi, RG rimosso, solo materia giuridica)

official_sources_query:
  "prescrizione responsabilità contrattuale termine decorrenza codice civile"

removed_sensitive_tokens:
  ["Rossi", "RG 1234/2025", "Bianchi"]

sensitivity:
  "sensitive"

can_use_ldr:
  True (la public_research_query supera il secondo controllo privacy)

can_use_external_provider:
  False (sensitivity=sensitive blocca provider esterni)
```

**Esempio 2 — Query con codice fiscale:**

```
Input:
"Il mio cliente con CF RSSMRA80A01H501U ha ricevuto un avviso
 di accertamento fiscale per IRPEF 2023. Come impugnarlo?"

Output:
private_context_query:
  "Il mio cliente con [CF_OSCURATO] ha ricevuto un avviso di accertamento
   fiscale per IRPEF 2023. Come impugnarlo?"

public_research_query:
  "accertamento fiscale irpef impugnazione ricorso tributario"

sensitivity:
  "sensitive"

removed_sensitive_tokens:
  ["RSSMRA80A01H501U"]
```

**Esempio 3 — Query pubblica senza dati sensibili:**

```
Input:
"Quali sono i termini di prescrizione per l'azione di responsabilità
 extracontrattuale nel diritto civile italiano?"

Output:
private_context_query:
  "Quali sono i termini di prescrizione per l'azione di responsabilità
   extracontrattuale nel diritto civile italiano?"
  (invariata: nessun dato da redactare)

public_research_query:
  "prescrizione responsabilità extracontrattuale termine diritto civile"

sensitivity:
  "public"

can_use_ldr: True
can_use_official_web: True
can_use_external_provider: False (dipende da LEX_EXTERNAL_ALLOWED)

removed_sensitive_tokens: []
```

**Esempio 4 — Query altamente sensibile:**

```
Input:
"Mario Rossi CF RSSMRA80A01H501U IBAN IT60X0542811101 tel 3471234567
 — come gestisco questo fascicolo di separazione?"

Output:
public_research_query:
  "separazione"  (o stringa vuota se nessuna keyword riconosciuta)

sensitivity:
  "highly_sensitive"

can_use_ldr: False
can_use_official_web: False
can_use_external_provider: False

requires_review: True
reason: "Sensitività classificata: highly_sensitive. Token rimossi dalla query
         pubblica: 'RSSMRA80A01H501U', 'IT60X0542811101', '3471234567', 'Mario Rossi'."
```

---

## 7. Limiti — cosa non viene riconosciuto automaticamente

1. **Nomi stranieri** — Il pattern `_NOME_PROPRIO_RE` è ottimizzato per nomi italiani. Nomi come `"Schmidt"`, `"O'Brien"`, `"van der Berg"` potrebbero non essere estratti correttamente.

2. **Acronimi aziendali** — `"S.r.l."`, `"S.p.A."` non sono considerati dati personali e non vengono rimossi. Il nome della società (es. `"Alfa Costruzioni S.r.l."`) potrebbe rimanere nella query pubblica.

3. **Indirizzi fisici** — Indirizzi come `"Via Roma 12, Milano"` non vengono riconosciuti come dati personali dai pattern attuali (non esiste un `ADDRESS_RE`).

4. **Numeri di causa al di fuori del pattern RG** — Formati non standard (es. `"causa n. 100/2024 sez. I"`) potrebbero non essere riconosciuti da `RG_RE`.

5. **Nomi propri in tutto maiuscolo** — `"ROSSI"` non viene riconosciuto da `_NOME_PROPRIO_RE` (che richiede iniziale maiuscola + lettere minuscole). Questo è un limite accettato per ridurre i falsi positivi su acronimi.

6. **Codici identificativi personalizzati** — Identificatori interni allo studio (es. `"pratica-2025-A01"`) non vengono rimossi automaticamente.

---

## 8. Come verificare che la riscrittura funziona

**Test manuale da Python:**

```python
from lex.research.privacy_safe_query_rewriter import rewrite_query_for_legal_research

result = rewrite_query_for_legal_research(
    "Nel fascicolo Rossi RG 1234/2025 posso eccepire la prescrizione "
    "nella causa di responsabilità contrattuale contro Bianchi?"
)

# Verifiche di base
assert "Rossi" not in result.public_research_query, "Nome proprio non rimosso"
assert "1234/2025" not in result.public_research_query, "RG non rimosso"
assert "prescrizione" in result.public_research_query, "Keyword giuridica rimossa"
assert result.sensitivity in {"public", "internal", "sensitive", "highly_sensitive"}
assert result.can_use_internal_retrieval is True

print("Riscrittura OK")
print(f"Query pubblica: {result.public_research_query}")
print(f"Token rimossi: {result.removed_sensitive_tokens}")
print(f"Sensitivity: {result.sensitivity}")
```

**Verificare tramite il payload debug (solo admin):**

Nel payload JSON della risposta Lex, controllare i campi:
- `public_research_query` — deve contenere solo materia giuridica
- `removed_sensitive_tokens.count` — deve essere > 0 se la query aveva dati sensibili

**Eseguire i test automatici:**

```bash
python -m pytest tests/test_privacy_query_rewriter.py -v
```

---

## 9. FAQ

**Domanda:** La riscrittura rallenta la risposta di Lex?
**Risposta:** No in modo percepibile. La riscrittura è interamente in-process (nessuna chiamata di rete) e impiega tipicamente meno di 5 ms per query. Il tempo è dominato dal regex matching.

**Domanda:** Cosa succede se il rewriter non riesce a estrarre alcun termine giuridico?
**Risposta:** Viene attivato un fallback che usa le parole della query di lunghezza >= 5 caratteri (escluse le parole comuni italiane). Se anche il fallback è vuoto, `public_research_query` è stringa vuota, `can_use_official_web=False` e `can_use_ldr=False`. Il warning `"Impossibile estrarre materia giuridica dalla query"` viene incluso nella risposta.

**Domanda:** Perché i nomi propri vengono mantenuti nella `private_context_query`?
**Risposta:** Perché il retrieval interno opera sui fascicoli dello studio, dove i nomi propri dei clienti e delle controparti sono informazioni essenziali per trovare il fascicolo corretto. La `private_context_query` non esce mai dal perimetro del tenant, quindi la presenza di nomi propri non costituisce un rischio di leak.

**Domanda:** Un utente può aggirare la riscrittura?
**Risposta:** No. La riscrittura viene eseguita automaticamente dal `LegalResearchIntegrator` prima di qualsiasi chiamata ai canali pubblici. Il flusso bounded context non prevede un percorso alternativo che bypassa il rewriter per le query pubbliche.

---

*Documento interno — IUSENTRA Legal Platform*
