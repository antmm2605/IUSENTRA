"""Prova pubblica: lettura riuscita oppure indisponibilità puntuale riscontrata."""
import html
import json
import sys
import tempfile
import time
from hashlib import sha256
from pathlib import Path

# Eccezione autorizzata il 29/10/2026 dopo il controllo sul portale ufficiale.
# Non è una lettura: il link della ricerca ufficiale apre questa precisa pagina
# di documento assente/rimosso. Un'altra risorsa, pagina o errore resta bloccante.
UNAVAILABLE_REFERENCE = {
    "relazione_id": "015|SENTENZA|2019|201900341|201800345",
    "resource_id": "5d568c50-7e0e-449d-af7a-43a84cb15aa8",
    "resource_sha256": "e9b12a1e4c1f46df0131515cb3f6cda719718b604646d7e8c61416cc2abb1d75",
}
UNAVAILABLE_IDENTITY = {
    "sede": "015", "tipo": "SENTENZA", "anno": 2019,
    "numero": "201900341", "ricorso": "201800345",
}
MISSING_PAGE_SHA256 = "e0bd0cddc8d06e07a6e357b6f6bfde5694d13b62d044570d94815007fe96b65a"


def expected_unavailability(identity, reference, result):
    """Solo il caso autorizzato e i byte della pagina d'errore già riscontrata."""
    if not isinstance(identity, dict) or not isinstance(result, dict):
        return False
    if reference != UNAVAILABLE_REFERENCE:
        return False
    if any(identity.get(key) != value for key, value in UNAVAILABLE_IDENTITY.items()):
        return False
    if (result.get("stato") != "non_trovato" or result.get("documento")
            or result.get("approvazione_automatica") is True
            or result.get("approvazione_avvocato") is True
            or result.get("lettura_confermata") is True):
        return False
    evidence = result.get("diagnostica")
    if not isinstance(evidence, list) or len(evidence) != 3:
        return False
    return all(isinstance(row, dict)
        and row.get("variante") == variant
        and row.get("stato_http") == 200 and row.get("trasporto") == "ok"
        and row.get("byte") == 1535 and row.get("sha256") == MISSING_PAGE_SHA256
        and bool(row.get("rifiuto"))
        for row, variant in zip(evidence, ("01", "20", "11")))


def verify(identity, reference):
    from flask import Flask, render_template
    from web.services.openga_document_jobs import _queue, start, status

    app = Flask("verifica-lettura-pubblica", template_folder="/app/web/templates",
                static_folder="/app/web/static")
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
            if expected_unavailability(identity, reference, result):
                return {"stato": "non_trovato", "fonte_indisponibile_verificata": True,
                        "lettura_confermata": False, "caratteri": 0,
                        "approvazione_automatica": False, "scritture_dati_studio": False,
                        "coda_persistente_verificata": True,
                        "html_consultabile_verificato": False,
                        "relazione_id": reference["relazione_id"],
                        "diagnostica": result["diagnostica"]}
            raise RuntimeError("Lettura ufficiale sul server non completata: "
                + result.get("stato", "ignoto") + "; diagnostica="
                + json.dumps(result.get("diagnostica", [])))
        document = result["documento"]
        with app.test_request_context():
            rendered = render_template("giurisprudenza/testo_ufficiale.html", documento=document)
        if not all(line.strip() in html.unescape(rendered)
                   for line in document["testo"].splitlines() if line.strip()):
            raise RuntimeError("Testo incompleto nella pagina HTML")
        return {"stato": "acquisito", "lettura_confermata": True,
                "caratteri": len(document["testo"]), "provenienza": document["provenienza"],
                "raw_sha256": document["raw_sha256"], "approvazione_automatica": False,
                "scritture_dati_studio": False, "coda_persistente_verificata": True,
                "html_consultabile_verificato": True,
                "html_sha256": sha256(rendered.encode()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(verify(json.loads(sys.argv[1]), json.loads(sys.argv[2]))))
