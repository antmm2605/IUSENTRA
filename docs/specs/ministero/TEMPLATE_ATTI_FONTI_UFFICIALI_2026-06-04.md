# Template Atti - fonti ufficiali integrate

Data consultazione: 4 giugno 2026.

Questo registro documenta i riferimenti normativi usati dall'editor Template Atti per proporre integrazioni nel pannello `Fonti` e nelle proposte Lex. Il software non copia il testo degli articoli e non inserisce riferimenti in automatico: l'avvocato deve accettare o modificare ogni richiamo prima di usarlo nel documento.

## Fonti consultate

- Normattiva, Codice civile, R.D. 16 marzo 1942, n. 262: riferimento usato per `art. 1219 c.c.` nei modelli di diffida, messa in mora, inadempimento e sollecito.
  URL: https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=042U0262&atto.dataPubblicazioneGazzetta=1942-04-04&tipoDettaglio=vigente
- Normattiva, Codice di procedura civile, R.D. 28 ottobre 1940, n. 1443: riferimento usato per `art. 167 c.p.c.` nei modelli di comparsa di costituzione e risposta e per `art. 163 c.p.c.` nei controlli sugli atti di citazione.
  URL: https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=040U1443&atto.dataPubblicazioneGazzetta=1940-10-28&tipoDettaglio=vigente
- EUR-Lex, Regolamento (UE) 2016/679: riferimento usato per `art. 6 GDPR` e `art. 13 GDPR` nei controlli privacy, basi giuridiche e informative.
  URL: https://eur-lex.europa.eu/eli/reg/2016/679/oj/ita

## Regola software

- I riferimenti sono proposte redazionali, non contenuto automatico del template.
- Lex può mostrarli in diff e il pannello `Fonti` può inserirli nel documento solo su click esplicito.
- Se un modello non corrisponde chiaramente a una fonte, il sistema mostra un riferimento prudenziale e mantiene la revisione professionale.
- Il codice del fascicolo e gli eventuali codici ufficiali di deposito restano separati dalla Guida Pratica e non vengono sovrascritti da questi riferimenti.

## Implementazione collegata

- Registro runtime: `pct/template_atti_legal_sources.py`.
- Esposizione React: `web/blueprints/api_v1_react.py`, campo `compliance.normativeReferences`.
- UI: pannello `Fonti` dell'editor professionale Template Atti.
