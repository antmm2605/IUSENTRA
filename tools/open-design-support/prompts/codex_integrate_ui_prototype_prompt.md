# Prompt Codex per integrare un prototipo UI in IUSENTRA

Hai un prototipo grafico o una descrizione UI.
Devi integrarlo in IUSENTRA senza rompere architettura, route, storage o permessi.

Prima di modificare:
- identifica se la UI e' Jinja, React `/app-v2`, CSS/SCSS o template legacy;
- leggi `IUSENTRA_DESIGN.md`;
- leggi `IUSENTRA_UI_RULES.md`;
- definisci file modificabili;
- definisci file vietati;
- dichiara test/smoke.

Regole:
- non copiare codice HTML generico senza adattamento;
- non introdurre dipendenze frontend;
- non cambiare API Flask senza task esplicito;
- non cambiare storage;
- non cambiare permessi;
- non rompere fallback legacy;
- mantenere testi italiani;
- mantenere responsive;
- evitare CSS non governabile.

Alla fine:
- esegui test/smoke pertinenti;
- esegui quality gate;
- riporta diff e classificazione autoresearch-lite.
