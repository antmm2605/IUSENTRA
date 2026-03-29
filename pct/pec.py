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

    def attendi_ricevute(self, timeout: int = TIMEOUT_RICEVUTA) -> dict:
        """
        Attende le ricevute PEC dopo l'invio della busta.

        Il sistema PCT invia due ricevute:
        1. Ricevuta di accettazione (dal gestore PEC mittente)
        2. Ricevuta di consegna (dal gestore PEC destinatario)

        Args:
            timeout: Timeout in secondi per l'attesa delle ricevute

        Returns:
            Dizionario con le ricevute ottenute
        """
        ricevute = {
            "accettazione": None,
            "consegna": None,
            "completato": False,
        }

        if not self.config.imap_host:
            return ricevute

        # Filtro data: cerca solo messaggi da oggi per evitare match su ricevute vecchie
        from email.utils import formatdate as _fmtdate
        _oggi = time.strftime("%d-%b-%Y", time.localtime()).upper()

        # Pattern alternativi per provider PEC italiani:
        # Aruba:    "Ricevuta di accettazione del messaggio" / "Ricevuta di consegna"
        # InfoCert: "ACCETTAZIONE" / "CONSEGNA"
        # Namirial: "accettazione" / "consegna"
        # Il criterio IMAP SUBJECT è case-insensitive (RFC 3501) ma
        # alcune implementazioni sono case-sensitive → usiamo OR su varianti.
        _CRITERI_ACC = (
            'OR OR SUBJECT "accettazione" SUBJECT "ACCETTAZIONE" SUBJECT "Accettazione"'
        )
        _CRITERI_CONS = (
            'OR OR SUBJECT "consegna" SUBJECT "CONSEGNA" SUBJECT "Consegna"'
        )

        inizio = time.time()
        try:
            mail = imaplib.IMAP4_SSL(self.config.imap_host, self.config.imap_port)
            mail.login(self.config.indirizzo, self.config.password)
            mail.select("INBOX")

            while time.time() - inizio < timeout:
                try:
                    _, messages = mail.search(
                        None, f'SINCE {_oggi} {_CRITERI_ACC}'
                    )
                    if messages[0]:
                        ricevute["accettazione"] = messages[0].decode()

                    _, messages = mail.search(
                        None, f'SINCE {_oggi} {_CRITERI_CONS}'
                    )
                    if messages[0]:
                        ricevute["consegna"] = messages[0].decode()
                except imaplib.IMAP4.error:
                    # Alcuni server non supportano OR — fallback senza filtro data
                    _, messages = mail.search(None, 'SUBJECT "accettazione"')
                    if messages[0]:
                        ricevute["accettazione"] = messages[0].decode()
                    _, messages = mail.search(None, 'SUBJECT "consegna"')
                    if messages[0]:
                        ricevute["consegna"] = messages[0].decode()

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
