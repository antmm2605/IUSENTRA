# Design token IUSENTRA

`tokens.json` e `web/static/scss/_design-tokens.scss` definiscono i token canonici dell'interfaccia IUSENTRA: colori, tipografia, spaziature, raggi, ombre, motion e dimensioni minime dei target interattivi.

## Uso rapido

I token CSS sono caricati dai bundle ufficiali `app.css` e `design-system.css`.

```css
.azione-principale {
  min-height: var(--size-touch-min);
  color: var(--color-text-inverse);
  background: var(--color-brand-primary);
  border-radius: var(--radius-m);
  box-shadow: var(--elevation-level1);
}
```

## Accessibilita

- Testo normale: contrasto minimo 4.5:1.
- Testo grande: contrasto minimo 3:1.
- Target interattivi: almeno 44x44 px.
- Motion: rispettare `prefers-reduced-motion`.

## QA in CI

I controlli sono in `tests/test_design_tokens.py` e verificano:

- struttura minima dei token;
- contrasto WCAG del testo principale su superficie;
- touch target minimo;
- token motion in millisecondi;
- elevation con valori `rgba`;
- icona store SVG con `viewBox`, pochi path e senza trasformazioni annidate.

Esecuzione:

```bash
python -m pytest tests/test_design_tokens.py -q
```
