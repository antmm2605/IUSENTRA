"""Che genere di PEC è e quali allegati entrano nel fascicolo (regole pure, senza archivio).

Generi:

* ``ricevuta_deposito``: ricevute ed esiti del deposito telematico. Le lavora il flusso del deposito
  (``_upsert_pct_deposit_from_report``), che resta intoccato: qui non si salva nulla.
* ``ricevuta_notifica``: accettazione, avvenuta consegna (anche completa) o mancata consegna di una
  notificazione L. 53/1994. La prova è l'.eml della ricevuta (art. 3-bis L. 53/1994; art. 19-bis Provv.
  DGSIA 16/04/2014): si conserva intero; la copia dell'atto che contiene non è un documento nuovo.
* ``ricevuta_altra``: ricevute di PEC qualsiasi; non provano una notifica e restano nel presidio.
* ``notifica``: la PEC di notificazione (inviata o ricevuta): .eml intero più atti allegati.
* ``comunicazione``: ogni altra PEC collegata (cancelleria, colleghi, enti): gli atti allegati (anche dentro
  lo .zip) e, se viene da un ufficio giudiziario, l'.eml della comunicazione. ``IndiceBusta.xml`` accanto a
  ``Comunicazione.xml`` non la rende una ricevuta di deposito.

``VERSIONE`` cambia quando cambiano queste regole: i messaggi già completati tornano nel recupero.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from email import message_from_bytes, policy
from pathlib import PurePosixPath

#: 2: comunicazione dell'ufficio con IndiceBusta.xml non più scambiata per ricevuta di deposito; .eml della comunicazione.
VERSIONE = "2"
LIMITE_BYTE = 30 * 1024 * 1024
MASSIMO_MEMBRI_ZIP = 20

RICEVUTA_DEPOSITO = "ricevuta_deposito"
RICEVUTA_NOTIFICA = "ricevuta_notifica"
RICEVUTA_ALTRA = "ricevuta_altra"
NOTIFICA = "notifica"
COMUNICAZIONE = "comunicazione"

MOTIVI = {
    "daticert": "Dati di certificazione del gestore PEC (daticert.xml): parte della busta, non un documento",
    "involucro_postacert": "Involucro postacert.eml: il messaggio si conserva intero solo quando è prova di notifica",
    "firma_gestore": "Firma S/MIME del gestore PEC (smime.p7s)",
    "xml_tecnico": "XML tecnico già letto dal presidio (Comunicazione.xml, IndiceBusta.xml, DatiAtto.xml)",
    "formato_non_documentale": "Formato non documentale (immagini del corpo, file tecnici o sconosciuti)",
    "troppo_grande": "File oltre 30 MB: resta nella PEC, va acquisito a mano",
    "doppione_nella_pec": "Stesso file già presente nella stessa PEC",
    "allegato_di_ricevuta": "Copia dell'atto dentro la ricevuta: la prova è l'.eml della ricevuta",
    "ricevuta_deposito_telematico": "Ricevuta o esito del deposito telematico: la lavora il flusso del deposito",
    "ricevuta_non_di_notifica": "Ricevuta di una PEC che non è una notificazione L. 53/1994",
    "gia_nel_fascicolo": "Documento già presente nel fascicolo con la stessa impronta",
    "zip_illeggibile": "Archivio ZIP non leggibile",
}

_NOTIFICA_L53 = re.compile(r"notificazione\s+ai\s+sensi\s+della\s+legge\s+n\.?\s*53|\[notifica_id:", re.I)
_DEPOSITO = re.compile(
    r"deposito\s+telematico|esito\s+controlli|accettazione\s+deposito|consegna\s+deposito|rifiuto\s+deposito|"
    r"esito\s+intervento\s+cancelleria|accettazione\s+manuale",
    re.I,
)
_FILE_DEPOSITO = {"indicebusta.xml", "datiatto.xml", "atto.enc"}
# La comunicazione dell'ufficio porta Comunicazione.xml e, con gli allegati, anche IndiceBusta.xml (art. 21
# Specifiche tecniche, provv. DGSIA 07/08/2024, Allegati 4 e 8): l'indice da solo non fa di lei un deposito.
# Solo DatiAtto.xml o Atto.enc sono propri della busta di deposito (art. 14 delle stesse Specifiche).
_FILE_SOLO_DEPOSITO = {"datiatto.xml", "atto.enc"}
_XML_TECNICI = {"comunicazione.xml", "indicebusta.xml", "datiatto.xml", "segnatura.xml", "esitoatto.xml"}
_DOCUMENTALI = (".pdf", ".p7m", ".doc", ".docx", ".rtf", ".odt")


@dataclass(frozen=True)
class Allegato:
    nome: str
    contenuto: bytes
    sha256: str


@dataclass(frozen=True)
class Scarto:
    nome: str
    motivo: str
    sha256: str = ""


def _nome(valore: str) -> str:
    nome = PurePosixPath(str(valore or "").replace("\\", "/")).name.strip()
    return re.sub(r'[<>:"|?*\x00-\x1f]+', "_", nome)[-180:]


def genere_messaggio(oggetto: str, nomi_allegati: list[str], tipo_ricevuta: str) -> str:
    """Il genere della PEC dall'oggetto, dagli allegati e dal tipo di ricevuta già riconosciuto dal presidio."""
    testo = " ".join(str(oggetto or "").split())
    nomi = {_nome(nome).casefold() for nome in nomi_allegati}
    file_deposito = _FILE_SOLO_DEPOSITO if "comunicazione.xml" in nomi else _FILE_DEPOSITO
    if _DEPOSITO.search(testo) or nomi & file_deposito:
        return RICEVUTA_DEPOSITO
    if tipo_ricevuta:
        return RICEVUTA_NOTIFICA if _NOTIFICA_L53.search(testo) else RICEVUTA_ALTRA
    if _NOTIFICA_L53.search(testo):
        return NOTIFICA
    return COMUNICAZIONE


def involucri(raw: bytes) -> list[Scarto]:
    """Le PEC annidate (postacert.eml) non sono documenti: si registrano come scartate con il motivo."""
    try:
        messaggio = message_from_bytes(raw or b"", policy=policy.default)
    except Exception:
        return []
    out = []
    for parte in messaggio.walk():
        if parte.get_content_type() == "message/rfc822":
            out.append(Scarto(_nome(parte.get_filename() or "postacert.eml") or "postacert.eml", "involucro_postacert"))
    return out


def _motivo_scarto(nome: str, dati: bytes) -> str:
    basso = nome.casefold()
    if basso == "daticert.xml":
        return "daticert"
    if basso.endswith(".p7s") or basso.startswith("smime"):
        return "firma_gestore"
    if basso in _XML_TECNICI or basso.endswith(".xml"):
        return "xml_tecnico"
    if basso.endswith(".eml"):
        return "involucro_postacert"
    if not basso.endswith(_DOCUMENTALI) or not dati:
        return "formato_non_documentale"
    if len(dati) > LIMITE_BYTE:
        return "troppo_grande"
    return ""


def _membri_zip(nome_zip: str, dati: bytes) -> tuple[list[tuple[str, bytes]], list[Scarto]]:
    membri: list[tuple[str, bytes]] = []
    scarti: list[Scarto] = []
    try:
        with zipfile.ZipFile(io.BytesIO(dati)) as archivio:
            for membro in archivio.infolist()[:MASSIMO_MEMBRI_ZIP]:
                if membro.is_dir():
                    continue
                nome = _nome(membro.filename)
                if membro.file_size > LIMITE_BYTE:
                    scarti.append(Scarto(nome, "troppo_grande"))
                    continue
                membri.append((nome, archivio.read(membro)))
    except (zipfile.BadZipFile, OSError, ValueError, RuntimeError):
        scarti.append(Scarto(nome_zip, "zip_illeggibile", hashlib.sha256(dati).hexdigest()))
    return membri, scarti


def scegli_allegati(allegati: list[tuple[str, bytes]], *, genere: str) -> tuple[list[Allegato], list[Scarto]]:
    """Gli allegati da salvare e quelli scartati con il motivo; i doppioni della stessa PEC una volta sola."""
    salvare: list[Allegato] = []
    scarti: list[Scarto] = []
    viste: set[str] = set()
    coda = [(_nome(nome) or "allegato", bytes(dati or b"")) for nome, dati in allegati]
    while coda:
        nome, dati = coda.pop(0)
        impronta = hashlib.sha256(dati).hexdigest() if dati else ""
        if nome.casefold().endswith(".zip"):
            membri, scarti_zip = _membri_zip(nome, dati)
            coda.extend(membri)
            scarti.extend(scarti_zip)
            continue
        if genere in {RICEVUTA_NOTIFICA, RICEVUTA_ALTRA, RICEVUTA_DEPOSITO}:
            motivo = _motivo_scarto(nome, dati) or "allegato_di_ricevuta"
            scarti.append(Scarto(nome, motivo, impronta))
            continue
        motivo = _motivo_scarto(nome, dati)
        if not motivo and impronta in viste:
            motivo = "doppione_nella_pec"
        if motivo:
            scarti.append(Scarto(nome, motivo, impronta))
            continue
        viste.add(impronta)
        salvare.append(Allegato(nome, dati, impronta))
    return salvare, scarti


def conserva_eml(genere: str, *, da_ufficio: bool = False) -> bool:
    """L'.eml intero si conserva per la notificazione e le sue ricevute e per la comunicazione dell'ufficio.

    La comunicazione di cancelleria è il messaggio stesso (corpo e Comunicazione.xml, art. 21 Specifiche
    tecniche; art. 16, comma 4, D.L. 179/2012): senza l'.eml nel fascicolo resterebbe solo la copia degli allegati.
    """
    return genere in {NOTIFICA, RICEVUTA_NOTIFICA} or (genere == COMUNICAZIONE and da_ufficio)


__all__ = [
    "COMUNICAZIONE", "LIMITE_BYTE", "VERSIONE", "MOTIVI", "NOTIFICA", "RICEVUTA_ALTRA", "RICEVUTA_DEPOSITO", "RICEVUTA_NOTIFICA",
    "Allegato", "Scarto", "conserva_eml", "genere_messaggio", "involucri", "scegli_allegati",
]
