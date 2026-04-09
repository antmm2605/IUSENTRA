"""
Client email completo per HACS — ricezione IMAP, gestione casella, auto-esito PCT.

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
import uuid
from datetime import datetime
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict


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

_RE_RG_PCT = re.compile(r"\bR\.?\s*G\.?\s+(\d+)\s*/\s*(\d{4})\b", re.IGNORECASE)
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

    # Allegati (solo nomi/dimensioni, non storicizziamo i file)
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
    Gestisce la casella email in HACS: ricezione, storage, ricerca.

    Storage: JSON flat file (stessa strategia del resto di HACS).
    """

    def __init__(self, db_path: str = "./email/casella.json"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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
    ) -> dict:
        """
        Scarica le email più recenti via IMAP e le salva nel database locale.

        Returns:
            {"nuove": int, "errori": int, "pst_trovate": int, "errore": str}
        """
        risultato = {"nuove": 0, "errori": 0, "pst_trovate": 0, "errore": ""}
        cartelle_imap = cartelle_imap or ["INBOX"]

        try:
            if use_ssl:
                mail = imaplib.IMAP4_SSL(imap_host, imap_port)
            else:
                mail = imaplib.IMAP4(imap_host, imap_port)
                mail.starttls()
            mail.login(username, password)
        except Exception as e:
            risultato["errore"] = f"Connessione IMAP fallita: {e}"
            return risultato

        db = self._carica()
        uid_esistenti = {e.uid_imap for e in db.values() if e.uid_imap}

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
                        if uid_str in uid_esistenti:
                            continue

                        try:
                            _, msg_data = mail.fetch(uid, "(RFC822)")
                            if not msg_data or not msg_data[0]:
                                continue

                            raw = msg_data[0][1]
                            if not isinstance(raw, bytes):
                                continue

                            parsed = email.message_from_bytes(raw)
                            em = self._parse_message(parsed, uid_str, cartella_imap)
                            if em:
                                # Auto-rileva risposte PST
                                self._analizza_pst(em)
                                db[em.id] = em
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
        self, msg: email.message.Message, uid_str: str, cartella_imap: str
    ) -> Optional[EmailRicevuta]:
        """Converte un messaggio IMAP in EmailRicevuta."""
        try:
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
                    if "attachment" in cd:
                        fname = self._decode_header_val(
                            part.get_filename() or ""
                        )
                        allegati.append({
                            "nome": fname or "allegato",
                            "mime": ct,
                            "size": len(part.get_payload(decode=True) or b""),
                        })
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
                id=uuid.uuid4().hex,
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


def sincronizza_pec_e_fascicoli(
    gestione_email: "GestioneEmailRicevute",
    gestione_fascicoli,
    config_pec: object,
    *,
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

    sync_result = gestione_email.sincronizza_imap(
        imap_host=config_pec.imap_host,
        imap_port=int(getattr(config_pec, "imap_port", 993) or 993),
        username=config_pec.indirizzo,
        password=config_pec.password,
        use_ssl=bool(getattr(config_pec, "use_ssl", True)),
        cartelle_imap=["INBOX"],
        limite=limite,
    )
    auto_log = aggiorna_esiti_da_email(gestione_email, gestione_fascicoli)
    try:
        poll_report = poll_cancelleria_pec(
            gf=gestione_fascicoli,
            config_pec=config_pec,
            state_path=state_path,
            giorni_indietro=giorni_indietro,
        )
    except TypeError:
        # Compatibilità con mock/test legacy che espongono ancora la firma corta.
        poll_report = poll_cancelleria_pec(
            gf=gestione_fascicoli,
            config_pec=config_pec,
            state_path=state_path,
        )
    return {
        "sync": sync_result,
        "auto_esiti": auto_log,
        "poll": poll_report,
    }


def aggiorna_esiti_da_email(
    gestione_email: GestioneEmailRicevute,
    gestione_fascicoli,  # GestioneFascicoli — evita import circolare
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

    for em in pst_da_processare:
        trovato = False
        try:
            tutti_fascicoli = gestione_fascicoli.tutti()
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

        em.auto_registrata = True
        if not trovato:
            log.append(f"Nessun deposito abbinato per email PST: {em.oggetto[:60]}")

    if pst_da_processare:
        gestione_email._salva()

    return log
