"""Serializzazione dei file del medesimo fascicolo, senza copie su disco.

Il lock non sostituisce il confronto SQL: impedisce che il recupero dei byte
di un comando fallito sovrascriva un altro comando documentale già riuscito.
"""
from functools import wraps
from hashlib import sha256
from pathlib import Path

from pct.prima_nota_transition import prima_nota_source_lock


def serialized_documents(method):
    @wraps(method)
    def run(self, id_fasc, *args, **kwargs):
        key = sha256(str(id_fasc).encode('utf-8')).hexdigest()
        path = Path(self.db_path).parent / '.iu-document-locks' / key
        with prima_nota_source_lock(path):
            return method(self, id_fasc, *args, **kwargs)
    return run
