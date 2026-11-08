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

from pct.imap_runtime import (
    describe_imap_connection_error,
    resolve_imap_timeout_seconds,
    run_imap_runtime_operation,
)
from pct.ricevute_deposito_pct import (
    INTESTAZIONI_IMAP,
    applica_ricevute,
    mittenti_interni,
    ricevuta_da_intestazioni,
    serve_testo,
    testo_messaggio,
)

if TYPE_CHECKING:
    from pct.fascicoli import GestioneFascicoli, EsitoDepositoPCT, Fascicolo

logger = logging.getLogger("pct.polling_depositi")

# Stati che richiedono polling
STATI_PENDENTI = frozenset({
    "INVIATO",
    "ACCETTATO_PEC",
    "CONSEGNATO",
    "CONTROLLI_SUPERATI",
    "WARN_CONTROLLI",
})

# Il tipo di ricevuta e il suo collegamento al deposito si decidono in pct/ricevute_deposito_pct.py
# (prefissi fissi d.P.R. 68/2005, X-Riferimento-Message-ID, IdMsgMitt/IdBusta/RefID): mai per
# parole generiche dell'oggetto, che compaiono anche in «AVVISO DI MANCATA CONSEGNA».

_MESSAGGIO_PDP_NON_DISPONIBILE = (
    "Esito dei depositi penali non interrogabile dal software: il Portale Deposito Atti Penali "
    "non espone un servizio per i gestionali; l'esito si legge sul portale (art. 111-bis c.p.p.)."
)


def _formato_data_imap(dt: datetime) -> str:
    """Formatta una data nel formato IMAP SINCE (01-Jan-2025)."""
    mesi = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{dt.day:02d}-{mesi[dt.month - 1]}-{dt.year}"


_INTESTAZIONI_PER_RICHIESTA = 200
_ESITI_DA_LEGGERE_MAX = 200
_ESITO_BYTES_MAX = 2 * 1024 * 1024


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
        def _connect_mail():
            client = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=timeout_s)
            client.login(indirizzo, password)
            return client

        mail = run_imap_runtime_operation(_connect_mail)
        mail.select("INBOX", readonly=True)

        since_dt = datetime.now() - timedelta(days=giorni_indietro)
        since_str = _formato_data_imap(since_dt)

        # Cerca email con subject tipico di ricevute PCT; un messaggio che
        # risponde a piu' criteri si legge una volta sola. «ESITO» copre l'esito
        # dell'intervento della cancelleria, che non sempre nomina il deposito.
        numeri: list[bytes] = []
        for criterio in [
            f'(SINCE "{since_str}" SUBJECT "deposito")',
            f'(SINCE "{since_str}" SUBJECT "telematic")',
            f'(SINCE "{since_str}" SUBJECT "ACCETTAZIONE")',
            f'(SINCE "{since_str}" SUBJECT "CONSEGNA")',
            f'(SINCE "{since_str}" SUBJECT "ESITO")',
        ]:
            try:
                _, data = mail.search(None, criterio)
            except imaplib.IMAP4.error:
                continue
            if data and data[0]:
                numeri.extend(data[0].split())
        numeri = list(dict.fromkeys(numeri))

        # Intestazioni lette a gruppi, non una richiesta per messaggio: con
        # centinaia di ricevute nel mese la differenza e' di decine di secondi.
        da_leggere: list[tuple[str, dict]] = []
        for inizio in range(0, len(numeri), _INTESTAZIONI_PER_RICHIESTA):
            gruppo = b",".join(numeri[inizio:inizio + _INTESTAZIONI_PER_RICHIESTA]).decode("ascii")
            try:
                _, msg_data = mail.fetch(gruppo, f"(BODY.PEEK[HEADER.FIELDS ({INTESTAZIONI_IMAP})])")
            except imaplib.IMAP4.error:
                continue
            for parte in msg_data or []:
                if not isinstance(parte, tuple) or len(parte) < 2 or not isinstance(parte[1], bytes):
                    continue
                try:
                    msg = _email_lib.message_from_bytes(parte[1])
                    ricevuta = ricevuta_da_intestazioni(msg)
                    risultati.append(ricevuta)
                    numero = parte[0].split(b" ", 1)[0].decode("ascii", errors="ignore") if isinstance(parte[0], bytes) else ""
                    if numero.isdigit() and serve_testo(ricevuta):
                        da_leggere.append((numero, ricevuta))
                except Exception:
                    pass

        # Esiti del Ministero (controlli automatici, cancelleria): l'identificativo del deposito
        # sta nel testo o in EsitoAtto.xml (IdMsgMitt), non nell'intestazione. Sono messaggi
        # piccoli; si leggono solo quelli, mai le RdAC complete che contengono la busta.
        for numero, ricevuta in da_leggere[:_ESITI_DA_LEGGERE_MAX]:
            try:
                _, dati = mail.fetch(numero, "(BODY.PEEK[])")
                grezzo = next(
                    (p[1] for p in dati or [] if isinstance(p, tuple) and len(p) > 1 and isinstance(p[1], bytes)),
                    b"",
                )
                if grezzo and len(grezzo) <= _ESITO_BYTES_MAX:
                    completo = _email_lib.message_from_bytes(grezzo)
                    ricevuta["testo"] = testo_messaggio(completo)
                    ricevuta["mittenti_interni"] = mittenti_interni(completo)
            except (imaplib.IMAP4.error, ValueError):
                continue

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
    Stato che le ricevute COLLEGATE al deposito portano, oppure None.

    Calcolo su una copia: il deposito reale si aggiorna solo con ``applica_ricevute``.
    Le PEC senza un identificativo del deposito sono ignorate (nessun ripiego su tutta la casella).
    """
    import copy

    prova = copy.copy(dep)
    esito = applica_ricevute(prova, ricevute)
    return esito["stato"] if esito["stato"] != dep.stato else None


def _poll_pdp_deposito(
    dep: "EsitoDepositoPCT",
    credenziali_pdp: dict,
) -> str | None:
    """
    Esito di un deposito penale: non interrogabile dal software.

    Il PDP (art. 111-bis c.p.p.; D.M. 217/2023) e' una maschera web per l'avvocato autenticato con
    CNS/CIE e non espone servizi ai gestionali (pct/pdp.py, pct/penale_pdp/): l'esito si registra
    dalle ricevute lette sul portale. Il vecchio richiamo a un client inesistente falliva in
    silenzio; ora il limite e' dichiarato con un messaggio controllato e nessuno stato cambia.
    """
    if dep.id_deposito_esterno:
        logger.warning("Deposito %s: %s", dep.id, _MESSAGGIO_PDP_NON_DISPONIBILE)
    return None


def esegui_polling(
    gf: "GestioneFascicoli",
    config_pec: object | None = None,
    credenziali_pdp: dict | None = None,
    giorni_indietro: int = 30,
    timeout_seconds: int | None = None,
    fascicolo_id: str | None = None,
) -> dict:
    """
    Punto di ingresso principale per il polling scheduler.

    Args:
        gf:               GestioneFascicoli istanziato
        config_pec:       Oggetto config PEC con imap_host/imap_port/indirizzo/password
        credenziali_pdp:  Dict credenziali PDP (il PDP non ha servizi: solo messaggio controllato)
        giorni_indietro:  Finestra temporale IMAP
        fascicolo_id:     Se indicato, controlla solo i depositi di quel fascicolo

    Returns:
        dict con "controllati", "aggiornati", "errori", "pdp_non_interrogabili"
    """
    from pct.deposito_simulazione import is_simulated_deposit

    controllati = 0
    aggiornati = 0
    errori = 0
    pdp_non_interrogabili = 0

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
    if fascicolo_id is not None:
        # Un identificativo vuoto non deve allargare il controllo a tutto lo studio.
        fascicoli = [f for f in fascicoli if fascicolo_id and getattr(f, "id", "") == fascicolo_id]

    for fasc in fascicoli:
        depositi_pendenti = [
            dep for dep in (fasc.depositi_pct or [])
            if dep.stato in STATI_PENDENTI and not is_simulated_deposit(dep)
        ]
        if not depositi_pendenti:
            continue

        for dep in depositi_pendenti:
            controllati += 1

            # Penale: il PDP non e' interrogabile dal software (messaggio controllato, nessuno stato).
            if credenziali_pdp and dep.id_deposito_esterno and str(dep.fonte_portale or "").upper() == "PDP":
                _poll_pdp_deposito(dep, credenziali_pdp)
                pdp_non_interrogabili += 1
                continue

            if not ricevute_imap:
                continue
            stato_prima = dep.stato
            try:
                esito = applica_ricevute(dep, ricevute_imap)
            except Exception as e:
                logger.warning("Polling PEC deposito %s: %s", dep.id, e)
                errori += 1
                continue
            if not esito["aggiornato"]:
                continue
            try:
                gf._salva()
                aggiornati += 1
                logger.info(
                    "Deposito %s (fascicolo %s): %s -> %s (%s)",
                    dep.id, fasc.id, stato_prima, dep.stato, "; ".join(esito["eventi"]),
                )
            except Exception as e:
                logger.error("Salvataggio stato deposito %s: %s", dep.id, e)
                errori += 1

    return {
        "controllati": controllati,
        "aggiornati": aggiornati,
        "errori": errori,
        "pdp_non_interrogabili": pdp_non_interrogabili,
    }


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
        def _connect_mail():
            client = imaplib.IMAP4_SSL(
                config_pec.imap_host,
                getattr(config_pec, "imap_port", 993),
                timeout=timeout_s,
            )
            client.login(config_pec.indirizzo, config_pec.password)
            return client

        mail = run_imap_runtime_operation(_connect_mail)
        # Sola lettura: il FETCH (RFC822) su una casella aperta in scrittura segna i messaggi come letti sul
        # server PEC dello studio, che l'avvocato non vedrebbe più come nuovi nel suo programma di posta.
        mail.select("INBOX", readonly=True)

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
