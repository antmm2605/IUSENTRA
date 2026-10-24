"""Prova pubblica di acquisizione e coda persistente, senza dati dello studio."""
import html
import json
import sys
import tempfile
import time
from hashlib import sha256
from pathlib import Path

from flask import Flask, render_template

from web.services.openga_document_jobs import _queue, start, status

identity, reference = json.loads(sys.argv[1]), json.loads(sys.argv[2])
app = Flask("verifica-lettura-pubblica", template_folder="/app/web/templates", static_folder="/app/web/static")
with tempfile.TemporaryDirectory(prefix="iusentra-lettura-collaudo-") as folder:
    path = str(Path(folder) / "lettura.db")
    result = start(app, db_path=path, payload=reference)
    if _queue(path).get(result["job_id"]).payload["identita"] != identity:
        raise RuntimeError("Identità della coda diversa dal catalogo verificato")
    deadline = time.monotonic() + 160
    while result.get("stato") == "in_corso" and time.monotonic() < deadline:
        time.sleep(0.5)
        result = status(path, result["job_id"])
    if result.get("stato") != "acquisito":
        raise RuntimeError("Lettura ufficiale sul server non completata: " + result.get("stato", "ignoto"))
    document = result["documento"]
    with app.test_request_context():
        rendered = render_template("giurisprudenza/testo_ufficiale.html", documento=document)
    if not all(line.strip() in html.unescape(rendered) for line in document["testo"].splitlines() if line.strip()):
        raise RuntimeError("Testo incompleto nella pagina HTML")
    print(json.dumps({"stato": result["stato"], "caratteri": len(document["testo"]),
                      "provenienza": document["provenienza"], "raw_sha256": document["raw_sha256"],
                      "approvazione_automatica": False, "scritture_dati_studio": False,
                      "coda_persistente_verificata": True, "html_consultabile_verificato": True,
                      "html_sha256": sha256(rendered.encode()).hexdigest()}))
