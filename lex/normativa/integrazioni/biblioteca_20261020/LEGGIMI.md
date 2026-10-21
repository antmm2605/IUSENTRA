# Biblioteca «Codici e leggi» — integrazione del 20/10/2026

9 atti in testo vigente al 20/10/2026. Gli atti italiani sono scaricati da Normattiva in formato Akoma Ntoso
(`scripts/normattiva_scarica_akn.py`) e convertiti con `scripts/normattiva_akn_a_jsonl.py`; i regolamenti UE sono
scaricati dall’Ufficio delle pubblicazioni dell’UE (XHTML ufficiale) e convertiti con `scripts/eurlex_xhtml_a_jsonl.py`:

- D.P.R. 396/2000 — ordinamento dello stato civile (rettificazione, artt. 95-96; cambio del nome, art. 89)
- L. 1185/1967 — passaporti (assenso dei genitori e giudice tutelare, artt. 3 e 3-bis)
- D.P.R. 639/1970 — decadenza dell’azione previdenziale (art. 47)
- D.L. 269/2003 — decadenza semestrale nell’invalidità civile (art. 42)
- D.Lgs. 168/2003 — sezioni specializzate in materia di impresa (artt. 3 e 4)
- L. 249/1997 — tentativo obbligatorio di conciliazione al Corecom (art. 1, comma 11)
- L. 481/1995 — conciliazione presso le autorità di regolazione dei servizi (art. 2, comma 24)
- Reg. UE 2021/782 — diritti dei passeggeri ferroviari (artt. 18, 19, 28)
- Reg. UE 2022/2065 — servizi digitali, responsabilità dei prestatori (artt. 6, 8, 16)

Importazione (crea da sola un backup del database prima di scrivere):

    python -m lex.normativa.consultazione --source lex/normativa/integrazioni/biblioteca_20261020 \
        --db /data/normativa/codici_leggi.sqlite --updated-at 2026-10-20
