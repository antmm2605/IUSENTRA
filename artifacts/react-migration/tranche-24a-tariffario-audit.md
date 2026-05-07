# Tranche 24A - Audit tariffario

## Route legacy
- `/tariffario`: consultazione e calcolo tariffario backend.
- `/compensi-forensi`: collegamento operativo ai compensi.
- `/preventivi` e `/preventivi/nuovo`: collegamenti a preventivi, senza spostare calcolo in React.

## Contratto legacy rilevato
- Capture non autenticata: redirect a login, coerente con sessione obbligatoria.
- Handler/servizi: `web/services/react_tariffario_bridge.py`, `web/services/react_tariffario_compute.py`, tabelle normative e motore backend.
- Template legacy: non rimosso.
- POST/calcolo: simulazione/calcolo backend gia presente via servizio.

## Strutture dati
- Versioni/tabelle normative: lette dal backend.
- Aree/procedimenti/fasi/scaglioni: derivate da cataloghi e tabelle backend.
- Voci tariffarie: profili/regole tariffarie reali.
- Collegamenti: compensi/preventivi solo come link o azione backend supportata.
- Calcolo tariffario/DM55: backend canonico.

## Gap per react_operational_full
- Contratto `writes: json_api`.
- GET JSON `/api/v1/ui/tariffario`.
- POST JSON `/api/v1/ui/tariffario/calcola` con validazione campi ignoti.
- Detail JSON sintetico voce.
- Check anti-formule/scaglioni frontend.
