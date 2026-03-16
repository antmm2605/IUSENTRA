"""
Entry point WSGI per produzione (Gunicorn, uWSGI, ecc.).

Uso:
    gunicorn wsgi:app
    gunicorn --bind 0.0.0.0:$PORT --workers 2 wsgi:app
"""
from web.app import create_app

app = create_app()
