"""
Sistema di messaggistica multicanale per lo studio legale.

Canali supportati:
  - Email   (SMTP)
  - SMS     (Twilio)
  - WhatsApp (Twilio WhatsApp Business API)

Funzionalità:
  - Template messaggi con variabili
  - Invio immediato e schedulato
  - Storico messaggi per cliente/fascicolo
  - Automazioni: reminder appuntamenti, avviso scadenze,
    aggiornamento stato fascicolo, richiesta documenti
  - Lettura ricevute (email bounce, SMS status, WA delivery)
"""

import json
import uuid
import re
from pct.config_studio import _SMTPv4, _SMTP_SSLv4, _crea_contesto_tls_sicuro, _msg_errore_rete
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr, getaddresses, make_msgid


# ------------------------------------------------------------------ Enums

class CanaleMsggio(str, Enum):
    EMAIL     = "EMAIL"
    SMS       = "SMS"
    WHATSAPP  = "WHATSAPP"


class StatoMessaggio(str, Enum):
    IN_CODA    = "IN_CODA"
    INVIATO    = "INVIATO"
    CONSEGNATO = "CONSEGNATO"
    LETTO      = "LETTO"
    FALLITO    = "FALLITO"
    ANNULLATO  = "ANNULLATO"


class TipoAutomazione(str, Enum):
    REMINDER_APPUNTAMENTO   = "REMINDER_APPUNTAMENTO"
    AVVISO_SCADENZA         = "AVVISO_SCADENZA"
    AGGIORNAMENTO_FASCICOLO = "AGGIORNAMENTO_FASCICOLO"
    RICHIESTA_DOCUMENTI     = "RICHIESTA_DOCUMENTI"
    BENVENUTO_CLIENTE       = "BENVENUTO_CLIENTE"
    SOLLECITO_PARCELLA      = "SOLLECITO_PARCELLA"
    COMUNICAZIONE_SENTENZA  = "COMUNICAZIONE_SENTENZA"
    PERSONALIZZATO          = "PERSONALIZZATO"


# ------------------------------------------------------------------ Config canali

@dataclass
class ConfigEmail:
    smtp_host: str = ""
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    mittente_nome: str = "Studio Legale"
    mittente_email: str = ""
    reply_to: str = ""


@dataclass
class ConfigTwilio:
    account_sid: str = ""
    auth_token: str = ""
    numero_sms: str = ""          # es. +39XXXXXXXXXX
    numero_whatsapp: str = ""     # es. whatsapp:+14155238886


@dataclass
class ConfigMessaggistica:
    email: ConfigEmail = field(default_factory=ConfigEmail)
    twilio: ConfigTwilio = field(default_factory=ConfigTwilio)
    studio_nome: str = "Studio Legale"
    studio_firma: str = ""


# ------------------------------------------------------------------ Messaggio

@dataclass
class Allegato:
    nome: str
    percorso: str
    mime_type: str = "application/octet-stream"


@dataclass
class Messaggio:
    """Singolo messaggio inviato o schedulato."""
    id: str
    canale: CanaleMsggio
    stato: StatoMessaggio

    # destinatario
    id_cliente: str = ""
    nome_destinatario: str = ""
    email_destinatario: str = ""
    telefono_destinatario: str = ""   # formato E.164: +39XXXXXXXXXX

    # contenuto
    oggetto: str = ""                 # solo email
    corpo: str = ""
    corpo_html: str = ""              # solo email
    allegati: List[str] = field(default_factory=list)  # percorsi file

    # metadati
    tipo_automazione: str = ""
    id_fascicolo: str = ""
    id_appuntamento: str = ""
    sid_esterno: str = ""             # Twilio SID o message-id email
    errore: str = ""
    note: str = ""

    # date
    creato_il: str = field(default_factory=lambda: datetime.now().isoformat())
    inviato_il: str = ""
    schedulato_per: str = ""          # ISO datetime per invio futuro

    def to_dict(self) -> dict:
        d = asdict(self)
        d["canale"] = self.canale.value
        d["stato"] = self.stato.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Messaggio":
        d = dict(d)
        d["canale"] = CanaleMsggio(d["canale"])
        d["stato"] = StatoMessaggio(d["stato"])
        return cls(**d)


# ------------------------------------------------------------------ Template

TEMPLATES: Dict[str, Dict[str, str]] = {
    # ---- Reminder appuntamento ----
    TipoAutomazione.REMINDER_APPUNTAMENTO.value: {
        "oggetto": "Promemoria appuntamento — {data}",
        "sms": (
            "Gentile {nome}, le ricordiamo l'appuntamento con lo Studio {studio} "
            "il {data} alle {ora}. Per info: {telefono_studio}."
        ),
        "whatsapp": (
            "Gentile *{nome}*,\n\n"
            "Le ricordiamo l'appuntamento con lo *Studio {studio}*:\n\n"
            "📅 *Data:* {data}\n"
            "⏰ *Ora:* {ora}\n"
            "📍 *Luogo:* {luogo}\n\n"
            "Per disdire o modificare risponda a questo messaggio.\n\n"
            "_Studio {studio}_"
        ),
        "email_html": """
<p>Gentile <strong>{nome}</strong>,</p>
<p>Le ricordiamo il suo appuntamento:</p>
<table style="border-collapse:collapse;margin:16px 0">
  <tr><td style="padding:6px 12px;color:#666">📅 Data</td>
      <td style="padding:6px 12px;font-weight:bold">{data}</td></tr>
  <tr><td style="padding:6px 12px;color:#666">⏰ Ora</td>
      <td style="padding:6px 12px;font-weight:bold">{ora}</td></tr>
  <tr><td style="padding:6px 12px;color:#666">📍 Luogo</td>
      <td style="padding:6px 12px">{luogo}</td></tr>
</table>
<p>Per disdire o modificare l'appuntamento la preghiamo di contattarci.</p>
""",
    },

    # ---- Avviso scadenza ----
    TipoAutomazione.AVVISO_SCADENZA.value: {
        "oggetto": "Scadenza imminente — Fascicolo {numero_fascicolo}",
        "sms": (
            "Studio {studio}: scadenza il {data} per il Suo fascicolo "
            "n. {numero_fascicolo}. Contatti il Suo avvocato."
        ),
        "whatsapp": (
            "Gentile *{nome}*,\n\n"
            "⚠️ *Scadenza imminente* per il Suo fascicolo "
            "n. *{numero_fascicolo}*:\n\n"
            "📅 *Data scadenza:* {data}\n"
            "📋 *Oggetto:* {oggetto_scadenza}\n\n"
            "Si prega di contattare il Suo avvocato.\n\n"
            "_Studio {studio}_"
        ),
        "email_html": """
<p>Gentile <strong>{nome}</strong>,</p>
<p>Le comunichiamo che è in scadenza la seguente attività:</p>
<table style="border-collapse:collapse;margin:16px 0">
  <tr><td style="padding:6px 12px;color:#666">Fascicolo</td>
      <td style="padding:6px 12px;font-weight:bold">{numero_fascicolo}</td></tr>
  <tr><td style="padding:6px 12px;color:#666">Scadenza</td>
      <td style="padding:6px 12px;font-weight:bold;color:#c62828">{data}</td></tr>
  <tr><td style="padding:6px 12px;color:#666">Oggetto</td>
      <td style="padding:6px 12px">{oggetto_scadenza}</td></tr>
</table>
<p>La preghiamo di mettersi in contatto con il Suo avvocato.</p>
""",
    },

    # ---- Aggiornamento fascicolo ----
    TipoAutomazione.AGGIORNAMENTO_FASCICOLO.value: {
        "oggetto": "Aggiornamento pratica — {numero_fascicolo}",
        "sms": (
            "Studio {studio}: aggiornamento pratica {numero_fascicolo}: "
            "{aggiornamento}. Per info: {telefono_studio}."
        ),
        "whatsapp": (
            "Gentile *{nome}*,\n\n"
            "📋 *Aggiornamento sulla Sua pratica* n. *{numero_fascicolo}*:\n\n"
            "{aggiornamento}\n\n"
            "Per ulteriori informazioni la preghiamo di contattarci.\n\n"
            "_Studio {studio}_"
        ),
        "email_html": """
<p>Gentile <strong>{nome}</strong>,</p>
<p>La informiamo di un aggiornamento relativo alla Sua pratica
   <strong>{numero_fascicolo}</strong>:</p>
<blockquote style="border-left:4px solid #1a3a5c;padding:8px 16px;margin:16px 0;
                   background:#f0f4f8;border-radius:4px">
  {aggiornamento}
</blockquote>
<p>Per ulteriori informazioni si prega di contattare il proprio avvocato.</p>
""",
    },

    # ---- Benvenuto cliente ----
    TipoAutomazione.BENVENUTO_CLIENTE.value: {
        "oggetto": "Benvenuto allo Studio {studio}",
        "sms": (
            "Benvenuto allo Studio {studio}, {nome}! "
            "Il Suo avvocato di riferimento è {avvocato}. "
            "Per info: {telefono_studio}."
        ),
        "whatsapp": (
            "Gentile *{nome}*,\n\n"
            "🤝 Benvenuto allo *Studio {studio}*!\n\n"
            "Il Suo avvocato di riferimento è *{avvocato}*.\n"
            "Per qualsiasi comunicazione non esiti a contattarci:\n"
            "📞 {telefono_studio}\n"
            "✉️ {email_studio}\n\n"
            "_Studio {studio}_"
        ),
        "email_html": """
<p>Gentile <strong>{nome}</strong>,</p>
<p>La ringraziamo per la fiducia accordata allo <strong>Studio {studio}</strong>.</p>
<p>Il Suo avvocato di riferimento sarà <strong>{avvocato}</strong>.</p>
<p>Per qualsiasi necessità può contattarci:</p>
<ul>
  <li>📞 {telefono_studio}</li>
  <li>✉️ {email_studio}</li>
</ul>
""",
    },

    # ---- Richiesta documenti ----
    TipoAutomazione.RICHIESTA_DOCUMENTI.value: {
        "oggetto": "Richiesta documentazione — {numero_fascicolo}",
        "sms": (
            "Studio {studio}: per la pratica {numero_fascicolo} "
            "sono necessari i seguenti documenti: {documenti}."
        ),
        "whatsapp": (
            "Gentile *{nome}*,\n\n"
            "📎 Per proseguire con la pratica *{numero_fascicolo}* "
            "abbiamo necessità dei seguenti documenti:\n\n"
            "{documenti}\n\n"
            "La preghiamo di farli pervenire entro il *{scadenza}*.\n\n"
            "_Studio {studio}_"
        ),
        "email_html": """
<p>Gentile <strong>{nome}</strong>,</p>
<p>Per proseguire con la pratica <strong>{numero_fascicolo}</strong>
   abbiamo necessità della seguente documentazione:</p>
<ul>{documenti_html}</ul>
<p>La preghiamo di trasmettere i documenti entro il <strong>{scadenza}</strong>.</p>
""",
    },

    # ---- Sollecito parcella ----
    TipoAutomazione.SOLLECITO_PARCELLA.value: {
        "oggetto": "Sollecito di pagamento — Fattura {numero_fattura}",
        "sms": (
            "Studio {studio}: La informiamo che risulta ancora aperta "
            "la fattura n. {numero_fattura} di € {importo}. "
            "La preghiamo di provvedere al pagamento."
        ),
        "whatsapp": (
            "Gentile *{nome}*,\n\n"
            "💳 La informiamo che risulta ancora aperta:\n\n"
            "📄 *Fattura:* {numero_fattura}\n"
            "💰 *Importo:* € {importo}\n"
            "📅 *Scadenza:* {scadenza_pagamento}\n\n"
            "La preghiamo di provvedere al pagamento o contattarci.\n\n"
            "_Studio {studio}_"
        ),
        "email_html": """
<p>Gentile <strong>{nome}</strong>,</p>
<p>La informiamo che risulta ancora aperta la seguente posizione:</p>
<table style="border-collapse:collapse;margin:16px 0">
  <tr><td style="padding:6px 12px;color:#666">Fattura n.</td>
      <td style="padding:6px 12px;font-weight:bold">{numero_fattura}</td></tr>
  <tr><td style="padding:6px 12px;color:#666">Importo</td>
      <td style="padding:6px 12px;font-weight:bold">€ {importo}</td></tr>
  <tr><td style="padding:6px 12px;color:#666">Scadenza</td>
      <td style="padding:6px 12px;color:#c62828">{scadenza_pagamento}</td></tr>
</table>
<p>La preghiamo di provvedere al pagamento o di contattarci per concordare
   modalità alternative.</p>
""",
    },
}


def _render(template: str, **vars) -> str:
    """Sostituisce {variabili} nel template."""
    try:
        return template.format(**vars)
    except KeyError:
        # ignora variabili mancanti
        for k, v in vars.items():
            template = template.replace("{" + k + "}", str(v))
        return template


# ------------------------------------------------------------------ Repository

class GestioneMessaggi:
    """
    Repository messaggi e motore di invio multicanale.
    Persiste lo storico su JSON, invia via SMTP/Twilio.
    """

    def __init__(
        self,
        config: ConfigMessaggistica,
        db_path: str = "./messaggi/storico.json",
        studio_db=None,
    ):
        self.config = config
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._studio_db = studio_db
        self._messaggi: dict[str, Messaggio] = {}
        self._carica()

    # ---------------------------------------------------------------- I/O

    def _carica(self) -> None:
        if self._studio_db is not None:
            import json as _json
            try:
                rows = self._studio_db.conn.execute(
                    "SELECT * FROM messaggi"
                ).fetchall()
                self._messaggi = {}
                for row in rows:
                    d = dict(row)
                    dati = d.get("dati_json")
                    try:
                        payload = _json.loads(dati) if dati else d
                        m = Messaggio.from_dict(payload)
                        self._messaggi[m.id] = m
                    except Exception:
                        pass
            except Exception:
                self._messaggi = {}
            return
        from pct import cache as _cache
        raw = _cache.load(self.db_path)
        self._messaggi = {k: Messaggio.from_dict(v) for k, v in raw.items()}

    def _salva(self) -> None:
        if self._studio_db is not None:
            import json as _json

            def _insert(conn, m):
                d = m.to_dict()
                conn.execute(
                    """
                    INSERT INTO messaggi
                    (id, canale, stato, oggetto, corpo,
                     email_destinatario, telefono_destinatario,
                     id_cliente, id_fascicolo, tipo_automazione,
                     inviato_il, errore_invio, creato_il, dati_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        m.id, m.canale.value, m.stato.value,
                        m.oggetto, m.corpo,
                        m.email_destinatario, m.telefono_destinatario,
                        m.id_cliente or None,
                        m.id_fascicolo or None,
                        m.tipo_automazione,
                        m.inviato_il,
                        m.errore,
                        m.creato_il,
                        _json.dumps(d, ensure_ascii=False),
                    ),
                )

            self._studio_db.salva_tabella("messaggi", list(self._messaggi.values()), _insert)
            return
        from pct import cache as _cache
        _cache.save(self.db_path, {k: v.to_dict() for k, v in self._messaggi.items()})

    # ---------------------------------------------------------------- Invio email

    def invia_email(
        self,
        destinatario: str,
        oggetto: str,
        corpo_testo: str,
        corpo_html: str = "",
        allegati: Optional[List[str]] = None,
        id_cliente: str = "",
        nome_destinatario: str = "",
        tipo_automazione: str = "",
        id_fascicolo: str = "",
    ) -> Messaggio:
        """Invia un'email e registra il messaggio."""
        msg = self._crea_messaggio(
            canale=CanaleMsggio.EMAIL,
            id_cliente=id_cliente,
            nome_destinatario=nome_destinatario,
            email_destinatario=destinatario,
            oggetto=oggetto,
            corpo=corpo_testo,
            corpo_html=corpo_html,
            allegati=allegati or [],
            tipo_automazione=tipo_automazione,
            id_fascicolo=id_fascicolo,
        )

        try:
            if not self.config or not getattr(self.config, "email", None):
                raise ValueError("Configurazione email non presente.")
            email_cfg = self.config.email
            sender = email_cfg.mittente_email or email_cfg.username
            recipients = [
                address
                for _name, address in getaddresses([destinatario])
                if address
            ]
            if not email_cfg.smtp_host:
                raise ValueError("Server SMTP non configurato.")
            if not sender or not email_cfg.username:
                raise ValueError("Indirizzo PEC mittente non configurato.")
            if not email_cfg.password:
                raise ValueError("Password PEC non configurata sul backend dello studio.")
            if not recipients:
                raise ValueError("Destinatario non valido.")

            has_attachments = bool(allegati)
            mime = MIMEMultipart("mixed" if has_attachments else "alternative")
            mime["From"] = formataddr((email_cfg.mittente_nome or "", sender))
            mime["To"] = ", ".join(recipients)
            mime["Subject"] = oggetto
            mime["Message-ID"] = make_msgid()
            if email_cfg.reply_to:
                mime["Reply-To"] = email_cfg.reply_to

            body_container = MIMEMultipart("alternative") if has_attachments else mime
            body_container.attach(MIMEText(corpo_testo, "plain", "utf-8"))
            if corpo_html:
                html_completo = self._wrap_html(corpo_html, oggetto)
                body_container.attach(MIMEText(html_completo, "html", "utf-8"))
            if has_attachments:
                mime.attach(body_container)

            for percorso in (allegati or []):
                p = Path(percorso)
                if p.exists():
                    with open(p, "rb") as fh:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(fh.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition",
                                    f'attachment; filename="{p.name}"')
                    mime.attach(part)

            ctx = _crea_contesto_tls_sicuro()
            if email_cfg.use_tls:
                smtp = _SMTPv4(email_cfg.smtp_host, email_cfg.smtp_port, timeout=30)
                smtp.starttls(context=ctx)
            else:
                smtp = _SMTP_SSLv4(email_cfg.smtp_host, email_cfg.smtp_port, context=ctx, timeout=30)

            smtp.login(email_cfg.username, email_cfg.password)
            smtp.send_message(mime, from_addr=sender, to_addrs=recipients)
            smtp.quit()

            msg.stato = StatoMessaggio.INVIATO
            msg.inviato_il = datetime.now().isoformat()
            msg.sid_esterno = mime.get("Message-ID", "")

        except Exception as e:
            msg.stato = StatoMessaggio.FALLITO
            msg.errore = _msg_errore_rete(e, "Invio PEC backend")

        self._messaggi[msg.id] = msg
        self._salva()
        return msg

    def registra_email_inviata(
        self,
        destinatario: str,
        oggetto: str,
        corpo_testo: str = "",
        corpo_html: str = "",
        allegati: Optional[List[str]] = None,
        id_cliente: str = "",
        nome_destinatario: str = "",
        tipo_automazione: str = "",
        id_fascicolo: str = "",
        message_id: str = "",
        note: str = "",
    ) -> Messaggio:
        """Registra un'email gia' inviata da un canale esterno verificato."""
        msg = self._crea_messaggio(
            canale=CanaleMsggio.EMAIL,
            id_cliente=id_cliente,
            nome_destinatario=nome_destinatario,
            email_destinatario=destinatario,
            oggetto=oggetto,
            corpo=corpo_testo,
            corpo_html=corpo_html,
            allegati=allegati or [],
            tipo_automazione=tipo_automazione,
            id_fascicolo=id_fascicolo,
        )
        msg.stato = StatoMessaggio.INVIATO
        msg.inviato_il = datetime.now().isoformat()
        msg.sid_esterno = str(message_id or "").strip()
        msg.note = str(note or "").strip()
        self._messaggi[msg.id] = msg
        self._salva()
        return msg

    # ---------------------------------------------------------------- Invio SMS

    def invia_sms(
        self,
        telefono: str,
        testo: str,
        id_cliente: str = "",
        nome_destinatario: str = "",
        tipo_automazione: str = "",
        id_fascicolo: str = "",
    ) -> Messaggio:
        """Invia un SMS tramite Twilio."""
        msg = self._crea_messaggio(
            canale=CanaleMsggio.SMS,
            id_cliente=id_cliente,
            nome_destinatario=nome_destinatario,
            telefono_destinatario=telefono,
            corpo=testo,
            tipo_automazione=tipo_automazione,
            id_fascicolo=id_fascicolo,
        )

        try:
            client = self._twilio_client()
            twilio_msg = client.messages.create(
                body=testo,
                from_=self.config.twilio.numero_sms,
                to=telefono,
            )
            msg.stato = StatoMessaggio.INVIATO
            msg.inviato_il = datetime.now().isoformat()
            msg.sid_esterno = twilio_msg.sid

        except Exception as e:
            msg.stato = StatoMessaggio.FALLITO
            msg.errore = str(e)

        self._messaggi[msg.id] = msg
        self._salva()
        return msg

    # ---------------------------------------------------------------- Invio WhatsApp

    def invia_whatsapp(
        self,
        telefono: str,
        testo: str,
        id_cliente: str = "",
        nome_destinatario: str = "",
        tipo_automazione: str = "",
        id_fascicolo: str = "",
    ) -> Messaggio:
        """Invia un messaggio WhatsApp tramite Twilio, o genera link WhatsApp Web se non configurato."""
        msg = self._crea_messaggio(
            canale=CanaleMsggio.WHATSAPP,
            id_cliente=id_cliente,
            nome_destinatario=nome_destinatario,
            telefono_destinatario=telefono,
            corpo=testo,
            tipo_automazione=tipo_automazione,
            id_fascicolo=id_fascicolo,
        )

        # Fallback WhatsApp Web se Twilio non è configurato
        if not (self.config.twilio.account_sid and self.config.twilio.auth_token):
            from pct.notifiche_wa import wa_link as _wa_link
            msg.sid_esterno = _wa_link(telefono, testo)
            msg.note = "WhatsApp Web — invio manuale tramite browser"
            self._messaggi[msg.id] = msg
            self._salva()
            return msg

        try:
            client = self._twilio_client()
            wa_from = self.config.twilio.numero_whatsapp
            wa_to = (telefono if telefono.startswith("whatsapp:")
                     else f"whatsapp:{telefono}")
            twilio_msg = client.messages.create(
                body=testo,
                from_=wa_from,
                to=wa_to,
            )
            msg.stato = StatoMessaggio.INVIATO
            msg.inviato_il = datetime.now().isoformat()
            msg.sid_esterno = twilio_msg.sid

        except Exception as e:
            msg.stato = StatoMessaggio.FALLITO
            msg.errore = str(e)

        self._messaggi[msg.id] = msg
        self._salva()
        return msg

    # ---------------------------------------------------------------- Automazioni

    def invia_da_template(
        self,
        tipo: TipoAutomazione,
        canali: List[CanaleMsggio],
        variabili: dict,
        destinatario_email: str = "",
        destinatario_telefono: str = "",
        id_cliente: str = "",
        nome_destinatario: str = "",
        id_fascicolo: str = "",
        allegati: Optional[List[str]] = None,
    ) -> List[Messaggio]:
        """
        Invia un messaggio da template su tutti i canali specificati.

        Args:
            tipo: tipo di automazione
            canali: lista di canali (EMAIL, SMS, WHATSAPP)
            variabili: dizionario con i valori da sostituire nel template
            ...

        Returns:
            Lista di messaggi inviati
        """
        tmpl = TEMPLATES.get(tipo.value, {})
        # variabili comuni
        variabili.setdefault("studio", self.config.studio_nome)
        variabili.setdefault("nome", nome_destinatario)

        inviati = []

        for canale in canali:
            if canale == CanaleMsggio.EMAIL and destinatario_email:
                oggetto = _render(tmpl.get("oggetto", tipo.value), **variabili)
                html = _render(tmpl.get("email_html", ""), **variabili)
                corpo_txt = re.sub(r"<[^>]+>", "", html).strip()
                if self.config.studio_firma:
                    corpo_txt += f"\n\n{self.config.studio_firma}"
                msg = self.invia_email(
                    destinatario=destinatario_email,
                    oggetto=oggetto,
                    corpo_testo=corpo_txt,
                    corpo_html=html,
                    allegati=allegati,
                    id_cliente=id_cliente,
                    nome_destinatario=nome_destinatario,
                    tipo_automazione=tipo.value,
                    id_fascicolo=id_fascicolo,
                )
                inviati.append(msg)

            elif canale == CanaleMsggio.SMS and destinatario_telefono:
                testo = _render(tmpl.get("sms", tipo.value), **variabili)
                msg = self.invia_sms(
                    telefono=destinatario_telefono,
                    testo=testo,
                    id_cliente=id_cliente,
                    nome_destinatario=nome_destinatario,
                    tipo_automazione=tipo.value,
                    id_fascicolo=id_fascicolo,
                )
                inviati.append(msg)

            elif canale == CanaleMsggio.WHATSAPP and destinatario_telefono:
                testo = _render(tmpl.get("whatsapp", tipo.value), **variabili)
                msg = self.invia_whatsapp(
                    telefono=destinatario_telefono,
                    testo=testo,
                    id_cliente=id_cliente,
                    nome_destinatario=nome_destinatario,
                    tipo_automazione=tipo.value,
                    id_fascicolo=id_fascicolo,
                )
                inviati.append(msg)

        return inviati

    def schedula(
        self,
        tipo: TipoAutomazione,
        canali: List[CanaleMsggio],
        variabili: dict,
        quando: datetime,
        **kwargs,
    ) -> Messaggio:
        """
        Schedula un messaggio per invio futuro.
        Il dispatcher (run_scheduled) processerà i messaggi in coda.
        """
        msg = self._crea_messaggio(
            canale=canali[0],
            tipo_automazione=tipo.value,
            corpo=json.dumps({"canali": [c.value for c in canali],
                              "variabili": variabili, "kwargs": kwargs}),
            schedulato_per=quando.isoformat(),
            **{k: v for k, v in kwargs.items() if hasattr(Messaggio, k)},
        )
        msg.stato = StatoMessaggio.IN_CODA
        self._messaggi[msg.id] = msg
        self._salva()
        return msg

    def processa_schedulati(self) -> List[Messaggio]:
        """
        Elabora tutti i messaggi schedulati il cui orario è passato.
        Da chiamare periodicamente (es. ogni minuto con APScheduler).
        """
        adesso = datetime.now().isoformat()
        da_inviare = [
            m for m in self._messaggi.values()
            if m.stato == StatoMessaggio.IN_CODA
            and m.schedulato_per
            and m.schedulato_per <= adesso
        ]
        risultati = []
        for msg in da_inviare:
            try:
                payload = json.loads(msg.corpo)
                canali = [CanaleMsggio(c) for c in payload["canali"]]
                kw = payload.get("kwargs", {})
                inviati = self.invia_da_template(
                    tipo=TipoAutomazione(msg.tipo_automazione),
                    canali=canali,
                    variabili=payload["variabili"],
                    id_cliente=msg.id_cliente,
                    nome_destinatario=msg.nome_destinatario,
                    destinatario_email=kw.get("destinatario_email", ""),
                    destinatario_telefono=kw.get("destinatario_telefono", ""),
                    id_fascicolo=msg.id_fascicolo,
                )
                risultati.extend(inviati)
                msg.stato = StatoMessaggio.INVIATO
                msg.inviato_il = datetime.now().isoformat()
            except Exception as e:
                msg.stato = StatoMessaggio.FALLITO
                msg.errore = str(e)
        self._salva()
        return risultati

    def aggiorna_stato_twilio(self, sid: str) -> Optional[Messaggio]:
        """Aggiorna lo stato di un messaggio SMS/WA da Twilio."""
        msg = next((m for m in self._messaggi.values()
                    if m.sid_esterno == sid), None)
        if not msg:
            return None
        try:
            client = self._twilio_client()
            twilio_msg = client.messages(sid).fetch()
            stato_map = {
                "delivered": StatoMessaggio.CONSEGNATO,
                "read": StatoMessaggio.LETTO,
                "failed": StatoMessaggio.FALLITO,
                "undelivered": StatoMessaggio.FALLITO,
                "sent": StatoMessaggio.INVIATO,
            }
            msg.stato = stato_map.get(twilio_msg.status, msg.stato)
            if twilio_msg.error_message:
                msg.errore = twilio_msg.error_message
        except Exception:
            pass
        self._salva()
        return msg

    # ---------------------------------------------------------------- Query

    def get(self, id_msg: str) -> Optional[Messaggio]:
        return self._messaggi.get(id_msg)

    def elimina(self, id_msg: str):
        """Rimuove un messaggio dallo storico."""
        if id_msg not in self._messaggi:
            raise ValueError(f"Messaggio {id_msg!r} non trovato")
        del self._messaggi[id_msg]
        self._salva()

    def per_cliente(self, id_cliente: str) -> List[Messaggio]:
        return sorted(
            [m for m in self._messaggi.values() if m.id_cliente == id_cliente],
            key=lambda m: m.creato_il,
            reverse=True,
        )

    def per_fascicolo(self, id_fascicolo: str) -> List[Messaggio]:
        return sorted(
            [m for m in self._messaggi.values() if m.id_fascicolo == id_fascicolo],
            key=lambda m: m.creato_il,
            reverse=True,
        )

    def tutti(
        self,
        canale: Optional[CanaleMsggio] = None,
        stato: Optional[StatoMessaggio] = None,
        da: Optional[date] = None,
        a: Optional[date] = None,
    ) -> List[Messaggio]:
        msgs = sorted(self._messaggi.values(),
                      key=lambda m: m.creato_il, reverse=True)
        if canale:
            msgs = [m for m in msgs if m.canale == canale]
        if stato:
            msgs = [m for m in msgs if m.stato == stato]
        if da:
            msgs = [m for m in msgs if m.creato_il[:10] >= da.isoformat()]
        if a:
            msgs = [m for m in msgs if m.creato_il[:10] <= a.isoformat()]
        return msgs

    def statistiche(self) -> dict:
        tutti = list(self._messaggi.values())
        return {
            "totale": len(tutti),
            "inviati": sum(1 for m in tutti if m.stato == StatoMessaggio.INVIATO),
            "consegnati": sum(1 for m in tutti if m.stato == StatoMessaggio.CONSEGNATO),
            "falliti": sum(1 for m in tutti if m.stato == StatoMessaggio.FALLITO),
            "in_coda": sum(1 for m in tutti if m.stato == StatoMessaggio.IN_CODA),
            "per_canale": {
                c.value: sum(1 for m in tutti if m.canale == c)
                for c in CanaleMsggio
            },
        }

    # ---------------------------------------------------------------- Helpers

    def _crea_messaggio(self, canale: CanaleMsggio, **kwargs) -> Messaggio:
        return Messaggio(
            id=uuid.uuid4().hex[:8].upper(),
            canale=canale,
            stato=StatoMessaggio.IN_CODA,
            **kwargs,
        )

    def _twilio_client(self):
        try:
            from twilio.rest import Client
        except ImportError:
            raise RuntimeError("twilio non installato. Eseguire: pip install twilio")
        return Client(self.config.twilio.account_sid,
                      self.config.twilio.auth_token)

    def _wrap_html(self, corpo: str, titolo: str = "") -> str:
        """Avvolge il corpo HTML in un template email responsive."""
        return f"""<!DOCTYPE html>
<html lang="it">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{titolo}</title></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0">
  <tr><td align="center" style="padding:24px 16px">
    <table width="600" cellpadding="0" cellspacing="0"
           style="background:#fff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.08)">
      <tr><td style="background:#1a3a5c;padding:20px 32px;border-radius:8px 8px 0 0">
        <span style="color:#fff;font-size:18px;font-weight:bold">
          {self.config.studio_nome}
        </span>
      </td></tr>
      <tr><td style="padding:32px;color:#333;font-size:14px;line-height:1.6">
        {corpo}
        {f'<hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0"><p style="color:#888;font-size:12px">{self.config.studio_firma}</p>' if self.config.studio_firma else ''}
      </td></tr>
      <tr><td style="background:#f4f6f9;padding:16px 32px;border-radius:0 0 8px 8px;
                     color:#aaa;font-size:11px;text-align:center">
        {self.config.studio_nome} — Comunicazione riservata
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""

    @staticmethod
    def valida_telefono(tel: str) -> bool:
        """Valida formato E.164 (+39XXXXXXXXXX)."""
        return bool(re.match(r"^\+[1-9]\d{6,14}$", tel.strip()))

    @staticmethod
    def valida_email(email: str) -> bool:
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


# ------------------------------------------------------------------ Scheduler (APScheduler)

def avvia_scheduler(gm: "GestioneMessaggi", intervallo_minuti: int = 1):
    """
    Avvia APScheduler per processare messaggi schedulati e automazioni.
    Restituisce lo scheduler (da tenere in vita nel processo principale).
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        raise RuntimeError("apscheduler non installato. Eseguire: pip install apscheduler")

    scheduler = BackgroundScheduler(timezone="Europe/Rome")

    # Processa messaggi schedulati ogni minuto
    scheduler.add_job(
        gm.processa_schedulati,
        "interval",
        minutes=intervallo_minuti,
        id="processa_schedulati",
        replace_existing=True,
    )

    scheduler.start()
    return scheduler


# Alias per backward compat
GestioneMessaggistica = GestioneMessaggi
