# Accessibility Report React

Generato: 2026-05-08

## Controlli applicati

- Nuovi componenti con `role=status`, `aria-live`, `aria-label` e focus ring compatibili con il design system.
- `IusErrorState` separa messaggio utente e dettagli tecnici espandibili.
- `IusWizardStepper` espone `aria-current` sul passo attivo.
- `IusChannelCard`, `IusMessageList` e `LexPanel` usano testo visibile, badge e label esplicite, non solo colore.

## Problemi corretti

- CTA legacy primarie rimosse dalle route promosse.
- Stati di compliance distinguono "Non verificato", "Fonte mancante", "Fallback attivo" e "Revisione manuale richiesta".

## Rischi residui

- Serve passaggio browser/tastiera completo sulle route principali dopo build finale.
- Route rimaste legacy non sono coperte da questo hardening React.
