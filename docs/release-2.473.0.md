# 2.473.0 — Catalogo dei documenti per tutte le materie (476 tipologie nuove, 10 esempi ciascuna)

Richiesta dell'avvocato del 02/11/2026: tutte le materie del diritto riconosciute, con esempi diversi per ogni caso.

- 476 regole d'identità nuove in sette moduli per area (`pct/document_intelligence/titoli/estesa_*.py`), ciascuna con
  la norma che definisce l'atto e la fonte Normattiva consultata il 02/11/2026:
  - penale (92): misure cautelari, sequestri, arresto e fermo, indagini e archiviazione, riti speciali, dibattimento,
    impugnazioni, esecuzione, sorveglianza (L. 354/1975), prevenzione (D.Lgs. 159/2011), minorile, enti (D.Lgs.
    231/2001), giudice di pace penale, MAE e OEI;
  - impresa, crisi, banca, assicurazioni e consumatori (78): D.Lgs. 14/2019, società, proprietà industriale e diritto
    d'autore, ABF/ACF, IVASS, azione di classe, AGCM, danno antitrust;
  - diritto pubblico (71): processo amministrativo, procedimento (L. 241/1990), appalti (D.Lgs. 36/2023), edilizia,
    ambiente, beni culturali e paesaggio, espropri, concorsi, Corte dei conti, enti locali;
  - persone e famiglia (62): filiazione, adozione, unioni civili e convivenze, tutela, stato civile, successioni,
    volontaria giurisdizione, immigrazione e cittadinanza;
  - Costituzione, Unione europea, CEDU e civile (62): giudizio costituzionale, rinvio pregiudiziale, Corte EDU, arbitrato,
    istruzione preventiva e prove, diritti reali e condominio, responsabilità sanitaria, contratti, ordinamento militare;
  - tributario, previdenza e lavoro (57): D.Lgs. 546/1992 (vigente fino al 31/12/2026), riscossione, INPS e INAIL,
    ispettorato del lavoro, rapporto di lavoro;
  - settori speciali (54): privacy, AGCOM/CORECOM, codice della strada, trasporti, L. 689/1981, ordinamento forense
    (L. 247/2012), spese di giustizia (D.P.R. 115/2002).
- Ogni regola ha un documento di prova e 10 varianti diverse (forma del titolo, ufficio, caso, lunghezza), tutte
  riconosciute con la voce attesa (`tests/test_catalogo_varianti_materie.py`); il generatore degli esempi di
  addestramento produce esempi per ogni voce nuova.
- «Memoria conclusionale» riconosciuta come comparsa conclusionale; esempi per comunicazione di cancelleria e rinvio
  d'ufficio.
- Le espressioni delle regole si compilano una volta sola (`catalog_titoli._modello`): con oltre 700 regole la cache di
  `re` si svuotava a ogni documento e la classificazione costava 0,37 s invece di 0,026 s.
- Fonte delle controdeduzioni tributarie corretta: oggi valgono gli artt. 18 e 23 D.Lgs. 546/1992; il Testo unico della
  giustizia tributaria (D.Lgs. 175/2024) si applica dal 01/01/2027.
