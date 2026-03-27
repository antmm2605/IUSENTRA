import os
import sys
from pathlib import Path

# 1. IMPORTIAMO IL MODULO AUTH PER PRIMO
import pct.auth

# 2. CREIAMO UNA VERSIONE "VERCEL-FRIENDLY" DELLA CLASSE
# Questa versione ignora i percorsi passati e usa sempre /tmp/
class VercelGestioneUtenti(pct.auth.GestioneUtenti):
    def __init__(self, *args, **kwargs):
        # Forziamo i parametri db_path e audit_path
        kwargs['db_path'] = "/tmp/utenti.json"
        kwargs['audit_path'] = "/tmp/audit.json"
        # Chiamiamo il costruttore originale con i nuovi percorsi
        super().__init__(*args, **kwargs)

# 3. SOSTITUIAMO LA CLASSE ORIGINALE CON QUELLA MODIFICATA
# Da questo momento in poi, chiunque chiami GestioneUtenti userà la nostra versione
pct.auth.GestioneUtenti = VercelGestioneUtenti

# 4. CONFIGURAZIONE AMBIENTE
os.environ['PCT_STUDIO_CONFIG'] = '/tmp/studio.json'
if 'DATABASE_URL' not in os.environ:
    os.environ['DATABASE_URL'] = 'sqlite:////tmp/hacs.db'

# 5. ORA POSSIAMO CARICARE L'APP IN SICUREZZA
try:
    from web.app import create_app
    app = create_app()
except Exception as e:
    print(f"ERRORE CRITICO AVVIO: {e}")
    raise e

app = app
