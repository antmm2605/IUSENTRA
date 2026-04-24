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
import json
import re
import socket
import uuid
import shutil
import unicodedata
from datetime import datetime
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

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
        cartella_email = self.attachments_dir / email_id
        cartella_email.mkdir(parents=True, exist_ok=True)

        nome_pulito = self._sanifica_nome_allegato(nome)
        target = cartella_email / nome_pulito
        stem = target.stem
        suffix = target.suffix
        idx = 1
        while target.exists():
            target = cartella_email / f"{stem}_{idx}{suffix}"
            idx += 1

        target.write_bytes(contenuto)
        return {
            "percorso_rel": str(target.relative_to(self.attachments_dir)).replace("\\", "/"),
            "nome_file": target.name,
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

    def _allegato_salvato(self, info: dict) -> bool:
        return self._percorso_allegato_da_info(info) is not None

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
            {"nuove": int, "errori": int, "pst_trovate": int, "allegati_salvati": int, "errore": str}
        """
        risultato = {"nuove": 0, "errori": 0, "pst_trovate": 0, "allegati_salvati": 0, "errore": ""}
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

        db = self._carica()
        email_per_uid = {e.uid_imap: e for e in db.values() if e.uid_imap}

        try:
            for cartella_imap in cartelle_imap:
                try:
                    status, _ = mail.select(cartella_imap, readonly=True)
                    if status != "OK":
                        continue

                    # Cerca ultime N email
                    _, data = mail.search(None, "ALL")
                    if not data or not data[0]:
                        continue

                    uid_list = data[0].decode().split()
                    uid_list = uid_list[-limite:]  # ultimi N

                    for uid in reversed(uid_list):
                        uid_str = f"{cartella_imap}:{uid}"
                        email_esistente = email_per_uid.get(uid_str)
                        ripara_allegati = bool(
                            email_esistente and self._email_ha_allegati_da_salvare(email_esistente)
                        )
                        if email_esistente and not ripara_allegati:
                            continue

                        try:
                            _, msg_data = mail.fetch(uid, "(RFC822)")
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
                            )
                            if em:
                                if email_esistente:
                                    salvati = self._merge_allegati_salvati(email_esistente, em)
                                    risultato["allegati_salvati"] += salvati
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

            self._salva()
            mail.logout()

        except Exception as e:
            risultato["errore"] = str(e)

        return risultato

    def sincronizza_inviati(self, messaggi_inviati: list) -> int:
        """
        Importa i messaggi email già inviati da messaggi.py nel database casella.
        Evita duplicati tramite sid_esterno/id.
        """
        db = self._carica()
        aggiunti = 0
        id_esistenti = set(db.keys())

        for msg in messaggi_inviati:
            em_id = f"INVIATA:{msg.id}"
            if em_id in id_esistenti:
                continue
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
                origine="INVIATA",
                ricevuta_il=getattr(msg, "inviato_il", "") or getattr(msg, "creato_il", ""),
            )
            db[em_id] = em
            aggiunti += 1

        if aggiunti:
            self._salva()
        return aggiunti

    # ---- Helpers privati ----

    @staticmethod
    def _decode_header_val(val: str) -> str:
        """Decodifica un header RFC 2047 in stringa Python."""
        if not val:
            return ""
        parts = decode_header(val)
        decoded = []
        for chunk, charset in parts:
            if isinstance(chunk, bytes):
                try:
                    decoded.append(chunk.decode(charset or "utf-8", errors="replace"))
                except Exception:
                    decoded.append(chunk.decode("latin-1", errors="replace"))
            else:
                decoded.append(str(chunk))
        return " ".join(decoded).strip()

    def _parse_message(
        self,
        msg: email.message.Message,
        uid_str: str,
        cartella_imap: str,
        *,
        email_id: str | None = None,
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

            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    cd = part.get("Content-Disposition", "")
                    fname = self._decode_header_val(part.get_filename() or "")
                    is_attachment = "attachment" in cd.lower() or ("inline" in cd.lower() and fname)
                    if is_attachment:
                        payload = part.get_payload(decode=True) or b""
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
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        corpo_testo = payload.decode(charset, errors="replace")
                    elif ct == "text/html" and not corpo_html:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        corpo_html = payload.decode(charset, errors="replace")
            else:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or "utf-8"
                if payload:
                    testo = payload.decode(charset, errors="replace")
                    if msg.get_content_type() == "text/html":
                        corpo_html = testo
                    else:
                        corpo_testo = testo

            cartella_interna = (
                CartellaEmail.INBOX if "inbox" in cartella_imap.lower() or cartella_imap == "INBOX"
                else CartellaEmail.INBOX
            )

            return EmailRicevuta(
                id=em_id,
                cartella=cartella_interna,
                stato=StatoEmail.NON_LETTA,
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
                origine="IMAP",
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
        corpo = (em.corpo_testo + em.corpo_html).upper()

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
        cartelle_imap=["INBOX"],
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
