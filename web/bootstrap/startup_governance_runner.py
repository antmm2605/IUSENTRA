"""Runner separato per la governance di avvio non critica.

Il processo web deve diventare pronto rapidamente: pack governance, indice
utenti tenant e bootstrap legacy vengono eseguiti qui, fuori dai worker
Gunicorn, con i lock definiti in runtime_bundle.
"""

from __future__ import annotations

import logging

from web.bootstrap.flask_app_factory import create_flask_app
from web.bootstrap.runtime_bundle import _run_startup_governance


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    app, _cfg = create_flask_app(None)
    with app.app_context():
        _run_startup_governance(app)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
