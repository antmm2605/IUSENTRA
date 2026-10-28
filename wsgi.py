"""
Entry point WSGI per produzione (Gunicorn, uWSGI, ecc.).

Uso:
    gunicorn wsgi:app
    gunicorn --bind 0.0.0.0:$PORT --worker-class gevent --workers 2 wsgi:app
"""
# La strategia di concorrenza appartiene al worker del server.
# Gunicorn gevent applica già le proprie patch prima di caricare l'app;
# imporle qui rompe i thread nativi del worker gthread e il suo heartbeat.

from web.app import create_app

app = create_app()
