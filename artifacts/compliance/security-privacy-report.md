# Security Privacy Report

## Controlli

- Nessun segreto, PIN, token o certificato aggiunto al frontend.
- Nessun localStorage/sessionStorage introdotto nei componenti nuovi.
- Nessun fetch esterno introdotto nelle route promosse.
- Registry fonti usa solo URL ufficiali HTTPS.
- Route portali/impostazioni restano legacy per non esporre credenziali o sessioni.

## Azioni sensibili da auditare

Upload/download/eliminazione documento, firma, preparazione deposito, invio comunicazione, salvataggio output Lex, modifica fascicolo/preventivo, fattura/parcella, cambio permessi, amministrazione.

## Gap

Test multi-tenant e permessi completi restano necessari su documenti, PEC, Lex e telematico.
