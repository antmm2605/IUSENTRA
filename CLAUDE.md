# CLAUDE.md — Istruzioni per Claude Code

## Autorizzazioni generali

- **Procedi sempre senza chiedere conferma.** L'utente ha autorizzato tutte le operazioni in modo permanente.
- Commit, push, modifica file, creazione file: esegui direttamente.
- Branch di sviluppo: `claude/legal-electronic-filing-kIxcV`

## Progetto

**HACS** — gestionale per studi legali (Python/Flask).

- Backend: `pct/` — modelli dati e logica di business
- Frontend: `web/app.py` (route Flask) + `web/templates/` (Jinja2) + `web/static/`
- Persistenza: file JSON per clienti, fascicoli, agenda, ecc.
- Stack: Python 3, Flask, Bootstrap 5, Bootstrap Icons

## Convenzioni

- Messaggi di commit in italiano, descrittivi
- Nessuna dipendenza esterna aggiunta senza necessità
- Mantenere coerenza visiva con Bootstrap 5 e le classi già usate nel progetto
