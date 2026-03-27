# vercel_app.py
from web.app import create_app

# NON usiamo gevent qui, lasciamo che Vercel gestisca l'esecuzione
app = create_app()

# Vercel richiede che l'oggetto app sia accessibile
app = app
