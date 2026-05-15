---
name: Controllo rinnovi
description: Estrae date, rinnovi, disdette e azioni da verificare in un contratto.
argument-hint: Carica contratto o riepilogo e indica data di riferimento.
user-invocable: true
allowed-tools:
  - document_context
  - studio_profile
references:
  - Contratto caricato dallo studio
required-context:
  - contratto
  - data_riferimento
output-schema:
  - Scadenze
  - Rinnovi
  - Disdette
  - Azioni
  - Fonti
source-mode: strict
---

Individua solo date e obblighi presenti nel documento o nel fascicolo.
Se una data non e' esplicita, segnala lacuna e non inventarla.
Ogni azione deve restare bozza da verificare prima di aggiornare agenda o scadenziario.
