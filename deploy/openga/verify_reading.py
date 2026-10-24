"""Prova pubblica positiva sul runtime applicativo, senza scrivere dati studio."""
import json
import sys

from pct.openga_recupero import recupera_testo

identity = json.loads(sys.argv[1])
result = recupera_testo(identity)
if result.get("stato") != "acquisito":
    raise RuntimeError("Lettura ufficiale sul server non completata: " + result.get("stato", "ignoto"))
document = result["documento"]
print(json.dumps({"stato": result["stato"], "caratteri": len(document["testo"]),
                  "provenienza": document["provenienza"], "raw_sha256": document["raw_sha256"],
                  "approvazione_automatica": False, "scritture_dati_studio": False}))
