"""
Entry point WSGI per produzione (Gunicorn, uWSGI, ecc.).

Uso:
    gunicorn wsgi:app
    gunicorn --bind 0.0.0.0:$PORT --worker-class gevent --workers 2 wsgi:app
"""
# Il monkey patching deve avvenire prima di qualsiasi altro import
# per rendere I/O e threading compatibili con gevent (necessario per SSE).
from gevent import monkey
monkey.patch_all()

from web.app import create_app

app = create_app()
