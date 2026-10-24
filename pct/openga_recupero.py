"""Recupero pubblico limitato: URL candidati mai certificati prima del riscontro."""
from base64 import b64encode
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from types import SimpleNamespace
from urllib.parse import urlencode, urlsplit

import requests

from lex.sources.polite_fetcher import PoliteFetcher
from pct.openga_documento import DocumentoNonVerificato, leggi_documento
from pct.openga_organi import verifica_organo as riscontra_organo
from pct.openga_organi import verifica_tipo

_HOST = "mdp.giustizia-amministrativa.it"
_LOCK = Lock()
# Schema di indirizzamento, non prova di provenienza. Ogni risposta va riscontrata.
_SCHEMI = {
    "001": "tar_lt", "002": "cds", "003": "tar_rm", "004": "tar_aq",
    "005": "tar_pe", "006": "tar_bz", "007": "tar_pz", "008": "tar_cz",
    "009": "tar_rc", "010": "tar_na", "011": "tar_sa", "012": "tar_bo",
    "013": "tar_pr", "014": "tar_ts", "015": "tar_ge", "016": "tar_mi",
    "017": "tar_bs", "018": "tar_an", "019": "tar_cb", "020": "tar_to",
    "021": "tar_ba", "022": "tar_le", "023": "tar_ca", "024": "tar_pa",
    "025": "tar_ct", "026": "tar_fi", "027": "tar_tn", "028": "tar_pg",
    "029": "tar_ao", "030": "tar_ve", "032": "cgagiur",
}


def _get_limitato(url, *, headers):
    """Solo il rinvio al 404 dello stesso host; ogni altro redirect è negato."""
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname != _HOST or parts.username
            or parts.password or parts.port not in (None, 443)
            or parts.path not in {"/robots.txt", "/visualizza/"}):
        raise ValueError("Destinazione non consentita")
    with requests.Session() as session:
        session.trust_env = False
        started = monotonic()
        with session.get(url, headers=headers, timeout=(5, 5),
                         allow_redirects=False, stream=True) as response:
            if 300 <= response.status_code < 400:
                # Riscontrato sul sito: robots.txt rimanda al 404 dello stesso host.
                # Non trattare il redirect come autorizzazione: acquisire il vero 404.
                target = response.headers.get("Location", "")
                if target == "https://" + _HOST + "/visualizza/404.html":
                    return _get_robots_404(session, target, headers)
                raise ValueError("Redirect non seguito")
            if response.status_code >= 500:
                response.raise_for_status()
            if int(response.headers.get("Content-Length") or 0) > 2_000_000:
                raise ValueError("Risposta troppo grande")
            chunks, size = [], 0
            for chunk in response.iter_content(16384):
                if monotonic() - started > 20:
                    raise ValueError("Tempo massimo superato")
                size += len(chunk)
                if size > 2_000_000:
                    raise ValueError("Risposta troppo grande")
                chunks.append(chunk)
            content = b"".join(chunks)
            return SimpleNamespace(content=content, text=content.decode("utf-8", "replace"),
                                   status_code=response.status_code, headers=dict(response.headers), url=url)


def _get_robots_404(session, target, headers):
    started = monotonic()
    with session.get(target, headers=headers, timeout=(5, 5),
                     allow_redirects=False, stream=True) as response:
        if response.status_code not in {200, 404}:
            raise ValueError("robots non riscontrabile")
        chunks, size = [], 0
        for chunk in response.iter_content(8192):
            if monotonic() - started > 20:
                raise ValueError("Tempo massimo superato")
            size += len(chunk)
            if size > 65536:
                raise ValueError("robots troppo grande")
            chunks.append(chunk)
        # Conservare il vero status e il vero corpo, anche per il soft-404 HTML.
        # La policy del fetcher interpreta la risposta, senza inventare un 404.
        return SimpleNamespace(content=b"".join(chunks), status_code=response.status_code,
                               headers=dict(response.headers), url=target)


_FETCHER = PoliteFetcher(http_get=_get_limitato, timeout_seconds=20, max_bytes=2_000_000)


def recupera_testo(row, *, fetcher=None, verifica_organo=riscontra_organo):
    """Row interna risolta dal catalogo, mai URL o identità inviati dal browser.

    Il verificatore d'organo è obbligatorio finché il registro delle forme
    ufficiali non è riscontrato: nessuna identità viene autocertificata.
    """
    if not _LOCK.acquire(timeout=15):
        return {"stato": "in_attesa", "message": "Un recupero è già in corso."}
    try:
        schema = _SCHEMI.get(str(row.get("sede", "")))
        if not schema or verifica_organo is None:
            return {"stato": "intervento_necessario", "message": "Identità dell'organo non ancora riscontrabile."}
        anno = int(row["anno"])
        number = str(row["numero"])
        if len(number) == 9 and number.startswith(str(anno)):
            number = number[4:]
        numero = int(number)
        ricorso = str(row["ricorso"])
        fetcher = fetcher or _FETCHER
        suffixes = ("11", "01", "20") if schema in {"cds", "cgagiur"} else ("01", "20", "11")
        for suffix in suffixes:
            url = "https://" + _HOST + "/visualizza/?" + urlencode({
                "nodeRef": "", "schema": schema, "nrg": ricorso,
                "nomeFile": f"{anno}{numero:05d}_{suffix}.html", "subDir": "Provvedimenti"})
            fetched = fetcher.fetch(url)
            if fetched.status in {"robots_blocked", "network_error", "too_large"}:
                return {"stato": "intervento_necessario", "message": "La fonte non consente il recupero automatico in questo momento."}
            if fetched.http_status in {401, 403, 429}:
                return {"stato": "intervento_necessario",
                        "message": "La fonte limita l'accesso automatico: nessun tentativo su altre varianti."}
            if fetched.status != "ok" or fetched.http_status != 200:
                continue
            try:
                result = leggi_documento(fetched.content, url=url, schema=schema,
                    anno=anno, numero=numero, ricorso=ricorso,
                    acquisita_il=datetime.now(timezone.utc).strftime("%d/%m/%Y"))
                if not verifica_organo(fetched.content, row) or not verifica_tipo(fetched.content, row):
                    continue
            except DocumentoNonVerificato:
                continue
            result["originale_base64"] = b64encode(fetched.content).decode("ascii")
            return {"stato": "acquisito", "documento": result}
        return {"stato": "non_trovato", "message": "Nessun testo corrispondente riscontrato; il risultato resta uno spunto."}
    except (KeyError, TypeError, ValueError):
        return {"stato": "intervento_necessario", "message": "Estremi del catalogo incompleti o non validi."}
    finally:
        _LOCK.release()
