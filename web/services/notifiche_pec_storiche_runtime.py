"""Lavoro in sfondo: verifica le ricevute PEC storiche e porta nel registro le notifiche provate.

Per ogni fascicolo con messaggi PEC (.eml) tra i documenti: verifica le ricevute del gestore una per una
(``pct/ricevute_pec_gestore.py``), cerca nella casella dello studio il messaggio inviato (cartella Inviati) e
le ricevute della stessa spedizione, correla tutto con la relata e l'atto (``pct/notifiche_pec_storiche_prova.py``)
e scrive i casi provati nel registro delle notifiche (``pct/registro_notifiche_storiche.py``), dove li trova
il ragionamento della causa. Le ricevute non verificate restano tali, con il motivo.

Bassa priorità e letture incrementali (registro delle letture, lettore «ricevute_pec_gestore»): un fascicolo con
inventario invariato e senza messaggi nuovi della casella per le sue spedizioni non si riesamina; una ricevuta
con la stessa impronta già verificata non si riverifica; con il carico della macchina alto il giro si ferma.
Nessun invio, nessuna scrittura nei documenti.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Callable

from pct.notifica_atto_l53 import e_notificazione_l53
from pct.notifiche_pec_storiche_prova import Invio, LetturaRelata, prova_spedizioni
from pct.pec_ricevute_archivio import tipo_eml_storico
from pct.registro_notifiche_storiche import assicura_schema, esiti_salvati, registra_esiti, registra_spedizioni
from pct.ricevute_pec_gestore import VERSIONE, EsitoRicevuta, esito_da_dizionario, verifica_ricevuta_gestore

logger = logging.getLogger(__name__)
LETTORE = "ricevute_pec_gestore"
_PARSER = BytesParser(policy=policy.default)
_PREFISSO_RICEVUTA = re.compile(r"^\s*(ACCETTAZIONE|CONSEGNA|AVVENUTA CONSEGNA)\s*:", re.IGNORECASE)
_MASSIMO_EML = 32 * 1024 * 1024
_CACHE_CASELLA: dict[str, tuple[tuple[int, int], "IndiceCasella"]] = {}


def _id(valore: Any) -> str:
    return re.sub(r"[\s<>]+", "", str(valore or "")).casefold()


@dataclass
class IndiceCasella:
    """Messaggi della casella utili alle notifiche: inviati L. 53/1994 e ricevute, per identificativo del messaggio."""

    cartella: Path | None = None
    inviati: dict[str, list[dict]] = field(default_factory=dict)
    ricevute: dict[str, list[dict]] = field(default_factory=dict)

    def raw(self, voce: dict) -> bytes:
        from pct.document_crypto import decrypt_doc

        if self.cartella is None:
            return b""
        percorso = (self.cartella / str(voce.get("eml_file") or "")).resolve()
        if self.cartella.resolve() not in percorso.parents or not percorso.is_file() or percorso.stat().st_size > _MASSIMO_EML:
            return b""
        return decrypt_doc(percorso.read_bytes())


def indice_casella(percorso_casella: str | Path | None) -> IndiceCasella:
    """Indice della casella (``casella.json``), ricostruito solo quando il file cambia."""
    if not percorso_casella:
        return IndiceCasella()
    percorso = Path(percorso_casella)
    try:
        stato = percorso.stat()
    except OSError:
        return IndiceCasella()
    firma = (int(stato.st_mtime_ns), int(stato.st_size))
    salvato = _CACHE_CASELLA.get(str(percorso))
    if salvato and salvato[0] == firma:
        return salvato[1]
    indice = IndiceCasella(cartella=percorso.parent)
    try:
        messaggi = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return indice
    for voce in (messaggi.values() if isinstance(messaggi, dict) else messaggi or []):
        if not isinstance(voce, dict) or not voce.get("eml_file"):
            continue
        oggetto = str(voce.get("oggetto") or "")
        if not e_notificazione_l53(oggetto):
            continue
        if str(voce.get("cartella") or "").upper() == "INVIATI" and not _PREFISSO_RICEVUTA.match(oggetto):
            indice.inviati.setdefault(_id(voce.get("message_id")), []).append(voce)
        elif _PREFISSO_RICEVUTA.match(oggetto):
            try:
                intestazione = _PARSER.parsebytes(indice.raw(voce)[:65536], headersonly=True)
            except Exception:
                continue
            riferimento = _id(intestazione["X-Riferimento-Message-ID"])
            if riferimento:
                indice.ricevute.setdefault(riferimento, []).append(voce)
    _CACHE_CASELLA[str(percorso)] = (firma, indice)
    return indice


def leggi_relata_file(data: bytes, nome: str) -> LetturaRelata:
    """Testo e firma della relata: PAdES verificata da pyHanko, CAdES da OpenSSL; senza firma integra, nessuna prova."""
    from pct.firma import analizza_firma_documento

    contenuto, integra, firme = data, False, analizza_firma_documento(data, nome)
    if nome.casefold().endswith(".p7m"):
        from pct.firme_cades import inspect_signed_document_bytes

        esame = inspect_signed_document_bytes(source_name=nome, data=data)
        integra, contenuto = bool(esame.status.signature_verified and esame.payload_bytes), esame.payload_bytes or b""
    else:
        integra = bool(firme) and all(f.get("content_digest_verified") and f.get("cryptographic_signature_verified") for f in firme)
    codici = {str(f.get("codice_fiscale") or "").upper() for f in firme if f.get("codice_fiscale")}
    testo = ""
    if contenuto[:4] == b"%PDF":
        import fitz

        with fitz.open(stream=contenuto, filetype="pdf") as documento:
            testo = "".join(pagina.get_text() for pagina in documento)
    return LetturaRelata(testo, integra and len(codici) == 1, next(iter(codici)) if len(codici) == 1 else "")


def _casella_studio() -> str:
    from flask import current_app

    fabbrica = (current_app.extensions.get("core_runtime") or {}).get("get_config_studio")
    config = fabbrica().config if callable(fabbrica) else None
    return str(getattr(getattr(config, "pec", None), "indirizzo", "") or "").strip()


def _impronta_fascicolo(inventario: str, casella: str, voci_casella: list[dict]) -> str:
    righe = [VERSIONE, inventario, casella.casefold(), *sorted(f"{v.get('id')}:{v.get('eml_sha256')}" for v in voci_casella)]
    return hashlib.sha256("|".join(righe).encode()).hexdigest()


def esamina_fascicolo(fascicolo: Any, *, conn: Any, tenant: str, casella: str, registro: Any, indice: IndiceCasella,
                      leggi_bytes: Callable[[str, Any], bytes], verifica: Callable[..., EsitoRicevuta] = verifica_ricevuta_gestore,
                      lettore_relata=leggi_relata_file) -> dict[str, Any]:
    """Esamina un fascicolo; restituisce i conteggi. Scrive solo nel registro delle notifiche e negli esiti."""
    from pct.registro_letture.modello import impronta_inventario
    from web.services.archivio_letture_runtime import _formato_documento

    fascicolo_id = str(fascicolo.id)
    oggetti = [o for o in registro.oggetti(tenant, fascicolo_id) if o.tipo == "documento"]
    impronte = {o.oggetto_id: str(o.sha256 or "").lower() for o in oggetti}
    for documento in fascicolo.documenti:
        impronte.setdefault(str(documento.id), str(getattr(documento, "hash_sha256", "") or "").lower())
    eml = [d for d in fascicolo.documenti if _formato_documento(d) == ".eml"]
    if not eml:
        return {"esaminato": False}
    assicura_schema(conn)
    salvati = esiti_salvati(conn, tenant=tenant, fascicolo_id=fascicolo_id)
    msgid_noti = {_id(d.get("msgid")) for d in salvati.values() if d.get("msgid")}
    voci_casella = [v for m in msgid_noti for v in indice.inviati.get(m, []) + indice.ricevute.get(m, [])]
    inventario = impronta_inventario(oggetti)
    impronta = _impronta_fascicolo(inventario, casella, voci_casella)
    riga = registro.impronta_fascicolo(tenant, fascicolo_id, LETTORE)
    precedente = json.loads(str((riga or {}).get("esito_json") or "{}")).get("impronta_completa") if riga else ""
    if registro.fascicolo_invariato(tenant, fascicolo_id, LETTORE, inventario, versione=VERSIONE) and precedente == impronta:
        return {"esaminato": False, "invariato": True}
    esiti: list[EsitoRicevuta] = []
    invii: list[Invio] = []
    da_ripetere = False

    def esamina(riferimento: str, sha: str, leggi: Callable[[], bytes], fonte: str) -> None:
        nonlocal da_ripetere
        noto = salvati.get(sha) if sha else None
        if (noto and noto.get("_versione") == VERSIONE and noto.get("riferimento") == riferimento
                and not noto.get("ripetibile") and noto.get("tipo_eml") != "invio"):
            # Stessa impronta, stessa versione del verificatore: l'esito vale, il file non si rilegge.
            esiti.append(esito_da_dizionario(noto))
            return
        raw = leggi()
        tipo = tipo_eml_storico(raw)
        if tipo == "invio":
            invii.append(Invio(riferimento, raw, fonte))
            messaggio = _PARSER.parsebytes(raw[:65536], headersonly=True)
            esiti.append(EsitoRicevuta(riferimento, hashlib.sha256(raw).hexdigest(), "non_ricevuta",
                                       firmatario={"_tipo_eml": "invio", "_msgid": str(messaggio["Message-ID"] or "")}))
            return
        if tipo != "ricevuta":
            esiti.append(EsitoRicevuta(riferimento, hashlib.sha256(raw).hexdigest(), "non_ricevuta", firmatario={"_tipo_eml": ""}))
            return
        esito = verifica(raw, riferimento=riferimento, casella_studio=casella)
        da_ripetere = da_ripetere or esito.ripetibile
        esiti.append(esito)

    for documento in eml:
        esamina(str(documento.id), impronte.get(str(documento.id), ""), lambda d=documento: leggi_bytes(fascicolo_id, d), "documento")
    msgid = {_id(e.ricevuta.message_id) for e in esiti if e.ricevuta} | {
        _id(e.firmatario.get("_msgid")) for e in esiti if e.firmatario.get("_msgid")}
    for m in sorted(x for x in msgid if x):
        for voce in indice.inviati.get(m, []):
            raw = indice.raw(voce)
            if raw:
                invii.append(Invio(f"casella:{voce.get('id')}", raw, "casella"))
        for voce in indice.ricevute.get(m, []):
            esamina(f"casella:{voce.get('id')}", str(voce.get("eml_sha256") or "").lower(), lambda v=voce: indice.raw(v), "casella")
    spedizioni = prova_spedizioni(esiti, invii, casella_studio=casella, documenti=impronte, leggi_relata_file=lettore_relata)
    dettagli = {e.riferimento: e.come_dizionario() for e in esiti if e.ricevuta}
    righe = []
    for e in esiti:
        voce = e.come_dizionario()
        voce["tipo_eml"] = e.firmatario.get("_tipo_eml", "ricevuta")
        voce["msgid"] = voce["msgid"] or e.firmatario.get("_msgid", "")
        voce["ripetibile"] = e.ripetibile
        if e.codice == "non_ricevuta":
            voce["motivo"] = ""
        righe.append(voce)
    conteggio = registra_spedizioni(conn, tenant=tenant, fascicolo_id=fascicolo_id, casella=casella,
                                    spedizioni=spedizioni, ricevute=dettagli)
    registra_esiti(conn, tenant=tenant, fascicolo_id=fascicolo_id, versione=VERSIONE, ricevute=righe, spedizioni=spedizioni)
    conn.commit()
    # Le voci della casella per queste spedizioni entrano nell'impronta del giro: arrivi nuovi riaprono il fascicolo.
    voci_casella = [v for m in msgid for v in indice.inviati.get(m, []) + indice.ricevute.get(m, [])]
    registro.segna_fascicolo(
        tenant, fascicolo_id, LETTORE, impronta=inventario, oggetti_totali=len(eml), oggetti_letti=len(esiti),
        stato="parziale" if da_ripetere else "completa", versione=VERSIONE,
        esito={"impronta_completa": "" if da_ripetere else _impronta_fascicolo(inventario, casella, voci_casella),
               "provate": sum(1 for s in spedizioni if s.provata), "dubbi": sum(1 for s in spedizioni if not s.provata)},
    )
    if conteggio["creati"] or conteggio["da_rivedere"]:
        _ricalcola(fascicolo_id)
    return {"esaminato": True, **conteggio,
            "ricevute": sum(1 for e in esiti if e.codice != "non_ricevuta"),
            "ricevute_verificate": sum(1 for e in esiti if e.verificata),
            "provate": sum(1 for s in spedizioni if s.provata), "dubbi": sum(1 for s in spedizioni if not s.provata)}


def _ricalcola(fascicolo_id: str) -> None:
    try:
        from web.services.lettura_cache import invalida_lettura
        from web.services.pannelli_pronti_runtime import segnala_scrittura_fascicolo

        invalida_lettura(fascicolo_id)
        segnala_scrittura_fascicolo(fascicolo_id)
    except Exception as exc:
        logger.info("Pannelli non segnalati dopo le notifiche storiche di %s: %s", fascicolo_id, exc)


def _carico_alto() -> bool:
    try:
        return os.getloadavg()[0] > 1.5 * (os.cpu_count() or 1)
    except OSError:
        return False


def giro(app, *, limite: int = 30, secondi: float = 240.0) -> dict[str, int]:
    """Un giro per studio, a piccoli lotti: si ferma a ``limite`` fascicoli esaminati, al tempo o col carico alto."""
    from flask import g

    from web.helpers import _studio_db, get_fascicoli
    from web.services.archivio_letture_runtime import _bytes_documento
    from web.services.bozze_passi_runtime import _contesto_studio
    from web.services.notification_presidia_runtime import _tenant_id
    from web.services.pannelli_pronti_sfondo import studi
    from web.services.registro_letture_runtime import registro_corrente

    totale = {"fascicoli": 0, "invariati": 0, "creati": 0, "da_rivedere": 0, "provate": 0, "dubbi": 0, "errori": 0, "fermato": 0}
    inizio = time.monotonic()
    for owner, _data_paths in studi(app):
        with _contesto_studio(app, owner):
            casella = _casella_studio()
            db = _studio_db("FASCICOLI_DB")
            if not casella or db is None:
                continue
            tenant = _tenant_id()
            registro = registro_corrente()
            indice = indice_casella((getattr(g, "data_paths", {}) or {}).get("EMAIL_CASELLA_DB"))
            for fascicolo in get_fascicoli().tutti(archiviati=True):
                if totale["fascicoli"] >= limite or time.monotonic() - inizio > secondi or _carico_alto():
                    totale["fermato"] = 1
                    return totale
                try:
                    esito = esamina_fascicolo(fascicolo, conn=db.conn, tenant=tenant, casella=casella, registro=registro,
                                              indice=indice, leggi_bytes=_bytes_documento)
                except Exception as exc:  # un fascicolo non ferma gli altri
                    logger.warning("Notifiche PEC storiche non verificate per %s: %s", getattr(fascicolo, "id", "?"), exc)
                    totale["errori"] += 1
                    try:
                        db.conn.rollback()
                    except Exception:
                        pass
                    continue
                if esito.get("invariato"):
                    totale["invariati"] += 1
                if not esito.get("esaminato"):
                    continue
                totale["fascicoli"] += 1
                for chiave in ("creati", "da_rivedere", "provate", "dubbi"):
                    totale[chiave] += int(esito.get(chiave) or 0)
    return totale


__all__ = ["IndiceCasella", "LETTORE", "esamina_fascicolo", "giro", "indice_casella", "leggi_relata_file"]
