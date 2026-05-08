# Full React accessibility check

Generato: 2026-05-08T09:10:14.073Z

## Verifiche strutturali

- Focus visibile: presente su bottoni, navigazione, input e search.
- Pulsanti iconici: i nuovi `IconButton` richiedono `label` e impostano `aria-label`.
- Form field: `TextField`, `DateField`, `Select`, `TextArea` espongono label reali.
- Modali/drawer: role `dialog`, `aria-modal` e pulsante `Chiudi`.
- Stati: `LoadingState`, `EmptyState`, `ErrorState`, `PermissionDeniedState` disponibili in italiano.

## Limite residuo

Serve verifica browser/tastiera sulle singole pagine migrate per confermare ESC, focus trap e assenza di sovrapposizioni su dati reali.
