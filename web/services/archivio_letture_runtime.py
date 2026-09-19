"""La catena di alimentazione dell'archivio dentro l'applicazione.

Qui i due motori incontrano i dati dello studio: i testi dei documenti (nativo
dal PDF, OCR dalla cache dell'indice di ricerca, indice documentale), i
messaggi del presidio PEC con i loro allegati, le date che agenda,
scadenziario, PEC e portale già conoscono (per il collaudo). La lettura è
incrementale per costruzione: si chiede al registro delle letture quali
oggetti i motori non hanno ancora letto e si leggono solo quelli; a lettura
fatta l'oggetto è segnato e non si rilegge finché il suo contenuto non
cambia. Nessuna lettura avviene nella richiesta dell'avvocato: la lettura
automatica gira nello scheduler, in un thread di sfondo al caricamento di un
documento o al collegamento di una PEC, e nel worker OCR a testo pronto.
"""

from __future__ import annotations

import logging
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Iterable

from flask import current_app, g, has_app_context

from pct.archivio_letture import VERSIONE_MOTORE_DOCUMENTI, VERSIONE_MOTORE_PEC, fatti_da_allegato, fatti_da_messaggio, leggi_testo, riassunto_archivio
from pct.archivio_letture.ciclo import StatoCiclo, stato_ciclo
from pct.archivio_letture.collaudo import Contesto, contesto_da_fascicolo
from pct.registro_letture import Fatto, Oggetto, RegistroLetture
from web.services.lettura_cache import invalida_lettura
from web.services.registro_letture_runtime import (
    _righe_pec_collegate,
    aggiorna_inventario,
    percorso_registro,
    registro_corrente,
    registro_per_percorsi,
    tenant_corrente,
)

logger = logging.getLogger(__name__)
LETTORE_DOCUMENTI = "motore_documenti"
LETTORE_PEC = "motore_pec"
BYTE_MASSIMI_PDF = 8_000_000
BYTE_MASSIMI_EMAIL = 128 * 1024 * 1024
VERSIONE_ESTRAZIONE_FORMATI = "2026.09.17.v4"
_LOCK = threading.Lock()
_IN_CORSO: set[str] = set()
_SCHEDULER_IDLE_MARKER = "archivio_letture_scheduler_idle.json"
_SCHEDULER_IDLE_ORE_DEFAULT = 24
ROME = ZoneInfo("Europe/Rome")


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _adesso_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(valore: datetime) -> str:
    return valore.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _leggi_iso_utc(valore: Any) -> datetime | None:
    testo = str(valore or "").strip()
    if not testo:
        return None
    try:
        letto = datetime.fromisoformat(testo.replace("Z", "+00:00"))
    except ValueError:
        return None
    return letto if letto.tzinfo else letto.replace(tzinfo=timezone.utc)


def _scheduler_idle_ore(app: Any | None = None) -> int:
    raw = ""
    try:
        raw = str((getattr(app, "config", {}) or {}).get("IUSENTRA_ARCHIVIO_LETTURE_IDLE_ORE") or "")
    except Exception:
        raw = ""
    raw = raw or os.getenv("IUSENTRA_ARCHIVIO_LETTURE_IDLE_ORE", "")
    try:
        ore = int(str(raw or "").strip())
    except (TypeError, ValueError):
        ore = _SCHEDULER_IDLE_ORE_DEFAULT
    return max(0, ore)


def _scheduler_idle_path(paths: dict[str, Any] | None = None) -> Path:
    registro_path = Path(percorso_registro(paths or {})).resolve()
    return registro_path.parent / _SCHEDULER_IDLE_MARKER


def _scheduler_idle_attivo(app: Any, paths: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Vero quando il giro schedulato può saltare la scansione pesante.

    Il marker è volutamente tenant-aware e vive accanto al registro delle
    letture: non è fonte di dati processuali, è solo il semaforo che evita di
    riesaminare ogni dieci minuti fascicoli già confermati.
    """
    if _scheduler_idle_ore(app) <= 0:
        return None
    percorso = _scheduler_idle_path(paths)
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except Exception:
        return None
    if dati.get("versione_documenti") != VERSIONE_MOTORE_DOCUMENTI or dati.get("versione_pec") != VERSIONE_MOTORE_PEC:
        return None
    fino_a = _leggi_iso_utc(dati.get("fino_a"))
    if fino_a is None or fino_a <= _adesso_utc():
        return None
    return dati


def _scrivi_scheduler_idle(app: Any, paths: dict[str, Any] | None, report: dict[str, Any]) -> None:
    percorso = _scheduler_idle_path(paths)
    deve_restare_attivo = (
        int(report.get("documenti_letti") or 0) == 0
        and int(report.get("pec_lette") or 0) == 0
        and int(report.get("senza_testo") or 0) == 0
        and int(report.get("promossi") or 0) == 0
        and int(report.get("restano") or 0) == 0
    )
    if not deve_restare_attivo or _scheduler_idle_ore(app) <= 0:
        try:
            percorso.unlink(missing_ok=True)
        except Exception:
            logger.debug("Marker inattività letture non rimosso: %s", percorso, exc_info=True)
        return
    adesso = _adesso_utc()
    dati = {
        "stato": "fermo",
        "ultimo_giro": _iso_utc(adesso),
        "fino_a": _iso_utc(adesso + timedelta(hours=_scheduler_idle_ore(app))),
        "versione_documenti": VERSIONE_MOTORE_DOCUMENTI,
        "versione_pec": VERSIONE_MOTORE_PEC,
        "fascicoli": int(report.get("fascicoli") or 0),
        "esaminati_ultimo_giro": int(report.get("esaminati") or 0),
    }
    try:
        percorso.parent.mkdir(parents=True, exist_ok=True)
        temporaneo = percorso.with_suffix(percorso.suffix + ".tmp")
        temporaneo.write_text(json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8")
        temporaneo.replace(percorso)
    except Exception:
        logger.debug("Marker inattività letture non scritto: %s", percorso, exc_info=True)


def riattiva_scheduler_letture(paths: dict[str, Any] | None = None) -> None:
    """Rimuove il marker di inattività quando un evento reale cambia il fascicolo."""
    try:
        _scheduler_idle_path(paths).unlink(missing_ok=True)
    except Exception:
        logger.debug("Marker inattività letture non riattivato", exc_info=True)


def _report_scheduler_saltato(marker: dict[str, Any]) -> dict[str, Any]:
    fascicoli = int(marker.get("fascicoli") or 0)
    return {
        "fascicoli": fascicoli,
        "esaminati": 0,
        "documenti_letti": 0,
        "pec_lette": 0,
        "fatti": 0,
        "verificati": 0,
        "promossi": 0,
        "senza_testo": 0,
        "restano": 0,
        "saltati": fascicoli,
        "fermo": True,
        "prossimo_controllo": str(marker.get("fino_a") or ""),
    }


# ---- i testi di un documento --------------------------------------------------

def _formato_documento(documento: Any) -> str:
    # Il titolo della PEC non è il nome fisico del file acquisito.
    for campo in ("percorso", "nome_originale", "nome"):
        estensione = Path(str(getattr(documento, campo, "") or "")).suffix.lower()
        if estensione in {".eml", ".pdf", ".zip", ".p7m", ".xml", ".docx", ".doc", ".txt", ".rtf"}:
            return estensione
    return ""


def _bytes_documento(fascicolo_id: str, documento: Any) -> bytes:
    try:
        from pct.document_crypto import decrypt_doc
        from web.helpers import get_fascicoli

        # Non riusare un manager messo in cache in una lettura precedente della
        # stessa richiesta: un documento appena caricato o sostituito deve essere
        # visibile subito e letto solo lui.
        manager = get_fascicoli()
        percorso = manager.percorso_documento_lettura(fascicolo_id, str(documento.id))
        limit = BYTE_MASSIMI_EMAIL
        if not percorso.exists() or percorso.stat().st_size > limit:
            return b""
        return decrypt_doc(percorso.read_bytes())
    except Exception:
        return b""


def _testo_nativo(fascicolo_id: str, documento: Any) -> str:
    formato = _formato_documento(documento)
    if formato == ".eml" or str(getattr(documento, "mime_type", "")) == "message/rfc822":
        from email import policy
        from email.parser import BytesParser
        data = _bytes_documento(fascicolo_id, documento)
        if not data:
            return ""
        message = BytesParser(policy=policy.default).parsebytes(data)
        if not message.get("From") or not message.get("Subject"):
            return ""
        body = message.get_body(preferencelist=("plain", "html"))
        text = str(body.get_content()) if body else ""
        if body is not None and body.get_content_type() == "text/html":
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text, "html.parser")
            for elemento in soup(["script", "style"]):
                elemento.decompose()
            text = soup.get_text(" ", strip=True)
        pec = "posta certificata" in str(message.get("Subject", "")).lower() or bool(message.get("X-Trasporto"))
        return f"Tipo contenuto: messaggio {'PEC' if pec else 'email'}\nMittente: {message.get('From', '')}\nOggetto: {message.get('Subject', '')}\n\n{text}"
    if formato != ".pdf":
        return ""
    dati = _bytes_documento(fascicolo_id, documento)
    if not dati:
        return ""
    try:
        import io

        import pdfplumber  # type: ignore

        from legal_ocr.motore.testo import _testo_nativo_affidabile

        pagine: list[str] = []
        with pdfplumber.open(io.BytesIO(dati)) as pdf:
            for pagina in pdf.pages:
                pagine.append(pagina.extract_text() or "")
        testo = "\n\n".join(parte for parte in pagine if parte.strip()).strip()
        return testo if _testo_nativo_affidabile(testo) else ""
    except Exception:
        return ""


def _testo_ocr(documento: Any) -> str:
    try:
        from web.helpers import get_indice

        return str(get_indice().get_ocr_cache(_testo(getattr(documento, "hash_sha256", ""))) or "")
    except Exception:
        return ""


def testi_indice_archivio(fascicolo: Any) -> dict[str, str]:
    """Testo SQL corrente, abbinato all'impronta del contenuto: nessun nome o JSON storico."""
    from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id
    from web.services.registro_letture_runtime import impronte_contenuto
    fid = str(fascicolo.id)
    cache = getattr(g, "_archivio_testi_sql", {}) if has_app_context() else {}
    if fid in cache:
        return cache[fid]
    repository = build_document_ai_service().repository
    tenant = document_ai_tenant_id()
    records = sorted(repository.list_documents(tenant, fid), key=lambda r: str(r.updated_at or ""), reverse=True)
    by_sha = {}
    for record in records:
        if str(record.status) == "ready" and record.sha256:
            by_sha.setdefault(record.sha256, record)
    hashes = impronte_contenuto(fid)
    text_by_sha, result = {}, {}
    for doc in fascicolo.documenti:
        sha = str(getattr(doc, "hash_contenuto_sha256", "") or "") or (hashes.nota(doc) if hashes else "") or str(getattr(doc, "hash_sha256", "") or "")
        record = by_sha.get(sha)
        if record is None:
            continue
        if sha not in text_by_sha:
            extracted = repository.get_extracted_text(tenant, fid, record.id, record.current_version_id)
            text = str(getattr(extracted, "text", "") or "")
            text_by_sha[sha] = "" if text.lstrip().startswith("PCTENC") else text
        if text_by_sha[sha].strip():
            result[str(doc.id)] = text_by_sha[sha]
    if has_app_context():
        cache[fid] = result
        g._archivio_testi_sql = cache
    return result


def _testo_indice(fascicolo: Any, documento: Any) -> str:
    return testi_indice_archivio(fascicolo).get(str(documento.id), "")


def testi_documento(fascicolo: Any, documento: Any) -> list[tuple[str, str]]:
    """Le letture disponibili del documento, dalla più affidabile: (origine, testo)."""
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    letture: list[tuple[str, str]] = []
    nativo = _testo_nativo(fascicolo_id, documento)
    if nativo:
        letture.append(("nativo", nativo))
    ocr = _testo_ocr(documento)
    if ocr.strip():
        letture.append(("ocr", ocr))
    indice = _testo_indice(fascicolo, documento)
    if indice.lstrip().startswith("PCTENC"):
        indice = ""  # encrypted storage is never readable evidence
    if indice.strip() and indice.strip() != ocr.strip():
        letture.append(("indice", indice))
    return letture


# ---- le date già note (per il collaudo) ------------------------------------------

def date_note_fascicolo(fascicolo: Any, *, messaggi_pec: Iterable[dict[str, Any]] | None = None) -> dict[str, list[str]]:
    note: dict[str, list[str]] = {}
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))

    def aggiungi(valore: Any, fonte: str) -> None:
        giorno = _testo(valore)[:10]
        if len(giorno) == 10 and giorno[4] == "-":
            elenco = note.setdefault(giorno, [])
            if fonte not in elenco:
                elenco.append(fonte)

    try:
        from web.helpers import get_scadenziario

        for scadenza in get_scadenziario().tutte(id_fascicolo=fascicolo_id, solo_aperte=False):
            aggiungi(getattr(scadenza, "data_scadenza", ""), "scadenziario")
    except Exception:
        pass
    try:
        from web.helpers import get_agenda

        ruolo = f"{_testo(getattr(fascicolo, 'numero_rg', ''))}/{_testo(getattr(fascicolo, 'anno_rg', ''))}" if _testo(getattr(fascicolo, "numero_rg", "")) else ""
        for appuntamento in get_agenda().tutti():
            if _testo(getattr(appuntamento, "id_fascicolo", "")) == fascicolo_id or (ruolo and ruolo in _testo(getattr(appuntamento, "procedimento", ""))):
                aggiungi(getattr(appuntamento, "data_ora", ""), "agenda")
    except Exception:
        pass
    for documento in list(getattr(fascicolo, "documenti", []) or []):
        aggiungi(getattr(documento, "data_deposito_portale", ""), "portale")
        aggiungi(getattr(documento, "data_comunicazione_cancelleria", ""), "portale")
    for messaggio in list(messaggi_pec or []):
        for udienza in list(messaggio.get("udienze") or []):
            aggiungi(udienza.get("hearing_date"), "presidio PEC")
        for termine in list(messaggio.get("termini") or []):
            aggiungi(termine.get("dies_a_quo_date"), "presidio PEC")
    return note


def importi_noti_fascicolo(fascicolo: Any) -> dict[str, list[str]]:
    """Gli importi che il fascicolo già registra: servono al collaudo come riscontro.

    Un importo letto in una sentenza che coincide con un pagamento registrato o
    con una parcella non è più una proposta: è un dato confermato da un'altra
    fonte, e il collaudo lo verifica.
    """
    noti: dict[str, list[str]] = {}

    def aggiungi(valore: Any, fonte: str) -> None:
        try:
            numero = float(valore)
        except (TypeError, ValueError):
            return
        if numero <= 0:
            return
        elenco = noti.setdefault(f"{round(numero, 2):.2f}", [])
        if fonte not in elenco:
            elenco.append(fonte)

    for voce in list(getattr(fascicolo, "pagamenti", []) or []):
        dati = voce if isinstance(voce, dict) else getattr(voce, "__dict__", {})
        for chiave in ("importo", "importo_previsto", "importo_pagato"):
            aggiungi(dati.get(chiave) if isinstance(dati, dict) else getattr(voce, chiave, None), "pagamenti del fascicolo")
    try:
        from web.helpers import get_fatturazione

        for parcella in get_fatturazione().tutte():
            if _testo(getattr(parcella, "id_fascicolo", "")) == _testo(getattr(fascicolo, "id", "")):
                aggiungi(getattr(parcella, "totale", None), "parcella")
    except Exception:
        pass
    aggiungi(getattr(fascicolo, "valore_causa", None), "valore della causa")
    return noti


def _messaggi_pec(fascicolo: Any) -> list[dict[str, Any]]:
    try:
        from web.services.fascicolo_pec_presidio import messaggi_pec_per_fascicolo

        return messaggi_pec_per_fascicolo(fascicolo)
    except Exception:
        return []


# ---- la lettura del fascicolo -----------------------------------------------------

def _attribuisci(fatti: Iterable[Fatto], oggetto: Oggetto, motore: str) -> list[Fatto]:
    esito = []
    for fatto in fatti:
        fatto.motore, fatto.tipo, fatto.oggetto_id, fatto.sha256 = motore, oggetto.tipo, oggetto.oggetto_id, oggetto.impronta
        esito.append(fatto)
    return esito


def _leggi_documenti(fascicolo: Any, registro: RegistroLetture, tenant: str, contesto: Contesto, *, forza: bool, limite: int) -> dict[str, int]:
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    conteggi = {"da_leggere": 0, "letti": 0, "senza_testo": 0, "assenti": 0, "fatti": 0, "verificati": 0}
    da_leggere = registro.da_leggere(tenant, fascicolo_id, LETTORE_DOCUMENTI, tipi=("documento",))
    documenti = {str(getattr(d, "id", "")): d for d in list(getattr(fascicolo, "documenti", []) or [])}
    # Ritenta le sole email escluse dall'estrattore precedente, senza invalidare
    # le letture valide di tutti gli altri documenti.
    letti_prima = {
        (l.oggetto_id, l.sha256) for l in registro.letture(tenant, fascicolo_id, lettore=LETTORE_DOCUMENTI)
        if l.stato == "non_leggibile" and (forza or (
            (l.esito or {}).get("estrattore_versione") != VERSIONE_ESTRAZIONE_FORMATI))
    }
    for oggetto in registro.oggetti(tenant, fascicolo_id):
        if oggetto.tipo == "documento" and (oggetto.oggetto_id, oggetto.impronta) in letti_prima and oggetto not in da_leggere:
            da_leggere.append(oggetto)
    conteggi["da_leggere"] = len(da_leggere)
    documenti = {str(getattr(d, "id", "")): d for d in list(getattr(fascicolo, "documenti", []) or [])}
    for oggetto in da_leggere[:limite]:
        documento = documenti.get(oggetto.oggetto_id)
        if documento is None:
            # L'oggetto è nell'inventario ma il documento non c'è più: senza questa
            # chiusura resterebbe «da leggere» per sempre e la lettura automatica
            # non risulterebbe mai completa.
            conteggi["assenti"] += 1
            registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE_DOCUMENTI, stato="non_leggibile", esito={"motivo": "documento non più presente nel fascicolo"}, versione=VERSIONE_MOTORE_DOCUMENTI)
            continue
        letture = testi_documento(fascicolo, documento)
        if not letture:
            from web.services.archivio_testo_contenitori import estrai_contenuto
            data = _bytes_documento(fascicolo_id, documento)
            nome = str(getattr(documento, "percorso", "") or oggetto.nome)
            estratto = estrai_contenuto(data, nome)
            if estratto.testo.strip() and not estratto.errori:
                letture = [(estratto.origine, estratto.testo)]
            else:
                conteggi["senza_testo"] += 1
                motivo = "; ".join(estratto.errori) or "Il file è leggibile ma non contiene testo estraibile."
                registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE_DOCUMENTI, stato="non_leggibile", esito={"motivo": motivo, "estrattore_versione": VERSIONE_ESTRAZIONE_FORMATI}, versione=VERSIONE_MOTORE_DOCUMENTI)
                continue
        oggetto = registro.oggetto(tenant, fascicolo_id, "documento", oggetto.oggetto_id) or oggetto
        origine, testo = letture[0]
        contesto_documento = Contesto(oggi=contesto.oggi, anno_riferimento=contesto.anno_riferimento, data_minima=contesto.data_minima, numero_rg=contesto.numero_rg, anno_rg=contesto.anno_rg, date_note=contesto.date_note, importi_noti=contesto.importi_noti)
        if len(letture) > 1:
            contesto_documento.testo_secondario, contesto_documento.etichetta_secondario = letture[1][1], {"ocr": "lettura OCR", "indice": "indice documentale", "nativo": "testo nativo del PDF"}[letture[1][0]]
        metadata = {"tipo_documento": _testo(getattr(documento, "tipo", "")), "classification": _testo(getattr(documento, "classificazione_portale", ""))}
        from web.services.sentenza_economic_runtime import _cu_tiers
        metadata.update(fascicolo=fascicolo, documento_id=documento.id,
                        document_hash_sha256=_testo(getattr(documento, "hash_sha256", "")), cu_tiers=_cu_tiers())
        fatti = _attribuisci(leggi_testo(testo, origine=origine, contesto=contesto_documento, nome=oggetto.nome, metadata=metadata), oggetto, "documenti")
        registro.registra_fatti(tenant, fascicolo_id, oggetto, "documenti", fatti, versione=VERSIONE_MOTORE_DOCUMENTI)
        registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE_DOCUMENTI, esito={"origine": origine, "estrattore_versione": VERSIONE_ESTRAZIONE_FORMATI, "letture": [o for o, _ in letture], "fatti": len(fatti), "verificati": sum(1 for f in fatti if f.verifica == "verificata")}, versione=VERSIONE_MOTORE_DOCUMENTI)
        conteggi["letti"] += 1
        conteggi["fatti"] += len(fatti)
        conteggi["verificati"] += sum(1 for f in fatti if f.verifica == "verificata")
    return conteggi


def _bytes_allegato_pec(oggetto: Any, repository: Any, cache: dict[str, bytes]) -> bytes:
    import hashlib
    from email import policy
    from email.parser import BytesParser
    if oggetto.origine not in cache:
        raw, row = repository.original_mime(oggetto.origine)
        if hashlib.sha256(raw).hexdigest() != row["mime_sha256"]:
            raise ValueError("Impronta del messaggio originale non corrispondente.")
        cache[oggetto.origine] = raw
    for part in BytesParser(policy=policy.default).parsebytes(cache[oggetto.origine]).walk():
        payload = part.get_payload(decode=True)
        if isinstance(payload, bytes) and payload and hashlib.sha256(payload).hexdigest() == oggetto.sha256:
            return payload
    raise ValueError("Allegato non ritrovato nel messaggio originale con la stessa impronta.")


def _allegato_tecnico(oggetto: Any, repository: Any, cache: dict[str, bytes]) -> dict[str, Any] | None:
    """Ispeziona il contenitore binario reale; non certifica la firma né decifra la busta."""
    import hashlib
    from email import policy
    from email.parser import BytesParser
    from asn1crypto.cms import ContentInfo
    if not str(oggetto.nome).lower().endswith((".p7s", ".enc")):
        return None
    if oggetto.origine not in cache:
        raw, row = repository.original_mime(oggetto.origine)
        if hashlib.sha256(raw).hexdigest() != row["mime_sha256"]:
            return None
        cache[oggetto.origine] = raw
    for part in BytesParser(policy=policy.default).parsebytes(cache[oggetto.origine]).walk():
        raw = part.get_payload(decode=True) or b""
        if not raw or hashlib.sha256(raw).hexdigest() != oggetto.sha256:
            continue
        try:
            cms = ContentInfo.load(raw, strict=True)
            kind = cms["content_type"].native
            if kind == "signed_data" and cms["content"]["encap_content_info"]["content"].native is None:
                return {"analisi": "metadati_tecnici", "tipo": "firma_separata", "motivo": "Firma PEC separata: struttura CMS letta; nessun testo autonomo. La validità crittografica resta nel presidio firme."}
            if kind == "enveloped_data":
                cms["content"]["encrypted_content_info"]["content_encryption_algorithm"].native
                return {"analisi": "metadati_tecnici", "tipo": "busta_cifrata", "motivo": "Busta cifrata: struttura CMS letta; contenuto riservato al destinatario. Atti e ricevute sono letti dalle rispettive fonti."}
        except (ValueError, TypeError, KeyError):
            return None
    return None


def _leggi_pec(fascicolo: Any, registro: RegistroLetture, tenant: str, contesto: Contesto, messaggi: list[dict[str, Any]], *, limite: int) -> dict[str, int]:
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    conteggi = {"da_leggere": 0, "letti": 0, "assenti": 0, "fatti": 0, "verificati": 0}
    da_leggere = registro.da_leggere(tenant, fascicolo_id, LETTORE_PEC, tipi=("pec", "allegato_pec"))
    falliti = {(l.oggetto_id, l.sha256) for l in registro.letture(tenant, fascicolo_id, lettore=LETTORE_PEC) if l.tipo == "allegato_pec" and l.stato == "non_leggibile" and (l.esito or {}).get("estrattore_versione") != VERSIONE_ESTRAZIONE_FORMATI}
    da_leggere.extend(o for o in registro.oggetti(tenant, fascicolo_id) if o.tipo == "allegato_pec" and (o.oggetto_id, o.impronta) in falliti and o not in da_leggere)
    conteggi["da_leggere"] = len(da_leggere)
    per_id = {str(m.get("id")): m for m in messaggi}
    allegati: dict[str, dict[str, Any]] = {}
    if any(o.tipo == "allegato_pec" for o in da_leggere):
        for riga in _righe_pec_collegate(fascicolo_id):
            for allegato in list(riga.get("allegati") or []):
                allegati[str(allegato.get("id") or "")] = allegato
    from web.services.pec_pipeline_runtime import repository_for_current_request
    repository_pec = repository_for_current_request()
    mime_cache: dict[str, bytes] = {}
    for oggetto in da_leggere[:limite]:
        if oggetto.tipo == "pec":
            messaggio = per_id.get(oggetto.oggetto_id)
            if messaggio is None:
                # Il messaggio non è più collegato al fascicolo: si chiude la lettura
                # invece di lasciare l'oggetto in attesa a ogni giro.
                conteggi["assenti"] += 1
                registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE_PEC, stato="non_leggibile", esito={"motivo": "messaggio PEC non più collegato al fascicolo"}, versione=VERSIONE_MOTORE_PEC)
                continue
            fatti = _attribuisci(fatti_da_messaggio(messaggio, contesto), oggetto, "pec")
        else:
            allegato = allegati.get(oggetto.oggetto_id)
            testo = str((allegato or {}).get("ocr_text") or "")
            if not testo.strip():
                tecnico = _allegato_tecnico(oggetto, repository_pec, mime_cache) if allegato is not None else None
                if tecnico:
                    registro.registra_fatti(tenant, fascicolo_id, oggetto, "pec", [], versione=VERSIONE_MOTORE_PEC)
                    registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE_PEC, esito=tecnico, versione=VERSIONE_MOTORE_PEC)
                    conteggi["letti"] += 1
                    continue
                motivo = "Allegato non più presente nella PEC collegata."
                if allegato is not None:
                    from web.services.archivio_testo_contenitori import estrai_contenuto
                    try:
                        estratto = estrai_contenuto(_bytes_allegato_pec(oggetto, repository_pec, mime_cache), oggetto.nome)
                        testo = estratto.testo if not estratto.errori else ""
                        motivo = "; ".join(estratto.errori) or "Allegato privo di testo estraibile."
                    except (ValueError, OSError) as exc:
                        motivo = str(exc)
                if not testo.strip():
                    conteggi["assenti"] += 1
                    registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE_PEC, stato="non_leggibile", esito={"motivo": motivo, "estrattore_versione": VERSIONE_ESTRAZIONE_FORMATI}, versione=VERSIONE_MOTORE_PEC)
                    continue
            fatti = _attribuisci(fatti_da_allegato(testo, nome=oggetto.nome, contesto=contesto), oggetto, "pec")
        registro.registra_fatti(tenant, fascicolo_id, oggetto, "pec", fatti, versione=VERSIONE_MOTORE_PEC)
        registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE_PEC, esito={"estrattore_versione": VERSIONE_ESTRAZIONE_FORMATI, "fatti": len(fatti), "verificati": sum(1 for f in fatti if f.verifica == "verificata")}, versione=VERSIONE_MOTORE_PEC)
        conteggi["letti"] += 1
        conteggi["fatti"] += len(fatti)
        conteggi["verificati"] += sum(1 for f in fatti if f.verifica == "verificata")
    return conteggi


def _ricollauda_plausibili(fascicolo: Any, registro: RegistroLetture, tenant: str, contesto: Contesto) -> int:
    """I fatti plausibili si riprovano con le date note di oggi: una concordanza nuova li verifica."""
    from pct.archivio_letture import collauda

    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    promossi = 0
    per_oggetto: dict[tuple[str, str, str, str], list[Fatto]] = {}
    for fatto in registro.fatti(tenant, fascicolo_id, verifiche=("plausibile",)):
        if fatto.categoria != "data" or fatto.valore.split("T")[0] not in contesto.date_note:
            continue
        per_oggetto.setdefault((fatto.tipo, fatto.oggetto_id, fatto.sha256, fatto.motore), []).append(fatto)
    for (tipo, oggetto_id, sha, motore), plausibili in per_oggetto.items():
        tutti = [f for f in registro.fatti_oggetto(tenant, tipo, oggetto_id) if f.sha256 == sha and f.motore == motore]
        cambiato = False
        for fatto in tutti:
            if any(fatto.id == p.id for p in plausibili):
                fatto.prove = [p for p in fatto.prove if p.get("codice") not in {"orizzonte", "doppia_lettura", "concordanza"}]
                fatto.verifica = "plausibile"
                collauda(fatto, contesto)
                if fatto.verifica == "verificata":
                    promossi += 1
                    cambiato = True
        if cambiato:
            oggetto = Oggetto(tipo=tipo, oggetto_id=oggetto_id, sha256=sha if not sha.startswith(("archivio:", "dimensione:")) else "", sha256_archivio=sha[9:] if sha.startswith("archivio:") else "", dimensione=int(sha[11:]) if sha.startswith("dimensione:") else 0)
            registro.registra_fatti(tenant, fascicolo_id, oggetto, motore, tutti, versione=VERSIONE_MOTORE_DOCUMENTI if motore == "documenti" else VERSIONE_MOTORE_PEC)
    return promossi


def _riconvalida(fascicolo: Any, registro: RegistroLetture, tenant: str) -> dict[str, int]:
    """Le regole di oggi ripassano ciò che è già registrato: niente resta aperto per una regola superata.

    Chi ha già letto un documento non lo rilegge; ma le anomalie e i fatti
    registrati con regole più larghe vanno riportati alle regole correnti,
    altrimenti l'avvocato continua a vedere conferme che il software oggi non
    chiederebbe più.
    """
    from pct.registro_letture.riconvalida import contesto_riconvalida

    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    esito = {"anomalie": 0, "fatti": 0}
    try:
        contesto = contesto_riconvalida(fascicolo)
        contesti_date: dict[tuple[str, str], list[str]] = {}
        for fatto in registro.fatti(tenant, fascicolo_id, verifiche=None):
            if fatto.categoria == "data" and fatto.contesto:
                contesti_date.setdefault((fatto.oggetto_id, fatto.valore_letto), []).append(fatto.contesto)
        contesto["contesti_date"] = contesti_date
        esito["anomalie"] = len(registro.chiudi_anomalie_superate(tenant, fascicolo_id, contesto=contesto))
    except Exception as exc:
        logger.debug("Riconvalida delle anomalie non riuscita per %s: %s", fascicolo_id, exc)
    try:
        esclusioni = {f.oggetto_id: f.contesto for f in registro.fatti(tenant, fascicolo_id, verifiche=("verificata", "corretta")) if f.campo == "natura_documentale" and f.valore in {"contratto_lavoro", "documento_identita", "precedente_giurisprudenziale"}}
        esito["fatti"] = len(registro.riconvalida_fatti(tenant, fascicolo_id, esclusioni_oggetto=esclusioni))
    except Exception as exc:
        logger.debug("Riconvalida dei fatti non riuscita per %s: %s", fascicolo_id, exc)
    return esito


def _impronta_viva(fascicolo: Any) -> str:
    """L'impronta dell'inventario corrente: documenti e PEC collegate, senza aprire file.

    Si basa sui metadati che il fascicolo già porta (identificativo, impronta
    SHA-256 del documento, dimensione) e sulle PEC collegate: cambia appena un
    documento viene aggiunto, sostituito o rimosso, o appena arriva una PEC.
    """
    from pct.registro_letture import impronta_inventario
    from web.services.registro_letture_runtime import inventario_fascicolo

    try:
        return impronta_inventario(inventario_fascicolo(fascicolo, con_pec=True))
    except Exception as exc:
        logger.debug("Impronta del fascicolo non calcolata per %s: %s", getattr(fascicolo, "id", ""), exc)
        return ""


def stato_ciclo_fascicolo(fascicolo_id: str, registro: RegistroLetture, tenant: str, *, impronta: str = "") -> StatoCiclo:
    """Dove sta il fascicolo nel ciclo dei due motori: fermo, da leggere o in errore."""
    from pct.registro_letture import versione_compatibile_lettore

    riga = dict(registro.impronta_fascicolo(tenant, fascicolo_id, LETTORE_DOCUMENTI) or {})
    if riga.get("esito_json") and "esito" not in riga:
        import json

        try:
            riga["esito"] = json.loads(str(riga.get("esito_json") or "{}"))
        except (TypeError, ValueError):
            riga["esito"] = {}
    return stato_ciclo(
        riga or None,
        versione_attesa=VERSIONE_MOTORE_DOCUMENTI,
        impronta_attesa=impronta,
        versione_compatibile=lambda versione: versione_compatibile_lettore(LETTORE_DOCUMENTI, versione, VERSIONE_MOTORE_DOCUMENTI),
    )


def _mancanti_motori(registro: RegistroLetture, tenant: str, fascicolo_id: str) -> tuple[int, int]:
    """Oggetti ancora non letti dai due motori, anche se la riga ciclo dice fermo."""
    try:
        stato = registro.stato_fascicolo(tenant, fascicolo_id, lettori=(LETTORE_DOCUMENTI, LETTORE_PEC))
    except Exception as exc:
        logger.exception("Stato oggetti dei motori non leggibile per %s", fascicolo_id)
        raise RuntimeError("Stato della lettura non disponibile: il ciclo resta aperto.") from exc
    mancanti = sum(int(voce.da_leggere or 0) for voce in stato.lettori)
    errori = sum(int(voce.errori or 0) for voce in stato.lettori)
    return mancanti, errori


def _segna_ciclo(registro: RegistroLetture, tenant: str, fascicolo_id: str, *, impronta: str, totali: int, letti: int, stato: str, motivo: str = "") -> None:
    """Scrive nell'archivio dove è arrivato il ciclo: è la conferma che chiude il giro."""
    try:
        registro.segna_fascicolo(
            tenant, fascicolo_id, LETTORE_DOCUMENTI,
            impronta=impronta, oggetti_totali=totali, oggetti_letti=letti,
            stato=stato, versione=VERSIONE_MOTORE_DOCUMENTI,
            esito={"motivo": motivo} if motivo else {},
        )
    except Exception as exc:
        logger.debug("Stato del ciclo non registrato per %s: %s", fascicolo_id, exc)


def _consegna_ai_presidi(fascicolo: Any, registro: RegistroLetture) -> dict[str, Any]:
    """L'archivio consegna ai presìdi che scrivono; un guasto qui non ferma il ciclo."""
    try:
        from web.services.consegna_presidi_runtime import consegna_fascicolo

        return consegna_fascicolo(fascicolo, registro=registro)
    except Exception as exc:
        logger.exception("Consegna ai presìdi non riuscita per il fascicolo %s", getattr(fascicolo, "id", ""))
        return {"errore": f"{type(exc).__name__}: {exc}"[:200], "consegnati": 0, "non_pertinenti": 0, "rifiutati": 0}


def leggi_fascicolo(fascicolo: Any, *, forza: bool = False, limite: int = 200, registro: RegistroLetture | None = None) -> dict[str, Any]:
    """Un giro del ciclo: i motori leggono solo ciò che manca, l'archivio conferma, poi ci si ferma.

    Il ciclo è chiuso: quando tutto è letto e l'archivio ha confermato, il
    fascicolo resta **fermo** e questa funzione non apre più nulla. Si riattiva
    su un documento nuovo, su un documento cambiato, su una PEC nuova, quando
    cambiano le regole di un motore, o al ricontrollo periodico che fa da rete
    di sicurezza se un evento è andato perso.
    """
    registro = registro or registro_corrente()
    tenant = tenant_corrente()
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    if not fascicolo_id:
        return {"documenti": {}, "pec": {}, "promossi": 0, "ciclo": {}}
    if not forza:
        # L'impronta si calcola dal fascicolo vivo — dai metadati dei documenti e
        # dalle PEC collegate, senza aprire alcun file — e si confronta con quella
        # che l'archivio ha confermato: se coincidono il ciclo è fermo e qui non
        # si fa nulla. Confrontare l'archivio con sé stesso non vedrebbe mai un
        # documento nuovo.
        prima = stato_ciclo_fascicolo(fascicolo_id, registro, tenant, impronta=_impronta_viva(fascicolo))
        mancanti_motori, errori_motori = _mancanti_motori(registro, tenant, fascicolo_id)
        if not prima.da_leggere and not mancanti_motori:
            return {
                "inventario": {},
                "documenti": {"da_leggere": 0, "letti": 0, "senza_testo": 0, "assenti": 0, "fatti": 0, "verificati": 0},
                "pec": {"da_leggere": 0, "letti": 0, "assenti": 0, "fatti": 0, "verificati": 0},
                "promossi": 0, "riconvalidati": {"anomalie": 0, "fatti": 0}, "restano": 0,
                "fermo": True, "ciclo": prima.to_dict(),
            }
        if not prima.da_leggere:
            logger.info(
                "Ciclo letture riaperto per %s: riga fascicolo ferma ma oggetti mancanti=%s errori storici=%s",
                fascicolo_id, mancanti_motori, errori_motori,
            )
    try:
        messaggi = _messaggi_pec(fascicolo)
        from web.services.correlazioni_ricevute_archivio import prepara_correlazioni
        from web.services.pec_pipeline_runtime import repository_for_current_request
        prepara_correlazioni(fascicolo, messaggi, repository_for_current_request())
        inventario = aggiorna_inventario(fascicolo, registro=registro, con_pec=True)
        contesto = contesto_da_fascicolo(fascicolo, date_note=date_note_fascicolo(fascicolo, messaggi_pec=messaggi))
        contesto.importi_noti = importi_noti_fascicolo(fascicolo)
        riconvalidati = _riconvalida(fascicolo, registro, tenant)
        documenti = _leggi_documenti(fascicolo, registro, tenant, contesto, forza=forza, limite=limite)
        pec = _leggi_pec(fascicolo, registro, tenant, contesto, messaggi, limite=limite)
        promossi = _ricollauda_plausibili(fascicolo, registro, tenant, contesto)
    except Exception as exc:
        # Il fascicolo non esce dal ciclo: resta in errore dichiarato e si riprova.
        logger.exception("Giro del ciclo non riuscito per il fascicolo %s", fascicolo_id)
        _segna_ciclo(registro, tenant, fascicolo_id, impronta="", totali=0, letti=0, stato="errore", motivo=f"{type(exc).__name__}: {exc}"[:300])
        raise
    # Seconda gamba della catena: l'archivio consegna ai presìdi che scrivono, e
    # loro confermano. Un fatto già consegnato non viene riproposto.
    consegne = _consegna_ai_presidi(fascicolo, registro)
    from web.services.sentenza_economic_runtime import ensure_fascicolo_sentenza_economic_analysis
    economia = ensure_fascicolo_sentenza_economic_analysis(fascicolo_id)
    if documenti["letti"] or pec["letti"] or promossi or riconvalidati["anomalie"] or riconvalidati["fatti"]:
        invalida_lettura(fascicolo_id)
    chiusi_documenti = documenti["letti"] + documenti["senza_testo"] + documenti["assenti"]
    chiusi_pec = pec["letti"] + pec["assenti"]
    restano = max(0, documenti["da_leggere"] - chiusi_documenti) + max(0, pec["da_leggere"] - chiusi_pec)
    # L'archivio conferma: il ciclo si chiude quando non resta nulla da leggere.
    impronta = _impronta_viva(fascicolo)
    _segna_ciclo(
        registro, tenant, fascicolo_id,
        impronta=impronta, totali=len(registro.oggetti(tenant, fascicolo_id)),
        letti=chiusi_documenti + chiusi_pec,
        stato="completa" if restano == 0 else "parziale",
        motivo="" if restano == 0 else f"{restano} oggetti oltre il tetto di questo giro",
    )
    dopo = stato_ciclo_fascicolo(fascicolo_id, registro, tenant, impronta=impronta)
    return {
        "inventario": inventario, "documenti": documenti, "pec": pec, "promossi": promossi, "riconvalidati": riconvalidati,
        "consegne": consegne, "economia": economia, "restano": restano, "fermo": restano == 0, "ciclo": dopo.to_dict(),
    }


def fatti_fascicolo(fascicolo: Any, **filtri: Any) -> list[Fatto]:
    """I fatti utili del fascicolo dall'archivio (mai una lettura in questa chiamata)."""
    canonico = bool(filtri.pop("canonico", True))
    try:
        fatti = registro_corrente().fatti(tenant_corrente(), _testo(getattr(fascicolo, "id", "")), **filtri)
        if not canonico or filtri.get("motore") or filtri.get("tipo"):
            return fatti
        from pct.archivio_letture import fatti_canonici

        return fatti_canonici(fatti)
    except Exception as exc:
        logger.exception("Archivio delle letture non disponibile per %s", getattr(fascicolo, "id", ""))
        raise RuntimeError("Archivio delle letture non disponibile: impossibile verificare i dati del fascicolo.") from exc


MOTIVI_IN_ATTESA = {
    "da_leggere": "non ancora letto dai motori",
    "da_rileggere": "il contenuto è cambiato: va riletto",
    "regole_aggiornate": "regole di lettura aggiornate: verifica automatica in corso",
    "in_corso": "lettura in corso",
    "errore": "la lettura precedente è fallita",
    "non_leggibile": "contenuto non leggibile: verificare il motivo registrato",
}


def oggetti_in_attesa(stato: Any, *, letture: Iterable[Any] = ()) -> list[dict[str, str]]:
    """Gli oggetti che i motori devono ancora leggere, con il motivo in italiano.

    Il pannello deve poter dire *quale* oggetto manca e perché: «la lettura
    automatica deve ancora leggere 1 oggetto» senza dire quale non è una
    informazione utilizzabile dall'avvocato.
    """
    motivi_registrati = {
        (lettura.tipo, lettura.oggetto_id, lettura.lettore): _testo((lettura.esito or {}).get("motivo"))
        for lettura in letture
    }
    in_attesa: list[dict[str, str]] = []
    stati_in_attesa = {"da_leggere", "da_rileggere", "regole_aggiornate", "in_corso"}
    for riga in list(getattr(stato, "per_oggetto", []) or []):
        for lettore, stato_lettura in dict(riga.get("letture") or {}).items():
            if lettore not in {LETTORE_DOCUMENTI, LETTORE_PEC} or stato_lettura not in stati_in_attesa:
                continue
            registrato = motivi_registrati.get((str(riga.get("tipo") or ""), str(riga.get("oggetto_id") or ""), lettore))
            in_attesa.append({
                "tipo": str(riga.get("tipo") or ""),
                "oggetto_id": str(riga.get("oggetto_id") or ""),
                "nome": str(riga.get("nome") or "") or str(riga.get("oggetto_id") or ""),
                "motore": "documenti" if lettore == LETTORE_DOCUMENTI else "PEC",
                "motivo": MOTIVI_IN_ATTESA[stato_lettura] if stato_lettura == "regole_aggiornate" else registrato or MOTIVI_IN_ATTESA[stato_lettura],
            })
    return in_attesa


def stato_archivio_payload(fascicolo: Any, *, registro: RegistroLetture | None = None) -> dict[str, Any]:
    """Il riquadro dell'archivio nel pannello «Letture e verifiche»."""
    from pct.formatting import format_datetime_it

    registro = registro or registro_corrente()
    tenant = tenant_corrente()
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    from pct.archivio_letture import fatti_canonici

    fatti = fatti_canonici(registro.fatti(tenant, fascicolo_id, verifiche=None))
    riassunto = riassunto_archivio(fatti)
    stato = registro.stato_fascicolo(tenant, fascicolo_id, lettori=(LETTORE_DOCUMENTI, LETTORE_PEC))
    lettori = {voce.lettore: voce for voce in stato.lettori}
    ultima = max([voce.ultima_lettura for voce in stato.lettori] + [""])
    da_leggere = sum(voce.da_leggere for voce in stato.lettori)
    errori = sum(voce.errori for voce in stato.lettori)
    in_attesa = oggetti_in_attesa(stato, letture=registro.letture(tenant, fascicolo_id))
    with _LOCK:
        in_corso = fascicolo_id in _IN_CORSO
    riassunto.update({
        "versione": {"documenti": VERSIONE_MOTORE_DOCUMENTI, "pec": VERSIONE_MOTORE_PEC},
        "lettura_automatica": {
            "in_corso": in_corso,
            "da_leggere": da_leggere,
            "errori": errori,
            "completa": da_leggere == 0 and not in_corso,
            "ultima_lettura": ultima,
            "ultima_lettura_it": format_datetime_it(ultima) if ultima else "",
            "documenti": {"letti": lettori[LETTORE_DOCUMENTI].letti, "da_leggere": lettori[LETTORE_DOCUMENTI].da_leggere} if LETTORE_DOCUMENTI in lettori else {},
            "pec": {"letti": lettori[LETTORE_PEC].letti, "da_leggere": lettori[LETTORE_PEC].da_leggere} if LETTORE_PEC in lettori else {},
            "in_attesa": in_attesa,
        },
        "collaudo_lettore": collaudo_lettore_payload(),
    })
    return riassunto


def decidi_fatto(fatto_id: str, *, esito: str, valore: str = "", registro: RegistroLetture | None = None) -> dict[str, Any]:
    """L'avvocato conferma («verificata»), corregge («corretta», con il valore giusto) o ignora un fatto dell'archivio."""
    from web.services.registro_letture_runtime import utente_corrente_id

    registro = registro or registro_corrente()
    verifica = {"confermata": "verificata", "verificata": "verificata", "corretta": "corretta", "ignorata": "ignorata"}.get(_testo(esito).lower(), "")
    if not verifica:
        raise ValueError("Esito non valido.")
    valore_iso = ""
    if verifica == "corretta":
        from pct.registro_letture.verifica_date import interpreta_data

        data = interpreta_data(valore)
        if data is None:
            raise ValueError("Per correggere serve una data nel formato gg/mm/aaaa.")
        valore_iso = data.isoformat()
    fatto = registro.decidi_fatto(tenant_corrente(), fatto_id, verifica=verifica, valore=valore_iso, utente_id=utente_corrente_id())
    if fatto.fascicolo_id:
        invalida_lettura(fatto.fascicolo_id)
    return fatto.to_dict()


def collaudo_lettore_payload() -> dict[str, Any]:
    try:
        from legal_ocr.collaudo import ultimo_esito

        return ultimo_esito(percorso_collaudo())
    except Exception:
        return {"eseguito": False}


def percorso_collaudo() -> Path:
    base = ""
    if has_app_context():
        base = _testo(current_app.config.get("SEARCH_INDEX"))
    return Path(base).resolve().parent.parent / "intelligence" / "collaudo_lettore.json" if base else Path("./data/intelligence/collaudo_lettore.json")


# ---- la lettura in sfondo e la lettura automatica ------------------------------------

def avvia_lettura_in_background(app: Any, fascicolo_id: str, *, paths: dict[str, Any] | None = None, tenant_slug: str = "", forza: bool = False) -> bool:
    """Un documento caricato o una PEC collegata: i motori leggono l'oggetto nuovo in un thread, mai nella richiesta."""
    fascicolo_id = _testo(fascicolo_id)
    if not fascicolo_id:
        return False
    with _LOCK:
        if fascicolo_id in _IN_CORSO:
            return False
        _IN_CORSO.add(fascicolo_id)

    def corsa() -> None:
        try:
            with app.test_request_context("/__archivio-letture/" + fascicolo_id):
                g.data_paths = dict(paths or {})
                g.tenant = None
                g.tenant_context_slug = tenant_slug
                g.tenant_context_required = False
                g.tenant_context_missing = False
                g.storage_runtime = None
                if tenant_slug and app.config.get("MULTI_TENANT"):
                    try:
                        from pct.tenant import GestioneTenant

                        g.tenant = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"]).get(tenant_slug)
                    except Exception:
                        g.tenant = None
                from web.helpers import get_fascicoli

                fascicolo = get_fascicoli().get(fascicolo_id)
                if fascicolo is not None:
                    esito = leggi_fascicolo(fascicolo, forza=forza)
                    if int(esito.get("restano") or 0) > 0:
                        # Solo se la lettura puntuale non chiude tutto si
                        # riattiva il giro di sicurezza. Una PEC nuova già
                        # letta qui non deve risvegliare tutti i fascicoli.
                        riattiva_scheduler_letture(paths)
        except Exception:
            riattiva_scheduler_letture(paths)
            logger.exception("Lettura in sfondo del fascicolo %s interrotta", fascicolo_id)
        finally:
            with _LOCK:
                _IN_CORSO.discard(fascicolo_id)

    threading.Thread(target=corsa, name=f"archivio-letture-{fascicolo_id}", daemon=True).start()
    return True


def _contesto_corrente() -> tuple[dict[str, Any], str]:
    if not has_app_context():
        return {}, ""
    return dict(getattr(g, "data_paths", {}) or {}), _testo(getattr(g, "tenant_context_slug", ""))


def lettura_dopo_evento(fascicolo_id: str) -> bool:
    """Chiamata dagli eventi del registro (documento caricato, PEC collegata): parte il thread se c'è un'app."""
    if not has_app_context():
        return False
    paths, slug = _contesto_corrente()
    try:
        return avvia_lettura_in_background(current_app._get_current_object(), fascicolo_id, paths=paths, tenant_slug=slug)
    except Exception as exc:
        logger.debug("Lettura in sfondo non avviata per %s: %s", fascicolo_id, exc)
        return False


def panoramica_letture(*, includi_fermi: bool = True, limite: int = 0) -> dict[str, Any]:
    """Lo stato della lettura su tutti i fascicoli dello studio, in una schermata.

    Con trecento fascicoli non si puo' aprirli uno alla volta per sapere se sono
    stati letti. Qui si guarda il registro — non i documenti: nessun file viene
    aperto e nessuna impronta ricalcolata — e si dice, per ciascuno, se i due
    motori hanno finito, quanto hanno letto e quando.

    La riga di un fascicolo mai esaminato non esiste nel registro: quel
    fascicolo compare come «mai letto», che e' un'informazione, non un errore.
    """
    from web.helpers import get_fascicoli

    registro = registro_corrente()
    tenant = tenant_corrente()
    try:
        righe_documenti = {
            _testo(r.get("fascicolo_id")): r for r in registro.righe_fascicoli(tenant, lettore=LETTORE_DOCUMENTI)
        }
        righe_pec = {
            _testo(r.get("fascicolo_id")): r for r in registro.righe_fascicoli(tenant, lettore=LETTORE_PEC)
        }
        conteggi = registro.conteggi_letture(tenant)
    except Exception:
        logger.exception("Panoramica delle letture non disponibile")
        return {"ok": False, "message": "Registro delle letture non leggibile."}

    fascicoli = list(get_fascicoli().tutti(archiviati=True))
    voci: list[dict[str, Any]] = []
    totali = {"fascicoli": 0, "fermi": 0, "da_leggere": 0, "in_errore": 0, "mai_letti": 0, "oggetti_letti": 0, "oggetti_non_leggibili": 0}
    for fascicolo in fascicoli:
        fascicolo_id = _testo(getattr(fascicolo, "id", ""))
        if not fascicolo_id:
            continue
        totali["fascicoli"] += 1
        documenti = righe_documenti.get(fascicolo_id) or {}
        pec = righe_pec.get(fascicolo_id) or {}
        per_stato = conteggi.get(fascicolo_id) or {}
        letti = int(per_stato.get("letto", 0))
        non_leggibili = int(per_stato.get("non_leggibile", 0))
        totali["oggetti_letti"] += letti
        totali["oggetti_non_leggibili"] += non_leggibili
        stato_documenti = _testo(documenti.get("stato"))
        stato_pec = _testo(pec.get("stato"))
        if not documenti and not pec:
            stato = "mai_letto"
        elif "errore" in (stato_documenti, stato_pec):
            stato = "in_errore"
        elif stato_documenti == "completa" and stato_pec in ("", "completa"):
            stato = "fermo"
        else:
            stato = "da_leggere"
        totali[{"fermo": "fermi", "da_leggere": "da_leggere", "in_errore": "in_errore", "mai_letto": "mai_letti"}[stato]] += 1
        if stato == "fermo" and not includi_fermi:
            continue
        voci.append({
            "fascicoloId": fascicolo_id,
            "numero": _testo(getattr(fascicolo, "numero", "")),
            "titolo": _testo(getattr(fascicolo, "titolo", "")),
            "cliente": _testo(getattr(fascicolo, "nome_cliente", "")),
            "stato": stato,
            "documentiLetti": int(documenti.get("oggetti_letti") or 0),
            "documentiTotali": int(documenti.get("oggetti_totali") or 0),
            "pecLette": int(pec.get("oggetti_letti") or 0),
            "pecTotali": int(pec.get("oggetti_totali") or 0),
            "nonLeggibili": non_leggibili,
            "ultimaLettura": _iso_a_etichetta(_testo(documenti.get("aggiornato_il")) or _testo(pec.get("aggiornato_il"))),
            "versioneMotore": _testo(documenti.get("versione_lettore")),
        })
    ordine = {"in_errore": 0, "mai_letto": 1, "da_leggere": 2, "fermo": 3}
    voci.sort(key=lambda v: (ordine.get(v["stato"], 9), v["numero"] or v["fascicoloId"]))
    if limite > 0:
        voci = voci[:limite]
    totali["tutti_fermi"] = totali["fascicoli"] > 0 and totali["fermi"] == totali["fascicoli"]
    return {"ok": True, "totali": totali, "fascicoli": voci}


def _iso_a_etichetta(valore: str) -> str:
    """La data come la scrive un atto italiano; vuota se non c'e'."""
    testo = _testo(valore)
    if not testo:
        return ""
    try:
        momento = datetime.fromisoformat(testo.replace("Z", "+00:00"))
    except ValueError:
        return testo[:19]
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=ROME)
    return momento.astimezone(ROME).strftime("%d/%m/%Y %H:%M")


def lettura_automatica_corrente(*, limite_oggetti: int = 150, usa_marker_scheduler: bool = False) -> dict[str, Any]:
    """Tutti i fascicoli dello studio corrente: legge solo ciò che manca, entro un tetto di oggetti per giro."""
    from web.helpers import get_fascicoli

    paths, _slug = _contesto_corrente()
    app_obj = current_app._get_current_object() if has_app_context() else None
    if usa_marker_scheduler:
        marker = _scheduler_idle_attivo(app_obj, paths)
        if marker:
            return _report_scheduler_saltato(marker)
    registro = registro_corrente()
    fascicoli = list(get_fascicoli().tutti(archiviati=True))
    report = {"fascicoli": len(fascicoli), "esaminati": 0, "documenti_letti": 0, "pec_lette": 0, "fatti": 0, "verificati": 0, "promossi": 0, "senza_testo": 0, "restano": 0, "saltati": 0}
    residuo = max(1, int(limite_oggetti))
    # Prima i fascicoli aperti, poi gli archiviati.
    fascicoli.sort(key=lambda f: (1 if _testo(getattr(getattr(f, "stato", ""), "value", getattr(f, "stato", ""))).upper() == "ARCHIVIATO" else 0, _testo(getattr(f, "id", ""))))
    for fascicolo in fascicoli:
        if residuo <= 0:
            report["restano"] += 1
            continue
        try:
            esito = leggi_fascicolo(fascicolo, limite=residuo, registro=registro)
        except Exception as exc:
            logger.warning("Lettura automatica non completata per il fascicolo %s: %s", getattr(fascicolo, "id", ""), exc)
            continue
        report["esaminati"] += 1
        documenti = esito.get("documenti") or {}
        pec = esito.get("pec") or {}
        documenti_letti = int(documenti.get("letti") or 0)
        pec_lette = int(pec.get("letti") or 0)
        senza_testo = int(documenti.get("senza_testo") or 0)
        letti = documenti_letti + pec_lette
        residuo -= letti + senza_testo
        report["documenti_letti"] += documenti_letti
        report["pec_lette"] += pec_lette
        report["fatti"] += int(documenti.get("fatti") or 0) + int(pec.get("fatti") or 0)
        report["verificati"] += int(documenti.get("verificati") or 0) + int(pec.get("verificati") or 0)
        report["promossi"] += int(esito["promossi"])
        report["senza_testo"] += senza_testo
        report["restano"] += int(esito["restano"])
    if usa_marker_scheduler:
        _scrivi_scheduler_idle(app_obj, paths, report)
    return report


def lettura_automatica_per_tutti(app: Any, *, limite_oggetti: int = 150, usa_marker_scheduler: bool = False) -> dict[str, Any]:
    """Il job dello scheduler: ogni studio attivo, con il suo contesto tenant-aware."""
    from web.services.fascicoli_presidi_runtime import _active_tenants, _attach_tenant_context

    totali = {"fascicoli": 0, "esaminati": 0, "documenti_letti": 0, "pec_lette": 0, "fatti": 0, "verificati": 0, "promossi": 0, "senza_testo": 0, "restano": 0, "saltati": 0}
    studi: list[dict[str, Any]] = []
    attivi = _active_tenants(app)
    if attivi:
        from pct.tenant import GestioneTenant

        manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        for studio in attivi:
            slug = _testo(getattr(studio, "slug", "")).lower()
            with app.test_request_context(f"/__scheduler/archivio-letture/{slug}"):
                _attach_tenant_context(manager, studio)
                report = lettura_automatica_corrente(limite_oggetti=limite_oggetti, usa_marker_scheduler=usa_marker_scheduler)
            studi.append({"tenant": slug, **report})
    elif app.config.get("MULTI_TENANT"):
        return {"ok": False, "job": "archivio_letture_automatico", "error": "nessuno studio attivo: la lettura automatica non ha fascicoli su cui lavorare", "tenants": [], "totals": totali}
    else:
        with app.test_request_context("/__scheduler/archivio-letture/default"):
            g.multi_tenant_enabled = False
            g.tenant_context_missing = False
            g.tenant_context_slug = ""
            report = lettura_automatica_corrente(limite_oggetti=limite_oggetti, usa_marker_scheduler=usa_marker_scheduler)
        studi.append({"tenant": "default", **report})
    for voce in studi:
        for chiave in totali:
            totali[chiave] += int(voce.get(chiave) or 0)
    prossimi = sorted(str(voce.get("prossimo_controllo") or "") for voce in studi if voce.get("prossimo_controllo"))
    if prossimi:
        totali["prossimo_controllo"] = prossimi[0]
    return {"ok": True, "job": "archivio_letture_automatico", "tenants": studi, "totals": totali}


def registra_lettura_ocr_nell_archivio(job: Any, testo: str) -> int:
    """Il worker OCR, a testo pronto, alimenta l'archivio da solo (senza Flask): il motore documenti legge quel documento."""
    registro_path = _testo(getattr(job, "registro_path", ""))
    if not registro_path or not str(testo or "").strip():
        return 0
    try:
        import os

        from pct.fascicoli import GestioneFascicoli

        registro = registro_per_percorsi({"REGISTRO_LETTURE_DB": registro_path})
        tenant = _testo(getattr(job, "tenant_id", ""))
        oggetto = registro.oggetto(tenant, job.id_fasc, "documento", job.id_doc)
        if oggetto is None:
            oggetto = Oggetto(tipo="documento", oggetto_id=job.id_doc, nome=job.nome_doc, sha256_archivio=job.hash_sha256)
            registro.registra_inventario(tenant, job.id_fasc, [oggetto], tipi=())
        fascicolo: Any = {}
        db_path = _testo(os.getenv("PCT_FASCICOLI_DB", ""))
        if db_path:
            try:
                fascicolo = GestioneFascicoli(db_path=db_path, documents_dir=_testo(os.getenv("PCT_FASCICOLI_DOCS", str(Path(db_path).resolve().parent / "documenti"))), archive_dir=_testo(os.getenv("PCT_FASCICOLI_ARCH", str(Path(db_path).resolve().parent / "archivio")))).get(job.id_fasc) or {}
            except Exception:
                fascicolo = {}
        contesto = contesto_da_fascicolo(fascicolo)
        # Il fascicolo non serve solo al contesto delle date: senza, la lettura
        # non puo' verificare che una sentenza parli davvero di questo fascicolo
        # (RG e cliente) e i suoi importi finirebbero nella parte economica di
        # una pratica che non c'entra.
        metadata_ocr = {
            "fascicolo": fascicolo,
            "documento_id": _testo(getattr(job, "id_doc", "")),
            "fascicolo_id": _testo(getattr(job, "id_fasc", "")),
        }
        fatti = _attribuisci(
            leggi_testo(testo, origine="ocr", contesto=contesto, nome=job.nome_doc, metadata=metadata_ocr),
            oggetto,
            "documenti",
        )
        registro.registra_fatti(tenant, job.id_fasc, oggetto, "documenti", fatti, versione=VERSIONE_MOTORE_DOCUMENTI)
        registro.segna_letto(tenant, job.id_fasc, oggetto, LETTORE_DOCUMENTI, esito={"origine": "ocr", "fatti": len(fatti), "verificati": sum(1 for f in fatti if f.verifica == "verificata")}, versione=VERSIONE_MOTORE_DOCUMENTI)
        return len(fatti)
    except Exception as exc:
        logger.debug("Archivio non alimentato dal job OCR %s: %s", getattr(job, "id", ""), exc)
        return 0


__all__ = [
    "LETTORE_DOCUMENTI", "LETTORE_PEC", "avvia_lettura_in_background", "collaudo_lettore_payload", "date_note_fascicolo", "decidi_fatto", "fatti_fascicolo", "importi_noti_fascicolo",
    "leggi_fascicolo", "lettura_automatica_corrente", "lettura_automatica_per_tutti", "lettura_dopo_evento", "percorso_collaudo",
    "registra_lettura_ocr_nell_archivio", "stato_archivio_payload", "testi_documento",
]
