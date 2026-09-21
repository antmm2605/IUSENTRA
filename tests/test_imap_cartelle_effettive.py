"""Si aprono le cartelle che esistono, non quelle che potrebbero esistere.

`cartelle_imap_standard()` e' un elenco di nomi tentati a indovinare — fra
italiano e inglese, per coprire i vari gestori di posta. Il server pero' sa
quali ha, e lo dice con una sola LIST.

Finche' quella risposta serviva soltanto ad aggiungere le cartelle trovate,
ogni sincronizzazione apriva anche tutte quelle inesistenti, una SELECT per
ciascuna. Su due studi con casella PEC e ordinaria facevano un centinaio di
viaggi verso il gestore a ogni giro, ed erano l'intero costo della
sincronizzazione: trentacinque secondi ogni quindici minuti, identici che ci
fosse posta nuova oppure no.
"""

from __future__ import annotations

from pct.email_client import GestioneEmailRicevute, cartelle_imap_standard


class MailFinta:
    """Il minimo di IMAP che serve: la risposta alla LIST."""

    def __init__(self, righe, status="OK"):
        self.righe = righe
        self.status = status
        self.chiamate = 0

    def list(self):
        self.chiamate += 1
        return self.status, self.righe


def riga(nome: str, flag: str = "\\HasNoChildren") -> bytes:
    return f'({flag}) "/" "{nome}"'.encode()


def _effettive(mail, richieste):
    return GestioneEmailRicevute._cartelle_imap_effettive(mail, richieste)


# ------------------------------------------------------- il taglio dei tentativi


def test_i_nomi_che_il_server_non_ha_non_vengono_aperti():
    mail = MailFinta([riga("INBOX"), riga("Sent"), riga("Trash")])

    effettive = _effettive(mail, cartelle_imap_standard())

    assert "Spedite" not in effettive
    assert "INBOX.Deleted Items" not in effettive
    assert len(effettive) < len(cartelle_imap_standard()) / 3


def test_la_inbox_c_e_sempre_quando_il_server_la_dichiara():
    mail = MailFinta([riga("INBOX")])

    assert _effettive(mail, cartelle_imap_standard()) == ["INBOX"]


def test_una_sola_interrogazione_al_server():
    """La LIST costa un viaggio: non se ne fanno due."""

    mail = MailFinta([riga("INBOX")])

    _effettive(mail, cartelle_imap_standard())

    assert mail.chiamate == 1


# ------------------------------------------------------- nomi scritti diversi


def test_il_separatore_diverso_non_fa_perdere_la_cartella():
    """«INBOX.Sent» e «INBOX/Sent» sono la stessa cartella."""

    mail = MailFinta([riga("INBOX"), riga("INBOX.Sent")])

    effettive = _effettive(mail, ["INBOX", "INBOX/Sent"])

    assert "INBOX.Sent" in effettive


def test_le_maiuscole_non_fanno_perdere_la_cartella():
    mail = MailFinta([riga("INBOX"), riga("Spedite")])

    assert "Spedite" in _effettive(mail, ["INBOX", "SPEDITE"])


def test_si_usa_il_nome_del_server_non_quello_tentato():
    """E' quello il nome che la SELECT accetta."""

    mail = MailFinta([riga("INBOX"), riga("Posta inviata")])

    effettive = _effettive(mail, ["INBOX", "POSTA INVIATA"])

    assert "Posta inviata" in effettive
    assert "POSTA INVIATA" not in effettive


# ------------------------------------------------------- quando non si sa


def test_se_la_lista_fallisce_si_torna_ai_nomi_tentati():
    """Meglio qualche SELECT a vuoto che una casella non guardata."""

    mail = MailFinta([], status="NO")

    assert _effettive(mail, ["INBOX", "Sent", "Spedite"]) == ["INBOX", "Sent", "Spedite"]


def test_una_lista_vuota_non_e_una_casella_senza_cartelle():
    """Una risposta che non sappiamo leggere non deve azzerare la lettura."""

    mail = MailFinta([])

    assert _effettive(mail, ["INBOX", "Sent"]) == ["INBOX", "Sent"]


def test_se_la_lista_solleva_si_torna_ai_nomi_tentati():
    class MailRotta:
        def list(self):
            raise OSError("connessione caduta")

    assert _effettive(MailRotta(), ["INBOX", "Sent"]) == ["INBOX", "Sent"]


# ------------------------------------------------------- cartelle non previste


def test_una_cartella_operativa_fuori_elenco_viene_comunque_aperta():
    """Il guadagno non deve costare una cartella di posta inviata sconosciuta."""

    mail = MailFinta([riga("INBOX"), riga("Posta Inviata Studio")])

    assert "Posta Inviata Studio" in _effettive(mail, ["INBOX"])


def test_nessun_duplicato_quando_il_nome_tentato_coincide():
    mail = MailFinta([riga("INBOX"), riga("Sent")])

    effettive = _effettive(mail, ["INBOX", "Sent"])

    assert effettive == ["INBOX", "Sent"]
