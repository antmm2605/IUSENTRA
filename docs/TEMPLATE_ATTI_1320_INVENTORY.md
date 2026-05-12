# Template Atti 1320 - Inventario STRICT

Aggiornato: 2026-05-12.

## Esito rilevazione

- Totale atteso dalla missione: 1320.
- Totale template canonici governati: 1320.
- Scostamento canonico: 0.
- Totale record di fonte ispezionati: 4576.
- Copie/record duplicati di fonte: 3256.
- Gruppi con copie multiple: 710.
- Copertura inventario dichiarabile come 1320: si, sui template canonici; le copie JSON/SQLite/tenant restano tracciate come evidenze di fonte.

## Fonti ispezionate

- Catalogo master JSON: 420.
- Split JSON: core 122, advanced 186, specialist 92, studio interno 20.
- Template compilatore: 192.
- Template redazione/workspace canonici: 708.
- Repository JSON globale: 708.
- Repository JSON tenant: 709.
- Repository SQLite globale: 708.
- Repository SQLite tenant: 709.
- Template custom tenant JSON: 2 record.

## Copertura capability

- Template canonici con profilo Cartabia o metadati Cartabia recuperati: 1320.
- Template canonici con prefill bindings recuperati: 1320.
- Template canonici con supporto timbro centrale: 1320.
- Template canonici con binding/fallback compilatore recuperato da fonti interne: 1320.
- Template canonici con renderer rilevato: 1320.
- Template non raggiungibili dal catalogo unificato: 0.
- Template con conflitto non riconciliato tra copie fonte: 0.
- Template con copie fonte riconciliate automaticamente: 1156.
- Template promossi a `cartabia_ready` come modelli governati: 1320.
- Template in revisione Cartabia: 0.

## Riconciliazione dei duplicati

Il precedente conteggio 3868 era un conteggio parziale dei record di fonte, non del catalogo operativo: sommava copie master/split, repository JSON, SQLite e tenant. L'inventario ora separa:

- catalogo canonico governato: 420 master, 192 compilatore, 708 workspace/repository = 1320;
- record di fonte ispezionati: 4576, inclusi JSON, SQLite e tenant;
- duplicati di fonte: 3256 copie eccedenti, mantenute nel report e non usate per gonfiare il catalogo.

Questa riconciliazione non corregge numeri a mano: ogni record resta visibile in `docs/reports/template_atti_inventory.md` e `docs/reports/template_atti_inventory.json`, mentre il catalogo unificato usa una sola identita canonica per template.

Regola STRICT applicata ora: una copia duplicata non e' un problema solo contabile. Se le copie dello stesso template hanno metadati discordanti ma riconciliabili, il template canonico usa la fonte autorevole e il report conserva la riconciliazione. Solo conflitti non decidibili, fonti normative mancanti o capability assenti bloccano il modello in `cartabia_review_required`.

La mancanza di una pratica selezionata non blocca il template: `Cliente / Mittente`, `Pratica Collegata`, `Destinatario / Ufficio Giudiziario` e `Autore` sono binding obbligatori del prefill e vengono valorizzati quando l'avvocato seleziona template e contesto operativo.

## Comando

```powershell
python scripts\template_atti\build_template_inventory.py
```

Il comando aggiorna `docs/reports/template_atti_inventory.md` e `docs/reports/template_atti_inventory.json`.
