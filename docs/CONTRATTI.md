# Sezione Contratti

Catalogo della contrattualistica dello studio (`/contratti`), con pratiche guidate, controlli giuridici, bozza e scheda di controllo.

## Base normativa
- Art. 1322 c.c. (autonomia contrattuale e contratti atipici) e disciplina generale artt. 1321-1469 c.c.
- Norme speciali dichiarate voce per voce in `pct/contratti/dati/*.json` (ricognizione al 02/11/2026, stato `da_verificare_su_fonte_ufficiale`).
- Redazione e negoziazione restano distinte dalla stipula nelle forme di legge: atto pubblico, scrittura autenticata e trascrizione vengono segnalati, non sostituiti.

## Struttura
| Livello | Modulo | Responsabilità |
|---|---|---|
| Dati | `pct/contratti/dati/` | 199 contratti in 15 aree, domande e controlli comuni, libreria di 65 clausole, ruoli delle parti, novità 2026 |
| Dominio | `catalogo.py`, `selezione.py`, `bozza.py`, `esporta_docx.py`, `archivio.py` | caricamento fail-closed, valutazione per fatti, bozza con segnaposti, Word, archivio con storico |
| Servizio | `web/services/contratti_runtime.py` | archivio di studio (tenant), fascicoli, salvataggio della bozza nel fascicolo |
| API | `web/blueprints/api_v1_contratti.py` | `/api/v1/ui/contratti/*` |
| UI | `frontend/src/components/ContrattiPage.tsx` + `components/contratti/` | catalogo, scheda, pratica in 5 passaggi |

## Regole
- Ogni voce ha almeno un riferimento normativo; ogni controllo ha esito (`blocco`, `valutazione_avvocato`, `adempimento`, `avviso`) e norma. Il catalogo non si carica altrimenti.
- I dati mancanti restano segnaposti `[DA COMPLETARE: …]`: mai valori inventati.
- L'approvazione del testo è rifiutata finché ci sono bloccanti, valutazioni dell'avvocato non registrate, domande senza risposta o segnaposti aperti.
- Una nuova famiglia guidata si aggiunge nel JSON dell'area con `domande`, `controlli` e `clausole` (chiavi di `_clausole.json`), insieme ai test in `tests/test_contratti_*.py`.
