"""La catena di alimentazione dell'archivio dentro l'applicazione.

Qui i due motori incontrano i dati dello studio: i testi dei documenti (nativo
dal PDF, OCR dalla cache dell'indice di ricerca, indice documentale), i
messaggi del presidio PEC con i loro allegati, le date che agenda,
scadenziario, PEC e portale già conoscono (per il collaudo). La lettura è
incrementale per costruzione: si chiede al registro delle letture quali
oggetti i motori non hanno ancora letto e si leggono solo quelli; a lettura
fatta l'oggetto è segnato e non si rilegge finché il suo contenuto non
cambia. Nessuna lettura avviene nella richiesta dell'avvocato: la lettura
automatica gira nello scheduler, in un thread di sfondo al caricamento di un
documento o al collegamento di una PEC, e nel worker OCR a testo pronto.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Iterable

from flask import current_app, g, has_app_context

from pct.archivio_letture import VERSIONE_MOTORE_DOCUMENTI, VERSIONE_MOTORE_PEC, fatti_da_allegato, fatti_da_messaggio, leggi_testo, riassunto_archivio
from pct.archivio_letture.ciclo import StatoCiclo, stato_ciclo
from pct.archivio_letture.collaudo import Contesto, contesto_da_fascicolo
from pct.registro_letture import Fatto, Oggetto, RegistroLetture
from web.services.lettura_cache import invalida_lettura
from web.services.registro_letture_runtime import (
    _righe_pec_collegate,
    aggiorna_inventario,
    registro_corrente,
    registro_per_percorsi,
    tenant_corrente,
)

logger = logging.getLogger(__name__)
LETTORE_DOCUMENTI = "motore_documenti"
LETTORE_PEC = "motore_pec"
BYTE_MASSIMI_PDF = 8_000_000
_LOCK = threading.Lock()
_IN_CORSO: set[str] = set()


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


# ---- i testi di un documento --------------------------------------------------

def _bytes_documento(fascicolo_id: str, documento: Any) -> bytes:
    try:
        from pct.document_crypto import decrypt_doc
        from web.helpers import get_fascicoli

        percorso = get_fascicoli().percorso_documento_lettura(fascicolo_id, str(documento.id))
        if not percorso.exists() or percorso.stat().st_size > BYTE_MASSIMI_PDF:
            return b""
        return decrypt_doc(percorso.read_bytes())
    except Exception:
        return b""


def _testo_nativo(fascicolo_id: str, documento: Any) -> str:
    nome = _testo(getattr(documento, "nome", "")).lower()
    if not nome.endswith(".pdf"):
        return ""
    dati = _bytes_documento(fascicolo_id, documento)
    if not dati:
        return ""
    try:
        import io

        import pdfplumber  # type: ignore

        from legal_ocr.motore.testo import _testo_nativo_affidabile

        pagine: list[str] = []
        with pdfplumber.open(io.BytesIO(dati)) as pdf:
            for pagina in pdf.pages[:12]:
                pagine.append(pagina.extract_text() or "")
        testo = "\n\n".join(parte for parte in pagine if parte.strip()).strip()
        return testo if _testo_nativo_affidabile(testo) else ""
    except Exception:
        return ""


def _testo_ocr(documento: Any) -> str:
    try:
        from web.helpers import get_indice

        return str(get_indice().get_ocr_cache(_testo(getattr(documento, "hash_sha256", ""))) or "")
    except Exception:
        return ""


def _testo_indice(fascicolo: Any, documento: Any) -> str:
    try:
        from web.services.react_fascicoli_bridge import _document_ai_texts_for_fascicolo

        return str((_document_ai_texts_for_fascicolo(fascicolo, documents=[documento]) or {}).get(str(documento.id)) or "")
    except Exception:
        return ""


def testi_documento(fascicolo: Any, documento: Any) -> list[tuple[str, str]]:
    """Le letture disponibili del documento, dalla più affidabile: (origine, testo)."""
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    letture: list[tuple[str, str]] = []
    nativo = _testo_nativo(fascicolo_id, documento)
    if nativo:
        letture.append(("nativo", nativo))
    ocr = _testo_ocr(documento)
    if ocr.strip():
        letture.append(("ocr", ocr))
    indice = _testo_indice(fascicolo, documento)
    if indice.strip() and indice.strip() != ocr.strip():
        letture.append(("indice", indice))
    return letture


# ---- le date già note (per il collaudo) ------------------------------------------

def date_note_fascicolo(fascicolo: Any, *, messaggi_pec: Iterable[dict[str, Any]] | None = None) -> dict[str, list[str]]:
    note: dict[str, list[str]] = {}
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))

    def aggiungi(valore: Any, fonte: str) -> None:
        giorno = _testo(valore)[:10]
        if len(giorno) == 10 and giorno[4] == "-":
            elenco = note.setdefault(giorno, [])
            if fonte not in elenco:
                elenco.append(fonte)

    try:
        from web.helpers import get_scadenziario

        for scadenza in get_scadenziario().tutte(id_fascicolo=fascicolo_id, solo_aperte=False):
            aggiungi(getattr(scadenza, "data_scadenza", ""), "scadenziario")
    except Exception:
        pass
    try:
        from web.helpers import get_agenda

        ruolo = f"{_testo(getattr(fascicolo, 'numero_rg', ''))}/{_testo(getattr(fascicolo, 'anno_rg', ''))}" if _testo(getattr(fascicolo, "numero_rg", "")) else ""
        for appuntamento in get_agenda().tutti():
            if _testo(getattr(appuntamento, "id_fascicolo", "")) == fascicolo_id or (ruolo and ruolo in _testo(getattr(appuntamento, "procedimento", ""))):
                aggiungi(getattr(appuntamento, "data_ora", ""), "agenda")
    except Exception:
        pass
    for documento in list(getattr(fascicolo, "documenti", []) or []):
        aggiungi(getattr(documento, "data_deposito_portale", ""), "portale")
        aggiungi(getattr(documento, "data_comunicazione_cancelleria", ""), "portale")
    for messaggio in list(messaggi_pec or []):
        for udienza in list(messaggio.get("udienze") or []):
            aggiungi(udienza.get("hearing_date"), "presidio PEC")
        for termine in list(messaggio.get("termini") or []):
            aggiungi(termine.get("dies_a_quo_date"), "presidio PEC")
    return note


def importi_noti_fascicolo(fascicolo: Any) -> dict[str, list[str]]:
    """Gli importi che il fascicolo già registra: servono al collaudo come riscontro.

    Un importo letto in una sentenza che coincide con un pagamento registrato o
    con una parcella non è più una proposta: è un dato confermato da un'altra
    fonte, e il collaudo lo verifica.
    """
    noti: dict[str, list[str]] = {}

    def aggiungi(valore: Any, fonte: str) -> None:
        try:
            numero = float(valore)
        except (TypeError, ValueError):
            return
        if numero <= 0:
            return
        elenco = noti.setdefault(f"{round(numero, 2):.2f}", [])
        if fonte not in elenco:
            elenco.append(fonte)

    for voce in list(getattr(fascicolo, "pagamenti", []) or []):
        dati = voce if isinstance(voce, dict) else getattr(voce, "__dict__", {})
        for chiave in ("importo", "importo_previsto", "importo_pagato"):
            aggiungi(dati.get(chiave) if isinstance(dati, dict) else getattr(voce, chiave, None), "pagamenti del fascicolo")
    try:
        from web.helpers import get_fatturazione

        for parcella in get_fatturazione().tutte():
            if _testo(getattr(parcella, "id_fascicolo", "")) == _testo(getattr(fascicolo, "id", "")):
                aggiungi(getattr(parcella, "totale", None), "parcella")
    except Exception:
        pass
    aggiungi(getattr(fascicolo, "valore_causa", None), "valore della causa")
    return noti


def _messaggi_pec(fascicolo: Any) -> list[dict[str, Any]]:
    try:
        from web.services.fascicolo_pec_presidio import messaggi_pec_per_fascicolo

        return messaggi_pec_per_fascicolo(fascicolo)
    except Exception:
        return []


# ---- la lettura del fascicolo -----------------------------------------------------

def _attribuisci(fatti: Iterable[Fatto], oggetto: Oggetto, motore: str) -> list[Fatto]:
    esito = []
    for fatto in fatti:
        fatto.motore, fatto.tipo, fatto.oggetto_id, fatto.sha256 = motore, oggetto.tipo, oggetto.oggetto_id, oggetto.impronta
        esito.append(fatto)
    return esito


def _leggi_documenti(fascicolo: Any, registro: RegistroLetture, tenant: str, contesto: Contesto, *, forza: bool, limite: int) -> dict[str, int]:
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    conteggi = {"da_leggere": 0, "letti": 0, "senza_testo": 0, "assenti": 0, "fatti": 0, "verificati": 0}
    da_leggere = registro.da_leggere(tenant, fascicolo_id, LETTORE_DOCUMENTI, tipi=("documento",))
    if forza:
        letti_prima = {(l.oggetto_id, l.sha256) for l in registro.letture(tenant, fascicolo_id, lettore=LETTORE_DOCUMENTI) if l.stato == "non_leggibile"}
        for oggetto in registro.oggetti(tenant, fascicolo_id):
            if oggetto.tipo == "documento" and (oggetto.oggetto_id, oggetto.impronta) in letti_prima and oggetto not in da_leggere:
                da_leggere.append(oggetto)
    conteggi["da_leggere"] = len(da_leggere)
    documenti = {str(getattr(d, "id", "")): d for d in list(getattr(fascicolo, "documenti", []) or [])}
    for oggetto in da_leggere[:limite]:
        documento = documenti.get(oggetto.oggetto_id)
        if documento is None:
            # L'oggetto è nell'inventario ma il documento non c'è più: senza questa
            # chiusura resterebbe «da leggere» per sempre e la lettura automatica
            # non risulterebbe mai completa.
            conteggi["assenti"] += 1
            registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE_DOCUMENTI, stato="non_leggibile", esito={"motivo": "documento non più presente nel fascicolo"}, versione=VERSIONE_MOTORE_DOCUMENTI)
            continue
        letture = testi_documento(fascicolo, documento)
        if not letture:
            conteggi["senza_testo"] += 1
            registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE_DOCUMENTI, stato="non_leggibile", esito={"motivo": "nessun testo disponibile: in attesa dell'OCR"}, versione=VERSIONE_MOTORE_DOCUMENTI)
            continue
        origine, testo = letture[0]
        contesto_documento = Contesto(oggi=contesto.oggi, anno_riferimento=contesto.anno_riferimento, data_minima=contesto.data_minima, numero_rg=contesto.numero_rg, anno_rg=contesto.anno_rg, date_note=contesto.date_note, importi_noti=contesto.importi_noti)
        if len(letture) > 1:
            contesto_documento.testo_secondario, contesto_documento.etichetta_secondario = letture[1][1], {"ocr": "lettura OCR", "indice": "indice documentale", "nativo": "testo nativo del PDF"}[letture[1][0]]
        metadata = {"tipo_documento": _testo(getattr(documento, "tipo", "")), "classification": _testo(getattr(documento, "classificazione_portale", ""))}
        fatti = _attribuisci(leggi_testo(testo, origine=origine, contesto=contesto_documento, nome=oggetto.nome, metadata=metadata), oggetto, "documenti")
        registro.registra_fatti(tenant, fascicolo_id, oggetto, "documenti", fatti, versione=VERSIONE_MOTORE_DOCUMENTI)
        registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE_DOCUMENTI, esito={"origine": origine, "letture": [o for o, _ in letture], "fatti": len(fatti), "verificati": sum(1 for f in fatti if f.verifica == "verificata")}, versione=VERSIONE_MOTORE_DOCUMENTI)
        conteggi["letti"] += 1
        conteggi["fatti"] += len(fatti)
        conteggi["verificati"] += sum(1 for f in fatti if f.verifica == "verificata")
    return conteggi


def _leggi_pec(fascicolo: Any, registro: RegistroLetture, tenant: str, contesto: Contesto, messaggi: list[dict[str, Any]], *, limite: int) -> dict[str, int]:
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    conteggi = {"da_leggere": 0, "letti": 0, "assenti": 0, "fatti": 0, "verificati": 0}
    da_leggere = registro.da_leggere(tenant, fascicolo_id, LETTORE_PEC, tipi=("pec", "allegato_pec"))
    conteggi["da_leggere"] = len(da_leggere)
    per_id = {str(m.get("id")): m for m in messaggi}
    allegati: dict[str, dict[str, Any]] = {}
    if any(o.tipo == "allegato_pec" for o in da_leggere):
        for riga in _righe_pec_collegate(fascicolo_id):
            for allegato in list(riga.get("allegati") or []):
                allegati[str(allegato.get("id") or "")] = allegato
    for oggetto in da_leggere[:limite]:
        if oggetto.tipo == "pec":
            messaggio = per_id.get(oggetto.oggetto_id)
            if messaggio is None:
                # Il messaggio non è più collegato al fascicolo: si chiude la lettura
                # invece di lasciare l'oggetto in attesa a ogni giro.
                conteggi["assenti"] += 1
                registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE_PEC, stato="non_leggibile", esito={"motivo": "messaggio PEC non più collegato al fascicolo"}, versione=VERSIONE_MOTORE_PEC)
                continue
            fatti = _attribuisci(fatti_da_messaggio(messaggio, contesto), oggetto, "pec")
        else:
            allegato = allegati.get(oggetto.oggetto_id)
            testo = str((allegato or {}).get("ocr_text") or "")
            if not testo.strip():
                motivo = "allegato senza testo letto dal presidio PEC" if allegato is not None else "allegato non più presente nella PEC collegata"
                if allegato is None:
                    conteggi["assenti"] += 1
                registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE_PEC, stato="non_leggibile", esito={"motivo": motivo}, versione=VERSIONE_MOTORE_PEC)
                continue
            fatti = _attribuisci(fatti_da_allegato(testo, nome=oggetto.nome, contesto=contesto), oggetto, "pec")
        registro.registra_fatti(tenant, fascicolo_id, oggetto, "pec", fatti, versione=VERSIONE_MOTORE_PEC)
        registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE_PEC, esito={"fatti": len(fatti), "verificati": sum(1 for f in fatti if f.verifica == "verificata")}, versione=VERSIONE_MOTORE_PEC)
        conteggi["letti"] += 1
        conteggi["fatti"] += len(fatti)
        conteggi["verificati"] += sum(1 for f in fatti if f.verifica == "verificata")
    return conteggi


def _ricollauda_plausibili(fascicolo: Any, registro: RegistroLetture, tenant: str, contesto: Contesto) -> int:
    """I fatti plausibili si riprovano con le date note di oggi: una concordanza nuova li verifica."""
    from pct.archivio_letture import collauda

    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    promossi = 0
    per_oggetto: dict[tuple[str, str, str, str], list[Fatto]] = {}
    for fatto in registro.fatti(tenant, fascicolo_id, verifiche=("plausibile",)):
        if fatto.categoria != "data" or fatto.valore.split("T")[0] not in contesto.date_note:
            continue
        per_oggetto.setdefault((fatto.tipo, fatto.oggetto_id, fatto.sha256, fatto.motore), []).append(fatto)
    for (tipo, oggetto_id, sha, motore), plausibili in per_oggetto.items():
        tutti = [f for f in registro.fatti_oggetto(tenant, tipo, oggetto_id) if f.sha256 == sha and f.motore == motore]
        cambiato = False
        for fatto in tutti:
            if any(fatto.id == p.id for p in plausibili):
                fatto.prove = [p for p in fatto.prove if p.get("codice") not in {"orizzonte", "doppia_lettura", "concordanza"}]
                fatto.verifica = "plausibile"
                collauda(fatto, contesto)
                if fatto.verifica == "verificata":
                    promossi += 1
                    cambiato = True
        if cambiato:
            oggetto = Oggetto(tipo=tipo, oggetto_id=oggetto_id, sha256=sha if not sha.startswith(("archivio:", "dimensione:")) else "", sha256_archivio=sha[9:] if sha.startswith("archivio:") else "", dimensione=int(sha[11:]) if sha.startswith("dimensione:") else 0)
            registro.registra_fatti(tenant, fascicolo_id, oggetto, motore, tutti, versione=VERSIONE_MOTORE_DOCUMENTI if motore == "documenti" else VERSIONE_MOTORE_PEC)
    return promossi


def _riconvalida(fascicolo: Any, registro: RegistroLetture, tenant: str) -> dict[str, int]:
    """Le regole di oggi ripassano ciò che è già registrato: niente resta aperto per una regola superata.

    Chi ha già letto un documento non lo rilegge; ma le anomalie e i fatti
    registrati con regole più larghe vanno riportati alle regole correnti,
    altrimenti l'avvocato continua a vedere conferme che il software oggi non
    chiederebbe più.
    """
    from pct.registro_letture.riconvalida import contesto_riconvalida

    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    esito = {"anomalie": 0, "fatti": 0}
    try:
        esito["anomalie"] = len(registro.chiudi_anomalie_superate(tenant, fascicolo_id, contesto=contesto_riconvalida(fascicolo)))
    except Exception as exc:
        logger.debug("Riconvalida delle anomalie non riuscita per %s: %s", fascicolo_id, exc)
    try:
        esito["fatti"] = len(registro.riconvalida_fatti(tenant, fascicolo_id))
    except Exception as exc:
        logger.debug("Riconvalida dei fatti non riuscita per %s: %s", fascicolo_id, exc)
    return esito


def _impronta_viva(fascicolo: Any) -> str:
    """L'impronta dell'inventario corrente: documenti e PEC collegate, senza aprire file.

    Si basa sui metadati che il fascicolo già porta (identificativo, impronta
    SHA-256 del documento, dimensione) e sulle PEC collegate: cambia appena un
    documento viene aggiunto, sostituito o rimosso, o appena arriva una PEC.
    """
    from pct.registro_letture import impronta_inventario
    from web.services.registro_letture_runtime import inventario_fascicolo

    try:
        return impronta_inventario(inventario_fascicolo(fascicolo, con_pec=True))
    except Exception as exc:
        logger.debug("Impronta del fascicolo non calcolata per %s: %s", getattr(fascicolo, "id", ""), exc)
        return ""


def stato_ciclo_fascicolo(fascicolo_id: str, registro: RegistroLetture, tenant: str, *, impronta: str = "") -> StatoCiclo:
    """Dove sta il fascicolo nel ciclo dei due motori: fermo, da leggere o in errore."""
    riga = dict(registro.impronta_fascicolo(tenant, fascicolo_id, LETTORE_DOCUMENTI) or {})
    if riga.get("esito_json") and "esito" not in riga:
        import json

        try:
            riga["esito"] = json.loads(str(riga.get("esito_json") or "{}"))
        except (TypeError, ValueError):
            riga["esito"] = {}
    return stato_ciclo(riga or None, versione_attesa=VERSIONE_MOTORE_DOCUMENTI, impronta_attesa=impronta)


def _mancanti_motori(registro: RegistroLetture, tenant: str, fascicolo_id: str) -> tuple[int, int]:
    """Oggetti ancora non letti dai due motori, anche se la riga ciclo dice fermo."""
    try:
        stato = registro.stato_fascicolo(tenant, fascicolo_id, lettori=(LETTORE_DOCUMENTI, LETTORE_PEC))
    except Exception as exc:
        logger.debug("Stato oggetti dei motori non leggibile per %s: %s", fascicolo_id, exc)
        return 0, 0
    mancanti = sum(int(voce.da_leggere or 0) for voce in stato.lettori)
    errori = sum(int(voce.errori or 0) for voce in stato.lettori)
    return mancanti, errori


def _segna_ciclo(registro: RegistroLetture, tenant: str, fascicolo_id: str, *, impronta: str, totali: int, letti: int, stato: str, motivo: str = "") -> None:
    """Scrive nell'archivio dove è arrivato il ciclo: è la conferma che chiude il giro."""
    try:
        registro.segna_fascicolo(
            tenant, fascicolo_id, LETTORE_DOCUMENTI,
            impronta=impronta, oggetti_totali=totali, oggetti_letti=letti,
            stato=stato, versione=VERSIONE_MOTORE_DOCUMENTI,
            esito={"motivo": motivo} if motivo else {},
        )
    except Exception as exc:
        logger.debug("Stato del ciclo non registrato per %s: %s", fascicolo_id, exc)


def _consegna_ai_presidi(fascicolo: Any, registro: RegistroLetture) -> dict[str, Any]:
    """L'archivio consegna ai presìdi che scrivono; un guasto qui non ferma il ciclo."""
    try:
        from web.services.consegna_presidi_runtime import consegna_fascicolo

        return consegna_fascicolo(fascicolo, registro=registro)
    except Exception as exc:
        logger.exception("Consegna ai presìdi non riuscita per il fascicolo %s", getattr(fascicolo, "id", ""))
        return {"errore": f"{type(exc).__name__}: {exc}"[:200], "consegnati": 0, "non_pertinenti": 0, "rifiutati": 0}


def leggi_fascicolo(fascicolo: Any, *, forza: bool = False, limite: int = 200, registro: RegistroLetture | None = None) -> dict[str, Any]:
    """Un giro del ciclo: i motori leggono solo ciò che manca, l'archivio conferma, poi ci si ferma.

    Il ciclo è chiuso: quando tutto è letto e l'archivio ha confermato, il
    fascicolo resta **fermo** e questa funzione non apre più nulla. Si riattiva
    su un documento nuovo, su un documento cambiato, su una PEC nuova, quando
    cambiano le regole di un motore, o al ricontrollo periodico che fa da rete
    di sicurezza se un evento è andato perso.
    """
    registro = registro or registro_corrente()
    tenant = tenant_corrente()
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    if not fascicolo_id:
        return {"documenti": {}, "pec": {}, "promossi": 0, "ciclo": {}}
    if not forza:
        # L'impronta si calcola dal fascicolo vivo — dai metadati dei documenti e
        # dalle PEC collegate, senza aprire alcun file — e si confronta con quella
        # che l'archivio ha confermato: se coincidono il ciclo è fermo e qui non
        # si fa nulla. Confrontare l'archivio con sé stesso non vedrebbe mai un
        # documento nuovo.
        prima = stato_ciclo_fascicolo(fascicolo_id, registro, tenant, impronta=_impronta_viva(fascicolo))
        mancanti_motori, errori_motori = _mancanti_motori(registro, tenant, fascicolo_id)
        if not prima.da_leggere and not mancanti_motori and not errori_motori:
            return {
                "inventario": {},
                "documenti": {"da_leggere": 0, "letti": 0, "senza_testo": 0, "assenti": 0, "fatti": 0, "verificati": 0},
                "pec": {"da_leggere": 0, "letti": 0, "assenti": 0, "fatti": 0, "verificati": 0},
                "promossi": 0, "riconvalidati": {"anomalie": 0, "fatti": 0}, "restano": 0,
                "fermo": True, "ciclo": prima.to_dict(),
            }
        if not prima.da_leggere:
            logger.info(
                "Ciclo letture riaperto per %s: riga fascicolo ferma ma oggetti mancanti=%s errori=%s",
                fascicolo_id, mancanti_motori, errori_motori,
            )
    try:
        inventario = aggiorna_inventario(fascicolo, registro=registro, con_pec=True)
        messaggi = _messaggi_pec(fascicolo)
        contesto = contesto_da_fascicolo(fascicolo, date_note=date_note_fascicolo(fascicolo, messaggi_pec=messaggi))
        contesto.importi_noti = importi_noti_fascicolo(fascicolo)
        riconvalidati = _riconvalida(fascicolo, registro, tenant)
        documenti = _leggi_documenti(fascicolo, registro, tenant, contesto, forza=forza, limite=limite)
        pec = _leggi_pec(fascicolo, registro, tenant, contesto, messaggi, limite=limite)
        promossi = _ricollauda_plausibili(fascicolo, registro, tenant, contesto)
    except Exception as exc:
        # Il fascicolo non esce dal ciclo: resta in errore dichiarato e si riprova.
        logger.exception("Giro del ciclo non riuscito per il fascicolo %s", fascicolo_id)
        _segna_ciclo(registro, tenant, fascicolo_id, impronta="", totali=0, letti=0, stato="errore", motivo=f"{type(exc).__name__}: {exc}"[:300])
        raise
    # Seconda gamba della catena: l'archivio consegna ai presìdi che scrivono, e
    # loro confermano. Un fatto già consegnato non viene riproposto.
    consegne = _consegna_ai_presidi(fascicolo, registro)
    if documenti["letti"] or pec["letti"] or promossi or riconvalidati["anomalie"] or riconvalidati["fatti"]:
        invalida_lettura(fascicolo_id)
    chiusi_documenti = documenti["letti"] + documenti["senza_testo"] + documenti["assenti"]
    chiusi_pec = pec["letti"] + pec["assenti"]
    restano = max(0, documenti["da_leggere"] - chiusi_documenti) + max(0, pec["da_leggere"] - chiusi_pec)
    # L'archivio conferma: il ciclo si chiude quando non resta nulla da leggere.
    impronta = _impronta_viva(fascicolo)
    _segna_ciclo(
        registro, tenant, fascicolo_id,
        impronta=impronta, totali=len(registro.oggetti(tenant, fascicolo_id)),
        letti=chiusi_documenti + chiusi_pec,
        stato="completa" if restano == 0 else "parziale",
        motivo="" if restano == 0 else f"{restano} oggetti oltre il tetto di questo giro",
    )
    dopo = stato_ciclo_fascicolo(fascicolo_id, registro, tenant, impronta=impronta)
    return {
        "inventario": inventario, "documenti": documenti, "pec": pec, "promossi": promossi, "riconvalidati": riconvalidati,
        "consegne": consegne, "restano": restano, "fermo": restano == 0, "ciclo": dopo.to_dict(),
    }


def fatti_fascicolo(fascicolo: Any, **filtri: Any) -> list[Fatto]:
    """I fatti utili del fascicolo dall'archivio (mai una lettura in questa chiamata)."""
    canonico = bool(filtri.pop("canonico", True))
    try:
        fatti = registro_corrente().fatti(tenant_corrente(), _testo(getattr(fascicolo, "id", "")), **filtri)
        if not canonico or filtri.get("motore") or filtri.get("tipo"):
            return fatti
        from pct.archivio_letture import fatti_canonici

        return fatti_canonici(fatti)
    except Exception as exc:
        logger.debug("Archivio delle letture non disponibile per %s: %s", getattr(fascicolo, "id", ""), exc)
        return []


MOTIVI_IN_ATTESA = {
    "da_leggere": "non ancora letto dai motori",
    "da_rileggere": "il contenuto è cambiato: va riletto",
    "in_corso": "lettura in corso",
    "errore": "la lettura precedente è fallita",
}


def oggetti_in_attesa(stato: Any, *, letture: Iterable[Any] = ()) -> list[dict[str, str]]:
    """Gli oggetti che i motori devono ancora leggere, con il motivo in italiano.

    Il pannello deve poter dire *quale* oggetto manca e perché: «la lettura
    automatica deve ancora leggere 1 oggetto» senza dire quale non è una
    informazione utilizzabile dall'avvocato.
    """
    motivi_registrati = {
        (lettura.tipo, lettura.oggetto_id, lettura.lettore): _testo((lettura.esito or {}).get("motivo"))
        for lettura in letture
    }
    in_attesa: list[dict[str, str]] = []
    for riga in list(getattr(stato, "per_oggetto", []) or []):
        for lettore, stato_lettura in dict(riga.get("letture") or {}).items():
            if lettore not in {LETTORE_DOCUMENTI, LETTORE_PEC} or stato_lettura not in MOTIVI_IN_ATTESA:
                continue
            registrato = motivi_registrati.get((str(riga.get("tipo") or ""), str(riga.get("oggetto_id") or ""), lettore))
            in_attesa.append({
                "tipo": str(riga.get("tipo") or ""),
                "oggetto_id": str(riga.get("oggetto_id") or ""),
                "nome": str(riga.get("nome") or "") or str(riga.get("oggetto_id") or ""),
                "motore": "documenti" if lettore == LETTORE_DOCUMENTI else "PEC",
                "motivo": registrato or MOTIVI_IN_ATTESA[stato_lettura],
            })
    return in_attesa


def stato_archivio_payload(fascicolo: Any, *, registro: RegistroLetture | None = None) -> dict[str, Any]:
    """Il riquadro dell'archivio nel pannello «Letture e verifiche»."""
    from pct.formatting import format_datetime_it

    registro = registro or registro_corrente()
    tenant = tenant_corrente()
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    from pct.archivio_letture import fatti_canonici

    fatti = fatti_canonici(registro.fatti(tenant, fascicolo_id, verifiche=None))
    riassunto = riassunto_archivio(fatti)
    stato = registro.stato_fascicolo(tenant, fascicolo_id, lettori=(LETTORE_DOCUMENTI, LETTORE_PEC))
    lettori = {voce.lettore: voce for voce in stato.lettori}
    ultima = max([voce.ultima_lettura for voce in stato.lettori] + [""])
    da_leggere = sum(voce.da_leggere + voce.errori for voce in stato.lettori)
    in_attesa = oggetti_in_attesa(stato, letture=registro.letture(tenant, fascicolo_id))
    with _LOCK:
        in_corso = fascicolo_id in _IN_CORSO
    riassunto.update({
        "versione": {"documenti": VERSIONE_MOTORE_DOCUMENTI, "pec": VERSIONE_MOTORE_PEC},
        "lettura_automatica": {
            "in_corso": in_corso,
            "da_leggere": da_leggere,
            "completa": da_leggere == 0 and not in_corso,
            "ultima_lettura": ultima,
            "ultima_lettura_it": format_datetime_it(ultima) if ultima else "",
            "documenti": {"letti": lettori[LETTORE_DOCUMENTI].letti, "da_leggere": lettori[LETTORE_DOCUMENTI].da_leggere} if LETTORE_DOCUMENTI in lettori else {},
            "pec": {"letti": lettori[LETTORE_PEC].letti, "da_leggere": lettori[LETTORE_PEC].da_leggere} if LETTORE_PEC in lettori else {},
            "in_attesa": in_attesa,
        },
        "collaudo_lettore": collaudo_lettore_payload(),
    })
    return riassunto


def decidi_fatto(fatto_id: str, *, esito: str, valore: str = "", registro: RegistroLetture | None = None) -> dict[str, Any]:
    """L'avvocato conferma («verificata»), corregge («corretta», con il valore giusto) o ignora un fatto dell'archivio."""
    from web.services.registro_letture_runtime import utente_corrente_id

    registro = registro or registro_corrente()
    verifica = {"confermata": "verificata", "verificata": "verificata", "corretta": "corretta", "ignorata": "ignorata"}.get(_testo(esito).lower(), "")
    if not verifica:
        raise ValueError("Esito non valido.")
    valore_iso = ""
    if verifica == "corretta":
        from pct.registro_letture.verifica_date import interpreta_data

        data = interpreta_data(valore)
        if data is None:
            raise ValueError("Per correggere serve una data nel formato gg/mm/aaaa.")
        valore_iso = data.isoformat()
    fatto = registro.decidi_fatto(tenant_corrente(), fatto_id, verifica=verifica, valore=valore_iso, utente_id=utente_corrente_id())
    if fatto.fascicolo_id:
        invalida_lettura(fatto.fascicolo_id)
    return fatto.to_dict()


def collaudo_lettore_payload() -> dict[str, Any]:
    try:
        from legal_ocr.collaudo import ultimo_esito

        return ultimo_esito(percorso_collaudo())
    except Exception:
        return {"eseguito": False}


def percorso_collaudo() -> Path:
    base = ""
    if has_app_context():
        base = _testo(current_app.config.get("SEARCH_INDEX"))
    return Path(base).resolve().parent.parent / "intelligence" / "collaudo_lettore.json" if base else Path("./data/intelligence/collaudo_lettore.json")


# ---- la lettura in sfondo e la lettura automatica ------------------------------------

def avvia_lettura_in_background(app: Any, fascicolo_id: str, *, paths: dict[str, Any] | None = None, tenant_slug: str = "", forza: bool = False) -> bool:
    """Un documento caricato o una PEC collegata: i motori leggono l'oggetto nuovo in un thread, mai nella richiesta."""
    fascicolo_id = _testo(fascicolo_id)
    if not fascicolo_id:
        return False
    with _LOCK:
        if fascicolo_id in _IN_CORSO:
            return False
        _IN_CORSO.add(fascicolo_id)

    def corsa() -> None:
        try:
            with app.test_request_context("/__archivio-letture/" + fascicolo_id):
                g.data_paths = dict(paths or {})
                g.tenant = None
                g.tenant_context_slug = tenant_slug
                g.tenant_context_required = False
                g.tenant_context_missing = False
                g.storage_runtime = None
                if tenant_slug and app.config.get("MULTI_TENANT"):
                    try:
                        from pct.tenant import GestioneTenant

                        g.tenant = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"]).get(tenant_slug)
                    except Exception:
                        g.tenant = None
                from web.helpers import get_fascicoli

                fascicolo = get_fascicoli().get(fascicolo_id)
                if fascicolo is not None:
                    leggi_fascicolo(fascicolo, forza=forza)
        except Exception:
            logger.exception("Lettura in sfondo del fascicolo %s interrotta", fascicolo_id)
        finally:
            with _LOCK:
                _IN_CORSO.discard(fascicolo_id)

    threading.Thread(target=corsa, name=f"archivio-letture-{fascicolo_id}", daemon=True).start()
    return True


def _contesto_corrente() -> tuple[dict[str, Any], str]:
    if not has_app_context():
        return {}, ""
    return dict(getattr(g, "data_paths", {}) or {}), _testo(getattr(g, "tenant_context_slug", ""))


def lettura_dopo_evento(fascicolo_id: str) -> bool:
    """Chiamata dagli eventi del registro (documento caricato, PEC collegata): parte il thread se c'è un'app."""
    if not has_app_context():
        return False
    paths, slug = _contesto_corrente()
    try:
        return avvia_lettura_in_background(current_app._get_current_object(), fascicolo_id, paths=paths, tenant_slug=slug)
    except Exception as exc:
        logger.debug("Lettura in sfondo non avviata per %s: %s", fascicolo_id, exc)
        return False


def lettura_automatica_corrente(*, limite_oggetti: int = 150) -> dict[str, Any]:
    """Tutti i fascicoli dello studio corrente: legge solo ciò che manca, entro un tetto di oggetti per giro."""
    from web.helpers import get_fascicoli

    registro = registro_corrente()
    fascicoli = list(get_fascicoli().tutti(archiviati=True))
    report = {"fascicoli": len(fascicoli), "esaminati": 0, "documenti_letti": 0, "pec_lette": 0, "fatti": 0, "verificati": 0, "promossi": 0, "senza_testo": 0, "restano": 0}
    residuo = max(1, int(limite_oggetti))
    # Prima i fascicoli aperti, poi gli archiviati.
    fascicoli.sort(key=lambda f: (1 if _testo(getattr(getattr(f, "stato", ""), "value", getattr(f, "stato", ""))).upper() == "ARCHIVIATO" else 0, _testo(getattr(f, "id", ""))))
    for fascicolo in fascicoli:
        if residuo <= 0:
            report["restano"] += 1
            continue
        try:
            esito = leggi_fascicolo(fascicolo, limite=residuo, registro=registro)
        except Exception as exc:
            logger.warning("Lettura automatica non completata per il fascicolo %s: %s", getattr(fascicolo, "id", ""), exc)
            continue
        report["esaminati"] += 1
        documenti = esito.get("documenti") or {}
        pec = esito.get("pec") or {}
        documenti_letti = int(documenti.get("letti") or 0)
        pec_lette = int(pec.get("letti") or 0)
        senza_testo = int(documenti.get("senza_testo") or 0)
        letti = documenti_letti + pec_lette
        residuo -= letti + senza_testo
        report["documenti_letti"] += documenti_letti
        report["pec_lette"] += pec_lette
        report["fatti"] += int(documenti.get("fatti") or 0) + int(pec.get("fatti") or 0)
        report["verificati"] += int(documenti.get("verificati") or 0) + int(pec.get("verificati") or 0)
        report["promossi"] += int(esito["promossi"])
        report["senza_testo"] += senza_testo
        report["restano"] += int(esito["restano"])
    return report


def lettura_automatica_per_tutti(app: Any, *, limite_oggetti: int = 150) -> dict[str, Any]:
    """Il job dello scheduler: ogni studio attivo, con il suo contesto tenant-aware."""
    from web.services.fascicoli_presidi_runtime import _active_tenants, _attach_tenant_context

    totali = {"fascicoli": 0, "esaminati": 0, "documenti_letti": 0, "pec_lette": 0, "fatti": 0, "verificati": 0, "promossi": 0, "senza_testo": 0, "restano": 0}
    studi: list[dict[str, Any]] = []
    attivi = _active_tenants(app)
    if attivi:
        from pct.tenant import GestioneTenant

        manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        for studio in attivi:
            slug = _testo(getattr(studio, "slug", "")).lower()
            with app.test_request_context(f"/__scheduler/archivio-letture/{slug}"):
                _attach_tenant_context(manager, studio)
                report = lettura_automatica_corrente(limite_oggetti=limite_oggetti)
            studi.append({"tenant": slug, **report})
    elif app.config.get("MULTI_TENANT"):
        return {"ok": False, "job": "archivio_letture_automatico", "error": "nessuno studio attivo: la lettura automatica non ha fascicoli su cui lavorare", "tenants": [], "totals": totali}
    else:
        with app.test_request_context("/__scheduler/archivio-letture/default"):
            g.multi_tenant_enabled = False
            g.tenant_context_missing = False
            g.tenant_context_slug = ""
            report = lettura_automatica_corrente(limite_oggetti=limite_oggetti)
        studi.append({"tenant": "default", **report})
    for voce in studi:
        for chiave in totali:
            totali[chiave] += int(voce.get(chiave) or 0)
    return {"ok": True, "job": "archivio_letture_automatico", "tenants": studi, "totals": totali}


def registra_lettura_ocr_nell_archivio(job: Any, testo: str) -> int:
    """Il worker OCR, a testo pronto, alimenta l'archivio da solo (senza Flask): il motore documenti legge quel documento."""
    registro_path = _testo(getattr(job, "registro_path", ""))
    if not registro_path or not str(testo or "").strip():
        return 0
    try:
        import os

        from pct.fascicoli import GestioneFascicoli

        registro = registro_per_percorsi({"REGISTRO_LETTURE_DB": registro_path})
        tenant = _testo(getattr(job, "tenant_id", ""))
        oggetto = registro.oggetto(tenant, job.id_fasc, "documento", job.id_doc)
        if oggetto is None:
            oggetto = Oggetto(tipo="documento", oggetto_id=job.id_doc, nome=job.nome_doc, sha256_archivio=job.hash_sha256)
            registro.registra_inventario(tenant, job.id_fasc, [oggetto], tipi=())
        fascicolo: Any = {}
        db_path = _testo(os.getenv("PCT_FASCICOLI_DB", ""))
        if db_path:
            try:
                fascicolo = GestioneFascicoli(db_path=db_path, documents_dir=_testo(os.getenv("PCT_FASCICOLI_DOCS", str(Path(db_path).resolve().parent / "documenti"))), archive_dir=_testo(os.getenv("PCT_FASCICOLI_ARCH", str(Path(db_path).resolve().parent / "archivio")))).get(job.id_fasc) or {}
            except Exception:
                fascicolo = {}
        contesto = contesto_da_fascicolo(fascicolo)
        fatti = _attribuisci(leggi_testo(testo, origine="ocr", contesto=contesto, nome=job.nome_doc), oggetto, "documenti")
        registro.registra_fatti(tenant, job.id_fasc, oggetto, "documenti", fatti, versione=VERSIONE_MOTORE_DOCUMENTI)
        registro.segna_letto(tenant, job.id_fasc, oggetto, LETTORE_DOCUMENTI, esito={"origine": "ocr", "fatti": len(fatti), "verificati": sum(1 for f in fatti if f.verifica == "verificata")}, versione=VERSIONE_MOTORE_DOCUMENTI)
        return len(fatti)
    except Exception as exc:
        logger.debug("Archivio non alimentato dal job OCR %s: %s", getattr(job, "id", ""), exc)
        return 0


__all__ = [
    "LETTORE_DOCUMENTI", "LETTORE_PEC", "avvia_lettura_in_background", "collaudo_lettore_payload", "date_note_fascicolo", "decidi_fatto", "fatti_fascicolo", "importi_noti_fascicolo",
    "leggi_fascicolo", "lettura_automatica_corrente", "lettura_automatica_per_tutti", "lettura_dopo_evento", "percorso_collaudo",
    "registra_lettura_ocr_nell_archivio", "stato_archivio_payload", "testi_documento",
]
