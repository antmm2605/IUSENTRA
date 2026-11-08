"""
Gestione invio PEC (Posta Elettronica Certificata) per il deposito PCT.
"""

import smtplib
import email
import imaplib
from pct.config_studio import _SMTPv4, _SMTP_SSLv4
import time
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class ConfigPEC:
    """Configurazione account PEC."""

    indirizzo: str
    password: str
    smtp_host: str
    smtp_port: int = 465
    imap_host: str = ""
    imap_port: int = 993
    use_ssl: bool = True


class ClientPEC:
    """
    Client per l'invio e la ricezione di PEC nel contesto del PCT.

    Il deposito avviene inviando la busta telematica (.enc) come allegato
    all'indirizzo PEC dell'ufficio giudiziario competente.
    """

    # Formato oggetto PEC conforme D.M. 44/2011 art. 14 comma 3
    # Il portale PST riconosce automaticamente i depositi dall'oggetto
    SUBJECT_DEPOSITO = "DEPOSITO TELEMATICO"
    TIMEOUT_RICEVUTA = 300  # 5 minuti

    def __init__(self, config: ConfigPEC):
        self.config = config

    def invia_busta(
        self,
        destinatario_pec: str,
        busta_path: str,
        oggetto: Optional[str] = None,
        corpo: Optional[str] = None,
    ) -> dict:
        """
        Invia la busta telematica all'indirizzo PEC dell'ufficio giudiziario.

        Args:
            destinatario_pec: Indirizzo PEC dell'ufficio giudiziario
            busta_path: Percorso alla busta telematica (.enc)
            oggetto: Oggetto del messaggio (default: "DEPOSITO")
            corpo: Corpo del messaggio

        Returns:
            Dizionario con esito invio e ID messaggio
        """
        msg = MIMEMultipart()
        msg["From"] = self.config.indirizzo
        msg["To"] = destinatario_pec
        msg["Subject"] = oggetto or self.SUBJECT_DEPOSITO
        # Message-ID fissato da chi invia: le ricevute del gestore lo riportano in
        # X-Riferimento-Message-ID (d.m. 2/11/2005) ed EsitoAtto.xml in IdMsgMitt; e' l'unico
        # aggancio certo tra il deposito e le sue ricevute.
        dominio = (self.config.indirizzo.rpartition("@")[2] or "localhost").strip() or "localhost"
        msg["Message-ID"] = make_msgid(domain=dominio)
        msg["Date"] = formatdate(localtime=True)

        corpo_testo = corpo or (
            "Deposito telematico tramite PCT.\n"
            "Si allega la busta telematica per il deposito.\n\n"
            "Inviato tramite sistema di deposito telematico."
        )
        msg.attach(MIMEText(corpo_testo, "plain", "utf-8"))

        # Allega la busta telematica
        busta_nome = Path(busta_path).name
        with open(busta_path, "rb") as f:
            allegato = MIMEBase("application", "octet-stream")
            allegato.set_payload(f.read())
            encoders.encode_base64(allegato)
            allegato.add_header(
                "Content-Disposition", f'attachment; filename="{busta_nome}"'
            )
            msg.attach(allegato)

        risultato = {"inviato": False, "message_id": None, "errore": None}

        try:
            if self.config.use_ssl:
                server = _SMTP_SSLv4(self.config.smtp_host, self.config.smtp_port, timeout=30.0)
            else:
                server = _SMTPv4(self.config.smtp_host, self.config.smtp_port, timeout=30.0)
                server.starttls()

            server.login(self.config.indirizzo, self.config.password)
            server.send_message(msg)
            server.quit()

            risultato["inviato"] = True
            risultato["message_id"] = msg.get("Message-ID", "")
        except smtplib.SMTPException as e:
            risultato["errore"] = str(e)

        return risultato

    def attendi_ricevute(self, timeout: int = TIMEOUT_RICEVUTA, message_id: str | None = None) -> dict:
        """
        Attende le ricevute PEC (accettazione e avvenuta consegna) del messaggio ``message_id``.

        Le ricevute si cercano solo con l'intestazione ``X-Riferimento-Message-ID`` uguale al
        Message-ID del messaggio di deposito (d.P.R. 68/2005; d.m. 2/11/2005): una PEC del giorno
        con «accettazione» o «consegna» nell'oggetto non e' una ricevuta di QUESTO deposito.
        Gli avvisi di non accettazione e di mancata consegna sono restituiti come tali, mai come
        ricevute positive. Senza Message-ID non si collega nulla.

        Returns:
            {"accettazione", "consegna", "non_accettazione", "mancata_consegna": testo di prova o None,
             "completato": bool, "ricevute": [dict per pct.ricevute_deposito_pct], "errore"?/"info"?}
        """
        from pct.ricevute_deposito_pct import (
            ACCETTAZIONE,
            CONSEGNA,
            INTESTAZIONI_IMAP,
            MANCATA_CONSEGNA,
            NON_ACCETTAZIONE,
            classifica,
            normalizza_message_id,
            ricevuta_da_intestazioni,
        )

        ricevute = {
            "accettazione": None,
            "consegna": None,
            "non_accettazione": None,
            "mancata_consegna": None,
            "completato": False,
            "ricevute": [],
        }

        if not self.config.imap_host:
            return ricevute
        riferimento = normalizza_message_id(message_id)
        if not riferimento:
            ricevute["info"] = (
                "Identificativo del messaggio di deposito non disponibile: le ricevute non si possono "
                "collegare in automatico. Verificale nella casella PEC."
            )
            return ricevute

        _oggi = time.strftime("%d-%b-%Y", time.localtime())
        criterio = f'(SINCE {_oggi} HEADER X-Riferimento-Message-ID "{riferimento}")'
        chiavi = {ACCETTAZIONE: "accettazione", CONSEGNA: "consegna",
                  NON_ACCETTAZIONE: "non_accettazione", MANCATA_CONSEGNA: "mancata_consegna"}

        inizio = time.time()
        try:
            mail = imaplib.IMAP4_SSL(self.config.imap_host, self.config.imap_port)
            mail.login(self.config.indirizzo, self.config.password)
            mail.select("INBOX", readonly=True)

            while time.time() - inizio < timeout:
                try:
                    _, messages = mail.search(None, criterio)
                except imaplib.IMAP4.error:
                    messages = [b""]
                numeri = (messages[0] or b"").split() if messages else []
                if numeri:
                    _, dati = mail.fetch(
                        b",".join(numeri).decode("ascii"),
                        f"(BODY.PEEK[HEADER.FIELDS ({INTESTAZIONI_IMAP})])",
                    )
                    for parte in dati or []:
                        if not isinstance(parte, tuple) or len(parte) < 2 or not isinstance(parte[1], bytes):
                            continue
                        r = ricevuta_da_intestazioni(email.message_from_bytes(parte[1]))
                        # Il server puo' ignorare il criterio HEADER: si ricontrolla qui.
                        if normalizza_message_id(r.get("riferimento_message_id")) != riferimento:
                            continue
                        tipo, _esito = classifica(r.get("subject"), x_ricevuta=r.get("x_ricevuta"))
                        chiave = chiavi.get(tipo)
                        if not chiave or r in ricevute["ricevute"]:
                            continue
                        ricevute["ricevute"].append(r)
                        ricevute[chiave] = ricevute[chiave] or (
                            f"Oggetto: {r.get('subject', '')}\nData: {r.get('date', '')}\n"
                            f"Message-ID ricevuta: {r.get('message_id', '')}\n"
                            f"Riferimento: {riferimento}"
                        )

                if ricevute["non_accettazione"] or ricevute["mancata_consegna"]:
                    break
                if ricevute["accettazione"] and ricevute["consegna"]:
                    ricevute["completato"] = True
                    break

                time.sleep(10)

            mail.logout()
        except imaplib.IMAP4.error as e:
            ricevute["errore"] = str(e)
        except OSError as e:
            ricevute["errore"] = f"Connessione IMAP fallita: {e}"
        except Exception as e:
            ricevute["errore"] = f"Errore attesa ricevute: {e}"

        return ricevute

    def verifica_indirizzo_pec(self, indirizzo: str) -> bool:
        """
        Verifica che un indirizzo PEC sia sintatticamente valido.

        Args:
            indirizzo: Indirizzo PEC da verificare

        Returns:
            True se l'indirizzo è valido
        """
        import re
        pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, indirizzo))
