import os
import sys
from pathlib import Path

# 1. FORZATURA IMMEDIATA (Monkey Patch)
# Importiamo il modulo auth e cambiamo i percorsi di default 
# prima che l'app Flask possa inizializzarli.
import pct.auth

# Definiamo i percorsi nella RAM (/tmp)
PATH_UTENTI = "/tmp/utenti.json"
PATH_AUDIT = "/tmp/audit.json"

# Sovrascriviamo il comportamento di GestioneUtenti
original_init = pct.auth.GestioneUtenti.__init__

def patched_init(self, *args, **kwargs):
    # Ignora i parametri passati e forza quelli di Vercel
    kwargs['db_path'] = PATH_UTENTI
    kwargs['audit_path'] = PATH_AUDIT
    return original_init(self, *args, **kwargs)

# Applichiamo la patch alla classe
pct.auth.GestioneUtenti.__init__ = patched_init

# 2. CONFIGURAZIONE AMBIENTE
os.environ['PCT_STUDIO_CONFIG'] = '/tmp/studio.json'
if 'DATABASE_URL' not in os.environ:
    os.environ['DATABASE_URL'] = 'sqlite:////tmp/hacs.db'

# 3. CARICAMENTO APPLICAZIONE
try:
    from web.app import create_app
    app = create_app()
except Exception as e:
    print(f"ERRORE CRITICO AVVIO: {e}")
    raise e

# Export per Vercel
app = app
