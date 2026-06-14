# Integrazione Brocardi — Importazione Normative Italiane

## Panoramica

Brocardi (https://www.brocardi.it/) è un portale italiano autorevole di consultazione normativa che fornisce accesso ai principali codici italiani con commento dottrinale e giurisprudenza associata.

**Status in IUSENTRA:**
- **Adapter creato**: `lex/legal_sources/adapters/brocardi.py` ✅
- **Registrato in**: `lex/legal_sources/adapters/__init__.py` ✅
- **Tier**: 2 (secondaria, autorevole)
- **Categoria**: `secondary_legislation`
- **Jurisdizione**: IT (Italia)
- **Ufficiale**: No (ma autorevole e open data)

---

## Codici Disponibili su Brocardi

Brocardi ospita i seguenti 5 codici principali:

| Codice | Slug URL | Categoria | Struttura |
|--------|----------|-----------|-----------|
| **Codice Civile** | `codice-civile` | Diritto civile | Libro → Titolo → Capo → Articolo → Comma |
| **Codice di Procedura Civile** | `codice-di-procedura-civile` | Procedura civile | Libro → Titolo → Capo → Articolo → Comma |
| **Codice Penale** | `codice-penale` | Diritto penale | Libro → Titolo → Capo → Articolo → Comma |
| **Codice di Procedura Penale** | `codice-di-procedura-penale` | Procedura penale | Libro → Titolo → Capo → Articolo → Comma |
| **Costituzione** | `costituzione` | Diritto costituzionale | Parte → Titolo → Sezione → Articolo |

---

## Struttura URL Brocardi

Gli URL su Brocardi seguono un pattern stabile:

```
https://www.brocardi.it/{codice-slug}/art{numero}.html
```

**Esempi:**
```
https://www.brocardi.it/codice-civile/art1.html
https://www.brocardi.it/codice-di-procedura-civile/art183.html
https://www.brocardi.it/codice-penale/art81.html
https://www.brocardi.it/codice-di-procedura-penale/art599bis.html
https://www.brocardi.it/costituzione/art1.html
```

---

## Script di Importazione

### File
- **Script**: `scripts/import_normative_brocardi.py`
- **Output JSONL**: `data/normative_brocardi.jsonl`
- **Output JSON** (opzionale): `data/normative_brocardi.json`

### Utilizzo

#### Modalità campione (default — per test e demo)
```bash
python3 scripts/import_normative_brocardi.py
```

Genera dati campione per 20 articoli (5 per codice) da tutti i codici disponibili.

#### Modalità Apify (scraping reale)
```bash
export APIFY_TOKEN="your-token-here"
python3 scripts/import_normative_brocardi.py --api
```

Usa Apify Web Scraper per scrapare il sito Brocardi in tempo reale.

#### Opzioni

```bash
# Scarica un singolo codice
python3 scripts/import_normative_brocardi.py --codice civile

# Specifica file output
python3 scripts/import_normative_brocardi.py --output data/brocardi_custom.jsonl

# Salva sia JSONL che JSON
python3 scripts/import_normative_brocardi.py --both-formats

# Usa Apify per scraping reale
python3 scripts/import_normative_brocardi.py --api --both-formats
```

---

## Formato Dati Importati

### Struttura JSONL (una riga per articolo/comma)

Ogni riga è un JSON oggetto conforme al modello `LegalCitation` di IUSENTRA:

```json
{
  "source_id": "brocardi",
  "source_name": "Brocardi",
  "source_category": "secondary_legislation",
  "jurisdiction": "IT",
  "document_type": "articolo",
  "authority": "Codice Civile",
  "title": "Codice Civile - Art. 1",
  "number": "art1",
  "article": "1",
  "paragraph": null,
  "section": null,
  "section_title": "Delle persone e della famiglia",
  "book": "Primo",
  "capo": null,
  "text": "La capacità giuridica si acquista dal momento della nascita...",
  "version_date": null,
  "publication": null,
  "publication_number": null,
  "urn": null,
  "eli": null,
  "celex": null,
  "ecli": null,
  "hudoc_id": null,
  "url": "https://www.brocardi.it/codice-civile/art1.html",
  "retrieved_at": "2026-06-14T14:59:45.777734"
}
```

**Campi chiave:**
- `source_id`: sempre `"brocardi"`
- `article`: numero articolo (stringa)
- `paragraph`: numero comma se presente, altrimenti `null`
- `section_title`: titolo della sezione/capo (livello gerarchico)
- `book`: libro (per struttura gerarchica)
- `url`: URL stabile del documento su Brocardi
- `retrieved_at`: timestamp di recupero
- `text`: testo normativo (da scrapare dal sito)

### Struttura JSON (raggruppata per codice)

Formato alternativo con raggruppamento gerarchico:

```json
{
  "source": "brocardi",
  "source_url": "https://www.brocardi.it/",
  "retrieved_at": "2026-06-14T14:59:45.777734",
  "stats": {
    "codici": 5,
    "articoli": 20,
    "commi": 8,
    "errori": 0
  },
  "codici": {
    "Codice Civile": [
      { ... },
      { ... }
    ],
    "Codice di Procedura Civile": [ ... ],
    "Codice Penale": [ ... ],
    "Codice di Procedura Penale": [ ... ],
    "Costituzione": [ ... ]
  }
}
```

---

## Integrazione con Lex AI

### Uso del BrocardiAdapter

```python
from lex.legal_sources.adapters import BrocardiAdapter

adapter = BrocardiAdapter()

# Accedi ai metadati
print(adapter.metadata.display_name)  # "Brocardi"
print(adapter.metadata.priority)      # 45
print(adapter.metadata.official)      # False
```

### Registrazione nel motore di ricerca

Il BrocardiAdapter è automaticamente registrato e disponibile come fonte secondaria in tutti i workflow di ricerca legale che supportano il tier 2.

**Tier system in Lex:**
- **Tier 1** (peso 1.0): Normattiva, Gazzetta Ufficiale, Giustizia.it
- **Tier 2** (peso 0.72): **Brocardi**, Altalex, Ilcaso.it
- **Tier 3** (peso 0.32): Blog, Forum, Fonti non verificate

---

## Limitazioni Attuali

1. **Nessun versioning storico**: Brocardi non mantiene versioni storiche dei codici. Sempre testo vigente.
2. **Nessun identificativo standard UE**: Non disponibili URN:NIR, ELI, CELEX (Brocardi è portale italiano).
3. **Scraping manuale richiesto**: La modalità Apify richiede configurazione manuale con credenziali e setup.
4. **No download massivo**: In questa fase, il download di tutti i codici è escluso per rispetto della policy di Brocardi.

---

## Prossimi Passi

### Fase 2 — Ingestione campione Apify
- [ ] Configurare credenziali Apify
- [ ] Testare scraping di un singolo codice (es. Civile)
- [ ] Salvare dati campione in `data/normative_brocardi.jsonl`
- [ ] Validare formato e completezza

### Fase 3 — Lookup esatto nel motore Lex
- [ ] Implementare `BrocardiAdapter.fetch_by_article(codice, numero_articolo, comma)`
- [ ] Integrare nel retrieval workflow di Lex
- [ ] Testare citazioni articolo → testo normativo

### Fase 4 — Monitoraggio aggiornamenti
- [ ] Setup scheduler per controllare aggiornamenti settimanali
- [ ] Notificare se articoli sono stati modificati
- [ ] Mantenere cache locale sincronizzata

### Fase 5 — Giurisprudenza associata
- [ ] Scrapare commenti e giurisprudenza associata da Brocardi
- [ ] Linkare articolo → sentenze rilevanti
- [ ] Integrare in risk assessment workflow

---

## FAQ

### D: Perché Brocardi è tier 2 e non tier 1?
**R:** Brocardi è autorevole ma non ufficiale. I testi provengono da Normattiva/Gazzetta Ufficiale, quindi le fonti primarie restano tier 1. Brocardi aggiunge commento e strutturazione.

### D: Brocardi supporta API ufficiali?
**R:** No. Brocardi non pubblica API ufficiali. L'accesso è tramite scraping web (Apify).

### D: Posso usare i dati di Brocardi per fini commerciali?
**R:** Verifica i termini di servizio di Brocardi. In IUSENTRA, l'uso è limitato a consultazione interna dello studio legale.

### D: Come faccio aggiornamenti quando Brocardi cambia gli articoli?
**R:** Riesegui `python3 scripts/import_normative_brocardi.py --api` periodicamente (settimanale consigliato).

### D: Posso scaricare TUTTI gli articoli di TUTTI i codici contemporaneamente?
**R:** Tecnicamente sì con Apify, ma sconsigliato per non sovraccaricare il sito. Usa il campione per test e scarica singoli codici per produzione.

---

## Rierenze

- **Sito Brocardi**: https://www.brocardi.it/
- **Adapter**: `lex/legal_sources/adapters/brocardi.py`
- **Script importazione**: `scripts/import_normative_brocardi.py`
- **Modello LegalCitation**: `lex/legal_sources/models.py`
- **Apify Web Scraper**: https://apify.com/motivational_nickel/my-actor

---

## Contatti e Supporto

Per domande su integrazione Brocardi in IUSENTRA, vedi:
- `CLAUDE.md` — Istruzioni progetto
- `AGENTS.md` — Regole sviluppo
- `docs/lex_ai_legal_source_engine_roadmap.md` — Piano completo integrazioni fonti
