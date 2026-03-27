import os
from web.app import create_app

# Forziamo una configurazione compatibile con Vercel
os.environ['DATABASE_URL'] = 'sqlite:////tmp/hacs.db'
os.environ['PCT_STUDIO_CONFIG'] = '/tmp/studio.json'

app = create_app()

# Esportazione per Vercel
app = app
