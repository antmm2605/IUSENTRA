"""Flask error handler registration."""

from __future__ import annotations

import traceback

from flask import Flask

from web.services.errore_shell_runtime import render_errore_shell, risposta_statica


def register_error_handlers(app: Flask) -> None:
    """Register shared HTTP error handlers.

    403 e 404 sono pagine React (``ErroreApp``); il 500 è HTML statico autonomo, che non dipende
    né dai template né dal bundle React.
    """

    @app.errorhandler(403)
    def errore_403(error):
        return render_errore_shell(403)

    @app.errorhandler(404)
    def errore_404(error):
        return render_errore_shell(404)

    @app.errorhandler(500)
    def errore_500(error):
        tb_str = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        app.logger.error("500 Internal Server Error: %s\n%s", error, tb_str)
        return risposta_statica("500.html", 500)
