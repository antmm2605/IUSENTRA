# IUSENTRA — Terzo blocco: Local Signer + AI locale

Questo pacchetto NON riscrive in cieco `local_signer.py`.
Fa la cosa giusta: introduce moduli pronti e un refactor incrementale, sicuro.

## Obiettivo
- togliere responsabilità laterali da `local_signer.py`
- centralizzare CORS/origins
- aggiungere cache AI locale
- preparare la migrazione del dispatch HTTP verso moduli separati

## File inclusi
- `local_signer_mod/security.py`
- `local_signer_mod/ai_cache.py`
- `local_signer_mod/ai_handlers.py`
- `local_signer_mod/server_bootstrap.py`
- `tools/check_local_signer_boundaries.py`
- `tests/test_local_signer_ai_cache.py`
- `PATCH_LOCAL_SIGNER_GUIDE.md`

## Applicazione consigliata
1. Crea la cartella `local_signer_mod/`
2. Copia i file inclusi
3. Segui `PATCH_LOCAL_SIGNER_GUIDE.md` per inserire gli import in `local_signer.py`
4. Aggiungi il test
5. Lancia:
   ```bash
   python tools/check_local_signer_boundaries.py
   python -m pytest -q tests/test_local_signer_ai_cache.py
   ```

## Perché così
Il tuo `local_signer.py` oggi contiene:
- un dispatcher POST molto esteso
- handlers AI locali già isolabili
- bootstrap server/CLI separabile
- regole CORS/origin e state cache interne

Quindi la modularizzazione iniziale sicura è:
- security/origins
- cache AI
- facciata handlers AI
- bootstrap server

Solo dopo ha senso spezzare PST/PDP/PAT/PTT.
