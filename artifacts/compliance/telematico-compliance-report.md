# Telematico Compliance Report

## Canali

PST/PolisWeb, PDP, PAT/SIGA, PTT/SIGIT, SIGP, Depositi, Import assistito e Local Signer restano distinti nel registro fonti e nelle regole operative.

## Controlli

- Nessuna automazione portali introdotta.
- Nessuno scraping HTML introdotto.
- PIN, certificati e credenziali non sono stati esposti.
- Route portali e deposito restano legacy per non dichiarare full React senza validazioni reali.
- Aggiunti componenti `IusChannelCard`, `IusWizardStepper`, `IusCompliancePanel` per stati futuri trasparenti.

## Fonti

PST, Ministero Giustizia, specifiche PCT art. 34, Giustizia Amministrativa, Giustizia Tributaria e SIGP sono registrati in `pct/data/legal_sources_registry.json`.

## Gap

Validazione XSD, DatiAtto.xml, allegati obbligatori, dimensione busta e conformita portale devono restare "da verificare" finche non esiste controllo reale.
