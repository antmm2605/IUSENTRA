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
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
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

PST_BASE_URL = "https://servizipst.giustizia.it"
PST_USER_AGENT = "IUSENTRA/2.0 (+https://app.iusentra.it)"
PST_DOWNLOAD_TIMEOUT_SECONDS = 25
PST_CERTIFICATI_CACHE_ENV = "PCT_CERTIFICATI_CIFRATURA_DIR"
PST_UFFICI_CATALOG_PATH = Path(__file__).resolve().parent / "data" / "uffici_pst_pubblici.json"
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
        "limite_dimensione_mb": 30,
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
        "limite_dimensione_mb": None,
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
        "limite_dimensione_mb": None,
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
    if Path("/data").exists():
        return Path("/data/pst/certificati_cifratura").resolve()
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
    return stato != "storico_o_non_operativo"


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


def scarica_certificato_cifratura_ufficio(
    codice_ufficio: str,
    *,
    cache_dir: str | Path | None = None,
    force_refresh: bool = False,
) -> CertificatoCifratura:
    codice = str(codice_ufficio or "").strip()
    if not codice:
        raise PSTCifraturaError("Codice ufficio mancante per il certificato PST.")
    target_dir = Path(cache_dir) if cache_dir else certificati_cifratura_cache_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    cert_path = target_dir / f"{_safe_code(codice)}.cer"
    meta_path = target_dir / f"{_safe_code(codice)}.json"

    if cert_path.exists() and not force_refresh:
        payload = cert_path.read_bytes()
        cert = _load_cert(payload)
        _validate_cert(cert, codice_ufficio=codice)
        source_url = ""
        if meta_path.exists():
            try:
                source_url = str(json.loads(meta_path.read_text(encoding="utf-8")).get("source_url") or "")
            except Exception:
                source_url = ""
        return _cert_info(
            codice_ufficio=codice,
            path=cert_path,
            payload=payload,
            cert=cert,
            source_url=source_url or "cache locale",
        )

    detail_url = _detail_url_for_office(codice)
    detail_html = _request_bytes(_quote_url(detail_url)).decode("utf-8", errors="replace")
    download_url = _download_url_from_detail(detail_html, detail_url=detail_url, codice_ufficio=codice)
    payload = _request_bytes(download_url)
    cert = _load_cert(payload)
    _validate_cert(cert, codice_ufficio=codice)
    cert_path.write_bytes(payload)
    info = _cert_info(
        codice_ufficio=codice,
        path=cert_path,
        payload=payload,
        cert=cert,
        source_url=download_url,
    )
    meta_path.write_text(json.dumps(asdict(info), ensure_ascii=False, indent=2), encoding="utf-8")
    return info


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
) -> dict[str, Any]:
    risultati: list[dict[str, Any]] = []
    ok = 0
    errori = 0
    saltati = 0
    saltati_senza_certificato = 0
    started = datetime.now(ROME_TZ)
    verificati = 0
    target_codes = {str(code).strip() for code in (codici_ufficio or []) if str(code).strip()}
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
        try:
            info = risolvi_certificato_cifratura_ufficio(
                codice,
                cache_dir=cache_dir,
                force_refresh=force_refresh,
            )
            risultati.append(
                {
                    "codice_ufficio": codice,
                    "descrizione": row.get("descrizione", ""),
                    "ok": True,
                    "certificato": asdict(info),
                }
            )
            ok += 1
        except Exception as exc:
            if _is_certificato_non_pubblicato(exc):
                risultati.append(
                    {
                        "codice_ufficio": codice,
                        "descrizione": row.get("descrizione", ""),
                        "ok": False,
                        "saltato": True,
                        "motivo": "certificato_cifratura_non_pubblicato",
                        "errore": str(exc),
                    }
                )
                saltati_senza_certificato += 1
                continue
            risultati.append(
                {
                    "codice_ufficio": codice,
                    "descrizione": row.get("descrizione", ""),
                    "ok": False,
                    "errore": str(exc),
                }
            )
            errori += 1
    finished = datetime.now(ROME_TZ)
    return {
        "ok": errori == 0,
        "generated_at": finished.isoformat(),
        "timezone": "Europe/Rome",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "cache_dir": str(Path(cache_dir) if cache_dir else certificati_cifratura_cache_dir()),
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
    )
    report["job"] = "pst_certificati_cifratura_weekly"
    report["source_of_truth"] = "catalogo_pubblico_pst"
    report["tenant_scope"] = "cache_tecnica_condivisa_non_operativa"
    report["json_authoritative"] = False
    report["report_path"] = str(
        scrivi_report_certificati_cifratura(
            report,
            report_path=report_path,
            cache_dir=cache_dir,
        )
    )
    return report
