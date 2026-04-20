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
import json
import logging
import os
import re
import socket
import email as _email_lib
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from pct.imap_runtime import describe_imap_connection_error, resolve_imap_timeout_seconds

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
    timeout_seconds: int | None = None,
) -> list[dict]:
    """
    Si connette all'IMAP e restituisce una lista di messaggi recenti
    che sembrano ricevute di deposito telematico.

    Ogni elemento: {"subject": str, "from": str, "date": str, "body_snippet": str}
    """
    risultati = []
    timeout_s = resolve_imap_timeout_seconds(timeout_seconds)
    try:
        mail = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=timeout_s)
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
    except (imaplib.IMAP4.error, OSError, socket.timeout, TimeoutError) as e:
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


def _estrai_corpo_email(msg: _email_lib.message.Message) -> tuple[str, str]:
    """Estrae il corpo testo/HTML da un messaggio PEC."""
    corpo_testo = ""
    corpo_html = ""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                content_type = (part.get_content_type() or "").lower()
                disposition = (part.get("Content-Disposition", "") or "").lower()
                if "attachment" in disposition:
                    continue
                if content_type not in {"text/plain", "text/html"}:
                    continue
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                charset = part.get_content_charset() or "utf-8"
                try:
                    decoded = payload.decode(charset, errors="replace").strip()
                except Exception:
                    decoded = payload.decode("utf-8", errors="replace").strip()
                if content_type == "text/plain" and not corpo_testo:
                    corpo_testo = decoded
                elif content_type == "text/html" and not corpo_html:
                    corpo_html = decoded
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                try:
                    decoded = payload.decode(charset, errors="replace").strip()
                except Exception:
                    decoded = payload.decode("utf-8", errors="replace").strip()
                if (msg.get_content_type() or "").lower() == "text/html":
                    corpo_html = decoded
                else:
                    corpo_testo = decoded
    except Exception as e:
        logger.debug("Estrazione corpo PEC fallita: %s", e)
    return corpo_testo, corpo_html


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
    timeout_seconds: int | None = None,
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
        timeout_s = resolve_imap_timeout_seconds(timeout_seconds)
        ricevute_imap = _cerca_ricevute_imap(
            imap_host=config_pec.imap_host,
            imap_port=getattr(config_pec, "imap_port", 993),
            indirizzo=config_pec.indirizzo,
            password=config_pec.password,
            giorni_indietro=giorni_indietro,
            timeout_seconds=timeout_s,
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


# ──────────────────────────────────────────────────────────────────────────────
# Polling PEC → Comunicazioni di cancelleria
# ──────────────────────────────────────────────────────────────────────────────

# Pattern per estrarre il numero RG dal subject delle PEC di cancelleria.
# Gestisce formati come: "RG 139/2023", "RG 139/ 2023", "R.G. 139/2023"
_RE_RG = re.compile(
    r'\bR\.?\s*G\.?\s+(\d+)\s*/\s*(\d{4})\b',
    re.IGNORECASE,
)

# Parole chiave nel subject che indicano una comunicazione di cancelleria rilevante
_KW_CANCELLERIA_SUBJ = (
    "accettazione",
    "rifiuto",
    "comunicazione di cancelleria",
    "comunicazione cancelleria",
    "esito deposito",
    "controparte",
    "notifica",
)


def _estrai_rg_da_subject(subject: str) -> tuple[str, int] | None:
    """Estrae (numero_rg, anno_rg) dal subject di una PEC, o None se non trovato."""
    m = _RE_RG.search(subject)
    if m:
        return m.group(1).strip(), int(m.group(2))
    return None


def _carica_uid_processati(state_path: str) -> set:
    """Carica il set di UID IMAP già processati dal file di stato."""
    try:
        with open(state_path, encoding="utf-8") as f:
            stato = json.load(f)
        return set(stato.get("uid_processati", []))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return set()


def _salva_uid_processati(uid_set: set, state_path: str) -> None:
    """Salva il set di UID processati, mantenendo al massimo gli ultimi 2000."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(state_path)), exist_ok=True)
        # Ordina e tronca per evitare crescita illimitata del file
        lista = sorted(uid_set)[-2000:]
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump({"uid_processati": lista, "aggiornato_il": datetime.now().isoformat()}, f)
    except OSError as e:
        logger.warning("Poll cancelleria: impossibile salvare stato UID: %s", e)


def poll_cancelleria_pec(
    gf: "GestioneFascicoli",
    config_pec: object,
    fascicolo_id: str | None = None,
    state_path: str = "",
    giorni_indietro: int = 30,
    timeout_seconds: int | None = None,
) -> dict:
    """
    Scansiona la casella PEC alla ricerca di comunicazioni di cancelleria
    e le associa automaticamente ai fascicoli tramite il numero RG nel subject.

    Per ogni email trovata con soggetto che contiene un RG (es. "RG 139/2023")
    corrispondente a un fascicolo aperto, crea automaticamente un'attività
    di tipo COMUNICAZIONE_CANCELLERIA nella sezione omonima del fascicolo.

    Args:
        gf:              GestioneFascicoli istanziato
        config_pec:      Oggetto config PEC (imap_host/imap_port/indirizzo/password)
        state_path:      Percorso al file JSON di stato UID (default: accanto al db)
        giorni_indietro: Finestra temporale IMAP

    Returns:
        dict con "trovati", "associati", "duplicati", "errori"
    """
    from pct.fascicoli import TipoAttivita, EsitoAttivita

    report = {"trovati": 0, "associati": 0, "duplicati": 0, "errori": 0}

    if not config_pec or not getattr(config_pec, "imap_host", ""):
        return report
    if not getattr(config_pec, "indirizzo", "") or not getattr(config_pec, "password", ""):
        return report

    # Determina path stato UID
    if not state_path:
        db_path = getattr(gf, "db_path", "") or ""
        base_dir = os.path.dirname(os.path.abspath(db_path)) if db_path else "."
        state_path = os.path.join(base_dir, "pec_cancelleria_state.json")

    uid_processati = _carica_uid_processati(state_path)

    # Costruisce indice fascicoli per lookup rapido (numero_rg, str(anno_rg)) → fascicolo
    fascicoli_index: dict[tuple, object] = {}
    try:
        tutti = gf.tutti() if hasattr(gf, "tutti") else list(
            gf._fascicoli.values() if hasattr(gf, "_fascicoli") else []
        )
    except Exception:
        tutti = []

    if fascicolo_id:
        tutti = [f for f in tutti if getattr(f, "id", "") == fascicolo_id]

    for f in tutti:
        nr = str(getattr(f, "numero_rg", "") or "").strip()
        ar = str(getattr(f, "anno_rg", 0) or "").strip()
        if nr and ar and ar != "0":
            fascicoli_index[(nr, ar)] = f

    if not fascicoli_index:
        logger.debug("Poll cancelleria PEC: nessun fascicolo con RG — skip")
        return report

    uid_nuovi: set = set()

    try:
        timeout_s = resolve_imap_timeout_seconds(timeout_seconds)
        mail = imaplib.IMAP4_SSL(
            config_pec.imap_host,
            getattr(config_pec, "imap_port", 993),
            timeout=timeout_s,
        )
        mail.login(config_pec.indirizzo, config_pec.password)
        mail.select("INBOX")

        since_dt = datetime.now() - timedelta(days=giorni_indietro)
        since_str = _formato_data_imap(since_dt)

        # Cerca email di accettazione/comunicazione cancelleria
        criteri_ricerca = [
            f'(SINCE "{since_str}" SUBJECT "ACCETTAZIONE")',
            f'(SINCE "{since_str}" SUBJECT "RIFIUTO")',
            f'(SINCE "{since_str}" SUBJECT "cancelleria")',
        ]

        uid_da_esaminare: list[bytes] = []
        visti: set[bytes] = set()
        for criterio in criteri_ricerca:
            try:
                _, data = mail.uid("SEARCH", None, criterio)
                if data and data[0]:
                    for uid_b in data[0].split():
                        if uid_b not in visti:
                            visti.add(uid_b)
                            uid_da_esaminare.append(uid_b)
            except imaplib.IMAP4.error:
                pass

        for uid_b in uid_da_esaminare:
            uid_str = uid_b.decode()
            uid_nuovi.add(uid_str)

            if uid_str in uid_processati:
                continue

            try:
                _, msg_data = mail.uid("FETCH", uid_b, "(RFC822)")
                if not msg_data or not msg_data[0]:
                    uid_nuovi.add(uid_str)  # marca processato anche se fetch fallisce
                    continue

                raw_message = msg_data[0][1]
                msg = _email_lib.message_from_bytes(raw_message)
                subject = _decode_header_value(msg.get("Subject", ""))
                from_ = _decode_header_value(msg.get("From", ""))
                date_str = msg.get("Date", "")
                corpo_testo, corpo_html = _estrai_corpo_email(msg)

                report["trovati"] += 1

                # Estrai RG dal subject
                rg = _estrai_rg_da_subject(subject)
                if not rg:
                    # Nessun RG nel subject — marca come processato e prosegui
                    uid_processati.add(uid_str)
                    continue

                numero_rg, anno_rg = rg

                # Cerca fascicolo corrispondente
                fasc = fascicoli_index.get((numero_rg, str(anno_rg)))
                if not fasc:
                    uid_processati.add(uid_str)
                    continue

                # Normalizza data dalla PEC
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(date_str)
                    data_att = dt.strftime("%Y-%m-%d")
                except Exception:
                    data_att = datetime.now().strftime("%Y-%m-%d")

                # Titolo attività (troncato a 120 char)
                titolo_att = f"PEC: {subject}"[:120]

                # Controlla duplicati: stessa data + stesso titolo
                att_esistente = next((
                    att for att in (getattr(fasc, "attivita", None) or [])
                    if getattr(att, "tipo", None) == TipoAttivita.COMUNICAZIONE_CANCELLERIA
                    and getattr(att, "titolo", "") == titolo_att
                    and getattr(att, "data", "") == data_att
                ), None)

                note_auto = (
                    f"Caricata automaticamente dalla PEC il "
                    f"{datetime.now().strftime('%d/%m/%Y %H:%M')} "
                    f"(UID IMAP: {uid_str})"
                )

                if att_esistente:
                    needs_enrichment = any([
                        subject and not getattr(att_esistente, "email_oggetto", ""),
                        from_ and not getattr(att_esistente, "email_mittente", ""),
                        uid_str and not getattr(att_esistente, "email_uid_imap", ""),
                        corpo_testo and not getattr(att_esistente, "email_testo", ""),
                        corpo_html and not getattr(att_esistente, "email_html", ""),
                    ])
                    if needs_enrichment:
                        gf.aggiorna_attivita(
                            fasc.id,
                            att_esistente.id,
                            descrizione=getattr(att_esistente, "descrizione", "") or f"Da: {from_}",
                            note=getattr(att_esistente, "note", "") or note_auto,
                            email_mittente=getattr(att_esistente, "email_mittente", "") or from_,
                            email_oggetto=getattr(att_esistente, "email_oggetto", "") or subject,
                            email_uid_imap=getattr(att_esistente, "email_uid_imap", "") or uid_str,
                            email_testo=getattr(att_esistente, "email_testo", "") or corpo_testo,
                            email_html=getattr(att_esistente, "email_html", "") or corpo_html,
                        )
                        report["associati"] += 1
                    else:
                        report["duplicati"] += 1
                    uid_processati.add(uid_str)
                    continue

                gia_presente = any(
                    getattr(att, "tipo", None) == TipoAttivita.COMUNICAZIONE_CANCELLERIA
                    and getattr(att, "titolo", "") == titolo_att
                    and getattr(att, "data", "") == data_att
                    for att in (getattr(fasc, "attivita", None) or [])
                )

                if gia_presente:
                    report["duplicati"] += 1
                    uid_processati.add(uid_str)
                    continue

                # Aggiunge l'attività al fascicolo
                try:
                    gf.aggiungi_attivita(
                        fasc.id,
                        tipo=TipoAttivita.COMUNICAZIONE_CANCELLERIA,
                        data=data_att,
                        titolo=titolo_att,
                        descrizione=f"Da: {from_}",
                        esito=EsitoAttivita.NON_APPLICABILE,
                        note=note_auto,
                        email_mittente=from_,
                        email_oggetto=subject,
                        email_uid_imap=uid_str,
                        email_testo=corpo_testo,
                        email_html=corpo_html,
                    )
                    report["associati"] += 1
                    logger.info(
                        "Poll cancelleria PEC: aggiunta comunicazione a fascicolo %s "
                        "(RG %s/%s) — %s",
                        fasc.id, numero_rg, anno_rg, subject[:60],
                    )
                except Exception as e:
                    logger.error(
                        "Poll cancelleria PEC: errore aggiungi_attivita fascicolo %s: %s",
                        getattr(fasc, "id", "?"), e,
                    )
                    report["errori"] += 1

                uid_processati.add(uid_str)

            except Exception as e:
                logger.warning("Poll cancelleria PEC: errore UID %s: %s", uid_str, e)
                report["errori"] += 1

        mail.logout()

    except (imaplib.IMAP4.error, OSError, socket.timeout, TimeoutError) as e:
        logger.warning("Poll cancelleria PEC: connessione IMAP fallita — %s", e)
    except Exception as e:
        logger.warning("Poll cancelleria PEC: errore inatteso — %s", e)
    finally:
        # Salva sempre lo stato aggiornato
        if uid_nuovi:
            uid_processati.update(uid_nuovi)
            _salva_uid_processati(uid_processati, state_path)

    return report
