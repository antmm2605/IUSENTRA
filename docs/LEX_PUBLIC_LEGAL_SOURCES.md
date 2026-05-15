# LEX — Fonti Legali Pubbliche (v2.201.0)

Guida tecnica al comportamento di Lex nella ricerca di fonti legali pubbliche: normativa, giurisprudenza, prassi amministrativa.

---

## Aggiornamento operativo 2.238.0 - 2026-05-15

`/ricerca-legale` e' ora una ricerca reale: il frontend invia la query a `/api/v1/ui/ricerca-legale`, il backend interroga `legal_updates.db` e, se le evidenze non bastano, attiva il gateway su domini ufficiali allowlisted. I risultati devono includere estratto o contesto fonte quando disponibile.

Tra le fonti PST governate e' registrata la news ufficiale `NWS4865` del 2026-05-11: ripristino dal 22/04/2026 di Registro Organismi di Mediazione, Elenco Enti per la Mediazione ed Elenco Formatori per la Mediazione.

---

## 1. Principio fondamentale

Lex distingue nettamente due categorie di fonti:

| Categoria | Esempi | Accesso |
|-----------|--------|---------|
| **Fonti pubbliche** | Normattiva, Gazzetta Ufficiale, Corte di Cassazione, EUR-Lex, Agenzia Entrate | Ricerca web su domini allowlisted |
| **Dati studio** | Clienti, fascicoli, agenda, parcelle | Gestori interni (pct/*) |

Lex **non mescola** le due categorie: la risposta indica sempre la provenienza.

---

## 2. Workflow per fonti pubbliche

### 2.1 Ricerca generica (giurisprudenza, normativa, prassi)

| Workflow | Quando | Comportamento |
|----------|--------|---------------|
| `giurisprudenza` | "sentenze sulla prescrizione" | Ricerca semantica su domini legali |
| `normativa` | "art. 2043 c.c." | Ricerca su normattiva.it + codici ufficiali |
| `prassi` | "circolare Entrate 2024" | Ricerca su agenziaentrate.gov.it, giustizia.it |

### 2.2 Ricerca esatta (`giurisprudenza_specifica`)

Attivato quando la query contiene **numero sentenza + (data o anno)**:

```
"Sentenza n. 7919 del 31/03/2026"
"Cass. Sez. Civ. n. 12345/2025"
"ordinanza n. 500 del 01/01/2024"
```

Il workflow `giurisprudenza_specifica`:
1. Analizza la query con `case_law_reference_parser.py` → `ExactLegalReference`
2. Forza `source_scope = public_legal_source`
3. Forza ricerca web anche se c'è contesto locale (fascicolo, cliente)
4. Usa query ottimizzate per `cortedicassazione.it`
5. Applica `ExactLegalReferenceGuard` sui risultati
6. Se non trovata: risponde "non ho trovato conferma ufficiale esatta"

---

## 3. Domini allowlisted per ricerca legale

| Dominio | Tipo | Priorità |
|---------|------|----------|
| `cortedicassazione.it` | Sentenze civili/penali | Alta |
| `normattiva.it` | Normativa vigente | Alta |
| `giustizia.it` | Portale Ministero Giustizia | Alta |
| `pst.giustizia.it` | PST - deposito telematico | Alta |
| `agenziaentrate.gov.it` | Prassi fiscale | Alta |
| `eur-lex.europa.eu` | Normativa europea | Media |
| `giustizia-amministrativa.it` | TAR e Consiglio di Stato | Alta |
| `cortecostituzionale.it` | Corte Costituzionale | Alta |

---

## 4. ExactLegalReferenceGuard

Il guard (`lex/guards/exact_legal_reference_guard.py`) viene applicato **dopo il retrieval** per ogni `giurisprudenza_specifica`:

| Stato | Quando | Confidence cap |
|-------|--------|----------------|
| `not_found` | Nessuna evidenza con numero/data corrispondenti | ≤ 0.45 |
| `found_no_text` | Evidenza trovata ma senza testo integrale/dispositivo | ≤ 0.55 |
| `found_with_text` | Evidenza con dispositivo completo ("p.q.m.", "per questi motivi") | ≤ 0.85 |

**Regole invarianti:**
- Lex non presenta mai una lista di sentenze diverse come risposta a una ricerca esatta
- Se non trovata: risposta onesta "non ho trovato la Sentenza n. XXXX del GG/MM/AAAA"
- Non vengono mai inventati testi di sentenze

---

## 5. Query variants per Cassazione

Il parser genera query ottimizzate per ogni riferimento esatto:

```python
# Esempio per "Sentenza n. 7919 del 31/03/2026"
cassazione_variants = [
    '"sentenza n. 7919" "31/03/2026" site:cortedicassazione.it',
    '"sentenza" "7919" "31/03/2026" cortedicassazione.it',
    'site:cortedicassazione.it "7919" "2026"',
    'site:cortedicassazione.it/it/ "7919"',
    '"sentenza" "7919" "31/03/2026" "cortedicassazione.it"',
]
```

---

## 6. _should_force_web_fallback — logica aggiornata

Il flag `force_web` è True quando:

1. **Riferimento legale esatto** → sempre True, anche se esiste contesto locale
2. **Nessun contesto locale specifico** + trigger legale nella query
3. **Web execution request** esplicita

L'override per riferimento esatto bypassa `_has_specific_local_context`:
```python
# Se è sentenza n. XXXX → web obbligatorio anche con fascicolo in contesto
if _is_exact_legal_reference_query(text):
    if any(token in text for token in ("sentenza", "ordinanza", ...)):
        return True  # ignora contesto locale
```

---

## 7. Variabili d'ambiente

| Variabile | Default | Effetto |
|-----------|---------|---------|
| `LEX_PUBLIC_WEB_ENABLED` | `1` | Abilita ricerca web pubblica |
| `LEX_CASE_LAW_WEB_SEARCH_ENABLED` | `1` | Abilita ricerca sentenze su web |
| `LEX_OFFICIAL_DOMAINS_ONLY` | `0` | Restringe a soli domini ufficiali |
| `LEX_WEB_RESULT_TTL` | `900` | TTL cache risultati web (secondi) |
