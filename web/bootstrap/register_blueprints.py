"""Centralized blueprint registration for the web application."""

from __future__ import annotations

from flask import Flask


def register_blueprints(app: Flask) -> None:
    """Register all modular blueprints on the Flask app."""
    # Imported here to avoid circular imports:
    # blueprints use web.helpers which relies on current_app during requests.
    from web.blueprints.admin import admin_bp
    from web.blueprints.api_v1 import api_v1
    from web.blueprints.applicazioni import applicazioni as applicazioni_bp
    from web.blueprints.assistente import assistente as assistente_bp
    from web.blueprints.email_client import email_client as email_client_bp
    from web.blueprints.export_csv import export_csv as export_csv_bp
    from web.blueprints.fatturazione import fatturazione as fatturazione_bp
    from web.blueprints.giurisprudenza import giurisprudenza as giurisprudenza_bp
    from web.blueprints.impostazioni import impostazioni as impostazioni_bp
    from web.blueprints.legal_intelligence import legal_intelligence as legal_intelligence_bp
    from web.blueprints.notifiche import notifiche as notifiche_bp
    from web.blueprints.pagamenti import pagamenti as pagamenti_bp
    from web.blueprints.portale import portale as portale_bp
    from web.blueprints.preventivi import preventivi as preventivi_bp
    from web.blueprints.statistiche import statistiche as statistiche_bp
    from web.blueprints.strumenti_legali import strumenti_legali as strumenti_legali_bp
    from web.blueprints.template_atti import template_atti as template_atti_bp
    from web.blueprints.wizard_pro import wizard_pro_bp

    app.register_blueprint(api_v1)
    app.register_blueprint(portale_bp)
    app.register_blueprint(fatturazione_bp)
    app.register_blueprint(notifiche_bp)
    app.register_blueprint(template_atti_bp)
    app.register_blueprint(statistiche_bp)
    app.register_blueprint(legal_intelligence_bp)
    app.register_blueprint(giurisprudenza_bp)
    app.register_blueprint(export_csv_bp)
    app.register_blueprint(pagamenti_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(impostazioni_bp)
    app.register_blueprint(email_client_bp)
    app.register_blueprint(assistente_bp)
    app.register_blueprint(preventivi_bp)
    app.register_blueprint(strumenti_legali_bp)
    app.register_blueprint(applicazioni_bp)
    app.register_blueprint(wizard_pro_bp)
