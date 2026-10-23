"""Trasporto verso il motore sullo stesso host; nessun modello nel processo web."""
import os
from urllib.parse import urlsplit


def search_openga(payload, config):
    import requests

    from pct.openga_search import search_openga as local_search
    endpoint = config.get("OPENGA_SEARCH_URL") or os.getenv("IUSENTRA_OPENGA_SEARCH_URL", "")
    if not endpoint:
        return local_search(payload, config)
    parsed = urlsplit(endpoint)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "openga-search", "host.docker.internal"}
        or parsed.port != 8092 or parsed.username or parsed.password or parsed.path not in {"", "/"}
        or parsed.query or parsed.fragment):
        raise ValueError("Servizio di ricerca locale non configurato correttamente.")
    # Non inoltrare cookie, token, tenant, percorsi o altri campi al servizio pubblico.
    data = {key: payload[key] for key in ("q", "dal", "al", "sede", "semantica") if key in payload}
    try:
        response = requests.post(endpoint.rstrip("/") + "/search", json=data, timeout=(3, 180), allow_redirects=False)
        if response.status_code == 400:
            raise ValueError("Controlla la domanda e l'intervallo degli anni.")
        response.raise_for_status()
        if len(response.content) > 2_000_000:
            raise RuntimeError("Risposta troppo grande")
        result = response.json()
        if not isinstance(result, dict) or result.get("evidence_scope") != "metadata_only":
            raise RuntimeError("Perimetro della risposta non valido")
        return result
    except requests.RequestException:
        return {"ok": False, "risultati": [], "evidence_scope": "metadata_only",
                "message": "Ricerca amministrativa non disponibile. Riprova più tardi."}
