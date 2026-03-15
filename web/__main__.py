"""Avvio server: python -m web"""
import os
from .app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PCT_PORT", 5000))
    debug = os.getenv("PCT_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
