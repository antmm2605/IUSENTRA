# LEX — Privacy e Source Scope (v2.201.0)

Documentazione delle regole di privacy e classificazione scope delle fonti per Lex.

---

## 1. SourceScope — classificazione query

Ogni query Lex viene classificata in un ambito di fonti (`source_scope`) che determina:
- Quali fonti Lex può usare
- Se la ricerca web è abilitata
- Se i dati interni dello studio vengono caricati

### Valori SourceScope

| Valore | Descrizione | Web | Dati studio |
|--------|-------------|-----|-------------|
| `studio_internal` | Dati solo interni (cliente, fascicolo, agenda) | No | Sì |
| `public_legal_source` | Fonti pubbliche (sentenze, normativa) | Sì | No |
| `mixed_private_public` | Entrambe (es: fascicolo + sentenza citata) | Sì | Sì |
| `diagnostic` | Query diagnostica/amministrativa | No | Sì |
| `operational_no_web` | Operativo puro (agenda, scadenze) | No | Sì |

### File: `lex/research/source_scope_policy.py`

```python
scope = classify_source_scope("trovami la Sentenza n. 7919 del 31/03/2026")
# → SourceScope(scope="public_legal_source", requires_public_web=True, exact_legal_reference=True)

scope = classify_source_scope("dammi i dati del cliente Mario Rossi")
# → SourceScope(scope="studio_internal", requires_studio_data=True, requires_public_web=False)
```

---

## 2. Regole privacy fondamentali

### 2.1 Dati studio — mai esposti all'esterno

- CF, PIVA, PEC, email, telefono dei clienti: usati solo per risposta locale
- Note riservate (`note_riservate`): mai incluse nel contesto Lex
- Dati economici (importi parcelle): mai inviati a provider AI esterni
- ID fascicolo, RG, documenti: usati solo come riferimento locale

### 2.2 Fonti pubbliche — mai usate come proxy per dati privati

Lex non usa una sentenza pubblica per "indovinare" informazioni su un cliente specifico.

### 2.3 Debug payload — campi redatti

Nel payload debug (admin/superadmin):
- `private_context_query` → sempre `"[REDATTO PER PRIVACY]"`
- `removed_sensitive_tokens` → solo il conteggio, mai i token reali
- Path assoluti → sanitizzati a basename

---

## 3. Flusso privacy per query mista

Esempio: "nel fascicolo Rossi cerca la Sentenza n. 7919 del 31/03/2026"

```
1. Router → workflow = giurisprudenza_specifica
2. source_scope = mixed_private_public
3. Carica contesto fascicolo Rossi (dati interni)
4. Forza ricerca web per sentenza esatta (bypassando _has_specific_local_context)
5. ExactLegalReferenceGuard verifica le evidenze web
6. Risposta: combina info fascicolo + link sentenza verificata
7. Non include dati CF/email del cliente nella risposta pubblica
```

---

## 4. query_helpers.py — funzioni leggere

Il modulo `lex/research/query_helpers.py` contiene funzioni standalone senza dipendenze pesanti:

```python
from lex.research.query_helpers import extract_entity_hint, is_exact_legal_reference_query

# Entity extraction
hints = extract_entity_hint("CF: RSSMRA80A01H501Z")
# → {"codice_fiscale": "RSSMRA80A01H501Z", "partita_iva": "", "email": ""}

# Riconoscimento riferimento esatto
is_exact_legal_reference_query("sentenza n. 7919 del 31/03/2026")
# → True

is_exact_legal_reference_query("sentenze sulla prescrizione")
# → False
```

Queste funzioni sono usate da:
- `assistente_studio_context.py` (thin wrapper)
- `studio_data_gateway.py` (entity extraction)
- Test suite (test diretti senza import pesanti)

---

## 5. Variabili d'ambiente privacy

| Variabile | Default | Effetto |
|-----------|---------|---------|
| `LEX_PRIVACY_MODE` | `standard` | `strict` = no CF/PEC in contesto |
| `LEX_AUDIT_LOG_STUDIO_QUERIES` | `0` | Registra ogni query ai dati studio |
| `LEX_STUDIO_DATA_IN_DEBUG` | `0` | Include dati studio nel debug payload |

---

## 6. Debug payload — campi source_scope (v2.0)

I seguenti campi sono disponibili nel payload debug admin:

```json
{
  "source_scope": "public_legal_source",
  "source_scope_confidence": 0.92,
  "exact_legal_reference": true,
  "exact_reference_number": "7919",
  "exact_reference_date": "31/03/2026",
  "exact_reference_year": "2026",
  "exact_reference_court": "Corte di Cassazione",
  "exact_reference_kind": "sentenza",
  "exact_reference_verdict": "not_found",
  "web_forced_by_exact_ref": true,
  "studio_data_lookup_used": false,
  "studio_entity_hint": ""
}
```

---

## 7. Conformità GDPR

- Il sistema rispetta `privacy.py` (registro trattamenti GDPR)
- L'accesso ai dati studio è loggato in `EventoAudit` per tutti i ruoli
- I dati cliente mostrati in risposta Lex sono limitati a quanto strettamente necessario alla risposta
- Lex non produce risposte che espongono dati personali a utenti non autorizzati
