# Open Design brief operativo

## Superficie

App shell e dashboard prodotto: sidebar, topbar, pagine React operative, pannelli, KPI, tabelle, form e stati vuoti.

## Skill Open Design usata

`dashboard`, usata come riferimento di workflow per superfici operative dense: navigazione prevedibile, gerarchia dati chiara, componenti con stati completi, layout responsive e nessun prototipo HTML separato nel prodotto.

## Direzione visiva

Fonte primaria: token IUSENTRA e documentazione interna (`docs/DESIGN_TOKENS.md`, piano React e top bar operativa). Fonte di controllo qualita: Open Design `Neutral Modern`, con tema chiaro, accento sobrio, superfici tintate e densita utile per lavoro legale.

## Principi applicati

- UI product-first: chiarezza operativa prima dell'effetto visivo.
- Neutrali tintati e token condivisi, evitando nero/bianco puri nei nuovi token.
- Focus, hover, active, disabled, empty e error states espliciti.
- Accento usato per azioni primarie, selezione e stati, non come decorazione.
- Niente card annidate, side-stripe spesse, gradient text o glassmorphism decorativo.

## Limiti

Open Design non e' stato aggiunto come dipendenza runtime. Il clone temporaneo serve solo come riferimento e deve essere rimosso a fine lavoro.
