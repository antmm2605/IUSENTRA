# Biblioteca «Codici e leggi» — integrazione del 19/10/2026

84 atti in testo vigente al 19/10/2026, scaricati da Normattiva in formato Akoma Ntoso
(`scripts/normattiva_scarica_akn.py`) e convertiti con `scripts/normattiva_akn_a_jsonl.py`.
Ogni articolo conserva URN, collegamento ufficiale Normattiva, data di vigenza e data di raccolta.
Materia ed etichetta: `lex/normativa/materie.py` e `lex/normativa/etichette_atti.py`.

Importazione (crea da sola un backup del database prima di scrivere):

    python -m lex.normativa.consultazione --source lex/normativa/integrazioni/biblioteca_20261019 \
        --db /data/normativa/codici_leggi.sqlite --updated-at 2026-10-19
