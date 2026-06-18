"""Certificati pubblici PST e cifratura ministeriale della busta.

Il modulo scarica dal Portale Servizi Telematici il certificato pubblico di
cifratura dell'ufficio destinatario e lo usa per produrre Atto.enc in CMS
PKCS#7 con algoritmo AES256.
"""

from __future__ import annotations

import html
import json
import os
import re
import ssl
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.serialization import Encoding, pkcs7
from cryptography.x509.oid import NameOID

from .pst_catalog import PST_MAX_BUSTA_MB

PST_BASE_URL = "https://servizipst.giustizia.it"
PST_USER_AGENT = "IUSENTRA/2.0 (+https://app.iusentra.it)"
PST_DOWNLOAD_TIMEOUT_SECONDS = 25
PST_CERTIFICATI_CACHE_ENV = "PCT_CERTIFICATI_CIFRATURA_DIR"
PST_CERTIFICATI_WORKERS_ENV = "PCT_PST_CERTIFICATI_CIFRATURA_WORKERS"
PST_UFFICI_CATALOG_PATH = Path(__file__).resolve().parent / "data" / "uffici_pst_pubblici.json"
PST_UFFICI_MINISTERO_PATH = Path(__file__).resolve().parent / "data" / "uffici_ministero.json"
PST_UFFICI_MINISTERO_EXTRA_PATH = Path(__file__).resolve().parent / "data" / "uffici_ministero_extra.json"
PST_TLS_INTERMEDIATES: tuple[dict[str, str], ...] = (
    {
        "url": "http://tiTrust.crt.sectigo.com/TITrustTechnologiesOVCA.crt",
        "sha256": "1BFD8702D8F9BB340F353820330C0BBA7E522C63164C91F295414DAC797F0863",
    },
)
ROME_TZ = ZoneInfo("Europe/Rome")
CANALI_TELEMATICI_CIFRATURA_POLICY: dict[str, dict[str, Any]] = {
    "pct_civile_dm44": {
        "nome": "PCT civile / lavoro / SICID-SIECIC / SIGP via PEC",
        "usa_certificati_pst_cer": True,
        "trasporto": "Atto.msg cifrato in Atto.enc AES256 con certificato pubblico PST dell'ufficio",
        "formati": ["PDF", "PDF firmato PAdES", "PDF.p7m CAdES", "DatiAtto.xml", "IndiceDocumentiDepositati.PDF"],
        "firma": "Atto principale firmato digitalmente; allegati firmabili ove richiesto.",
        "limite_dimensione_mb": PST_MAX_BUSTA_MB,
        "controlli_software": [
            "risoluzione PEC ufficio dal catalogo PST",
            "recupero e validazione .cer pubblico dell'ufficio",
            "generazione Atto.msg con DatiAtto.xml, documenti e indice",
            "cifratura Atto.enc AES256",
            "blocco invio reale se Atto.enc non è generato o se il certificato non è valido",
        ],
        "fonte": "Specifiche tecniche art. 34 DM 44/2011, art. 17",
        "fonte_url": "https://pst.giustizia.it/PST/resources/cms/documents/m_dg.DOG07.07082024.0004292.ID_SPECIFICHETECNICHE_DM_44_2011_FINALE_31_.pdf",
    },
    "pdp_penale": {
        "nome": "PDP penale",
        "usa_certificati_pst_cer": False,
        "trasporto": "Deposito tramite servizio PDP, non invio PEC PCT con Atto.enc generato dallo studio",
        "formati": ["PDF A4 da testo", "PDF firmato digitalmente", "allegati PDF A4"],
        "firma": "Atto principale sottoscritto con firma digitale; allegati firmati nei casi previsti.",
        "limite_dimensione_mb": 500,
        "limite_singolo_file_mb": 50,
        "controlli_software": [
            "non usare .cer PST e non generare Atto.enc PCT",
            "verificare PDF A4 e provenienza da documento testuale dove richiesto",
            "verificare firma digitale dell'atto principale",
            "preparare elenco documenti per deposito su portale PDP",
            "bloccare l'invio se il canale richiesto è PCT ma il fascicolo è penale PDP",
        ],
        "fonte": "Specifiche tecniche Portale deposito atti penali, artt. 3, 5 e 7",
        "fonte_url": "https://pst.giustizia.it/PST/resources/cms/documents/Specifiche_Tecniche_PPT_11.07.2023_post_DM_2023_signed.pdf",
    },
    "pat_amministrativo": {
        "nome": "PAT amministrativo",
        "usa_certificati_pst_cer": False,
        "trasporto": "Deposito tramite Formweb come canale prioritario; PEC solo residuale nei casi tecnici previsti",
        "formati": ["modulo PAT aggiornato", "documenti secondo regole tecniche PAT", "firma digitale PAdES ove prevista"],
        "firma": "Firma digitale secondo regole PAT; usare moduli aggiornati pubblicati dal portale.",
        "limite_dimensione_mb": 300,
        "controlli_software": [
            "non usare .cer PST e non generare Atto.enc PCT",
            "selezionare Formweb come canale prioritario dal 1 febbraio 2026",
            "trattare PEC come canale residuale solo per comprovati problemi tecnici",
            "verificare modulo/atto e allegati secondo regole PAT",
            "controllare limite complessivo documenti Formweb quando applicabile",
        ],
        "fonte": "Giustizia amministrativa, regole tecnico-operative PAT e avviso 28 gennaio 2026",
        "fonte_url": "https://www.giustizia-amministrativa.it/-/152174-737",
    },
    "ptt_tributario": {
        "nome": "PTT tributario / SIGIT",
        "usa_certificati_pst_cer": False,
        "trasporto": "Deposito guidato sul PTT/SIGIT con specifiche MEF proprie",
        "formati": ["PDF/A-1a", "PDF/A-1b"],
        "firma": "Atti e documenti firmati digitalmente secondo le specifiche PTT/SIGIT.",
        "limite_singolo_file_mb": 50,
        "controlli_software": [
            "non usare .cer PST e non generare Atto.enc PCT",
            "verificare PDF/A-1a o PDF/A-1b per atti processuali",
            "verificare firma digitale prima del deposito",
            "preparare checklist PTT/SIGIT separata dal flusso PCT",
            "bloccare l'invio se il canale richiesto è PCT ma il fascicolo è tributario PTT",
        ],
        "fonte": "Specifiche tecniche PTT MEF 4 agosto 2015 e modifiche 21 aprile 2023",
        "fonte_url": "https://www.gazzettaufficiale.it/eli/id/2023/05/03/23A02531/SG",
    },
}


def canali_telematici_cifratura_policy() -> dict[str, dict[str, Any]]:
    return {key: dict(value) for key, value in CANALI_TELEMATICI_CIFRATURA_POLICY.items()}


def valida_canale_telematico_per_cifratura(canale: str) -> dict[str, Any]:
    """Restituisce il presidio corretto per il canale telematico richiesto."""

    codice = str(canale or "").strip().lower()
    profilo = CANALI_TELEMATICI_CIFRATURA_POLICY.get(codice)
    if profilo is None:
        return {
            "ok": False,
            "canale": codice,
            "errore": "Canale telematico non riconosciuto.",
            "azione": "Seleziona PCT, PDP, PAT o PTT prima di preparare il deposito.",
        }
    usa_cer = bool(profilo.get("usa_certificati_pst_cer"))
    return {
        "ok": True,
        "canale": codice,
        "nome": profilo["nome"],
        "usa_certificati_pst_cer": usa_cer,
        "procedura": "cifratura_pst_atto_enc" if usa_cer else "procedura_dedicata_non_pst",
        "trasporto": profilo["trasporto"],
        "controlli_software": list(profilo.get("controlli_software") or []),
        "fonte": profilo.get("fonte", ""),
        "fonte_url": profilo.get("fonte_url", ""),
    }


class PSTCifraturaError(RuntimeError):
    """Errore bloccante nella preparazione della busta ministeriale."""


@dataclass(frozen=True)
class CertificatoCifratura:
    codice_ufficio: str
    path: str
    subject: str
    issuer: str
    serial_number: str
    not_valid_after: str
    source_url: str
    sha256: str


def certificati_cifratura_cache_dir() -> Path:
    configured = os.getenv(PST_CERTIFICATI_CACHE_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    for candidate in (os.getenv("IUSENTRA_RUNTIME_DIR"), os.getenv("PCT_DATA_DIR")):
        if candidate:
            return (Path(candidate).expanduser().resolve() / "pst" / "certificati_cifratura")
    if os.name != "nt" and Path("/data").exists():
        return Path("/data/pst/certificati_cifratura").resolve()
    project_cache = Path(__file__).resolve().parents[1] / "data" / "pst" / "certificati_cifratura"
    if project_cache.exists():
        return project_cache.resolve()
    return (Path(tempfile.gettempdir()) / "iusentra" / "pst" / "certificati_cifratura").resolve()


def certificati_cifratura_report_path(cache_dir: str | Path | None = None) -> Path:
    target_dir = Path(cache_dir) if cache_dir else certificati_cifratura_cache_dir()
    return target_dir / "audit_certificati_cifratura_pst.json"


def _safe_code(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return cleaned or "ufficio"


def _sha256_bytes(payload: bytes) -> str:
    digest = hashes.Hash(hashes.SHA256())
    digest.update(payload)
    return digest.finalize().hex().upper()


def _load_cert(payload: bytes) -> x509.Certificate:
    try:
        return x509.load_der_x509_certificate(payload)
    except ValueError:
        try:
            return x509.load_pem_x509_certificate(payload)
        except ValueError as exc:
            raise PSTCifraturaError("Il certificato PST scaricato non è leggibile.") from exc


def _cert_subject(cert: x509.Certificate) -> str:
    return cert.subject.rfc4514_string()


def _cert_issuer(cert: x509.Certificate) -> str:
    return cert.issuer.rfc4514_string()


def _validate_cert(cert: x509.Certificate, *, codice_ufficio: str) -> None:
    now = datetime.now(UTC)
    not_after = cert.not_valid_after_utc
    not_before = cert.not_valid_before_utc
    if now < not_before:
        raise PSTCifraturaError(
            f"Il certificato di cifratura PST per l'ufficio {codice_ufficio} non è ancora valido."
        )
    if now >= not_after:
        raise PSTCifraturaError(
            f"Il certificato di cifratura PST per l'ufficio {codice_ufficio} è scaduto."
        )
    try:
        key_usage = cert.extensions.get_extension_for_class(x509.KeyUsage).value
    except x509.ExtensionNotFound:
        return
    if not (key_usage.key_encipherment or key_usage.data_encipherment):
        raise PSTCifraturaError(
            f"Il certificato PST dell'ufficio {codice_ufficio} non consente la cifratura della busta."
        )


def _cert_info(
    *,
    codice_ufficio: str,
    path: Path,
    payload: bytes,
    cert: x509.Certificate,
    source_url: str,
) -> CertificatoCifratura:
    return CertificatoCifratura(
        codice_ufficio=codice_ufficio,
        path=str(path),
        subject=_cert_subject(cert),
        issuer=_cert_issuer(cert),
        serial_number=f"{cert.serial_number:X}",
        not_valid_after=cert.not_valid_after_utc.isoformat(),
        source_url=source_url,
        sha256=_sha256_bytes(payload),
    )


def carica_certificato_cifratura(path: str | Path) -> x509.Certificate:
    payload = Path(path).read_bytes()
    cert = _load_cert(payload)
    _validate_cert(cert, codice_ufficio=Path(path).stem)
    return cert


def certificato_cifratura_in_cache(
    codice_ufficio: str,
    *,
    cache_dir: str | Path | None = None,
) -> CertificatoCifratura | None:
    """Restituisce il certificato gia' presente in cache senza interrogare il PST."""

    codice = _codice_certificato_download(str(codice_ufficio or "").strip())
    if not codice:
        return None
    target_dir = Path(cache_dir) if cache_dir else certificati_cifratura_cache_dir()
    cert_path = target_dir / f"{_safe_code(codice)}.cer"
    meta_path = target_dir / f"{_safe_code(codice)}.json"
    if not cert_path.exists():
        return None
    payload = cert_path.read_bytes()
    cert = _load_cert(payload)
    _validate_cert(cert, codice_ufficio=codice)
    source_url = "cache locale"
    if meta_path.exists():
        try:
            source_url = str(json.loads(meta_path.read_text(encoding="utf-8")).get("source_url") or source_url)
        except Exception:
            source_url = "cache locale"
    return _cert_info(
        codice_ufficio=codice,
        path=cert_path,
        payload=payload,
        cert=cert,
        source_url=source_url,
    )


def salva_certificato_cifratura_ufficio(
    codice_ufficio: str,
    payload: bytes,
    *,
    source_url: str = "",
    cache_dir: str | Path | None = None,
) -> CertificatoCifratura:
    """Valida e salva un certificato PST ottenuto da un canale ministeriale autenticato."""

    codice = str(codice_ufficio or "").strip()
    if not codice:
        raise PSTCifraturaError("Codice ufficio mancante per il certificato PST.")
    if not payload:
        raise PSTCifraturaError("Certificato PST vuoto.")
    target_dir = Path(cache_dir) if cache_dir else certificati_cifratura_cache_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    cert_path = target_dir / f"{_safe_code(codice)}.cer"
    meta_path = target_dir / f"{_safe_code(codice)}.json"
    cert = _load_cert(payload)
    _validate_cert(cert, codice_ufficio=codice)
    cert_path.write_bytes(payload)
    info = _cert_info(
        codice_ufficio=codice,
        path=cert_path,
        payload=payload,
        cert=cert,
        source_url=source_url or "CatalogoServizi.getCertificato",
    )
    meta_path.write_text(json.dumps(asdict(info), ensure_ascii=False, indent=2), encoding="utf-8")
    return info


def _request_bytes(url: str, *, timeout: int = PST_DOWNLOAD_TIMEOUT_SECONDS) -> bytes:
    request = Request(url, headers={"User-Agent": PST_USER_AGENT})
    try:
        with urlopen(request, timeout=timeout, context=_pst_tls_context()) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise PSTCifraturaError(f"Download PST non riuscito: {url}") from exc


def _pst_tls_context() -> ssl.SSLContext | None:
    try:
        import certifi  # type: ignore

        context = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        try:
            context = ssl.create_default_context()
        except Exception:
            return None
    _load_pinned_intermediates(context)
    return context


def _load_pinned_intermediates(context: ssl.SSLContext) -> None:
    for item in PST_TLS_INTERMEDIATES:
        try:
            payload = _cached_tls_intermediate(item["url"], item["sha256"])
            cert = _load_cert(payload)
            pem = cert.public_bytes(serialization.Encoding.PEM).decode("ascii")
            context.load_verify_locations(cadata=pem)
        except Exception:
            continue


def _cached_tls_intermediate(url: str, expected_sha256: str) -> bytes:
    cache_dir = certificati_cifratura_cache_dir() / "tls_intermediates"
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"{expected_sha256}.crt"
    if target.exists():
        payload = target.read_bytes()
        if _sha256_bytes(payload) == expected_sha256:
            return payload
    request = Request(url, headers={"User-Agent": PST_USER_AGENT})
    with urlopen(request, timeout=PST_DOWNLOAD_TIMEOUT_SECONDS) as response:
        payload = response.read()
    if _sha256_bytes(payload) != expected_sha256:
        raise PSTCifraturaError("Intermedio TLS PST non corrisponde all'impronta attesa.")
    target.write_bytes(payload)
    return payload


def _quote_url(url: str) -> str:
    parts = urlsplit(url)
    path = quote(parts.path, safe="/;:@")
    query = quote(parts.query, safe="=&%:/;,+@")
    return urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def _catalog_sections() -> Iterable[tuple[str, list[dict[str, Any]]]]:
    if not PST_UFFICI_CATALOG_PATH.exists():
        return []
    data = json.loads(PST_UFFICI_CATALOG_PATH.read_text(encoding="utf-8"))
    uffici = data.get("uffici", {}) if isinstance(data, dict) else {}
    sections: list[tuple[str, list[dict[str, Any]]]] = []
    for key, rows in uffici.items():
        if isinstance(rows, list):
            sections.append((str(key), [row for row in rows if isinstance(row, dict)]))
    return sections


def _iter_ministero_cert_records() -> Iterable[tuple[str, dict[str, Any]]]:
    for path in (PST_UFFICI_MINISTERO_PATH, PST_UFFICI_MINISTERO_EXTRA_PATH):
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows = raw.get("uffici", {}) if isinstance(raw, dict) else {}
        if isinstance(rows, dict):
            for internal_code, record in rows.items():
                if isinstance(record, dict):
                    yield str(internal_code), record
        elif isinstance(rows, list):
            for record in rows:
                if isinstance(record, dict):
                    yield "", record


@lru_cache(maxsize=1)
def _ministero_cert_catalog() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for internal_code, record in _iter_ministero_cert_records():
        codice_ministero = str(record.get("codice_ministero") or record.get("codice") or "").strip()
        if not codice_ministero:
            continue
        item = {
            "codice_download": codice_ministero,
            "codice_interno": internal_code,
            "descrizione": str(record.get("descrizione_ministero") or record.get("nome") or "").strip(),
            "tipo_ministero": str(record.get("tipo_ministero") or "").strip(),
            "tipo_descrizione": str(record.get("tipo_ministero_descrizione") or "").strip(),
            "comune": str(record.get("comune_ministero") or "").strip(),
            "nome_certificato_cifra": str(record.get("nome_certificato_cifra") or "").strip(),
            "certificato_mimetype": str(record.get("certificato_mimetype") or "application/octet-stream").strip()
            or "application/octet-stream",
            "servizi_ministero": list(record.get("servizi_ministero") or []),
        }
        catalog[codice_ministero] = item
        if internal_code:
            catalog[internal_code] = item
    return catalog


def _cert_catalog_record(codice_ufficio: str) -> dict[str, Any]:
    return dict(_ministero_cert_catalog().get(str(codice_ufficio or "").strip()) or {})


def _codice_certificato_download(codice_ufficio: str) -> str:
    codice = str(codice_ufficio or "").strip()
    record = _cert_catalog_record(codice)
    return str(record.get("codice_download") or codice).strip()


def iter_uffici_pst_catalogo() -> Iterable[dict[str, Any]]:
    for sezione, rows in _catalog_sections():
        for row in rows:
            item = dict(row)
            item.setdefault("sezione_catalogo", sezione)
            yield item


def _ufficio_richiede_certificato_pct(row: dict[str, Any]) -> bool:
    """Il precarico .cer riguarda solo canali PCT/SIGP con Atto.enc."""

    if str(row.get("sezione_catalogo") or "").strip().lower() != "civili":
        return False
    if row.get("deposito_prudenziale") is False:
        return False
    stato = str(row.get("stato_prudenziale") or "").strip().lower()
    if stato == "storico_o_non_operativo":
        return False
    codice = str(row.get("codice_ufficio") or "").strip()
    record = _cert_catalog_record(codice)
    if record and record.get("tipo_ministero"):
        return _ministero_record_richiede_certificato(record)
    descrizione = str(row.get("descrizione") or "").strip().upper()
    if any(marker in descrizione for marker in ("EX GIUD", "NON ATTIVO", "EX SD", "SEZIONE DISTACCATA")):
        return False
    if any(marker in descrizione for marker in ("UNEP", "PROCURA", "SORVEGLIANZA", "CORTE D'ASSISE")):
        return False
    return any(
        marker in descrizione
        for marker in (
            "GIUDICE DI PACE",
            "TRIBUNALE ORDINARIO",
            "TRIBUNALE DI ",
            "CORTE D'APPELLO",
            "CASSAZIONE",
        )
    )


def _ministero_record_richiede_certificato(record: dict[str, Any]) -> bool:
    tipo = str(record.get("tipo_ministero") or record.get("tipo") or "").strip().upper()
    tipo_interno = str(record.get("tipo") or "").strip().upper()
    descrizione = str(record.get("descrizione_ministero") or record.get("descrizione") or record.get("nome") or "").upper()
    if any(marker in descrizione for marker in ("EX GIUD", "NON ATTIVO", "EX SD", "SEZIONE DISTACCATA")):
        return False
    if tipo not in {"CA", "OR", "SC", "TM", "GP", "CC"} and tipo_interno not in {
        "TRIBUNALE",
        "CORTE_APPELLO",
        "CORTE_CASSAZIONE",
        "TM",
        "GDP",
    }:
        return False
    servizi = {
        str(servizio or "").strip().upper()
        for servizio in (record.get("servizi_ministero") or [])
        if str(servizio or "").strip()
    }
    return any(servizio.startswith("JPW_") for servizio in servizi)


def _iter_ministero_cert_target_rows() -> Iterable[dict[str, Any]]:
    """Righe certificate da ListaUfficiGiudiziari.xml usate dal job .cer."""

    for internal_code, record in _iter_ministero_cert_records():
        if not _ministero_record_richiede_certificato(record):
            continue
        codice = str(record.get("codice_ministero") or record.get("codice") or "").strip()
        if not codice:
            continue
        yield {
            "codice_ufficio": codice,
            "codice_interno": str(internal_code or "").strip(),
            "descrizione": str(record.get("descrizione_ministero") or record.get("nome") or "").strip(),
            "sezione_catalogo": "civili",
            "stato_prudenziale": "pst_visibile",
            "deposito_prudenziale": True,
            "fonte_catalogo": "ListaUfficiGiudiziari.xml",
        }


def _iter_certificati_cifratura_target_rows() -> Iterable[dict[str, Any]]:
    seen: set[str] = set()
    for row in iter_uffici_pst_catalogo():
        codice = str(row.get("codice_ufficio") or "").strip()
        if not codice or not _ufficio_richiede_certificato_pct(row):
            continue
        if codice in seen:
            continue
        seen.add(codice)
        yield row
    for row in _iter_ministero_cert_target_rows():
        codice = str(row.get("codice_ufficio") or "").strip()
        if not codice or codice in seen:
            continue
        seen.add(codice)
        yield row


def trova_ufficio_pst(codice_ufficio: str) -> dict[str, Any] | None:
    codice = str(codice_ufficio or "").strip()
    if not codice:
        return None
    for row in iter_uffici_pst_catalogo():
        if str(row.get("codice_ufficio") or "").strip() == codice:
            return row
    return None


def _detail_url_for_office(codice_ufficio: str) -> str:
    row = trova_ufficio_pst(codice_ufficio)
    href = str((row or {}).get("href") or "").strip()
    if href:
        return urljoin(PST_BASE_URL, href)
    return (
        f"{PST_BASE_URL}/PST/it/pst_2_4.wp"
        "?actionPath=/ExtStr2/do/ufficiepda/uffici/ricerca/viewUfficio.action"
        f"&currentFrame=8&codiceUfficio={quote(str(codice_ufficio))}"
        "&distretto=&localita=&tipoUfficio=&ufficioSelect=giudiziari"
    )


def _download_url_from_filename(
    codice_ufficio: str,
    filename: str,
    *,
    mimetype: str = "application/octet-stream",
) -> str:
    return (
        f"{PST_BASE_URL}/PST/do/ufficiepda/uffici/ricerca/download.action"
        f"?codiceUfficio={quote(str(codice_ufficio))}"
        f"&fileName={quote(str(filename))}"
        f"&mimetype={quote(str(mimetype or 'application/octet-stream'), safe='/')}"
    )


def _candidate_cert_filenames(codice_ufficio: str) -> list[str]:
    codice = str(codice_ufficio or "").strip()
    record = _cert_catalog_record(codice)
    download_code = str(record.get("codice_download") or codice).strip()
    labels = [
        str(record.get("nome_certificato_cifra") or "").strip(),
        str(record.get("descrizione") or "").strip(),
    ]
    tipo = str(record.get("tipo_ministero") or "").strip().upper()
    comune = str(record.get("comune") or "").strip()
    if tipo == "GP" and comune:
        labels.extend(
            [
                f"Giudice di Pace - {comune}",
                f"Ufficio del Giudice di Pace - {comune}",
            ]
        )
    if tipo == "OR" and comune:
        labels.append(f"Tribunale Ordinario - {comune}")
    out: list[str] = []
    for label in labels:
        if not label:
            continue
        filename = label if label.lower().endswith(".cer") else f"{download_code}_{label}.cer"
        if filename not in out:
            out.append(filename)
    return out


def _scarica_certificato_da_nome_catalogo(
    codice_ufficio: str,
    *,
    cache_dir: str | Path,
) -> CertificatoCifratura | None:
    codice = _codice_certificato_download(codice_ufficio)
    record = _cert_catalog_record(codice_ufficio) or _cert_catalog_record(codice)
    mimetype = str(record.get("certificato_mimetype") or "application/octet-stream").strip()
    for filename in _candidate_cert_filenames(codice):
        download_url = _download_url_from_filename(codice, filename, mimetype=mimetype)
        try:
            payload = _request_bytes(download_url)
            return salva_certificato_cifratura_ufficio(
                codice,
                payload,
                source_url=download_url,
                cache_dir=cache_dir,
            )
        except Exception as exc:
            _ = exc
            continue
    return None


def _download_url_from_detail(detail_html: str, *, detail_url: str, codice_ufficio: str) -> str:
    body = html.unescape(detail_html)
    patterns = [
        r'href=["\']([^"\']*download\.action[^"\']*?fileName=[^"\']*?\.cer[^"\']*)["\']',
        r'(\/PST\/do\/ufficiepda\/uffici\/ricerca\/download\.action[^"\'<>\s]*?fileName=[^"\'<>]*?\.cer[^"\'<>]*)',
    ]
    for pattern in patterns:
        match = re.search(pattern, body, flags=re.IGNORECASE)
        if match:
            return _quote_url(urljoin(detail_url, match.group(1)))
    raise PSTCifraturaError(
        f"Certificato di cifratura PST non trovato per l'ufficio {codice_ufficio}."
    )


def _is_certificato_non_pubblicato(exc: Exception) -> bool:
    return "Certificato di cifratura PST non trovato" in str(exc)


def _cache_cer_count(cache_dir: str | Path | None = None) -> int:
    target_dir = Path(cache_dir) if cache_dir else certificati_cifratura_cache_dir()
    try:
        return sum(1 for path in target_dir.glob("*.cer") if path.is_file())
    except OSError:
        return 0


def _eligible_pct_cert_codes() -> set[str]:
    return {
        str(row.get("codice_ufficio") or "").strip()
        for row in _iter_certificati_cifratura_target_rows()
        if str(row.get("codice_ufficio") or "").strip()
    }


def _precarico_workers(max_workers: int | None = None) -> int:
    if max_workers is not None:
        return max(1, min(int(max_workers), 12))
    raw = os.getenv(PST_CERTIFICATI_WORKERS_ENV, "").strip()
    if raw:
        try:
            return max(1, min(int(raw), 12))
        except ValueError:
            return 6
    return 6


def report_path_certificati_mirato(
    codici_ufficio: Iterable[str],
    *,
    cache_dir: str | Path | None = None,
) -> Path:
    """Report separato per controlli puntuali: non sovrascrive l'audit completo."""

    target_dir = Path(cache_dir) if cache_dir else certificati_cifratura_cache_dir()
    codes = sorted({_safe_code(code) for code in codici_ufficio if str(code or "").strip()})
    suffix = "_".join(codes[:4]) or "ufficio"
    if len(codes) > 4:
        suffix = f"{suffix}_piu_{len(codes) - 4}"
    return target_dir / f"audit_certificati_cifratura_pst_mirato_{suffix}.json"


def scarica_certificato_cifratura_ufficio(
    codice_ufficio: str,
    *,
    cache_dir: str | Path | None = None,
    force_refresh: bool = False,
) -> CertificatoCifratura:
    codice = _codice_certificato_download(str(codice_ufficio or "").strip())
    if not codice:
        raise PSTCifraturaError("Codice ufficio mancante per il certificato PST.")
    target_dir = Path(cache_dir) if cache_dir else certificati_cifratura_cache_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    cert_path = target_dir / f"{_safe_code(codice)}.cer"
    meta_path = target_dir / f"{_safe_code(codice)}.json"

    if cert_path.exists() and not force_refresh:
        cached = certificato_cifratura_in_cache(codice, cache_dir=target_dir)
        if cached:
            return cached

    direct = _scarica_certificato_da_nome_catalogo(codice, cache_dir=target_dir)
    if direct:
        return direct

    detail_url = _detail_url_for_office(codice)
    detail_html = _request_bytes(_quote_url(detail_url)).decode("utf-8", errors="replace")
    download_url = _download_url_from_detail(detail_html, detail_url=detail_url, codice_ufficio=codice)
    payload = _request_bytes(download_url)
    return salva_certificato_cifratura_ufficio(
        codice,
        payload,
        source_url=download_url,
        cache_dir=target_dir,
    )


def risolvi_certificato_cifratura_ufficio(
    codice_ufficio: str,
    *,
    cache_dir: str | Path | None = None,
    force_refresh: bool = False,
) -> CertificatoCifratura:
    return scarica_certificato_cifratura_ufficio(
        codice_ufficio,
        cache_dir=cache_dir,
        force_refresh=force_refresh,
    )


def cifra_atto_msg_aes256(atto_msg: bytes, certificato: x509.Certificate) -> bytes:
    try:
        return (
            pkcs7.PKCS7EnvelopeBuilder()
            .set_data(atto_msg)
            .add_recipient(certificato)
            .set_content_encryption_algorithm(algorithms.AES256)
            .encrypt(Encoding.DER, [pkcs7.PKCS7Options.Binary])
        )
    except Exception as exc:
        raise PSTCifraturaError("Cifratura Atto.enc AES256 non completata.") from exc


def crea_certificato_cifratura_test(target: str | Path) -> CertificatoCifratura:
    """Crea un certificato pubblico temporaneo per test automatici offline."""
    target_path = Path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IT"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "IUSENTRA Test"),
            x509.NameAttribute(NameOID.COMMON_NAME, "ufficio-test-cifra.invalid"),
        ]
    )
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=True,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    payload = cert.public_bytes(serialization.Encoding.DER)
    target_path.write_bytes(payload)
    return _cert_info(
        codice_ufficio="TEST",
        path=target_path,
        payload=payload,
        cert=cert,
        source_url="certificato test offline",
    )


def precarica_certificati_cifratura(
    *,
    cache_dir: str | Path | None = None,
    limit: int | None = None,
    force_refresh: bool = False,
    codici_ufficio: Iterable[str] | None = None,
    max_workers: int | None = None,
) -> dict[str, Any]:
    risultati: list[dict[str, Any]] = []
    ok = 0
    errori = 0
    saltati = 0
    saltati_senza_certificato = 0
    started = datetime.now(ROME_TZ)
    verificati = 0
    target_codes = {str(code).strip() for code in (codici_ufficio or []) if str(code).strip()}
    eligible_codes = _eligible_pct_cert_codes()
    rows_to_check: list[dict[str, Any]] = []
    seen_to_check: set[str] = set()
    for row in iter_uffici_pst_catalogo():
        codice = str(row.get("codice_ufficio") or "").strip()
        if not codice:
            continue
        if target_codes and codice not in target_codes:
            continue
        if not target_codes and not _ufficio_richiede_certificato_pct(row):
            saltati += 1
            continue
        verificati += 1
        if limit is not None and verificati > limit:
            break
        rows_to_check.append(dict(row))
        seen_to_check.add(codice)
    if limit is None or verificati <= limit:
        for row in _iter_ministero_cert_target_rows():
            codice = str(row.get("codice_ufficio") or "").strip()
            codice_interno = str(row.get("codice_interno") or "").strip()
            if not codice or codice in seen_to_check:
                continue
            if target_codes and codice not in target_codes and codice_interno not in target_codes:
                continue
            if not target_codes:
                verificati += 1
            if limit is not None and verificati > limit:
                break
            rows_to_check.append(dict(row))
            seen_to_check.add(codice)

    def _controlla(row: dict[str, Any]) -> dict[str, Any]:
        codice = str(row.get("codice_ufficio") or "").strip()
        try:
            info = risolvi_certificato_cifratura_ufficio(
                codice,
                cache_dir=cache_dir,
                force_refresh=force_refresh,
            )
            return {
                "codice_ufficio": codice,
                "descrizione": row.get("descrizione", ""),
                "ok": True,
                "certificato": asdict(info),
            }
        except Exception as exc:
            if _is_certificato_non_pubblicato(exc):
                return {
                    "codice_ufficio": codice,
                    "descrizione": row.get("descrizione", ""),
                    "ok": False,
                    "saltato": True,
                    "motivo": "certificato_cifratura_non_pubblicato",
                    "errore": str(exc),
                }
            return {
                "codice_ufficio": codice,
                "descrizione": row.get("descrizione", ""),
                "ok": False,
                "errore": str(exc),
            }

    workers = min(_precarico_workers(max_workers), max(1, len(rows_to_check)))
    indexed_results: list[tuple[int, dict[str, Any]]] = []
    if workers <= 1 or len(rows_to_check) <= 1:
        indexed_results = [(index, _controlla(row)) for index, row in enumerate(rows_to_check)]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_index = {
                pool.submit(_controlla, row): index
                for index, row in enumerate(rows_to_check)
            }
            for future in as_completed(future_to_index):
                indexed_results.append((future_to_index[future], future.result()))

    for _, result in sorted(indexed_results, key=lambda item: item[0]):
        risultati.append(result)
        if result.get("ok"):
            ok += 1
        elif result.get("motivo") == "certificato_cifratura_non_pubblicato":
            saltati_senza_certificato += 1
        else:
            errori += 1
    finished = datetime.now(ROME_TZ)
    scope_mode = "mirato" if target_codes else "completo"
    return {
        "ok": errori == 0,
        "generated_at": finished.isoformat(),
        "timezone": "Europe/Rome",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "cache_dir": str(Path(cache_dir) if cache_dir else certificati_cifratura_cache_dir()),
        "scope_mode": scope_mode,
        "target_codes": sorted(target_codes),
        "catalogo_pct_operativi": len(eligible_codes),
        "cache_cer_presenti": _cache_cer_count(cache_dir),
        "workers": workers,
        "channel_scope": canali_telematici_cifratura_policy(),
        "totale": len(risultati),
        "saltati_non_pct_o_non_operativi": saltati,
        "saltati_senza_certificato_pubblicato": saltati_senza_certificato,
        "perimetro": (
            "solo uffici dei canali PCT/SIGP che richiedono certificato .cer PST "
            "per Atto.enc; PDP, PAT e PTT usano regole e trasporti separati"
        ),
        "scaricati_o_validi": ok,
        "errori": errori,
        "risultati": risultati,
    }


def scrivi_report_certificati_cifratura(
    report: dict[str, Any],
    *,
    report_path: str | Path | None = None,
    cache_dir: str | Path | None = None,
) -> Path:
    target = Path(report_path) if report_path else certificati_cifratura_report_path(cache_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def esegui_controllo_settimanale_certificati_cifratura(
    *,
    cache_dir: str | Path | None = None,
    report_path: str | Path | None = None,
    force_refresh: bool = True,
    limit: int | None = None,
    codici_ufficio: Iterable[str] | None = None,
    max_workers: int | None = None,
) -> dict[str, Any]:
    """Controlla e aggiorna i certificati PST ufficiali per tutti gli uffici in catalogo.

    Il controllo è deliberatamente fuori dai dati di tenant: i `.cer` sono
    cache tecnica ministeriale condivisa, mentre fascicoli/clienti/documenti
    restano governati da SQLite/PostgreSQL tenant-aware.
    """

    report = precarica_certificati_cifratura(
        cache_dir=cache_dir,
        limit=limit,
        force_refresh=force_refresh,
        codici_ufficio=codici_ufficio,
        max_workers=max_workers,
    )
    report["job"] = "pst_certificati_cifratura_weekly"
    report["source_of_truth"] = "catalogo_pubblico_pst"
    report["tenant_scope"] = "cache_tecnica_condivisa_non_operativa"
    report["json_authoritative"] = False
    effective_report_path = report_path
    target_codes = [str(code).strip() for code in (codici_ufficio or []) if str(code).strip()]
    if effective_report_path is None and target_codes:
        effective_report_path = report_path_certificati_mirato(
            target_codes,
            cache_dir=cache_dir,
        )
        report["report_principale_preservato"] = str(certificati_cifratura_report_path(cache_dir))
    report["report_path"] = str(
        scrivi_report_certificati_cifratura(
            report,
            report_path=effective_report_path,
            cache_dir=cache_dir,
        )
    )
    return report
