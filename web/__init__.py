"""Web application per lo studio legale (PCT + Agenda)."""
"""Web application per lo studio legale (PCT + Agenda)."""

import os
from flask import Flask, g, request
from datetime import datetime


def create_app(config=None):
    """Crea e configura l'applicazione Flask."""
    
    app = Flask(
        __name__,
        static_folder='static',
        static_url_path='/static'
    )
    
    # ═══════════════════════════════════════════════════
    # CONFIGURAZIONE BASE
    # ═══════════════════════════════════════════════════
    app.config["SECRET_KEY"] = os.getenv("PCT_SECRET_KEY", "dev-key-change-in-production")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("PCT_HTTPS", "").lower() in ("1", "true", "yes")
    
    # Versione app (da setup.py o hardcoded)
    try:
        from pct import __version__
        app.config["APP_VERSION"] = __version__
    except:
        app.config["APP_VERSION"] = "2.27.8"
    
    # ═══════════════════════════════════════════════════
    # CONTEXT PROCESSORS (variabili globali per template)
    # ═══════════════════════════════════════════════════
    @app.context_processor
    def inject_app_version():
        """Aggiunge la versione dell'app a tutti i template."""
        return dict(app_version=app.config.get("APP_VERSION", "2.27.8"))
    
    @app.context_processor
    def inject_file_version():
        """Aggiunge funzione per versioning file statici basato su timestamp."""
        def file_version(filepath):
            try:
                full_path = os.path.join(app.static_folder, filepath)
                return str(int(os.path.getmtime(full_path)))
            except Exception:
                return "1"
        return dict(file_version=file_version)
    
    @app.context_processor
    def inject_now():
        """Aggiunge funzione now() ai template."""
        return dict(now=datetime.now)
    
    # ═══════════════════════════════════════════════════
    # CACHE CONTROL (solo in sviluppo)
    # ═══════════════════════════════════════════════════
    @app.after_request
    def add_header_development(response):
        """Disabilita cache CSS/JS solo in modalità debug."""
        if app.debug:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "-1"
            
            # Forza ricaricamento per file statici
            if request.path.startswith('/static/'):
                response.headers["Cache-Control"] = "no-store"
        
        return response
    
    # ═══════════════════════════════════════════════════
    # REGISTRAZIONE BLUEPRINT
    # ═══════════════════════════════════════════════════
    from web.blueprints.fascicoli import fascicoli
    app.register_blueprint(fascicoli, url_prefix='/fascicoli')
    
    from web.blueprints.template_atti import template_atti
    app.register_blueprint(template_atti, url_prefix='/template-atti')
    
    # Aggiungi altri blueprint qui...
    # from web.blueprints.clienti import clienti
    # app.register_blueprint(clienti, url_prefix='/clienti')
    
    # ═══════════════════════════════════════════════════
    # ROUTE PRINCIPALI
    # ═══════════════════════════════════════════════════
    @app.route("/")
    def index():
        """Pagina principale."""
        from flask import redirect, url_for
        return redirect(url_for('fascicoli.lista'))
    
    @app.route("/health")
    def health():
        """Health check per Railway/production."""
        return {"status": "ok", "version": app.config["APP_VERSION"]}
    
    # ═══════════════════════════════════════════════════
    # ERROR HANDLERS
    # ═══════════════════════════════════════════════════
    @app.errorhandler(404)
    def not_found(error):
        from flask import render_template
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        return render_template('errors/500.html'), 500
    
    return app


# ═══════════════════════════════════════════════════
# PUNTO DI INGRESSO (python -m web)
# ═══════════════════════════════════════════════════
if __name__ == '__main__':
    app = create_app()
    app.run(
        host=os.getenv("PCT_HOST", "0.0.0.0"),
        port=int(os.getenv("PCT_PORT", "5000")),
        debug=os.getenv("PCT_DEBUG", "true").lower() in ("1", "true", "yes")
    )
