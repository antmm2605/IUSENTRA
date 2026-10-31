# 2.466.1 — Sblocco del deploy, Panoramica più veloce e motivi degli scarti

- **CI**: la rimisura della copertura della versione già accettata (2.461.1) superava i 5 minuti nella parte 6 e fermava ogni deploy dal 29/10; la sola rimisura della baseline ha ora 10 minuti, le parti della candidata restano a 5.
- **Sicurezza (CodeQL py/polynomial-redos)**: l'indirizzo del mittente delle notifiche si estrae con una scansione lineare, senza espressione regolare non ancorata.
- **Panoramica (V12)**: la posta in arrivo si legge dalle colonne indicizzate (non letti e messaggi recenti) invece di caricare l'intera casella (oltre 2.000 messaggi, circa 2 secondi).
- **Letture (V13)**: il riepilogo dell'archivio indica perché i fatti sono stati respinti dal collaudo, raggruppati per controllo.
