# Setup esterno consigliato per Open Design

Open Design va usato come laboratorio esterno, non come dipendenza interna di IUSENTRA.

## Posizione consigliata

Esempi:

```text
D:\tools\open-design
```

oppure:

```text
D:\legale\open-design
```

Non clonare Open Design dentro la repo IUSENTRA.

## Requisiti tipici

Open Design richiede un ambiente Node/pnpm separato.
Prima di usarlo verificare:

```powershell
node --version
pnpm --version
corepack --version
codex --version
```

## Uso consigliato con IUSENTRA

1. Usare Open Design per prototipo HTML/mockup/deck.
2. Usare `tools/open-design-support/IUSENTRA_DESIGN.md` come design system.
3. Usare le skill in `tools/open-design-support/skills/`.
4. Salvare eventuali prototipi fuori dal runtime IUSENTRA.
5. Integrare in IUSENTRA solo dopo review manuale.
6. Codex deve tradurre il prototipo in Jinja/React/CSS rispettando l'architettura reale.

## Divieti

- Non aggiungere Open Design a `requirements.txt`.
- Non aggiungere Open Design a `pyproject.toml`.
- Non installare pacchetti Node dentro IUSENTRA per questo workflow.
- Non copiare automaticamente artifact generati dentro `web/` senza review.
- Non modificare UI prodotto senza scope e test.
