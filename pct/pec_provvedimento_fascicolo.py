"""Il provvedimento allegato alla comunicazione di cancelleria entra nel fascicolo collegato.

Verifica sulle PEC reali del 31/10/2026: in sei presìdi di notifica su sei la sentenza o il
decreto arrivati con la PEC della cancelleria non erano tra i documenti del fascicolo, e gli
obblighi di notifica lavoravano su copie di precedenti importati. Il provvedimento è la fonte
certa della causa: la comunicazione di cancelleria ne dà conoscenza legale alle parti
(art. 136 c.p.c.; art. 16, comma 4, D.L. 179/2012), quindi lo studio lo archivia nel fascicolo
con la provenienza (messaggio PEC, impronta SHA-256: art. 20 CAD; D.M. 44/2011 art. 3) e da lì
parte la lettura che alimenta termini, notifiche ed economia.

È una copia informativa: serve alla lettura (contenuto, parti, spese) ma non è la copia da
notificare. Quella certificata è la copia informatica scaricata dal Portale dei Servizi Telematici,
con i dati del deposito; su di essa si fanno notifica e attestazione di conformità (L. 53/1994,
art. 3-bis; art. 16-bis, comma 9-bis, D.L. 179/2012). Per questo la fonte del documento è
«PEC_CANCELLERIA» e non «PORTALE_TELEMATICO»: i presìdi di notifica continuano a chiedere
l'originale dal portale.

Solo i file del giudice: PDF (anche firmati .p7m) allegati o dentro lo zip della comunicazione.
Non si archiviano i file tecnici (Comunicazione.xml, daticert.xml, IndiceBusta.xml, firme .p7s).
Il download dal portale resta dell'avvocato: qui si usa solo ciò che la PEC ha già consegnato.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from email import message_from_bytes, policy
from typing import Any

LIMITE_BYTE = 30 * 1024 * 1024
_PROVVEDIMENTO = re.compile(r"\.pdf(?:\.p7m)?$", re.IGNORECASE)
_TECNICI = re.compile(r"(?:comunicazione|daticert|indicebusta|postacert|datiatto)\.(?:xml|eml)|\.p7s$|smime", re.IGNORECASE)


def _nome_pulito(nome: str) -> str:
    return re.sub(r"[\\/]+", "_", str(nome or "").strip())[-180:] or "provvedimento.pdf"


def provvedimenti_allegati(raw: bytes) -> list[tuple[str, bytes]]:
    """(nome, contenuto) dei PDF del giudice nella PEC, anche dentro il messaggio interno e lo zip."""
    from pct.pec_pipeline import extract_message_parts

    trovati: dict[str, tuple[str, bytes]] = {}
    try:
        _testo, _html, allegati = extract_message_parts(message_from_bytes(raw or b"", policy=policy.default))
    except Exception:
        return []
    for allegato in allegati:
        nome = str(getattr(allegato, "filename", "") or "")
        dati = bytes(getattr(allegato, "data", b"") or b"")
        if not dati or _TECNICI.search(nome):
            continue
        if _PROVVEDIMENTO.search(nome) and len(dati) <= LIMITE_BYTE:
            trovati.setdefault(hashlib.sha256(dati).hexdigest(), (_nome_pulito(nome), dati))
        elif nome.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(dati)) as archivio:
                    for membro in archivio.infolist()[:20]:
                        if membro.is_dir() or not _PROVVEDIMENTO.search(membro.filename) or _TECNICI.search(membro.filename):
                            continue
                        if membro.file_size > LIMITE_BYTE:
                            continue
                        contenuto = archivio.read(membro)
                        trovati.setdefault(hashlib.sha256(contenuto).hexdigest(), (_nome_pulito(membro.filename.rsplit("/", 1)[-1]), contenuto))
            except (zipfile.BadZipFile, OSError, ValueError):
                continue
    return list(trovati.values())


def tipo_documento(kind: str, evento: str) -> Any:
    """Tipo del documento nel fascicolo dal genere di comunicazione di cancelleria."""
    from pct.fascicoli import TipoDocumento

    testo = f"{kind} {evento}".lower()
    if "sentenz" in testo:
        return TipoDocumento.SENTENZA
    if "ordinanz" in testo:
        return TipoDocumento.ORDINANZA
    if "decret" in testo:
        return TipoDocumento.DECRETO
    if "verbal" in testo:
        return TipoDocumento.VERBALE
    return TipoDocumento.ATTO_GIUDIZIARIO


__all__ = ["LIMITE_BYTE", "provvedimenti_allegati", "tipo_documento"]
