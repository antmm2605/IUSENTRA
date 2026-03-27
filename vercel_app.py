import os
from web.app import create_app

# Forziamo una configurazione compatibile con Vercel
os.environ['PCT_STUDIO_CONFIG'] = '/tmp/studio.json' 

app = create_app()

# Esportazione per Vercel
app = app
