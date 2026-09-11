"""Memoria del testo gia' estratto dai documenti di un fascicolo.

Lex rileggeva ogni documento del fascicolo a ogni domanda: con dodici PDF di
quattro pagine servivano circa nove secondi per rispondere, e la domanda
successiva ricominciava da capo. Il contenuto di un documento pero' non cambia
fra una domanda e l'altra: qui viene tenuto da parte, con una chiave che
comprende data di modifica e dimensione del file, cosi' un documento
sostituito viene riletto e uno immutato no.

La memoria e' volutamente limitata: serve a non rifare lo stesso lavoro dentro
una sessione di lavoro, non a sostituire l'indice documentale.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from threading import Lock
from typing import Any, TypeVar

#  Quanti documenti tenere in memoria. Un fascicolo corposo ne ha qualche
#  decina: il limite copre piu' fascicoli aperti di seguito senza far crescere
#  la memoria del processo in modo indefinito.
CAPACITA_PREDEFINITA = 256

T = TypeVar("T")


class MemoriaEstrazioni:
    """Cache a capacita' limitata, sicura fra thread."""

    def __init__(self, capacita: int = CAPACITA_PREDEFINITA) -> None:
        self._capacita = max(1, int(capacita))
        self._voci: OrderedDict[tuple[Any, ...], Any] = OrderedDict()
        self._lock = Lock()
        self.letture = 0
        self.riusi = 0

    def _firma(self, percorso: Path, ambito: str) -> tuple[Any, ...] | None:
        """Identita' del file: percorso, data di modifica e dimensione.

        Se il file non e' leggibile non si memorizza nulla: meglio rifare il
        lavoro che servire il contenuto di un documento che non c'e' piu'.
        """

        try:
            stato = percorso.stat()
        except OSError:
            return None
        return (str(percorso), stato.st_mtime_ns, stato.st_size, ambito)

    def ottieni(self, percorso: Path, ambito: str, calcola: Callable[[], T]) -> T:
        """Restituisce il valore memorizzato, altrimenti lo calcola una volta."""

        chiave = self._firma(percorso, ambito)
        if chiave is None:
            return calcola()

        with self._lock:
            self.letture += 1
            if chiave in self._voci:
                self._voci.move_to_end(chiave)
                self.riusi += 1
                return self._voci[chiave]

        valore = calcola()

        with self._lock:
            self._voci[chiave] = valore
            self._voci.move_to_end(chiave)
            while len(self._voci) > self._capacita:
                self._voci.popitem(last=False)
        return valore

    def statistiche(self) -> dict[str, int]:
        with self._lock:
            return {
                "voci": len(self._voci),
                "capacita": self._capacita,
                "letture": self.letture,
                "riusi": self.riusi,
            }

    def svuota(self) -> None:
        with self._lock:
            self._voci.clear()
            self.letture = 0
            self.riusi = 0


#  Memoria condivisa dal processo: i worker hanno la propria, e va bene cosi',
#  perche' la chiave comprende sempre lo stato del file su disco.
MEMORIA_DOCUMENTI = MemoriaEstrazioni()
