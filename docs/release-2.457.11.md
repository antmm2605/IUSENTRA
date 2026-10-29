# Release 2.457.11

- Il riepilogo del censimento riporta solo voci del catalogo governato: il documento d'identità intitolato al titolare diventa il tipo di documento, le etichette scritte a mano o dedotte dal nome del file diventano «Voce fuori elenco». Nessun nome di cliente esce dal server.

## Base normativa
- GDPR 2016/679 art. 5, par. 1, lett. c) (minimizzazione) e art. 25 (protezione dei dati fin dalla progettazione); D.Lgs. 196/2003.

## Verifiche
- tests/test_verita_catalogo.py::test_il_riepilogo_non_porta_nomi_dei_clienti.
