"""Impronta privata della configurazione effettiva del backend PostgreSQL."""
import hashlib
import json


def postgres_configuration_key(database) -> str:
    values = [str(getattr(database, field, '') or '').strip()
              for field in ('host', 'db_name', 'utente')]
    values.extend((str(getattr(database, 'password', '') or ''),
                   int(getattr(database, 'porta_effettiva', 0) or 5432),
                   bool(getattr(database, 'ssl', False))))
    # La chiave resta nella richiesta e non espone credenziali nei report.
    return hashlib.sha256(json.dumps(values).encode('utf-8')).hexdigest()
