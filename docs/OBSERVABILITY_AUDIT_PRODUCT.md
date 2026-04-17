# Observability e Audit come Capability di Prodotto

## Punto di arrivo

Osservabilita' non significa solo metriche runtime. Nel prodotto devono esistere anche:

- visibilita' sullo stato storage e sulla parity di migrazione
- controllo delle superfici autorizzative
- audit degli accessi e delle azioni sensibili
- capability operative telematiche e AI leggibili dal pannello admin

## Capability attive

| Capability | Superficie | Output |
| --- | --- | --- |
| Metriche runtime HTTP e Lex | `admin/osservabilita` | latenze, p95, bucket endpoint, first token |
| Storage parity e migrazione | `admin/governance` | matrice R/W, fallback, wave di cutover |
| Audit accessi e ruoli | `admin/governance` | eventi audit, superfici presidiate, ruoli ammessi |
| Capability telematiche | Centro Servizi Telematici / Motori Legali | stato canali, fonti, warning, catalogo capability |
| Salute sistema | `admin/salute-sistema` | backup, OCR, provider locali, readiness deploy |

## Regole

- ogni superficie sensibile deve avere una lettura prodotto, non solo log tecnici
- i dati di audit devono essere esportabili in modo governato
- il pannello admin deve mostrare sia `runtime` sia `product capability`
- il deploy non e' chiuso se metriche, audit e storage manifest raccontano storie diverse
