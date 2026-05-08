# LEX — Studio Data Gateway (v2.201.0)

Documentazione del gateway strutturato per l'accesso ai dati interni dello studio da parte di Lex.

---

## 1. Scopo

Lex usa `lex/tools/studio_data_gateway.py` come layer di accesso governato ai dati dello studio.
Il gateway:
- Avvolge i gestori `pct/*` con output strutturati e privi di eccezioni raw
- Supporta entity extraction (CF, PIVA, email) per ricerche precise
- Restituisce dati completi (email, PEC, CF, fascicoli) — non solo nome+stato
- Non espone dati a web o provider esterni

---

## 2. Funzioni disponibili

| Funzione | Descrizione | Output |
|----------|-------------|--------|
| `find_cliente(query, limit=8)` | Cerca clienti per nome/CF/PIVA/email/testo | `list[ClienteResult]` |
| `get_cliente_details(cliente_id)` | Dettagli completi cliente per ID | `ClienteResult | None` |
| `get_cliente_contacts(cliente_id)` | Solo recapiti (email, PEC, tel, indirizzo) | `dict[str, str]` |
| `find_fascicoli_by_cliente(cliente_id, limit=10)` | Fascicoli collegati a un cliente | `list[FascicoloResult]` |
| `find_fascicolo(query, limit=8)` | Cerca fascicoli per titolo/RG/oggetto | `list[FascicoloResult]` |
| `get_fascicolo_details(fascicolo_id)` | Dettagli completi fascicolo per ID | `FascicoloResult | None` |
| `get_cliente_timeline(cliente_id, limit=10)` | Agenda + scadenze del cliente | `list[dict]` |
| `get_cliente_economic_summary(cliente_id)` | Sommario parcelle/fatture | `dict` |
| `get_cliente_documents(cliente_id, limit=10)` | Documenti nei fascicoli del cliente | `list[dict]` |
| `extract_entity_hint(query)` | Estrae CF/PIVA/email dalla query | `dict[str, str]` |

---

## 3. ClienteResult — campi

```python
@dataclass
class ClienteResult:
    id: str
    nome_completo: str
    tipo: str                    # persona_fisica | persona_giuridica
    stato: str                   # attivo | sospeso | archiviato
    codice_fiscale: str
    partita_iva: str
    email: str
    pec: str
    telefono: str
    indirizzo: str
    avvocato_referente: str
    data_prima_acquisizione: str
    note: str
    tag: list[str]
    n_fascicoli: int
```

---

## 4. FascicoloResult — campi

```python
@dataclass
class FascicoloResult:
    id: str
    titolo: str
    numero_rg: str
    anno_rg: str
    stato: str
    tribunale: str
    sezione: str
    oggetto: str
    tipo: str
    valore_causa: float
    avvocato_referente: str
    data_apertura: str
    data_chiusura: str
    cliente_nome: str
    cliente_id: str
    note: str
```

---

## 5. Entity extraction

Il gateway prioritizza la ricerca precisa per entità nella query:

```
Priorità 1: CF esatto (RSSMRA80A01H501Z)
Priorità 2: P.IVA esatta (12345678901)
Priorità 3: Email esatta (mario@studio.it)
Priorità 4: Testo libero (gestore.cerca(query))
```

Esempio: "dati del cliente RSSMRA80A01H501Z" → cerca clienti con CF=RSSMRA80A01H501Z esatto.

---

## 6. Workflow studio_data_lookup

Attivato quando:
- Intent = `cliente_anagrafica`
- Query contiene: "dati del cliente", "anagrafica di", "recapiti del cliente", "email del cliente", ecc.

Il workflow `studio_data_lookup`:
1. Classifica `source_scope = studio_internal`
2. Non effettua ricerche web
3. Usa `find_cliente()` o `get_cliente_details()` dal gateway
4. Restituisce dati completi (CF, email, PEC, fascicoli)
5. Log nel debug payload: `studio_data_lookup_used = True`

---

## 7. Miglioramenti rispetto al precedente _clienti_lines

| Aspetto | Prima | Dopo |
|---------|-------|------|
| Limite risultati | 4 clienti | 8 clienti |
| Dati restituiti | nome + stato + referente | + CF, PIVA, email, PEC, telefono |
| Entity extraction | No | CF, PIVA, email dalla query |
| Ricerca per CF | No | Sì (match esatto) |
| Ricerca per PEC/email | No | Sì (match esatto) |
| Trigger sezione | Richiede "cliente" nella query | Riconosce "dati di", "anagrafica di", ecc. |

---

## 8. Privacy e accesso

- I dati dello studio non vengono mai inviati al provider AI come fonti web
- Il campo `note_riservate` del cliente non è mai esposto nel contesto Lex
- Tutti gli accessi sono loggati in audit log (se `auth.audit_log` è attivo)
- Il gateway rispetta il tenant scope (multi-tenant isolato)
