"""
pct/polling_depositi.py — Polling automatico esiti depositi telematici.

Interroga periodicamente PEC (civile/amministrativo) e PDP REST (penale)
per aggiornare lo stato degli EsitoDepositoPCT in transizioni intermedie.

Stadi che richiedono polling:
  INVIATO             → attende ACCETTATO_PEC (ricevuta accettazione PEC)
  ACCETTATO_PEC       → attende CONSEGNATO (ricevuta consegna PEC)
  CONSEGNATO          → attende WARN_CONTROLLI / ERRORE_CONTROLLI (cancelleria)
  WARN_CONTROLLI      → attende ACCETTATO_CANCELLERIA / RIFIUTATO_CANCELLERIA

Stadi terminali (non pollati):
  ACCETTATO_CANCELLERIA, RIFIUTATO_CANCELLERIA, ERRORE, IMPORTATO_DA_PORTALE,
  IMPORTATO_DA_PST, ERRORE_CONTROLLI
"""
from __future__ import annotations

import imaplib
import logging
import email as _email_lib
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pct.fascicoli import GestioneFascicoli, EsitoDepositoPCT, Fascicolo

logger = logging.getLogger("pct.polling_depositi")

# Stati che richiedono polling
STATI_PENDENTI = frozenset({
    "INVIATO",
    "ACCETTATO_PEC",
    "CONSEGNATO",
    "WARN_CONTROLLI",
})

# Parole chiave nel subject per identificare il tipo di ricevuta
_KW_ACCETTAZIONE = ("accettazione", "accepted", "presa in carico")
_KW_CONSEGNA = ("consegna", "delivered", "consegnata")
_KW_ERRORE = ("anomalia", "rifiuto", "errore", "error", "rejected")


def _subject_contiene(subject: str, parole: tuple) -> bool:
    s = subject.lower()
    return any(p in s for p in parole)


def _formato_data_imap(dt: datetime) -> str:
    """Formatta una data nel formato IMAP SINCE (01-Jan-2025)."""
    mesi = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{dt.day:02d}-{mesi[dt.month - 1]}-{dt.year}"


def _cerca_ricevute_imap(
    imap_host: str,
    imap_port: int,
    indirizzo: str,
    password: str,
    giorni_indietro: int = 30,
) -> list[dict]:
    """
    Si connette all'IMAP e restituisce una lista di messaggi recenti
    che sembrano ricevute di deposito telematico.

    Ogni elemento: {"subject": str, "from": str, "date": str, "body_snippet": str}
    """
    risultati = []
    try:
        mail = imaplib.IMAP4_SSL(imap_host, imap_port)
        mail.login(indirizzo, password)
        mail.select("INBOX")

        since_dt = datetime.now() - timedelta(days=giorni_indietro)
        since_str = _formato_data_imap(since_dt)

        # Cerca email con subject tipico di ricevute PCT
        for criterio in [
            f'(SINCE "{since_str}" SUBJECT "deposito")',
            f'(SINCE "{since_str}" SUBJECT "telematic")',
            f'(SINCE "{since_str}" SUBJECT "ACCETTAZIONE")',
            f'(SINCE "{since_str}" SUBJECT "CONSEGNA")',
        ]:
            try:
                _, data = mail.search(None, criterio)
                if not data or not data[0]:
                    continue
                for num in data[0].split():
                    try:
                        _, msg_data = mail.fetch(num, "(RFC822.SIZE RFC822.HEADER)")
                        if not msg_data or not msg_data[0]:
                            continue
                        raw_header = msg_data[0][1]
                        msg = _email_lib.message_from_bytes(raw_header)
                        subj = _decode_header_value(msg.get("Subject", ""))
                        from_ = msg.get("From", "")
                        date_ = msg.get("Date", "")
                        risultati.append({
                            "subject": subj,
                            "from": from_,
                            "date": date_,
                        })
                    except Exception:
                        pass
            except imaplib.IMAP4.error:
                pass

        mail.logout()
    except (imaplib.IMAP4.error, OSError) as e:
        logger.warning("IMAP polling depositi: connessione fallita — %s", e)
    except Exception as e:
        logger.warning("IMAP polling depositi: errore inatteso — %s", e)
    return risultati


def _decode_header_value(value: str) -> str:
    """Decodifica un header MIME (es. =?utf-8?b?...?=)."""
    try:
        import email.header
        parts = email.header.decode_header(value)
        decoded = []
        for bts, charset in parts:
            if isinstance(bts, bytes):
                decoded.append(bts.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(bts)
        return " ".join(decoded)
    except Exception:
        return value


def _stima_nuovo_stato(dep: "EsitoDepositoPCT", ricevute: list[dict]) -> str | None:
    """
    Analizza le ricevute IMAP e determina il nuovo stato per il deposito.
    Restituisce None se non ci sono aggiornamenti da applicare.
    """
    # Cerca ricevute che menzionano il numero fascicolo o l'ID deposito
    chiavi = set()
    if dep.id:
        chiavi.add(dep.id.lower())
    if dep.nome_atto_principale:
        # Usa l'inizio del nome atto (prime 20 char) come fingerprint
        chiavi.add(dep.nome_atto_principale[:20].lower())

    candidati = ricevute
    # Se abbiamo chiavi specifiche, filtriamo le ricevute
    if chiavi:
        candidati = [
            r for r in ricevute
            if any(k in r.get("subject", "").lower() for k in chiavi)
        ] or ricevute  # fallback a tutte se nessuna match

    # Determina il miglior upgrade di stato
    ha_accettazione = any(_subject_contiene(r["subject"], _KW_ACCETTAZIONE) for r in candidati)
    ha_consegna = any(_subject_contiene(r["subject"], _KW_CONSEGNA) for r in candidati)
    ha_errore = any(_subject_contiene(r["subject"], _KW_ERRORE) for r in candidati)

    stato_corrente = dep.stato

    if stato_corrente == "INVIATO":
        if ha_errore:
            return "ERRORE"
        if ha_consegna:
            return "CONSEGNATO"
        if ha_accettazione:
            return "ACCETTATO_PEC"

    elif stato_corrente == "ACCETTATO_PEC":
        if ha_errore:
            return "ERRORE"
        if ha_consegna:
            return "CONSEGNATO"

    # CONSEGNATO e WARN_CONTROLLI vengono aggiornati dalla cancelleria
    # Non possiamo dedurli dall'IMAP senza leggere il body completo
    return None


def _poll_pdp_deposito(
    dep: "EsitoDepositoPCT",
    credenziali_pdp: dict,
) -> str | None:
    """
    Interroga PDP REST API per l'esito di un deposito penale.
    Restituisce il nuovo stato o None se non disponibile.
    """
    if not dep.id_deposito_esterno:
        return None
    try:
        from pct.pdp import GestorePDP
        g = GestorePDP(credenziali=credenziali_pdp)
        esito = g.get_esito_deposito(dep.id_deposito_esterno)
        if not esito:
            return None
        stato_pdp = (esito.get("stato") or "").upper()
        # Mappa stati PDP → stati interni
        _mappa = {
            "ACCETTATO": "ACCETTATO_PEC",
            "CONSEGNATO": "CONSEGNATO",
            "APPROVATO": "ACCETTATO_CANCELLERIA",
            "RIFIUTATO": "RIFIUTATO_CANCELLERIA",
            "ERRORE": "ERRORE",
            "WARN": "WARN_CONTROLLI",
        }
        return _mappa.get(stato_pdp)
    except Exception as e:
        logger.debug("PDP polling deposito %s: %s", dep.id_deposito_esterno, e)
        return None


def esegui_polling(
    gf: "GestioneFascicoli",
    config_pec: object | None = None,
    credenziali_pdp: dict | None = None,
    giorni_indietro: int = 30,
) -> dict:
    """
    Punto di ingresso principale per il polling scheduler.

    Args:
        gf:               GestioneFascicoli istanziato
        config_pec:       Oggetto config PEC con imap_host/imap_port/indirizzo/password
        credenziali_pdp:  Dict credenziali PDP REST (p12_path, p12_password, ecc.)
        giorni_indietro:  Finestra temporale IMAP

    Returns:
        dict con "controllati", "aggiornati", "errori"
    """
    controllati = 0
    aggiornati = 0
    errori = 0

    # Carica ricevute IMAP una volta sola (costoso)
    ricevute_imap: list[dict] = []
    if config_pec and getattr(config_pec, "imap_host", ""):
        ricevute_imap = _cerca_ricevute_imap(
            imap_host=config_pec.imap_host,
            imap_port=getattr(config_pec, "imap_port", 993),
            indirizzo=config_pec.indirizzo,
            password=config_pec.password,
            giorni_indietro=giorni_indietro,
        )
        logger.info("Polling depositi: trovate %d ricevute PEC recenti", len(ricevute_imap))

    fascicoli = list(gf._fascicoli.values()) if hasattr(gf, "_fascicoli") else []
    if not fascicoli:
        try:
            fascicoli = gf.tutte() if hasattr(gf, "tutte") else []
        except Exception:
            fascicoli = []

    for fasc in fascicoli:
        depositi_pendenti = [
            dep for dep in (fasc.depositi_pct or [])
            if dep.stato in STATI_PENDENTI
        ]
        if not depositi_pendenti:
            continue

        for dep in depositi_pendenti:
            controllati += 1
            nuovo_stato = None

            # Prova PDP se è un deposito penale con ID esterno
            if credenziali_pdp and dep.id_deposito_esterno:
                try:
                    nuovo_stato = _poll_pdp_deposito(dep, credenziali_pdp)
                except Exception as e:
                    logger.debug("Polling PDP deposito %s: %s", dep.id, e)
                    errori += 1

            # Prova PEC IMAP per tutti gli altri
            if not nuovo_stato and ricevute_imap:
                try:
                    nuovo_stato = _stima_nuovo_stato(dep, ricevute_imap)
                except Exception as e:
                    logger.debug("Polling PEC deposito %s: %s", dep.id, e)
                    errori += 1

            if nuovo_stato and nuovo_stato != dep.stato:
                try:
                    dep.stato = nuovo_stato
                    dep.note = (dep.note or "") + (
                        f"\n[AUTO {datetime.now().strftime('%d/%m/%Y %H:%M')}] "
                        f"Stato aggiornato automaticamente: {nuovo_stato}"
                    )
                    gf._salva()
                    aggiornati += 1
                    logger.info(
                        "Deposito %s (fascicolo %s): %s → %s",
                        dep.id, fasc.id, dep.stato, nuovo_stato,
                    )
                except Exception as e:
                    logger.error("Salvataggio stato deposito %s: %s", dep.id, e)
                    errori += 1

    return {"controllati": controllati, "aggiornati": aggiornati, "errori": errori}
