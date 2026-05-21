# Sicurezza Estrazione Archivi

Il modulo `zip_safety.py` applica controlli preventivi su ogni membro ZIP prima di leggere il contenuto.

## Controlli

- blocco `../`;
- blocco path assoluti Unix e Windows;
- blocco drive Windows e UNC;
- dimensione massima singolo file;
- dimensione totale estratta;
- numero massimo file;
- profondità ZIP annidati;
- rapporto compressione per zip bomb;
- estensioni consentite configurabili;
- MIME reale tramite magic bytes dopo estrazione;
- quarantena formati non ammessi;
- nessun crash su ZIP corrotto.

## Audit

Ogni blocco produce `archive.unsafe_blocked` e un task di revisione. I file estratti e validati producono `archive.extracted` con path virtuale, profondità e relazione padre/figlio.

## Estensione

Per aggiungere formati, aggiornare `SUPPORTED_EXTENSIONS`, `EXTENSION_BY_MIME` e le regole di OCR. Un formato nuovo deve avere test negativi e non deve essere indicizzato in Lex finché non supera validazione.
