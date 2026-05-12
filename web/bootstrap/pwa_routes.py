"""Infrastructure routes for the PWA shell."""

from __future__ import annotations

from flask import Flask, render_template, send_file


def register_pwa_routes(app: Flask) -> None:
    """Register service worker and offline fallback routes."""

    @app.route("/favicon.ico")
    def favicon():
        return send_file(
            app.root_path + "/static/img/logo-iusentra.png",
            mimetype="image/png",
        )

    @app.route("/sw.js")
    def service_worker():
        response = send_file(
            app.root_path + "/static/sw.js",
            mimetype="application/javascript",
        )
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.route("/manifest.webmanifest")
    def web_manifest():
        return send_file(
            app.root_path + "/static/manifest.webmanifest",
            mimetype="application/manifest+json",
        )

    @app.route("/offline")
    def offline():
        return render_template("offline.html")
