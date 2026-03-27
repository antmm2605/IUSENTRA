import os
import sys
from pathlib import Path

# --- 1. PREPARAZIONE AMBIENTE VERCEL ---
# Forza i percorsi in /tmp (l'unico posto scrivibile)
os.environ['PCT_STUDIO_CONFIG'] = '/tmp/studio.json'

# AGGIUNTA IMPORTANTE: Configura il Database SQL (Fascicoli/Clienti)
# Se non hai impostato DATABASE_URL su Vercel (Neon), usa un database temporaneo in /tmp
if 'DATABASE_URL' not in os.environ:
    os.environ['DATABASE_URL'] = 'sqlite:////tmp/hacs.db'

# --- 2. IL "TRUCCO" (Monkey Patching) ---
import pct.auth
import pct.agenda

# Patch per pct/auth.py
pct.auth.GestioneUtenti.__init__.__defaults__ = (
    "/tmp/utenti.json", 
    "/tmp/audit.json", 
    os.environ.get("PCT_SECRET_KEY", "chiave-segreta-temporanea"), 
    730, 
    True
)

# Patch per pct/agenda.py
pct.agenda.Agenda.__init__.__defaults__ = ("/tmp/appuntamenti.json",)

# AGGIUNTA: Se hai altre classi che scrivono file (es. Backup o Documenti),
# assicurati di reindirizzare anche quelle se necessario.

# --- 3. CARICAMENTO APPLICAZIONE ---
try:
    from web.app import create_app
    app = create_app()
except Exception as e:
    # Stampiamo l'errore completo nei log di Vercel se l'avvio fallisce
    print(f"ERRORE CRITICO AVVIO: {type(e).__name__}: {e}")
    raise e

# Export per il server Vercel
app = app
