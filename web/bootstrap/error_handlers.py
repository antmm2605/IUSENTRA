"""Flask error handler registration."""

from __future__ import annotations

import traceback

from flask import Flask, render_template


def register_error_handlers(app: Flask) -> None:
    """Register shared HTTP error handlers."""

    @app.errorhandler(403)
    def errore_403(error):
        return render_template("errori/403.html"), 403

    @app.errorhandler(404)
    def errore_404(error):
        return render_template("errori/404.html"), 404

    @app.errorhandler(500)
    def errore_500(error):
        tb_str = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        app.logger.error("500 Internal Server Error: %s\n%s", error, tb_str)
        return render_template("errori/500.html"), 500
