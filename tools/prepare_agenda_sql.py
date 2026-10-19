"""Adozione Agenda mediante il cutover calendario esistente, fuori dalle richieste."""
from tools.prepare_scadenziario_sql import main


if __name__ == '__main__':
    raise SystemExit(main(domain='agenda'))
