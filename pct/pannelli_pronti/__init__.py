"""Pannelli pronti del fascicolo: payload già calcolati dal loro motore, validi finché le fonti non cambiano.

Il pacchetto contiene solo dominio e persistenza:

- ``revisioni``: contatori di revisione per fascicolo (e per tabella senza fascicolo), aggiornati da trigger SQL
  nelle stesse transazioni che modificano le fonti;
- ``impronta``: l'impronta delle fonti di un fascicolo, calcolata con poche query indicizzate;
- ``archivio``: il database dedicato dello studio (``intelligence/pannelli_pronti.db``) con i payload salvati.

L'orchestrazione (richiesta web, profilo dei permessi, ricalcolo in sfondo) sta in
``web/services/pannelli_pronti_runtime.py``.
"""
