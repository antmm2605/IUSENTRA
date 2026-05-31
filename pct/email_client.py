"""
Client email completo per IUSENTRA — ricezione IMAP, gestione casella, auto-esito PCT.

Funzionalità:
  - Ricezione email via IMAP (ordinaria + PEC)
  - Storage persistente su JSON
  - Cestino (soft-delete)
  - Auto-riconoscimento risposte PST/PCT e aggiornamento EsitoDepositoPCT
  - Sync bidirezionale (inviati da messaggi.py + ricevuti da IMAP)
"""

from __future__ import annotations

import email
import imaplib
import os
import json
import re
import socket
import uuid
import shutil
import unicodedata
import zipfile
from email import policy
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

from pct.email_attachments import content_sha256, files_are_same_content
from pct.imap_runtime import (
    describe_imap_connection_error,
    resolve_imap_timeout_seconds,
    run_imap_runtime_operation,
)


# ------------------------------------------------------------------ Enums / cost.

class CartellaEmail(str):
    INBOX    = "INBOX"
    INVIATI  = "INVIATI"
    CESTINO  = "CESTINO"
    BOZZE    = "BOZZE"


class StatoEmail(str):
    NON_LETTA = "NON_LETTA"
    LETTA     = "LETTA"
    CESTINO   = "CESTINO"
    BOZZA     = "BOZZA"


# Pattern per riconoscere risposte PST/PCT (D.M. 44/2011 art. 15)
_PATTERN_PST = [
    re.compile(r"ACCETTAZIONE.*DEPOSITO", re.I),
    re.compile(r"CONSEGNA.*DEPOSITO", re.I),
    re.compile(r"AVVISO.*CANCELLERIA", re.I),
    re.compile(r"RIFIUTO.*DEPOSITO", re.I),
    re.compile(r"ESITO.*DEPOSITO\s+TELEMATICO", re.I),
    re.compile(r"DEPOSITO TELEMATICO.*ACCETTATO", re.I),
    re.compile(r"DEPOSITO TELEMATICO.*RIFIUTATO", re.I),
    re.compile(r"ANOMALIA.*DEPOSITO", re.I),
    re.compile(r"WARN.*CONTROLLI", re.I),
]

_MAPPA_STATO_PST = {
    "ACCETTAZIONE":          "ACCETTATO_PEC",
    "CONSEGNA":              "CONSEGNATO",
    "AVVISO.*CANCELLERIA":   "ACCETTATO_CANCELLERIA",
    "RIFIUTO":               "RIFIUTATO_CANCELLERIA",
    "RIFIUTATO":             "RIFIUTATO_CANCELLERIA",
    "ACCETTATO":             "ACCETTATO_CANCELLERIA",
    "WARN|ANOMALIA":         "WARN_CONTROLLI",
    "ERRORE":                "ERRORE_CONTROLLI",
}

_RE_RG_PCT = re.compile(
    r"\b(?:N\.?\s*CAUSA\s*)?(?:R\.?\s*G\.?|REGISTRO\s+GENERALE)(?:\s*N\.?\s*R\.?)?\s*[:\-]?\s*(\d+)\s*/\s*(\d{4})\b",
    re.IGNORECASE,
)
_RE_SAFE_FILENAME = re.compile(r'[^A-Za-z0-9._()\- ]+')
_STATI_PCT_ORDINE = {
    "INVIATO": 0,
    "ACCETTATO_PEC": 1,
    "CONSEGNATO": 2,
    "WARN_CONTROLLI": 3,
    "ERRORE_CONTROLLI": 3,
    "ACCETTATO_CANCELLERIA": 4,
    "RIFIUTATO_CANCELLERIA": 4,
    "ERRORE": 4,
}

_SENT_FOLDER_HINTS = ("sent", "inviat", "spedit", "posta inviata", "sent items")
_TRASH_FOLDER_HINTS = ("trash", "deleted", "eliminat", "cestin")
_DRAFT_FOLDER_HINTS = ("draft", "bozz")
_NON_SYNC_DISCOVERY_FOLDER_HINTS = (
    "all mail",
    "tutti i messaggi",
    "archive",
    "archivio",
    "archiviati",
    "spam",
    "junk",
    "indesiderat",
)
_IMAP_TIMEOUT_ERROR_HINTS = ("cannot read from timed out object", "timed out", "timeout")


def cartelle_imap_standard() -> list[str]:
    """Cartelle IMAP comuni da tentare senza rendere la sync aggressiva."""
    return [
        "INBOX",
        "Sent",
        "Sent Items",
        "INVIATI",
        "Spedite",
        "SPEDITE",
        "Posta inviata",
        "INBOX/Spedite",
        "INBOX/Posta Inviata",
        "INBOX.Sent",
        "INBOX.Sent Items",
        "Trash",
        "Deleted Items",
        "CESTINO",
        "Posta eliminata",
        "INBOX/Trash",
        "INBOX/Posta eliminata",
        "INBOX.Trash",
        "INBOX.Deleted Items",
        "INBOX/Draft",
        "INBOX/Posta Indesiderata",
    ]


def _cartella_interna_da_imap(cartella_imap: str) -> str:
    raw = str(cartella_imap or "").strip().lower()
    if any(hint in raw for hint in _SENT_FOLDER_HINTS):
        return CartellaEmail.INVIATI
    if any(hint in raw for hint in _TRASH_FOLDER_HINTS):
        return CartellaEmail.CESTINO
    if any(hint in raw for hint in _DRAFT_FOLDER_HINTS):
        return CartellaEmail.BOZZE
    return CartellaEmail.INBOX


def _stato_iniziale_da_cartella(cartella_interna: str) -> str:
    if cartella_interna == CartellaEmail.CESTINO:
        return StatoEmail.CESTINO
    if cartella_interna == CartellaEmail.INVIATI:
        return StatoEmail.LETTA
    if cartella_interna == CartellaEmail.BOZZE:
        return StatoEmail.BOZZA
    return StatoEmail.NON_LETTA


# ------------------------------------------------------------------ Dataclass

@dataclass
class EmailRicevuta:
    """Rappresenta una singola email ricevuta."""

    id: str
    cartella: str = CartellaEmail.INBOX
    stato: str    = StatoEmail.NON_LETTA

    # Header
    mittente: str       = ""
    mittente_nome: str  = ""
    destinatari: str    = ""
    oggetto: str        = ""
    data: str           = ""      # ISO datetime

    # Corpo
    corpo_testo: str    = ""
    corpo_html: str     = ""

    # Allegati PEC salvati localmente con percorso relativo protetto.
    allegati: List[Dict] = field(default_factory=list)  # [{nome, size, mime}]

    # Metadati
    message_id: str     = ""       # Message-ID header originale
    uid_imap: str       = ""       # UID IMAP per evitare duplicati
    origine: str        = "IMAP"   # IMAP | INVIATA | BOZZA
    eml_file: str       = ""       # percorso relativo dell'EML originale salvato
    eml_sha256: str     = ""       # impronta SHA-256 dell'EML originale

    # Correlazione PCT
    id_deposito_pct: str = ""      # se riconosciuta come risposta PST
    stato_pct: str       = ""      # nuovo stato PCT rilevato
    auto_registrata: bool = False  # se già aggiornata nel fascicolo

    # Audit
    ricevuta_il: str = field(default_factory=lambda: datetime.now().isoformat())
    letta_il: str    = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EmailRicevuta":
        d = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**d)

    @property
    def timestamp(self) -> str:
        return self.data or self.ricevuta_il

    @property
    def anteprima(self) -> str:
        testo = self.corpo_testo or re.sub(r"<[^>]+>", " ", self.corpo_html)
        testo = " ".join(testo.split())
        return testo[:120] + ("…" if len(testo) > 120 else "")

    @property
    def e_pst(self) -> bool:
        """True se l'email è una risposta del Portale Servizi Telematici."""
        return bool(self.stato_pct)


# ------------------------------------------------------------------ Gestore

class GestioneEmailRicevute:
    """
    Gestisce la casella email in IUSENTRA: ricezione, storage, ricerca.

    Storage: JSON flat file (stessa strategia del resto di IUSENTRA).
    """

    def __init__(self, db_path: str = "./email/casella.json"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.attachments_dir = self.db_path.parent / "allegati"
        self.attachments_dir.mkdir(parents=True, exist_ok=True)
        self.attachment_archive_path = self.attachments_dir / "archivio-allegati.zip"
        self.archive_storage_enabled = str(
            os.getenv("IUSENTRA_EMAIL_ATTACHMENT_STORAGE", "")
            or os.getenv("PCT_EMAIL_ATTACHMENT_STORAGE", "")
        ).strip().lower() in {"1", "true", "yes", "on", "archive", "zip", "zip-deflate"}
        self._cache: Optional[Dict[str, EmailRicevuta]] = None

    # ---- Storage ----

    def _carica(self) -> Dict[str, EmailRicevuta]:
        if self._cache is not None:
            return self._cache
        if not self.db_path.exists():
            self._cache = {}
            return self._cache
        try:
            data = json.loads(self.db_path.read_text(encoding="utf-8"))
            self._cache = {k: EmailRicevuta.from_dict(v) for k, v in data.items()}
        except Exception:
            self._cache = {}
        return self._cache

    def _salva(self) -> None:
        db = self._carica()
        self.db_path.write_text(
            json.dumps({k: v.to_dict() for k, v in db.items()},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _invalida(self) -> None:
        self._cache = None

    @staticmethod
    def _sanifica_nome_allegato(nome: str, fallback: str = "allegato.bin") -> str:
        nome_pulito = Path(str(nome or fallback)).name.strip() or fallback
        nome_pulito = _RE_SAFE_FILENAME.sub("_", nome_pulito)
        nome_pulito = re.sub(r"\s+", " ", nome_pulito).strip(" .")
        return nome_pulito or fallback

    def _salva_allegato(self, email_id: str, nome: str, contenuto: bytes) -> dict:
        if self.archive_storage_enabled:
            return self._salva_allegato_archivio(nome, contenuto)

        cartella_email = self.attachments_dir / email_id
        cartella_email.mkdir(parents=True, exist_ok=True)

        nome_pulito = self._sanifica_nome_allegato(nome)
        sha256 = content_sha256(contenuto)
        target = cartella_email / nome_pulito
        stem = target.stem
        suffix = target.suffix
        idx = 1
        while target.exists():
            if files_are_same_content(target, contenuto, expected_sha256=sha256):
                return {
                    "percorso_rel": str(target.relative_to(self.attachments_dir)).replace("\\", "/"),
                    "nome_file": target.name,
                    "sha256": sha256,
                }
            target = cartella_email / f"{stem}_{idx}{suffix}"
            idx += 1

        target.write_bytes(contenuto)
        return {
            "percorso_rel": str(target.relative_to(self.attachments_dir)).replace("\\", "/"),
            "nome_file": target.name,
            "sha256": sha256,
        }

    def _salva_eml_originale(self, email_id: str, contenuto: bytes) -> dict[str, str]:
        if not contenuto:
            return {}
        folder = self.db_path.parent / "eml"
        folder.mkdir(parents=True, exist_ok=True)
        safe_id = self._sanifica_nome_allegato(email_id, fallback=uuid.uuid4().hex)
        safe_id = re.sub(r"\.eml$", "", safe_id, flags=re.IGNORECASE)
        target = folder / f"{safe_id}.eml"
        sha256 = content_sha256(contenuto)
        if not target.exists() or not files_are_same_content(target, contenuto, expected_sha256=sha256):
            target.write_bytes(contenuto)
        rel = target.relative_to(self.db_path.parent)
        return {"eml_file": str(rel).replace("\\", "/"), "eml_sha256": sha256}

    def _archive_member_for_sha(self, sha256: str) -> str:
        safe_hash = re.sub(r"[^a-fA-F0-9]", "", str(sha256 or "").lower())
        if len(safe_hash) < 64:
            safe_hash = content_sha256(safe_hash.encode("utf-8"))
        return f"{safe_hash[:2]}/{safe_hash}"

    def _quarantena_archivio_allegati_corrotto(self) -> None:
        if not self.attachment_archive_path.exists():
            return
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        quarantine = self.attachment_archive_path.with_name(
            f"{self.attachment_archive_path.stem}.corrotto-{timestamp}{self.attachment_archive_path.suffix}"
        )
        idx = 1
        while quarantine.exists():
            quarantine = self.attachment_archive_path.with_name(
                f"{self.attachment_archive_path.stem}.corrotto-{timestamp}-{idx}{self.attachment_archive_path.suffix}"
            )
            idx += 1
        try:
            self.attachment_archive_path.replace(quarantine)
        except OSError:
            return

    def _archivio_members(self) -> set[str]:
        if not self.attachment_archive_path.exists():
            return set()
        try:
            with zipfile.ZipFile(self.attachment_archive_path, "r") as archive:
                return set(archive.namelist())
        except zipfile.BadZipFile:
            self._quarantena_archivio_allegati_corrotto()
            return set()

    def _salva_allegato_archivio(self, nome: str, contenuto: bytes) -> dict:
        nome_pulito = self._sanifica_nome_allegato(nome)
        sha256 = content_sha256(contenuto)
        member = self._archive_member_for_sha(sha256)
        self.attachment_archive_path.parent.mkdir(parents=True, exist_ok=True)
        exists = member in self._archivio_members()
        if not exists:
            with zipfile.ZipFile(
                self.attachment_archive_path,
                "a",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as archive:
                archive.writestr(member, contenuto)
        return {
            "archivio_rel": self.attachment_archive_path.relative_to(self.attachments_dir).as_posix(),
            "archivio_membro": member,
            "archivio_formato": "zip-deflate",
            "nome_file": nome_pulito,
            "sha256": sha256,
            "size": len(contenuto),
        }

    def percorso_allegato(self, em: EmailRicevuta, indice_allegato: int) -> Path | None:
        allegati = list(getattr(em, "allegati", []) or [])
        if indice_allegato < 0 or indice_allegato >= len(allegati):
            return None
        info = allegati[indice_allegato] or {}
        percorso_rel = str(info.get("percorso_rel", "") or "").strip().replace("\\", "/")
        if not percorso_rel:
            return None
        percorso = (self.attachments_dir / Path(percorso_rel)).resolve()
        root = self.attachments_dir.resolve()
        try:
            percorso.relative_to(root)
        except ValueError:
            return None
        if not percorso.exists() or not percorso.is_file():
            return None
        return percorso

    def _percorso_allegato_da_info(self, info: dict) -> Path | None:
        percorso_rel = str((info or {}).get("percorso_rel", "") or "").strip().replace("\\", "/")
        if not percorso_rel:
            return None
        percorso = (self.attachments_dir / Path(percorso_rel)).resolve()
        root = self.attachments_dir.resolve()
        try:
            percorso.relative_to(root)
        except ValueError:
            return None
        if not percorso.exists() or not percorso.is_file():
            return None
        return percorso

    def _archivio_allegato_da_info(self, info: dict) -> tuple[Path, str] | None:
        archivio_rel = str((info or {}).get("archivio_rel", "") or "").strip().replace("\\", "/")
        member = str((info or {}).get("archivio_membro", "") or "").strip().replace("\\", "/")
        if not archivio_rel or not member or member.startswith("/") or ".." in Path(member).parts:
            return None
        archivio = (self.attachments_dir / Path(archivio_rel)).resolve()
        root = self.attachments_dir.resolve()
        try:
            archivio.relative_to(root)
        except ValueError:
            return None
        if not archivio.exists() or not archivio.is_file() or archivio.suffix.lower() != ".zip":
            return None
        return archivio, member

    def _allegato_archiviato(self, info: dict) -> bool:
        archive_info = self._archivio_allegato_da_info(info)
        if not archive_info:
            return False
        archivio, member = archive_info
        try:
            with zipfile.ZipFile(archivio, "r") as archive:
                archive.getinfo(member)
            return True
        except (KeyError, OSError, zipfile.BadZipFile):
            return False

    def _allegato_salvato(self, info: dict) -> bool:
        return self._percorso_allegato_da_info(info) is not None or self._allegato_archiviato(info)

    def allegato_disponibile(self, em: EmailRicevuta, indice_allegato: int) -> bool:
        allegati = list(getattr(em, "allegati", []) or [])
        if indice_allegato < 0 or indice_allegato >= len(allegati):
            return False
        info = allegati[indice_allegato] or {}
        return self._allegato_salvato(info)

    def leggi_allegato(self, em: EmailRicevuta, indice_allegato: int) -> bytes | None:
        allegati = list(getattr(em, "allegati", []) or [])
        if indice_allegato < 0 or indice_allegato >= len(allegati):
            return None
        info = allegati[indice_allegato] or {}
        percorso = self._percorso_allegato_da_info(info)
        if percorso:
            try:
                return percorso.read_bytes()
            except OSError:
                return None
        archive_info = self._archivio_allegato_da_info(info)
        if not archive_info:
            return None
        archivio, member = archive_info
        try:
            with zipfile.ZipFile(archivio, "r") as archive:
                return archive.read(member)
        except (KeyError, OSError, zipfile.BadZipFile):
            return None

    def comprimi_allegati(self, *, apply: bool = False) -> dict[str, Any]:
        db = self._carica()
        loose_items: list[tuple[EmailRicevuta, dict, Path, str]] = []
        loose_bytes = 0
        for em in db.values():
            for info in list(getattr(em, "allegati", []) or []):
                if not isinstance(info, dict):
                    continue
                path = self._percorso_allegato_da_info(info)
                if not path:
                    continue
                try:
                    content_hash = str(info.get("sha256") or "").strip().lower()
                    if not re.fullmatch(r"[a-f0-9]{64}", content_hash):
                        content_hash = content_sha256(path.read_bytes())
                    loose_bytes += path.stat().st_size
                    loose_items.append((em, info, path, content_hash))
                except OSError:
                    continue

        archive_before = self.attachment_archive_path.stat().st_size if self.attachment_archive_path.exists() else 0
        archived_existing = sum(
            1
            for em in db.values()
            for info in list(getattr(em, "allegati", []) or [])
            if isinstance(info, dict) and self._allegato_archiviato(info)
        )

        archive_after = archive_before
        reclaimed = 0
        if apply and loose_items:
            self.attachment_archive_path.parent.mkdir(parents=True, exist_ok=True)
            known_members = self._archivio_members()
            with zipfile.ZipFile(
                self.attachment_archive_path,
                "a",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as archive:
                for _, info, path, content_hash in loose_items:
                    member = self._archive_member_for_sha(content_hash)
                    if member not in known_members:
                        archive.write(path, member)
                        known_members.add(member)
                    info["archivio_rel"] = self.attachment_archive_path.relative_to(self.attachments_dir).as_posix()
                    info["archivio_membro"] = member
                    info["archivio_formato"] = "zip-deflate"
                    info["sha256"] = content_hash
            for _, _, path, _ in loose_items:
                try:
                    size = path.stat().st_size
                    path.unlink()
                    reclaimed += size
                except OSError:
                    continue
            for directory in sorted({path.parent for _, _, path, _ in loose_items}, key=lambda p: len(p.parts), reverse=True):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            self._salva()
            archive_after = self.attachment_archive_path.stat().st_size if self.attachment_archive_path.exists() else 0

        archive_growth = max(0, archive_after - archive_before)
        net_reclaimed = max(0, reclaimed - archive_growth) if apply else 0
        estimated_reclaimable = max(0, loose_bytes - archive_growth)
        return {
            "applied": apply,
            "mailbox": str(self.db_path),
            "archive_path": str(self.attachment_archive_path),
            "loose_files": len(loose_items),
            "archived_existing": archived_existing,
            "bytes_input": loose_bytes,
            "archive_before_bytes": archive_before,
            "archive_after_bytes": archive_after,
            "bytes_reclaimable": estimated_reclaimable,
            "bytes_reclaimed": net_reclaimed,
        }

    def _email_ha_allegati_da_salvare(self, em: EmailRicevuta) -> bool:
        allegati = list(getattr(em, "allegati", []) or [])
        return any(not self._allegato_salvato(info) for info in allegati)

    def _merge_allegati_salvati(self, target: EmailRicevuta, parsed: EmailRicevuta) -> int:
        vecchi_salvati = sum(1 for info in (target.allegati or []) if self._allegato_salvato(info))
        nuovi_salvati = sum(1 for info in (parsed.allegati or []) if self._allegato_salvato(info))
        if not nuovi_salvati:
            return 0

        target.allegati = list(parsed.allegati or [])
        if not target.corpo_testo and parsed.corpo_testo:
            target.corpo_testo = parsed.corpo_testo
        if not target.corpo_html and parsed.corpo_html:
            target.corpo_html = parsed.corpo_html
        if not target.message_id and parsed.message_id:
            target.message_id = parsed.message_id
        return max(0, nuovi_salvati - vecchi_salvati)

    @staticmethod
    def _score_testo_decodificato(value: str) -> int:
        text = str(value or "")
        controlli = sum(1 for char in text if ord(char) < 32 and char not in "\r\n\t")
        mojibake = len(re.findall("(?:\\u00c3.|\\u00c2.|\\u00e2[\\u20ac\\x80-\\xbf]|\\ufffd)", text))
        return (text.count("\ufffd") * 100) + (mojibake * 12) + (controlli * 10)

    @classmethod
    def _scegli_testo_migliore(cls, current: str, candidate: str) -> tuple[str, bool]:
        candidate_text = str(candidate or "")
        current_text = str(current or "")
        if not candidate_text.strip():
            return current_text, False
        if not current_text.strip():
            return candidate_text, True
        current_score = cls._score_testo_decodificato(current_text)
        candidate_score = cls._score_testo_decodificato(candidate_text)
        if "\ufffd" in current_text and candidate_score < current_score:
            return candidate_text, True
        if current_score >= 12 and candidate_score + 12 < current_score:
            return candidate_text, True
        return current_text, False

    @classmethod
    def _email_ha_testo_da_riparare(cls, em: EmailRicevuta) -> bool:
        return any(
            "\ufffd" in str(getattr(em, field_name, "") or "")
            for field_name in ("oggetto", "mittente", "mittente_nome", "destinatari", "corpo_testo", "corpo_html")
        )

    @classmethod
    def _merge_testo_migliore(cls, target: EmailRicevuta, parsed: EmailRicevuta) -> bool:
        changed = False
        for field_name in ("oggetto", "mittente", "mittente_nome", "destinatari", "corpo_testo", "corpo_html"):
            best, replace = cls._scegli_testo_migliore(
                str(getattr(target, field_name, "") or ""),
                str(getattr(parsed, field_name, "") or ""),
            )
            if replace:
                setattr(target, field_name, best)
                changed = True
        return changed

    @staticmethod
    def _message_id_key(value: str) -> str:
        return str(value or "").strip().strip("<>").lower()

    @staticmethod
    def _fingerprint_email(em: EmailRicevuta) -> tuple[str, str, str, str]:
        return (
            str(em.cartella or "").strip().upper(),
            str(em.oggetto or "").strip().lower(),
            str(em.mittente or "").strip().lower(),
            str(em.data or "")[:19],
        )

    @staticmethod
    def _cartella_confronto(email_obj: EmailRicevuta) -> str:
        return str(getattr(email_obj, "cartella", "") or "").strip().upper()

    @staticmethod
    def _uid_imap_stabile(uid_imap: str) -> bool:
        return ":UID:" in str(uid_imap or "").upper()

    @classmethod
    def _uid_stabile_diverso(cls, candidate: EmailRicevuta, uid_str: str) -> bool:
        candidate_uid = str(getattr(candidate, "uid_imap", "") or "").strip()
        current_uid = str(uid_str or "").strip()
        return bool(
            candidate_uid
            and current_uid
            and candidate_uid != current_uid
            and cls._uid_imap_stabile(candidate_uid)
            and cls._uid_imap_stabile(current_uid)
        )

    @staticmethod
    def _normalizza_testo_confronto(value: str) -> str:
        return " ".join(str(value or "").split()).strip().lower()

    @classmethod
    def _normalizza_indirizzi_confronto(cls, value: str) -> str:
        indirizzi = sorted(
            address.strip().lower()
            for _name, address in getaddresses([str(value or "")])
            if address and address.strip()
        )
        if indirizzi:
            return ",".join(indirizzi)
        return cls._normalizza_testo_confronto(value)

    @classmethod
    def _corpo_inviata_confronto(cls, email_obj: EmailRicevuta) -> str:
        return cls._normalizza_testo_confronto(
            getattr(email_obj, "corpo_testo", "") or getattr(email_obj, "corpo_html", "")
        )[:240]

    @classmethod
    def _data_minuto_confronto(cls, email_obj: EmailRicevuta) -> str:
        timestamp = cls._timestamp_email_confronto(email_obj)
        if timestamp is None:
            return str(getattr(email_obj, "data", "") or getattr(email_obj, "ricevuta_il", "") or "")[:16]
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M")

    @classmethod
    def _fingerprint_operativo_inbox(
        cls,
        email_obj: EmailRicevuta,
        *,
        require_body: bool = True,
    ) -> tuple[str, str, str, str, str, str]:
        body = cls._corpo_inviata_confronto(email_obj)
        if require_body and not body:
            return ("", "", "", "", "", "")
        return (
            cls._cartella_confronto(email_obj),
            cls._normalizza_testo_confronto(getattr(email_obj, "oggetto", "")),
            cls._normalizza_indirizzi_confronto(
                getattr(email_obj, "mittente", "") or getattr(email_obj, "mittente_nome", "")
            ),
            cls._normalizza_indirizzi_confronto(getattr(email_obj, "destinatari", "")),
            cls._data_minuto_confronto(email_obj),
            body,
        )

    @classmethod
    def _chiave_duplicato_email(cls, email_obj: EmailRicevuta) -> tuple[str, ...]:
        message_id = cls._message_id_key(getattr(email_obj, "message_id", ""))
        if message_id:
            fingerprint = cls._fingerprint_operativo_inbox(email_obj, require_body=False)
            if all(fingerprint[:5]):
                return ("message-id", message_id, *fingerprint)
        fingerprint = cls._fingerprint_operativo_inbox(email_obj, require_body=True)
        if all(fingerprint):
            return ("semantic", *fingerprint)
        return ()

    @classmethod
    def _email_operativa_equivalente(
        cls,
        candidate: EmailRicevuta,
        parsed: EmailRicevuta,
        uid_str: str,
    ) -> bool:
        if cls._cartella_confronto(candidate) != cls._cartella_confronto(parsed):
            return False
        candidate_msg = cls._message_id_key(getattr(candidate, "message_id", ""))
        parsed_msg = cls._message_id_key(getattr(parsed, "message_id", ""))
        same_message_id = bool(candidate_msg and parsed_msg and candidate_msg == parsed_msg)
        same_strong_key = bool(cls._chiave_duplicato_email(candidate) and cls._chiave_duplicato_email(candidate) == cls._chiave_duplicato_email(parsed))
        if same_message_id and not cls._uid_stabile_diverso(candidate, uid_str):
            return True
        return same_strong_key

    @classmethod
    def _merge_duplicato_email(cls, target: EmailRicevuta, duplicate: EmailRicevuta) -> bool:
        changed = False
        for field_name in (
            "mittente",
            "mittente_nome",
            "destinatari",
            "oggetto",
            "data",
            "corpo_testo",
            "corpo_html",
            "message_id",
            "ricevuta_il",
            "uid_imap",
            "origine",
            "stato_pct",
        ):
            if not str(getattr(target, field_name, "") or "").strip() and str(getattr(duplicate, field_name, "") or "").strip():
                setattr(target, field_name, getattr(duplicate, field_name))
                changed = True
        if duplicate.stato == StatoEmail.NON_LETTA and target.stato != StatoEmail.NON_LETTA:
            target.stato = StatoEmail.NON_LETTA
            changed = True
        if not target.allegati and duplicate.allegati:
            target.allegati = list(duplicate.allegati)
            changed = True
        elif target.allegati and duplicate.allegati:
            existing = {
                (
                    str(item.get("nome", "")),
                    str(item.get("sha256", "")),
                    str(item.get("percorso_rel", "")),
                )
                for item in target.allegati
                if isinstance(item, dict)
            }
            for item in duplicate.allegati:
                if not isinstance(item, dict):
                    continue
                key = (
                    str(item.get("nome", "")),
                    str(item.get("sha256", "")),
                    str(item.get("percorso_rel", "")),
                )
                if key not in existing:
                    target.allegati.append(item)
                    existing.add(key)
                    changed = True
        return changed

    @classmethod
    def _deduplica_db_in_memoria(cls, db: Dict[str, EmailRicevuta]) -> int:
        seen: dict[tuple[str, ...], str] = {}
        removed = 0
        for email_id, email_obj in list(db.items()):
            key = cls._chiave_duplicato_email(email_obj)
            if not key:
                continue
            canonical_id = seen.get(key)
            if not canonical_id:
                seen[key] = email_id
                continue
            canonical = db.get(canonical_id)
            if canonical is None:
                seen[key] = email_id
                continue
            cls._merge_duplicato_email(canonical, email_obj)
            db.pop(email_id, None)
            removed += 1
        return removed

    @staticmethod
    def _timestamp_confronto(value: str) -> float | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        candidates = [raw, raw[:19]]
        for candidate in candidates:
            try:
                dt = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            except ValueError:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        try:
            dt = parsedate_to_datetime(raw)
        except (TypeError, ValueError, IndexError, OverflowError):
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()

    @classmethod
    def _timestamp_email_confronto(cls, email_obj: EmailRicevuta) -> float | None:
        return cls._timestamp_confronto(
            getattr(email_obj, "data", "") or getattr(email_obj, "ricevuta_il", "") or ""
        )

    @classmethod
    def _origine_record_locale_inviata(cls, email_obj: EmailRicevuta) -> bool:
        origin = str(getattr(email_obj, "origine", "") or "").strip().upper()
        record_id = str(getattr(email_obj, "id", "") or "")
        return origin == "INVIATA" or record_id.startswith("INVIATA:")

    @classmethod
    def _origine_record_imap_inviata(cls, email_obj: EmailRicevuta) -> bool:
        origin = str(getattr(email_obj, "origine", "") or "").strip().upper()
        uid_imap = str(getattr(email_obj, "uid_imap", "") or "")
        return origin in {"IMAP", CartellaEmail.INVIATI} or cls._uid_imap_stabile(uid_imap)

    @classmethod
    def _coppia_locale_imap_inviata(
        cls,
        candidate: EmailRicevuta,
        existing: EmailRicevuta,
    ) -> bool:
        return (
            cls._origine_record_locale_inviata(candidate)
            and cls._origine_record_imap_inviata(existing)
        ) or (
            cls._origine_record_locale_inviata(existing)
            and cls._origine_record_imap_inviata(candidate)
        )

    @classmethod
    def _fingerprint_inviata(cls, email_obj: EmailRicevuta) -> tuple[str, str, str, str]:
        return (
            cls._normalizza_testo_confronto(getattr(email_obj, "oggetto", "")),
            cls._normalizza_indirizzi_confronto(getattr(email_obj, "destinatari", "")),
            str(getattr(email_obj, "data", "") or getattr(email_obj, "ricevuta_il", "") or "")[:19],
            cls._corpo_inviata_confronto(email_obj),
        )

    @classmethod
    def _email_inviata_equivalente_con_scarto_orario(
        cls,
        candidate: EmailRicevuta,
        existing: EmailRicevuta,
    ) -> bool:
        if not cls._coppia_locale_imap_inviata(candidate, existing):
            return False
        candidate_subject, candidate_recipients, _candidate_date, candidate_body = cls._fingerprint_inviata(candidate)
        existing_subject, existing_recipients, _existing_date, existing_body = cls._fingerprint_inviata(existing)
        if not candidate_subject or candidate_subject != existing_subject:
            return False
        if not candidate_recipients or candidate_recipients != existing_recipients:
            return False
        if not candidate_body or candidate_body != existing_body:
            return False
        candidate_timestamp = cls._timestamp_email_confronto(candidate)
        existing_timestamp = cls._timestamp_email_confronto(existing)
        if candidate_timestamp is None or existing_timestamp is None:
            return False
        return abs(candidate_timestamp - existing_timestamp) <= 15 * 60

    @classmethod
    def _email_inviata_equivalente(
        cls,
        candidate: EmailRicevuta,
        existing: EmailRicevuta,
    ) -> bool:
        if str(getattr(existing, "cartella", "") or "").upper() != CartellaEmail.INVIATI:
            return False
        candidate_msg_id = cls._message_id_key(getattr(candidate, "message_id", ""))
        existing_msg_id = cls._message_id_key(getattr(existing, "message_id", ""))
        if candidate_msg_id and existing_msg_id and candidate_msg_id == existing_msg_id:
            return True
        fingerprint = cls._fingerprint_inviata(candidate)
        if not all(fingerprint[:3]):
            return False
        if fingerprint == cls._fingerprint_inviata(existing):
            return True
        return cls._email_inviata_equivalente_con_scarto_orario(candidate, existing)

    @classmethod
    def _preferisci_record_inviato_canonico(
        cls,
        *records: tuple[str, EmailRicevuta],
        preferred_id: str = "",
    ) -> tuple[str, EmailRicevuta] | None:
        valid_records = [(record_id, record) for record_id, record in records if record_id and record]
        if not valid_records:
            return None
        for record_id, record in valid_records:
            if str(getattr(record, "cartella", "") or "").upper() == CartellaEmail.INVIATI and cls._uid_imap_stabile(getattr(record, "uid_imap", "")):
                return record_id, record
        if preferred_id:
            for record_id, record in valid_records:
                if record_id == preferred_id:
                    return record_id, record
        return valid_records[0]

    def _trova_email_esistente(
        self,
        db: Dict[str, EmailRicevuta],
        email_per_uid: Dict[str, EmailRicevuta],
        uid_str: str,
        parsed: EmailRicevuta,
    ) -> Optional[EmailRicevuta]:
        exact = email_per_uid.get(uid_str)
        if exact:
            return exact

        for candidate in db.values():
            if self._email_operativa_equivalente(candidate, parsed, uid_str):
                return candidate
        return None

    @staticmethod
    def _imap_tokens(data: Any) -> List[str]:
        if not data or not data[0]:
            return []
        raw = data[0]
        if isinstance(raw, bytes):
            raw = raw.decode(errors="ignore")
        return [token for token in str(raw).split() if token]

    @staticmethod
    def _imap_token_sort_key(token: str) -> tuple[int, str]:
        try:
            return int(str(token)), str(token)
        except ValueError:
            return 0, str(token)

    @staticmethod
    def _imap_exception_is_timeout(exc: BaseException) -> bool:
        if isinstance(exc, (socket.timeout, TimeoutError)):
            return True
        message = str(exc or "").strip().lower()
        return any(hint in message for hint in _IMAP_TIMEOUT_ERROR_HINTS)

    def _imap_search_all(self, mail) -> tuple[List[str], bool]:
        try:
            status, data = mail.uid("SEARCH", None, "ALL")
            tokens = self._imap_tokens(data)
            if status == "OK" and tokens:
                return tokens, True
        except (AttributeError, imaplib.IMAP4.error, TypeError):
            pass

        _, data = mail.search(None, "ALL")
        return self._imap_tokens(data), False

    @staticmethod
    def _imap_fetch_message(mail, token: str, *, use_uid: bool):
        if use_uid:
            try:
                return mail.uid("FETCH", token, "(RFC822)")
            except (AttributeError, imaplib.IMAP4.error, TypeError):
                pass
        return mail.fetch(token, "(RFC822)")

    @staticmethod
    def _imap_mailbox_select_arg(mailbox: str) -> str:
        name = str(mailbox or "").strip()
        if not name or (name.startswith('"') and name.endswith('"')):
            return name
        if any(char.isspace() for char in name) or '"' in name:
            escaped = name.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return name

    @classmethod
    def _imap_select_folder(cls, mail: Any, mailbox: str):
        return mail.select(cls._imap_mailbox_select_arg(mailbox), readonly=True)

    @staticmethod
    def _imap_mailbox_from_list_line(line: Any) -> str:
        raw = line.decode(errors="ignore") if isinstance(line, bytes) else str(line or "")
        raw = raw.strip()
        if not raw:
            return ""
        match = re.search(r'\)\s+"[^"]*"\s+(.+)$', raw)
        if match:
            return match.group(1).strip().strip('"')
        quoted = re.findall(r'"((?:[^"\\]|\\.)*)"', raw)
        if quoted:
            return quoted[-1].replace(r"\"", '"').strip()
        return raw.rsplit(" ", 1)[-1].strip().strip('"')

    @staticmethod
    def _imap_mailbox_list_entry_is_operativa(line: Any, mailbox: str) -> bool:
        name = str(mailbox or "").strip().strip('"')
        if not name:
            return False
        raw_line = line.decode(errors="ignore") if isinstance(line, bytes) else str(line or "")
        lowered = f"{raw_line} {name}".lower()
        if name.upper() == "INBOX":
            return True
        if any(hint in lowered for hint in (*_SENT_FOLDER_HINTS, *_TRASH_FOLDER_HINTS, *_DRAFT_FOLDER_HINTS)):
            return True
        if any(hint in lowered for hint in _NON_SYNC_DISCOVERY_FOLDER_HINTS):
            return False
        return False

    @classmethod
    def _cartelle_imap_effettive(cls, mail: Any, richieste: List[str]) -> List[str]:
        cartelle: list[str] = []

        def _add(value: Any) -> None:
            name = str(value or "").strip()
            if name and name not in cartelle:
                cartelle.append(name)

        for cartella in richieste:
            _add(cartella)

        try:
            status, data = mail.list()
        except (AttributeError, imaplib.IMAP4.error, OSError, socket.timeout, TimeoutError, TypeError):
            return cartelle
        if status != "OK":
            return cartelle

        for line in data or []:
            mailbox = cls._imap_mailbox_from_list_line(line)
            if not mailbox:
                continue
            if cls._imap_mailbox_list_entry_is_operativa(line, mailbox):
                _add(mailbox)
        return cartelle

    @staticmethod
    def _allinea_cartella_da_imap(email_obj: EmailRicevuta, cartella_imap: str) -> bool:
        expected = _cartella_interna_da_imap(cartella_imap)
        if expected == CartellaEmail.INBOX:
            return False
        expected_status = _stato_iniziale_da_cartella(expected)
        changed = False
        if email_obj.cartella != expected:
            email_obj.cartella = expected
            changed = True
        if email_obj.stato != expected_status:
            email_obj.stato = expected_status
            changed = True
        return changed

    # ---- Query ----

    def tutte(
        self,
        cartella: Optional[str] = None,
        solo_non_lette: bool = False,
        q: str = "",
        stato_lettura: str = "",
        solo_pst: bool = False,
        con_allegati: bool = False,
        stato_pct: str = "",
        origine: str = "",
        data_da: str = "",
        data_a: str = "",
    ) -> List[EmailRicevuta]:
        db = self._carica()
        if self._deduplica_db_in_memoria(db):
            self._salva()
        emails = list(db.values())
        if cartella:
            emails = [e for e in emails if e.cartella == cartella]
        if solo_non_lette or stato_lettura == StatoEmail.NON_LETTA:
            emails = [e for e in emails if e.stato == StatoEmail.NON_LETTA]
        elif stato_lettura == StatoEmail.LETTA:
            emails = [e for e in emails if e.stato == StatoEmail.LETTA]
        if solo_pst:
            emails = [e for e in emails if e.e_pst]
        if con_allegati:
            emails = [e for e in emails if e.allegati]
        if stato_pct:
            emails = [e for e in emails if e.stato_pct == stato_pct]
        if origine:
            emails = [e for e in emails if (e.origine or "").upper() == origine.upper()]
        if data_da:
            emails = [e for e in emails if (e.timestamp or "")[:10] >= data_da]
        if data_a:
            emails = [e for e in emails if (e.timestamp or "")[:10] <= data_a]
        if q:
            ql = q.lower()
            emails = [
                e for e in emails
                if ql in e.oggetto.lower()
                or ql in e.mittente.lower()
                or ql in e.mittente_nome.lower()
                or ql in e.corpo_testo.lower()
                or ql in e.destinatari.lower()
                or ql in e.corpo_html.lower()
                or ql in e.stato_pct.lower()
            ]
        emails.sort(key=lambda e: e.timestamp, reverse=True)
        return emails

    def get(self, id_email: str) -> Optional[EmailRicevuta]:
        return self._carica().get(id_email)

    def statistiche(self) -> dict:
        db = self._carica()
        if self._deduplica_db_in_memoria(db):
            self._salva()
        emails = list(db.values())
        return {
            "totale":     len(emails),
            "non_lette":  sum(1 for e in emails if e.stato == StatoEmail.NON_LETTA
                              and e.cartella == CartellaEmail.INBOX),
            "inviati":    sum(1 for e in emails if e.cartella == CartellaEmail.INVIATI),
            "cestino":    sum(1 for e in emails if e.cartella == CartellaEmail.CESTINO),
            "pst":        sum(1 for e in emails if e.e_pst),
            "inbox":      sum(1 for e in emails if e.cartella == CartellaEmail.INBOX),
        }

    # ---- Azioni ----

    def marca_letta(self, id_email: str) -> None:
        db = self._carica()
        if id_email in db:
            db[id_email].stato = StatoEmail.LETTA
            db[id_email].letta_il = datetime.now().isoformat()
            self._salva()

    def marca_non_letta(self, id_email: str) -> None:
        db = self._carica()
        if id_email in db:
            db[id_email].stato = StatoEmail.NON_LETTA
            db[id_email].letta_il = ""
            self._salva()

    def sposta_cestino(self, id_email: str) -> None:
        db = self._carica()
        if id_email in db:
            db[id_email].cartella = CartellaEmail.CESTINO
            db[id_email].stato    = StatoEmail.CESTINO
            self._salva()

    def sposta_cestino_multipla(self, ids_email: List[str]) -> dict[str, list[str]]:
        db = self._carica()
        updated: list[str] = []
        missing: list[str] = []
        skipped: list[str] = []
        seen: set[str] = set()

        for raw_id in ids_email:
            id_email = str(raw_id or "").strip()
            if not id_email or id_email in seen:
                continue
            seen.add(id_email)
            email_obj = db.get(id_email)
            if email_obj is None:
                missing.append(id_email)
                continue
            if str(email_obj.cartella or "").upper() == CartellaEmail.CESTINO:
                skipped.append(id_email)
                continue
            email_obj.cartella = CartellaEmail.CESTINO
            email_obj.stato = StatoEmail.CESTINO
            updated.append(id_email)

        if updated:
            self._salva()
        return {"updated": updated, "missing": missing, "skipped": skipped}

    def ripristina(self, id_email: str) -> None:
        db = self._carica()
        if id_email in db:
            em = db[id_email]
            em.cartella = CartellaEmail.INBOX
            em.stato    = StatoEmail.LETTA
            self._salva()

    def elimina_definitivamente(self, id_email: str) -> None:
        db = self._carica()
        if id_email in db:
            del db[id_email]
            cartella_email = self.attachments_dir / id_email
            if cartella_email.exists():
                shutil.rmtree(cartella_email, ignore_errors=True)
            self._salva()
            self._invalida()

    def elimina_definitivamente_multipla(self, ids_email: List[str]) -> dict[str, list[str]]:
        db = self._carica()
        updated: list[str] = []
        missing: list[str] = []
        seen: set[str] = set()

        for raw_id in ids_email:
            id_email = str(raw_id or "").strip()
            if not id_email or id_email in seen:
                continue
            seen.add(id_email)
            if id_email not in db:
                missing.append(id_email)
                continue
            del db[id_email]
            updated.append(id_email)

        if updated:
            self._salva()
            for id_email in updated:
                cartella_email = self.attachments_dir / id_email
                if cartella_email.exists():
                    shutil.rmtree(cartella_email, ignore_errors=True)
            self._invalida()
        return {"updated": updated, "missing": missing, "skipped": []}

    def svuota_cestino(self) -> int:
        db = self._carica()
        da_eliminare = [k for k, v in db.items() if v.cartella == CartellaEmail.CESTINO]
        for k in da_eliminare:
            del db[k]
        if da_eliminare:
            self._salva()
            self._invalida()
        return len(da_eliminare)

    def aggiungi(self, email_obj: EmailRicevuta) -> None:
        """Aggiunge (o aggiorna) un'email nel database."""
        db = self._carica()
        db[email_obj.id] = email_obj
        self._salva()

    # ---- Sync IMAP ----

    def sincronizza_imap(
        self,
        imap_host: str,
        imap_port: int,
        username: str,
        password: str,
        use_ssl: bool = True,
        cartelle_imap: Optional[List[str]] = None,
        limite: int = 50,
        timeout_seconds: int | None = None,
    ) -> dict:
        """
        Scarica le email più recenti via IMAP e le salva nel database locale.

        Returns:
            {"nuove": int, "errori": int, "pst_trovate": int, "allegati_salvati": int, "cartelle_corrette": int, "testi_corretti": int, "errore": str}
        """
        risultato = {
            "nuove": 0,
            "errori": 0,
            "pst_trovate": 0,
            "allegati_salvati": 0,
            "cartelle_corrette": 0,
            "testi_corretti": 0,
            "duplicati_rimossi": 0,
            "riconnessioni_imap": 0,
            "errore": "",
        }
        cartelle_imap = cartelle_imap or ["INBOX"]
        timeout_s = resolve_imap_timeout_seconds(timeout_seconds)

        try:
            def _connect_mail():
                if use_ssl:
                    client = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=timeout_s)
                else:
                    client = imaplib.IMAP4(imap_host, imap_port, timeout=timeout_s)
                    client.starttls()
                client.login(username, password)
                return client

            mail = run_imap_runtime_operation(_connect_mail)
        except (imaplib.IMAP4.error, OSError, socket.timeout, TimeoutError) as e:
            risultato["errore"] = describe_imap_connection_error(e, timeout_seconds=timeout_s)
            return risultato
        except Exception as e:
            risultato["errore"] = describe_imap_connection_error(e, timeout_seconds=timeout_s)
            return risultato

        def _logout_quietly(client: Any) -> None:
            try:
                client.logout()
            except Exception:
                pass

        def _reconnect_mail() -> bool:
            nonlocal mail
            _logout_quietly(mail)
            try:
                mail = run_imap_runtime_operation(_connect_mail)
                risultato["riconnessioni_imap"] += 1
                return True
            except (imaplib.IMAP4.error, OSError, socket.timeout, TimeoutError) as exc:
                risultato["errore"] = describe_imap_connection_error(exc, timeout_seconds=timeout_s)
                return False
            except Exception as exc:
                risultato["errore"] = describe_imap_connection_error(exc, timeout_seconds=timeout_s)
                return False

        def _select_folder_with_retry(cartella_imap: str):
            try:
                return self._imap_select_folder(mail, cartella_imap)
            except imaplib.IMAP4.error:
                return "NO", []
            except Exception as exc:
                if not self._imap_exception_is_timeout(exc):
                    raise
                if not _reconnect_mail():
                    return "NO", []
                try:
                    return self._imap_select_folder(mail, cartella_imap)
                except imaplib.IMAP4.error:
                    return "NO", []

        def _search_all_with_retry(cartella_imap: str) -> tuple[List[str], bool]:
            try:
                return self._imap_search_all(mail)
            except Exception as exc:
                if not self._imap_exception_is_timeout(exc):
                    raise
                if not _reconnect_mail():
                    return [], True
                status, _ = _select_folder_with_retry(cartella_imap)
                if status != "OK":
                    return [], True
                try:
                    return self._imap_search_all(mail)
                except Exception as retry_exc:
                    if self._imap_exception_is_timeout(retry_exc):
                        risultato["errori"] += 1
                        return [], True
                    raise

        def _fetch_message_with_retry(cartella_imap: str, uid: str, *, use_uid: bool):
            try:
                return self._imap_fetch_message(mail, uid, use_uid=use_uid)
            except Exception as exc:
                if not self._imap_exception_is_timeout(exc):
                    raise
                if not _reconnect_mail():
                    return None
                status, _ = _select_folder_with_retry(cartella_imap)
                if status != "OK":
                    return None
                try:
                    return self._imap_fetch_message(mail, uid, use_uid=use_uid)
                except Exception as retry_exc:
                    if self._imap_exception_is_timeout(retry_exc):
                        risultato["errori"] += 1
                        return None
                    raise

        db = self._carica()
        dedup_iniziale = self._deduplica_db_in_memoria(db)
        risultato["duplicati_rimossi"] += dedup_iniziale
        email_per_uid = {e.uid_imap: e for e in db.values() if e.uid_imap}

        try:
            for cartella_imap in self._cartelle_imap_effettive(mail, cartelle_imap):
                if risultato["errore"]:
                    break
                try:
                    status, _ = _select_folder_with_retry(cartella_imap)
                    if status != "OK":
                        continue

                    uid_list_all, usa_uid_stabile = _search_all_with_retry(cartella_imap)
                    if not uid_list_all:
                        continue

                    uid_list_all = sorted(uid_list_all, key=self._imap_token_sort_key)
                    finestra_sync = max(int(limite or 0), 500)
                    uid_list = uid_list_all[-finestra_sync:]

                    # Le PEC storiche gia' presenti ma senza file allegati non devono
                    # restare fuori solo perche' non sono tra gli ultimi messaggi.
                    prefix_cartella = f"{cartella_imap}:"
                    uid_da_riparare = [
                        uid_key.rsplit(":", 1)[1]
                        for uid_key, em_storica in email_per_uid.items()
                        if uid_key.startswith(prefix_cartella)
                        and uid_key.rsplit(":", 1)[1] in uid_list_all
                        and (
                            self._email_ha_allegati_da_salvare(em_storica)
                            or self._email_ha_testo_da_riparare(em_storica)
                        )
                    ]
                    uid_list = list(dict.fromkeys(uid_list + uid_da_riparare))

                    for uid in reversed(uid_list):
                        if risultato["errore"]:
                            break
                        uid_str = f"{cartella_imap}:UID:{uid}" if usa_uid_stabile else f"{cartella_imap}:{uid}"
                        email_esistente = email_per_uid.get(uid_str)
                        ripara_allegati = bool(
                            email_esistente and self._email_ha_allegati_da_salvare(email_esistente)
                        )
                        ripara_testo = bool(
                            email_esistente and self._email_ha_testo_da_riparare(email_esistente)
                        )
                        if email_esistente and not (ripara_allegati or ripara_testo):
                            if self._allinea_cartella_da_imap(email_esistente, cartella_imap):
                                risultato["cartelle_corrette"] += 1
                            continue

                        try:
                            fetched = _fetch_message_with_retry(cartella_imap, uid, use_uid=usa_uid_stabile)
                            if fetched is None:
                                if risultato["errore"]:
                                    break
                                continue
                            _, msg_data = fetched
                            if not msg_data or not msg_data[0]:
                                continue

                            raw = msg_data[0][1]
                            if not isinstance(raw, bytes):
                                continue

                            parsed = email.message_from_bytes(raw)
                            em = self._parse_message(
                                parsed,
                                uid_str,
                                cartella_imap,
                                email_id=email_esistente.id if email_esistente else None,
                                raw_bytes=raw,
                            )
                            if em:
                                if not email_esistente:
                                    email_esistente = self._trova_email_esistente(db, email_per_uid, uid_str, em)
                                    ripara_allegati = bool(
                                        email_esistente and self._email_ha_allegati_da_salvare(email_esistente)
                                    )

                                if email_esistente:
                                    if uid_str and email_esistente.uid_imap != uid_str:
                                        old_uid = email_esistente.uid_imap
                                        email_esistente.uid_imap = uid_str
                                        if old_uid in email_per_uid:
                                            email_per_uid.pop(old_uid, None)
                                        email_per_uid[uid_str] = email_esistente
                                    if self._allinea_cartella_da_imap(email_esistente, cartella_imap):
                                        risultato["cartelle_corrette"] += 1
                                    salvati = self._merge_allegati_salvati(email_esistente, em)
                                    risultato["allegati_salvati"] += salvati
                                    if self._merge_testo_migliore(email_esistente, em):
                                        risultato["testi_corretti"] += 1
                                    if not email_esistente.eml_file and em.eml_file:
                                        email_esistente.eml_file = em.eml_file
                                        email_esistente.eml_sha256 = em.eml_sha256
                                else:
                                    # Auto-rileva risposte PST
                                    self._analizza_pst(em)
                                    db[em.id] = em
                                    email_per_uid[uid_str] = em
                                    risultato["nuove"] += 1
                                    if em.e_pst:
                                        risultato["pst_trovate"] += 1
                        except Exception:
                            risultato["errori"] += 1

                except Exception:
                    risultato["errori"] += 1

            risultato["duplicati_rimossi"] += self._deduplica_db_in_memoria(db)
            self._salva()
            _logout_quietly(mail)

        except Exception as e:
            risultato["errore"] = describe_imap_connection_error(e, timeout_seconds=timeout_s)
            try:
                self._salva()
            except Exception:
                pass
            _logout_quietly(mail)

        return risultato

    def sincronizza_inviati(self, messaggi_inviati: list) -> int:
        """
        Importa i messaggi email già inviati da messaggi.py nel database casella.
        Evita duplicati tra storico messaggi e copia IMAP della cartella Inviati.
        """
        db = self._carica()
        aggiunti = 0
        modificati = False

        for msg in messaggi_inviati:
            em_id = f"INVIATA:{msg.id}"
            em = EmailRicevuta(
                id=em_id,
                cartella=CartellaEmail.INVIATI,
                stato=StatoEmail.LETTA,
                mittente=getattr(msg, "email_mittente", "") or "",
                mittente_nome="Studio legale",
                destinatari=getattr(msg, "email_destinatario", "") or "",
                oggetto=getattr(msg, "oggetto", "") or "",
                data=getattr(msg, "inviato_il", "") or getattr(msg, "creato_il", ""),
                corpo_testo=getattr(msg, "corpo", "") or "",
                corpo_html=getattr(msg, "corpo_html", "") or "",
                message_id=getattr(msg, "sid_esterno", "") or "",
                origine="INVIATA",
                ricevuta_il=getattr(msg, "inviato_il", "") or getattr(msg, "creato_il", ""),
            )

            candidati: list[tuple[str, EmailRicevuta]] = []
            record_esatto = db.get(em_id)
            if record_esatto is not None:
                candidati.append((em_id, record_esatto))
            for existing_id, existing in list(db.items()):
                if existing_id == em_id:
                    continue
                if self._email_inviata_equivalente(em, existing):
                    candidati.append((existing_id, existing))

            if not candidati:
                db[em_id] = em
                aggiunti += 1
                modificati = True
                continue

            canonico = self._preferisci_record_inviato_canonico(*candidati, preferred_id=em_id)
            if canonico is None:
                db[em_id] = em
                aggiunti += 1
                modificati = True
                continue

            canonico_id, email_canonica = canonico
            changed = False
            if not email_canonica.message_id and em.message_id:
                email_canonica.message_id = em.message_id
                changed = True
            if not email_canonica.destinatari and em.destinatari:
                email_canonica.destinatari = em.destinatari
                changed = True
            if not email_canonica.corpo_testo and em.corpo_testo:
                email_canonica.corpo_testo = em.corpo_testo
                changed = True
            if not email_canonica.corpo_html and em.corpo_html:
                email_canonica.corpo_html = em.corpo_html
                changed = True
            if not email_canonica.ricevuta_il and em.ricevuta_il:
                email_canonica.ricevuta_il = em.ricevuta_il
                changed = True
            if str(email_canonica.cartella or "").upper() != CartellaEmail.INVIATI:
                email_canonica.cartella = CartellaEmail.INVIATI
                changed = True
            if str(email_canonica.stato or "").upper() != StatoEmail.LETTA:
                email_canonica.stato = StatoEmail.LETTA
                changed = True

            for duplicate_id, _duplicate in candidati:
                if duplicate_id == canonico_id:
                    continue
                db.pop(duplicate_id, None)
                modificati = True

            if changed:
                modificati = True

        if aggiunti or modificati:
            self._salva()
        return aggiunti

    # ---- Helpers privati ----

    @classmethod
    def _decode_bytes_testo(cls, payload: bytes, charset: str | None = None) -> str:
        if not payload:
            return ""
        candidates: list[str] = []
        for candidate in (charset, "utf-8", "windows-1252", "iso-8859-1", "latin-1"):
            if not candidate:
                continue
            normalized = str(candidate).strip().lower()
            if normalized and normalized not in candidates:
                candidates.append(normalized)

        best_text = ""
        best_score: int | None = None
        for encoding in candidates:
            try:
                decoded = payload.decode(encoding, errors="replace")
            except LookupError:
                continue
            score = cls._score_testo_decodificato(decoded)
            if best_score is None or score < best_score:
                best_text = decoded
                best_score = score
                if score == 0:
                    break
        return best_text

    @classmethod
    def _decode_part_text(cls, part: email.message.Message) -> str:
        payload = part.get_payload(decode=True)
        if isinstance(payload, bytes):
            return cls._decode_bytes_testo(payload, part.get_content_charset() or "utf-8")
        raw_payload = part.get_payload()
        if isinstance(raw_payload, str):
            return raw_payload
        return ""

    @classmethod
    def _decode_header_val(cls, val: str) -> str:
        """Decodifica un header RFC 2047 in stringa Python."""
        if not val:
            return ""
        parts = decode_header(val)
        decoded = []
        for chunk, charset in parts:
            if isinstance(chunk, bytes):
                decoded.append(cls._decode_bytes_testo(chunk, charset or "utf-8"))
            else:
                decoded.append(str(chunk))
        return " ".join(decoded).strip()

    @staticmethod
    def _payload_allegato(part: email.message.Message) -> bytes:
        payload = part.get_payload(decode=True)
        if payload:
            return payload
        if part.get_content_type() != "message/rfc822":
            return b""
        nested = part.get_payload()
        if isinstance(nested, list):
            chunks: list[bytes] = []
            for nested_message in nested:
                if hasattr(nested_message, "as_bytes"):
                    chunks.append(nested_message.as_bytes(policy=policy.default))
                elif nested_message is not None:
                    chunks.append(str(nested_message).encode("utf-8", errors="replace"))
            return b"\r\n".join(chunk for chunk in chunks if chunk)
        if isinstance(nested, str):
            return nested.encode("utf-8", errors="replace")
        return b""

    @staticmethod
    def _is_allegato_part(part: email.message.Message, filename: str) -> bool:
        content_disposition = str(part.get("Content-Disposition", "") or "").lower()
        if "attachment" in content_disposition:
            return True
        if "inline" in content_disposition and filename:
            return True
        return bool(filename and part.get_content_maintype() != "multipart")

    def _parse_message(
        self,
        msg: email.message.Message,
        uid_str: str,
        cartella_imap: str,
        *,
        email_id: str | None = None,
        raw_bytes: bytes | None = None,
    ) -> Optional[EmailRicevuta]:
        """Converte un messaggio IMAP in EmailRicevuta."""
        try:
            em_id = email_id or uuid.uuid4().hex
            oggetto = self._decode_header_val(msg.get("Subject", ""))
            mittente_raw = self._decode_header_val(msg.get("From", ""))
            destinatari  = self._decode_header_val(msg.get("To", ""))

            # Parse mittente nome + indirizzo
            match = re.match(r"^(.*?)\s*<([^>]+)>", mittente_raw)
            if match:
                mittente_nome = match.group(1).strip().strip('"')
                mittente_addr = match.group(2).strip()
            else:
                mittente_nome = ""
                mittente_addr = mittente_raw.strip()

            # Data
            data_raw = msg.get("Date", "")
            try:
                data_iso = parsedate_to_datetime(data_raw).isoformat()
            except Exception:
                data_iso = datetime.now().isoformat()

            # Corpo
            corpo_testo = ""
            corpo_html  = ""
            allegati    = []
            eml_info = self._salva_eml_originale(em_id, raw_bytes or b"") if raw_bytes else {}

            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    fname = self._decode_header_val(part.get_filename() or "")
                    is_attachment = self._is_allegato_part(part, fname)
                    if is_attachment:
                        payload = self._payload_allegato(part)
                        nome_originale = fname or "allegato.bin"
                        att = {
                            "nome": nome_originale,
                            "mime": ct,
                            "size": len(payload),
                        }
                        if payload:
                            att.update(self._salva_allegato(em_id, nome_originale, payload))
                        allegati.append(att)
                    elif ct == "text/plain" and not corpo_testo:
                        corpo_testo = self._decode_part_text(part)
                    elif ct == "text/html" and not corpo_html:
                        corpo_html = self._decode_part_text(part)
            else:
                testo = self._decode_part_text(msg)
                if testo:
                    if msg.get_content_type() == "text/html":
                        corpo_html = testo
                    else:
                        corpo_testo = testo

            cartella_interna = _cartella_interna_da_imap(cartella_imap)

            return EmailRicevuta(
                id=em_id,
                cartella=cartella_interna,
                stato=_stato_iniziale_da_cartella(cartella_interna),
                mittente=mittente_addr,
                mittente_nome=mittente_nome,
                destinatari=destinatari,
                oggetto=oggetto,
                data=data_iso,
                corpo_testo=corpo_testo.strip(),
                corpo_html=corpo_html.strip(),
                allegati=allegati,
                message_id=msg.get("Message-ID", "").strip(),
                uid_imap=uid_str,
                origine="IMAP" if cartella_interna == CartellaEmail.INBOX else cartella_interna,
                eml_file=eml_info.get("eml_file", ""),
                eml_sha256=eml_info.get("eml_sha256", ""),
            )
        except Exception:
            return None

    @staticmethod
    def _analizza_pst(em: EmailRicevuta) -> None:
        """
        Analizza l'oggetto e il corpo dell'email per riconoscere
        una risposta del Portale Servizi Telematici.
        Popola em.stato_pct se riconosciuta.
        """
        sogg = em.oggetto.upper()
        e_pst = any(p.search(sogg) for p in _PATTERN_PST)
        if not e_pst:
            # Controlla il mittente: PST invia da @giustiziapec.it
            e_pst = "GIUSTIZIAPEC" in em.mittente.upper() or "SICUREZZAPEC" in em.mittente.upper()
        if not e_pst:
            return

        # Determina nuovo stato PCT
        for pattern_key, stato_pct in _MAPPA_STATO_PST.items():
            if re.search(pattern_key, sogg, re.I):
                em.stato_pct = stato_pct
                break

        if not em.stato_pct:
            em.stato_pct = "CONSEGNATO"  # default se riconosciuta ma stato incerto

        # Prova a estrarre ID deposito dall'oggetto/corpo
        match = re.search(r"[A-Z0-9]{8,16}", sogg)
        if match:
            em.id_deposito_pct = match.group(0)


def _estrai_rg_email(em: EmailRicevuta) -> tuple[str, str] | None:
    testo = " ".join([
        em.oggetto or "",
        em.corpo_testo or "",
        re.sub(r"<[^>]+>", " ", em.corpo_html or ""),
    ])
    match = _RE_RG_PCT.search(testo)
    if not match:
        return None
    return match.group(1).lstrip("0") or "0", match.group(2)


_EMAIL_MATCH_STOPWORDS = {
    "rg",
    "tribunale",
    "causa",
    "fascicolo",
    "telematico",
    "deposito",
    "cancelleria",
    "pec",
    "atto",
    "udienza",
    "della",
    "delle",
    "degli",
    "degli",
    "dello",
    "dalla",
    "dello",
    "per",
    "con",
    "del",
    "dell",
    "dellavv",
    "avv",
    "studio",
}
_KEYWORDS_CANCELLERIA = (
    "accettazione",
    "consegna",
    "cancelleria",
    "deposito telematico",
    "esito deposito",
    "controlli automatici",
    "rifiuto",
    "notificazione ai sensi del d l 179 2012",
    "biglietto di cancelleria",
    "comunicazione di cancelleria",
    "tribunale ordinario",
    "ufficio notificazioni",
)
_GIUSTIZIA_SENDER_HINTS = (
    "giustiziapec.it",
    "giustiziacert.it",
    "civile.ptel.giustiziacert.it",
    "pst.giustizia.it",
    "appweb.giustizia.it",
    "giustizia.it",
)


def _normalizza_testo_email_match(value: str) -> str:
    testo = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    testo = re.sub(r"[_/\\-]+", " ", testo.lower())
    return " ".join(testo.split())


def _normalizza_testo_email_keywords(value: str) -> str:
    testo = _normalizza_testo_email_match(value)
    testo = re.sub(r"[^a-z0-9]+", " ", testo)
    return " ".join(testo.split())


def _tokenizza_email_match(value: str) -> set[str]:
    testo = _normalizza_testo_email_match(value)
    tokens = re.findall(r"[a-z0-9]{3,}", testo)
    return {
        token
        for token in tokens
        if token not in _EMAIL_MATCH_STOPWORDS and not token.isdigit()
    }


def _corpo_normalizzato_email(em: EmailRicevuta) -> str:
    return _normalizza_testo_email_keywords(
        " ".join(
            [
                em.oggetto or "",
                em.corpo_testo or "",
                re.sub(r"<[^>]+>", " ", em.corpo_html or ""),
                em.mittente or "",
                em.mittente_nome or "",
            ]
        )
    )


def _email_da_canale_giustizia(em: EmailRicevuta) -> bool:
    sender_text = _normalizza_testo_email_match(" ".join([em.mittente or "", em.mittente_nome or ""]))
    body_text = _corpo_normalizzato_email(em)
    return any(
        hint in sender_text or hint in body_text
        for hint in _GIUSTIZIA_SENDER_HINTS
    )


def _score_fascicolo_email_identity(fasc, em: EmailRicevuta) -> int:
    testo_email = _corpo_normalizzato_email(em)
    tokens_email = _tokenizza_email_match(testo_email)
    score = 0

    nome_cliente = str(getattr(fasc, "nome_cliente", "") or "").strip()
    if nome_cliente:
        nome_cliente_norm = _normalizza_testo_email_match(nome_cliente)
        if nome_cliente_norm and nome_cliente_norm in testo_email:
            score += 55
        overlap_cliente = _tokenizza_email_match(nome_cliente) & tokens_email
        if len(overlap_cliente) >= 2:
            score += 35
        elif len(overlap_cliente) == 1:
            score += 15

    controparte = str(getattr(fasc, "controparte", "") or "").strip()
    if controparte:
        overlap_controparte = _tokenizza_email_match(controparte) & tokens_email
        if len(overlap_controparte) >= 2:
            score += 18

    oggetto = str(getattr(fasc, "oggetto", "") or "").strip()
    if oggetto:
        overlap_oggetto = _tokenizza_email_match(oggetto) & tokens_email
        if len(overlap_oggetto) >= 2:
            score += 14

    tribunale = str(getattr(fasc, "tribunale", "") or "").strip()
    if tribunale:
        overlap_tribunale = _tokenizza_email_match(tribunale) & tokens_email
        if len(overlap_tribunale) >= 1:
            score += 8

    return score


def _ordine_stato_pct(stato: str) -> int:
    return _STATI_PCT_ORDINE.get(str(stato or "").upper(), -1)


def _render_ricevuta_email(em: EmailRicevuta) -> str:
    corpo = (em.corpo_testo or re.sub(r"<[^>]+>", " ", em.corpo_html or "")).strip()
    righe = []
    if em.oggetto:
        righe.append(f"Oggetto: {em.oggetto}")
    if em.mittente:
        righe.append(f"Da: {em.mittente_nome or em.mittente}")
    if em.timestamp:
        righe.append(f"Data: {em.timestamp}")
    if corpo:
        righe.append("")
        righe.append(corpo)
    return "\n".join(righe).strip()


def _aggiorna_ricevute_deposito_da_email(dep, em: EmailRicevuta) -> None:
    testo = _render_ricevuta_email(em)
    stato_nuovo = str(em.stato_pct or "").upper()
    if stato_nuovo == "ACCETTATO_PEC" and not dep.ricevuta_accettazione:
        dep.ricevuta_accettazione = testo
    elif stato_nuovo == "CONSEGNATO" and not dep.ricevuta_consegna:
        dep.ricevuta_consegna = testo
    elif stato_nuovo in {"WARN_CONTROLLI", "ERRORE_CONTROLLI"}:
        if not dep.ricevuta_controlli_automatici:
            dep.ricevuta_controlli_automatici = testo
        dep.esito_controlli = "WARN" if stato_nuovo == "WARN_CONTROLLI" else "ERROR"
    elif stato_nuovo in {"ACCETTATO_CANCELLERIA", "RIFIUTATO_CANCELLERIA"} and not dep.ricevuta_cancelleria:
        dep.ricevuta_cancelleria = testo

    if _ordine_stato_pct(stato_nuovo) >= _ordine_stato_pct(getattr(dep, "stato", "")):
        dep.stato = stato_nuovo or dep.stato
    dep.messaggio = f"[Auto PEC] {em.oggetto[:120]}".strip()


def _trova_match_deposito_email(fascicoli: List[object], em: EmailRicevuta) -> tuple[object, object] | tuple[None, None]:
    rg_email = _estrai_rg_email(em)
    best: tuple[int, object, object] | None = None

    for fasc in fascicoli:
        rg_ok = False
        identity_score = _score_fascicolo_email_identity(fasc, em)
        if rg_email:
            num_rg, anno_rg = rg_email
            rg_ok = (
                str(getattr(fasc, "numero_rg", "") or "").lstrip("0") == num_rg
                and str(getattr(fasc, "anno_rg", "") or "") == anno_rg
            )
        for dep in getattr(fasc, "depositi_pct", []) or []:
            score = 0
            token = (em.id_deposito_pct or "").upper()
            if token:
                if token in str(getattr(dep, "id", "") or "").upper():
                    score += 120
                if token in str(getattr(dep, "id_deposito_esterno", "") or "").upper():
                    score += 140
            if rg_ok:
                score += 60
            score += identity_score
            if str(getattr(dep, "stato", "") or "").upper() not in {
                "ACCETTATO_CANCELLERIA",
                "RIFIUTATO_CANCELLERIA",
                "ERRORE",
            }:
                score += 15
            if score <= 0:
                continue
            if (
                best is None
                or score > best[0]
                or (
                    score == best[0]
                    and str(getattr(dep, "timestamp", "") or "") > str(getattr(best[2], "timestamp", "") or "")
                )
            ):
                best = (score, fasc, dep)

    if best:
        return best[1], best[2]
    return None, None


def _email_e_comunicazione_cancelleria(em: EmailRicevuta) -> bool:
    if not _estrai_rg_email(em):
        return False
    testo = _corpo_normalizzato_email(em)
    if em.e_pst:
        return True
    if _email_da_canale_giustizia(em):
        return True
    return any(parola in testo for parola in _KEYWORDS_CANCELLERIA)


def _trova_fascicolo_da_email(fascicoli: List[object], em: EmailRicevuta):
    rg_email = _estrai_rg_email(em)
    if not rg_email:
        return None
    num_rg, anno_rg = rg_email
    best: tuple[int, object] | None = None
    for fasc in fascicoli:
        if not (
            str(getattr(fasc, "numero_rg", "") or "").lstrip("0") == num_rg
            and str(getattr(fasc, "anno_rg", "") or "") == anno_rg
        ):
            continue
        score = 100 + _score_fascicolo_email_identity(fasc, em)
        if best is None or score > best[0]:
            best = (score, fasc)
    return best[1] if best else None


def aggiorna_comunicazioni_cancelleria_da_email(
    gestione_email: GestioneEmailRicevute,
    gestione_fascicoli,
    fascicolo_id: str | None = None,
) -> dict:
    from pct.fascicoli import TipoAttivita, EsitoAttivita

    report = {"trovati": 0, "associati": 0, "duplicati": 0, "errori": 0}
    db = gestione_email._carica()
    emails = sorted(db.values(), key=lambda e: e.timestamp or e.ricevuta_il)
    fascicoli = gestione_fascicoli.tutti()
    if fascicolo_id:
        fascicoli = [fasc for fasc in fascicoli if getattr(fasc, "id", "") == fascicolo_id]

    for em in emails:
        if not _email_e_comunicazione_cancelleria(em):
            continue
        report["trovati"] += 1
        try:
            fascicolo = _trova_fascicolo_da_email(fascicoli, em)
            if not fascicolo:
                continue

            titolo_att = f"PEC: {em.oggetto}"[:120] if em.oggetto else "PEC: Comunicazione di cancelleria"
            data_att = (em.timestamp or datetime.now().isoformat())[:10]
            uid_imap = str(em.uid_imap or "")
            note_parts = []
            if em.message_id:
                note_parts.append(f"Message-ID: {em.message_id}")
            if em.allegati:
                note_parts.append(
                    "Allegati email: " + ", ".join(
                        (a.get("nome") or a.get("nome_file") or "allegato") for a in em.allegati
                    )
                )
            note_auto = "\n".join(note_parts).strip()

            att_esistente = next((
                att for att in (getattr(fascicolo, "attivita", None) or [])
                if getattr(att, "tipo", None) == TipoAttivita.COMUNICAZIONE_CANCELLERIA
                and (
                    (uid_imap and getattr(att, "email_uid_imap", "") == uid_imap)
                    or (getattr(att, "titolo", "") == titolo_att and getattr(att, "data", "") == data_att)
                )
            ), None)

            if att_esistente:
                needs_enrichment = any([
                    em.oggetto and not getattr(att_esistente, "email_oggetto", ""),
                    em.mittente and not getattr(att_esistente, "email_mittente", ""),
                    uid_imap and not getattr(att_esistente, "email_uid_imap", ""),
                    em.corpo_testo and not getattr(att_esistente, "email_testo", ""),
                    em.corpo_html and not getattr(att_esistente, "email_html", ""),
                    note_auto and note_auto not in (getattr(att_esistente, "note", "") or ""),
                ])
                if needs_enrichment:
                    note_finali = (getattr(att_esistente, "note", "") or "").strip()
                    if note_auto:
                        note_finali = "\n".join([p for p in [note_finali, note_auto] if p]).strip()
                    gestione_fascicoli.aggiorna_attivita(
                        fascicolo.id,
                        att_esistente.id,
                        descrizione=getattr(att_esistente, "descrizione", "") or f"Da: {em.mittente_nome or em.mittente}",
                        note=note_finali,
                        email_mittente=getattr(att_esistente, "email_mittente", "") or em.mittente,
                        email_oggetto=getattr(att_esistente, "email_oggetto", "") or em.oggetto,
                        email_uid_imap=getattr(att_esistente, "email_uid_imap", "") or uid_imap,
                        email_testo=getattr(att_esistente, "email_testo", "") or em.corpo_testo,
                        email_html=getattr(att_esistente, "email_html", "") or em.corpo_html,
                    )
                    report["associati"] += 1
                else:
                    report["duplicati"] += 1
                continue

            gestione_fascicoli.aggiungi_attivita(
                fascicolo.id,
                tipo=TipoAttivita.COMUNICAZIONE_CANCELLERIA,
                data=data_att,
                titolo=titolo_att,
                descrizione=f"Da: {em.mittente_nome or em.mittente}",
                esito=EsitoAttivita.NON_APPLICABILE,
                note=note_auto,
                email_mittente=em.mittente,
                email_oggetto=em.oggetto,
                email_uid_imap=uid_imap,
                email_testo=em.corpo_testo,
                email_html=em.corpo_html,
            )
            report["associati"] += 1
        except Exception:
            report["errori"] += 1

    return report


def sincronizza_pec_e_fascicoli(
    gestione_email: "GestioneEmailRicevute",
    gestione_fascicoli,
    config_pec: object,
    *,
    fascicolo_id: str | None = None,
    state_path: str = "",
    giorni_indietro: int = 30,
    limite: int = 100,
) -> dict:
    """
    Sincronizza la casella PEC e aggiorna fascicoli e comunicazioni di cancelleria
    con un workflow unico condiviso tra pagina email e fascicolo.
    """
    from pct.polling_depositi import poll_cancelleria_pec

    if not config_pec or not getattr(config_pec, "imap_host", ""):
        raise ValueError("PEC IMAP non configurata.")
    if not getattr(config_pec, "indirizzo", "") or not getattr(config_pec, "password", ""):
        raise ValueError("Credenziali PEC incomplete.")
    timeout_s = resolve_imap_timeout_seconds()

    sync_result = gestione_email.sincronizza_imap(
        imap_host=config_pec.imap_host,
        imap_port=int(getattr(config_pec, "imap_port", 993) or 993),
        username=config_pec.indirizzo,
        password=config_pec.password,
        use_ssl=bool(getattr(config_pec, "use_ssl", True)),
        cartelle_imap=cartelle_imap_standard(),
        limite=limite,
        timeout_seconds=timeout_s,
    )
    auto_log = aggiorna_esiti_da_email(
        gestione_email,
        gestione_fascicoli,
        fascicolo_id=fascicolo_id,
    )
    comm_report = aggiorna_comunicazioni_cancelleria_da_email(
        gestione_email,
        gestione_fascicoli,
        fascicolo_id=fascicolo_id,
    )
    try:
        poll_report_raw = poll_cancelleria_pec(
            gf=gestione_fascicoli,
            config_pec=config_pec,
            fascicolo_id=fascicolo_id,
            state_path=state_path,
            giorni_indietro=giorni_indietro,
            timeout_seconds=timeout_s,
        )
    except TypeError:
        # Compatibilità con mock/test legacy che espongono ancora la firma corta.
        poll_report_raw = poll_cancelleria_pec(
            gf=gestione_fascicoli,
            config_pec=config_pec,
            fascicolo_id=fascicolo_id,
            state_path=state_path,
            giorni_indietro=giorni_indietro,
        )
    poll_report = {
        "trovati": int(comm_report.get("trovati", 0)) + int((poll_report_raw or {}).get("trovati", 0)),
        "associati": int(comm_report.get("associati", 0)) + int((poll_report_raw or {}).get("associati", 0)),
        "duplicati": int(comm_report.get("duplicati", 0)) + int((poll_report_raw or {}).get("duplicati", 0)),
        "errori": int(comm_report.get("errori", 0)) + int((poll_report_raw or {}).get("errori", 0)),
        "da_email": comm_report,
        "poll_imap": poll_report_raw or {},
    }
    return {
        "sync": sync_result,
        "auto_esiti": auto_log,
        "poll": poll_report,
    }


def aggiorna_esiti_da_email(
    gestione_email: GestioneEmailRicevute,
    gestione_fascicoli,  # GestioneFascicoli — evita import circolare
    fascicolo_id: str | None = None,
) -> List[str]:
    """
    Scorre le email PST non ancora auto-registrate e aggiorna
    l'EsitoDepositoPCT nei fascicoli corrispondenti.

    Returns:
        Lista di messaggi di log (aggiornamenti effettuati).
    """
    log = []
    db = gestione_email._carica()

    pst_da_processare = sorted(
        [e for e in db.values() if e.e_pst and not e.auto_registrata],
        key=lambda e: e.timestamp or e.ricevuta_il,
    )

    tutti_fascicoli = gestione_fascicoli.tutti()
    if fascicolo_id:
        tutti_fascicoli = [fasc for fasc in tutti_fascicoli if getattr(fasc, "id", "") == fascicolo_id]

    for em in pst_da_processare:
        trovato = False
        try:
            fasc, dep = _trova_match_deposito_email(tutti_fascicoli, em)
            if fasc and dep:
                _aggiorna_ricevute_deposito_da_email(dep, em)
                gestione_fascicoli._salva()
                trovato = True
                log.append(
                    f"Fascicolo {fasc.numero}: deposito {getattr(dep, 'id', '')} → {em.stato_pct} "
                    f"(email: {em.oggetto[:60]})"
                )
        except Exception as exc:
            log.append(f"Errore auto-esito email {em.id}: {exc}")

        if trovato:
            em.auto_registrata = True
        else:
            log.append(f"Nessun deposito abbinato per email PST: {em.oggetto[:60]}")

    if pst_da_processare:
        gestione_email._salva()

    return log


def riassunto_auto_esiti(log: List[str]) -> dict:
    aggiornati = 0
    non_abbinati = 0
    errori = 0
    for entry in log or []:
        testo = str(entry or "").strip()
        if not testo:
            continue
        if testo.startswith("Nessun deposito abbinato"):
            non_abbinati += 1
        elif testo.lower().startswith("errore"):
            errori += 1
        else:
            aggiornati += 1
    return {
        "aggiornati": aggiornati,
        "non_abbinati": non_abbinati,
        "errori": errori,
        "totale": len(log or []),
    }
